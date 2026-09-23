"""Discover Jules-created pull requests as untrusted candidate locators.

C2-F deliberately stops at a GitHub pull-request URL/number. The Jules Session
output does not provide authoritative GitHub head-SHA evidence, so the SCM layer
must resolve and bind the PR head before candidate normalization/verification.

A discovered PR is not accepted work.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

from idkmesh.connector_errors import ConnectorError


_SESSION_RE = re.compile(r"sessions/[^/]+\Z")


class JulesCandidateClient(Protocol):
    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """GET one decoded Jules JSON object."""


@dataclass(frozen=True)
class JulesPullRequestCandidate:
    candidate_type: str
    provider: str
    session_name: str
    repository: str
    pull_request_number: int
    url: str
    head_sha: None
    requires_scm_resolution: bool


def _session_name(value: str, connection_id: str) -> str:
    if not isinstance(value, str) or _SESSION_RE.fullmatch(value) is None:
        raise ConnectorError(
            code="configuration_error",
            message="Jules session name is invalid.",
            connection_id=connection_id,
        )
    return value


def _parse_github_pr_url(
    url: Any,
    *,
    expected_owner: str,
    expected_repo: str,
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

    if owner.casefold() != expected_owner.casefold() or repo.casefold() != expected_repo.casefold():
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a pull request outside the authorized repository.",
            connection_id=connection_id,
            details={
                "expected_repository": f"{expected_owner}/{expected_repo}",
                "observed_repository": f"{owner}/{repo}",
            },
        )

    canonical = f"https://github.com/{owner}/{repo}/pull/{number}"
    return number, canonical


class JulesCandidateDiscoveryService:
    """Read provider outputs and return PR locators for later SCM resolution."""

    def __init__(self, client: JulesCandidateClient, *, connection_id: str) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._client = client
        self._connection_id = connection_id

    def discover_pull_requests(
        self,
        session_name: str,
        *,
        github_owner: str,
        github_repo: str,
    ) -> tuple[JulesPullRequestCandidate, ...]:
        session = _session_name(session_name, self._connection_id)
        for value, field in ((github_owner, "github_owner"), (github_repo, "github_repo")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")

        raw = self._client.get_json("/" + session)
        if not isinstance(raw, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Session candidate metadata.",
                connection_id=self._connection_id,
            )
        observed_name = raw.get("name")
        if observed_name != session:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned a different Session than requested.",
                connection_id=self._connection_id,
                details={
                    "requested_session": session,
                    "observed_session": observed_name,
                },
            )

        outputs = raw.get("outputs", [])
        if not isinstance(outputs, list):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Session outputs.",
                connection_id=self._connection_id,
            )

        candidates: dict[int, JulesPullRequestCandidate] = {}
        for index, output in enumerate(outputs):
            if not isinstance(output, Mapping):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules returned malformed Session output metadata.",
                    connection_id=self._connection_id,
                    details={"output_index": index},
                )

            if "pullRequest" not in output:
                # Jules may return other output kinds; C2-F handles PRs only.
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
                expected_owner=github_owner,
                expected_repo=github_repo,
                connection_id=self._connection_id,
            )

            candidate = JulesPullRequestCandidate(
                candidate_type="github_pull_request",
                provider="jules",
                session_name=session,
                repository=f"{github_owner}/{github_repo}",
                pull_request_number=number,
                url=canonical_url,
                head_sha=None,
                requires_scm_resolution=True,
            )
            previous = candidates.get(number)
            if previous is not None and previous.url != candidate.url:
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules returned conflicting pull request locators.",
                    connection_id=self._connection_id,
                    details={"pull_request_number": number},
                )
            candidates[number] = candidate

        return tuple(candidates[number] for number in sorted(candidates))
