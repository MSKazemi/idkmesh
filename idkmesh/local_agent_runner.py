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
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Iterable, Mapping


class LocalRunnerError(RuntimeError):
    """Fail-closed local-runner setup or execution error."""


@dataclass(frozen=True)
class ProcessLimits:
    timeout_seconds: float = 300.0
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")


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
        if name == "PATH":
            continue
        if name in source_env:
            result[name] = source_env[name]
    return result


def _bounded_text(data: bytes | str | None, limit: int) -> tuple[str, bool]:
    if data is None:
        return "", False
    raw = data.encode("utf-8", errors="replace") if isinstance(data, str) else data
    truncated = len(raw) > limit
    bounded = raw[:limit]
    return bounded.decode("utf-8", errors="replace"), truncated


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
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workdir,
            env=active_env,
            input=None if stdin_text is None else stdin_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=active_limits.timeout_seconds,
            shell=False,
        )
        duration = time.monotonic() - started
        stdout, stdout_truncated = _bounded_text(
            completed.stdout, active_limits.max_output_bytes
        )
        stderr, stderr_truncated = _bounded_text(
            completed.stderr, active_limits.max_output_bytes
        )
        return ProcessResult(
            argv=command,
            returncode=completed.returncode,
            timed_out=False,
            duration_seconds=round(duration, 6),
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        stdout, stdout_truncated = _bounded_text(
            exc.stdout, active_limits.max_output_bytes
        )
        stderr, stderr_truncated = _bounded_text(
            exc.stderr, active_limits.max_output_bytes
        )
        return ProcessResult(
            argv=command,
            returncode=None,
            timed_out=True,
            duration_seconds=round(duration, 6),
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
