from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .model import WorkUnit, canonical_digest, repo_root


class RunnerError(RuntimeError):
    """Raised when the local node cannot prepare or execute a Work Unit."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _truncate(data: bytes, limit: int) -> tuple[bytes, bool]:
    return data[:limit], len(data) > limit


def require_tools() -> None:
    missing = [tool for tool in ("git", "docker") if shutil.which(tool) is None]
    if missing:
        raise RunnerError(f"missing required tool(s): {', '.join(missing)}")


def clone_revision(work: WorkUnit, workspace: Path) -> None:
    commands = [
        ["git", "init", "--quiet", str(workspace)],
        ["git", "-C", str(workspace), "remote", "add", "origin", work.source.repo_url],
        ["git", "-C", str(workspace), "fetch", "--quiet", "--depth", "1", "origin", work.source.revision],
        ["git", "-C", str(workspace), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
    ]
    for command in commands:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RunnerError(detail or "git preparation failed")


def docker_command(work: WorkUnit, workspace: Path, container_name: str) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(work.execution.pids_limit),
        "--cpus",
        str(work.execution.cpus),
        "--memory",
        f"{work.execution.memory_mb}m",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--mount",
        f"type=bind,source={workspace.resolve()},target=/workspace",
        "--workdir",
        "/workspace",
    ]
    if os.name == "posix" and hasattr(os, "getuid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    command.extend([work.execution.image, *work.execution.command])
    return command


def _git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _changed_paths(workspace: Path) -> tuple[list[str], list[str]]:
    proc = _git(workspace, ["status", "--porcelain=v1", "--untracked-files=all"])
    if proc.returncode != 0:
        raise RunnerError(proc.stderr.decode("utf-8", errors="replace").strip() or "git status failed")

    changed: list[str] = []
    untracked: list[str] = []
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        changed.append(path)
        if status == "??":
            untracked.append(path)
    return changed, untracked


def _normalize_prefix(raw: str) -> str:
    value = str(PurePosixPath(raw)).lstrip("./")
    return value.rstrip("/")


def _matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = str(PurePosixPath(path)).lstrip("./")
    normalized_prefix = _normalize_prefix(prefix)
    if not normalized_prefix:
        return False
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


def policy_violations(work: WorkUnit, changed_paths: list[str]) -> list[str]:
    violations: list[str] = []
    for path in changed_paths:
        if any(_matches_prefix(path, prefix) for prefix in work.forbidden_paths):
            violations.append(f"forbidden path changed: {path}")
            continue
        if not any(_matches_prefix(path, prefix) for prefix in work.allowed_paths):
            violations.append(f"path outside constraints.allowed_paths changed: {path}")
    return violations


def _capture_patch(workspace: Path, untracked: list[str], limit: int) -> tuple[bytes, bool]:
    if untracked:
        proc = _git(workspace, ["add", "-N", "--", *untracked])
        if proc.returncode != 0:
            raise RunnerError(proc.stderr.decode("utf-8", errors="replace").strip() or "git add -N failed")
    proc = _git(workspace, ["diff", "--binary", "--no-ext-diff", "HEAD", "--", "."])
    if proc.returncode != 0:
        raise RunnerError(proc.stderr.decode("utf-8", errors="replace").strip() or "git diff failed")
    return _truncate(proc.stdout, limit)


def _validate_result_manifest(result: dict[str, Any]) -> None:
    schema_path = repo_root() / "schemas/result-manifest-v0.1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = []
        for error in errors[:10]:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{location}: {error.message}")
        raise RunnerError("generated ResultManifest is invalid: " + "; ".join(rendered))


def run_work_unit(work: WorkUnit, output_dir: str | Path, *, attempt: int = 1) -> dict[str, Any]:
    require_tools()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    started = time.monotonic()
    container_name = f"idkmesh-{work.id.replace('/', '-')[:28].lower()}-{uuid.uuid4().hex[:8]}"
    exit_code: int | None = None
    timed_out = False
    stdout = b""
    stderr = b""
    changed_paths: list[str] = []
    violations: list[str] = []
    patch = b""
    patch_truncated = False

    with tempfile.TemporaryDirectory(prefix="idkmesh-node-") as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        clone_revision(work, workspace)

        command = docker_command(work, workspace, container_name)
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=work.execution.timeout_seconds,
                check=False,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        changed_paths, untracked = _changed_paths(workspace)
        violations = policy_violations(work, changed_paths)
        patch, patch_truncated = _capture_patch(
            workspace,
            untracked,
            work.execution.max_patch_bytes,
        )

    stdout, stdout_truncated = _truncate(stdout, work.execution.max_log_bytes)
    stderr, stderr_truncated = _truncate(stderr, work.execution.max_log_bytes)

    patch_path = output / "changes.patch"
    stdout_path = output / "stdout.txt"
    stderr_path = output / "stderr.txt"
    patch_path.write_bytes(patch)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    if timed_out:
        status = "timeout"
    elif exit_code == 0 and not violations and not patch_truncated:
        status = "succeeded"
    else:
        status = "failed"

    elapsed = max(0.0, time.monotonic() - started)
    work_digest = canonical_digest(work.data)
    execution_profile = work.data.get("extensions", {}).get("org.idkmesh.execution.docker", {})
    result: dict[str, Any] = {
        "schema_version": "0.1",
        "id": f"{work.id}/attempt-{attempt}",
        "work_unit_id": work.id,
        "work_unit_version": work.version,
        "attempt": attempt,
        "worker": {
            "id": "idkmesh-node/local",
            "type": "system",
            "adapter": "docker-command",
            "adapter_version": "0.1",
        },
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "produced_artifacts": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "locator": patch_path.name,
                "digest": _sha256_file(patch_path),
                "media_type": "text/x-diff",
                "description": "Unverified candidate patch captured from the sandbox workspace.",
            }
        ],
        "logs": [
            {
                "type": "stdout",
                "locator": stdout_path.name,
                "digest": _sha256_file(stdout_path),
            },
            {
                "type": "stderr",
                "locator": stderr_path.name,
                "digest": _sha256_file(stderr_path),
            },
        ],
        "metrics": {
            "exit_code": exit_code,
            "changed_path_count": len(changed_paths),
            "policy_violation_count": len(violations),
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": "Local sandbox execution finished; this is an unverified worker self-report.",
            "claims": [
                f"sandbox process status: {status}",
                "candidate artifacts still require independent verification",
            ],
            "confidence": {
                "value": 1.0 if status == "succeeded" else 0.0,
                "meaning": "uncalibrated",
            },
        },
        "provenance": {
            "work_unit_digest": work_digest,
            "source_revision": work.source.revision,
            "worker_config_digest": canonical_digest(execution_profile),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "container_image": work.execution.image,
                "tool_versions": {"idkmesh-node": "0.1"},
            },
        },
        "verification_request": {
            "expected_validator_ids": list(work.validator_ids),
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Worker completion is not acceptance. Verify the patch independently before integration.",
        },
        "extensions": {
            "org.idkmesh.node": {
                "changed_paths": changed_paths,
                "policy_violations": violations,
                "timed_out": timed_out,
                "patch_truncated": patch_truncated,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            }
        },
    }
    _validate_result_manifest(result)
    (output / "result-manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
