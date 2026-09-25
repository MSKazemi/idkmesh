"""Bounded read-only GitHub Issue REST source for C5-D.

This adapter fetches one issue object from the fixed api.github.com endpoint and
hands the untrusted decoded mapping to github_issue_preview normalization.

It performs no mutation, routing, authorization, dispatch, secret persistence,
candidate acceptance, push, or merge action.
"""

from __future__ import annotations

import json
import math
import re
import socket
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    GitHubIssueSnapshot,
    parse_github_issue_snapshot,
)


_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ACCEPT = "application/vnd.github+json"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_CONFIGURED_RESPONSE_BYTES = 8 * 1024 * 1024


def _repository(value: Any) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("repository must be in owner/name form")
    return value


def _issue_number(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("issue_number must be an integer >= 1")
    return value


def _token(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("token must be a non-empty string or None")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("token must not contain control characters")
    return value


def _timeout(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value <= 0
        or value > 120
    ):
        raise ValueError(
            "timeout_seconds must be finite and in (0, 120]"
        )
    return float(value)


def _max_response_bytes(value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > _MAX_CONFIGURED_RESPONSE_BYTES
    ):
        raise ValueError(
            "max_response_bytes must be an integer from 1 to "
            f"{_MAX_CONFIGURED_RESPONSE_BYTES}"
        )
    return value


def _header(headers: Any, name: str) -> str | None:
    if headers is None:
        return None
    try:
        value = headers.get(name)
    except (AttributeError, TypeError):
        return None
    return None if value is None else str(value)


def _http_error(
    exc: HTTPError,
    *,
    repository: str,
    issue_number: int,
    connection_id: str,
) -> ConnectorError:
    status = int(exc.code)
    details: dict[str, Any] = {
        "status": status,
        "repository": repository,
        "issue_number": issue_number,
    }
    if status == 401:
        code = "authentication_error"
        message = "GitHub rejected the configured issue-read credential."
    elif status == 403:
        remaining = _header(
            exc.headers,
            "X-RateLimit-Remaining",
        )
        if remaining == "0":
            code = "rate_limited"
            message = "GitHub API rate limit is exhausted."
        else:
            code = "authorization_error"
            message = "GitHub denied issue metadata access."
    elif status == 404:
        code = "not_found"
        message = "GitHub issue was not found."
    elif status == 408:
        code = "timeout"
        message = "GitHub issue request timed out."
    elif status == 429:
        code = "rate_limited"
        message = "GitHub API rate limited the issue request."
    elif 500 <= status <= 599:
        code = "provider_unavailable"
        message = "GitHub API is temporarily unavailable."
    else:
        code = "provider_unavailable"
        message = "GitHub API returned an unexpected HTTP status."

    retry_after = _header(exc.headers, "Retry-After")
    if retry_after is not None and retry_after.strip():
        details["retry_after"] = retry_after.strip()

    return ConnectorError(
        code=code,
        message=message,
        connection_id=connection_id,
        details=details,
    )


class GitHubRestIssueSource:
    """Fetch one issue REST object through a bounded fixed-host transport."""

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: int | float = 15,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        user_agent: str = "idkmesh/0.1",
        connection_id: str = "github-issue-read",
    ) -> None:
        self._token = _token(token)
        self._timeout_seconds = _timeout(timeout_seconds)
        self._max_response_bytes = _max_response_bytes(
            max_response_bytes
        )
        if not callable(opener):
            raise ValueError("opener must be callable")
        self._opener = opener
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be a non-empty string")
        if any(
            ord(char) < 32 or ord(char) == 127
            for char in user_agent
        ):
            raise ValueError(
                "user_agent must not contain control characters"
            )
        self._user_agent = user_agent
        if (
            not isinstance(connection_id, str)
            or not connection_id.strip()
        ):
            raise ValueError(
                "connection_id must be a non-empty string"
            )
        self._connection_id = connection_id

    def get_issue(
        self,
        *,
        repository: str,
        issue_number: int,
    ) -> Mapping[str, Any]:
        repo = _repository(repository)
        number = _issue_number(issue_number)
        owner, name = repo.split("/", 1)
        url = (
            f"{_API_BASE}/repos/{owner}/{name}/issues/{number}"
        )

        headers = {
            "Accept": _ACCEPT,
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": self._user_agent,
        }
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"

        request = Request(
            url,
            headers=headers,
            method="GET",
        )

        try:
            context = self._opener(
                request,
                timeout=self._timeout_seconds,
            )
            with context as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise ConnectorError(
                        code="provider_unavailable",
                        message=(
                            "GitHub API returned an unexpected "
                            "issue response status."
                        ),
                        connection_id=self._connection_id,
                        details={
                            "status": status,
                            "repository": repo,
                            "issue_number": number,
                        },
                    )
                payload = response.read(
                    self._max_response_bytes + 1
                )
        except HTTPError as exc:
            raise _http_error(
                exc,
                repository=repo,
                issue_number=number,
                connection_id=self._connection_id,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectorError(
                code="timeout",
                message="GitHub issue request timed out.",
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            code = (
                "timeout"
                if isinstance(
                    reason,
                    (TimeoutError, socket.timeout),
                )
                else "provider_unavailable"
            )
            raise ConnectorError(
                code=code,
                message="GitHub issue metadata is unavailable.",
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            ) from exc
        except ConnectorError:
            raise
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub issue metadata is unavailable.",
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            ) from exc

        if not isinstance(payload, bytes):
            raise ConnectorError(
                code="result_normalization_error",
                message=(
                    "GitHub returned a non-bytes issue response."
                ),
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            )
        if len(payload) > self._max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message=(
                    "GitHub issue response exceeds the "
                    "configured size limit."
                ),
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                    "max_response_bytes": (
                        self._max_response_bytes
                    ),
                },
            )

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed issue JSON.",
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            ) from exc
        if not isinstance(decoded, dict):
            raise ConnectorError(
                code="result_normalization_error",
                message=(
                    "GitHub returned a non-object issue JSON response."
                ),
                connection_id=self._connection_id,
                details={
                    "repository": repo,
                    "issue_number": number,
                },
            )
        return decoded

    def get_issue_snapshot(
        self,
        *,
        repository: str,
        issue_number: int,
    ) -> GitHubIssueSnapshot:
        raw = self.get_issue(
            repository=repository,
            issue_number=issue_number,
        )
        return parse_github_issue_snapshot(
            raw,
            repository=repository,
            expected_number=issue_number,
        )
