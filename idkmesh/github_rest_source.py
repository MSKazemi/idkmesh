"""Bounded GitHub REST transport for pull-request identity lookup.

This module performs only the network transport needed by
GitHubPullRequestCandidateReader. It does not decide candidate identity itself:
the reader still validates repository, PR number, canonical URL, state/draft,
and exact head object id.

The source is stdlib-only, constructs a fixed api.github.com endpoint, limits
response bytes, and normalizes transport/auth/rate failures into ConnectorError.
Raw response bodies and credentials are never copied into error details.
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


def _number(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("number must be an integer >= 1")
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
        raise ValueError("timeout_seconds must be finite and in (0, 120]")
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
    if value is None:
        return None
    return str(value)


def _http_error(
    exc: HTTPError,
    *,
    repository: str,
    number: int,
) -> ConnectorError:
    status = int(exc.code)
    details: dict[str, Any] = {
        "status": status,
        "repository": repository,
        "pull_request_number": number,
    }

    if status == 401:
        code = "authentication_error"
        message = "GitHub rejected the configured credential."
    elif status == 403:
        remaining = _header(exc.headers, "X-RateLimit-Remaining")
        if remaining == "0":
            code = "rate_limited"
            message = "GitHub API rate limit is exhausted."
        else:
            code = "authorization_error"
            message = "GitHub denied pull-request metadata access."
    elif status == 404:
        code = "not_found"
        message = "GitHub pull request was not found."
    elif status == 408:
        code = "timeout"
        message = "GitHub pull-request request timed out."
    elif status == 429:
        code = "rate_limited"
        message = "GitHub API rate limited the pull-request request."
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
        connection_id="github",
        details=details,
    )


class GitHubRestPullRequestSource:
    """Fetch one GitHub PR REST object through a bounded fixed-host transport."""

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: int | float = 15,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        user_agent: str = "idkmesh/0.1",
    ) -> None:
        self._token = _token(token)
        self._timeout_seconds = _timeout(timeout_seconds)
        self._max_response_bytes = _max_response_bytes(max_response_bytes)
        if not callable(opener):
            raise ValueError("opener must be callable")
        self._opener = opener
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be a non-empty string")
        if any(ord(char) < 32 or ord(char) == 127 for char in user_agent):
            raise ValueError("user_agent must not contain control characters")
        self._user_agent = user_agent

    def get_pull_request(
        self,
        *,
        repository: str,
        number: int,
    ) -> Mapping[str, Any]:
        """Return one untrusted decoded PR object for the identity reader."""

        repo = _repository(repository)
        pr_number = _number(number)
        owner, name = repo.split("/", 1)
        url = f"{_API_BASE}/repos/{owner}/{name}/pulls/{pr_number}"

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
            response_context = self._opener(
                request,
                timeout=self._timeout_seconds,
            )
            with response_context as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise ConnectorError(
                        code="provider_unavailable",
                        message="GitHub API returned an unexpected HTTP status.",
                        connection_id="github",
                        details={
                            "status": status,
                            "repository": repo,
                            "pull_request_number": pr_number,
                        },
                    )
                payload = response.read(self._max_response_bytes + 1)
        except HTTPError as exc:
            raise _http_error(
                exc,
                repository=repo,
                number=pr_number,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectorError(
                code="timeout",
                message="GitHub pull-request request timed out.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise ConnectorError(
                    code="timeout",
                    message="GitHub pull-request request timed out.",
                    connection_id="github",
                    details={
                        "repository": repo,
                        "pull_request_number": pr_number,
                    },
                ) from exc
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub pull-request metadata is unavailable.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            ) from exc
        except ConnectorError:
            raise
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="GitHub pull-request metadata is unavailable.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            ) from exc

        if not isinstance(payload, bytes):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned a non-bytes pull-request response.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            )
        if len(payload) > self._max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub pull-request response exceeds the configured size limit.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                    "max_response_bytes": self._max_response_bytes,
                },
            )

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned malformed pull-request JSON.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            ) from exc

        if not isinstance(decoded, dict):
            raise ConnectorError(
                code="result_normalization_error",
                message="GitHub returned a non-object pull-request JSON response.",
                connection_id="github",
                details={
                    "repository": repo,
                    "pull_request_number": pr_number,
                },
            )
        return decoded
