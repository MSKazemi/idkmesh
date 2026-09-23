"""Fail-closed local-agent execution boundary and execution-neutral primitives.

The raw process/worktree helpers remain useful C4-B/C primitives but are not a
hostile-code sandbox. Real coding-agent presets may run only through an explicit
LocalSandboxExecutor whose enforcement capabilities satisfy the canonical
WorkUnit and AgentPreset before execution.

Candidate patches and logs are captured after sandbox execution into bounded,
content-addressed artifacts outside worker authority. The module grants no
verification, acceptance, or repository integration authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterable, Mapping, Protocol

from idkmesh.agent_presets import AgentPreset, get_builtin_preset
from idkmesh.candidate_reference import ArtifactBundleCandidateReference
from idkmesh.local_candidate_reader import LocalArtifactBundleReader
from idkmesh.result_manifest_builder import (
    ExecutionEnvironment,
    LogReference,
    ResourceUsage,
    SelfReport,
    WorkerIdentity,
    build_result_manifest,
)
from idkmesh.work_unit_binding import bind_work_unit_source


class LocalRunnerError(RuntimeError):
    """Fail-closed local-runner setup or execution error."""


@dataclass(frozen=True)
class ProcessLimits:
    timeout_seconds: float = 300.0
    max_output_bytes: int = 1_000_000
    max_stdin_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number")
        for name in ("max_output_bytes", "max_stdin_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    duration_seconds: float
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def _run_git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository), *args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"PATH": os.environ.get("PATH", "")},
    )
    if completed.returncode != 0:
        raise LocalRunnerError(
            f"git {' '.join(args)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def resolve_exact_revision(repository: Path, revision: str) -> str:
    """Resolve revision to one commit SHA, rejecting ambiguous/non-commit refs."""
    if not revision or revision.startswith("-"):
        raise LocalRunnerError("revision must be a non-option Git revision")
    resolved = _run_git(repository, "rev-parse", "--verify", f"{revision}^{{commit}}")
    if not resolved:
        raise LocalRunnerError("revision did not resolve to a commit")
    return resolved


class DisposableGitWorkspace:
    """Context-managed detached worktree removed deterministically on exit."""

    def __init__(self, repository: str | Path, revision: str) -> None:
        self.repository = Path(repository).resolve()
        self.requested_revision = revision
        self.source_sha = ""
        self.path: Path | None = None
        self._temp_root: Path | None = None

    def __enter__(self) -> "DisposableGitWorkspace":
        if not (self.repository / ".git").exists():
            raise LocalRunnerError(f"not a Git worktree: {self.repository}")

        self.source_sha = resolve_exact_revision(self.repository, self.requested_revision)
        self._temp_root = Path(tempfile.mkdtemp(prefix="idkmesh-agent-"))
        self.path = self._temp_root / "workspace"

        completed = subprocess.run(
            (
                "git",
                "-C",
                str(self.repository),
                "worktree",
                "add",
                "--detach",
                str(self.path),
                self.source_sha,
            ),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": os.environ.get("PATH", "")},
        )
        if completed.returncode != 0:
            self._cleanup_files()
            raise LocalRunnerError(
                "failed to materialize disposable worktree: "
                + completed.stderr.strip()
            )

        actual = resolve_exact_revision(self.path, "HEAD")
        if actual != self.source_sha:
            self.__exit__(None, None, None)
            raise LocalRunnerError(
                f"materialized SHA mismatch: expected {self.source_sha}, got {actual}"
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.path is not None and self.path.exists():
            subprocess.run(
                (
                    "git",
                    "-C",
                    str(self.repository),
                    "worktree",
                    "remove",
                    "--force",
                    str(self.path),
                ),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={"PATH": os.environ.get("PATH", "")},
            )
        self._cleanup_files()
        subprocess.run(
            ("git", "-C", str(self.repository), "worktree", "prune"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "")},
        )

    def _cleanup_files(self) -> None:
        if self._temp_root is not None:
            shutil.rmtree(self._temp_root, ignore_errors=True)


def minimal_environment(
    allowed_names: Iterable[str],
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy only explicitly allowed variables plus a minimal executable PATH."""
    source_env = os.environ if source is None else source
    result = {"PATH": source_env.get("PATH", os.defpath)}
    for name in allowed_names:
        if not isinstance(name, str) or re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) is None:
            raise LocalRunnerError(f"invalid environment allowlist name: {name!r}")
        if name == "PATH":
            continue
        if name in source_env:
            value = source_env[name]
            if not isinstance(value, str) or "\x00" in value:
                raise LocalRunnerError(f"invalid environment value for {name}")
            result[name] = value
    return result


