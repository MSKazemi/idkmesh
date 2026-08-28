from __future__ import annotations

from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import uuid

from . import __version__
from .model import WorkUnit, canonical_digest, validate_result_manifest


class RunnerError(RuntimeError):
    """Raised when the local node cannot prepare or execute a Work Unit."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _truncate(data: bytes, limit: int) -> tuple[bytes, bool]:
    return data[:limit], len(data) > limit


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


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


def _git_bytes(workspace: Path, args: list[str]) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(workspace), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RunnerError(detail or "git result capture failed")
    return proc.stdout


def _decode_nul_paths(raw: bytes) -> list[str]:
    return sorted(
        {
            chunk.decode("utf-8", errors="surrogateescape")
            for chunk in raw.split(b"\0")
            if chunk
        }
    )


def untracked_paths(workspace: Path) -> list[str]:
    return _decode_nul_paths(
        _git_bytes(workspace, ["ls-files", "--others", "--exclude-standard", "-z"])
    )


def changed_paths(workspace: Path) -> list[str]:
    tracked = _decode_nul_paths(
        _git_bytes(workspace, ["diff", "--name-only", "-z", "HEAD", "--", "."])
    )
    return sorted(set(tracked + untracked_paths(workspace)))


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def path_policy_violations(work: WorkUnit, paths: list[str]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        if _matches(path, work.forbidden_paths):
            violations.append(f"forbidden path changed: {path}")
        if not _matches(path, work.allowed_paths):
            violations.append(f"path outside constraints.allowed_paths: {path}")
        if not _matches(path, work.write_paths):
            violations.append(f"path outside permissions.filesystem_write: {path}")
    return violations


def unpackaged_artifact_violations(paths: list[str]) -> list[str]:
    """Fail closed until node v0.1 can package untracked artifacts explicitly."""
    return [
        f"untracked artifact is not packaged by node v0.1: {path}"
        for path in paths
    ]


def run_work_unit(work: WorkUnit, output_dir: str | Path) -> dict:
    require_tools()
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise RunnerError("output directory must be empty to avoid mixing result bundles")
    output.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    started = time.monotonic()
    container_name = f"idkmesh-{work.id.replace('/', '-')[:28]}-{uuid.uuid4().hex[:8]}"
    exit_code: int | None = None
    timed_out = False
    stdout = b""
    stderr = b""
    paths: list[str] = []
    untracked: list[str] = []
    violations: list[str] = []

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

        untracked = untracked_paths(workspace)
        paths = changed_paths(workspace)
        violations = path_policy_violations(work, paths)
        violations.extend(unpackaged_artifact_violations(untracked))
        patch_raw = _git_bytes(workspace, ["diff", "--binary", "--no-ext-diff", "HEAD", "--", "."])

    patch, patch_truncated = _truncate(patch_raw, work.output.max_patch_bytes)
    stdout, stdout_truncated = _truncate(stdout, work.output.max_log_bytes)
    stderr, stderr_truncated = _truncate(stderr, work.output.max_log_bytes)

    patch_path = output / "changes.patch"
    stdout_path = output / "stdout.txt"
    stderr_path = output / "stderr.txt"
    patch_path.write_bytes(patch)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    elapsed = max(0.0, time.monotonic() - started)
    if timed_out:
        status = "timeout"
    elif exit_code != 0 or violations:
        status = "failed"
    else:
        status = "succeeded"

    result = {
        "schema_version": "0.1",
        "id": f"{work.id}/attempt-1-{uuid.uuid4().hex[:10]}",
        "work_unit_id": work.id,
        "work_unit_version": work.version,
        "attempt": 1,
        "worker": {
            "id": "local/idkmesh-node",
            "type": "system",
            "adapter": "idkmesh-node",
            "adapter_version": __version__,
        },
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "produced_artifacts": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "locator": "changes.patch",
                "digest": _sha256_bytes(patch),
                "media_type": "text/x-diff",
                "description": "Unverified tracked-file candidate patch produced by the local node.",
            }
        ],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": _sha256_bytes(stdout)},
            {"type": "stderr", "locator": "stderr.txt", "digest": _sha256_bytes(stderr)},
        ],
        "metrics": {
            "exit_code": exit_code,
            "changed_file_count": len(paths),
            "untracked_file_count": len(untracked),
            "policy_violation_count": len(violations),
            "stdout_truncated": int(stdout_truncated),
            "stderr_truncated": int(stderr_truncated),
            "patch_truncated": int(patch_truncated),
        },
        "resources": {"wall_seconds": elapsed},
        "self_report": {
            "summary": "Local sandbox execution completed; all outputs remain unverified candidates.",
            "claims": [
                "The task container was launched with Docker network mode none.",
                "The candidate must be independently verified before acceptance.",
            ],
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work.document),
            "source_revision": work.source.revision,
            "worker_config_digest": canonical_digest(work.binding),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "container_image": work.execution.image,
                "tool_versions": {"idkmesh-node": __version__},
            },
        },
        "verification_request": {
            "expected_validator_ids": list(work.required_validator_ids),
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Worker self-report is not an acceptance verdict.",
        },
        "extensions": {
            "org.idkmesh.node.v0_1": {
                "changed_paths": paths,
                "untracked_paths": untracked,
                "path_policy_violations": violations,
                "timed_out": timed_out,
            }
        },
    }
    validate_result_manifest(result)

    result_path = output / "result-manifest.json"
    import json

    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
