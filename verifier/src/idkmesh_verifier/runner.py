from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
from typing import Any

from .model import (
    VerificationContext,
    VerifierError,
    canonical_digest,
    file_digest,
    validate_verification_result,
)


class VerificationRuntimeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_tools() -> None:
    missing = [tool for tool in ("git", "docker") if shutil.which(tool) is None]
    if missing:
        raise VerificationRuntimeError("missing required tool(s): " + ", ".join(missing))


def resolve_artifact(root: Path, locator: str) -> Path:
    root = root.resolve()
    candidate = (root / locator).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VerificationRuntimeError(f"artifact locator escapes artifact root: {locator}") from exc
    if not candidate.is_file():
        raise VerificationRuntimeError(f"candidate artifact does not exist: {locator}")
    return candidate


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def clone_revision(context: VerificationContext, workspace: Path) -> None:
    commands = [
        ["git", "init", "--quiet", str(workspace)],
        ["git", "-C", str(workspace), "remote", "add", "origin", context.repo_url],
        ["git", "-C", str(workspace), "fetch", "--quiet", "--depth", "1", "origin", context.source_revision],
        ["git", "-C", str(workspace), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
    ]
    for command in commands:
        result = _run(command)
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise VerificationRuntimeError(detail or "git checkout preparation failed")


def apply_patch(workspace: Path, patch_path: Path) -> None:
    check = _run(["git", "apply", "--check", str(patch_path)], cwd=workspace)
    if check.returncode != 0:
        detail = check.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationRuntimeError("candidate patch cannot be applied cleanly: " + detail)
    applied = _run(["git", "apply", str(patch_path)], cwd=workspace)
    if applied.returncode != 0:
        detail = applied.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationRuntimeError("candidate patch application failed: " + detail)


def changed_paths(workspace: Path) -> list[str]:
    result = _run(["git", "diff", "--name-only", "HEAD", "--", "."], cwd=workspace)
    if result.returncode != 0:
        raise VerificationRuntimeError("unable to enumerate candidate changed paths")
    return [line for line in result.stdout.decode("utf-8", errors="replace").splitlines() if line]


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or path == pattern.rstrip("/") for pattern in patterns)


def scope_violations(context: VerificationContext, paths: list[str]) -> list[str]:
    constraints = context.work_unit["constraints"]
    permissions = context.work_unit["permissions"]
    allowed = constraints["allowed_paths"]
    writable = permissions["filesystem_write"]
    forbidden = constraints["forbidden_paths"]
    violations: list[str] = []
    for path in paths:
        if _matches(path, forbidden):
            violations.append(f"forbidden path changed: {path}")
            continue
        if not _matches(path, allowed):
            violations.append(f"path outside constraints.allowed_paths: {path}")
        if not _matches(path, writable):
            violations.append(f"path outside permissions.filesystem_write: {path}")
    return violations


def docker_check_command(context: VerificationContext, workspace: Path, command: tuple[str, ...]) -> list[str]:
    result = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--cpus",
        "1",
        "--memory",
        "1024m",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
        "--mount",
        f"type=bind,source={workspace.resolve()},target=/workspace",
        "--workdir",
        "/workspace",
    ]
    if os.name == "posix" and hasattr(os, "getuid"):
        result.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    result.extend([context.container_image, *command])
    return result


def _write_evidence(output: Path, evidence_id: str, content: str) -> dict[str, Any]:
    evidence_dir = output / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "-" for c in evidence_id)
    path = evidence_dir / f"{safe_name}.txt"
    path.write_text(content, encoding="utf-8")
    return {
        "id": evidence_id,
        "type": "test_output",
        "locator": str(path.relative_to(output)),
        "digest": file_digest(path),
        "media_type": "text/plain",
    }


def _check_record(spec: Any, status: str, summary: str, evidence_id: str, diagnostics: str = "") -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": spec.id,
        "type": spec.type,
        "required": spec.required,
        "status": status,
        "summary": summary,
        "evidence_ids": [evidence_id],
    }
    if diagnostics:
        record["diagnostics"] = diagnostics
    return record