def _drain_bounded(
    pipe,
    limit: int,
    chunks: list[bytes],
    truncated: list[bool],
) -> None:
    """Drain a pipe without allowing retained output to exceed ``limit``."""
    retained = 0
    try:
        while True:
            chunk = pipe.read(64 * 1024)
            if not chunk:
                break
            remaining = limit - retained
            if remaining > 0:
                kept = chunk[:remaining]
                chunks.append(kept)
                retained += len(kept)
            if len(chunk) > remaining:
                truncated[0] = True
    finally:
        pipe.close()


def _write_stdin(pipe, data: bytes) -> None:
    try:
        pipe.write(data)
        pipe.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        pipe.close()


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Best-effort cleanup for the raw execution-neutral process primitive.

    On POSIX the child starts a new session, so the process-group identifier
    remains usable after the leader exits while descendants are still alive.
    This prevents a background descendant that inherited stdout/stderr from
    keeping the bounded reader threads open forever.
    """
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return
    if process.poll() is None:
        process.kill()


def run_bounded_process(
    argv: Iterable[str],
    *,
    cwd: str | Path,
    limits: ProcessLimits | None = None,
    env: Mapping[str, str] | None = None,
    stdin_text: str | None = None,
) -> ProcessResult:
    """Run one argv-only process and normalize timeout/output evidence."""
    command = tuple(argv)
    if not command or any(not isinstance(token, str) or not token for token in command):
        raise LocalRunnerError("argv must contain non-empty string tokens")
    if any("\x00" in token or "\n" in token or "\r" in token for token in command):
        raise LocalRunnerError("argv tokens must not contain control line breaks")

    workdir = Path(cwd)
    if not workdir.is_dir():
        raise LocalRunnerError(f"cwd is not a directory: {workdir}")

    active_limits = limits or ProcessLimits()
    active_env = dict(env or minimal_environment(()))
    stdin_bytes = None if stdin_text is None else stdin_text.encode("utf-8")
    if stdin_bytes is not None and len(stdin_bytes) > active_limits.max_stdin_bytes:
        raise LocalRunnerError("stdin exceeds max_stdin_bytes")

    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=workdir,
        env=active_env,
        stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=os.name == "posix",
    )
    assert process.stdout is not None and process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_truncated = [False]
    stderr_truncated = [False]
    readers = (
        threading.Thread(
            target=_drain_bounded,
            args=(process.stdout, active_limits.max_output_bytes, stdout_chunks, stdout_truncated),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_bounded,
            args=(process.stderr, active_limits.max_output_bytes, stderr_chunks, stderr_truncated),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    if stdin_bytes is not None:
        assert process.stdin is not None
        threading.Thread(
            target=_write_stdin,
            args=(process.stdin, stdin_bytes),
            daemon=True,
        ).start()

    timed_out = False
    try:
        process.wait(timeout=active_limits.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_tree(process)
        process.wait()
    finally:
        # A normally exited leader may have left descendants behind. POSIX
        # process-group cleanup must therefore run on every exit, not only on
        # timeout. A real coding-agent path still requires a sandbox executor;
        # this only hardens the execution-neutral primitive.
        _terminate_process_tree(process)

    for reader in readers:
        reader.join(timeout=2.0)
    if any(reader.is_alive() for reader in readers):
        raise LocalRunnerError(
            "process output pipes remained open after process-tree cleanup"
        )

    duration = time.monotonic() - started
    return ProcessResult(
        argv=command,
        returncode=None if timed_out else process.returncode,
        timed_out=timed_out,
        duration_seconds=round(duration, 6),
        stdout=b"".join(stdout_chunks).decode("utf-8", errors="replace"),
        stderr=b"".join(stderr_chunks).decode("utf-8", errors="replace"),
        stdout_truncated=stdout_truncated[0],
        stderr_truncated=stderr_truncated[0],
    )


@dataclass(frozen=True)
class SandboxLimits:
    """Limits a production sandbox executor must enforce for one attempt."""

    wall_seconds: float
    cpu_seconds: float
    memory_mb: int
    disk_mb: int
    max_processes: int
    max_output_bytes: int = 1_000_000
    max_stdin_bytes: int = 1_000_000
    max_candidate_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in ("wall_seconds", "cpu_seconds"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number")
        for name in (
            "memory_mb",
            "disk_mb",
            "max_processes",
            "max_output_bytes",
            "max_stdin_bytes",
            "max_candidate_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class SandboxCapabilities:
    """Attested enforcement properties required by the orchestration layer."""

    network_policy: str
    process_tree_isolation: bool
    cpu_limit: bool
    memory_limit: bool
    disk_limit: bool
    process_limit: bool
    filesystem_isolation: bool
    credential_isolation: bool

    def __post_init__(self) -> None:
        if self.network_policy not in {"disabled", "model_only", "allowlisted"}:
            raise ValueError("unsupported sandbox network_policy")


class LocalSandboxExecutor(Protocol):
    """Execution backend boundary for hostile/untrusted coding-agent processes."""

    capabilities: SandboxCapabilities

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        limits: SandboxLimits,
        env: Mapping[str, str],
        stdin_text: str | None,
    ) -> ProcessResult:
        """Execute one candidate process inside the backend's enforced sandbox."""


