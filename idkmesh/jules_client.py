"""Minimal Jules REST transport shell for C2-A (#575).

The client is intentionally small and provider-specific while depending only on
the shared provider-neutral ConnectorError contract. It owns HTTP mechanics,
authentication header construction, timeout behavior, bounded response reads,
and HTTP-to-error normalization.

It does not own:
- secret-reference resolution;
- WorkUnit admission;
- source selection;
- session semantics;
- plan approval policy;
- candidate acceptance or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import socket
from typing import Any, Mapping, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlencode, urlsplit

from idkmesh.connector_errors import ConnectorError


DEFAULT_BASE_URL = "https://jules.googleapis.com/v1alpha"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class JulesHttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class JulesTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> JulesHttpResponse:
        """Execute one HTTP request without interpreting Jules semantics."""


class UrllibJulesTransport:
    """Small stdlib transport used by the live client path."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> JulesHttpResponse:
        req = urlrequest.Request(
            url=url,
            data=body,
            headers=dict(headers),
            method=method,
        )
        try:
            with urlrequest.urlopen(req, timeout=timeout_seconds) as response:
                payload = response.read(max_response_bytes + 1)
                if len(payload) > max_response_bytes:
                    raise ValueError("response body exceeds configured maximum")
                return JulesHttpResponse(
                    status=int(response.status),
                    headers={key: value for key, value in response.headers.items()},
                    body=payload,
                )
        except urlerror.HTTPError as exc:
            payload = exc.read(max_response_bytes + 1)
            if len(payload) > max_response_bytes:
                payload = b""
            return JulesHttpResponse(
                status=int(exc.code),
                headers={key: value for key, value in exc.headers.items()},
                body=payload,
            )
        except socket.timeout as exc:
            raise TimeoutError("Jules request timed out") from exc
        except urlerror.URLError as exc:
            reason = exc.reason
            if isinstance(reason, socket.timeout):
                raise TimeoutError("Jules request timed out") from exc
            raise OSError("Jules transport unavailable") from exc


def _validate_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be a non-empty string")

    normalized = base_url.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain credentials, query, or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("plain HTTP is allowed only for loopback test endpoints")
    return normalized


def _positive_finite_number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return value


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _retry_after_seconds(headers: Mapping[str, str]) -> int | None:
    raw = _normalized_headers(headers).get("retry-after")
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


class JulesClient:
    """HTTP-only Jules client with injected transport for deterministic tests."""

    def __init__(
        self,
        *,
        api_key: str,
        connection_id: str = "jules",
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        transport: JulesTransport | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty runtime credential")
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")

        self._api_key = api_key
        self._connection_id = connection_id
        self._base_url = _validate_base_url(base_url)
        self._timeout_seconds = _positive_finite_number(
            timeout_seconds, "timeout_seconds"
        )
        self._max_response_bytes = _positive_int(
            max_response_bytes, "max_response_bytes"
        )
        self._transport = transport or UrllibJulesTransport()

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def connection_id(self) -> str:
        return self._connection_id

    def _url(
        self,
        path: str,
        query: Mapping[str, str | int] | None = None,
    ) -> str:
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if "://" in path:
            raise ValueError("path must be relative to the configured Jules base URL")

        url = self._base_url + path
        if query:
            encoded: dict[str, str | int] = {}
            for key, value in query.items():
                if not isinstance(key, str) or not key:
                    raise ValueError("query keys must be non-empty strings")
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    raise ValueError("query values must be strings or integers")
                encoded[key] = value
            url += "?" + urlencode(encoded)
        return url

    def _headers(self, *, has_body: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "User-Agent": "idkmesh-jules/0.1",
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one Jules request and return a decoded JSON object."""

        if method not in {"GET", "POST", "DELETE"}:
            raise ValueError("method must be GET, POST, or DELETE")
        payload = None
        if body is not None:
            try:
                payload = json.dumps(
                    body,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ConnectorError(
                    code="configuration_error",
                    message="Jules request body is not strict JSON.",
                    connection_id=self._connection_id,
                ) from exc

        try:
            response = self._transport.request(
                method=method,
                url=self._url(path, query),
                headers=self._headers(has_body=payload is not None),
                body=payload,
                timeout_seconds=self._timeout_seconds,
                max_response_bytes=self._max_response_bytes,
            )
        except TimeoutError as exc:
            raise ConnectorError(
                code="timeout",
                message="Jules request timed out.",
                connection_id=self._connection_id,
            ) from exc
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules response exceeded the configured safety boundary.",
                connection_id=self._connection_id,
            ) from exc
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="Jules transport is unavailable.",
                connection_id=self._connection_id,
            ) from exc

        if not 200 <= response.status < 300:
            raise self._http_error(response)

        if not response.body:
            return {}

        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned a non-JSON response.",
                connection_id=self._connection_id,
                details={"http_status": response.status},
            ) from exc
        if not isinstance(decoded, dict):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned a JSON value with the wrong top-level type.",
                connection_id=self._connection_id,
                details={"http_status": response.status},
            )
        return decoded

    def _http_error(self, response: JulesHttpResponse) -> ConnectorError:
        status = response.status
        if status == 400:
            code = "configuration_error"
            message = "Jules rejected the request."
        elif status == 401:
            code = "authentication_error"
            message = "Jules authentication failed."
        elif status == 403:
            code = "authorization_error"
            message = "Jules denied access to the requested resource."
        elif status == 404:
            code = "not_found"
            message = "Jules resource was not found."
        elif status == 409:
            code = "conflict"
            message = "Jules reported a resource conflict."
        elif status == 429:
            code = "rate_limited"
            message = "Jules temporarily rate limited the request."
        elif 500 <= status <= 599:
            code = "provider_unavailable"
            message = "Jules is temporarily unavailable."
        else:
            code = "configuration_error"
            message = "Jules rejected the request."

        details: dict[str, Any] = {"http_status": status}
        retry_after = _retry_after_seconds(response.headers)
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after

        return ConnectorError(
            code=code,
            message=message,
            connection_id=self._connection_id,
            details=details,
        )

    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        return self.request_json("GET", path, query=query)

    def post_json(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request_json("POST", path, body=body)

    def delete_json(self, path: str) -> dict[str, Any]:
        return self.request_json("DELETE", path)
