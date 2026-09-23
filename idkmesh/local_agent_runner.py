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
from typing import Iterable, Mapping


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