@dataclass(frozen=True)
class LocalAgentRunResult:
    """Provider-neutral result from a sandboxed local coding-agent attempt."""

    manifest: dict[str, Any]
    candidate: ArtifactBundleCandidateReference
    process_result: ProcessResult
    workspace_sha: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "manifest": self.manifest,
                "candidate": self.candidate.to_dict(),
                "process_result": json.loads(self.process_result.to_json()),
                "workspace_sha": self.workspace_sha,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalRunnerError(f"{field} must be a non-empty string")
    return value.strip()


def _scope_matches(path: str, pattern: str) -> bool:
    """Match verifier-style globs plus intuitive literal-directory prefixes."""
    if fnmatchcase(path, pattern):
        return True
    if not any(char in pattern for char in "*?["):
        prefix = pattern.rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return False


def _validate_local_agent_admission(
    work_unit: dict[str, Any],
    preset: AgentPreset,
    sandbox: LocalSandboxExecutor,
    limits: SandboxLimits,
) -> str:
    """Validate only execution/admission facts needed at this product boundary."""
    objective = _require_nonempty_string(work_unit.get("objective"), "work_unit.objective")

    permissions = work_unit.get("permissions")
    if not isinstance(permissions, dict):
        raise LocalRunnerError("work_unit.permissions must be an object")
    if permissions.get("process_execution") is not True:
        raise LocalRunnerError("local coding-agent WorkUnit must allow process_execution")
    secrets = permissions.get("secrets")
    if secrets != []:
        raise LocalRunnerError(
            "local coding-agent execution currently requires an empty secrets permission"
        )

    security = work_unit.get("security")
    if not isinstance(security, dict) or security.get("sandbox_required") is not True:
        raise LocalRunnerError(
            "local coding-agent WorkUnit must explicitly require a sandbox"
        )

    constraints = work_unit.get("constraints")
    if not isinstance(constraints, dict):
        raise LocalRunnerError("work_unit.constraints must be an object")
    allowed = constraints.get("allowed_paths")
    forbidden = constraints.get("forbidden_paths")
    if not isinstance(allowed, list) or not allowed:
        raise LocalRunnerError("work_unit.constraints.allowed_paths must be non-empty")
    if not isinstance(forbidden, list):
        raise LocalRunnerError("work_unit.constraints.forbidden_paths must be an array")
    for field, values in (("allowed_paths", allowed), ("forbidden_paths", forbidden)):
        for value in values:
            if (
                not isinstance(value, str)
                or not value
                or "\x00" in value
                or value.startswith("/")
                or ".." in Path(value).parts
            ):
                raise LocalRunnerError(f"unsafe WorkUnit {field} entry: {value!r}")

    budget = work_unit.get("budget")
    if not isinstance(budget, dict):
        raise LocalRunnerError("work_unit.budget must be an object")
    wall_budget = budget.get("wall_seconds")
    if (
        isinstance(wall_budget, bool)
        or not isinstance(wall_budget, (int, float))
        or not math.isfinite(float(wall_budget))
        or wall_budget <= 0
    ):
        raise LocalRunnerError(
            "local coding-agent WorkUnit requires a positive budget.wall_seconds"
        )
    if limits.wall_seconds > float(wall_budget):
        raise LocalRunnerError(
            "sandbox wall limit exceeds WorkUnit budget.wall_seconds"
        )

    resources = work_unit.get("requirements", {}).get("resources")
    if not isinstance(resources, dict):
        raise LocalRunnerError("work_unit.requirements.resources must be an object")
    minimum_memory = resources.get("memory_mb_min", 0)
    minimum_disk = resources.get("disk_mb_min", 0)
    if isinstance(minimum_memory, int) and limits.memory_mb < minimum_memory:
        raise LocalRunnerError("sandbox memory limit is below WorkUnit minimum")
    if isinstance(minimum_disk, int) and limits.disk_mb < minimum_disk:
        raise LocalRunnerError("sandbox disk limit is below WorkUnit minimum")

    caps = getattr(sandbox, "capabilities", None)
    if not isinstance(caps, SandboxCapabilities):
        raise LocalRunnerError("sandbox executor must expose SandboxCapabilities")
    enforcement = {
        "process_tree_isolation": caps.process_tree_isolation,
        "cpu_limit": caps.cpu_limit,
        "memory_limit": caps.memory_limit,
        "disk_limit": caps.disk_limit,
        "process_limit": caps.process_limit,
        "filesystem_isolation": caps.filesystem_isolation,
        "credential_isolation": caps.credential_isolation,
    }
    missing = sorted(name for name, enabled in enforcement.items() if not enabled)
    if missing:
        raise LocalRunnerError(
            "sandbox executor is missing required enforcement: " + ", ".join(missing)
        )

    network = permissions.get("network")
    if network == "none":
        required_network_policy = "disabled"
    elif network == "allowlist":
        allowlist = permissions.get("network_allowlist")
        if not isinstance(allowlist, list) or not allowlist:
            raise LocalRunnerError("network=allowlist requires network_allowlist")
        required_network_policy = preset.network_policy
        if required_network_policy not in {"model_only", "allowlisted"}:
            raise LocalRunnerError(
                "preset network policy cannot satisfy an allowlisted WorkUnit"
            )
    else:
        raise LocalRunnerError(
            "local coding-agent execution does not admit unrestricted network"
        )
    if preset.network_policy != required_network_policy:
        raise LocalRunnerError(
            "preset network policy conflicts with WorkUnit network permission"
        )
    if caps.network_policy != required_network_policy:
        raise LocalRunnerError(
            "sandbox network enforcement does not match admitted preset policy"
        )

    return objective


