"""Read-only GitHub projection of canonical connector routing (C5-E).

GitHub labels/status are a UI projection of RoutingDecision + RouteResolution.
They are not inputs to routing and cannot broaden authority, risk, spend,
external-processing, or connector eligibility.

This module performs no GitHub mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
import re

from idkmesh.connector_routing import (
    RouteResolution,
    RoutingDecision,
)
from idkmesh.work_unit_binding import canonical_digest


MANAGED_LABEL_PREFIX = "idkmesh:"
_ROUTING_LABEL_FAMILIES = (
    "tier:", "authority:", "risk:", "route:", "processing:", "review:",
)


def _is_managed_routing_label(label: str) -> bool:
    folded = label.casefold()
    return any(
        folded.startswith(MANAGED_LABEL_PREFIX + family)
        for family in _ROUTING_LABEL_FAMILIES
    )


def _decision_payload(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "required_capability_tier": decision.required_capability_tier,
        "authority_mode": decision.authority_mode,
        "risk_class": decision.risk_class,
        "task_classes": sorted(decision.task_classes),
        "required_tools": sorted(decision.required_tools),
        "allowed_connector_kinds": sorted(
            decision.allowed_connector_kinds
        ),
        "external_processing_allowed": (
            decision.external_processing_allowed
        ),
        "project_spend_usd_max": decision.project_spend_usd_max,
        "human_gate_satisfied": decision.human_gate_satisfied,
        "prefer_zero_cost": decision.prefer_zero_cost,
        "avoid_provider_families": sorted(
            decision.avoid_provider_families
        ),
        "independent_reviewer_required": (
            decision.independent_reviewer_required
        ),
    }


def _resolution_payload(resolution: RouteResolution) -> dict[str, Any]:
    return {
        "eligible": [
            {
                "connection_id": item.connection_id,
                "supported_tier": item.supported_tier,
                "selection_key": list(item.selection_key),
            }
            for item in resolution.eligible
        ],
        "ineligible": [
            {
                "connection_id": item.connection_id,
                "reasons": list(item.reasons),
            }
            for item in resolution.ineligible
        ],
        "selected_connection_id": resolution.selected_connection_id,
        "selection_reason": list(resolution.selection_reason),
    }


def _validate_resolution(resolution: RouteResolution) -> None:
    eligible = [item.connection_id for item in resolution.eligible]
    ineligible = [item.connection_id for item in resolution.ineligible]

    if len(eligible) != len(set(eligible)):
        raise ValueError("eligible connector IDs must be unique")
    if len(ineligible) != len(set(ineligible)):
        raise ValueError("ineligible connector IDs must be unique")
    overlap = sorted(set(eligible).intersection(ineligible))
    if overlap:
        raise ValueError(
            "connector cannot be both eligible and ineligible: "
            + ", ".join(overlap)
        )

    selected = resolution.selected_connection_id
    if selected is not None and selected not in set(eligible):
        raise ValueError(
            "selected_connection_id must reference an eligible connector"
        )


@dataclass(frozen=True, slots=True)
class GitHubRoutingProjection:
    routing_digest: str
    route_state: str
    managed_labels: tuple[str, ...]
    selected_connection_id: str | None
    eligible_connection_ids: tuple[str, ...]
    ineligible: tuple[tuple[str, tuple[str, ...]], ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "routing_digest": self.routing_digest,
            "route_state": self.route_state,
            "managed_labels": list(self.managed_labels),
            "selected_connection_id": self.selected_connection_id,
            "eligible_connection_ids": list(
                self.eligible_connection_ids
            ),
            "ineligible": [
                {
                    "connection_id": connection_id,
                    "reasons": list(reasons),
                }
                for connection_id, reasons in self.ineligible
            ],
            "summary": self.summary,
            "github_mutation_performed": False,
        }


def _route_state(resolution: RouteResolution) -> str:
    if resolution.selected_connection_id is not None:
        return "selected"
    if resolution.eligible:
        return "eligible"
    return "blocked"


def _labels(
    decision: RoutingDecision,
    route_state: str,
) -> tuple[str, ...]:
    labels = {
        f"{MANAGED_LABEL_PREFIX}tier:{decision.required_capability_tier}",
        (
            f"{MANAGED_LABEL_PREFIX}authority:"
            + decision.authority_mode.replace("_", "-")
        ),
        f"{MANAGED_LABEL_PREFIX}risk:{decision.risk_class}",
        f"{MANAGED_LABEL_PREFIX}route:{route_state}",
        (
            f"{MANAGED_LABEL_PREFIX}processing:"
            + (
                "external-ok"
                if decision.external_processing_allowed
                else "local-only"
            )
        ),
        (
            f"{MANAGED_LABEL_PREFIX}review:"
            + (
                "independent-required"
                if decision.independent_reviewer_required
                else "standard"
            )
        ),
    }
    result = tuple(sorted(labels, key=str.casefold))
    if any(len(label) > 50 for label in result):
        raise ValueError("managed routing label exceeds GitHub label limit")
    return result


def project_routing_to_github(
    decision: RoutingDecision,
    resolution: RouteResolution,
) -> GitHubRoutingProjection:
    """Project canonical routing state without recomputing routing."""

    if not isinstance(decision, RoutingDecision):
        raise TypeError("decision must be RoutingDecision")
    if not isinstance(resolution, RouteResolution):
        raise TypeError("resolution must be RouteResolution")

    _validate_resolution(resolution)
    state = _route_state(resolution)
    digest = canonical_digest(
        {
            "schema_version": "0.1",
            "kind": "github-routing-projection",
            "decision": _decision_payload(decision),
            "resolution": _resolution_payload(resolution),
        }
    )

    if state == "selected":
        summary = "Routing selected one eligible connector."
    elif state == "eligible":
        summary = (
            f"Routing found {len(resolution.eligible)} eligible "
            "connector(s); explicit selection is pending."
        )
    else:
        summary = "Routing is blocked; no connector is eligible."

    return GitHubRoutingProjection(
        routing_digest=digest,
        route_state=state,
        managed_labels=_labels(decision, state),
        selected_connection_id=resolution.selected_connection_id,
        eligible_connection_ids=tuple(
            item.connection_id for item in resolution.eligible
        ),
        ineligible=tuple(
            (item.connection_id, item.reasons)
            for item in resolution.ineligible
        ),
        summary=summary,
    )


def replace_managed_routing_labels(
    existing_labels: Iterable[str],
    projection: GitHubRoutingProjection,
) -> tuple[str, ...]:
    """Preserve human labels and replace only the IDKMesh-managed namespace."""

    if isinstance(existing_labels, (str, bytes)):
        raise ValueError("existing_labels must be an iterable of strings")
    if not isinstance(projection, GitHubRoutingProjection):
        raise TypeError("projection must be GitHubRoutingProjection")

    preserved: list[str] = []
    seen: set[str] = set()
    for value in existing_labels:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "existing_labels must contain non-empty strings"
            )
        label = value.strip()
        folded = label.casefold()
        if _is_managed_routing_label(label):
            continue
        if folded in seen:
            continue
        seen.add(folded)
        preserved.append(label)

    for label in projection.managed_labels:
        folded = label.casefold()
        if folded not in seen:
            seen.add(folded)
            preserved.append(label)

    return tuple(preserved)



_PROJECT_SYNC_FIELDS = frozenset({"risk", "routing", "review"})
_PROJECT_FIELD_ID_RE = re.compile(r"[A-Za-z0-9_:-]{1,80}\Z")


def plan_github_project_routing_fields(
    decision: RoutingDecision,
    resolution: RouteResolution,
    *,
    field_ids: Mapping[str, str],
    observed_fields: Mapping[str, str | None],
    expected_routing_digest: str | None = None,
) -> dict[str, Any]:
    """Plan read-model changes; never mutate GitHub Projects or authority.

    Field ids are trusted configuration, not issue/Project contents.
    The observed values determine only which writes are redundant.
    """
    projection = project_routing_to_github(decision, resolution)
    if expected_routing_digest is not None and (
        expected_routing_digest != projection.routing_digest
    ):
        raise ValueError("stale canonical routing digest")
    if not isinstance(field_ids, Mapping) or set(field_ids) != _PROJECT_SYNC_FIELDS:
        raise ValueError("field_ids must map exactly risk/routing/review")
    ids = list(field_ids.values())
    if any(
        not isinstance(value, str) or _PROJECT_FIELD_ID_RE.fullmatch(value) is None
        for value in ids
    ) or len(ids) != len(set(ids)):
        raise ValueError("project field ids must be distinct bounded identifiers")
    if not isinstance(observed_fields, Mapping):
        raise TypeError("observed_fields must be a mapping")
    if any(
        not isinstance(key, str)
        or not isinstance(value, (str, type(None)))
        for key, value in observed_fields.items()
    ):
        raise ValueError("observed_fields must contain text or null values")

    canonical = {
        "risk": decision.risk_class,
        "routing": projection.route_state,
        "review": (
            "independent-required"
            if decision.independent_reviewer_required
            else "standard"
        ),
    }
    desired = tuple(
        sorted(
            (field_ids[field], canonical[field])
            for field in _PROJECT_SYNC_FIELDS
        )
    )
    updates = tuple(
        (field_id, value)
        for field_id, value in desired
        if observed_fields.get(field_id) != value
    )
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-project-routing-sync-plan",
        "routing_digest": projection.routing_digest,
        "desired_fields": [
            {"field_id": field_id, "value": value}
            for field_id, value in desired
        ],
        "updates": [
            {"field_id": field_id, "value": value}
            for field_id, value in updates
        ],
        "noop": len(updates) == 0,
        "project_mutation_performed": False,
        "execution_authority": False,
        "human_decision_authority": False,
        "integration_authority": False,
    }
