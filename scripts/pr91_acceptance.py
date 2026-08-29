#!/usr/bin/env python3
"""Fail-closed controlled-host acceptance harness for PR #91.

This helper does not weaken or replace issue #37. It automates the positive
controlled-Docker path, independently checks the emitted ResultManifest bundle,
and can execute the required negative A-E runtime matrix using temporary WorkUnit
variants on an explicitly controlled host.

The harness can be reviewed/tested without Docker via ``self-test``. Real
``preflight``, ``run-positive``, and ``run-negatives`` commands require Docker.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

EXPECTED_PR91_HEAD = "d638a2f78e4a89353b98e91052233e365f56f90a"
EXPECTED_NODE_CI_RUN = 33183974768
EXPECTED_PHASE0_CI_RUN = 33183974817
DEFAULT_IMAGE = "python:3.12-alpine"
NEGATIVE_IMAGE = "alpine:3.20"
DEFAULT_WORK_UNIT = "node/examples/work-unit.canonical-smoke.json"
DEFAULT_OUTPUT = "/tmp/idkmesh-node-acceptance"
DEFAULT_NEGATIVE_OUTPUT = "/tmp/idkmesh-node-negative-acceptance"
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REPO_DIGEST_RE = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")
NEGATIVE_CASES = ("A", "B", "C", "D", "E")


class AcceptanceError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcceptanceError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 300.0,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AcceptanceError(f"command timed out: {' '.join(command)}") from exc
    if proc.returncode != 0 and not allow_failure:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise AcceptanceError(f"command failed: {' '.join(command)}\n{detail}")
    return proc


def command_observation(command: list[str], proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _image_repository(reference: str) -> str:
    without_digest = reference.split("@", 1)[0]
    last_slash = without_digest.rfind("/")
    last_colon = without_digest.rfind(":")
    if last_colon > last_slash:
        return without_digest[:last_colon]
    return without_digest


def parse_image_inspect(payload: str, configured_reference: str) -> tuple[str, str]:
    try:
        documents = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AcceptanceError("docker image inspect returned invalid JSON") from exc
    if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
        raise AcceptanceError("docker image inspect must return exactly one image object")

    document = documents[0]
    image_id = document.get("Id")
    repo_digests = document.get("RepoDigests") or []
    if not isinstance(image_id, str) or not IMAGE_ID_RE.fullmatch(image_id.lower()):
        raise AcceptanceError("docker image inspect did not return an immutable sha256 image ID")
    if not isinstance(repo_digests, list):
        raise AcceptanceError("docker image inspect RepoDigests must be an array")

    repository = _image_repository(configured_reference)
    matches = sorted(
        item.lower()
        for item in repo_digests
        if isinstance(item, str)
        and REPO_DIGEST_RE.fullmatch(item.lower())
        and item.split("@", 1)[0] == repository
    )
    if not matches:
        raise AcceptanceError(
            "configured image has no matching immutable repository digest; "
            "pre-pull the expected registry image instead of relying on a local retag"
        )
    return image_id.lower(), matches[0]


def git_head(repo: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=repo, timeout=20).stdout.strip()


def preflight(repo: Path, image: str) -> dict[str, Any]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise AcceptanceError(f"not a Git checkout: {repo}")
    head = git_head(repo)
    if head != EXPECTED_PR91_HEAD:
        raise AcceptanceError(
            f"wrong PR #91 head: observed {head}, expected {EXPECTED_PR91_HEAD}; "
            "do not carry runtime acceptance across candidate-head changes"
        )
    if sys.version_info < (3, 11):
        raise AcceptanceError("Python 3.11+ is required")
    for tool in ("git", "docker"):
        if shutil.which(tool) is None:
            raise AcceptanceError(f"missing required controlled-host tool: {tool}")

    docker_version = run(["docker", "--version"], timeout=20).stdout.strip()
    inspect = run(["docker", "image", "inspect", image], timeout=30)
    image_id, repo_digest = parse_image_inspect(inspect.stdout, image)

    return {
        "tested_pr": 91,
        "tested_head": head,
        "required_ci": {
            "idkmesh_node_ci": EXPECTED_NODE_CI_RUN,
            "phase0_schema_check": EXPECTED_PHASE0_CI_RUN,
        },
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "docker": docker_version,
        },
        "container": {
            "configured_image": image,
            "resolved_image_id": image_id,
            "resolved_repo_digest": repo_digest,
        },
    }


def normalize_diff_path(raw: str) -> str | None:
    raw = raw.strip().split("\t", 1)[0]
    if raw == "/dev/null":
        return None
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise AcceptanceError(f"unsafe unified-diff path: {raw!r}")
    return path.as_posix()


def parse_patch_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for line in text.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            normalized = normalize_diff_path(line[4:])
            if normalized:
                paths.add(normalized)
    if not paths and text.strip():
        raise AcceptanceError("non-empty patch contained no parseable unified-diff paths")
    return sorted(paths)


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def scope_errors(work_unit: dict[str, Any], paths: list[str]) -> list[str]:
    constraints = work_unit.get("constraints") or {}
    permissions = work_unit.get("permissions") or {}
    allowed = list(constraints.get("allowed_paths") or [])
    forbidden = list(constraints.get("forbidden_paths") or [])
    writable = list(permissions.get("filesystem_write") or [])
    errors: list[str] = []
    for path in paths:
        if matches(path, forbidden):
            errors.append(f"forbidden path observed: {path}")
        if not matches(path, allowed):
            errors.append(f"path outside constraints.allowed_paths: {path}")
        if not matches(path, writable):
            errors.append(f"path outside permissions.filesystem_write: {path}")
    return errors


def find_artifact(manifest: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    for artifact in manifest.get("produced_artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("id") == artifact_id:
            return artifact
    return None


def find_log(manifest: dict[str, Any], log_type: str) -> dict[str, Any] | None:
    for log in manifest.get("logs") or []:
        if isinstance(log, dict) and log.get("type") == log_type:
            return log
    return None


def _require_empty_list(errors: list[str], owner: dict[str, Any], key: str) -> None:
    value = owner.get(key)
    if value != []:
        errors.append(f"{key} must be an empty array, observed {value!r}")


def validate_positive_bundle(
    *,
    repo: Path,
    bundle: Path,
    expected_image: str,
    expected_image_id: str,
    expected_repo_digest: str,
) -> dict[str, Any]:
    repo = repo.resolve()
    bundle = bundle.resolve()
    work_unit = load_json(repo / DEFAULT_WORK_UNIT)
    manifest_path = bundle / "result-manifest.json"
    patch_path = bundle / "changes.patch"
    stdout_path = bundle / "stdout.txt"
    stderr_path = bundle / "stderr.txt"
    for path in (manifest_path, patch_path, stdout_path, stderr_path):
        if not path.is_file():
            raise AcceptanceError(f"missing positive evidence file: {path}")

    manifest = load_json(manifest_path)
    errors: list[str] = []

    if manifest.get("schema_version") != "0.1":
        errors.append("ResultManifest schema_version must be 0.1")
    if manifest.get("status") != "succeeded":
        errors.append(f"positive ResultManifest status must be succeeded, got {manifest.get('status')!r}")
    if manifest.get("work_unit_id") != work_unit.get("id"):
        errors.append("ResultManifest work_unit_id does not match canonical WorkUnit")
    if manifest.get("work_unit_version") != work_unit.get("version"):
        errors.append("ResultManifest work_unit_version does not match canonical WorkUnit")

    work_revision = ((work_unit.get("provenance") or {}).get("source_revision"))
    execution_revision = (
        ((work_unit.get("extensions") or {}).get("org.idkmesh.node.execution") or {}).get("source_revision")
    )
    manifest_revision = ((manifest.get("provenance") or {}).get("source_revision"))
    if not work_revision or work_revision != execution_revision or manifest_revision != work_revision:
        errors.append("source revision is not exactly bound across WorkUnit execution/provenance and ResultManifest")

    candidate = find_artifact(manifest, "candidate-patch")
    if candidate is None:
        errors.append("ResultManifest missing candidate-patch artifact")
    else:
        observed = sha256_file(patch_path)
        if candidate.get("locator") != "changes.patch":
            errors.append("candidate-patch locator must be changes.patch")
        if candidate.get("digest") != observed:
            errors.append(f"candidate-patch digest mismatch: declared {candidate.get('digest')!r}, observed {observed}")

    for log_type, path in (("stdout", stdout_path), ("stderr", stderr_path)):
        log = find_log(manifest, log_type)
        if log is None:
            errors.append(f"ResultManifest missing {log_type} log")
            continue
        observed = sha256_file(path)
        if log.get("locator") != path.name:
            errors.append(f"{log_type} locator must be {path.name}")
        if log.get("digest") != observed:
            errors.append(f"{log_type} digest mismatch: declared {log.get('digest')!r}, observed {observed}")

    patch_text = patch_path.read_text(encoding="utf-8", errors="strict")
    try:
        patch_paths = parse_patch_paths(patch_text)
    except AcceptanceError as exc:
        errors.append(str(exc))
        patch_paths = []
    errors.extend(scope_errors(work_unit, patch_paths))

    metrics = manifest.get("metrics") or {}
    if metrics.get("untracked_file_count") != 0:
        errors.append(f"untracked_file_count must be 0, got {metrics.get('untracked_file_count')!r}")
    if metrics.get("patch_truncated") != 0:
        errors.append(f"patch_truncated must be 0, got {metrics.get('patch_truncated')!r}")
    if metrics.get("policy_violation_count") != 0:
        errors.append(f"policy_violation_count must be 0, got {metrics.get('policy_violation_count')!r}")

    node_ext = ((manifest.get("extensions") or {}).get("org.idkmesh.node.v0_1") or {})
    if node_ext.get("configured_container_image") != expected_image:
        errors.append("configured_container_image differs from preflight image")
    if node_ext.get("resolved_container_image_id") != expected_image_id:
        errors.append("resolved_container_image_id differs from preflight Docker inspection")
    if node_ext.get("resolved_container_repo_digest") != expected_repo_digest:
        errors.append("resolved_container_repo_digest differs from preflight Docker inspection")
    if node_ext.get("untracked_paths") != []:
        errors.append(f"untracked_paths must be empty, observed {node_ext.get('untracked_paths')!r}")
    for key in (
        "path_policy_violations",
        "unpackaged_artifact_violations",
        "protected_metadata_violations",
        "output_policy_violations",
        "runtime_policy_violations",
        "policy_violations",
    ):
        _require_empty_list(errors, node_ext, key)

    independently_observed_paths = sorted(patch_paths)
    if sorted(node_ext.get("changed_paths") or []) != independently_observed_paths:
        errors.append(
            "worker changed_paths does not match independently parsed patch paths: "
            f"worker={node_ext.get('changed_paths')!r}, parsed={independently_observed_paths!r}"
        )

    provenance = manifest.get("provenance") or {}
    environment = provenance.get("environment") or {}
    if environment.get("container_image") != expected_repo_digest:
        errors.append("provenance.environment.container_image must equal immutable repository digest")

    required_validator_ids = sorted(
        validator.get("id")
        for validator in work_unit.get("validators") or []
        if isinstance(validator, dict) and validator.get("required") is True
    )
    verification_request = manifest.get("verification_request") or {}
    requested = sorted(verification_request.get("expected_validator_ids") or [])
    if requested != required_validator_ids:
        errors.append(
            f"verification_request validator IDs mismatch: expected {required_validator_ids!r}, got {requested!r}"
        )
    if "candidate-patch" not in (verification_request.get("evidence_artifact_ids") or []):
        errors.append("verification_request must request independent verification of candidate-patch")

    for forbidden_claim in ("accepted", "decision_support", "verification_result"):
        if forbidden_claim in manifest:
            errors.append(f"worker ResultManifest must not contain integration/verification claim: {forbidden_claim}")

    return {
        "passed": not errors,
        "errors": errors,
        "observed": {
            "bundle": str(bundle),
            "patch_sha256": sha256_file(patch_path),
            "patch_paths": independently_observed_paths,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_sha256": sha256_file(stderr_path),
            "source_revision": manifest_revision,
            "configured_image": node_ext.get("configured_container_image"),
            "resolved_image_id": node_ext.get("resolved_container_image_id"),
            "resolved_repo_digest": node_ext.get("resolved_container_repo_digest"),
            "required_validator_ids": required_validator_ids,
        },
    }


def safe_reset_output(path: Path) -> None:
    path = path.resolve()
    tmp = Path("/tmp").resolve()
    try:
        path.relative_to(tmp)
    except ValueError as exc:
        raise AcceptanceError("automatic cleanup is restricted to /tmp; choose a /tmp output path") from exc
    if path == tmp:
        raise AcceptanceError("refusing to remove /tmp itself")
    if path.exists():
        shutil.rmtree(path)


def run_positive(repo: Path, output: Path, image: str) -> dict[str, Any]:
    pre = preflight(repo, image)
    safe_reset_output(output)

    commands: list[dict[str, Any]] = []
    command_specs = [
        ([sys.executable, "-m", "pip", "install", "-e", "node"], 180.0),
        ([sys.executable, "-m", "unittest", "discover", "-s", "node/tests", "-v"], 180.0),
        ([sys.executable, "-m", "idkmesh_node", "validate", DEFAULT_WORK_UNIT], 60.0),
        ([sys.executable, "-m", "idkmesh_node", "run", DEFAULT_WORK_UNIT, "--output", str(output)], 180.0),
    ]
    for command, timeout in command_specs:
        proc = run(command, cwd=repo, timeout=timeout)
        commands.append(command_observation(command, proc))

    validation = validate_positive_bundle(
        repo=repo,
        bundle=output,
        expected_image=image,
        expected_image_id=pre["container"]["resolved_image_id"],
        expected_repo_digest=pre["container"]["resolved_repo_digest"],
    )
    return {
        "schema_version": "0.2",
        "kind": "pr91-positive-controlled-docker-evidence",
        "preflight": pre,
        "commands": commands,
        "bundle_validation": validation,
        "negative_runtime_checks_required": list(NEGATIVE_CASES),
    }


def _copy_document(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))


def build_negative_work_unit(base: dict[str, Any], case: str) -> dict[str, Any]:
    if case not in NEGATIVE_CASES:
        raise AcceptanceError(f"unsupported negative case: {case}")
    work = _copy_document(base)
    work["id"] = f"{base['id']}/acceptance-negative-{case.lower()}"
    work["objective"] = f"Controlled Docker negative acceptance case {case}; failure is the expected outcome."
    binding = work["extensions"]["org.idkmesh.node.execution"]
    container = binding["container"]

    if case == "A":
        container["command"] = [
            "python",
            "-c",
            "from pathlib import Path; p=Path('SECURITY.md'); p.write_text(p.read_text() + '\n<!-- pr91 negative A -->\n')",
        ]
    elif case == "B":
        work["constraints"]["allowed_paths"] = ["README.md", "results/**"]
        work["permissions"]["filesystem_write"] = ["README.md", "results/**"]
        container["command"] = [
            "python",
            "-c",
            "from pathlib import Path; p=Path('results/ignored-output.txt'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('pr91 negative B ignored output\n')",
        ]
    elif case == "C":
        container["command"] = [
            "python",
            "-c",
            "from pathlib import Path; Path('.git').write_text('gitdir: /tmp/attacker-controlled\\n'); p=Path('README.md'); p.write_text(p.read_text() + '\n<!-- pr91 negative C visible change -->\n')",
        ]
    elif case == "D":
        binding["output_limits"]["max_patch_bytes"] = 128
        container["command"] = [
            "python",
            "-c",
            "from pathlib import Path; p=Path('README.md'); p.write_text(p.read_text() + '\n' + ('X' * 5000) + '\n')",
        ]
    elif case == "E":
        container["image"] = NEGATIVE_IMAGE
        container["command"] = ["python", "-c", "raise SystemExit(77)"]
    return work


def _negative_common_errors(manifest: dict[str, Any], bundle: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if manifest.get("schema_version") != "0.1":
        errors.append("negative ResultManifest schema_version must be 0.1")
    if manifest.get("status") == "succeeded":
        errors.append("negative case unexpectedly reported status=succeeded")
    for forbidden_claim in ("accepted", "decision_support", "verification_result"):
        if forbidden_claim in manifest:
            errors.append(f"negative worker ResultManifest contains forbidden authority claim: {forbidden_claim}")

    patch_path = bundle / "changes.patch"
    candidate = find_artifact(manifest, "candidate-patch")
    patch_digest = None
    patch_bytes = None
    if not patch_path.is_file():
        errors.append("negative bundle missing changes.patch")
    else:
        patch_digest = sha256_file(patch_path)
        patch_bytes = patch_path.stat().st_size
        if candidate is None:
            errors.append("negative ResultManifest missing candidate-patch artifact")
        elif candidate.get("digest") != patch_digest:
            errors.append("negative candidate-patch digest does not match stored patch bytes")

    for log_type in ("stdout", "stderr"):
        log = find_log(manifest, log_type)
        path = bundle / f"{log_type}.txt"
        if not path.is_file():
            errors.append(f"negative bundle missing {log_type}.txt")
        elif log is None:
            errors.append(f"negative ResultManifest missing {log_type} log")
        elif log.get("digest") != sha256_file(path):
            errors.append(f"negative {log_type} digest does not match stored bytes")

    return errors, {
        "status": manifest.get("status"),
        "patch_sha256": patch_digest,
        "patch_bytes": patch_bytes,
    }


def validate_negative_bundle(case: str, bundle: Path) -> dict[str, Any]:
    bundle = bundle.resolve()
    manifest_path = bundle / "result-manifest.json"
    if not manifest_path.is_file():
        raise AcceptanceError(f"negative {case} bundle missing ResultManifest: {manifest_path}")
    manifest = load_json(manifest_path)
    errors, observed = _negative_common_errors(manifest, bundle)
    metrics = manifest.get("metrics") or {}
    ext = ((manifest.get("extensions") or {}).get("org.idkmesh.node.v0_1") or {})
    changed = list(ext.get("changed_paths") or [])

    if case == "A":
        if "SECURITY.md" not in changed:
            errors.append(f"negative A did not retain SECURITY.md in changed_paths: {changed!r}")
        violations = list(ext.get("path_policy_violations") or [])
        if not any("SECURITY.md" in item for item in violations):
            errors.append("negative A did not record a SECURITY.md path-policy violation")
        observed["path_policy_violations"] = violations
    elif case == "B":
        expected = "results/ignored-output.txt"
        untracked = list(ext.get("untracked_paths") or [])
        unpackaged = list(ext.get("unpackaged_artifact_violations") or [])
        if metrics.get("untracked_file_count", 0) < 1:
            errors.append("negative B did not report untracked_file_count > 0")
        if expected not in untracked:
            errors.append(f"negative B did not observe ignored untracked path {expected!r}")
        if not any(expected in item for item in unpackaged):
            errors.append("negative B did not record unpackaged-artifact violation for ignored output")
        if ext.get("path_policy_violations") != []:
            errors.append(
                "negative B should isolate the unpackaged-artifact rule without path-policy violations"
            )
        observed.update({"untracked_paths": untracked, "unpackaged_artifact_violations": unpackaged})
    elif case == "C":
        protected = list(ext.get("protected_metadata_violations") or [])
        if not protected:
            errors.append("negative C did not record protected Git metadata pointer tampering")
        if "README.md" not in changed:
            errors.append(
                "negative C host evidence capture did not retain the visible README change after .git tampering"
            )
        patch_path = bundle / "changes.patch"
        if patch_path.is_file():
            try:
                paths = parse_patch_paths(patch_path.read_text(encoding="utf-8"))
            except (AcceptanceError, UnicodeDecodeError) as exc:
                errors.append(f"negative C patch could not be independently parsed: {exc}")
                paths = []
            if "README.md" not in paths:
                errors.append(
                    "negative C stored patch did not retain README.md despite task-visible .git tampering"
                )
            observed["independently_parsed_patch_paths"] = paths
        observed["protected_metadata_violations"] = protected
    elif case == "D":
        output_violations = list(ext.get("output_policy_violations") or [])
        if metrics.get("patch_truncated") != 1:
            errors.append(f"negative D expected patch_truncated=1, got {metrics.get('patch_truncated')!r}")
        if not output_violations:
            errors.append("negative D did not record output-policy violation")
        patch_path = bundle / "changes.patch"
        if patch_path.is_file() and patch_path.stat().st_size > 128:
            errors.append("negative D stored diagnostic patch exceeded configured 128-byte bound")
        observed["output_policy_violations"] = output_violations
    else:
        raise AcceptanceError(f"validate_negative_bundle does not handle case {case}")

    if metrics.get("policy_violation_count", 0) < 1:
        errors.append(f"negative {case} did not report any policy violation")
    observed.update(
        {
            "changed_paths": changed,
            "policy_violation_count": metrics.get("policy_violation_count"),
        }
    )
    return {"passed": not errors, "errors": errors, "observed": observed}


def _node_run_command(work_unit: Path, output: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "idkmesh_node",
        "run",
        str(work_unit),
        "--output",
        str(output),
    ]


def _run_negative_abcd(
    *, repo: Path, work_unit_dir: Path, output_base: Path, base: dict[str, Any], case: str
) -> dict[str, Any]:
    work = build_negative_work_unit(base, case)
    work_unit_path = work_unit_dir / f"negative-{case.lower()}.work-unit.json"
    write_json(work_unit_path, work)
    output = output_base / case.lower()
    safe_reset_output(output)
    command = _node_run_command(work_unit_path, output)
    proc = run(command, cwd=repo, timeout=180, allow_failure=True)
    errors: list[str] = []
    if proc.returncode != 1:
        errors.append(
            f"negative {case} expected node CLI return code 1 for a retained failed ResultManifest, got {proc.returncode}"
        )
    try:
        validation = validate_negative_bundle(case, output)
    except (AcceptanceError, OSError, json.JSONDecodeError) as exc:
        validation = {"passed": False, "errors": [str(exc)], "observed": {}}
    errors.extend(validation["errors"])
    return {
        "passed": not errors,
        "errors": errors,
        "command": command_observation(command, proc),
        "bundle": str(output),
        "validation": validation,
    }


def _docker_tag_exists(reference: str) -> bool:
    proc = run(["docker", "image", "inspect", reference], timeout=30, allow_failure=True)
    return proc.returncode == 0


def _run_negative_e(
    *,
    repo: Path,
    work_unit_dir: Path,
    output_base: Path,
    base: dict[str, Any],
    pre: dict[str, Any],
) -> dict[str, Any]:
    """Exercise both missing-image and locally-retagged-image refusal safely.

    The alternate allowlisted tag must be absent before this function starts. We
    never replace an existing host tag. A temporary local retag is removed in a
    finally block and absence is re-verified.
    """

    if _docker_tag_exists(NEGATIVE_IMAGE):
        raise AcceptanceError(
            f"negative E requires {NEGATIVE_IMAGE!r} to be absent initially; refusing to overwrite an existing host Docker tag"
        )

    work = build_negative_work_unit(base, "E")
    work_unit_path = work_unit_dir / "negative-e.work-unit.json"
    write_json(work_unit_path, work)
    errors: list[str] = []

    missing_output = output_base / "e-missing"
    safe_reset_output(missing_output)
    missing_command = _node_run_command(work_unit_path, missing_output)
    missing_proc = run(missing_command, cwd=repo, timeout=90, allow_failure=True)
    if missing_proc.returncode != 2:
        errors.append(
            f"negative E missing-image case expected CLI return code 2, got {missing_proc.returncode}"
        )
    missing_detail = (missing_proc.stderr + "\n" + missing_proc.stdout).lower()
    if "no such image" not in missing_detail and "not available locally" not in missing_detail:
        errors.append("negative E missing-image case did not report local image absence")
    if _docker_tag_exists(NEGATIVE_IMAGE):
        errors.append("negative E missing-image run caused the node to pull/create the absent image tag")

    retag_created = False
    retag_observation: dict[str, Any] = {}
    try:
        source_image_id = pre["container"]["resolved_image_id"]
        tag_command = ["docker", "tag", source_image_id, NEGATIVE_IMAGE]
        tag_proc = run(tag_command, timeout=30)
        retag_created = True
        inspect = run(["docker", "image", "inspect", NEGATIVE_IMAGE], timeout=30)
        parser_rejected = False
        parser_error = None
        try:
            parse_image_inspect(inspect.stdout, NEGATIVE_IMAGE)
        except AcceptanceError as exc:
            parser_rejected = True
            parser_error = str(exc)
        if not parser_rejected:
            errors.append("negative E temporary local retag unexpectedly had a matching immutable RepoDigest")

        retag_output = output_base / "e-local-retag"
        safe_reset_output(retag_output)
        retag_command = _node_run_command(work_unit_path, retag_output)
        retag_proc = run(retag_command, cwd=repo, timeout=90, allow_failure=True)
        if retag_proc.returncode != 2:
            errors.append(
                f"negative E local-retag case expected CLI return code 2, got {retag_proc.returncode}"
            )
        retag_detail = (retag_proc.stderr + "\n" + retag_proc.stdout).lower()
        if "no matching immutable repository digest" not in retag_detail:
            errors.append("negative E local-retag case did not fail on repository-digest mismatch")
        retag_observation = {
            "tag_command": command_observation(tag_command, tag_proc),
            "inspect_payload": json.loads(inspect.stdout),
            "harness_parser_rejected": parser_rejected,
            "harness_parser_error": parser_error,
            "node_command": command_observation(retag_command, retag_proc),
        }
    finally:
        cleanup: dict[str, Any] | None = None
        if retag_created:
            cleanup_command = ["docker", "image", "rm", NEGATIVE_IMAGE]
            cleanup_proc = run(cleanup_command, timeout=30, allow_failure=True)
            cleanup = command_observation(cleanup_command, cleanup_proc)
            if cleanup_proc.returncode != 0:
                errors.append("negative E could not remove its temporary local Docker tag")
        if _docker_tag_exists(NEGATIVE_IMAGE):
            errors.append("negative E temporary Docker tag still exists after cleanup")
        if cleanup is not None:
            retag_observation["cleanup"] = cleanup

    return {
        "passed": not errors,
        "errors": errors,
        "missing_image": command_observation(missing_command, missing_proc),
        "local_retag": retag_observation,
    }


def run_negatives(repo: Path, output_base: Path, image: str) -> dict[str, Any]:
    repo = repo.resolve()
    pre = preflight(repo, image)
    if image != DEFAULT_IMAGE:
        raise AcceptanceError(
            f"negative matrix is pinned to configured positive image {DEFAULT_IMAGE!r}; got {image!r}"
        )
    output_base = output_base.resolve()
    safe_reset_output(output_base)
    output_base.mkdir(parents=True, exist_ok=True)
    work_unit_dir = output_base / "work-units"
    work_unit_dir.mkdir()

    install_command = [sys.executable, "-m", "pip", "install", "-e", "node"]
    install_proc = run(install_command, cwd=repo, timeout=180)
    base = load_json(repo / DEFAULT_WORK_UNIT)

    cases: dict[str, Any] = {}
    for case in ("A", "B", "C", "D"):
        cases[case] = _run_negative_abcd(
            repo=repo,
            work_unit_dir=work_unit_dir,
            output_base=output_base,
            base=base,
            case=case,
        )
    try:
        cases["E"] = _run_negative_e(
            repo=repo,
            work_unit_dir=work_unit_dir,
            output_base=output_base,
            base=base,
            pre=pre,
        )
    except AcceptanceError as exc:
        cases["E"] = {"passed": False, "errors": [str(exc)]}

    failed = [case for case in NEGATIVE_CASES if not cases[case]["passed"]]
    return {
        "schema_version": "0.1",
        "kind": "pr91-negative-controlled-docker-evidence",
        "preflight": pre,
        "install": command_observation(install_command, install_proc),
        "output_base": str(output_base),
        "cases": cases,
        "passed": not failed,
        "failed_cases": failed,
        "authority": {
            "runtime_failure_is_evidence_only": True,
            "automatic_merge": False,
            "integration_decision": None,
        },
    }


def self_test() -> None:
    fake_id = "sha256:" + "1" * 64
    fake_digest = "python@sha256:" + "2" * 64
    inspect_payload = json.dumps([{"Id": fake_id, "RepoDigests": [fake_digest]}])
    observed_id, observed_digest = parse_image_inspect(inspect_payload, DEFAULT_IMAGE)
    assert observed_id == fake_id
    assert observed_digest == fake_digest
    try:
        parse_image_inspect(inspect_payload, NEGATIVE_IMAGE)
    except AcceptanceError:
        pass
    else:
        raise AcceptanceError("self-test expected local-retag repository-digest mismatch rejection")

    patch = """diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1,2 @@\n hello\n+world\n"""
    assert parse_patch_paths(patch) == ["README.md"]
    try:
        parse_patch_paths("--- ../../etc/passwd\n+++ b/README.md\n")
    except AcceptanceError:
        pass
    else:
        raise AcceptanceError("self-test expected traversal diff path rejection")

    work_unit = {
        "id": "node/canonical-smoke",
        "version": 2,
        "objective": "self-test",
        "constraints": {"allowed_paths": ["README.md"], "forbidden_paths": ["SECURITY.md"]},
        "permissions": {"filesystem_write": ["README.md"]},
        "validators": [
            {"id": "result-manifest-schema", "required": True},
            {"id": "independent-review", "required": True},
        ],
        "provenance": {"source_revision": "a" * 40},
        "extensions": {
            "org.idkmesh.node.execution": {
                "source_revision": "a" * 40,
                "container": {"image": DEFAULT_IMAGE, "command": ["python", "-c", "print('ok')"]},
                "output_limits": {"max_patch_bytes": 1000000, "max_log_bytes": 262144},
            }
        },
    }
    negative_a = build_negative_work_unit(work_unit, "A")
    assert "SECURITY.md" in negative_a["extensions"]["org.idkmesh.node.execution"]["container"]["command"][2]
    negative_b = build_negative_work_unit(work_unit, "B")
    assert "results/**" in negative_b["constraints"]["allowed_paths"]
    negative_c = build_negative_work_unit(work_unit, "C")
    assert ".git" in negative_c["extensions"]["org.idkmesh.node.execution"]["container"]["command"][2]
    negative_d = build_negative_work_unit(work_unit, "D")
    assert negative_d["extensions"]["org.idkmesh.node.execution"]["output_limits"]["max_patch_bytes"] == 128
    negative_e = build_negative_work_unit(work_unit, "E")
    assert negative_e["extensions"]["org.idkmesh.node.execution"]["container"]["image"] == NEGATIVE_IMAGE

    with tempfile.TemporaryDirectory(prefix="idkmesh-pr91-harness-") as tmp_raw:
        tmp = Path(tmp_raw)
        repo = tmp / "repo"
        bundle = tmp / "bundle"
        (repo / "node/examples").mkdir(parents=True)
        bundle.mkdir()
        write_json(repo / DEFAULT_WORK_UNIT, work_unit)
        (bundle / "changes.patch").write_text(patch, encoding="utf-8")
        (bundle / "stdout.txt").write_text("ok\n", encoding="utf-8")
        (bundle / "stderr.txt").write_text("", encoding="utf-8")

        manifest = {
            "schema_version": "0.1",
            "work_unit_id": work_unit["id"],
            "work_unit_version": work_unit["version"],
            "status": "succeeded",
            "produced_artifacts": [
                {
                    "id": "candidate-patch",
                    "locator": "changes.patch",
                    "digest": sha256_file(bundle / "changes.patch"),
                }
            ],
            "logs": [
                {"type": "stdout", "locator": "stdout.txt", "digest": sha256_file(bundle / "stdout.txt")},
                {"type": "stderr", "locator": "stderr.txt", "digest": sha256_file(bundle / "stderr.txt")},
            ],
            "metrics": {"untracked_file_count": 0, "patch_truncated": 0, "policy_violation_count": 0},
            "provenance": {
                "source_revision": "a" * 40,
                "environment": {"container_image": fake_digest},
            },
            "verification_request": {
                "expected_validator_ids": ["result-manifest-schema", "independent-review"],
                "evidence_artifact_ids": ["candidate-patch"],
            },
            "extensions": {
                "org.idkmesh.node.v0_1": {
                    "configured_container_image": DEFAULT_IMAGE,
                    "resolved_container_image_id": fake_id,
                    "resolved_container_repo_digest": fake_digest,
                    "changed_paths": ["README.md"],
                    "untracked_paths": [],
                    "path_policy_violations": [],
                    "unpackaged_artifact_violations": [],
                    "protected_metadata_violations": [],
                    "output_policy_violations": [],
                    "runtime_policy_violations": [],
                    "policy_violations": [],
                }
            },
        }
        write_json(bundle / "result-manifest.json", manifest)
        result = validate_positive_bundle(
            repo=repo,
            bundle=bundle,
            expected_image=DEFAULT_IMAGE,
            expected_image_id=fake_id,
            expected_repo_digest=fake_digest,
        )
        if not result["passed"]:
            raise AcceptanceError("self-test positive bundle unexpectedly failed: " + "; ".join(result["errors"]))

        (bundle / "changes.patch").write_text(patch + "+tampered\n", encoding="utf-8")
        tampered = validate_positive_bundle(
            repo=repo,
            bundle=bundle,
            expected_image=DEFAULT_IMAGE,
            expected_image_id=fake_id,
            expected_repo_digest=fake_digest,
        )
        if tampered["passed"] or not any("digest mismatch" in error for error in tampered["errors"]):
            raise AcceptanceError("self-test failed to detect tampered patch bytes")

    print("OK: PR91 acceptance harness self-test passed without Docker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight", help="Check exact PR #91 head and controlled Docker image evidence.")
    pre.add_argument("--repo", required=True, type=Path)
    pre.add_argument("--image", default=DEFAULT_IMAGE)
    pre.add_argument("--report", type=Path)

    verify = sub.add_parser("verify-positive", help="Independently validate an already-produced positive node bundle.")
    verify.add_argument("--repo", required=True, type=Path)
    verify.add_argument("--bundle", required=True, type=Path)
    verify.add_argument("--image", default=DEFAULT_IMAGE)
    verify.add_argument("--image-id", required=True)
    verify.add_argument("--repo-digest", required=True)
    verify.add_argument("--report", type=Path)

    positive = sub.add_parser("run-positive", help="Run the positive controlled-Docker path and verify its evidence bundle.")
    positive.add_argument("--repo", required=True, type=Path)
    positive.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    positive.add_argument("--image", default=DEFAULT_IMAGE)
    positive.add_argument("--report", type=Path)

    negatives = sub.add_parser(
        "run-negatives",
        help="Run controlled-Docker negative acceptance cases A-E using temporary WorkUnit variants.",
    )
    negatives.add_argument("--repo", required=True, type=Path)
    negatives.add_argument("--output-base", type=Path, default=Path(DEFAULT_NEGATIVE_OUTPUT))
    negatives.add_argument("--image", default=DEFAULT_IMAGE)
    negatives.add_argument("--report", type=Path)

    sub.add_parser("self-test", help="Exercise deterministic parsing/digest/negative-fixture checks without Docker.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "self-test":
            self_test()
            return 0
        if args.command == "preflight":
            result = preflight(args.repo, args.image)
            if args.report:
                write_json(args.report, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "verify-positive":
            result = validate_positive_bundle(
                repo=args.repo,
                bundle=args.bundle,
                expected_image=args.image,
                expected_image_id=args.image_id,
                expected_repo_digest=args.repo_digest,
            )
            if args.report:
                write_json(args.report, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["passed"] else 1
        if args.command == "run-positive":
            result = run_positive(args.repo.resolve(), args.output, args.image)
            if args.report:
                write_json(args.report, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["bundle_validation"]["passed"] else 1
        if args.command == "run-negatives":
            result = run_negatives(args.repo.resolve(), args.output_base, args.image)
            if args.report:
                write_json(args.report, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["passed"] else 1
        raise AcceptanceError(f"unsupported command: {args.command}")
    except (AcceptanceError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