def _changed_paths(workspace: Path, *, max_bytes: int = 1_000_000) -> list[tuple[str, bool]]:
    result = run_bounded_process(
        (
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--no-renames",
        ),
        cwd=workspace,
        limits=ProcessLimits(
            timeout_seconds=30,
            max_output_bytes=max_bytes,
            max_stdin_bytes=1,
        ),
        env=minimal_environment(()),
    )
    if result.timed_out or result.returncode != 0 or result.stdout_truncated:
        raise LocalRunnerError("unable to enumerate candidate paths within bounds")
    if "\ufffd" in result.stdout:
        raise LocalRunnerError("candidate path is not valid UTF-8")

    rows: list[tuple[str, bool]] = []
    for entry in result.stdout.split("\x00"):
        if not entry:
            continue
        if len(entry) < 4 or entry[2] != " ":
            raise LocalRunnerError(f"unexpected git status entry: {entry!r}")
        status = entry[:2]
        path = entry[3:]
        if not path or path.startswith("/") or ".." in Path(path).parts:
            raise LocalRunnerError(f"unsafe changed path: {path!r}")
        rows.append((path.replace("\\", "/"), status == "??"))
    return rows


def _validate_candidate_scope(
    changed: list[tuple[str, bool]],
    work_unit: dict[str, Any],
) -> None:
    constraints = work_unit["constraints"]
    allowed = list(constraints["allowed_paths"])
    forbidden = list(constraints["forbidden_paths"])
    for path, _ in changed:
        if any(_scope_matches(path, pattern) for pattern in forbidden):
            raise LocalRunnerError(f"candidate modified forbidden path: {path}")
        if not any(_scope_matches(path, pattern) for pattern in allowed):
            raise LocalRunnerError(f"candidate modified path outside allowed scope: {path}")


