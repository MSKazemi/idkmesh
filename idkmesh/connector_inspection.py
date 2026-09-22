"""Read-only connector inspection helpers for C1-H (#618).

This module turns validated connector configuration plus the offline fake-driver
registry into probe, doctor, and route-explanation views. It performs no live
provider I/O, no secret materialization, no dispatch, and no repository
mutation.

The important safety rule is that routing capability comes from the registered
driver declaration/probe result, never from a profile claim alone.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from idkmesh.connector_probe import (
    ConnectorProbeResult,
    FakeProbeDriver,
    probe_connector,
)
from idkmesh.connector_profiles import ConnectorConfig
from idkmesh.connector_registry import (
    ConnectorRegistry,
    ConnectorRegistryError,
    DriverCapabilities,
    build_fake_registry,
)
from idkmesh.connector_routing import (
    RISK_ORDER,
    ConnectorProfile,
    RoutingDecision,
    resolve_routes,
)


_DECISION_FIELDS = {
    "required_capability_tier",
    "authority_mode",
    "risk_class",
    "task_classes",
    "required_tools",
    "allowed_connector_kinds",
    "external_processing_allowed",
    "project_spend_usd_max",
    "human_gate_satisfied",
    "prefer_zero_cost",
    "avoid_provider_families",
    "independent_reviewer_required",
}


class ConnectorInspectionError(ValueError):
    """Read-only inspection input/contract error with a stable code."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _error(code: str, path: str, message: str) -> ConnectorInspectionError:
    return ConnectorInspectionError(code, path, message)


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error("invalid_type", path, "must be a non-empty string")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _error("invalid_type", path, "must be a boolean")
    return value


def _string_set(value: Any, path: str) -> frozenset[str]:
    if not isinstance(value, list):
        raise _error("invalid_type", path, "must be an array of strings")
    items: list[str] = []
    for index, item in enumerate(value):
        items.append(_string(item, f"{path}[{index}]"))
    if len(items) != len(set(items)):
        raise _error("duplicate_value", path, "must not contain duplicates")
    return frozenset(items)


def _money(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error("invalid_type", path, "must be a finite number >= 0")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise _error("invalid_value", path, "must be a finite number >= 0")
    return number


def parse_routing_decision_document(data: Any) -> RoutingDecision:
    """Parse one strict JSON object into the canonical RoutingDecision."""

    if not isinstance(data, Mapping):
        raise _error("invalid_document", "$", "routing decision must be an object")

    unknown = sorted(set(data) - _DECISION_FIELDS)
    if unknown:
        raise _error(
            "unknown_field",
            f"$.{unknown[0]}",
            f"unknown routing-decision field {unknown[0]!r}",
        )

    missing = [
        name
        for name in ("required_capability_tier", "authority_mode")
        if name not in data
    ]
    if missing:
        raise _error("missing_field", "$", "missing: " + ", ".join(missing))

    kwargs: dict[str, Any] = {
        "required_capability_tier": _string(
            data["required_capability_tier"], "$.required_capability_tier"
        ),
        "authority_mode": _string(data["authority_mode"], "$.authority_mode"),
    }

    if "risk_class" in data:
        kwargs["risk_class"] = _string(data["risk_class"], "$.risk_class")
    if "task_classes" in data:
        kwargs["task_classes"] = _string_set(
            data["task_classes"], "$.task_classes"
        )
    if "required_tools" in data:
        kwargs["required_tools"] = _string_set(
            data["required_tools"], "$.required_tools"
        )
    if "allowed_connector_kinds" in data:
        kwargs["allowed_connector_kinds"] = _string_set(
            data["allowed_connector_kinds"], "$.allowed_connector_kinds"
        )
    if "external_processing_allowed" in data:
        kwargs["external_processing_allowed"] = _boolean(
            data["external_processing_allowed"],
            "$.external_processing_allowed",
        )
    if "project_spend_usd_max" in data:
        kwargs["project_spend_usd_max"] = _money(
            data["project_spend_usd_max"], "$.project_spend_usd_max"
        )
    if "human_gate_satisfied" in data:
        kwargs["human_gate_satisfied"] = _boolean(
            data["human_gate_satisfied"], "$.human_gate_satisfied"
        )
    if "prefer_zero_cost" in data:
        kwargs["prefer_zero_cost"] = _boolean(
            data["prefer_zero_cost"], "$.prefer_zero_cost"
        )
    if "avoid_provider_families" in data:
        kwargs["avoid_provider_families"] = _string_set(
            data["avoid_provider_families"], "$.avoid_provider_families"
        )
    if "independent_reviewer_required" in data:
        kwargs["independent_reviewer_required"] = _boolean(
            data["independent_reviewer_required"],
            "$.independent_reviewer_required",
        )

    try:
        return RoutingDecision(**kwargs)
    except ValueError as exc:
        raise _error("invalid_routing_decision", "$", str(exc)) from exc


def load_routing_decision_document(path: str | Path) -> RoutingDecision:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _error(
            "decision_read_error", str(source), exc.__class__.__name__
        ) from exc
    except json.JSONDecodeError as exc:
        raise _error(
            "invalid_json",
            str(source),
            f"line {exc.lineno}, column {exc.colno}",
        ) from exc
    return parse_routing_decision_document(data)


@dataclass(frozen=True)
class InspectedConnector:
    config: ConnectorConfig
    probe: ConnectorProbeResult | None
    error_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "connection_id": self.config.id,
            "kind": self.config.kind,
            "driver": self.config.driver,
            "probe": self.probe.to_dict() if self.probe else None,
            "error": (
                {"code": self.error_code}
                if self.error_code is not None
                else None
            ),
        }


