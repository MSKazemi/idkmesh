#!/usr/bin/env python3
"""Summarize an adaptive-policy shadow cohort without causal overclaiming."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from tools.adaptive_policy_outcome import sha256_digest


EVALUATOR_VERSION = "0.1"


class AdaptivePolicyCohortError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 9)


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 9)


def _coverage(observed: int, total: int) -> dict[str, Any]:
    return {
        "observed": observed,
        "total": total,
        "rate": _rate(observed, total),
    }


def summarize_cohort(
    *,
    plans: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    limitations: Sequence[str],
) -> dict[str, Any]:
    plan_list = [dict(plan) for plan in plans]
    outcome_list = [dict(outcome) for outcome in outcomes]

    plan_map: dict[str, dict[str, Any]] = {}
    for plan in plan_list:
        if plan.get("kind") != "idkmesh-adaptive-policy-plan":
            raise AdaptivePolicyCohortError(
                "all plans must be adaptive-policy shadow plans"
            )
        plan_id = plan.get("plan_id")
        if not isinstance(plan_id, str) or not plan_id:
            raise AdaptivePolicyCohortError("plan_id is required")
        if plan_id in plan_map:
            raise AdaptivePolicyCohortError(
                f"duplicate plan_id: {plan_id}"
            )
        plan_map[plan_id] = plan

    outcome_map: dict[str, dict[str, Any]] = {}
    for outcome in outcome_list:
        if outcome.get("kind") != "idkmesh-adaptive-policy-outcome":
            raise AdaptivePolicyCohortError(
                "all outcomes must be adaptive-policy outcome records"
            )
        plan_id = outcome.get("plan_id")
        if plan_id not in plan_map:
            raise AdaptivePolicyCohortError(
                f"outcome references unknown plan: {plan_id}"
            )
        if plan_id in outcome_map:
            raise AdaptivePolicyCohortError(
                f"duplicate outcome for plan: {plan_id}"
            )
        expected_digest = sha256_digest(plan_map[plan_id])
        if outcome.get("plan_digest") != expected_digest:
            raise AdaptivePolicyCohortError(
                f"plan digest mismatch: {plan_id}"
            )
        if outcome.get("comparison", {}).get(
            "shadow_counterfactual_observed"
        ) is not False:
            raise AdaptivePolicyCohortError(
                "shadow counterfactual must remain unobserved"
            )
        if outcome.get("comparison", {}).get(
            "causal_claim_allowed"
        ) is not False:
            raise AdaptivePolicyCohortError(
                "shadow cohort cannot allow causal claims"
            )
        outcome_map[plan_id] = outcome

    limitation_list = [
        str(value)
        for value in limitations
        if isinstance(value, str) and value
    ]
    if not limitation_list:
        raise AdaptivePolicyCohortError(
            "at least one limitation is required"
        )

    joined_ids = sorted(set(plan_map).intersection(outcome_map))
    joined = [outcome_map[plan_id] for plan_id in joined_ids]

    comparable = disagree = 0
    shadow_matches_actual = baseline_matches_actual = neither = 0
    known_outcomes = successful = 0
    escape_observed = escaped = 0
    high_risk_observed = high_risk_escapes = 0
    utilities: list[float] = []

    coverage_values = {
        "verified_utility": 0,
        "escaped_defect": 0,
        "high_risk_escape": 0,
        "project_spend_usd": 0,
        "compute_units": 0,
        "review_units": 0,
        "human_attention_units": 0,
    }

    for plan_id in joined_ids:
        plan = plan_map[plan_id]
        outcome = outcome_map[plan_id]
        shadow = plan["recommendation"]["selected_choice_id"]
        baseline = plan["recommendation"]["baseline_choice_id"]
        actual = outcome["observed_process"]["actual_choice_id"]

        if shadow is not None and baseline is not None:
            comparable += 1
            disagree += int(shadow != baseline)

        if actual is not None:
            shadow_match = shadow is not None and actual == shadow
            baseline_match = baseline is not None and actual == baseline
            shadow_matches_actual += int(shadow_match)
            baseline_matches_actual += int(baseline_match)
            neither += int(not shadow_match and not baseline_match)

        observed = outcome["observed_process"]
        status = observed["outcome"]
        if status != "unknown":
            known_outcomes += 1
            successful += int(status == "succeeded")

        utility = observed.get("verified_utility")
        if utility is not None:
            coverage_values["verified_utility"] += 1
            utilities.append(float(utility))

        defect = observed.get("escaped_defect")
        if defect is not None:
            coverage_values["escaped_defect"] += 1
            escape_observed += 1
            escaped += int(defect)

        high_risk = observed.get("high_risk_escape")
        if high_risk is not None:
            coverage_values["high_risk_escape"] += 1
            high_risk_observed += 1
            high_risk_escapes += int(high_risk)

        actual_cost = observed.get("actual_cost", {})
        for field in (
            "project_spend_usd",
            "compute_units",
            "review_units",
            "human_attention_units",
        ):
            if actual_cost.get(field) is not None:
                coverage_values[field] += 1

    policy_ids = sorted(
        {
            str(plan["policy"]["id"])
            for plan in plan_list
        }
    )
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "plans": sorted(plan_map),
                "outcomes": sorted(outcome_map),
                "plan_digests": {
                    plan_id: sha256_digest(plan_map[plan_id])
                    for plan_id in sorted(plan_map)
                },
            }
        )
    ).hexdigest()[:12]

    total_joined = len(joined)
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-adaptive-policy-cohort-summary",
        "evaluator_version": EVALUATOR_VERSION,
        "summary_id": f"adaptive-cohort-{fingerprint}",
        "policy_ids": policy_ids,
        "counts": {
            "plans": len(plan_list),
            "outcomes": len(outcome_list),
            "joined": total_joined,
            "missing_outcomes": len(plan_list) - total_joined,
            "duplicate_outcomes_rejected": 0,
        },
        "disagreement": {
            "shadow_vs_baseline_comparable": comparable,
            "shadow_vs_baseline_disagree": disagree,
            "shadow_vs_baseline_disagreement_rate": _rate(
                disagree,
                comparable,
            ),
            "shadow_matches_actual": shadow_matches_actual,
            "baseline_matches_actual": baseline_matches_actual,
            "neither_matches_actual": neither,
        },
        "observed_outcomes": {
            "known_outcomes": known_outcomes,
            "successful": successful,
            "success_rate": _rate(successful, known_outcomes),
            "escaped_defects": escaped,
            "escaped_defect_rate": _rate(
                escaped,
                escape_observed,
            ),
            "high_risk_escapes": high_risk_escapes,
            "high_risk_escape_rate": _rate(
                high_risk_escapes,
                high_risk_observed,
            ),
            "mean_verified_utility": _mean(utilities),
        },
        "measurement_coverage": {
            field: _coverage(count, total_joined)
            for field, count in coverage_values.items()
        },
        "identifiability": {
            "descriptive_only": True,
            "shadow_counterfactual_observed": False,
            "causal_effect_estimate": None,
            "promotion_decision_automatic": False,
        },
        "limitations": limitation_list,
        "authority": {
            "evidence_only": True,
            "dispatch": False,
            "execute": False,
            "approve": False,
            "merge": False,
            "repository_write": False,
        },
    }