def _git_patch_fragment(
    workspace: Path,
    argv: tuple[str, ...],
    *,
    max_bytes: int,
) -> str:
    result = run_bounded_process(
        argv,
        cwd=workspace,
        limits=ProcessLimits(
            timeout_seconds=60,
            max_output_bytes=max_bytes,
            max_stdin_bytes=1,
        ),
        env=minimal_environment(()),
    )
    if result.timed_out or result.stdout_truncated:
        raise LocalRunnerError("candidate patch exceeds configured capture bounds")
    if result.returncode not in {0, 1}:
        raise LocalRunnerError(
            "git patch capture failed: " + result.stderr.strip()
        )
    return result.stdout


def _capture_candidate_patch(
    workspace: Path,
    work_unit: dict[str, Any],
    artifact_root: Path,
    *,
    max_bytes: int,
) -> tuple[ArtifactBundleCandidateReference, Path]:
    changed = _changed_paths(workspace)
    if not changed:
        raise LocalRunnerError("local agent produced no candidate changes")
    _validate_candidate_scope(changed, work_unit)

    tracked = [path for path, untracked in changed if not untracked]
    untracked = [path for path, is_untracked in changed if is_untracked]
    fragments: list[str] = []
    retained = 0

    if tracked:
        pathspecs = tuple(f":(literal){path}" for path in tracked)
        fragment = _git_patch_fragment(
            workspace,
            ("git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", *pathspecs),
            max_bytes=max_bytes,
        )
        fragments.append(fragment)
        retained += len(fragment.encode("utf-8"))
    for path in untracked:
        remaining = max_bytes - retained
        if remaining < 1:
            raise LocalRunnerError("candidate patch exceeds configured capture bounds")
        fragment = _git_patch_fragment(
            workspace,
            (
                "git",
                "diff",
                "--no-index",
                "--binary",
                "--no-ext-diff",
                "--",
                os.devnull,
                path,
            ),
            max_bytes=remaining,
        )
        fragments.append(fragment)
        retained += len(fragment.encode("utf-8"))
        if retained > max_bytes:
            raise LocalRunnerError("candidate patch exceeds configured capture bounds")

    patch_text = "".join(fragments)
    patch_bytes = patch_text.encode("utf-8")
    if not patch_bytes or len(patch_bytes) > max_bytes:
        raise LocalRunnerError("candidate patch is empty or exceeds configured bounds")

    artifact_root.mkdir(parents=True, exist_ok=True)
    digest = "sha256:" + hashlib.sha256(patch_bytes).hexdigest()
    path = artifact_root / f"candidate-{digest[7:19]}.patch"
    path.write_bytes(patch_bytes)
    resolution = LocalArtifactBundleReader(
        artifact_root,
        max_bytes=max_bytes,
    ).resolve(
        relative_path=path.name,
        expected_digest=digest,
        media_type="text/x-diff",
    )
    return resolution.reference, path


def _write_log_reference(
    artifact_root: Path,
    *,
    log_type: str,
    text: str,
    max_bytes: int,
) -> LogReference | None:
    if not text:
        return None
    data = text.encode("utf-8")
    if len(data) > max_bytes:
        raise LocalRunnerError(f"{log_type} exceeds retained output bound")
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    path = artifact_root / f"{log_type}-{digest[7:19]}.log"
    path.write_bytes(data)
    resolution = LocalArtifactBundleReader(
        artifact_root,
        max_bytes=max_bytes,
    ).resolve(
        relative_path=path.name,
        expected_digest=digest,
        media_type="text/plain",
    )
    return LogReference(
        type=log_type,
        locator=resolution.reference.locator,
        digest=digest,
    )


