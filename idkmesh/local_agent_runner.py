"""Bounded local-runner primitives for disposable candidate execution.

This module deliberately does not know goose, Gemini CLI, mini-SWE-agent, or
any model provider. It materializes an exact Git revision into a disposable
workspace and can run one argv-only process with a minimal environment,
wall-time limit, and bounded captured output.

Network namespace/resource isolation is a later C4-D slice; callers must not
treat this process boundary alone as a hostile-code sandbox.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Iterable, Mapping

from idkmesh.agent_presets import (
    FORBIDDEN_ENV_NAMES,
    _SECRET_ENV_SUFFIXES,
    AgentPreset,
    get_builtin_preset,
)
from idkmesh.candidate_reference import ArtifactBundleCandidateReference
from idkmesh.local_candidate_reader import LocalArtifactBundleReader
from idkmesh.result_manifest_builder import (
    ExecutionEnvironment,
    LogReference,
    ModelIdentity,
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


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
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
        _terminate_process(process)
        process.wait()
    for reader in readers:
        reader.join()

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
class LocalAgentRunResult:
    """Normalized output from executing one local coding-agent preset."""

    manifest: dict[str, Any]
    candidate: ArtifactBundleCandidateReference
    process_result: ProcessResult
    workspace_sha: str
    patch_text: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "manifest": self.manifest,
                "candidate": self.candidate.to_dict(),
                "process_result": json.loads(self.process_result.to_json()),
                "workspace_sha": self.workspace_sha,
                "patch_text": self.patch_text,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def run_local_agent_preset(
    preset: AgentPreset | str,
    work_unit: dict[str, Any],
    *,
    source_revision: str,
    repository: str | Path = ".",
    limits: ProcessLimits | None = None,
    extra_env: Mapping[str, str] | None = None,
    manifest_id: str | None = None,
    attempt: int = 1,
    artifact_dir: str | Path | None = None,
) -> LocalAgentRunResult:
    """Run one local coding-agent preset in a bounded disposable workspace."""
    if isinstance(preset, str):
        active_preset = get_builtin_preset(preset)
    elif isinstance(preset, AgentPreset):
        active_preset = preset
    else:
        raise LocalRunnerError(
            "preset must be an AgentPreset instance or valid preset identifier"
        )

    binding = bind_work_unit_source(work_unit, source_revision=source_revision)

    prompt = ""
    if isinstance(work_unit, dict):
        for field in ("prompt", "description", "goal", "title"):
            val = work_unit.get(field)
            if isinstance(val, str) and val.strip():
                prompt = val.strip()
                break

    repo_path = Path(repository).resolve()
    with DisposableGitWorkspace(repo_path, binding.source_revision) as workspace:
        if workspace.path is None:
            raise LocalRunnerError("disposable workspace path is unavailable")

        prefix = active_preset.invocation_prefix()
        stdin_text = None

        if active_preset.prompt_transport == "stdin":
            argv = prefix
            stdin_text = prompt
        elif active_preset.prompt_transport == "argument":
            arg = active_preset.prompt_arg
            argv = (*prefix, arg, prompt) if arg else (*prefix, prompt)
        elif active_preset.prompt_transport == "file":
            prompt_file = workspace.path / ".idkmesh_prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            if active_preset.prompt_arg:
                argv = (*prefix, active_preset.prompt_arg, str(prompt_file))
            else:
                argv = (*prefix, str(prompt_file))
        else:
            raise LocalRunnerError(
                f"unsupported prompt_transport: {active_preset.prompt_transport}"
            )

        active_env = minimal_environment(
            active_preset.env_allowlist, source=extra_env
        )

        for env_key, env_val in active_env.items():
            if env_key in FORBIDDEN_ENV_NAMES or any(
                env_key.endswith(suffix) for suffix in _SECRET_ENV_SUFFIXES
            ):
                raise LocalRunnerError(
                    f"forbidden host credential environment variable exposed in preset env: {env_key}"
                )
            if env_key == "DOCKER_HOST" or "docker.sock" in env_val.casefold():
                raise LocalRunnerError(
                    "Docker socket mount or authority is forbidden in local candidate runner"
                )

        active_limits = limits or ProcessLimits()
        started_at = datetime.now(timezone.utc)
        proc_result = run_bounded_process(
            argv,
            cwd=workspace.path,
            limits=active_limits,
            env=active_env,
            stdin_text=stdin_text,
        )
        finished_at = datetime.now(timezone.utc)

        _run_git(workspace.path, "add", "-N", ".")
        patch_text = _run_git(workspace.path, "diff", "HEAD")
        patch_bytes = patch_text.encode("utf-8")
        patch_digest = "sha256:" + hashlib.sha256(patch_bytes).hexdigest()

        if artifact_dir is not None:
            target_dir = Path(artifact_dir).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            patch_file = target_dir / f"patch_{patch_digest[7:19]}.diff"
            patch_file.write_bytes(patch_bytes)
            reader = LocalArtifactBundleReader(target_dir, max_bytes=10 * 1024 * 1024)
            resolution = reader.resolve(
                relative_path=patch_file.name,
                expected_digest=patch_digest,
                media_type="text/x-diff",
            )
            candidate_ref = resolution.reference
        else:
            candidate_ref = ArtifactBundleCandidateReference(
                locator=f"artifact:bundle:patch:{patch_digest[7:19]}",
                digest=patch_digest,
                media_type="text/x-diff",
            )

        if proc_result.timed_out:
            status = "timeout"
        elif proc_result.returncode == 0:
            status = "succeeded"
        else:
            status = "failed"

        log_refs = []
        if proc_result.stdout:
            stdout_digest = (
                "sha256:"
                + hashlib.sha256(proc_result.stdout.encode("utf-8")).hexdigest()
            )
            log_refs.append(
                LogReference(
                    type="stdout", locator="inline:stdout", digest=stdout_digest
                )
            )
        if proc_result.stderr:
            stderr_digest = (
                "sha256:"
                + hashlib.sha256(proc_result.stderr.encode("utf-8")).hexdigest()
            )
            log_refs.append(
                LogReference(
                    type="stderr", locator="inline:stderr", digest=stderr_digest
                )
            )

        active_manifest_id = (
            manifest_id or f"manifest-{binding.work_unit_id}-attempt-{attempt}"
        )

        worker_id = WorkerIdentity(
            id=active_preset.preset_id,
            type="agent",
            adapter=active_preset.agent_family,
            adapter_version="0.1",
            model=ModelIdentity(name=active_preset.model_connection_ref),
        )

        resources = ResourceUsage(wall_seconds=proc_result.duration_seconds)

        self_report = SelfReport(
            summary=f"Local agent preset {active_preset.preset_id} execution completed.",
            claims=(),
        )

        execution_env = ExecutionEnvironment(
            platform=sys.platform,
            python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            tool_versions={active_preset.executable: "0.1"},
        )

        manifest = build_result_manifest(
            work_unit=work_unit,
            binding=binding,
            candidate=candidate_ref,
            manifest_id=active_manifest_id,
            attempt=attempt,
            worker=worker_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            resources=resources,
            self_report=self_report,
            self_report_source="normalizer",
            logs=tuple(log_refs),
            environment=execution_env,
        )

        return LocalAgentRunResult(
            manifest=manifest,
            candidate=candidate_ref,
            process_result=proc_result,
            workspace_sha=workspace.source_sha,
            patch_text=patch_text,
        )
