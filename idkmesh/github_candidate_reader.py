"""Resolve GitHub pull requests into immutable CandidateReference objects.

This module is intentionally split from provider adapters. A provider may supply
repository/PR discovery data, but the SCM reader owns observation of the exact
GitHub head object id.

The reader emits identity/provenance only. It does not verify, accept, merge, or
otherwise integrate the candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.connector_errors import ConnectorError


_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class GitHubPullRequestSource(Protocol):
    def get_pull_request(
        self,
        *,
        repository: str,
        number: int,
    ) -> Mapping[str, Any]:
        """Return one GitHub pull-request API object."""


@dataclass(frozen=True)
class GitHubPullRequestResolution:
    """Trusted SCM resolution result without acceptance authority."""

    reference: GitHubPullRequestCandidateReference
    state: str
    draft: bool


def _repository(value: Any) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("repository must be in owner/name form")
    return value


def _number(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("number must be an integer >= 1")
    return value


def _mapping(
    value: Any,
    *,
    field: str,
    connection_id: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub returned malformed pull-request metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _string(
    value: Any,
    *,
    field: str,
    connection_id: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub returned malformed pull-request metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _canonical_pr_url(
    value: Any,
    *,
    repository: str,
    number: int,
    connection_id: str,
) -> str:
    url = _string(value, field="html_url", connection_id=connection_id)
    parsed = urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len(parts) != 4
        or parts[2] != "pull"
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub returned a non-canonical pull-request URL.",
            connection_id=connection_id,
        )

    try:
        observed_number = int(parts[3])
    except ValueError as exc:
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub returned a pull-request URL with an invalid number.",
            connection_id=connection_id,
        ) from exc

    owner, repo = repository.split("/", 1)
    if (
        parts[0].casefold() != owner.casefold()
        or parts[1].casefold() != repo.casefold()
        or observed_number != number
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="GitHub pull-request URL does not match requested candidate identity.",
            connection_id=connection_id,
            details={
                "requested_repository": repository,
                "requested_number": number,
            },
        )
    return f"https://github.com/{owner}/{repo}/pull/{number}"


class GitHubPullRequestCandidateReader:
    """Resolve one target-repository PR to an immutable exact-head reference."""

    def __init__(
        self,
        source: GitHubPullRequestSource,
        *,
        connection_id: str = "github",
    ) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._source = source
        self._connection_id = connection_id

    def resolve(
        self,
        *,
        repository: str,
        number: int,
    ) -> GitHubPullRequestResolution:
        expected_repository = _repository(repository)
        expected_number = _number(number)

        raw = self._source.get_pull_request(
            repository=expected_repository,
            number=expected_number,
        )
        if not isinstance(raw, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned a non-object pull-request response.",
                connection_id=self._connection_id,
            )

        observed_number = raw.get("number")
        if (
            isinstance(observed_number, bool)
            or not isinstance(observed_number, int)
            or observed_number != expected_number
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned a different pull request than requested.",
                connection_id=self._connection_id,
                details={
                    "requested_number": expected_number,
                    "observed_number": observed_number,
                },
            )

        base = _mapping(
            raw.get("base"),
            field="base",
            connection_id=self._connection_id,
        )
        base_repo = _mapping(
            base.get("repo"),
            field="base.repo",
            connection_id=self._connection_id,
        )
        observed_repository = _string(
            base_repo.get("full_name"),
            field="base.repo.full_name",
            connection_id=self._connection_id,
        )
        if observed_repository.casefold() != expected_repository.casefold():
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned a pull request from another target repository.",
                connection_id=self._connection_id,
                details={
                    "requested_repository": expected_repository,
                    "observed_repository": observed_repository,
                },
            )

        _canonical_pr_url(
            raw.get("html_url"),
            repository=expected_repository,
            number=expected_number,
            connection_id=self._connection_id,
        )

        head = _mapping(
            raw.get("head"),
            field="head",
            connection_id=self._connection_id,
        )
        head_sha = _string(
            head.get("sha"),
            field="head.sha",
            connection_id=self._connection_id,
        )
        try:
            reference = GitHubPullRequestCandidateReference(
                repository=expected_repository,
                number=expected_number,
                head_sha=head_sha,
            )
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned an invalid immutable pull-request head.",
                connection_id=self._connection_id,
                details={"field": "head.sha"},
            ) from exc

        state = _string(
            raw.get("state"),
            field="state",
            connection_id=self._connection_id,
        )
        if state not in {"open", "closed"}:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned an unknown pull-request state.",
                connection_id=self._connection_id,
                details={"state": state},
            )
        draft = raw.get("draft")
        if type(draft) is not bool:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed pull-request draft metadata.",
                connection_id=self._connection_id,
            )

        return GitHubPullRequestResolution(
            reference=reference,
            state=state,
            draft=draft,
        )
