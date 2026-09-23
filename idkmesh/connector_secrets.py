"""Environment secret-reference and redaction boundary for C1-E (#615).

Tracked connector configuration may name a secret reference such as
"env:JULES_API_KEY", but raw secret values must not enter repository config,
issue text, WorkUnits, logs, exceptions, reprs, or persisted connector metadata.

This module keeps three operations separate:

1. parse a reference;
2. check whether the referenced environment variable exists;
3. materialize a redacted SecretValue only after an explicit admission grant.

The module is stdlib-only and performs no provider or GitHub API calls.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import os
import re
from typing import Any

from idkmesh.connector_profiles import ConnectorConfig


_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "authorization",
    "bearer_token",
    "client_secret",
    "credentials",
    "password",
    "secret",
    "token",
}
_REDACTED = "<redacted>"
_GRANT_SENTINEL = object()


class SecretReferenceError(ValueError):
    """Safe secret-boundary error with a stable code and no raw secret value."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class EnvSecretRef:
    """Parsed reference to one environment-variable secret."""

    name: str

    @property
    def canonical(self) -> str:
        return f"env:{self.name}"


class SecretValue:
    """Opaque secret wrapper whose string/repr forms are always redacted."""

    __slots__ = ("__value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or value == "":
            raise SecretReferenceError(
                "invalid_secret_value",
                "materialized secret must be a non-empty string",
            )
        self.__value = value

    def reveal_for_provider(self) -> str:
        """Return the raw value only at the final provider-call boundary."""

        return self.__value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    def __str__(self) -> str:
        return _REDACTED


@dataclass(frozen=True, init=False)
class SecretAccessGrant:
    """Admission-bound capability required before secret materialization."""

    connection_id: str
    secret_ref: str
    admission_id: str

    def __init__(
        self,
        connection_id: str,
        secret_ref: str,
        admission_id: str,
        *,
        _sentinel: object,
    ) -> None:
        if _sentinel is not _GRANT_SENTINEL:
            raise SecretReferenceError(
                "invalid_secret_grant",
                "secret access grants must be minted by the admission boundary",
            )
        object.__setattr__(self, "connection_id", connection_id)
        object.__setattr__(self, "secret_ref", secret_ref)
        object.__setattr__(self, "admission_id", admission_id)


def parse_secret_ref(value: object) -> EnvSecretRef:
    """Parse the only supported first-version secret-reference scheme."""

    if not isinstance(value, str) or value == "":
        raise SecretReferenceError(
            "inline_secret_forbidden",
            "secret configuration must use an env:NAME reference",
        )

    if ":" not in value:
        raise SecretReferenceError(
            "inline_secret_forbidden",
            "secret configuration must use an env:NAME reference",
        )

    scheme, name = value.split(":", 1)
    if scheme != "env":
        raise SecretReferenceError(
            "unsupported_secret_scheme",
            "only env:NAME secret references are supported",
        )
    if _ENV_NAME.fullmatch(name) is None:
        raise SecretReferenceError(
            "invalid_env_secret_ref",
            "environment variable name is invalid",
        )
    return EnvSecretRef(name=name)


def config_secret_ref(config: ConnectorConfig) -> EnvSecretRef | None:
    """Read the secret reference only from trusted connector configuration."""

    if config.secret_ref is None:
        return None
    return parse_secret_ref(config.secret_ref)


def secret_is_available(
    ref: EnvSecretRef,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Check presence without returning/materializing the secret value."""

    source = os.environ if environ is None else environ
    return ref.name in source


def config_secret_is_available(
    config: ConnectorConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Check configured secret presence; no configured secret means available."""

    ref = config_secret_ref(config)
    if ref is None:
        return True
    return secret_is_available(ref, environ=environ)


def mint_secret_access_grant(
    config: ConnectorConfig,
    *,
    admitted: bool,
    admission_id: str,
) -> SecretAccessGrant:
    """Mint a grant only after higher-level run admission has succeeded."""

    if admitted is not True:
        raise SecretReferenceError(
            "secret_access_not_admitted",
            "secret materialization requires an admitted run",
        )
    if not isinstance(admission_id, str) or not admission_id:
        raise SecretReferenceError(
            "invalid_admission_id",
            "admission_id must be a non-empty string",
        )

    ref = config_secret_ref(config)
    if ref is None:
        raise SecretReferenceError(
            "secret_not_configured",
            "connector has no configured secret reference",
        )

    return SecretAccessGrant(
        config.id,
        ref.canonical,
        admission_id,
        _sentinel=_GRANT_SENTINEL,
    )


def materialize_config_secret(
    config: ConnectorConfig,
    grant: SecretAccessGrant,
    *,
    environ: Mapping[str, str] | None = None,
) -> SecretValue:
    """Materialize the configured secret after validating its admission grant."""

    ref = config_secret_ref(config)
    if ref is None:
        raise SecretReferenceError(
            "secret_not_configured",
            "connector has no configured secret reference",
        )

    if (
        grant.connection_id != config.id
        or grant.secret_ref != ref.canonical
        or not grant.admission_id
    ):
        raise SecretReferenceError(
            "secret_grant_mismatch",
            "secret access grant does not match connector configuration",
        )

    source = os.environ if environ is None else environ
    if ref.name not in source:
        raise SecretReferenceError(
            "missing_secret",
            "configured environment secret is unavailable",
        )

    value = source[ref.name]
    if not isinstance(value, str) or value == "":
        raise SecretReferenceError(
            "missing_secret",
            "configured environment secret is unavailable",
        )
    return SecretValue(value)


def redact_text(
    text: object,
    *,
    known_secrets: Iterable[str | SecretValue] = (),
) -> str:
    """Redact known secret values from free-form text.

    This helper is a final logging/error boundary. Callers should still prefer
    structured symbolic errors over carrying raw provider exception strings.
    """

    rendered = str(text)
    for secret in known_secrets:
        raw = (
            secret.reveal_for_provider()
            if isinstance(secret, SecretValue)
            else secret
        )
        if isinstance(raw, str) and raw:
            rendered = rendered.replace(raw, _REDACTED)
    return rendered


def redact_metadata(
    value: Any,
    *,
    known_secrets: Iterable[str | SecretValue] = (),
) -> Any:
    """Return a recursively log-safe copy of metadata."""

    secret_values = tuple(known_secrets)

    if isinstance(value, SecretValue):
        return _REDACTED

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _SENSITIVE_KEYS:
                result[str(key)] = _REDACTED
            else:
                result[str(key)] = redact_metadata(
                    child,
                    known_secrets=secret_values,
                )
        return result

    if isinstance(value, list):
        return [
            redact_metadata(item, known_secrets=secret_values)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            redact_metadata(item, known_secrets=secret_values)
            for item in value
        )

    if isinstance(value, str):
        return redact_text(value, known_secrets=secret_values)

    return value
