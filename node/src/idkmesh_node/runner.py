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


def _remaining_seconds(deadline: float, phase: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RunnerError(f"Work Unit wall budget exhausted during {phase}")
    return remaining


def require_tools() -> None:
    missing = [tool for tool in ("git", "docker") if shutil.which(tool) is None]
    if missing:
        raise RunnerError(f"missing required tool(s): {', '.join(missing)}")


def _git_environment(config_home: Path) -> dict[str, str]:
    """Return a Git environment isolated from host/user Git configuration.

    Work Unit repositories are untrusted inputs. Host-level Git filters,
    credential helpers, fsmonitor hooks, aliases, or template configuration must
    never become an execution path outside the task container merely because a
    repository contains matching attributes/config triggers.
    """

    config_home.mkdir(parents=True, exist_ok=True)
    xdg_home = config_home / "xdg"
    xdg_home.mkdir(parents=True, exist_ok=True)

    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "HOME": str(config_home),
            "XDG_CONFIG_HOME": str(xdg_home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    return env


def _git_repo_command(workspace: Path, git_dir: Path, args: list[str]) -> list[str]:
    """Address trusted Git metadata explicitly instead of discovering workspace .git."""

    return [
        "git",
        "--git-dir",
        str(git_dir),
        "--work-tree",
        str(workspace),
        *args,
    ]


def _container_git_pointer(workspace: Path) -> Path:
    pointer = workspace / ".git"
    pointer.write_text("gitdir: /git-meta\n", encoding="utf-8")
    return pointer


def clone_revision(
    work: WorkUnit,
    workspace: Path,
    git_dir: Path,
    git_home: Path,
    *,
    deadline: float,
) -> None:
    """Materialize an immutable revision while keeping control metadata outside the task root."""

    empty_template = git_home / "empty-template"
    empty_template.mkdir(parents=True, exist_ok=True)
    env = _git_environment(git_home)

    commands = [
        [
            "git",
            "init",
            "--quiet",
            f"--template={empty_template}",
            f"--separate-git-dir={git_dir}",
            str(workspace),
        ],
        _git_repo_command(workspace, git_dir, ["config", "core.worktree", "/workspace"]),
        _git_repo_command(workspace, git_dir, ["remote", "add", "origin", work.source.repo_url]),
        _git_repo_command(
            workspace,
            git_dir,
            ["fetch", "--quiet", "--depth", "1", "origin", work.source.revision],
        ),
        _git_repo_command(
            workspace,
            git_dir,
            ["checkout", "--quiet", "--detach", "FETCH_HEAD"],
        ),
    ]
    for command in commands:
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=_remaining_seconds(deadline, "source preparation"),
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RunnerError("source preparation exceeded Work Unit wall budget") from exc
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RunnerError(detail or "git preparation failed")

    # The container may read Git metadata, but the metadata itself is mounted
    # read-only outside /workspace. Host result capture never trusts this pointer.
    _container_git_pointer(workspace)


def resolve_container_image_id(image: str, *, deadline: float) -> str:
    """Resolve a preloaded allowed image to the exact immutable local image ID.

    Node v0.1 refuses an implicit pull during task execution. A controlled host
    preloads the allowlisted image first; the worker then executes by immutable
    image ID and records that ID in its ResultManifest extension.
    """

    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", "--format={{.Id}}", image],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_remaining_seconds(deadline, "container image resolution"),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container image resolution exceeded Work Unit wall budget") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RunnerError(
            "allowed container image must be preloaded on the controlled host"
            + (f": {detail}" if detail else "")
        )
    image_id = proc.stdout.decode("utf-8", errors="strict").strip().lower()
    if not image_id.startswith("sha256:") or len(image_id) != 71:
        raise RunnerError(f"Docker returned an invalid immutable image ID for {image!r}")
    try:
        int(image_id[7:], 16)
    except ValueError as exc:
        raise RunnerError(f"Docker returned a non-hex image ID for {image!r}") from exc
    return image_id


def docker_command(
    work: WorkUnit,
    workspace: Path,
    container_name: str,
    git_dir: Path | None = None,
    *,
    image_ref: str | None = None,
) -> list[str]:
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
    ]
    if git_dir is not None:
        command.extend(
            [
                "--mount",
                f"type=bind,source={git_dir.resolve()},target=/git-meta,readonly",
            ]
        )
    command.extend(["--workdir", "/workspace"])
    if os.name == "posix" and hasattr(os, "getuid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    command.extend([image_ref or work.execution.image, *work.execution.command])
    return command


def _git_bytes(workspace: Path, git_dir: Path, git_home: Path, args: list[str]) -> bytes:
    proc = subprocess.run(
        _git_repo_command(workspace, git_dir, args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=_git_environment(git_home),
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


def untracked_paths(workspace: Path, git_dir: Path, git_home: Path) -> list[str]:
    # Do not use --exclude-standard here. Ignored files are still task outputs and
    # must not disappear from evidence simply because the source repository's
    # .gitignore happens to match them.
    return _decode_nul_paths(
        _git_bytes(workspace, git_dir, git_home, ["ls-files", "--others", "-z"])
    )


def changed_paths(workspace: Path, git_dir: Path, git_home: Path) -> list[str]:
    tracked = _decode_nul_paths(
        _git_bytes(
            workspace,
            git_dir,
            git_home,
            ["diff", "--no-ext-diff", "--name-only", "-z", "HEAD", "--", "."],
        )
    )
    return sorted(set(tracked + untracked_paths(workspace, git_dir, git_home)))


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


def protected_metadata_violations(workspace: Path) -> list[str]:
    """Detect attempts to tamper with the task-visible pointer to trusted Git metadata."""

    pointer = workspace / ".git"
    expected = "gitdir: /git-meta\n"
    try:
        if not pointer.is_file() or pointer.read_text(encoding="utf-8") != expected:
            return ["task modified protected .git metadata pointer"]
    except (OSError, UnicodeError):
        return ["task modified protected .git metadata pointer"]
    return []


def output_policy_violations(*, patch_truncated: bool, max_patch_bytes: int) -> list[str]:
    """A candidate patch is evidence; silently truncating it cannot be success."""

    if not patch_truncated:
        return []
    return [
        "candidate patch exceeded output_limits.max_patch_bytes "
        f"({max_patch_bytes}) and was truncated"
    ]


def run_work_unit(work: WorkUnit, output_dir: str | Path) -> dict:
    require_tools()
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise RunnerError("output directory must be empty to avoid mixing result bundles")
    output.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    started = time.monotonic()
    deadline = started + work.wall_seconds
    container_name = f"idkmesh-{work.id.replace('/', '-')[:28]}-{uuid.uuid4().hex[:8]}"
    exit_code: int | None = None
    timed_out = False
    stdout = b""
    stderr = b""
    paths: list[str] = []
    untracked: list[str] = []
    path_violations: list[str] = []
    artifact_violations: list[str] = []
    metadata_violations: list[str] = []
    output_violations: list[str] = []
    runtime_violations: list[str] = []
    image_id = ""

    with tempfile.TemporaryDirectory(prefix="idkmesh-node-") as temp_dir:
        temp_root = Path(temp_dir)
        workspace = temp_root / "workspace"
        workspace.mkdir()
        git_dir = temp_root / "git-meta"
        git_home = temp_root / "git-home"
        image_id = resolve_container_image_id(work.execution.image, deadline=deadline)
        clone_revision(work, workspace, git_dir, git_home, deadline=deadline)

        command = docker_command(
            work,
            workspace,
            container_name,
            git_dir,
            image_ref=image_id,
        )
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=min(
                    float(work.execution.timeout_seconds),
                    _remaining_seconds(deadline, "container execution"),
                ),
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

        metadata_violations = protected_metadata_violations(workspace)
        untracked = untracked_paths(workspace, git_dir, git_home)
        paths = changed_paths(workspace, git_dir, git_home)
        path_violations = path_policy_violations(work, paths)
        artifact_violations = unpackaged_artifact_violations(untracked)
        patch_raw = _git_bytes(
            workspace,
            git_dir,
            git_home,
            ["diff", "--binary", "--no-ext-diff", "HEAD", "--", "."],
        )

    patch, patch_truncated = _truncate(patch_raw, work.output.max_patch_bytes)
    stdout, stdout_truncated = _truncate(stdout, work.output.max_log_bytes)
    stderr, stderr_truncated = _truncate(stderr, work.output.max_log_bytes)
    output_violations = output_policy_violations(
        patch_truncated=patch_truncated,
        max_patch_bytes=work.output.max_patch_bytes,
    )

    patch_path = output / "changes.patch"
    stdout_path = output / "stdout.txt"
    stderr_path = output / "stderr.txt"
    patch_path.write_bytes(patch)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    elapsed = max(0.0, time.monotonic() - started)
    if elapsed > work.wall_seconds:
        runtime_violations.append(
            "whole-attempt wall budget exceeded: "
            f"{elapsed:.3f}s > {work.wall_seconds:.3f}s"
        )
    violations = (
        path_violations
        + artifact_violations
        + metadata_violations
        + output_violations
        + runtime_violations
    )

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
                "description": (
                    "Unverified tracked-file candidate patch produced by the local node. "
                    "If patch_truncated=1 the worker fails closed and this file is diagnostic evidence only."
                ),
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
                "Host Git metadata was kept outside the task-writable workspace.",
                "The exact local container image ID was resolved before execution and used as the Docker run image reference.",
                "The Work Unit wall budget constrained image resolution, source preparation, and task execution.",
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
                "path_policy_violations": path_violations,
                "unpackaged_artifact_violations": artifact_violations,
                "protected_metadata_violations": metadata_violations,
                "output_policy_violations": output_violations,
                "runtime_policy_violations": runtime_violations,
                "policy_violations": violations,
                "timed_out": timed_out,
                "container_image_id": image_id,
            }
        },
    }
    validate_result_manifest(result)

    result_path = output / "result-manifest.json"
    import json

    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
