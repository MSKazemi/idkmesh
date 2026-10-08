"""Canonical immutable GitHub evidence links for C14-C.

A GitHub-hosted URL is not automatically durable evidence. Branch and tag
references can move, Actions artifacts expire, and query/fragment variants are
poor provenance identities. This module defines the narrow Git-backed evidence
link form IDKMesh may call durable in GitHub-native presentation surfaces.

The helper is pure and dependency-free. It does not fetch GitHub, verify file
contents, write repository state, or grant any execution/integration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote, unquote, urlsplit


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_MAX_PATH_LENGTH = 2048
_MAX_URL_LENGTH = 4096


class DurableGitHubEvidenceLinkError(ValueError):
    """The supplied evidence reference is not immutable/canonical."""


def _repository(value: object) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise DurableGitHubEvidenceLinkError(
            "repository must be in owner/name form"
        )
    return value


def _commit_sha(value: object) -> str:
    if not isinstance(value, str):
        raise DurableGitHubEvidenceLinkError(
            "commit_sha must be a 40- or 64-hex Git revision"
        )
    normalized = value.lower()
    if _COMMIT_RE.fullmatch(normalized) is None:
        raise DurableGitHubEvidenceLinkError(
            "commit_sha must be a 40- or 64-hex Git revision"
        )
    return normalized


def _path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise DurableGitHubEvidenceLinkError(
            "path must be a non-empty repository-relative file path"
        )
    if len(value) > _MAX_PATH_LENGTH:
        raise DurableGitHubEvidenceLinkError("path exceeds maximum length")
    if value.startswith("/") or value.endswith("/"):
        raise DurableGitHubEvidenceLinkError(
            "path must identify a repository-relative file"
        )
    if "\\" in value:
        raise DurableGitHubEvidenceLinkError(
            "path must use POSIX '/' separators"
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise DurableGitHubEvidenceLinkError(
            "path contains unsupported control characters"
        )
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DurableGitHubEvidenceLinkError(
            "path must not contain empty, '.' or '..' segments"
        )
    return value


@dataclass(frozen=True, slots=True)
class DurableGitHubEvidenceReference:
    """One immutable evidence file located by repository + exact commit + path."""

    repository: str
    commit_sha: str
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "repository", _repository(self.repository))
        object.__setattr__(self, "commit_sha", _commit_sha(self.commit_sha))
        object.__setattr__(self, "path", _path(self.path))

    @property
    def encoded_path(self) -> str:
        return quote(self.path, safe="/-._~")

    @property
    def html_url(self) -> str:
        return (
            f"https://github.com/{self.repository}/blob/"
            f"{self.commit_sha}/{self.encoded_path}"
        )

    @property
    def raw_url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.repository}/"
            f"{self.commit_sha}/{self.encoded_path}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "commit_sha": self.commit_sha,
            "path": self.path,
            "html_url": self.html_url,
            "raw_url": self.raw_url,
            "retention_identity": "git-commit-pinned-file",
            "actions_artifact": False,
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        }


def parse_durable_github_evidence_url(
    value: object,
    *,
    expected_repository: str | None = None,
) -> DurableGitHubEvidenceReference:
    """Parse only canonical commit-pinned GitHub blob/raw evidence URLs."""

    if not isinstance(value, str) or not value:
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL must be a non-empty string"
        )
    if len(value) > _MAX_URL_LENGTH:
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL exceeds maximum length"
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL contains control characters"
        )

    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL must be plain HTTPS without credentials, "
            "port, query, or fragment"
        )

    segments = parsed.path.split("/")
    host = (parsed.hostname or "").lower()
    form: str
    if host == "github.com":
        if (
            len(segments) < 7
            or segments[0] != ""
            or segments[3] != "blob"
        ):
            raise DurableGitHubEvidenceLinkError(
                "GitHub durable evidence URL must use "
                "/OWNER/REPO/blob/<commit>/<path>"
            )
        owner, repo, commit = segments[1], segments[2], segments[4]
        encoded_path = "/".join(segments[5:])
        form = "html"
    elif host == "raw.githubusercontent.com":
        if len(segments) < 6 or segments[0] != "":
            raise DurableGitHubEvidenceLinkError(
                "raw GitHub durable evidence URL must use "
                "/OWNER/REPO/<commit>/<path>"
            )
        owner, repo, commit = segments[1], segments[2], segments[3]
        encoded_path = "/".join(segments[4:])
        form = "raw"
    else:
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL must use github.com or raw.githubusercontent.com"
        )

    try:
        decoded_path = unquote(encoded_path, errors="strict")
    except UnicodeError as exc:
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL path is not valid UTF-8"
        ) from exc

    reference = DurableGitHubEvidenceReference(
        repository=f"{owner}/{repo}",
        commit_sha=commit,
        path=decoded_path,
    )

    canonical = reference.html_url if form == "html" else reference.raw_url
    if canonical != value:
        raise DurableGitHubEvidenceLinkError(
            "durable evidence URL must use the canonical commit-pinned encoding"
        )

    if expected_repository is not None:
        expected = _repository(expected_repository)
        if reference.repository.casefold() != expected.casefold():
            raise DurableGitHubEvidenceLinkError(
                "durable evidence URL repository does not match the configured repository"
            )

    return reference


def validate_durable_github_evidence_url(
    value: object,
    *,
    expected_repository: str | None = None,
) -> str:
    """Return a canonical immutable URL or raise a fail-closed contract error."""

    reference = parse_durable_github_evidence_url(
        value,
        expected_repository=expected_repository,
    )
    if isinstance(value, str) and value == reference.raw_url:
        return reference.raw_url
    return reference.html_url