def run_local_agent_preset(
    preset: AgentPreset | str,
    work_unit: dict[str, Any],
    *,
    source_revision: str,
    sandbox: LocalSandboxExecutor,
    limits: SandboxLimits,
    artifact_dir: str | Path,
    repository: str | Path = ".",
    extra_env: Mapping[str, str] | None = None,
    manifest_id: str | None = None,
    attempt: int = 1,
) -> LocalAgentRunResult:
    """Run one preset only through an explicitly conforming sandbox executor."""
    if isinstance(preset, str):
        try:
            active_preset = get_builtin_preset(preset)
        except KeyError as exc:
            raise LocalRunnerError(str(exc)) from exc
    elif isinstance(preset, AgentPreset):
        active_preset = preset
    else:
        raise LocalRunnerError(
            "preset must be an AgentPreset instance or valid preset identifier"
        )

    binding = bind_work_unit_source(work_unit, source_revision=source_revision)
    objective = _validate_local_agent_admission(
        work_unit,
        active_preset,
        sandbox,
        limits,
    )

    # File transport needs a sandbox-owned ephemeral input mount so task text can
    # never appear in the candidate diff. No production executor supplies that
    # contract yet, so fail closed instead of writing a prompt into the worktree.
    if active_preset.prompt_transport == "file":
        raise LocalRunnerError(
            "file prompt transport requires an isolated sandbox input mount"
        )

    prefix = active_preset.invocation_prefix()
    if active_preset.prompt_transport == "stdin":
        argv = prefix
        stdin_text = objective
    elif active_preset.prompt_transport == "argument":
        argv = (*prefix, active_preset.prompt_arg, objective)
        stdin_text = None
    else:
        raise LocalRunnerError(
            f"unsupported prompt transport: {active_preset.prompt_transport}"
        )

    # Host environment inheritance is never implicit on the coding-agent path.
    explicit_env = {} if extra_env is None else extra_env
    active_env = minimal_environment(active_preset.env_allowlist, source=explicit_env)
    if any("docker.sock" in value.casefold() for value in active_env.values()):
        raise LocalRunnerError("Docker socket authority is forbidden")

    repo_path = Path(repository).resolve()
    artifact_root = Path(artifact_dir).resolve()
    try:
        artifact_root.relative_to(repo_path)
    except ValueError:
        pass
    else:
        raise LocalRunnerError(
            "artifact_dir must be outside the canonical repository"
        )

    with DisposableGitWorkspace(repo_path, binding.source_revision) as workspace:
        if workspace.path is None:
            raise LocalRunnerError("disposable workspace path is unavailable")
        try:
            artifact_root.relative_to(workspace.path)
        except ValueError:
            pass
        else:
            raise LocalRunnerError("artifact_dir must be outside worker workspace")

        started_at = datetime.now(timezone.utc)
        process_result = sandbox.run(
            argv,
            cwd=workspace.path,
            limits=limits,
            env=active_env,
            stdin_text=stdin_text,
        )
        finished_at = datetime.now(timezone.utc)
        if not isinstance(process_result, ProcessResult):
            raise LocalRunnerError("sandbox executor returned an invalid ProcessResult")

        candidate, _ = _capture_candidate_patch(
            workspace.path,
            work_unit,
            artifact_root,
            max_bytes=limits.max_candidate_bytes,
        )

        log_refs: list[LogReference] = []
        for log_type, value in (
            ("stdout", process_result.stdout),
            ("stderr", process_result.stderr),
        ):
            reference = _write_log_reference(
                artifact_root,
                log_type=log_type,
                text=value,
                max_bytes=limits.max_output_bytes,
            )
            if reference is not None:
                log_refs.append(reference)

        if process_result.timed_out:
            status = "timeout"
        elif process_result.returncode == 0:
            status = "succeeded"
        else:
            status = "failed"

        active_manifest_id = (
            manifest_id or f"manifest-{binding.work_unit_id}-attempt-{attempt}"
        )
        manifest = build_result_manifest(
            work_unit=work_unit,
            binding=binding,
            candidate=candidate,
            manifest_id=active_manifest_id,
            attempt=attempt,
            worker=WorkerIdentity(
                id=active_preset.preset_id,
                type="agent",
                adapter=active_preset.agent_family,
            ),
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            resources=ResourceUsage(wall_seconds=process_result.duration_seconds),
            self_report=SelfReport(
                summary=(
                    f"Sandboxed local agent preset {active_preset.preset_id} "
                    "returned a candidate; no verification authority is implied."
                ),
                claims=(),
            ),
            self_report_source="normalizer",
            logs=tuple(log_refs),
            environment=ExecutionEnvironment(
                platform=os.name,
                tool_versions=None,
            ),
        )

        return LocalAgentRunResult(
            manifest=manifest,
            candidate=candidate,
            process_result=process_result,
            workspace_sha=workspace.source_sha,
        )
