"""Bounded public-GitHub REST sources for SCM identity lookup.

This module owns fixed-host HTTP mechanics, bounded JSON decoding, and stable
ConnectorError translation for GitHub identity reads.

It deliberately does not decide SCM identity correctness:
- GitHubPullRequestCandidateReader validates pull-request identity;
- GitHubBranchHeadReader validates branch-ref identity.

Raw response bodies and credentials are never copied into error details.
"""

from __future__ import annotations

import json
import math
import re
import socket
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from idkmesh.connector_errors import ConnectorError


_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ACCEPT = "application/vnd.github+json"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_BRANCH_CHARS_RE = re.compile(r"[A-Za-z0-9._/-]+\Z")
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
    connection_id: str,
    details: Mapping[str, Any],
    resource_label: str,
) -> ConnectorError:
    status = int(exc.code)
    normalized_details = {
        "status": status,
        **dict(details),
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
            message = f"GitHub denied {resource_label} access."
    elif status == 404:
        code = "not_found"
        message = f"GitHub {resource_label} was not found."
    elif status == 408:
        code = "timeout"
        message = f"GitHub {resource_label} request timed out."
    elif status == 429:
        code = "rate_limited"
        message = f"GitHub API rate limited the {resource_label} request."
    elif 500 <= status <= 599:
        code = "provider_unavailable"
        message = "GitHub API is temporarily unavailable."
    else:
        code = "provider_unavailable"
        message = "GitHub API returned an unexpected HTTP status."

    retry_after = _header(exc.headers, "Retry-After")
    if retry_after is not None and retry_after.strip():
        normalized_details["retry_after"] = retry_after.strip()

    return ConnectorError(
        code=code,
        message=message,
        connection_id=connection_id,
        details=normalized_details,
    )


class GitHubRestIdentitySource:
    """Fixed-host bounded REST source for GitHub SCM identity observations."""

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: int | float = 15,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        user_agent: str = "idkmesh/0.1",
        connection_id: str = "github",
    ) -> None:
        self._token = _token(token)
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._connection_id = connection_id
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

    def _get_json(
        self,
        *,
        url: str,
        details: Mapping[str, Any],
        resource_label: str,
    ) -> Mapping[str, Any]:
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
                        connection_id=self._connection_id,
                        details={
                            "status": status,
                            **dict(details),
                        },
                    )
                payload = response.read(self._max_response_bytes + 1)
        except HTTPError as exc:
            raise _http_error(
                exc,
                connection_id=self._connection_id,
                details=details,
                resource_label=resource_label,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectorError(
                code="timeout",
                message=f"GitHub {resource_label} request timed out.",
                connection_id=self._connection_id,
                details=dict(details),
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise ConnectorError(
                    code="timeout",
                    message=f"GitHub {resource_label} request timed out.",
                    connection_id=self._connection_id,
                    details=dict(details),
                ) from exc
            raise ConnectorError(
                code="provider_unavailable",
                message=f"GitHub {resource_label} metadata is unavailable.",
                connection_id=self._connection_id,
                details=dict(details),
            ) from exc
        except ConnectorError:
            raise
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message=f"GitHub {resource_label} metadata is unavailable.",
                connection_id=self._connection_id,
                details=dict(details),
            ) from exc

        if not isinstance(payload, bytes):
            raise ConnectorError(
                code="result_normalization_error",
                message=f"GitHub returned a non-bytes {resource_label} response.",
                connection_id=self._connection_id,
                details=dict(details),
            )
        if len(payload) > self._max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message=(
                    f"GitHub {resource_label} response exceeds "
                    "the configured size limit."
                ),
                connection_id=self._connection_id,
                details={
                    **dict(details),
                    "max_response_bytes": self._max_response_bytes,
                },
            )

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message=f"GitHub returned malformed {resource_label} JSON.",
                connection_id=self._connection_id,
                details=dict(details),
            ) from exc

        if not isinstance(decoded, dict):
            raise ConnectorError(
                code="result_normalization_error",
                message=(
                    f"GitHub returned a non-object {resource_label} "
                    "JSON response."
                ),
                connection_id=self._connection_id,
                details=dict(details),
            )
        return decoded

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
        return self._get_json(
            url=f"{_API_BASE}/repos/{owner}/{name}/pulls/{pr_number}",
            details={
                "repository": repo,
                "pull_request_number": pr_number,
            },
            resource_label="pull-request",
        )

    def get_branch_ref(
        self,
        *,
        repository: str,
        branch: str,
    ) -> Mapping[str, Any]:
        """Return one untrusted decoded branch-ref object for the identity reader."""

        repo = _repository(repository)
        branch_name = _branch(branch)
        owner, name = repo.split("/", 1)
        encoded_branch = quote(branch_name, safe="")
        return self._get_json(
            url=(
                f"{_API_BASE}/repos/{owner}/{name}/git/ref/heads/"
                f"{encoded_branch}"
            ),
            details={
                "repository": repo,
                "branch": branch_name,
            },
            resource_label="branch-ref",
        )


# Compatibility alias retained for existing callers introduced in v0.1.
GitHubRestPullRequestSource = GitHubRestIdentitySource
