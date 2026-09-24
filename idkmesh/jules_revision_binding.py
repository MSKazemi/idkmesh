"""Authorize Jules SCM revision binding only after trusted observation matches.

The GitHub branch reader establishes identity evidence. This module is the
separate comparison boundary that decides whether the authorized requested
repository/branch/revision exactly matches that evidence.

Only a successful comparison may construct ScmRevisionBinding(verified=True).
No dispatch, candidate, verification-result, merge, or integration authority is
granted here.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_sessions import ScmRevisionBinding


_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


class ObservedScmBranchHead(Protocol):
    repository: str
    branch: str
    revision: str


def _expected_repository(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("expected_repository must be in owner/name form")
    owner, repo = value.split("/", 1)
    return value, owner, repo


def _branch(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _revision(value: Any, field: str) -> str:
    if not isinstance(value, str) or _REVISION_RE.fullmatch(value) is None:
        raise ValueError(
            f"{field} must be a 40- or 64-character hexadecimal Git object id"
        )
    return value.lower()


def verify_jules_scm_revision(
    *,
    expected_repository: str,
    expected_branch: str,
    expected_revision: str,
    observed: ObservedScmBranchHead,
    connection_id: str,
) -> ScmRevisionBinding:
    """Return verified Jules binding only when trusted SCM evidence matches."""

    canonical_repository, owner, repo = _expected_repository(
        expected_repository
    )
    branch = _branch(expected_branch, "expected_branch")
    revision = _revision(expected_revision, "expected_revision")
    if not isinstance(connection_id, str) or not connection_id.strip():
        raise ValueError("connection_id must be a non-empty string")

    try:
        observed_repository = observed.repository
        observed_branch = observed.branch
        observed_revision = observed.revision
    except AttributeError as exc:
        raise ConnectorError(
            code="result_normalization_error",
            message="Trusted SCM branch-head observation is incomplete.",
            connection_id=connection_id,
        ) from exc

    if (
        not isinstance(observed_repository, str)
        or _REPOSITORY_RE.fullmatch(observed_repository) is None
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="Trusted SCM branch-head observation has invalid repository identity.",
            connection_id=connection_id,
        )
    if not isinstance(observed_branch, str) or not observed_branch.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="Trusted SCM branch-head observation has invalid branch identity.",
            connection_id=connection_id,
        )
    if (
        not isinstance(observed_revision, str)
        or _REVISION_RE.fullmatch(observed_revision) is None
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="Trusted SCM branch-head observation has invalid revision identity.",
            connection_id=connection_id,
        )

    mismatches: list[str] = []
    if observed_repository.casefold() != canonical_repository.casefold():
        mismatches.append("repository")
    if observed_branch != branch:
        mismatches.append("branch")
    if observed_revision.lower() != revision:
        mismatches.append("revision")

    if mismatches:
        raise ConnectorError(
            code="conflict",
            message="Authorized source revision does not match trusted SCM branch-head evidence.",
            connection_id=connection_id,
            details={
                "mismatched_fields": mismatches,
                "expected_repository": canonical_repository,
                "expected_branch": branch,
                "expected_revision": revision,
                "observed_repository": observed_repository,
                "observed_branch": observed_branch,
                "observed_revision": observed_revision.lower(),
            },
        )

    return ScmRevisionBinding(
        github_owner=owner,
        github_repo=repo,
        branch=branch,
        revision=revision,
        verified=True,
    )
