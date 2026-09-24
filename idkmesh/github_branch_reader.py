"""Validate GitHub branch-ref observations into exact source bindings.

This module is the read-only identity boundary for a mutable GitHub branch.
A transport returns an untrusted GitHub ref object; the reader proves that the
object describes the exact requested refs/heads/<branch> and that its target is
an immutable Git commit object id.

The result is source identity evidence only. It does not authorize dispatch,
mark a Jules ScmRevisionBinding as verified by itself, or grant candidate,
verification, merge, or integration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol


_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_GIT_OBJECT_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_BRANCH_CHARS_RE = re.compile(r"[A-Za-z0-9._/-]+\Z")


class BranchHeadResolutionError(RuntimeError):
    """Raised when SCM ref data cannot prove the requested branch head."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.details = dict(details or {})


class GitHubBranchRefSource(Protocol):
    def get_branch_ref(
        self,
        *,
        repository: str,
        branch: str,
    ) -> Mapping[str, Any]:
        """Return one untrusted GitHub git-ref API object."""


@dataclass(frozen=True)
class GitHubBranchHeadBinding:
    """Exact observed head of one requested GitHub branch."""

    repository: str
    branch: str
    revision: str

    def __post_init__(self) -> None:
        _repository(self.repository)
        _branch(self.branch)
        normalized = _revision(self.revision, "revision")
        object.__setattr__(self, "revision", normalized)

    @property
    def full_ref(self) -> str:
        return f"refs/heads/{self.branch}"

    def to_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "branch": self.branch,
            "revision": self.revision,
        }


def _repository(value: Any) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("repository must be in owner/name form")
    return value


def _branch(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("branch must be a non-empty string")
    if len(value) > 255:
        raise ValueError("branch exceeds the 255-character bound")
    if _BRANCH_CHARS_RE.fullmatch(value) is None:
        raise ValueError("branch contains unsupported characters")
    if (
        value.startswith("/")
        or value.endswith("/")
        or value.startswith(".")
        or value.endswith(".")
        or value.endswith(".lock")
        or "//" in value
        or ".." in value
        or "@{" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("branch is not a safe canonical Git branch name")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BranchHeadResolutionError(
            "GitHub returned malformed branch-ref metadata.",
            field=field,
        )
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BranchHeadResolutionError(
            "GitHub returned malformed branch-ref metadata.",
            field=field,
        )
    return value


def _revision(value: Any, field: str) -> str:
    revision = _string(value, field)
    if _GIT_OBJECT_RE.fullmatch(revision) is None:
        raise BranchHeadResolutionError(
            "GitHub branch ref does not point to a valid immutable Git object id.",
            field=field,
        )
    return revision.lower()


class GitHubBranchHeadReader:
    """Resolve one requested branch to its exact immutable commit object id."""

    def __init__(self, source: GitHubBranchRefSource) -> None:
        self._source = source

    def resolve(
        self,
        *,
        repository: str,
        branch: str,
    ) -> GitHubBranchHeadBinding:
        expected_repository = _repository(repository)
        expected_branch = _branch(branch)
        expected_ref = f"refs/heads/{expected_branch}"

        raw = self._source.get_branch_ref(
            repository=expected_repository,
            branch=expected_branch,
        )
        if not isinstance(raw, Mapping):
            raise BranchHeadResolutionError(
                "GitHub returned a non-object branch-ref response."
            )

        observed_ref = _string(raw.get("ref"), "ref")
        if observed_ref != expected_ref:
            raise BranchHeadResolutionError(
                "GitHub returned a different branch ref than requested.",
                field="ref",
                details={
                    "requested_ref": expected_ref,
                    "observed_ref": observed_ref,
                },
            )

        target = _mapping(raw.get("object"), "object")
        object_type = _string(target.get("type"), "object.type")
        if object_type != "commit":
            raise BranchHeadResolutionError(
                "GitHub branch ref target is not a commit object.",
                field="object.type",
                details={"object_type": object_type},
            )

        revision = _revision(target.get("sha"), "object.sha")
        return GitHubBranchHeadBinding(
            repository=expected_repository,
            branch=expected_branch,
            revision=revision,
        )
