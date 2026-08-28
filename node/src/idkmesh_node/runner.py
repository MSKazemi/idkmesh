from __future__ import annotations

from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from . import __version__
from .model import WorkUnit, canonical_digest, validate_result_manifest


class RunnerError(RuntimeError):
    """Raised when the local node cannot prepare or execute a Work Unit."""


IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REPO_DIGEST_RE = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")


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


def _run_git_command(
    command: list[str],
    *,
    env: dict[str, str],
    deadline: float,
    phase: str,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
            timeout=_remaining_seconds(deadline, phase),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"Work Unit wall budget exhausted during {phase}") from exc


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
        (
            [
                "git",
                "init",
                "--quiet",
                f"--template={empty_template}",
                f"--separate-git-dir={git_dir}",
                str(workspace),
            ],
            "git initialization",
        ),
        (
            _git_repo_command(workspace, git_dir, ["config", "core.worktree", "/workspace"]),
            "git work-tree configuration",
        ),
        (
            _git_repo_command(workspace, git_dir, ["remote", "add", "origin", work.source.repo_url]),
            "git remote configuration",
        ),
        (
            _git_repo_command(
                workspace,
                git_dir,
                ["fetch", "--quiet", "--depth", "1", "origin", work.source.revision],
            ),
            "git source fetch",
        ),
        (
            _git_repo_command(
                workspace,
                git_dir,
                ["checkout", "--quiet", "--detach", "FETCH_HEAD"],
            ),
            "git source checkout",
        ),
    ]
    for command, phase in commands:
        proc = _run_git_command(command, env=env, deadline=deadline, phase=phase)
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RunnerError(detail or f"{phase} failed")

    # The container may read Git metadata, but the metadata itself is mounted
    # read-only outside /workspace. Host result capture never trusts this pointer.
    _container_git_pointer(workspace)


def _image_repository(reference: str) -> str:
    """Return repository portion for the small v0.1 allowlisted tag surface."""

    without_digest = reference.split("@", 1)[0]
    last_slash = without_digest.rfind("/")
    last_colon = without_digest.rfind(":")
    if last_colon > last_slash:
        return without_digest[:last_colon]
    return without_digest


def parse_image_inspect(payload: bytes, configured_reference: str) -> tuple[str, str]:
    """Return immutable local image ID and matching repository digest."""

    try:
        documents = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError("docker image inspect returned invalid JSON") from exc
    if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
        raise RunnerError("docker image inspect must return exactly one image object")

    document = documents[0]
    image_id = document.get("Id")
    repo_digests = document.get("RepoDigests") or []
    if not isinstance(image_id, str) or not IMAGE_ID_RE.fullmatch(image_id.lower()):
        raise RunnerError("docker image inspect did not return an immutable sha256 image ID")
    image_id = image_id.lower()
    if not isinstance(repo_digests, list):
        raise RunnerError("docker image inspect RepoDigests must be an array")

    repository = _image_repository(configured_reference)
    matching = sorted(
        digest.lower()
        for digest in repo_digests
        if isinstance(digest, str)
        and REPO_DIGEST_RE.fullmatch(digest.lower())
        and digest.split("@", 1)[0] == repository
    )
    if not matching:
        raise RunnerError(
            "allowlisted container tag has no matching immutable repository digest; "
            "pre-pull the expected registry image instead of using a locally retagged/unresolved image"
        )
    return image_id, matching[0]


def resolve_container_image(work: WorkUnit, *, deadline: float) -> tuple[str, str]:
    """Resolve a pre-pulled allowlisted tag to immutable evidence and execution identity.

    The node never relies on an implicit pull during task execution. A controlled
    host must prepare the image first; the worker records and runs the exact local
    sha256 image ID it inspected.
    """

    phase = "container image resolution"
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", work.execution.image],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_remaining_seconds(deadline, phase),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"Work Unit wall budget exhausted during {phase}") from exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RunnerError(
            detail
            or (
                f"container image {work.execution.image!r} is not available locally; "
                "pre-pull it on the controlled host before execution"
            )
        )
    return parse_image_inspect(proc.stdout, work.execution.image)


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