def _probe_driver_for(
    config: ConnectorConfig,
    base_registry: ConnectorRegistry,
) -> FakeProbeDriver:
    """Wrap one offline static fake driver in a probe-capable fake."""

    driver = base_registry.resolve_config(config)
    capabilities = driver.declared_capabilities(config)
    return FakeProbeDriver(
        kind=driver.kind,
        driver_id=driver.driver_id,
        driver_version=driver.driver_version,
        capabilities=capabilities,
    )


def inspect_connectors(
    configs: Iterable[ConnectorConfig],
    *,
    checked_at: str,
) -> tuple[InspectedConnector, ...]:
    """Probe configured connectors using only the offline fake-driver registry."""

    base_registry = build_fake_registry()
    inspected: list[InspectedConnector] = []

    for config in sorted(configs, key=lambda item: item.id):
        try:
            probe_driver = _probe_driver_for(config, base_registry)
            registry = ConnectorRegistry()
            registry.register(probe_driver)
            result = probe_connector(
                config,
                registry,
                checked_at=checked_at,
                secret_available=False if config.secret_ref is not None else None,
            )
        except ConnectorRegistryError as exc:
            inspected.append(
                InspectedConnector(
                    config=config,
                    probe=None,
                    error_code=exc.code,
                )
            )
            continue

        inspected.append(InspectedConnector(config=config, probe=result))

    return tuple(inspected)


def doctor_report(
    inspected: Iterable[InspectedConnector],
) -> dict[str, object]:
    """Return a deterministic PASS/WARN/FAIL summary."""

    rows: list[dict[str, object]] = []
    overall = "PASS"

    for item in inspected:
        if item.error_code is not None:
            state = "FAIL"
            reason = item.error_code
        else:
            assert item.probe is not None
            status = item.probe.status
            if status == "unavailable":
                state = "FAIL"
                reason = (
                    item.probe.failure.code
                    if item.probe.failure is not None
                    else "unavailable"
                )
            elif status in {"degraded", "disabled"}:
                state = "WARN"
                reason = status
            else:
                state = "PASS"
                reason = "healthy"

        if state == "FAIL":
            overall = "FAIL"
        elif state == "WARN" and overall == "PASS":
            overall = "WARN"

        rows.append(
            {
                "connection_id": item.config.id,
                "state": state,
                "reason": reason,
            }
        )

    return {"status": overall, "connections": rows}


def _more_restrictive_risk(left: str, right: str) -> str:
    return left if RISK_ORDER[left] <= RISK_ORDER[right] else right


