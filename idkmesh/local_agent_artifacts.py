"""Controller-owned local-agent candidate artifact capture.

C4-E captures a finished disposable worktree into one bounded content-addressed
artifact bundle. The worker never chooses the bundle destination or digest.

The bundle contains:
- a binary-capable Git diff against the exact source SHA;
- bounded process stdout/stderr;
- bounded regular untracked files;
- optional controller-selected regular artifact files;
- a small JSON manifest.

The resulting ZIP is resolved immediately through LocalArtifactBundleReader and
therefore enters C6 as an immutable ArtifactBundleCandidateReference.

Symlinks, path traversal, worktree repository rebinding, oversized data, and
truncated Git capture fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Iterable
import zipfile

from idkmesh.local_agent_runner import (
    LocalRunnerError,
    ProcessLimits,
    ProcessResult,
    resolve_exact_revision,
    run_bounded_process,
)
from idkmesh.local_candidate_reader import (
    LocalArtifactBundleReader,
    LocalArtifactBundleResolution,
)


_BUNDLE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.zip\Z")
_MEDIA_TYPE = "application/vnd.idkmesh.local-agent-candidate+zip"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class ArtifactCaptureLimits:
    max_patch_bytes: int = 4 * 1024 * 1024
    max_listing_bytes: int = 512 * 1024
    max_file_bytes: int = 4 * 1024 * 1024
    max_bundle_bytes: int = 16 * 1024 * 1024
    max_untracked_files: int = 256
    git_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        for name in (
            "max_patch_bytes",
            "max_listing_bytes",
            "max_file_bytes",
            "max_bundle_bytes",
            "max_untracked_files",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1")
        if (
            isinstance(self.git_timeout_seconds, bool)
            or not isinstance(self.git_timeout_seconds, (int, float))
            or self.git_timeout_seconds <= 0
        ):
            raise ValueError("git_timeout_seconds must be > 0")


@dataclass(frozen=True)
class LocalAgentArtifactCapture:
    source_sha: str
    bundle: LocalArtifactBundleResolution
    patch_bytes: int
    untracked_files: int
    included_artifacts: tuple[str, ...]
    stdout_bytes: int
    stderr_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha": self.source_sha,
            "bundle": self.bundle.reference.to_dict(),
            "bundle_size_bytes": self.bundle.size_bytes,
            "patch_bytes": self.patch_bytes,
            "untracked_files": self.untracked_files,
            "included_artifacts": list(self.included_artifacts),
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
        }


def _git_common_dir(path: Path) -> Path:
    result = run_bounded_process(
        ("git", "rev-parse", "--path-format=absolute", "--git-common-dir"),
        cwd=path,
        limits=ProcessLimits(
            timeout_seconds=10,
            max_output_bytes=64 * 1024,
            max_stdin_bytes=1,
        ),
        env={"PATH": os.environ.get("PATH", os.defpath)},
    )
    if result.timed_out or result.returncode != 0 or result.stdout_truncated:
        raise LocalRunnerError("could not resolve Git common directory")
    value = result.stdout.strip()
    if not value:
        raise LocalRunnerError("Git common directory is empty")
    return Path(value).resolve()


def _validate_worktree_binding(
    workspace: Path,
    repository: Path,
    source_revision: str,
) -> str:
    if not workspace.is_dir():
        raise LocalRunnerError("workspace must be an existing directory")
    if not repository.is_dir():
        raise LocalRunnerError("repository must be an existing directory")

    expected_common = _git_common_dir(repository)
    observed_common = _git_common_dir(workspace)
    if observed_common != expected_common:
        raise LocalRunnerError(
            "workspace Git metadata no longer points at the expected repository"
        )

    source_sha = resolve_exact_revision(repository, source_revision)
    observed_source = resolve_exact_revision(workspace, source_sha)
    if observed_source.lower() != source_sha.lower():
        raise LocalRunnerError("workspace cannot resolve the exact source SHA")
    return source_sha.lower()


def _git_capture(
    workspace: Path,
    argv: tuple[str, ...],
    *,
    timeout_seconds: float,
    max_bytes: int,
) -> bytes:
    result = run_bounded_process(
        argv,
        cwd=workspace,
        limits=ProcessLimits(
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_bytes,
            max_stdin_bytes=1,
        ),
        env={"PATH": os.environ.get("PATH", os.defpath)},
    )
    if result.timed_out:
        raise LocalRunnerError("Git artifact capture timed out")
    if result.returncode != 0:
        raise LocalRunnerError("Git artifact capture failed")
    if result.stdout_truncated:
        raise LocalRunnerError("Git artifact capture exceeded configured byte limit")
    return result.stdout.encode("utf-8")


def _relative_regular_path(root: Path, relative: str) -> tuple[Path, Path]:
    if not isinstance(relative, str) or not relative:
        raise LocalRunnerError("artifact path must be a non-empty string")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise LocalRunnerError("artifact path must stay relative to the workspace")

    cursor = root
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise LocalRunnerError("artifact path must not traverse symlinks")

    try:
        resolved = (root / path).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LocalRunnerError("artifact path must resolve inside the workspace") from exc
    if not resolved.is_file():
        raise LocalRunnerError("artifact path must identify a regular file")
    return path, resolved


def _read_stable_regular_file(path: Path, *, max_bytes: int) -> bytes:
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise LocalRunnerError("candidate artifact must be a regular file")
            if before.st_size > max_bytes:
                raise LocalRunnerError("candidate artifact exceeds max_file_bytes")
            data = handle.read(max_bytes + 1)
            after = os.fstat(handle.fileno())
    except LocalRunnerError:
        raise
    except OSError as exc:
        raise LocalRunnerError("candidate artifact could not be read") from exc

    if len(data) > max_bytes:
        raise LocalRunnerError("candidate artifact exceeds max_file_bytes")
    before_id = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_id = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_id != after_id or len(data) != after.st_size:
        raise LocalRunnerError("candidate artifact changed while being read")
    return data


def _untracked_paths(
    workspace: Path,
    *,
    limits: ArtifactCaptureLimits,
) -> tuple[str, ...]:
    raw = _git_capture(
        workspace,
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
        timeout_seconds=limits.git_timeout_seconds,
        max_bytes=limits.max_listing_bytes,
    )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LocalRunnerError(
            "untracked candidate paths must be valid UTF-8"
        ) from exc
    paths = tuple(item for item in text.split("\x00") if item)
    if len(paths) > limits.max_untracked_files:
        raise LocalRunnerError("too many untracked candidate files")
    return tuple(sorted(paths))


def _zip_write_bytes(
    archive: zipfile.ZipFile,
    name: str,
    data: bytes,
) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def capture_local_agent_artifacts(
    *,
    workspace: str | Path,
    repository: str | Path,
    source_revision: str,
    output_root: str | Path,
    process_result: ProcessResult,
    include_paths: Iterable[str] = (),
    bundle_name: str = "candidate-bundle.zip",
    limits: ArtifactCaptureLimits | None = None,
) -> LocalAgentArtifactCapture:
    """Capture one worker attempt into a C6-compatible immutable bundle."""

    if not isinstance(process_result, ProcessResult):
        raise ValueError("process_result must be ProcessResult")
    if not isinstance(bundle_name, str) or _BUNDLE_NAME_RE.fullmatch(bundle_name) is None:
        raise ValueError("bundle_name must be one safe .zip filename")

    active_limits = limits or ArtifactCaptureLimits()
    workspace_path = Path(workspace).resolve()
    repository_path = Path(repository).resolve()
    output_path = Path(output_root).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        output_path.relative_to(workspace_path)
    except ValueError:
        pass
    else:
        raise LocalRunnerError(
            "artifact output root must be outside the worker workspace"
        )

    source_sha = _validate_worktree_binding(
        workspace_path,
        repository_path,
        source_revision,
    )

    patch = _git_capture(
        workspace_path,
        (
            "git",
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-color",
            source_sha,
            "--",
            ".",
        ),
        timeout_seconds=active_limits.git_timeout_seconds,
        max_bytes=active_limits.max_patch_bytes,
    )

    untracked = _untracked_paths(workspace_path, limits=active_limits)
    selected = tuple(sorted(set(include_paths)))

    entries: list[tuple[str, bytes]] = []
    for relative in untracked:
        rel, resolved = _relative_regular_path(workspace_path, relative)
        data = _read_stable_regular_file(
            resolved,
            max_bytes=active_limits.max_file_bytes,
        )
        entries.append((f"workspace/untracked/{rel.as_posix()}", data))

    included_names: list[str] = []
    for relative in selected:
        rel, resolved = _relative_regular_path(workspace_path, relative)
        data = _read_stable_regular_file(
            resolved,
            max_bytes=active_limits.max_file_bytes,
        )
        entries.append((f"artifacts/{rel.as_posix()}", data))
        included_names.append(rel.as_posix())

    stdout_bytes = process_result.stdout.encode("utf-8")
    stderr_bytes = process_result.stderr.encode("utf-8")
    if (
        len(stdout_bytes) > active_limits.max_file_bytes
        or len(stderr_bytes) > active_limits.max_file_bytes
    ):
        raise LocalRunnerError("captured process log exceeds max_file_bytes")

    manifest = {
        "schema": "idkmesh.local-agent-candidate/v1",
        "source_sha": source_sha,
        "process": {
            "returncode": process_result.returncode,
            "timed_out": process_result.timed_out,
            "stdout_truncated": process_result.stdout_truncated,
            "stderr_truncated": process_result.stderr_truncated,
        },
        "untracked_files": list(untracked),
        "included_artifacts": included_names,
    }
    manifest_bytes = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    final_path = output_path / bundle_name
    fd, temp_name = tempfile.mkstemp(
        prefix=".idkmesh-candidate-",
        suffix=".zip.tmp",
        dir=output_path,
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_STORED) as archive:
            _zip_write_bytes(archive, "manifest.json", manifest_bytes)
            _zip_write_bytes(archive, "candidate.patch", patch)
            _zip_write_bytes(archive, "logs/stdout.txt", stdout_bytes)
            _zip_write_bytes(archive, "logs/stderr.txt", stderr_bytes)
            for name, data in sorted(entries):
                _zip_write_bytes(archive, name, data)

        if temp_path.stat().st_size > active_limits.max_bundle_bytes:
            raise LocalRunnerError("candidate bundle exceeds max_bundle_bytes")
        os.replace(temp_path, final_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    resolution = LocalArtifactBundleReader(
        output_path,
        max_bytes=active_limits.max_bundle_bytes,
    ).resolve(
        relative_path=bundle_name,
        media_type=_MEDIA_TYPE,
    )
    return LocalAgentArtifactCapture(
        source_sha=source_sha,
        bundle=resolution,
        patch_bytes=len(patch),
        untracked_files=len(untracked),
        included_artifacts=tuple(included_names),
        stdout_bytes=len(stdout_bytes),
        stderr_bytes=len(stderr_bytes),
    )
