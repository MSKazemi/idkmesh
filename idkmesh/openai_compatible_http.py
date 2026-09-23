"""HTTP transport and /models probe for OpenAI-compatible endpoints.

This C3-B slice is provider-neutral. It uses the static connection contract from
openai_compatible and the shared ConnectorError envelope.

The probe is advisory connection evidence only. It does not dispatch coding
work, select a model for a WorkUnit, or grant repository authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from typing import Any, Mapping, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig


@dataclass(frozen=True)
class OpenAICompatibleHttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class OpenAICompatibleTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> OpenAICompatibleHttpResponse:
        """Execute one bounded HTTP request."""


class UrllibOpenAICompatibleTransport:
    """Stdlib transport for live compatible endpoints."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> OpenAICompatibleHttpResponse:
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
                return OpenAICompatibleHttpResponse(
                    status=int(response.status),
                    headers={
                        key: value
                        for key, value in response.headers.items()
                    },
                    body=payload,
                )
        except urlerror.HTTPError as exc:
            payload = exc.read(max_response_bytes + 1)
            if len(payload) > max_response_bytes:
                payload = b""
            return OpenAICompatibleHttpResponse(
                status=int(exc.code),
                headers={
                    key: value
                    for key, value in (exc.headers.items() if exc.headers else [])
                },
                body=payload,
            )
        except socket.timeout as exc:
            raise TimeoutError("model endpoint request timed out") from exc
        except urlerror.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise TimeoutError("model endpoint request timed out") from exc
            raise OSError("model endpoint transport unavailable") from exc


@dataclass(frozen=True)
class OpenAICompatibleProbeResult:
    connection_id: str
    status: str
    configured_model: str
    observed_models: tuple[str, ...]
    model_available: bool
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"healthy", "degraded"}:
            raise ValueError("probe status must be healthy or degraded")


def _retry_after_seconds(headers: Mapping[str, str]) -> int | None:
    for key, value in headers.items():
        if str(key).lower() != "retry-after":
            continue
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return None
        return seconds if seconds >= 0 else None
    return None


class OpenAICompatibleClient:
    """Small REST client for compatible model endpoints."""

    def __init__(
        self,
        config: OpenAICompatibleModelConfig,
        *,
        api_key: str | None = None,
        transport: OpenAICompatibleTransport | None = None,
    ) -> None:
        self.config = config
        if config.auth_required:
            if not isinstance(api_key, str) or not api_key.strip():
                raise ConnectorError(
                    code="authentication_error",
                    message="Model endpoint credential is unavailable.",
                    connection_id=config.connection_id,
                )
            self._api_key = api_key
        else:
            if api_key is not None and (
                not isinstance(api_key, str) or not api_key.strip()
            ):
                raise ValueError("api_key must be a non-empty string or None")
            self._api_key = api_key
        self._transport = transport or UrllibOpenAICompatibleTransport()

    def _headers(self, *, has_body: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "idkmesh-openai-compatible/0.1",
        }
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method not in {"GET", "POST"}:
            raise ValueError("method must be GET or POST")

        url = self.config.endpoint(path)
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
                    message="Model request body is not strict JSON.",
                    connection_id=self.config.connection_id,
                ) from exc

        try:
            response = self._transport.request(
                method=method,
                url=url,
                headers=self._headers(has_body=payload is not None),
                body=payload,
                timeout_seconds=self.config.timeout_seconds,
                max_response_bytes=self.config.max_response_bytes,
            )
        except TimeoutError as exc:
            raise ConnectorError(
                code="timeout",
                message="Model endpoint request timed out.",
                connection_id=self.config.connection_id,
            ) from exc
        except ValueError as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint response exceeded the configured safety boundary.",
                connection_id=self.config.connection_id,
            ) from exc
        except OSError as exc:
            raise ConnectorError(
                code="provider_unavailable",
                message="Model endpoint transport is unavailable.",
                connection_id=self.config.connection_id,
            ) from exc

        if (
            isinstance(response.status, bool)
            or not isinstance(response.status, int)
            or not 100 <= response.status <= 599
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="Model transport returned an invalid HTTP status.",
                connection_id=self.config.connection_id,
            )
        if not isinstance(response.body, bytes):
            raise ConnectorError(
                code="result_normalization_error",
                message="Model transport returned a non-byte response body.",
                connection_id=self.config.connection_id,
            )
        if len(response.body) > self.config.max_response_bytes:
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint response exceeded the configured safety boundary.",
                connection_id=self.config.connection_id,
            )

        if not 200 <= response.status < 300:
            raise self._http_error(response)

        if not response.body:
            return {}
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned a non-JSON response.",
                connection_id=self.config.connection_id,
                details={"http_status": response.status},
            ) from exc
        if not isinstance(decoded, dict):
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned the wrong top-level JSON type.",
                connection_id=self.config.connection_id,
                details={"http_status": response.status},
            )
        return decoded

    def _http_error(
        self,
        response: OpenAICompatibleHttpResponse,
    ) -> ConnectorError:
        status = response.status
        if status == 400:
            code = "configuration_error"
            message = "Model endpoint rejected the request."
        elif status == 401:
            code = "authentication_error"
            message = "Model endpoint authentication failed."
        elif status == 403:
            code = "authorization_error"
            message = "Model endpoint denied the request."
        elif status == 404:
            code = "not_found"
            message = "Model endpoint resource was not found."
        elif status == 409:
            code = "conflict"
            message = "Model endpoint reported a conflict."
        elif status == 429:
            code = "rate_limited"
            message = "Model endpoint temporarily rate limited the request."
        elif 500 <= status <= 599:
            code = "provider_unavailable"
            message = "Model endpoint is temporarily unavailable."
        else:
            code = "configuration_error"
            message = "Model endpoint rejected the request."

        details: dict[str, Any] = {"http_status": status}
        retry_after = _retry_after_seconds(response.headers)
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after
        return ConnectorError(
            code=code,
            message=message,
            connection_id=self.config.connection_id,
            details=details,
        )

    def list_models(self) -> tuple[str, ...]:
        """Return deterministic model IDs from the compatible /models API."""

        raw = self.request_json("GET", "/models")
        data = raw.get("data")
        if not isinstance(data, list):
            raise ConnectorError(
                code="result_normalization_error",
                message="Model endpoint returned malformed model-list metadata.",
                connection_id=self.config.connection_id,
            )

        model_ids: list[str] = []
        for index, item in enumerate(data):
            if not isinstance(item, Mapping):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Model endpoint returned malformed model metadata.",
                    connection_id=self.config.connection_id,
                    details={"model_index": index},
                )
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Model endpoint returned a model without a valid id.",
                    connection_id=self.config.connection_id,
                    details={"model_index": index},
                )
            normalized = model_id.strip()
            if normalized not in model_ids:
                model_ids.append(normalized)
        return tuple(sorted(model_ids))

    def probe(self) -> OpenAICompatibleProbeResult:
        observed = self.list_models()
        available = self.config.model in observed
        warnings = () if available else ("configured_model_not_observed",)
        return OpenAICompatibleProbeResult(
            connection_id=self.config.connection_id,
            status="healthy" if available else "degraded",
            configured_model=self.config.model,
            observed_models=observed,
            model_available=available,
            warnings=warnings,
        )
