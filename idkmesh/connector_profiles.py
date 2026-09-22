"""Versioned connector profile loading and validation for C1-B (#611).

This module is stdlib-only and intentionally does not perform provider calls,
driver lookup, probes, or secret materialization. It converts trusted
repository/local JSON configuration into normalized connector metadata and the
existing routing-facing ``ConnectorProfile`` shape.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any

from idkmesh.connector_routing import (
    CONNECTOR_KINDS,
    HEALTH_STATES,
    RISK_ORDER,
    TIER_ORDER,
    ConnectorProfile,
)

SUPPORTED_API_VERSION = "idkmesh.io/v1alpha1"
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_TOP = {
    "api_version", "id", "kind", "driver", "enabled",
    "auth", "settings", "capabilities", "policy", "independence",
}
_AUTH = {"secret_ref"}
_CAP = {"tiers", "task_classes", "tools", "candidate_types", "max_risk"}
_POLICY = {
    "task_classes", "allowed_risk", "external_processing",
    "project_spend_usd_max", "max_concurrency",
}
_INDEPENDENCE = {"provider_family", "agent_family", "execution_family"}
_RAW_SECRET_KEYS = {
    "api_key", "apikey", "access_token", "auth_token", "authorization",
    "bearer_token", "client_secret", "credentials", "password", "secret", "token",
}


class ConnectorProfileError(ValueError):
    """Validation error with a stable machine-readable ``code`` and ``path``."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _error(code: str, path: str, message: str) -> ConnectorProfileError:
    return ConnectorProfileError(code, path, message)


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error("invalid_type", path, "must be an object")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _error("invalid_type", path, "must be a string")
    if not allow_empty and not value.strip():
        raise _error("invalid_value", path, "must not be empty")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _error("invalid_type", path, "must be a boolean")
    return value