def _intersection_or_driver(
    configured: frozenset[str],
    observed: frozenset[str],
) -> frozenset[str]:
    return observed if not configured else configured & observed


def _routing_profile_from_inspection(
    item: InspectedConnector,
    *,
    project_cost_usd: float,
) -> ConnectorProfile | str:
    """Convert observed fake-driver facts into routing input."""

    if item.error_code is not None:
        return f"inspection_error:{item.error_code}"
    assert item.probe is not None

    config = item.config
    probe = item.probe
    cost = _money(project_cost_usd, f"connector_costs.{config.id}")
    if cost > config.project_spend_usd_max:
        return "connector_spend_policy_exceeded"

    caps: DriverCapabilities = probe.observed_capabilities
    capability_tiers = _intersection_or_driver(
        config.capability_tiers, caps.capability_tiers
    )
    task_classes = _intersection_or_driver(
        config.task_classes, caps.task_classes
    )
    tools = _intersection_or_driver(config.tools, caps.tools)

    return ConnectorProfile(
        connection_id=config.id,
        kind=config.kind,
        driver=config.driver,
        enabled=config.enabled,
        health=probe.status,
        capability_tiers=capability_tiers,
        task_classes=task_classes,
        tools=tools,
        max_risk=_more_restrictive_risk(config.max_risk, caps.max_risk),
        external_processing=(
            config.external_processing or caps.external_processing
        ),
        project_cost_usd=cost,
        secret_required=config.secret_ref is not None,
        secret_available=probe.auth_configured,
        capacity_available=probe.status in {"healthy", "degraded"},
        provider_family=config.provider_family,
        agent_family=config.agent_family,
        execution_family=config.execution_family,
    )


def explain_route(
    decision: RoutingDecision,
    inspected: Iterable[InspectedConnector],
    *,
    connector_costs: Mapping[str, float] | None = None,
    auto_select: bool = False,
) -> dict[str, object]:
    """Explain routing with stable reasons and zero external work."""

    connector_costs = connector_costs or {}
    profiles: list[ConnectorProfile] = []
    pre_rejected: list[dict[str, object]] = []

    for item in inspected:
        cost = connector_costs.get(item.config.id, 0.0)
        profile = _routing_profile_from_inspection(
            item, project_cost_usd=cost
        )
        if isinstance(profile, str):
            pre_rejected.append(
                {
                    "connection_id": item.config.id,
                    "reasons": [profile],
                }
            )
        else:
            profiles.append(profile)

    result = resolve_routes(
        decision,
        profiles,
        auto_select=auto_select,
    )

    ineligible = [
        {
            "connection_id": item.connection_id,
            "reasons": list(item.reasons),
        }
        for item in result.ineligible
    ]
    ineligible.extend(pre_rejected)
    ineligible.sort(key=lambda item: str(item["connection_id"]))

    return {
        "eligible": [
            {
                "connection_id": item.connection_id,
                "supported_tier": item.supported_tier,
            }
            for item in result.eligible
        ],
        "ineligible": ineligible,
        "selected_connection_id": result.selected_connection_id,
        "selection_reason": list(result.selection_reason),
    }


def parse_connector_costs(values: Iterable[str]) -> dict[str, float]:
    """Parse repeated CLI values of the form CONNECTION_ID=USD."""

    result: dict[str, float] = {}
    for index, raw in enumerate(values):
        if "=" not in raw:
            raise _error(
                "invalid_cost",
                f"cost[{index}]",
                "must use CONNECTION_ID=USD",
            )
        connection_id, amount = raw.split("=", 1)
        if not connection_id:
            raise _error(
                "invalid_cost", f"cost[{index}]", "connection id is empty"
            )
        if connection_id in result:
            raise _error(
                "duplicate_cost",
                f"cost[{index}]",
                f"duplicate cost for {connection_id}",
            )
        try:
            numeric = float(amount)
        except ValueError as exc:
            raise _error(
                "invalid_cost",
                f"cost[{index}]",
                "USD amount must be numeric",
            ) from exc
        result[connection_id] = _money(numeric, f"cost[{index}]")
    return result
