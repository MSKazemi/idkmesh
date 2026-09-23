"""Stable connector error envelope and redaction boundary.

This module implements the error vocabulary documented by Connector Control API
v0.1. It is deliberately stdlib-only and performs no provider I/O.

The boundary has two jobs:

* normalize connector/control-plane failures into stable machine-readable codes;
* keep common credential/header fields out of error details before those details
  can reach logs, CLI output, API responses, or persisted run metadata.

Provider adapters may add context in details but must not store raw response
bodies, prompts, credentials, or authorization headers there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping


ERROR_CODES = frozenset(
    {
        "configuration_error",
        "authentication_error",
        "authorization_error",
        "rate_limited",
        "quota_exhausted",
        "provider_unavailable",
        "source_not_connected",
        "sandbox_failure",
        "agent_failed",
        "timeout",
        "cancelled",
        "result_normalization_error",
        "policy_denied",
        "verification_failed",
        "conflict",
        "not_found",
    }
)

# Retryability is intentionally conservative. A caller may override it when a
# provider gives stronger evidence (for example an explicit Retry-After).
_DEFAULT_RETRYABLE = {
    "configuration_error": False,
    "authentication_error": False,
    "authorization_error": False,
    "rate_limited": True,
    "quota_exhausted": False,
    "provider_unavailable": True,
    "source_not_connected": False,
    "sandbox_failure": False,
    "agent_failed": False,
    "timeout": True,
    "cancelled": False,
    "result_normalization_error": False,
    "policy_denied": False,
    "verification_failed": False,
    "conflict": False,
    "not_found": False,
}

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "authorization",
        "bearer_token",
        "client_secret",
        "cookie",
        "credentials",
        "password",
        "proxy_authorization",
        "secret",
        "set_cookie",
        "token",
        "x_api_key",
    }
)

_REDACTED = "[REDACTED]"
_MAX_DETAIL_DEPTH = 8


def _normalized_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _sanitize_detail(value: Any, *, depth: int = 0) -> Any:
    """Return a JSON-safe, redacted copy of one detail value.

    Error details are observability metadata, not a transport for arbitrary
    provider payloads. Unsupported values fail closed instead of relying on
    default stringification because stringification can disclose secrets.
    """

    if depth > _MAX_DETAIL_DEPTH:
        raise ValueError("error details exceed maximum nesting depth")

    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            lowered = value.lstrip().lower()
            if lowered.startswith(("bearer ", "basic ", "token ", "api-key ")):
                return _REDACTED
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("error details must not contain non-finite numbers")
        return value

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("error detail object keys must be non-empty strings")
            if _normalized_key(key) in _SENSITIVE_KEYS:
                sanitized[key] = _REDACTED
            else:
                sanitized[key] = _sanitize_detail(child, depth=depth + 1)
        return sanitized

    if isinstance(value, (list, tuple)):
        return [_sanitize_detail(item, depth=depth + 1) for item in value]

    raise ValueError(
        "error details must contain only JSON-compatible scalar, object, or array values"
    )


def sanitize_error_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a defensive, JSON-safe copy suitable for an error envelope."""

    if details is None:
        return {}
    if not isinstance(details, Mapping):
        raise ValueError("error details must be an object")
    sanitized = _sanitize_detail(details)
    assert isinstance(sanitized, dict)
    return sanitized


@dataclass(frozen=True)
class ConnectorError(RuntimeError):
    """Normalized connector/control-plane failure.

    The human-readable exception string intentionally omits details so an
    accidental print(exc) does not disclose provider metadata.
    """

    code: str
    message: str
    retryable: bool | None = None
    connection_id: str | None = None
    run_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            raise ValueError(f"unknown connector error code: {self.code}")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("connector error message must be a non-empty string")
        if self.retryable is not None and type(self.retryable) is not bool:
            raise ValueError("retryable must be a boolean or None")
        for name in ("connection_id", "run_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")

        sanitized = sanitize_error_details(self.details)
        object.__setattr__(self, "details", sanitized)

        # RuntimeError does not automatically receive dataclass fields as args.
        RuntimeError.__init__(self, self.message)

    @property
    def is_retryable(self) -> bool:
        if self.retryable is not None:
            return self.retryable
        return _DEFAULT_RETRYABLE[self.code]

    def to_envelope(self) -> dict[str, Any]:
        """Return the Connector Control API v0.1 error envelope."""

        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.is_retryable,
        }
        if self.connection_id is not None:
            payload["connection_id"] = self.connection_id
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.details:
            payload["details"] = dict(self.details)
        return {"error": payload}


def connector_error(
    code: str,
    message: str,
    *,
    retryable: bool | None = None,
    connection_id: str | None = None,
    run_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> ConnectorError:
    """Construct one normalized connector error."""

    return ConnectorError(
        code=code,
        message=message,
        retryable=retryable,
        connection_id=connection_id,
        run_id=run_id,
        details=details or {},
    )
