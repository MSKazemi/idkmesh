#!/usr/bin/env python3
"""Join an observed real-process outcome to an immutable shadow policy plan.

This helper does not estimate the unexecuted shadow counterfactual. It records
what actually happened and whether the shadow/baseline choices matched it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Sequence


EVALUATOR_VERSION = "0.1"
OUTCOMES = {"succeeded", "failed", "rejected", "abstained", "unknown"}


class AdaptivePolicyOutcomeError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _timestamp(value: str, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value:
        raise AdaptivePolicyOutcomeError(
            f"{field} must be a non-empty ISO-8601 timestamp"
        )
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AdaptivePolicyOutcomeError(
            f"{field} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise AdaptivePolicyOutcomeError(
            f"{field} must include a timezone"
        )
    utc = parsed.astimezone(timezone.utc)
    return (
        utc.isoformat().replace("+00:00", "Z"),
        utc,
    )


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdaptivePolicyOutcomeError(f"{field} must not be empty")
    return value


def _non_negative_or_none(
    value: float | None,
    field: str,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdaptivePolicyOutcomeError(
            f"{field} must be numeric or null"
        )
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise AdaptivePolicyOutcomeError(
            f"{field} must be finite and >= 0"
        )
    return result


def build_outcome_record(
    *,
    plan: dict[str, Any],
    actual_choice_id: str | None,
    observed_at: str,
    outcome: str,
    verified_utility: float | None = None,
    escaped_defect: bool | None = None,
    high_risk_escape: bool | None = None,
    project_spend_usd: float | None = None,
    compute_units: float | None = None,
    review_units: float | None = None,
    human_attention_units: float | None = None,
    evidence_refs: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    if plan.get("kind") != "idkmesh-adaptive-policy-plan":
        raise AdaptivePolicyOutcomeError(
            "plan must be an adaptive-policy shadow plan"
        )
    if plan.get("mode") != "shadow":
        raise AdaptivePolicyOutcomeError("plan mode must be shadow")

    authority = plan.get("authority", {})
    required_false = (
        "dispatch",
        "execute",
        "approve",
        "merge",
        "repository_write",
        "relax_hard_gates",
        "modify_required_verification",
        "authorize_project_spend",
    )
    if not authority.get("advisory_only"):
        raise AdaptivePolicyOutcomeError(
            "plan must be advisory_only"
        )
    if any(authority.get(field) is not False for field in required_false):
        raise AdaptivePolicyOutcomeError(
            "plan contains non-shadow authority"
        )

    if outcome not in OUTCOMES:
        raise AdaptivePolicyOutcomeError(f"unknown outcome: {outcome}")

    observed_at, observed_dt = _timestamp(
        observed_at,
        "observed_at",
    )
    captured_raw = plan.get("binding", {}).get("captured_at")
    captured_at, captured_dt = _timestamp(
        captured_raw,
        "plan.binding.captured_at",
    )
    if observed_dt < captured_dt:
        raise AdaptivePolicyOutcomeError(
            "observed_at cannot be earlier than plan captured_at"
        )

    selected = plan["recommendation"]["selected_choice_id"]
    baseline = plan["recommendation"]["baseline_choice_id"]
    eligible_ids = {
        choice["id"]
        for choice in plan.get("eligible_choices", [])
    }
    if actual_choice_id is not None and actual_choice_id not in eligible_ids:
        raise AdaptivePolicyOutcomeError(
            "actual_choice_id must name a choice frozen in the plan"
        )

    if escaped_defect is not None and not isinstance(
        escaped_defect, bool
    ):
        raise AdaptivePolicyOutcomeError(
            "escaped_defect must be boolean or null"
        )
    if high_risk_escape is not None and not isinstance(
        high_risk_escape, bool
    ):
        raise AdaptivePolicyOutcomeError(
            "high_risk_escape must be boolean or null"
        )
    if high_risk_escape is True and escaped_defect is not True:
        raise AdaptivePolicyOutcomeError(
            "high_risk_escape=true requires escaped_defect=true"
        )

    limitations_list = [
        _nonempty(str(value), "limitation")
        for value in limitations
    ]
    if not limitations_list:
        raise AdaptivePolicyOutcomeError(
            "at least one limitation is required"
        )

    evidence = sorted(
        {
            _nonempty(str(value), "evidence_ref")
            for value in evidence_refs
        }
    )

    plan_digest = sha256_digest(plan)
    fingerprint = sha256_digest(
        {
            "plan_digest": plan_digest,
            "actual_choice_id": actual_choice_id,
            "observed_at": observed_at,
            "outcome": outcome,
            "evidence_refs": evidence,
        }
    ).split(":", 1)[1][:12]

    plan_suffix = hashlib.sha256(
        plan["plan_id"].encode("utf-8")
    ).hexdigest()[:12]

    return {
        "schema_version": "0.1",
        "kind": "idkmesh-adaptive-policy-outcome",
        "evaluator_version": EVALUATOR_VERSION,
        "record_id": (
            f"adaptive-outcome-{plan_suffix}-{fingerprint}"
        ),
        "plan_id": plan["plan_id"],
        "plan_digest": plan_digest,
        "binding": {
            "repository": plan["binding"]["repository"],
            "source_revision_sha": (
                plan["binding"]["source_revision_sha"]
            ),
            "input_digest": plan["binding"]["input_digest"],
        },
        "observed_process": {
            "actual_choice_id": actual_choice_id,
            "outcome": outcome,
            "verified_utility": _non_negative_or_none(
                verified_utility,
                "verified_utility",
            ),
            "escaped_defect": escaped_defect,
            "high_risk_escape": high_risk_escape,
            "actual_cost": {
                "project_spend_usd": _non_negative_or_none(
                    project_spend_usd,
                    "project_spend_usd",
                ),
                "compute_units": _non_negative_or_none(
                    compute_units,
                    "compute_units",
                ),
                "review_units": _non_negative_or_none(
                    review_units,
                    "review_units",
                ),
                "human_attention_units": _non_negative_or_none(
                    human_attention_units,
                    "human_attention_units",
                ),
            },
        },
        "comparison": {
            "shadow_choice_id": selected,
            "baseline_choice_id": baseline,
            "shadow_matches_actual": (
                None
                if actual_choice_id is None or selected is None
                else actual_choice_id == selected
            ),
            "baseline_matches_actual": (
                None
                if actual_choice_id is None or baseline is None
                else actual_choice_id == baseline
            ),
            "shadow_counterfactual_observed": False,
            "causal_claim_allowed": False,
        },
        "evidence_refs": evidence,
        "limitations": limitations_list,
        "authority": {
            "evidence_only": True,
            "dispatch": False,
            "execute": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
        },
    }
