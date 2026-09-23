"""Provider-neutral immutable candidate references.

CandidateReference v0.1 identifies an already discovered candidate precisely
enough for downstream normalization and verification. It deliberately carries
no acceptance, verification, merge, or provider-completion authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, TypeAlias


_SCHEMA_VERSION = "0.1"
_REPOSITORY_RE = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z"
)
_GIT_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _strict_keys(
    raw: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    keys = set(raw)
    missing = required - keys
    if missing:
        raise ValueError(
            "candidate reference is missing required field(s): "
            + ", ".join(sorted(missing))
        )
    unexpected = keys - required - optional
    if unexpected:
        raise ValueError(
            "candidate reference contains unexpected field(s): "
            + ", ".join(sorted(unexpected))
        )


@dataclass(frozen=True)
class GitHubPullRequestCandidateReference:
    """Immutable identity for one GitHub pull-request candidate."""

    repository: str
    number: int
    head_sha: str
    schema_version: str = _SCHEMA_VERSION
    type: str = "github_pull_request"

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("unsupported candidate reference schema_version")
        if self.type != "github_pull_request":
            raise ValueError("type must be github_pull_request")
        repository = _nonempty(self.repository, "repository")
        if _REPOSITORY_RE.fullmatch(repository) is None:
            raise ValueError("repository must be in owner/name form")
        if (
            isinstance(self.number, bool)
            or not isinstance(self.number, int)
            or self.number < 1
        ):
            raise ValueError("number must be an integer >= 1")
        head_sha = _nonempty(self.head_sha, "head_sha")
        if _GIT_REVISION_RE.fullmatch(head_sha) is None:
            raise ValueError(
                "head_sha must be a 40- or 64-character hexadecimal Git object id"
            )
        object.__setattr__(self, "repository", repository)
        object.__setattr__(self, "head_sha", head_sha.lower())

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.repository}/pull/{self.number}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "type": self.type,
            "repository": self.repository,
            "number": self.number,
            "head_sha": self.head_sha,
        }


@dataclass(frozen=True)
class ArtifactBundleCandidateReference:
    """Immutable identity for a content-addressed artifact bundle."""

    locator: str
    digest: str
    media_type: str | None = None
    schema_version: str = _SCHEMA_VERSION
    type: str = "artifact_bundle"

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("unsupported candidate reference schema_version")
        if self.type != "artifact_bundle":
            raise ValueError("type must be artifact_bundle")
        object.__setattr__(self, "locator", _nonempty(self.locator, "locator"))
        digest = _nonempty(self.digest, "digest")
        if _SHA256_RE.fullmatch(digest) is None:
            raise ValueError("digest must be a lowercase sha256 content digest")
        if self.media_type is not None:
            object.__setattr__(
                self,
                "media_type",
                _nonempty(self.media_type, "media_type"),
            )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "type": self.type,
            "locator": self.locator,
            "digest": self.digest,
        }
        if self.media_type is not None:
            result["media_type"] = self.media_type
        return result


CandidateReference: TypeAlias = (
    GitHubPullRequestCandidateReference | ArtifactBundleCandidateReference
)


def candidate_reference_from_dict(raw: Mapping[str, Any]) -> CandidateReference:
    """Parse one strict v0.1 reference without provider-specific semantics."""

    if not isinstance(raw, Mapping):
        raise ValueError("candidate reference must be an object")
    schema_version = raw.get("schema_version")
    if schema_version != _SCHEMA_VERSION:
        raise ValueError("unsupported candidate reference schema_version")

    candidate_type = raw.get("type")
    if candidate_type == "github_pull_request":
        required = {"schema_version", "type", "repository", "number", "head_sha"}
        _strict_keys(raw, required=required)
        return GitHubPullRequestCandidateReference(
            repository=raw["repository"],
            number=raw["number"],
            head_sha=raw["head_sha"],
        )
    if candidate_type == "artifact_bundle":
        required = {"schema_version", "type", "locator", "digest"}
        _strict_keys(raw, required=required, optional={"media_type"})
        return ArtifactBundleCandidateReference(
            locator=raw["locator"],
            digest=raw["digest"],
            media_type=raw.get("media_type"),
        )

    raise ValueError("unsupported candidate reference type")
