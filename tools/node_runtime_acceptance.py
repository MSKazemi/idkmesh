#!/usr/bin/env python3
"""Independent runtime acceptance harness for the frozen canonical idkmesh-node candidate.

The harness is intentionally kept outside the candidate tree. It invokes the
candidate only by an exact frozen commit checkout, uses a sanitized subprocess
environment, and exercises one positive and five fail-closed runtime cases.

It does not merge, push, approve, or grant acceptance authority to the worker.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Any

FROZEN_CANDIDATE_SHA = "d638a2f78e4a89353b98e91052233e365f56f90a"
FROZEN_SOURCE_SHA = "b1397a9be91da6570e8ae370de4fa9f4bc44df5c"
POSITIVE_IMAGE = "python:3.12-alpine"
NEGATIVE_IMAGE = "alpine:3.20"
NODE_PR = 91
NODE_CI_RUN = 33183974768
PHASE0_CI_RUN = 33183974817


class AcceptanceError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AcceptanceError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def candidate_env(candidate: Path, home: Path) -> dict[str, str]:
    """Give candidate code only the minimum host environment needed for the test."""

    home.mkdir(parents=True, exist_ok=True)
    xdg = home / "xdg"
    xdg.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONPATH": str(candidate / "node" / "src"),
        "PYTHONUNBUFFERED": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def node_command(
    candidate: Path,
    home: Path,
    args: list[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, "-m", "idkmesh_node", *args],
        cwd=candidate,
        env=candidate_env(candidate, home),
        check=check,
    )


def matching_image_evidence(reference: str) -> tuple[str, str]:
    payload = json.loads(run(["docker", "image", "inspect", reference]).stdout)
    assert_true(isinstance(payload, list) and len(payload) == 1, "docker inspect shape invalid")
    document = payload[0]
    image_id = str(document.get("Id", "")).lower()
    assert_true(image_id.startswith("sha256:") and len(image_id) == 71, "image ID is not immutable sha256")
    repository = reference.rsplit(":", 1)[0]
    repo_digests = [
        str(value).lower()
        for value in (document.get("RepoDigests") or [])
        if isinstance(value, str) and value.lower().startswith(repository + "@sha256:")
    ]
    assert_true(bool(repo_digests), f"no matching repository digest for {reference}")
    return image_id, sorted(repo_digests)[0]


def validate_result_schema(result: dict[str, Any], schema_path: Path) -> None:
    from jsonschema import Draft202012Validator, FormatChecker

    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(result), key=lambda error: list(error.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors[:10]
        )
        raise AcceptanceError("positive ResultManifest failed independent schema validation: " + detail)


def mutate_command(base: dict[str, Any], command: str) -> dict[str, Any]:
    data = copy.deepcopy(base)
    data["extensions"]["org.idkmesh.node.execution"]["container"]["command"] = [
        "python",
        "-c",
        command,
    ]
    return data


def run_manifest_case(
    *,
    candidate: Path,
    candidate_home: Path,
    temp_root: Path,
    name: str,
    manifest: dict[str, Any],
) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, Any] | None]:
    fixture = temp_root / f"{name}.work-unit.json"
    output = temp_root / f"{name}-output"
    write_json(fixture, manifest)
    proc = node_command(
        candidate,
        candidate_home,
        ["run", str(fixture), "--output", str(output)],
    )
    result_path = output / "result-manifest.json"
    result = load_json(result_path) if result_path.exists() else None
    return proc, output, result


def violation_extension(result: dict[str, Any]) -> dict[str, Any]:
    return result["extensions"]["org.idkmesh.node.v0_1"]


def summarize_negative(result: dict[str, Any]) -> dict[str, Any]:
    ext = violation_extension(result)
    return {
        "status": result["status"],
        "exit_code": result["metrics"]["exit_code"],
        "changed_paths": ext["changed_paths"],
        "untracked_paths": ext["untracked_paths"],
        "path_policy_violations": ext["path_policy_violations"],
        "unpackaged_artifact_violations": ext["unpackaged_artifact_violations"],
        "protected_metadata_violations": ext["protected_metadata_violations"],
        "output_policy_violations": ext["output_policy_violations"],
        "runtime_policy_violations": ext["runtime_policy_violations"],
        "patch_truncated": result["metrics"]["patch_truncated"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    harness_root = Path(__file__).resolve().parents[1]
    schema_path = harness_root / "schemas" / "result-manifest-v0.1.schema.json"
    fixture_path = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"

    actual_sha = run(["git", "-C", str(candidate), "rev-parse", "HEAD"]).stdout.strip()
    assert_true(actual_sha == FROZEN_CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")
    base = load_json(fixture_path)
    assert_true(
        base["extensions"]["org.idkmesh.node.execution"]["source_revision"] == FROZEN_SOURCE_SHA,
        "fixture source revision drift",
    )

    docker_version = run(["docker", "--version"]).stdout.strip()
    image_id, image_repo_digest = matching_image_evidence(POSITIVE_IMAGE)

    with tempfile.TemporaryDirectory(prefix="idkmesh-node-independent-acceptance-") as raw_temp:
        temp_root = Path(raw_temp)
        candidate_home = temp_root / "candidate-home"

        # The issue's positive procedure includes the candidate's own tests and
        # schema validation, but the evidence below is evaluated independently.
        unit_proc = run(
            [sys.executable, "-m", "unittest", "discover", "-s", "node/tests", "-v"],
            cwd=candidate,
            env=candidate_env(candidate, candidate_home),
            check=False,
        )
        assert_true(unit_proc.returncode == 0, "candidate unit tests failed during controlled acceptance")
        validate_proc = node_command(candidate, candidate_home, ["validate", str(fixture_path)])
        assert_true(validate_proc.returncode == 0, "canonical node fixture validation failed")

        # Positive runtime.
        positive_proc, positive_output, positive = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="positive",
            manifest=base,
        )
        assert_true(positive_proc.returncode == 0, f"positive node run failed: {positive_proc.stderr}")
        assert_true(positive is not None, "positive ResultManifest missing")
        validate_result_schema(positive, schema_path)
        positive_ext = violation_extension(positive)
        assert_true(positive["status"] == "succeeded", "positive worker status is not succeeded")
        assert_true(positive["provenance"]["source_revision"] == FROZEN_SOURCE_SHA, "source revision mismatch")
        assert_true(positive_ext["changed_paths"] == ["README.md"], "unexpected positive changed paths")
        assert_true(positive["metrics"]["untracked_file_count"] == 0, "positive run has untracked artifacts")
        assert_true(positive_ext["untracked_paths"] == [], "positive untracked_paths is not empty")
        for field in (
            "path_policy_violations",
            "unpackaged_artifact_violations",
            "protected_metadata_violations",
            "output_policy_violations",
            "runtime_policy_violations",
            "policy_violations",
        ):
            assert_true(positive_ext[field] == [], f"positive {field} is not empty")
        assert_true(positive["metrics"]["patch_truncated"] == 0, "positive patch was truncated")
        assert_true(positive_ext["configured_container_image"] == POSITIVE_IMAGE, "configured image mismatch")
        assert_true(positive_ext["resolved_container_image_id"] == image_id, "resolved image ID mismatch")
        assert_true(
            positive_ext["resolved_container_repo_digest"] == image_repo_digest,
            "resolved repository digest mismatch",
        )
        assert_true(
            positive["provenance"]["environment"]["container_image"] == image_repo_digest,
            "provenance container image is not immutable repository digest",
        )

        digest_checks: dict[str, bool] = {}
        for artifact in positive["produced_artifacts"]:
            actual = sha256_file(positive_output / artifact["locator"])
            digest_checks[f"artifact:{artifact['id']}"] = actual == artifact["digest"]
        for log in positive["logs"]:
            actual = sha256_file(positive_output / log["locator"])
            digest_checks[f"log:{log['type']}"] = actual == log["digest"]
        assert_true(all(digest_checks.values()), "one or more declared positive file digests do not match")

        expected_validators = sorted(
            validator["id"] for validator in base["validators"] if validator["required"]
        )
        assert_true(
            sorted(positive["verification_request"]["expected_validator_ids"]) == expected_validators,
            "verification request does not contain all required validator IDs",
        )
        claims = positive["self_report"]["claims"]
        assert_true(
            any("must be independently verified" in claim.lower() for claim in claims),
            "worker self-report does not explicitly require independent verification",
        )

        # Derive the Docker command in a sanitized candidate subprocess and inspect
        # the exact policy-producing function without importing candidate code into
        # this evaluator process.
        policy_probe = run(
            [
                sys.executable,
                "-c",
                (
                    "import json; from pathlib import Path; "
                    "from idkmesh_node.model import load_work_unit; "
                    "from idkmesh_node.runner import docker_command; "
                    f"w=load_work_unit({str(fixture_path)!r}); "
                    f"print(json.dumps(docker_command(w, Path('/tmp/workspace'), 'acceptance-probe', "
                    f"Path('/tmp/git-meta'), image_ref={image_id!r})))"
                ),
            ],
            cwd=candidate,
            env=candidate_env(candidate, candidate_home),
        )
        docker_policy = json.loads(policy_probe.stdout)
        joined_policy = " ".join(docker_policy)
        sandbox_checks = {
            "network_none": "--network none" in joined_policy,
            "read_only_root": "--read-only" in docker_policy,
            "capabilities_dropped": "--cap-drop ALL" in joined_policy,
            "no_new_privileges": "--security-opt no-new-privileges" in joined_policy,
            "pid_limit": "--pids-limit 64" in joined_policy,
            "cpu_limit": "--cpus 1.0" in joined_policy,
            "memory_limit": "--memory 256m" in joined_policy,
            "git_metadata_read_only": "/git-meta,readonly" in joined_policy,
            "no_docker_socket": "/var/run/docker.sock" not in joined_policy,
            "immutable_image_execution": image_id in docker_policy,
        }
        assert_true(all(sandbox_checks.values()), "positive Docker policy check failed")

        # Negative A: tracked but forbidden/out-of-scope change.
        negative_a = mutate_command(
            base,
            "from pathlib import Path; p=Path('SECURITY.md'); p.write_text(p.read_text() + '\\nnode-negative-a\\n')",
        )
        proc_a, _, result_a = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="negative-a-out-of-scope",
            manifest=negative_a,
        )
        assert_true(proc_a.returncode == 1 and result_a is not None, "negative A did not fail as a worker result")
        ext_a = violation_extension(result_a)
        assert_true(result_a["status"] == "failed", "negative A status not failed")
        assert_true(any("SECURITY.md" in item for item in ext_a["path_policy_violations"]), "negative A path violation missing")

        # Negative B: ignored untracked output must remain observable.
        negative_b = mutate_command(
            base,
            "from pathlib import Path; p=Path('results/ignored.txt'); p.parent.mkdir(exist_ok=True); p.write_text('ignored but observable\\n')",
        )
        proc_b, _, result_b = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="negative-b-ignored-untracked",
            manifest=negative_b,
        )
        assert_true(proc_b.returncode == 1 and result_b is not None, "negative B did not fail as a worker result")
        ext_b = violation_extension(result_b)
        assert_true(result_b["metrics"]["untracked_file_count"] > 0, "negative B untracked count is zero")
        assert_true("results/ignored.txt" in ext_b["untracked_paths"], "negative B ignored path was hidden")
        assert_true(bool(ext_b["unpackaged_artifact_violations"]), "negative B unpackaged-artifact violation missing")

        # Negative C: candidate tampers only with task-visible .git pointer; host
        # capture must still observe the tracked README change via external metadata.
        negative_c = mutate_command(
            base,
            (
                "from pathlib import Path; Path('.git').write_text('gitdir: /tmp/evil\\n'); "
                "p=Path('README.md'); p.write_text(p.read_text() + '\\nnode-negative-c\\n')"
            ),
        )
        proc_c, _, result_c = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="negative-c-git-metadata",
            manifest=negative_c,
        )
        assert_true(proc_c.returncode == 1 and result_c is not None, "negative C did not fail as a worker result")
        ext_c = violation_extension(result_c)
        assert_true(bool(ext_c["protected_metadata_violations"]), "negative C metadata violation missing")
        assert_true("README.md" in ext_c["changed_paths"], "negative C hid the tracked candidate change")

        # Negative D: a partial/truncated patch can only be diagnostic evidence.
        negative_d = mutate_command(
            base,
            "from pathlib import Path; p=Path('README.md'); p.write_text(p.read_text() + '\\n' + ('X' * 6000) + '\\n')",
        )
        negative_d["extensions"]["org.idkmesh.node.execution"]["output_limits"]["max_patch_bytes"] = 1024
        proc_d, _, result_d = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="negative-d-oversized-patch",
            manifest=negative_d,
        )
        assert_true(proc_d.returncode == 1 and result_d is not None, "negative D did not fail as a worker result")
        ext_d = violation_extension(result_d)
        assert_true(result_d["metrics"]["patch_truncated"] == 1, "negative D did not mark patch truncation")
        assert_true(bool(ext_d["output_policy_violations"]), "negative D output-policy violation missing")

        # Negative E1/E2: absent image and locally retagged image with no matching
        # repository digest must both fail before task execution.
        run(["docker", "image", "rm", "-f", NEGATIVE_IMAGE], check=False)
        negative_e = copy.deepcopy(base)
        negative_e["extensions"]["org.idkmesh.node.execution"]["container"]["image"] = NEGATIVE_IMAGE
        proc_e1, _, result_e1 = run_manifest_case(
            candidate=candidate,
            candidate_home=candidate_home,
            temp_root=temp_root,
            name="negative-e1-image-absent",
            manifest=negative_e,
        )
        assert_true(proc_e1.returncode == 2 and result_e1 is None, "negative E1 absent image did not fail before result creation")

        run(["docker", "tag", POSITIVE_IMAGE, NEGATIVE_IMAGE])
        try:
            proc_e2, _, result_e2 = run_manifest_case(
                candidate=candidate,
                candidate_home=candidate_home,
                temp_root=temp_root,
                name="negative-e2-image-retagged",
                manifest=negative_e,
            )
        finally:
            run(["docker", "image", "rm", "-f", NEGATIVE_IMAGE], check=False)
        assert_true(proc_e2.returncode == 2 and result_e2 is None, "negative E2 retagged image did not fail before result creation")
        assert_true(
            "no matching immutable repository digest" in proc_e2.stderr.lower(),
            "negative E2 did not fail for repository-digest mismatch",
        )

        evidence = {
            "schema_version": "0.1",
            "candidate": {
                "pull_request": NODE_PR,
                "sha": FROZEN_CANDIDATE_SHA,
                "source_revision": FROZEN_SOURCE_SHA,
            },
            "preexisting_ci": {
                "idkmesh_node_ci_run": NODE_CI_RUN,
                "phase0_schema_check_run": PHASE0_CI_RUN,
            },
            "host": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "docker": docker_version,
            },
            "container": {
                "configured_tag": POSITIVE_IMAGE,
                "image_id": image_id,
                "repository_digest": image_repo_digest,
            },
            "positive": {
                "result_manifest_schema_valid": True,
                "declared_file_digests_match": digest_checks,
                "sandbox_policy": sandbox_checks,
                "result_manifest": positive,
                "changes_patch_sha256": sha256_file(positive_output / "changes.patch"),
            },
            "negative": {
                "a_out_of_scope_tracked_path": summarize_negative(result_a),
                "b_ignored_untracked_artifact": summarize_negative(result_b),
                "c_git_metadata_tampering": summarize_negative(result_c),
                "d_oversized_patch": summarize_negative(result_d),
                "e1_absent_image": {
                    "returncode": proc_e1.returncode,
                    "stderr": proc_e1.stderr.strip(),
                    "result_manifest_created": result_e1 is not None,
                },
                "e2_locally_retagged_image": {
                    "returncode": proc_e2.returncode,
                    "stderr": proc_e2.stderr.strip(),
                    "result_manifest_created": result_e2 is not None,
                },
            },
            "worker_acceptance_authority": False,
            "all_acceptance_checks_passed": True,
        }

        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.evidence, evidence)
        print("IDKMESH_ACCEPTANCE_EVIDENCE_BEGIN")
        print(json.dumps(evidence, indent=2, sort_keys=True))
        print("IDKMESH_ACCEPTANCE_EVIDENCE_END")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