def _money(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error("invalid_type", path, "must be a finite number >= 0")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise _error("invalid_value", path, "must be a finite number >= 0")
    return number


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _error("invalid_value", path, "must be an integer >= 1")
    return value


def _string_set(value: Any, path: str) -> frozenset[str]:
    if not isinstance(value, list):
        raise _error("invalid_type", path, "must be an array of strings")
    items = [_string(item, f"{path}[{i}]") for i, item in enumerate(value)]
    if len(items) != len(set(items)):
        raise _error("duplicate_value", path, "must not contain duplicates")
    return frozenset(items)


def _fields(mapping: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if not unknown:
        return
    key = unknown[0]
    if key.lower() in _RAW_SECRET_KEYS:
        raise _error(
            "inline_secret_forbidden",
            f"{path}.{key}",
            f"inline credential field '{key}' is forbidden; use auth.secret_ref",
        )
    raise _error("unknown_field", f"{path}.{key}", f"unknown field '{key}'")


def _scan_settings(value: Any, path: str) -> None:
    """Reject credential-shaped fields in arbitrary provider settings."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            normalized = str(key).lower()
            if normalized in _RAW_SECRET_KEYS:
                raise _error(
                    "inline_secret_forbidden",
                    child_path,
                    f"inline credential field '{key}' is forbidden; use auth.secret_ref",
                )
            if normalized == "secret_ref":
                raise _error(
                    "secret_ref_outside_auth",
                    child_path,
                    "secret_ref is only allowed under auth.secret_ref",
                )
            _scan_settings(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_settings(child, f"{path}[{index}]")


def _identifier(value: Any, path: str) -> str:
    text = _string(value, path)
    if _ID_RE.fullmatch(text) is None:
        raise _error("invalid_identifier", path, "contains unsupported characters")
    return text


def _risk(cap: Mapping[str, Any], policy: Mapping[str, Any], path: str) -> str:
    cap_risk = None
    if "max_risk" in cap:
        cap_risk = _string(cap["max_risk"], f"{path}.capabilities.max_risk")
        if cap_risk not in RISK_ORDER:
            raise _error("invalid_risk", f"{path}.capabilities.max_risk", cap_risk)

    policy_risk = None
    if "allowed_risk" in policy:
        allowed = _string_set(policy["allowed_risk"], f"{path}.policy.allowed_risk")
        if not allowed or not allowed <= set(RISK_ORDER):
            raise _error("invalid_risk", f"{path}.policy.allowed_risk", "unknown/empty risk set")
        max_rank = max(RISK_ORDER[item] for item in allowed)
        expected = {name for name, rank in RISK_ORDER.items() if rank <= max_rank}
        if set(allowed) != expected:
            raise _error(
                "non_monotonic_risk_policy",
                f"{path}.policy.allowed_risk",
                "must form a ceiling from low through the maximum",
            )
        policy_risk = max(allowed, key=RISK_ORDER.__getitem__)

    if cap_risk and policy_risk and cap_risk != policy_risk:
        raise _error("conflicting_field", path, "max_risk and allowed_risk disagree")
    return cap_risk or policy_risk or "low"


def _task_classes(
    cap: Mapping[str, Any], policy: Mapping[str, Any], path: str
) -> frozenset[str]:
    left = (
        _string_set(cap["task_classes"], f"{path}.capabilities.task_classes")
        if "task_classes" in cap else None
    )
    right = (
        _string_set(policy["task_classes"], f"{path}.policy.task_classes")
        if "task_classes" in policy else None
    )
    if left is not None and right is not None and left != right:
        raise _error("conflicting_field", path, "task_classes declarations disagree")
    return left or right or frozenset()


@dataclass(frozen=True)
class ConnectorConfig:
    """Validated static connection configuration; contains no credential value."""

    api_version: str
    id: str
    kind: str
    driver: str
    enabled: bool
    secret_ref: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict, repr=False)
    capability_tiers: frozenset[str] = field(default_factory=frozenset)
    task_classes: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    candidate_types: frozenset[str] = field(default_factory=frozenset)
    max_risk: str = "low"
    external_processing: bool = False
    project_spend_usd_max: float = 0.0
    max_concurrency: int = 1
    provider_family: str = ""
    agent_family: str = ""
    execution_family: str = ""

    @property
    def connection_id(self) -> str:
        return self.id

    def to_routing_profile(
        self,
        *,
        project_cost_usd: float,
        health: str | None = None,
        secret_available: bool | None = None,
        capacity_available: bool = False,
    ) -> ConnectorProfile:
        """Combine static config with runtime facts for the routing kernel.

        ``project_cost_usd`` is required because a configured spend ceiling is
        not evidence of actual provider cost. Capacity defaults to false so an
        unprobed connector cannot accidentally become dispatchable.
        """

        cost = _money(project_cost_usd, f"connector[{self.id}].project_cost_usd")
        if cost > self.project_spend_usd_max:
            raise _error(
                "connector_spend_policy_exceeded",
                f"connector[{self.id}].project_cost_usd",
                "runtime cost exceeds connector profile ceiling",
            )

        actual_health = health or ("disabled" if not self.enabled else "degraded")
        if actual_health not in HEALTH_STATES:
            raise _error("invalid_health", f"connector[{self.id}].health", actual_health)

        secret_required = self.secret_ref is not None
        if secret_available is None:
            secret_available = not secret_required
        if type(secret_available) is not bool or type(capacity_available) is not bool:
            raise _error("invalid_type", f"connector[{self.id}]", "runtime flags must be booleans")

        return ConnectorProfile(
            connection_id=self.id,
            kind=self.kind,
            driver=self.driver,
            enabled=self.enabled,
            health=actual_health,
            capability_tiers=self.capability_tiers,
            task_classes=self.task_classes,
            tools=self.tools,
            max_risk=self.max_risk,
            external_processing=self.external_processing,
            project_cost_usd=cost,
            secret_required=secret_required,
            secret_available=secret_available,
            capacity_available=capacity_available,
            provider_family=self.provider_family,
            agent_family=self.agent_family,
            execution_family=self.execution_family,
        )


def _parse_connection(raw: Any, path: str) -> ConnectorConfig:
    item = _object(raw, path)
    _fields(item, _TOP, path)

    missing = [name for name in ("api_version", "id", "kind", "driver", "enabled") if name not in item]
    if missing:
        raise _error("missing_field", path, "missing: " + ", ".join(missing))

    version = _string(item["api_version"], f"{path}.api_version")
    if version != SUPPORTED_API_VERSION:
        raise _error("unsupported_api_version", f"{path}.api_version", version)

    connection_id = _identifier(item["id"], f"{path}.id")
    kind = _string(item["kind"], f"{path}.kind")
    if kind not in CONNECTOR_KINDS:
        raise _error("unknown_connector_kind", f"{path}.kind", kind)
    driver = _identifier(item["driver"], f"{path}.driver")
    enabled = _boolean(item["enabled"], f"{path}.enabled")

    auth = _object(item.get("auth", {}), f"{path}.auth")
    _fields(auth, _AUTH, f"{path}.auth")
    secret_ref = (
        _string(auth["secret_ref"], f"{path}.auth.secret_ref")
        if "secret_ref" in auth else None
    )

    settings = _object(item.get("settings", {}), f"{path}.settings")
    _scan_settings(settings, f"{path}.settings")

    cap = _object(item.get("capabilities", {}), f"{path}.capabilities")
    policy = _object(item.get("policy", {}), f"{path}.policy")
    independence = _object(item.get("independence", {}), f"{path}.independence")
    _fields(cap, _CAP, f"{path}.capabilities")
    _fields(policy, _POLICY, f"{path}.policy")
    _fields(independence, _INDEPENDENCE, f"{path}.independence")

    tiers = _string_set(cap.get("tiers", []), f"{path}.capabilities.tiers")
    unknown_tiers = sorted(set(tiers) - set(TIER_ORDER))
    if unknown_tiers:
        raise _error(
            "invalid_capability_tier",
            f"{path}.capabilities.tiers",
            ", ".join(unknown_tiers),
        )

    external = (
        _boolean(policy["external_processing"], f"{path}.policy.external_processing")
        if "external_processing" in policy else False
    )
    spend = _money(
        policy.get("project_spend_usd_max", 0.0),
        f"{path}.policy.project_spend_usd_max",
    )
    concurrency = _positive_int(
        policy.get("max_concurrency", 1),
        f"{path}.policy.max_concurrency",
    )

    def family(name: str) -> str:
        return (
            _string(independence[name], f"{path}.independence.{name}", allow_empty=True)
            if name in independence else ""
        )

    return ConnectorConfig(
        api_version=version,
        id=connection_id,
        kind=kind,
        driver=driver,
        enabled=enabled,
        secret_ref=secret_ref,
        settings=dict(settings),
        capability_tiers=tiers,
        task_classes=_task_classes(cap, policy, path),
        tools=_string_set(cap.get("tools", []), f"{path}.capabilities.tools"),
        candidate_types=_string_set(
            cap.get("candidate_types", []), f"{path}.capabilities.candidate_types"
        ),
        max_risk=_risk(cap, policy, path),
        external_processing=external,
        project_spend_usd_max=spend,
        max_concurrency=concurrency,
        provider_family=family("provider_family"),
        agent_family=family("agent_family"),
        execution_family=family("execution_family"),
    )


def parse_connector_profile_document(data: Any) -> tuple[ConnectorConfig, ...]:
    """Validate one connection object or an array of versioned objects."""

    if isinstance(data, Mapping):
        raw_items, paths = [data], ["$"]
    elif isinstance(data, list):
        raw_items = data
        paths = [f"$[{index}]" for index in range(len(data))]
    else:
        raise _error(
            "invalid_document",
            "$",
            "must be a connection object or an array of connection objects",
        )

    configs = tuple(_parse_connection(raw, path) for raw, path in zip(raw_items, paths))
    duplicates = sorted(
        key for key, count in Counter(config.id for config in configs).items() if count > 1
    )
    if duplicates:
        raise _error("duplicate_connection_id", "$", ", ".join(duplicates))

    return tuple(sorted(configs, key=lambda config: config.id))


def load_connector_profile_document(path: str | Path) -> tuple[ConnectorConfig, ...]:
    """Load UTF-8 JSON from disk and validate it as connector configuration."""

    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _error("profile_read_error", str(source), exc.__class__.__name__) from exc
    except json.JSONDecodeError as exc:
        raise _error(
            "invalid_json",
            str(source),
            f"line {exc.lineno}, column {exc.colno}",
        ) from exc
    return parse_connector_profile_document(data)
