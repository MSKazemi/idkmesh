"""Versioned, fail-closed connector profile loading.

This is the C1-B implementation slice from issue #611. It deliberately stops
at configuration validation and deterministic normalization:

- no live provider/network calls;
- no driver registry lookup;
- no secret materialization;
- no dispatch or repository authority.

A stored connection profile is configuration, not evidence that the connector
is healthy, capable, authorized, or currently available. Routing-facing
profiles therefore remain fail-closed until later registry/probe slices enrich
them with observed capabilities and health.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from idkmesh.connector_routing import ConnectorProfile, RISK_ORDER


PROFILE_API_VERSION = "idkmesh.io/v1alpha1"

_ALLOWED_TOP_LEVEL_FIELDS = {
    "api_version",
    "id",
    "kind",
    "driver",
    "enabled",
    "auth",
    "settings",
    "policy",
}
_ALLOWED_AUTH_FIELDS = {"secret_ref"}
_ALLOWED_POLICY_FIELDS = {
    "task_classes",
    "allowed_risk",
    "max_concurrency",
    "external_processing",
    "project_spend_usd_max",
    "network",
}
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
_SECRET_REF_RE = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")

# Exact key matches only. Names such as "max_tokens" are not rejected, while
# credential-shaped fields such as "api_key" or "access_token" are.
_RAW_SECRET_KEYS = {
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "secret_value",
    "token",
    "access_token",
}


class ConnectorProfileError(ValueError):
    """A user-fixable connector profile validation error."""


@dataclass(frozen=True)
class ConnectionConfig:
    """Validated configuration for one connector.

    settings remains driver-specific opaque configuration for later
    registry/driver slices. policy contains only the common policy fields
    understood by this first control-plane version.

    secret_ref is retained as a reference string only. This module never
    checks or materializes its target value.
    """

    api_version: str
    connection_id: str
    kind: str
    driver: str
    enabled: bool
    secret_ref: str | None
    settings: Mapping[str, Any]
    policy: Mapping[str, Any]

    def to_routing_profile(self) -> ConnectorProfile:
        """Return a fail-closed routing-facing profile.

        Stored configuration is not a successful probe. Until C1-C/C1-D add
        driver capability declarations and normalized probes, enabled
        connections are marked unavailable with no observed capability tiers
        and no available capacity.

        Policy fields that can be represented safely by ConnectorProfile are
        carried forward. project_spend_usd_max is a ceiling, not an observed
        connector cost, so it is intentionally not copied into
        project_cost_usd.
        """

        task_classes = frozenset(self.policy.get("task_classes", ()))
        max_risk = _max_risk_from_policy(self.policy)
        external_processing = self.policy.get("external_processing", False)
        secret_required = self.secret_ref is not None

        return ConnectorProfile(
            connection_id=self.connection_id,
            kind=self.kind,
            driver=self.driver,
            enabled=self.enabled,
            health="disabled" if not self.enabled else "unavailable",
            capability_tiers=frozenset(),
            task_classes=task_classes,
            tools=frozenset(),
            max_risk=max_risk,
            external_processing=external_processing,
            project_cost_usd=0.0,
            secret_required=secret_required,
            secret_available=not secret_required,
            capacity_available=False,
        )


def _fail(source: str, message: str) -> ConnectorProfileError:
    return ConnectorProfileError(f"{source}: {message}")


def _expect_object(value: Any, *, source: str, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(source, f"{field} must be a JSON object")
    for key in value:
        if not isinstance(key, str):
            raise _fail(source, f"{field} contains a non-string key")
    return value


def _validate_identifier(
    value: Any, *, source: str, field: str, allow_slash: bool = False
) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(source, f"{field} must be a non-empty string")
    if allow_slash:
        parts = value.split("/")
        if any(not part or not _IDENTIFIER_RE.fullmatch(part) for part in parts):
            raise _fail(source, f"{field} has an invalid identifier shape")
        return value
    if not _IDENTIFIER_RE.fullmatch(value):
        raise _fail(source, f"{field} has an invalid identifier shape")
    return value


def _validate_string_list(
    value: Any, *, source: str, field: str
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _fail(source, f"{field} must be a JSON array")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise _fail(
                source, f"{field}[{index}] must be a non-empty string"
            )
        if item in seen:
            raise _fail(source, f"{field} contains duplicate value {item!r}")
        seen.add(item)
        result.append(item)
    return tuple(result)


def _validate_number(
    value: Any, *, source: str, field: str, minimum: float = 0.0
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(source, f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise _fail(source, f"{field} must be finite and >= {minimum:g}")
    return number


def _scan_for_raw_secret_fields(
    value: Any, *, source: str, path: str = "$"
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise _fail(source, f"{path} contains a non-string key")
            normalized = key.strip().lower().replace("-", "_")
            if normalized in _RAW_SECRET_KEYS:
                raise _fail(
                    source,
                    f"{path}.{key} looks like an inline credential field; "
                    "use auth.secret_ref instead",
                )
            _scan_for_raw_secret_fields(
                child, source=source, path=f"{path}.{key}"
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_for_raw_secret_fields(
                child, source=source, path=f"{path}[{index}]"
            )


def _validate_auth(
    raw: Any, *, source: str
) -> tuple[str | None, dict[str, Any]]:
    if raw is None:
        return None, {}
    auth = _expect_object(raw, source=source, field="auth")
    unknown = sorted(set(auth) - _ALLOWED_AUTH_FIELDS)
    if unknown:
        raise _fail(
            source,
            "auth contains unsupported field(s): " + ", ".join(unknown),
        )
    if not auth:
        return None, {}

    secret_ref = auth.get("secret_ref")
    if not isinstance(secret_ref, str) or not secret_ref:
        raise _fail(source, "auth.secret_ref must be a non-empty string")
    if not _SECRET_REF_RE.fullmatch(secret_ref):
        raise _fail(
            source,
            "auth.secret_ref must use an explicit scheme such as env:NAME",
        )
    return secret_ref, {"secret_ref": secret_ref}


def _validate_policy(raw: Any, *, source: str) -> dict[str, Any]:
    if raw is None:
        return {}
    policy = _expect_object(raw, source=source, field="policy")
    unknown = sorted(set(policy) - _ALLOWED_POLICY_FIELDS)
    if unknown:
        raise _fail(
            source,
            "policy contains unsupported field(s): " + ", ".join(unknown),
        )

    result: dict[str, Any] = {}

    if "task_classes" in policy:
        result["task_classes"] = _validate_string_list(
            policy["task_classes"], source=source, field="policy.task_classes"
        )

    if "allowed_risk" in policy:
        risks = _validate_string_list(
            policy["allowed_risk"], source=source, field="policy.allowed_risk"
        )
        unknown_risks = sorted(set(risks) - set(RISK_ORDER))
        if unknown_risks:
            raise _fail(
                source,
                "policy.allowed_risk contains unknown risk value(s): "
                + ", ".join(unknown_risks),
            )
        if not risks:
            raise _fail(source, "policy.allowed_risk must not be empty")

        highest = max(risks, key=RISK_ORDER.__getitem__)
        expected = tuple(
            risk
            for risk, rank in sorted(
                RISK_ORDER.items(), key=lambda item: item[1]
            )
            if rank <= RISK_ORDER[highest]
        )
        if set(risks) != set(expected):
            raise _fail(
                source,
                "policy.allowed_risk must be cumulative from low through "
                f"{highest!r} so max-risk normalization cannot broaden policy",
            )
        result["allowed_risk"] = expected

    if "max_concurrency" in policy:
        value = policy["max_concurrency"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise _fail(
                source, "policy.max_concurrency must be an integer >= 1"
            )
        result["max_concurrency"] = value

    if "external_processing" in policy:
        value = policy["external_processing"]
        if type(value) is not bool:
            raise _fail(
                source, "policy.external_processing must be a boolean"
            )
        result["external_processing"] = value

    if "project_spend_usd_max" in policy:
        result["project_spend_usd_max"] = _validate_number(
            policy["project_spend_usd_max"],
            source=source,
            field="policy.project_spend_usd_max",
        )

    if "network" in policy:
        value = policy["network"]
        if not isinstance(value, str) or not value:
            raise _fail(source, "policy.network must be a non-empty string")
        result["network"] = value

    return result


def _max_risk_from_policy(policy: Mapping[str, Any]) -> str:
    risks = policy.get("allowed_risk")
    if not risks:
        return "low"
    return max(risks, key=RISK_ORDER.__getitem__)


def parse_connector_profile(
    raw: Any, *, source: str = "<memory>"
) -> ConnectionConfig:
    """Validate one decoded JSON connector object."""

    profile = _expect_object(raw, source=source, field="profile")
    unknown = sorted(set(profile) - _ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        raise _fail(
            source,
            "profile contains unsupported top-level field(s): "
            + ", ".join(unknown),
        )

    missing = [
        field
        for field in ("api_version", "id", "kind", "driver", "enabled")
        if field not in profile
    ]
    if missing:
        raise _fail(
            source, "profile is missing required field(s): " + ", ".join(missing)
        )

    if profile["api_version"] != PROFILE_API_VERSION:
        raise _fail(
            source,
            "unsupported api_version "
            f"{profile['api_version']!r}; expected {PROFILE_API_VERSION!r}",
        )

    connection_id = _validate_identifier(
        profile["id"], source=source, field="id"
    )
    kind = profile["kind"]
    if kind not in {"scm", "agent", "model", "execution"}:
        raise _fail(source, f"kind has unsupported value {kind!r}")

    driver = _validate_identifier(
        profile["driver"], source=source, field="driver", allow_slash=True
    )

    enabled = profile["enabled"]
    if type(enabled) is not bool:
        raise _fail(source, "enabled must be a boolean")

    secret_ref, normalized_auth = _validate_auth(
        profile.get("auth"), source=source
    )
    settings = _expect_object(
        profile.get("settings", {}), source=source, field="settings"
    )
    policy = _validate_policy(profile.get("policy"), source=source)

    # Scan all driver-specific/settings content too. C1-E will own concrete
    # secret resolution; C1-B simply refuses credential-shaped inline fields.
    _scan_for_raw_secret_fields(settings, source=source, path="$.settings")
    _scan_for_raw_secret_fields(policy, source=source, path="$.policy")
    _scan_for_raw_secret_fields(
        normalized_auth, source=source, path="$.auth"
    )

    return ConnectionConfig(
        api_version=PROFILE_API_VERSION,
        connection_id=connection_id,
        kind=kind,
        driver=driver,
        enabled=enabled,
        secret_ref=secret_ref,
        settings=deepcopy(settings),
        policy=deepcopy(policy),
    )


def load_connector_profile(path: str | Path) -> ConnectionConfig:
    """Load and validate one connector JSON document from path."""

    source_path = Path(path)
    source = str(source_path)
    try:
        text = source_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        reason = exc.strerror or type(exc).__name__
        raise _fail(source, f"cannot read profile: {reason}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(
            source,
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}",
        ) from exc

    return parse_connector_profile(raw, source=source)


def load_connector_profiles(
    paths: Iterable[str | Path],
) -> tuple[ConnectionConfig, ...]:
    """Load multiple connection documents and reject duplicate IDs."""

    loaded: list[ConnectionConfig] = []
    seen: dict[str, str] = {}

    for path in paths:
        profile = load_connector_profile(path)
        source = str(Path(path))
        previous = seen.get(profile.connection_id)
        if previous is not None:
            raise _fail(
                source,
                f"duplicate connection id {profile.connection_id!r}; "
                f"already defined by {previous}",
            )
        seen[profile.connection_id] = source
        loaded.append(profile)

    return tuple(loaded)