def run_verification(
    context: VerificationContext,
    *,
    artifact_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    require_tools()
    artifact_root = Path(artifact_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    timer = time.monotonic()

    patch_path = resolve_artifact(artifact_root, context.candidate_artifact["locator"])
    actual_patch_digest = file_digest(patch_path)
    declared_patch_digest = context.candidate_artifact["digest"]

    checks: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    check_status: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="idkmesh-verifier-") as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        clone_revision(context, workspace)

        patch_apply_error = ""
        if actual_patch_digest == declared_patch_digest:
            try:
                apply_patch(workspace, patch_path)
            except VerificationRuntimeError as exc:
                patch_apply_error = str(exc)
        else:
            patch_apply_error = (
                f"candidate artifact digest mismatch: declared {declared_patch_digest}, "
                f"actual {actual_patch_digest}"
            )

        paths = changed_paths(workspace) if not patch_apply_error else []
        violations = scope_violations(context, paths) if not patch_apply_error else []

        for spec in context.checks:
            evidence_id = f"{spec.id}-evidence"
            if spec.mode == "result_schema":
                content = "Worker ResultManifest schema and exact WorkUnit lineage validated before verifier execution.\n"
                item = _write_evidence(output, evidence_id, content)
                evidence.append(item)
                checks.append(_check_record(spec, "passed", "Worker ResultManifest contract is valid and bound to the exact WorkUnit.", evidence_id))
                check_status[spec.id] = "passed"
                continue

            if spec.mode == "artifact_integrity":
                passed = not patch_apply_error and actual_patch_digest == declared_patch_digest
                content = (
                    f"declared={declared_patch_digest}\nactual={actual_patch_digest}\n"
                    + ("patch_apply=ok\n" if not patch_apply_error else f"patch_apply={patch_apply_error}\n")
                )
                item = _write_evidence(output, evidence_id, content)
                item["type"] = "artifact_hash"
                evidence.append(item)
                status = "passed" if passed else "failed"
                checks.append(_check_record(spec, status, "Candidate patch digest and clean application checked.", evidence_id, patch_apply_error))
                check_status[spec.id] = status
                if not passed:
                    findings.append({"severity": "high", "category": "provenance", "summary": patch_apply_error or "candidate patch integrity failed"})
                continue

            if spec.mode == "scope_policy":
                passed = not patch_apply_error and not violations
                content = "changed_paths:\n" + "\n".join(paths) + "\nviolations:\n" + "\n".join(violations) + "\n"
                item = _write_evidence(output, evidence_id, content)
                item["type"] = "static_analysis"
                evidence.append(item)
                status = "passed" if passed else "failed"
                checks.append(_check_record(spec, status, "Candidate repository scope policy checked.", evidence_id, "; ".join(violations)))
                check_status[spec.id] = status
                for violation in violations:
                    findings.append({"severity": "high", "category": "scope", "summary": violation})
                continue

            if spec.mode == "container_command":
                if patch_apply_error:
                    content = "check not run because candidate patch integrity/application failed\n"
                    evidence.append(_write_evidence(output, evidence_id, content))
                    checks.append(_check_record(spec, "skipped", "Hidden/container check skipped because patch could not be trusted/applied.", evidence_id))
                    check_status[spec.id] = "skipped"
                    continue
                command = docker_check_command(context, workspace, spec.command)
                try:
                    result = subprocess.run(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=spec.timeout_seconds,
                        check=False,
                    )
                    stdout = result.stdout.decode("utf-8", errors="replace")
                    stderr = result.stderr.decode("utf-8", errors="replace")
                    content = f"exit_code={result.returncode}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
                    status = "passed" if result.returncode == 0 else "failed"
                    diagnostics = stderr[-4000:] if result.returncode != 0 else ""
                except subprocess.TimeoutExpired as exc:
                    stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
                    stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
                    content = f"timeout_seconds={spec.timeout_seconds}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
                    status = "error"
                    diagnostics = "container verification command timed out"
                item = _write_evidence(output, evidence_id, content)
                evidence.append(item)
                checks.append(_check_record(spec, status, spec.description or "Independent container check executed.", evidence_id, diagnostics))
                check_status[spec.id] = status
                if status != "passed":
                    findings.append({"severity": "high" if spec.required else "medium", "category": "correctness", "summary": f"verification check {spec.id} did not pass"})
                continue

            raise VerificationRuntimeError(f"unsupported verifier check mode: {spec.mode}")

    required_failures = [spec.id for spec in context.checks if spec.required and check_status.get(spec.id) != "passed"]
    if required_failures:
        overall_status = "failed"
        recommendation = "reject_candidate"
        confidence = 1.0
        rationale = "Required independent verification check(s) did not pass: " + ", ".join(required_failures)
    else:
        overall_status = "passed"
        recommendation = "accept_candidate"
        confidence = 1.0
        rationale = "All required independent verification checks passed. This is decision support, not an automatic merge."

    elapsed = max(0.0, time.monotonic() - timer)
    worker_env = context.worker_result["provenance"].get("environment", {})
    verification_result: dict[str, Any] = {
        "schema_version": "0.1",
        "id": f"verification/{context.worker_result['id']}",
        "result_manifest_id": context.worker_result["id"],
        "work_unit_id": context.worker_result["work_unit_id"],
        "work_unit_version": context.worker_result["work_unit_version"],
        "attempt": context.worker_result["attempt"],
        "verifier": {
            "id": context.verifier_id,
            "type": "system",
            "adapter": context.verifier_adapter,
            "adapter_version": context.verifier_adapter_version,
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": context.worker_result["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": bool(worker_env.get("container_image")),
            "correlation_notes": "Independent verifier configuration is not supplied to the worker. Docker runtime technology may still be shared.",
        },
        "status": overall_status,
        "started_at": started_at,
        "finished_at": utc_now(),
        "checks": checks,
        "evidence": evidence,
        "findings": findings,
        "metrics": {
            "required_checks_passed": sum(1 for spec in context.checks if spec.required and check_status.get(spec.id) == "passed"),
            "required_checks_failed": len(required_failures),
            "changed_path_count": len(paths),
            "finding_count": len(findings),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(context.worker_result),
            "work_unit_digest": canonical_digest(context.work_unit),
            "source_revision": context.source_revision,
            "verifier_config_digest": canonical_digest(context.plan),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "container_image": context.container_image,
                "tool_versions": {"idkmesh-independent-verifier": "0.1"},
            },
        },
        "decision_support": {
            "recommendation": recommendation,
            "confidence": confidence,
            "rationale": rationale,
        },
        "extensions": {
            "org.idkmesh.verifier": {
                "candidate_artifact_id": context.candidate_artifact["id"],
                "changed_paths": paths,
            }
        },
    }
    validate_verification_result(verification_result)
    (output / "verification-result.json").write_text(
        json.dumps(verification_result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verification_result
