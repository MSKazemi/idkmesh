"""Reusable HTTP service-runtime primitives for IDKMesh.

The module is intentionally dependency-free. It provides cross-cutting
production concerns that should be shared by the local Control Tower, future C7
HTTP control-plane surfaces, and other bounded IDKMesh services:

- request correlation without trusting arbitrary header content;
- liveness/readiness metadata without exposing project state;
- stable service/version/read-only response headers;
- optional structured access logs that never include request bodies, secrets,
  authentication tokens, or query strings.

It is not an authentication or authorization system. Identity/RBAC remains
owned by the C10 policy layer and network/mutating API authorization by C7.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import threading
import time
import secrets
import sys
from typing import Any, Mapping, TextIO

REQUEST_ID_HEADER = "X-Request-ID"
SERVICE_HEADER = "X-IDKMesh-Service"
SERVICE_VERSION_HEADER = "X-IDKMesh-Service-Version"
READ_ONLY_HEADER = "X-IDKMesh-Read-Only"
ACCESS_LOG_ENV = "IDKMESH_HTTP_ACCESS_LOG"

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEADER_VALUE_RE = re.compile(r"^[!-~]{1,128}$")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

# ADR-0022: bounded service limits for the local development servers.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_CONCURRENT_REQUESTS = 16
DEFAULT_RETRY_AFTER_SECONDS = 1
DEFAULT_DRAIN_TIMEOUT_SECONDS = 5.0
MIN_REQUEST_TIMEOUT_SECONDS = 0.1
MAX_REQUEST_TIMEOUT_SECONDS = 300.0
MAX_CONCURRENT_REQUESTS_CEILING = 1024
# The stdlib parser's own bounds (http.server / http.client); documented and
# pinned by tests rather than re-implemented. http.client allows 100 lines but
# counts the blank line that ends the header block, so the largest accepted
# request carries 99 header fields (measured: 99 -> 200, 100 -> 431).
# ADR-0023: bounded Server-Sent Events streams.
DEFAULT_MAX_SSE_CLIENTS = 8
MAX_SSE_CLIENTS_CEILING = 64
SSE_POLL_SECONDS = 0.5
SSE_HEARTBEAT_SECONDS = 15.0
SSE_MAX_STREAM_SECONDS = 300.0
MAX_REQUEST_LINE_BYTES = 65536
MAX_HEADER_LINE_BYTES = 65536
MAX_HEADER_COUNT = 99
_MAX_LOG_PATH = 2048
_MAX_LOG_METHOD = 32
_MAX_LOG_SERVICE = 128


def new_request_id() -> str:
    """Return an opaque request identifier suitable for logs and headers."""
    return "req_" + secrets.token_hex(16)


def resolve_request_id(value: str | None) -> str:
    """Accept one safe caller correlation ID or replace it with a local ID."""
    if value is not None and _REQUEST_ID_RE.fullmatch(value):
        return value
    return new_request_id()


def access_logging_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    return env.get(ACCESS_LOG_ENV, "").strip().lower() in _TRUE_VALUES


def _header_value(value: str, field: str) -> str:
    if not isinstance(value, str) or not _HEADER_VALUE_RE.fullmatch(value):
        raise ValueError(
            f"{field} must be 1-128 visible ASCII characters without spaces"
        )
    return value


def _bounded_log_text(value: str, max_length: int) -> str:
    text = "".join(
        char if char.isprintable() and char not in "\r\n" else "?"
        for char in str(value)
    )
    return text[:max_length]


def service_headers(
    *,
    service: str,
    service_version: str,
    request_id: str,
    read_only: bool,
    api_version: str | None = None,
) -> dict[str, str]:
    """Build stable cross-service response metadata headers."""
    headers = {
        REQUEST_ID_HEADER: (
            request_id
            if _REQUEST_ID_RE.fullmatch(request_id)
            else resolve_request_id(None)
        ),
        SERVICE_HEADER: _header_value(service, "service"),
        SERVICE_VERSION_HEADER: _header_value(
            service_version, "service_version"
        ),
        READ_ONLY_HEADER: "true" if read_only else "false",
    }
    if api_version is not None:
        headers["X-IDKMesh-API-Version"] = _header_value(
            api_version, "api_version"
        )
    return headers


def readiness_document(
    *,
    service: str,
    service_version: str,
    mode: str,
    api_version: str | None = None,
) -> dict[str, Any]:
    """Return a minimal readiness document with no project/evidence state."""
    result: dict[str, Any] = {
        "status": "ready",
        "service": _header_value(service, "service"),
        "service_version": _header_value(
            service_version, "service_version"
        ),
        "mode": _header_value(mode, "mode"),
    }
    if api_version is not None:
        result["api_version"] = _header_value(
            api_version, "api_version"
        )
    return result


def build_access_log_event(
    *,
    service: str,
    request_id: str,
    method: str,
    path: str,
    status: int,
    response_bytes: int,
    duration_ms: float,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Create a bounded access-log event.

    Query strings are stripped defensively and text fields are bounded before
    serialization. Headers and request/response bodies are intentionally not
    accepted.
    """
    if occurred_at is None:
        occurred_at = (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    status_value = int(status)
    response_size = int(response_bytes)
    if not 100 <= status_value <= 599:
        raise ValueError("status must be an HTTP status code")
    if response_size < 0:
        raise ValueError("response_bytes must be >= 0")

    safe_path = str(path).split("?", 1)[0]
    return {
        "event": "http_request",
        "service": _bounded_log_text(service, _MAX_LOG_SERVICE),
        "request_id": (
            request_id
            if _REQUEST_ID_RE.fullmatch(request_id)
            else resolve_request_id(None)
        ),
        "method": _bounded_log_text(method, _MAX_LOG_METHOD),
        "path": _bounded_log_text(safe_path, _MAX_LOG_PATH),
        "status": status_value,
        "response_bytes": response_size,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "occurred_at": occurred_at,
    }


def write_access_log(
    event: Mapping[str, Any],
    *,
    stream: TextIO | None = None,
) -> None:
    """Write one compact JSON event to stderr or an injected test stream."""
    target = sys.stderr if stream is None else stream
    target.write(
        json.dumps(
            dict(event),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    target.flush()


ADMITTED = "admitted"
OVERLOADED = "overloaded"
DRAINING = "draining"


def validate_request_timeout(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not (
            MIN_REQUEST_TIMEOUT_SECONDS
            <= float(value)
            <= MAX_REQUEST_TIMEOUT_SECONDS
        )
    ):
        raise ValueError(
            "request timeout must be between "
            f"{MIN_REQUEST_TIMEOUT_SECONDS} and "
            f"{MAX_REQUEST_TIMEOUT_SECONDS} seconds"
        )
    return float(value)


def validate_max_sse_clients(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not (1 <= value <= MAX_SSE_CLIENTS_CEILING)
    ):
        raise ValueError(
            "max SSE clients must be an integer between 1 and "
            f"{MAX_SSE_CLIENTS_CEILING}"
        )
    return value


def validate_max_concurrent_requests(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not (1 <= value <= MAX_CONCURRENT_REQUESTS_CEILING)
    ):
        raise ValueError(
            "max concurrent requests must be an integer between 1 and "
            f"{MAX_CONCURRENT_REQUESTS_CEILING}"
        )
    return value


class RequestLimiter:
    """Thread-safe concurrency cap with a drain switch (ADR-0022).

    ``admit()`` never blocks: it returns ``ADMITTED``, ``OVERLOADED`` (the cap
    is reached) or ``DRAINING``. Only an ``ADMITTED`` caller may ``release()``.
    An unbounded wait queue would be an unbounded memory and latency
    commitment, so saturation is rejected, not queued.
    """

    def __init__(self, max_concurrent: int) -> None:
        self._max = validate_max_concurrent_requests(max_concurrent)
        self._condition = threading.Condition()
        self._in_flight = 0
        self._draining = False

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def in_flight(self) -> int:
        with self._condition:
            return self._in_flight

    @property
    def draining(self) -> bool:
        with self._condition:
            return self._draining

    def admit(self) -> str:
        with self._condition:
            if self._draining:
                return DRAINING
            if self._in_flight >= self._max:
                return OVERLOADED
            self._in_flight += 1
            return ADMITTED

    def release(self) -> None:
        with self._condition:
            if self._in_flight <= 0:
                raise RuntimeError("release() without a matching admit()")
            self._in_flight -= 1
            if self._in_flight == 0:
                self._condition.notify_all()

    def begin_drain(self) -> None:
        with self._condition:
            self._draining = True

    def wait_idle(self, timeout: float) -> bool:
        """Wait until no request is in flight; False if ``timeout`` elapses."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._in_flight > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True


def limits_document(
    *,
    request_timeout_seconds: float,
    max_concurrent_requests: int,
    max_request_body_bytes: int,
    retry_after_seconds: int = DEFAULT_RETRY_AFTER_SECONDS,
    drain_timeout_seconds: float = DEFAULT_DRAIN_TIMEOUT_SECONDS,
    max_sse_clients: int = DEFAULT_MAX_SSE_CLIENTS,
    sse_heartbeat_seconds: float = SSE_HEARTBEAT_SECONDS,
    sse_max_stream_seconds: float = SSE_MAX_STREAM_SECONDS,
) -> dict[str, Any]:
    """The limits actually in force, published as ``operations.limits``.

    Every value is either a configured limit or a measured stdlib bound pinned
    by tests (ADR-0022). Nothing here is aspirational.
    """
    return {
        "request_timeout_seconds": float(request_timeout_seconds),
        "max_concurrent_requests": int(max_concurrent_requests),
        "retry_after_seconds": int(retry_after_seconds),
        "drain_timeout_seconds": float(drain_timeout_seconds),
        "max_request_line_bytes": MAX_REQUEST_LINE_BYTES,
        "max_header_line_bytes": MAX_HEADER_LINE_BYTES,
        "max_header_count": MAX_HEADER_COUNT,
        "max_request_body_bytes": int(max_request_body_bytes),
        "overload_status": 503,
        "connection_policy": "close_after_response",
        "per_client_rate_limit": "not_implemented",
        "max_sse_clients": int(max_sse_clients),
        "sse_heartbeat_seconds": float(sse_heartbeat_seconds),
        "sse_max_stream_seconds": float(sse_max_stream_seconds),
    }
