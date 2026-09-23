"""Discover Jules pull-request outputs as untrusted SCM resolution hints.

Jules SessionOutput currently exposes pull-request URL/title/description, but no
immutable Git head object id. This module therefore returns only bounded
discovery hints. It cannot produce CandidateReference or candidate_ready state.

The expected repository comes from the trusted JulesSessionHandle captured at
session creation, not from issue text or a new caller-supplied repository.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_sessions import JulesSessionHandle


_SESSION_RE = re.compile(r"sessions/[^/]+\Z")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class JulesCandidateClient(Protocol):
    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """GET one decoded Jules JSON object."""


@dataclass(frozen=True)
class JulesPullRequestHint:
    """Provider observation requiring independent SCM resolution."""

    provider: str
    session_name: str
    repository: str
    pull_request_number: int
    url: str

    @property
    def requires_scm_resolution(self) -> bool:
        return True


def _parse_repository(repository: str) -> tuple[str, str]:
    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise ValueError("session repository must be in owner/name form")
    owner, repo = repository.split("/", 1)
    return owner, repo


def _parse_github_pr_url(
    url: Any,
    *,
    expected_repository: str,
    connection_id: str,
) -> tuple[int, str]:
    if not isinstance(url, str) or not url.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a pull request without a valid URL.",
            connection_id=connection_id,
        )

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a non-canonical GitHub pull request URL.",
            connection_id=connection_id,
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "pull":
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a non-canonical GitHub pull request URL.",
            connection_id=connection_id,
        )

    owner, repo, _, number_text = parts
    try:
        number = int(number_text)
    except ValueError as exc:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a pull request URL with an invalid number.",
            connection_id=connection_id,
        ) from exc
    if number < 1:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a pull request URL with an invalid number.",
            connection_id=connection_id,
        )

    expected_owner, expected_repo = _parse_repository(expected_repository)
    if (
        owner.casefold() != expected_owner.casefold()
        or repo.casefold() != expected_repo.casefold()
    ):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a pull request outside the authorized repository.",
            connection_id=connection_id,
            details={
                "expected_repository": expected_repository,
                "observed_repository": f"{owner}/{repo}",
            },
        )

    canonical_url = (
        f"https://github.com/{expected_owner}/{expected_repo}/pull/{number}"
    )
    return number, canonical_url


class JulesCandidateDiscoveryService:
    """Read completed Session outputs without inventing immutable SCM evidence."""

    def __init__(self, client: JulesCandidateClient, *, connection_id: str) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._client = client
        self._connection_id = connection_id

    def discover_pull_request_hints(
        self,
        session: JulesSessionHandle,
    ) -> tuple[JulesPullRequestHint, ...]:
        if not isinstance(session, JulesSessionHandle):
            raise ValueError("session must be a JulesSessionHandle")
        if _SESSION_RE.fullmatch(session.session_name) is None:
            raise ValueError("session handle contains an invalid session_name")
        _parse_repository(session.repository)

        raw = self._client.get_json("/" + session.session_name)
        if not isinstance(raw, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Session candidate metadata.",
                connection_id=self._connection_id,
            )

        if raw.get("name") != session.session_name or raw.get("id") != session.session_id:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned a different Session than requested.",
                connection_id=self._connection_id,
                details={"requested_session": session.session_name},
            )

        provider_state = raw.get("state")
        if provider_state != "COMPLETED":
            raise ConnectorError(
                code="conflict",
                message="Jules candidate discovery requires a completed Session.",
                connection_id=self._connection_id,
                details={"provider_state": provider_state},
            )

        outputs = raw.get("outputs", [])
        if not isinstance(outputs, list):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Session outputs.",
                connection_id=self._connection_id,
            )

        hints: dict[int, JulesPullRequestHint] = {}
        for index, output in enumerate(outputs):
            if not isinstance(output, Mapping):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules returned malformed Session output metadata.",
                    connection_id=self._connection_id,
                    details={"output_index": index},
                )

            if "pullRequest" not in output:
                continue
            pull_request = output["pullRequest"]
            if not isinstance(pull_request, Mapping):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules returned malformed pull request metadata.",
                    connection_id=self._connection_id,
                    details={"output_index": index},
                )

            number, canonical_url = _parse_github_pr_url(
                pull_request.get("url"),
                expected_repository=session.repository,
                connection_id=self._connection_id,
            )
            hint = JulesPullRequestHint(
                provider="jules",
                session_name=session.session_name,
                repository=session.repository,
                pull_request_number=number,
                url=canonical_url,
            )
            hints[number] = hint

        return tuple(hints[number] for number in sorted(hints))
