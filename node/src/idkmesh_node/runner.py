from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

from .model import WorkUnit


class RunnerError(RuntimeError):
    """Raised when the local node cannot prepare or execute a Work Unit."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(data: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(data) > limit
    chunk = data[:limit]
    return chunk.decode("utf-8", errors="replace"), truncated


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
            raise RunnerError(proc.stderr.decode("utf-8", errors="replace").strip() or "git preparation failed")


def docker_command(work: WorkUnit, workspace: Path, container_name: str) -> list[str]:
    command = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(work.execution.pids_limit),
        "--cpus", str(work.execution.cpus),
        "--memory", f"{work.execution.memory_mb}m",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--mount", f"type=bind,source={workspace.resolve()},target=/workspace",
        "--workdir", "/workspace",
    ]
    if os.name == "posix" and hasattr(os, "getuid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    command.extend([work.execution.image, *work.execution.command])
    return command


def _git_capture(workspace: Path, args: list[str], limit: int) -> tuple[str, bool]:
    proc = subprocess.run(
        ["git", "-C", str(workspace), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RunnerError(proc.stderr.decode("utf-8", errors="replace").strip() or "git result capture failed")
    return _truncate(proc.stdout, limit)


def run_work_unit(work: WorkUnit, raw_work_unit: bytes, output_dir: str | Path) -> dict:
    require_tools()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    started = time.monotonic()
    container_name = f"idkmesh-{work.id[:32].lower()}-{uuid.uuid4().hex[:8]}"
    exit_code: int | None = None
    timed_out = False
    stdout = b""
    stderr = b""

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
            subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        status, status_truncated = _git_capture(workspace, ["status", "--porcelain=v1", "--untracked-files=all"], work.output.max_log_bytes)
        patch, patch_truncated = _git_capture(workspace, ["diff", "--binary", "--no-ext-diff", "HEAD", "--", "."], work.output.max_patch_bytes)

        # Git diff excludes untracked files. Record their names in status; future protocol versions
        # should package explicitly approved untracked artifacts with separate size/type limits.
        patch_path = output / "changes.patch"
        patch_path.write_text(patch, encoding="utf-8")

    stdout_text, stdout_truncated = _truncate(stdout, work.output.max_log_bytes)
    stderr_text, stderr_truncated = _truncate(stderr, work.output.max_log_bytes)
    (output / "stdout.txt").write_text(stdout_text, encoding="utf-8")
    (output / "stderr.txt").write_text(stderr_text, encoding="utf-8")

    result = {
        "protocol_version": work.version,
        "work_unit_id": work.id,
        "work_unit_sha256": hashlib.sha256(raw_work_unit).hexdigest(),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source": asdict(work.source),
        "execution": {
            "image": work.execution.image,
            "command": list(work.execution.command),
            "timeout_seconds": work.execution.timeout_seconds,
            "cpus": work.execution.cpus,
            "memory_mb": work.execution.memory_mb,
            "pids_limit": work.execution.pids_limit,
            "network": "none",
        },
        "outcome": {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "status": status,
            "status_truncated": status_truncated,
            "patch_truncated": patch_truncated,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        },
        "artifacts": {
            "patch": "changes.patch",
            "stdout": "stdout.txt",
            "stderr": "stderr.txt",
        },
        "trust": "unverified-candidate",
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