def _git_bytes(
    workspace: Path,
    git_dir: Path,
    git_home: Path,
    args: list[str],
    *,
    deadline: float,
    phase: str,
) -> bytes:
    proc = _run_git_command(
        _git_repo_command(workspace, git_dir, args),
        env=_git_environment(git_home),
        deadline=deadline,
        phase=phase,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RunnerError(detail or f"{phase} failed")
    return proc.stdout


def _decode_nul_paths(raw: bytes) -> list[str]:
    return sorted(
        {
            chunk.decode("utf-8", errors="surrogateescape")
            for chunk in raw.split(b"\0")
            if chunk
        }
    )


def untracked_paths(
    workspace: Path,
    git_dir: Path,
    git_home: Path,
    *,
    deadline: float,
) -> list[str]:
    # Do not use --exclude-standard here. Ignored files are still task outputs and
    # must not disappear from evidence simply because the source repository's
    # .gitignore happens to match them.
    return _decode_nul_paths(
        _git_bytes(
            workspace,
            git_dir,
            git_home,
            ["ls-files", "--others", "-z"],
            deadline=deadline,
            phase="untracked output capture",
        )
    )


def changed_paths(
    workspace: Path,
    git_dir: Path,
    git_home: Path,
    *,
    deadline: float,
) -> list[str]:
    tracked = _decode_nul_paths(
        _git_bytes(
            workspace,
            git_dir,
            git_home,
            ["diff", "--no-ext-diff", "--name-only", "-z", "HEAD", "--", "."],
            deadline=deadline,
            phase="tracked path capture",
        )
    )
    return sorted(
        set(tracked + untracked_paths(workspace, git_dir, git_home, deadline=deadline))
    )


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
    overall_deadline = started + work.wall_seconds
    # Reserve a small bounded tail for evidence capture so a task consuming its
    # execution budget cannot prevent the node from recording why it stopped.
    capture_reserve = min(5.0, work.wall_seconds * 0.10)
    execution_deadline = overall_deadline - capture_reserve

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

    image_id, image_repo_digest = resolve_container_image(work, deadline=execution_deadline)

    with tempfile.TemporaryDirectory(prefix="idkmesh-node-") as temp_dir:
        temp_root = Path(temp_dir)
        workspace = temp_root / "workspace"
        workspace.mkdir()
        git_dir = temp_root / "git-meta"
        git_home = temp_root / "git-home"
        clone_revision(
            work,
            workspace,
            git_dir,
            git_home,
            deadline=execution_deadline,
        )

        command = docker_command(
            work,
            workspace,
            container_name,
            git_dir,
            image_ref=image_id,
        )
        docker_timeout = min(
            float(work.execution.timeout_seconds),
            _remaining_seconds(execution_deadline, "task container execution"),
        )
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=docker_timeout,
                check=False,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            # Mandatory containment cleanup is best-effort and tightly bounded.
            # It may outlive the task's execution slice, but it does not grant the
            # task additional execution time.
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                pass

        metadata_violations = protected_metadata_violations(workspace)
        untracked = untracked_paths(
            workspace,
            git_dir,
            git_home,
            deadline=overall_deadline,
        )
        paths = changed_paths(
            workspace,
            git_dir,
            git_home,
            deadline=overall_deadline,
        )
        path_violations = path_policy_violations(work, paths)
        artifact_violations = unpackaged_artifact_violations(untracked)
        patch_raw = _git_bytes(
            workspace,
            git_dir,
            git_home,
            ["diff", "--binary", "--no-ext-diff", "HEAD", "--", "."],
            deadline=overall_deadline,
            phase="candidate patch capture",
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
                    "If patch_truncated=1 this file is diagnostic evidence only."
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
                "The task ran by immutable local container image ID.",
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
                "container_image": image_repo_digest,
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
                "configured_container_image": work.execution.image,
                "resolved_container_image_id": image_id,
                "resolved_container_repo_digest": image_repo_digest,
                "whole_attempt_budget_seconds": work.wall_seconds,
                "changed_paths": paths,
                "untracked_paths": untracked,
                "path_policy_violations": path_violations,
                "unpackaged_artifact_violations": artifact_violations,
                "protected_metadata_violations": metadata_violations,
                "output_policy_violations": output_violations,
                "runtime_policy_violations": runtime_violations,
                "policy_violations": violations,
                "timed_out": timed_out,
            }
        },
    }
    validate_result_manifest(result)

    result_path = output / "result-manifest.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
