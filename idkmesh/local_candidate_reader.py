"""Resolve bounded local artifact bundles into immutable CandidateReference objects.

The reader owns filesystem confinement and content addressing for one regular
file inside a configured workspace root. It emits identity/provenance only and
never marks a candidate verified, accepted, or integration-ready.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any

from idkmesh.candidate_reference import ArtifactBundleCandidateReference


_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CHUNK_BYTES = 1024 * 1024


class LocalArtifactResolutionError(RuntimeError):
    """Raised when a local candidate cannot be safely content-addressed."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.details = dict(details or {})


@dataclass(frozen=True)
class LocalArtifactBundleResolution:
    """Content-addressed local candidate metadata without acceptance authority."""

    reference: ArtifactBundleCandidateReference
    size_bytes: int


def _relative_path(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("relative_path must be a non-empty string")
    path = Path(value)
    if path.is_absolute():
        raise ValueError("relative_path must not be absolute")
    if ".." in path.parts:
        raise ValueError("relative_path must not contain parent traversal")
    if path == Path("."):
        raise ValueError("relative_path must identify a file")
    return path


def _expected_digest(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(
            "expected_digest must be a lowercase sha256 content digest"
        )
    return value


class LocalArtifactBundleReader:
    """Hash one regular file inside a bounded workspace into CandidateReference."""

    def __init__(self, workspace_root: str | Path, *, max_bytes: int) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be an integer >= 1")

        root = Path(workspace_root)
        try:
            resolved_root = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("workspace_root must exist") from exc
        if not resolved_root.is_dir():
            raise ValueError("workspace_root must be a directory")

        self._root = resolved_root
        self._max_bytes = max_bytes

    def resolve(
        self,
        *,
        relative_path: str,
        expected_digest: str | None = None,
        media_type: str | None = None,
    ) -> LocalArtifactBundleResolution:
        relative = _relative_path(relative_path)
        expected = _expected_digest(expected_digest)

        unresolved = self._root / relative

        # Reject symlink aliases in every path component below the trusted root.
        cursor = self._root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise LocalArtifactResolutionError(
                    "local candidate path must not traverse symlinks",
                    field="relative_path",
                )

        try:
            resolved = unresolved.resolve(strict=True)
        except OSError as exc:
            raise LocalArtifactResolutionError(
                "local candidate file does not exist",
                field="relative_path",
            ) from exc

        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise LocalArtifactResolutionError(
                "local candidate escapes the configured workspace root",
                field="relative_path",
            ) from exc

        if not resolved.is_file():
            raise LocalArtifactResolutionError(
                "local candidate must be a regular file",
                field="relative_path",
            )

        digest = hashlib.sha256()
        size_bytes = 0

        try:
            with resolved.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise LocalArtifactResolutionError(
                        "local candidate must be a regular file",
                        field="relative_path",
                    )
                if before.st_size > self._max_bytes:
                    raise LocalArtifactResolutionError(
                        "local candidate exceeds configured size limit",
                        field="relative_path",
                        details={
                            "size_bytes": before.st_size,
                            "max_bytes": self._max_bytes,
                        },
                    )

                while True:
                    chunk = handle.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > self._max_bytes:
                        raise LocalArtifactResolutionError(
                            "local candidate exceeded configured size limit while reading",
                            field="relative_path",
                            details={"max_bytes": self._max_bytes},
                        )
                    digest.update(chunk)

                after = os.fstat(handle.fileno())
        except LocalArtifactResolutionError:
            raise
        except OSError as exc:
            raise LocalArtifactResolutionError(
                "local candidate could not be read",
                field="relative_path",
            ) from exc

        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_identity != after_identity or size_bytes != after.st_size:
            raise LocalArtifactResolutionError(
                "local candidate changed while being content-addressed",
                field="relative_path",
            )

        try:
            path_after = resolved.stat()
        except OSError as exc:
            raise LocalArtifactResolutionError(
                "local candidate disappeared after content addressing",
                field="relative_path",
            ) from exc
        path_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
        )
        if path_identity != after_identity:
            raise LocalArtifactResolutionError(
                "local candidate path changed during content addressing",
                field="relative_path",
            )

        content_digest = "sha256:" + digest.hexdigest()
        if expected is not None and expected != content_digest:
            raise LocalArtifactResolutionError(
                "local candidate digest does not match the expected digest",
                field="expected_digest",
                details={
                    "expected_digest": expected,
                    "observed_digest": content_digest,
                },
            )

        try:
            reference = ArtifactBundleCandidateReference(
                locator=resolved.as_uri(),
                digest=content_digest,
                media_type=media_type,
            )
        except ValueError as exc:
            raise LocalArtifactResolutionError(
                "local candidate metadata is invalid",
                field="media_type",
            ) from exc

        return LocalArtifactBundleResolution(
            reference=reference,
            size_bytes=size_bytes,
        )
