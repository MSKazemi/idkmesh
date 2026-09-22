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
import secrets
import sys
from typing import Any, Mapping, TextIO

REQUEST_ID_HEADER = "X-Request-ID"
SERVICE_HEADER = "X-IDKMesh-Service"
SERVICE_VERSION_HEADER = "X-IDKMesh-Service-Version"
READ_ONLY_HEADER = "X-IDKMesh-Read-Only"
ACCESS_LOG_ENV = "IDKMESH_HTTP_ACCESS_LOG"

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


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
        REQUEST_ID_HEADER: request_id,
        SERVICE_HEADER: service,
        SERVICE_VERSION_HEADER: service_version,
        READ_ONLY_HEADER: "true" if read_only else "false",
    }
    if api_version is not None:
        headers["X-IDKMesh-API-Version"] = api_version
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
        "service": service,
        "service_version": service_version,
        "mode": mode,
    }
    if api_version is not None:
        result["api_version"] = api_version
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

    Callers must provide a URL path only, with query strings already removed.
    Headers and request/response bodies are intentionally not accepted.
    """
    if occurred_at is None:
        occurred_at = (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    return {
        "event": "http_request",
        "service": service,
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": int(status),
        "response_bytes": int(response_bytes),
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
