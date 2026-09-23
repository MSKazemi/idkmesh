#!/usr/bin/env python3
"""Build deterministic non-authoritative adaptive-policy shadow plans.

The helper does not implement AVE, Physarum, or any other policy. It only
normalizes their recommendations into one fail-closed contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


PLANNER_VERSION = "0.1"
SUBSYSTEMS = {
    "task-routing",
    "verification-allocation",
    "compute-path-routing",
    "community-policy",
    "other",
}
MATURITY = {"N1", "N2", "N3"}


class AdaptivePolicyPlanError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdaptivePolicyPlanError(
            f"{field} must be a non-empty ISO-8601 timestamp"
        )
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AdaptivePolicyPlanError(
            f"{field} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise AdaptivePolicyPlanError(
            f"{field} must include a timezone"
        )
    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha(value: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise AdaptivePolicyPlanError(
            f"{field} must be a lowercase 40-character Git SHA"
        )
    return value


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdaptivePolicyPlanError(f"{field} must not be empty")
    return value


def _unit_interval_or_none(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdaptivePolicyPlanError(f"{field} must be numeric or null")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise AdaptivePolicyPlanError(f"{field} must be in [0, 1]")
    return result


def _cost_or_none(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdaptivePolicyPlanError(f"{field} must be numeric or null")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise AdaptivePolicyPlanError(f"{field} must be finite and >= 0")
    return result


def _normalize_gates(
    gates: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in gates:
        gate_id = _nonempty(str(raw.get("id", "")), "gate.id")
        if gate_id in seen:
            raise AdaptivePolicyPlanError(f"duplicate hard gate: {gate_id}")
        seen.add(gate_id)
        status = raw.get("status")
        if status not in {"pass", "fail"}:
            raise AdaptivePolicyPlanError(
                f"gate {gate_id}: status must be pass or fail"
            )
        reason = _nonempty(str(raw.get("reason", "")), f"gate {gate_id}.reason")
        result.append({"id": gate_id, "status": status, "reason": reason})
    if not result:
        raise AdaptivePolicyPlanError("at least one hard gate is required")
    return sorted(result, key=lambda item: item["id"])


def _normalize_choices(
    choices: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in choices:
        choice_id = _nonempty(str(raw.get("id", "")), "choice.id")
        if choice_id in seen:
            raise AdaptivePolicyPlanError(f"duplicate choice: {choice_id}")
        seen.add(choice_id)
        choice_class = _nonempty(
            str(raw.get("class", "")),
            f"choice {choice_id}.class",
        )
        reasons_raw = raw.get("reasons", [])
        if not isinstance(reasons_raw, list):
            raise AdaptivePolicyPlanError(
                f"choice {choice_id}.reasons must be a list"
            )
        reasons = [
            _nonempty(str(reason), f"choice {choice_id}.reason")
            for reason in reasons_raw
        ]
        metrics = raw.get("metrics", {})
        if not isinstance(metrics, dict):
            raise AdaptivePolicyPlanError(
                f"choice {choice_id}.metrics must be an object"
            )
        for key, value in metrics.items():
            _nonempty(str(key), f"choice {choice_id}.metric key")
            if value is not None and not isinstance(
                value, (str, int, float, bool)
            ):
                raise AdaptivePolicyPlanError(
                    f"choice {choice_id}.metrics values must be scalar"
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise AdaptivePolicyPlanError(
                    f"choice {choice_id}.metrics must be finite"
                )
        result.append(
            {
                "id": choice_id,
                "class": choice_class,
                "reasons": reasons,
                "metrics": dict(sorted(metrics.items())),
            }
        )
    return sorted(result, key=lambda item: item["id"])


def build_shadow_plan(
    *,
    repository: str,
    source_revision_sha: str,
    captured_at: str,
    subsystem: str,
    policy_id: str,
    policy_version: str,
    maturity: str,
    input_state: Any,
    input_refs: Sequence[str],
    hard_gates: Iterable[Mapping[str, Any]],
    eligible_choices: Iterable[Mapping[str, Any]],
    selected_choice_id: str | None,
    baseline_choice_id: str | None,
    selection_reasons: Sequence[str],
    exploration: bool = False,
    uncertainty: float | None = None,
    compute_units: float | None = None,
    review_units: float | None = None,
    human_attention_units: float | None = None,
    evidence_refs: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    repository = _nonempty(repository, "repository")
    source_revision_sha = _sha(source_revision_sha, "source_revision_sha")
    captured_at = _timestamp(captured_at, "captured_at")
    if subsystem not in SUBSYSTEMS:
        raise AdaptivePolicyPlanError(f"unknown subsystem: {subsystem}")
    policy_id = _nonempty(policy_id, "policy_id")
    policy_version = _nonempty(policy_version, "policy_version")
    if maturity not in MATURITY:
        raise AdaptivePolicyPlanError(
            "maturity must be one of N1, N2, N3"
        )

    gates = _normalize_gates(hard_gates)
    choices = _normalize_choices(eligible_choices)
    ids = {choice["id"] for choice in choices}
    all_gates_pass = all(gate["status"] == "pass" for gate in gates)

    if selected_choice_id is not None and selected_choice_id not in ids:
        raise AdaptivePolicyPlanError(
            "selected_choice_id must name an eligible choice"
        )
    if baseline_choice_id is not None and baseline_choice_id not in ids:
        raise AdaptivePolicyPlanError(
            "baseline_choice_id must name an eligible choice"
        )
    if not all_gates_pass and selected_choice_id is not None:
        raise AdaptivePolicyPlanError(
            "a failed hard gate requires selected_choice_id=null"
        )
    if all_gates_pass and selected_choice_id is None and choices:
        # A policy may explicitly abstain, but it has to say why.
        if not selection_reasons:
            raise AdaptivePolicyPlanError(
                "abstention with eligible choices requires a reason"
            )

    reasons = [
        _nonempty(str(reason), "selection reason")
        for reason in selection_reasons
    ]
    if not reasons:
        reasons = [
            "hard-gate-failure"
            if not all_gates_pass
            else "no-recommendation"
        ]

    limitations_list = [
        _nonempty(str(value), "limitation")
        for value in limitations
    ]
    if not limitations_list:
        raise AdaptivePolicyPlanError(
            "at least one limitation is required"
        )

    refs = sorted(
        {
            _nonempty(str(value), "input_ref")
            for value in input_refs
        }
    )
    evidence = sorted(
        {
            _nonempty(str(value), "evidence_ref")
            for value in evidence_refs
        }
    )

    try:
        input_digest = sha256_digest(input_state)
    except (TypeError, ValueError) as exc:
        raise AdaptivePolicyPlanError(
            "input_state must be strict JSON with finite numbers"
        ) from exc
    fingerprint = sha256_digest(
        {
            "repository": repository,
            "source_revision_sha": source_revision_sha,
            "captured_at": captured_at,
            "subsystem": subsystem,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "input_digest": input_digest,
            "gates": gates,
            "choices": choices,
        }
    ).split(":", 1)[1][:12]

    safe_policy_id = "".join(
        ch if ch.isalnum() or ch in "._-" else "-"
        for ch in policy_id.lower()
    ).strip("-")
    if not safe_policy_id:
        safe_policy_id = "policy"

    return {
        "schema_version": "0.1",
        "kind": "idkmesh-adaptive-policy-plan",
        "planner_version": PLANNER_VERSION,
        "mode": "shadow",
        "plan_id": f"adaptive-plan-{safe_policy_id}-{fingerprint}",
        "subsystem": subsystem,
        "binding": {
            "repository": repository,
            "source_revision_sha": source_revision_sha,
            "captured_at": captured_at,
            "input_digest": input_digest,
            "input_refs": refs,
        },
        "policy": {
            "id": policy_id,
            "version": policy_version,
            "maturity": maturity,
        },
        "hard_gates": gates,
        "eligible_choices": choices,
        "recommendation": {
            "selected_choice_id": selected_choice_id,
            "baseline_choice_id": baseline_choice_id,
            "exploration": bool(exploration),
            "reasons": reasons,
            "uncertainty": _unit_interval_or_none(
                uncertainty,
                "uncertainty",
            ),
            "expected_cost": {
                "project_spend_usd": 0,
                "compute_units": _cost_or_none(
                    compute_units,
                    "compute_units",
                ),
                "review_units": _cost_or_none(
                    review_units,
                    "review_units",
                ),
                "human_attention_units": _cost_or_none(
                    human_attention_units,
                    "human_attention_units",
                ),
            },
        },
        "evidence_refs": evidence,
        "limitations": limitations_list,
        "authority": {
            "advisory_only": True,
            "dispatch": False,
            "execute": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
            "relax_hard_gates": False,
            "modify_required_verification": False,
            "authorize_project_spend": False,
        },
    }
