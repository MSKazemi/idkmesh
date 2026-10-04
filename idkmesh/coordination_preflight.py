"""Read-only dependency/effort preflight for the coordination plan (#915).

Trusted callers supply schema-valid WorkUnits, exact SCM revisions and
prerequisite observations. This is a replayable local projection, not an
authentication producer, durable ledger, dispatch or acceptance boundary.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
import json
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from idkmesh.connector_routing import (
    ConnectorProfile, RISK_ORDER, RoutingDecision, TIER_ORDER, resolve_routes,
)
from idkmesh.tenant_scope import TenantScope
from idkmesh.work_unit_binding import (
    WorkUnitBindingError, WorkUnitSourceBinding, bind_work_unit_source, canonical_digest,
)


class CoordinationPreflightError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _text(value: str, field: str) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > 512
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise CoordinationPreflightError("invalid_input", f"invalid {field}")
    return value


def _digest(value: str, field: str) -> str:
    # Reuse the canonical WorkUnit digest/revision validation.
    try:
        WorkUnitSourceBinding("validation", 1, value, "0" * 40)
    except WorkUnitBindingError as exc:
        raise CoordinationPreflightError("invalid_input", f"invalid {field}") from exc
    return value


class DependencyGraph:
    """Freeze WorkUnit v0.2 requires edges, source/content pins and topology."""

    def __init__(
        self, scope: TenantScope, work_units: Iterable[dict[str, Any]],
        *, source_revisions: Mapping[str, str],
    ) -> None:
        if not isinstance(scope, TenantScope):
            raise CoordinationPreflightError("invalid_input", "scope must be TenantScope")
        bindings: dict[str, WorkUnitSourceBinding] = {}
        requires: dict[str, tuple[str, ...]] = {}
        risk_floors: dict[str, str] = {}
        for raw in work_units:
            # Detach from mutable caller input before computing immutable digests.
            try:
                unit = json.loads(json.dumps(raw, allow_nan=False))
            except (TypeError, ValueError) as exc:
                raise CoordinationPreflightError("invalid_input", "WorkUnit must be finite JSON") from exc
            if not isinstance(unit, dict) or unit.get("schema_version") != "0.2":
                raise CoordinationPreflightError("unsupported_work_unit", "requires WorkUnit v0.2")
            unit_id = _text(unit.get("id"), "work_unit.id")
            security = unit.get("security")
            risk = security.get("risk_class") if isinstance(security, dict) else None
            if not isinstance(risk, str) or risk not in RISK_ORDER:
                raise CoordinationPreflightError("invalid_work_unit_security", "WorkUnit must declare a risk floor")
            if unit_id in bindings:
                raise CoordinationPreflightError("duplicate_work_unit", "WorkUnit IDs must be unique")
            try:
                binding = bind_work_unit_source(unit, source_revision=source_revisions[unit_id])
            except (KeyError, WorkUnitBindingError) as exc:
                raise CoordinationPreflightError("source_binding_invalid", str(exc)) from exc
            dependencies = unit.get("dependencies")
            if not isinstance(dependencies, list):
                raise CoordinationPreflightError("invalid_dependency", "dependencies must be an array")
            edges: set[str] = set()
            for dependency in dependencies:
                if (not isinstance(dependency, dict)
                        or not {"work_unit_id", "relationship"} <= dependency.keys()
                        or set(dependency) - {"work_unit_id", "relationship", "condition"}):
                    raise CoordinationPreflightError("invalid_dependency", "invalid dependency fields")
                target = _text(dependency["work_unit_id"], "dependency.work_unit_id")
                relationship = dependency["relationship"]
                if relationship not in ("requires", "blocks", "informs", "validates", "derived_from"):
                    raise CoordinationPreflightError("invalid_dependency", "unknown relationship")
                if relationship == "requires":
                    if dependency.get("condition") not in (None, ""):
                        raise CoordinationPreflightError("unsupported_condition", "free-text conditions need an explicit policy")
                    if target in edges:
                        raise CoordinationPreflightError("duplicate_dependency", "duplicate requires edge")
                    edges.add(target)
            bindings[unit_id] = binding
            requires[unit_id] = tuple(sorted(edges))
            risk_floors[unit_id] = risk
        if not bindings:
            raise CoordinationPreflightError("invalid_input", "graph must contain a WorkUnit")
        dependents: dict[str, list[str]] = {key: [] for key in bindings}
        for node, prerequisites in requires.items():
            for prerequisite in prerequisites:
                if prerequisite not in bindings:
                    raise CoordinationPreflightError("missing_prerequisite", f"missing required target: {prerequisite}")
                dependents[prerequisite].append(node)
        remaining = {node: len(edges) for node, edges in requires.items()}
        queue = deque(sorted(node for node, count in remaining.items() if count == 0))
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for dependent in sorted(dependents[node]):
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    queue.append(dependent)
        if len(order) != len(bindings):
            raise CoordinationPreflightError("dependency_cycle", "requires graph contains a cycle")
        self.scope = scope
        self.bindings = MappingProxyType(bindings)
        self.requires = MappingProxyType(requires)
        self.risk_floors = MappingProxyType(risk_floors)
        self.dependents = MappingProxyType({node: tuple(sorted(edges)) for node, edges in dependents.items()})
        self.topological_order = tuple(order)
        self.digest = canonical_digest({
            "scope": scope.to_dict(),
            "nodes": [{"binding": bindings[node].to_dict(), "requires": list(requires[node])}
                      for node in sorted(bindings)],
        })


@dataclass(frozen=True, slots=True)
class PrerequisiteObservation:
    scope: TenantScope
    event_id: str
    sequence: int
    binding: WorkUnitSourceBinding
    state: str
    inputs_digest: str
    integrated_revision: str | None = None
    artifacts_digest: str | None = None
    verification_reference: str | None = None
    integration_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, TenantScope) or not isinstance(self.binding, WorkUnitSourceBinding):
            raise CoordinationPreflightError("invalid_input", "invalid scope or source binding")
        _text(self.event_id, "event_id")
        if type(self.sequence) is not int or self.sequence < 1:
            raise CoordinationPreflightError("invalid_input", "sequence must be an integer >= 1")
        if self.state not in ("pending", "candidate", "integrated", "rejected"):
            raise CoordinationPreflightError("invalid_input", "invalid prerequisite state")
        _digest(self.inputs_digest, "inputs_digest")
        if self.artifacts_digest is not None:
            _digest(self.artifacts_digest, "artifacts_digest")
        if self.integrated_revision is not None:
            try:
                WorkUnitSourceBinding("validation", 1, self.inputs_digest, self.integrated_revision)
            except WorkUnitBindingError as exc:
                raise CoordinationPreflightError("invalid_input", "invalid integrated_revision") from exc
        for field in ("verification_reference", "integration_reference"):
            value = getattr(self, field)
            if value is not None:
                _text(value, field)
        if self.state == "integrated" and any(getattr(self, field) is None for field in (
            "integrated_revision", "artifacts_digest", "verification_reference", "integration_reference",
        )):
            raise CoordinationPreflightError("integration_evidence_required", "integrated requires exact artifact/SCM/evidence references")

    def to_dict(self) -> dict[str, Any]:
        return {"scope": self.scope.to_dict(), "event_id": self.event_id, "sequence": self.sequence,
                "binding": self.binding.to_dict(), "state": self.state,
                "inputs_digest": self.inputs_digest, "integrated_revision": self.integrated_revision,
                "artifacts_digest": self.artifacts_digest,
                "verification_reference": self.verification_reference,
                "integration_reference": self.integration_reference}

    def input_pin(self) -> dict[str, Any]:
        # Delivery/sequence/ref aliases do not change artifact input identity.
        return {"binding": self.binding.to_dict(), "inputs_digest": self.inputs_digest,
                "integrated_revision": self.integrated_revision, "artifacts_digest": self.artifacts_digest}


@dataclass(frozen=True, slots=True)
class TaskReadiness:
    ready: bool
    satisfied: bool
    inputs_digest: str | None
    blockers: tuple[str, ...]


class DependencyProjection:
    """Local bounded replay projection; restore by replaying retained trusted events.

    No counter decrement on observations: readiness is recomputed from the
    current exact snapshot, avoiding duplicate-event counter corruption.
    """

    def __init__(self, graph: DependencyGraph, *, max_events: int = 10000) -> None:
        if not isinstance(graph, DependencyGraph) or type(max_events) is not int or max_events < 1:
            raise CoordinationPreflightError("invalid_input", "invalid graph or event limit")
        self.graph = graph
        self.max_events = max_events
        self._events: dict[str, str] = {}
        self._sequences: dict[tuple[str, int], str] = {}
        self._latest: dict[str, PrerequisiteObservation] = {}

    def observe(self, observation: PrerequisiteObservation) -> bool:
        """Apply once; conflicting identity/sequence fails; late older state is ignored."""
        if not isinstance(observation, PrerequisiteObservation):
            raise CoordinationPreflightError("invalid_input", "observation must be normalized")
        if observation.scope != self.graph.scope:
            raise CoordinationPreflightError("scope_mismatch", "observation belongs to another tenant/project")
        node = observation.binding.work_unit_id
        if node not in self.graph.bindings:
            raise CoordinationPreflightError("unknown_work_unit", "observation is outside this graph")
        digest = canonical_digest(observation.to_dict())
        if observation.event_id in self._events:
            if self._events[observation.event_id] != digest:
                raise CoordinationPreflightError("event_conflict", "event identity has different content")
            return False
        old = self._latest.get(node)
        holder = self._sequences.get((node, observation.sequence))
        if holder is not None and holder != observation.event_id:
            # Checked against every sequence seen for this WorkUnit, not only the
            # newest one: a different event at an older sequence is a conflict, not
            # something to ignore silently.
            raise CoordinationPreflightError("sequence_conflict", "one source sequence has different events")
        if len(self._events) >= self.max_events:
            raise CoordinationPreflightError("event_budget_exhausted", "local replay event budget exhausted")
        self._events[observation.event_id] = digest
        self._sequences[(node, observation.sequence)] = observation.event_id
        if old is not None and observation.sequence < old.sequence:
            return False
        self._latest[node] = observation
        return True

    @property
    def observation_digest(self) -> str:
        return canonical_digest([self._latest[node].to_dict() for node in sorted(self._latest)])

    def readiness(self) -> dict[str, TaskReadiness]:
        states: dict[str, TaskReadiness] = {}
        for node in self.graph.topological_order:
            prerequisites = self.graph.requires[node]
            blocked = []
            for prerequisite in prerequisites:
                if states[prerequisite].satisfied:
                    continue
                observed = self._latest.get(prerequisite)
                if observed is None:
                    code = "prerequisite_missing"
                elif not states[prerequisite].ready:
                    code = "prerequisite_blocked"
                elif observed.state != "integrated":
                    code = "prerequisite_not_integrated"
                elif observed.binding != self.graph.bindings[prerequisite]:
                    code = "prerequisite_binding_changed"
                else:
                    code = "prerequisite_inputs_changed"
                blocked.append(code + ":" + prerequisite)
            blockers = tuple(blocked)
            inputs = None if blockers else canonical_digest({
                "scope": self.graph.scope.to_dict(), "task": self.graph.bindings[node].to_dict(),
                "prerequisites": [self._latest[prerequisite].input_pin() for prerequisite in prerequisites],
            })
            observation = self._latest.get(node)
            satisfied = bool(not blockers and observation is not None
                             and observation.state == "integrated"
                             and observation.binding == self.graph.bindings[node]
                             and observation.inputs_digest == inputs)
            states[node] = TaskReadiness(not blockers, satisfied, inputs, blockers)
        return states

    def prerequisite_pins(self, node: str) -> list[dict[str, Any]]:
        return [self._latest[prerequisite].to_dict() for prerequisite in self.graph.requires[node]
                if prerequisite in self._latest]


@dataclass(frozen=True, slots=True)
class EffortEstimate:
    components: int | None
    ambiguity: str
    coupling: str
    execution_seconds: float | None
    verification_minutes: float | None
    integration_minutes: float | None
    estimate_source: str
    deterministic_operation: bool = False

    def __post_init__(self) -> None:
        if self.components is not None and (type(self.components) is not int or not 1 <= self.components <= 10000):
            raise CoordinationPreflightError("invalid_input", "components must be 1..10000 or unknown")
        for field in ("ambiguity", "coupling"):
            if getattr(self, field) not in ("low", "medium", "high", "unknown"):
                raise CoordinationPreflightError("invalid_input", f"invalid {field}")
        for field in ("execution_seconds", "verification_minutes", "integration_minutes"):
            value = getattr(self, field)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e9):
                raise CoordinationPreflightError("invalid_input", f"invalid {field}")
        _text(self.estimate_source, "estimate_source")
        if type(self.deterministic_operation) is not bool:
            raise CoordinationPreflightError("invalid_input", "deterministic_operation must be boolean")

    @property
    def total_seconds(self) -> float | None:
        if any(value is None for value in (self.execution_seconds, self.verification_minutes, self.integration_minutes)):
            return None
        return self.execution_seconds + 60 * (self.verification_minutes + self.integration_minutes)


def effort_capability(estimate: EffortEstimate, decision: RoutingDecision) -> tuple[str | None, tuple[str, ...]]:
    """Uncalibrated shadow heuristic; never lower the trusted capability floor."""
    if estimate.components is None or "unknown" in (estimate.ambiguity, estimate.coupling):
        return None, ("effort_requirements_unknown",)
    if estimate.deterministic_operation and estimate.ambiguity == estimate.coupling == "low":
        proposed, reasons = "T0", ["declared_deterministic_operation"]
    else:
        rank = 1
        reasons = ["declared_scope_ambiguity_coupling"]
        if estimate.components >= 3 or "medium" in (estimate.ambiguity, estimate.coupling):
            rank = 2
        if estimate.components >= 8 or estimate.coupling == "high" or decision.risk_class == "high":
            rank = 3
        if estimate.ambiguity == "high" or decision.risk_class == "critical":
            rank = 4
        proposed = "T" + str(rank)
    if TIER_ORDER[proposed] < TIER_ORDER[decision.required_capability_tier]:
        proposed = decision.required_capability_tier
        reasons.append("trusted_capability_floor_preserved")
    return proposed, tuple(reasons)


def critical_path_ranks(graph: DependencyGraph, estimates: Mapping[str, EffortEstimate]) -> dict[str, float]:
    """HEFT-inspired remaining-chain time including review/integration, in seconds."""
    if set(estimates) != set(graph.bindings):
        raise CoordinationPreflightError("estimate_missing", "rank needs an estimate for each task")
    ranks: dict[str, float] = {}
    for node in reversed(graph.topological_order):
        duration = estimates[node].total_seconds
        if duration is None:
            raise CoordinationPreflightError("duration_unknown", "cannot rank with unknown duration")
        ranks[node] = duration + max((ranks[dependent] for dependent in graph.dependents[node]), default=0)
    return ranks


def coordination_preflight(
    projection: DependencyProjection, node: str, estimate: EffortEstimate,
    decision: RoutingDecision, connectors: Iterable[ConnectorProfile],
) -> dict[str, Any]:
    """Return a versioned, read-only recommendation; no admission or dispatch."""
    if node not in projection.graph.bindings:
        raise CoordinationPreflightError("unknown_work_unit", "task is outside this graph")
    state = projection.readiness()[node]
    risk = max((decision.risk_class, projection.graph.risk_floors[node]), key=RISK_ORDER.__getitem__)
    decision = replace(decision, risk_class=risk)
    tier, reasons = effort_capability(estimate, decision)
    blockers = list(state.blockers)
    if state.satisfied:
        blockers.append("task_already_integrated")
    if tier is None:
        blockers.append("effort_requirements_unknown")
    deterministic_conflict = decision.authority_mode == "deterministic" and tier not in (None, "T0")
    if deterministic_conflict:
        blockers.append("deterministic_context_conflict")
    # Project-level zero spend is non-compensating, even if task policy is lax.
    routed_decision = replace(decision, project_spend_usd_max=0.0,
                              required_capability_tier=decision.required_capability_tier if tier is None or deterministic_conflict else tier)
    resolution = resolve_routes(routed_decision, connectors, auto_select=not blockers)
    if not blockers and resolution.selected_connection_id is None:
        blockers.append("no_eligible_connector")
    return {
        "kind": "idkmesh-coordination-preflight", "schema_version": "0.1",
        "scope": projection.graph.scope.to_dict(), "graph_digest": projection.graph.digest,
        "observation_digest": projection.observation_digest,
        "binding": projection.graph.bindings[node].to_dict(),
        "inputs_digest": state.inputs_digest, "ready": state.ready,
        "satisfied": state.satisfied, "blockers": blockers,
        "prerequisite_pins": projection.prerequisite_pins(node), "effort": asdict(estimate),
        "capability": {"trusted_floor": decision.required_capability_tier, "recommended_tier": tier,
                       "reasons": list(reasons), "expected_total_seconds": estimate.total_seconds,
                       "evidence_class": "declared_estimate"},
        "routing": {"authority_mode": decision.authority_mode, "risk_class": decision.risk_class,
                    "project_spend_usd_max": 0.0,
                    "eligible": [{"connection_id": lane.connection_id, "supported_tier": lane.supported_tier}
                                 for lane in resolution.eligible],
                    "ineligible": [{"connection_id": lane.connection_id, "reasons": list(lane.reasons)}
                                   for lane in resolution.ineligible],
                    "recommended_connection_id": resolution.selected_connection_id,
                    "selection_reason": list(resolution.selection_reason)},
        "authority": {"dispatch": False, "executes_worker": False, "accepts_candidate": False, "merge": False},
    }
