"""Provider-neutral connector admission and routing.

This module is the first bounded implementation slice of issue #574.  It is
pure stdlib and deliberately contains no live provider calls, secret
materialization, GitHub mutation, or merge authority.

The router answers only:

    given a normalized task decision and configured connector capabilities,
    which connectors are eligible and which eligible connector would the
    deterministic v0.1 policy prefer?

Capability is separate from authority.  A stronger connector never upgrades a
human-required task into an automatically dispatchable one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
HEALTH_STATES = {"healthy", "degraded", "unavailable", "disabled"}
CONNECTOR_KINDS = {"scm", "agent", "model", "execution"}
AUTHORITY_MODES = {
    "deterministic",
    "agent_candidate",
    "human_gate_then_agent",
    "human_required",
}


def _as_frozenset(values: Iterable[str] | frozenset[str]) -> frozenset[str]:
    return values if isinstance(values, frozenset) else frozenset(values)


@dataclass(frozen=True)
class ConnectorProfile:
    """Normalized routing-facing view of one configured connector.

    Provider-specific settings stay outside this object.  The routing kernel
    only needs capabilities and policy-relevant state.
    """

    connection_id: str
    kind: str
    driver: str
    enabled: bool = True
    health: str = "healthy"
    capability_tiers: frozenset[str] = field(default_factory=frozenset)
    task_classes: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    max_risk: str = "low"
    external_processing: bool = False
    project_cost_usd: float = 0.0
    secret_required: bool = False
    secret_available: bool = True
    capacity_available: bool = True
    provider_family: str = ""
    agent_family: str = ""
    execution_family: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capability_tiers", _as_frozenset(self.capability_tiers)
        )
        object.__setattr__(self, "task_classes", _as_frozenset(self.task_classes))
        object.__setattr__(self, "tools", _as_frozenset(self.tools))

        if not self.connection_id:
            raise ValueError("connection_id must not be empty")
        if self.kind not in CONNECTOR_KINDS:
            raise ValueError(f"unknown connector kind: {self.kind}")
        if not self.driver:
            raise ValueError("driver must not be empty")
        if self.health not in HEALTH_STATES:
            raise ValueError(f"unknown health state: {self.health}")
        unknown_tiers = sorted(set(self.capability_tiers) - set(TIER_ORDER))
        if unknown_tiers:
            raise ValueError(
                "unknown capability tier(s): " + ", ".join(unknown_tiers)
            )
        if self.max_risk not in RISK_ORDER:
            raise ValueError(f"unknown max_risk: {self.max_risk}")
        if self.project_cost_usd < 0:
            raise ValueError("project_cost_usd must be >= 0")


@dataclass(frozen=True)
class RoutingDecision:
    """Normalized task-side routing requirements.

    This object contains no provider name.  It describes what the task needs
    and what project policy permits.
    """

    required_capability_tier: str
    authority_mode: str
    risk_class: str = "low"
    task_classes: frozenset[str] = field(default_factory=frozenset)
    required_tools: frozenset[str] = field(default_factory=frozenset)
    allowed_connector_kinds: frozenset[str] = field(
        default_factory=lambda: frozenset({"agent"})
    )
    external_processing_allowed: bool = True
    project_spend_usd_max: float | None = None
    human_gate_satisfied: bool = True
    prefer_zero_cost: bool = True
    avoid_provider_families: frozenset[str] = field(default_factory=frozenset)
    independent_reviewer_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_classes", _as_frozenset(self.task_classes))
        object.__setattr__(
            self, "required_tools", _as_frozenset(self.required_tools)
        )
        object.__setattr__(
            self,
            "allowed_connector_kinds",
            _as_frozenset(self.allowed_connector_kinds),
        )
        object.__setattr__(
            self,
            "avoid_provider_families",
            _as_frozenset(self.avoid_provider_families),
        )

        if self.required_capability_tier not in TIER_ORDER:
            raise ValueError(
                f"unknown required capability tier: {self.required_capability_tier}"
            )
        if self.authority_mode not in AUTHORITY_MODES:
            raise ValueError(f"unknown authority mode: {self.authority_mode}")
        if self.risk_class not in RISK_ORDER:
            raise ValueError(f"unknown risk class: {self.risk_class}")
        unknown_kinds = sorted(
            set(self.allowed_connector_kinds) - CONNECTOR_KINDS
        )
        if unknown_kinds:
            raise ValueError(
                "unknown allowed connector kind(s): " + ", ".join(unknown_kinds)
            )
        if self.project_spend_usd_max is not None and self.project_spend_usd_max < 0:
            raise ValueError("project_spend_usd_max must be >= 0 when set")


@dataclass(frozen=True)
class RejectedConnector:
    connection_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EligibleConnector:
    connection_id: str
    supported_tier: str
    selection_key: tuple[int | float | str, ...]


@dataclass(frozen=True)
class RouteResolution:
    """Deterministic route resolution result."""

    eligible: tuple[EligibleConnector, ...]
    ineligible: tuple[RejectedConnector, ...]
    selected_connection_id: str | None
    selection_reason: tuple[str, ...]


def _minimum_supported_tier(
    profile: ConnectorProfile, required_tier: str
) -> str | None:
    required_rank = TIER_ORDER[required_tier]
    candidates = [
        tier
        for tier in profile.capability_tiers
        if TIER_ORDER[tier] >= required_rank
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda tier: TIER_ORDER[tier])


def _rejection_reasons(
    decision: RoutingDecision, profile: ConnectorProfile
) -> tuple[str, ...]:
    reasons: list[str] = []

    if decision.authority_mode == "human_required":
        reasons.append("human_required")
    elif (
        decision.authority_mode == "human_gate_then_agent"
        and not decision.human_gate_satisfied
    ):
        reasons.append("human_gate_pending")

    if not profile.enabled or profile.health == "disabled":
        reasons.append("connector_disabled")
    elif profile.health == "unavailable":
        reasons.append("connector_unavailable")

    if profile.kind not in decision.allowed_connector_kinds:
        reasons.append("connector_kind_not_allowed")

    supported_tier = _minimum_supported_tier(
        profile, decision.required_capability_tier
    )
    if supported_tier is None:
        reasons.append("insufficient_capability_tier")

    missing_task_classes = sorted(
        set(decision.task_classes) - set(profile.task_classes)
    )
    reasons.extend(
        f"task_class_unsupported:{task_class}"
        for task_class in missing_task_classes
    )

    missing_tools = sorted(set(decision.required_tools) - set(profile.tools))
    reasons.extend(f"required_tool_missing:{tool}" for tool in missing_tools)

    if RISK_ORDER[profile.max_risk] < RISK_ORDER[decision.risk_class]:
        reasons.append("risk_not_allowed")

    if profile.external_processing and not decision.external_processing_allowed:
        reasons.append("external_processing_forbidden")

    if (
        decision.project_spend_usd_max is not None
        and profile.project_cost_usd > decision.project_spend_usd_max
    ):
        reasons.append("project_spend_exceeded")

    if profile.secret_required and not profile.secret_available:
        reasons.append("secret_unavailable")

    if not profile.capacity_available:
        reasons.append("capacity_unavailable")

    return tuple(reasons)


def _selection_key(
    decision: RoutingDecision, profile: ConnectorProfile, supported_tier: str
) -> tuple[int | float | str, ...]:
    required_rank = TIER_ORDER[decision.required_capability_tier]
    overprovision = TIER_ORDER[supported_tier] - required_rank
    paid_penalty = (
        1 if decision.prefer_zero_cost and profile.project_cost_usd > 0 else 0
    )
    avoided_family_penalty = (
        1
        if profile.provider_family
        and profile.provider_family in decision.avoid_provider_families
        else 0
    )
    external_processing_penalty = 1 if profile.external_processing else 0
    degraded_penalty = 1 if profile.health == "degraded" else 0

    return (
        overprovision,
        paid_penalty,
        avoided_family_penalty,
        external_processing_penalty,
        degraded_penalty,
        profile.project_cost_usd,
        profile.connection_id,
    )


def resolve_routes(
    decision: RoutingDecision,
    connectors: Iterable[ConnectorProfile],
    *,
    auto_select: bool = True,
) -> RouteResolution:
    """Resolve eligible connectors and optionally select one deterministically.

    Selection is lexicographic and intentionally transparent.  Hard policy
    filters are non-compensating: a cheap connector cannot offset insufficient
    capability, forbidden external processing, a pending human gate, or any
    other rejection reason.
    """

    eligible: list[EligibleConnector] = []
    ineligible: list[RejectedConnector] = []

    for profile in sorted(connectors, key=lambda item: item.connection_id):
        reasons = _rejection_reasons(decision, profile)
        if reasons:
            ineligible.append(
                RejectedConnector(profile.connection_id, reasons)
            )
            continue

        supported_tier = _minimum_supported_tier(
            profile, decision.required_capability_tier
        )
        # No reasons implies a supported tier exists.
        assert supported_tier is not None
        eligible.append(
            EligibleConnector(
                connection_id=profile.connection_id,
                supported_tier=supported_tier,
                selection_key=_selection_key(
                    decision, profile, supported_tier
                ),
            )
        )

    eligible.sort(key=lambda item: item.selection_key)

    selected: str | None = None
    selection_reason: tuple[str, ...] = ()
    if auto_select and eligible:
        selected = eligible[0].connection_id
        selection_reason = (
            "lexicographic_v0_1",
            f"required_tier:{decision.required_capability_tier}",
            f"authority:{decision.authority_mode}",
            f"risk:{decision.risk_class}",
        )

    return RouteResolution(
        eligible=tuple(eligible),
        ineligible=tuple(ineligible),
        selected_connection_id=selected,
        selection_reason=selection_reason,
    )
