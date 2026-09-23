"""Bind Jules pull-request discovery hints to trusted GitHub candidate identity.

Jules is allowed to tell IDKMesh where it believes a pull request exists.
Jules is not allowed to define the immutable Git head that makes that pull
request a CandidateReference.

This bridge consumes a bounded JulesPullRequestHint and delegates exact identity
resolution to the provider-neutral GitHubPullRequestCandidateReader. It returns
that shared SCM resolution unchanged and grants no run-state, verification,
acceptance, or integration authority.
"""

from __future__ import annotations

import re
from typing import Protocol

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import (
    CandidateResolutionError,
    GitHubPullRequestResolution,
)
from idkmesh.jules_candidates import JulesPullRequestHint


_SESSION_RE = re.compile(r"sessions/[^/]+\Z")


class JulesPullRequestResolver(Protocol):
    """Provider-neutral SCM resolver required by the Jules bridge."""

    def resolve(
        self,
        *,
        repository: str,
        number: int,
    ) -> GitHubPullRequestResolution:
        """Resolve target repository + PR number to exact SCM identity."""


def _expected_url(hint: JulesPullRequestHint) -> str:
    return (
        f"https://github.com/{hint.repository}/pull/"
        f"{hint.pull_request_number}"
    )


class JulesCandidateBindingService:
    """Convert a Jules discovery hint into trusted SCM candidate identity."""

    def __init__(
        self,
        resolver: JulesPullRequestResolver,
        *,
        connection_id: str,
    ) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._resolver = resolver
        self._connection_id = connection_id

    def resolve_pull_request_hint(
        self,
        hint: JulesPullRequestHint,
    ) -> GitHubPullRequestResolution:
        """Resolve one Jules PR hint through the independent SCM boundary.

        The result is provider-neutral. This method intentionally does not
        return or mutate control-plane run state.
        """

        if not isinstance(hint, JulesPullRequestHint):
            raise ValueError("hint must be a JulesPullRequestHint")
        if hint.provider != "jules":
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate binding received a non-Jules hint.",
                connection_id=self._connection_id,
            )
        if (
            not isinstance(hint.session_name, str)
            or _SESSION_RE.fullmatch(hint.session_name) is None
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate hint contains an invalid Session name.",
                connection_id=self._connection_id,
            )
        if not isinstance(hint.repository, str) or not hint.repository.strip():
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate hint contains an invalid repository.",
                connection_id=self._connection_id,
            )
        if (
            isinstance(hint.pull_request_number, bool)
            or not isinstance(hint.pull_request_number, int)
            or hint.pull_request_number < 1
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate hint contains an invalid pull request number.",
                connection_id=self._connection_id,
            )

        expected_url = _expected_url(hint)
        if hint.url != expected_url:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate hint URL does not match its bound repository and pull request.",
                connection_id=self._connection_id,
                details={
                    "repository": hint.repository,
                    "pull_request_number": hint.pull_request_number,
                },
            )

        try:
            resolved = self._resolver.resolve(
                repository=hint.repository,
                number=hint.pull_request_number,
            )
        except CandidateResolutionError as exc:
            details = {
                "repository": hint.repository,
                "pull_request_number": hint.pull_request_number,
            }
            if exc.field is not None:
                details["scm_field"] = exc.field
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub could not establish immutable identity for the Jules candidate.",
                connection_id=self._connection_id,
                details=details,
            ) from exc
        except ValueError as exc:
            # The provider-neutral reader uses ValueError only for malformed
            # caller identity. A Jules hint reaching this point is provider
            # observation, so expose it through the connector taxonomy.
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate hint could not be admitted by the SCM resolver.",
                connection_id=self._connection_id,
                details={
                    "repository": hint.repository,
                    "pull_request_number": hint.pull_request_number,
                },
            ) from exc

        if not isinstance(resolved, GitHubPullRequestResolution):
            raise ConnectorError(
                code="result_normalization_error",
                message="SCM resolver returned an unexpected candidate resolution type.",
                connection_id=self._connection_id,
            )

        reference = resolved.reference
        if (
            reference.repository != hint.repository
            or reference.number != hint.pull_request_number
            or reference.canonical_url != hint.url
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="SCM candidate identity does not match the Jules discovery hint.",
                connection_id=self._connection_id,
                details={
                    "repository": hint.repository,
                    "pull_request_number": hint.pull_request_number,
                },
            )

        return resolved
