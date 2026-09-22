#!/usr/bin/env python3
"""Build an AVE-core verifier-allocation shadow recommendation.

Research only. The adapter consumes canonical WorkUnit/EvaluatorPlan state plus
one point-in-time verifier observation pool and emits an Adaptive Policy Shadow
Plan. It never modifies the EvaluatorPlan or dispatches verification.

Reliability evidence is deliberately domain- and time-scoped. E025 showed that
learned verifier weighting can improve stable regimes and fail materially under
distribution shift, so stale/shifted/probe-only evidence is neutral rather than
positive trust.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from typing import Any, Iterable, Mapping, Sequence

try:
    from tools.adaptive_policy_shadow import build_shadow_plan
except ModuleNotFoundError:  # direct: python tools/ave_shadow_adapter.py
    from adaptive_policy_shadow import build_shadow_plan


POLICY_ID = "ave-core"
POLICY_VERSION = "0.1"
MAX_PORTFOLIOS = 50_000
RISK_FAMILY_FLOOR = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 3,
}


class AVEShadowAdapterError(RuntimeError):
    pass


def canonical_digest(value: Any) -> str:
    """Match IDKMesh WorkUnit/EvaluatorPlan canonical JSON digest semantics."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _parse_time(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AVEShadowAdapterError(f"{field} must be a non-empty timestamp")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        result = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AVEShadowAdapterError(
            f"{field} must be ISO-8601"
        ) from exc
    if result.tzinfo is None:
        raise AVEShadowAdapterError(f"{field} must include a timezone")
    return result.astimezone(timezone.utc)


def _normalized_pool(pool: Mapping[str, Any]) -> dict[str, Any]:
    """Canonicalize set-like pool arrays before policy hashing/replay."""
    result = dict(pool)
    normalized_candidates: list[dict[str, Any]] = []
    for raw in pool.get("verifier_candidates", []):
        candidate = dict(raw)
        candidate["supported_validator_ids"] = sorted(
            set(candidate.get("supported_validator_ids", []))
        )
        reliability = dict(candidate.get("reliability", {}))
        reliability["source_refs"] = sorted(
            set(reliability.get("source_refs", []))
        )
        candidate["reliability"] = reliability
        normalized_candidates.append(candidate)
    result["verifier_candidates"] = sorted(
        normalized_candidates,
        key=lambda candidate: str(candidate.get("id", "")),
    )
    result["limitations"] = sorted(
        set(str(value) for value in pool.get("limitations", []))
    )
    return result


def validate_verifier_pool(pool: Mapping[str, Any]) -> None:
    if pool.get("schema_version") != "0.1":
        raise AVEShadowAdapterError(
            "unsupported verifier observation pool schema_version"
        )
    if pool.get("kind") != "idkmesh-verifier-observation-pool":
        raise AVEShadowAdapterError(
            "unexpected verifier observation pool kind"
        )
    max_age = pool.get("reliability_max_age_days")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 1:
        raise AVEShadowAdapterError(
            "reliability_max_age_days must be a positive integer"
        )
    captured = _parse_time(pool.get("captured_at", ""), "captured_at")

    candidates = pool.get("verifier_candidates")
    if not isinstance(candidates, list) or not candidates:
        raise AVEShadowAdapterError(
            "verifier_candidates must be a non-empty list"
        )

    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise AVEShadowAdapterError(
                "verifier candidate must be an object"
            )
        verifier_id = candidate.get("id")
        if not isinstance(verifier_id, str) or not verifier_id:
            raise AVEShadowAdapterError(
                "verifier candidate id must be non-empty"
            )
        if verifier_id in seen:
            raise AVEShadowAdapterError(
                f"duplicate verifier candidate: {verifier_id}"
            )
        seen.add(verifier_id)

        family = candidate.get("family")
        if not isinstance(family, str) or not family:
            raise AVEShadowAdapterError(
                f"{verifier_id}: family must be non-empty"
            )

        validators = candidate.get("supported_validator_ids")
        if not isinstance(validators, list) or any(
            not isinstance(value, str) or not value
            for value in validators
        ):
            raise AVEShadowAdapterError(
                f"{verifier_id}: supported_validator_ids must be strings"
            )
        if len(set(validators)) != len(validators):
            raise AVEShadowAdapterError(
                f"{verifier_id}: supported_validator_ids must be unique"
            )

        for field in ("review_units", "queue_load"):
            value = candidate.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise AVEShadowAdapterError(
                    f"{verifier_id}: {field} must be finite and >= 0"
                )

        independence = candidate.get("independence")
        if not isinstance(independence, dict):
            raise AVEShadowAdapterError(
                f"{verifier_id}: independence must be an object"
            )
        for field in (
            "independent_from_worker",
            "shared_model_family",
            "shared_runtime",
        ):
            if not isinstance(independence.get(field), bool):
                raise AVEShadowAdapterError(
                    f"{verifier_id}: independence.{field} must be boolean"
                )

        reliability = candidate.get("reliability")
        if not isinstance(reliability, dict):
            raise AVEShadowAdapterError(
                f"{verifier_id}: reliability must be an object"
            )
        basis = reliability.get("basis")
        if basis not in {
            "live_outcomes",
            "known_bad_probes",
            "synthetic",
            "unknown",
        }:
            raise AVEShadowAdapterError(
                f"{verifier_id}: unsupported reliability basis"
            )
        for field in ("alpha", "beta"):
            value = reliability.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 1
            ):
                raise AVEShadowAdapterError(
                    f"{verifier_id}: reliability.{field} must be >= 1"
                )
        sample_count = reliability.get("sample_count")
        if (
            isinstance(sample_count, bool)
            or not isinstance(sample_count, int)
            or sample_count < 0
        ):
            raise AVEShadowAdapterError(
                f"{verifier_id}: reliability.sample_count must be >= 0"
            )
        if not isinstance(reliability.get("shift_warning"), bool):
            raise AVEShadowAdapterError(
                f"{verifier_id}: reliability.shift_warning must be boolean"
            )

        trials = reliability.get("known_bad_probe_trials")
        breaches = reliability.get("known_bad_probe_breaches")
        if (
            isinstance(trials, bool)
            or not isinstance(trials, int)
            or trials < 0
            or isinstance(breaches, bool)
            or not isinstance(breaches, int)
            or breaches < 0
            or breaches > trials
        ):
            raise AVEShadowAdapterError(
                f"{verifier_id}: invalid known-bad probe counts"
            )

        observed_at = reliability.get("observed_at")
        if observed_at is not None:
            observed = _parse_time(
                observed_at,
                f"{verifier_id}.reliability.observed_at",
            )
            if observed > captured:
                raise AVEShadowAdapterError(
                    f"{verifier_id}: reliability evidence is future-dated"
                )


def _required_validator_ids(work_unit: Mapping[str, Any]) -> set[str]:
    validators = work_unit.get("validators", [])
    if not isinstance(validators, list):
        return set()
    return {
        str(item.get("id"))
        for item in validators
        if isinstance(item, dict)
        and item.get("required") is True
        and isinstance(item.get("id"), str)
        and item.get("id")
    }


def _gate(gate_id: str, passed: bool, reason: str) -> dict[str, str]:
    return {
        "id": gate_id,
        "status": "pass" if passed else "fail",
        "reason": reason,
    }


def _hard_gates(
    *,
    repository: str,
    work_unit: Mapping[str, Any],
    evaluator_plan: Mapping[str, Any],
    pool: Mapping[str, Any],
) -> tuple[list[dict[str, str]], set[str]]:
    binding = evaluator_plan.get("binding", {})
    plan_policy = evaluator_plan.get("policy", {})
    required = _required_validator_ids(work_unit)
    plan_required_raw = evaluator_plan.get("required_validator_ids", [])
    plan_required = (
        set(str(value) for value in plan_required_raw)
        if isinstance(plan_required_raw, list)
        else set()
    )

    wu_schema_ok = work_unit.get("schema_version") == "0.2"
    digest = canonical_digest(work_unit)
    digest_ok = binding.get("work_unit_digest") == digest
    id_version_ok = (
        binding.get("work_unit_id") == work_unit.get("id")
        and binding.get("work_unit_version") == work_unit.get("version")
    )
    source = work_unit.get("provenance", {}).get("source_revision")
    source_ok = (
        isinstance(source, str)
        and len(source) == 40
        and source == binding.get("source_revision")
        and source == pool.get("source_revision")
    )
    pool_ok = (
        pool.get("repository") == repository
        and pool.get("work_unit_id") == work_unit.get("id")
    )
    sovereignty_ok = (
        plan_policy.get("require_verifier_distinct_from_worker") is True
    )
    budget = work_unit.get("budget", {})
    project_spend = budget.get("project_spend_usd_max")
    zero_spend_ok = (
        not isinstance(project_spend, bool)
        and isinstance(project_spend, (int, float))
        and math.isfinite(float(project_spend))
        and float(project_spend) == 0.0
        and budget.get("paid_fallback_allowed") is False
    )
    verification = work_unit.get("verification_policy", {})
    independent_policy_ok = (
        verification.get("independent_from_worker") is True
    )
    validator_binding_ok = required.issubset(plan_required)

    gates = [
        _gate(
            "work-unit-v0.2",
            wu_schema_ok,
            "WorkUnit schema_version is 0.2"
            if wu_schema_ok
            else "AVE shadow adapter currently supports WorkUnit v0.2 only",
        ),
        _gate(
            "exact-work-unit-digest",
            digest_ok,
            "EvaluatorPlan is bound to the exact canonical WorkUnit digest"
            if digest_ok
            else "EvaluatorPlan WorkUnit digest does not match",
        ),
        _gate(
            "work-unit-id-version-binding",
            id_version_ok,
            "EvaluatorPlan WorkUnit id/version match"
            if id_version_ok
            else "EvaluatorPlan WorkUnit id/version mismatch",
        ),
        _gate(
            "source-revision-binding",
            source_ok,
            "WorkUnit, EvaluatorPlan, and verifier pool share one exact source revision"
            if source_ok
            else "source revision binding is missing or inconsistent",
        ),
        _gate(
            "verifier-pool-binding",
            pool_ok,
            "verifier pool repository/WorkUnit binding matches"
            if pool_ok
            else "verifier pool repository/WorkUnit binding mismatch",
        ),
        _gate(
            "evaluator-sovereignty",
            sovereignty_ok,
            "EvaluatorPlan requires verifier distinct from worker"
            if sovereignty_ok
            else "EvaluatorPlan does not preserve verifier/worker separation",
        ),
        _gate(
            "zero-project-spend",
            zero_spend_ok,
            "WorkUnit preserves the repository zero-project-spend lane"
            if zero_spend_ok
            else "WorkUnit requests a non-zero or paid-fallback lane",
        ),
        _gate(
            "independent-verification-policy",
            independent_policy_ok,
            "WorkUnit requires independent verification"
            if independent_policy_ok
            else "WorkUnit does not require verifier independence",
        ),
        _gate(
            "required-validator-binding",
            validator_binding_ok,
            "EvaluatorPlan covers every WorkUnit-required validator"
            if validator_binding_ok
            else "EvaluatorPlan omits a WorkUnit-required validator",
        ),
    ]
    return gates, required.union(plan_required)


def _is_hard_eligible(
    candidate: Mapping[str, Any],
    independent_required: bool,
) -> bool:
    if candidate.get("available") is not True:
        return False
    if independent_required and candidate.get("independence", {}).get(
        "independent_from_worker"
    ) is not True:
        return False
    return True


def _probe_breached(candidate: Mapping[str, Any]) -> bool:
    return (
        int(
            candidate.get("reliability", {}).get(
                "known_bad_probe_breaches",
                0,
            )
        )
        > 0
    )


def _reliability_evidence(
    candidate: Mapping[str, Any],
    pool: Mapping[str, Any],
) -> dict[str, Any]:
    reliability = candidate["reliability"]
    captured = _parse_time(pool["captured_at"], "captured_at")
    observed_raw = reliability.get("observed_at")
    fresh = False
    age_days: float | None = None
    if observed_raw is not None:
        observed = _parse_time(
            observed_raw,
            f"{candidate['id']}.reliability.observed_at",
        )
        age_days = (captured - observed).total_seconds() / 86400.0
        fresh = (
            age_days >= 0
            and age_days <= int(pool["reliability_max_age_days"])
        )

    supported = (
        reliability.get("basis") == "live_outcomes"
        and reliability.get("domain") == pool.get("task_domain")
        and reliability.get("shift_warning") is False
        and int(reliability.get("sample_count", 0)) > 0
        and fresh
    )
    mean = (
        float(reliability["alpha"])
        / (float(reliability["alpha"]) + float(reliability["beta"]))
        if supported
        else 0.5
    )
    samples = int(reliability.get("sample_count", 0)) if supported else 0
    uncertainty = (
        min(1.0, 1.0 / math.sqrt(samples + 1))
        if supported
        else 1.0
    )
    return {
        "supported": supported,
        "mean": mean,
        "samples": samples,
        "uncertainty": uncertainty,
        "fresh": fresh,
        "age_days": age_days,
    }


def _candidate_reason(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[str]:
    reasons = [
        f"verifier-family:{candidate['family']}",
        (
            "live-outcome-reliability-supported"
            if evidence["supported"]
            else "reliability-neutral-no-current-domain-live-outcome-support"
        ),
    ]
    independence = candidate["independence"]
    if independence.get("shared_model_family"):
        reasons.append("shared-model-family-correlation-signal")
    if independence.get("shared_runtime"):
        reasons.append("shared-runtime-correlation-signal")
    if _probe_breached(candidate):
        reasons.append("known-bad-probe-breach")
    return reasons


def _portfolio_metrics(
    candidates: Sequence[Mapping[str, Any]],
    pool: Mapping[str, Any],
    required_validators: set[str],
) -> dict[str, Any]:
    evidence = [_reliability_evidence(candidate, pool) for candidate in candidates]
    families = {str(candidate["family"]) for candidate in candidates}
    coverage = set().union(
        *(
            set(candidate.get("supported_validator_ids", []))
            for candidate in candidates
        )
    ) if candidates else set()
    supported = [value for value in evidence if value["supported"]]
    mean_reliability = (
        sum(float(value["mean"]) for value in evidence) / len(evidence)
        if evidence
        else 0.5
    )
    uncertainty = (
        sum(float(value["uncertainty"]) for value in evidence) / len(evidence)
        if evidence
        else 1.0
    )
    correlation_penalty = sum(
        int(candidate["independence"].get("shared_model_family") is True)
        + int(candidate["independence"].get("shared_runtime") is True)
        for candidate in candidates
    )
    return {
        "family_count": len(families),
        "live_supported_count": len(supported),
        "live_sample_count": sum(
            int(value["samples"]) for value in evidence
        ),
        "mean_reliability": mean_reliability,
        "uncertainty": uncertainty,
        "correlation_penalty": correlation_penalty,
        "review_units": sum(float(candidate["review_units"]) for candidate in candidates),
        "queue_load": sum(float(candidate["queue_load"]) for candidate in candidates),
        "required_validator_coverage": len(required_validators.intersection(coverage)),
        "covers_all_required_validators": required_validators.issubset(coverage),
        "probe_breach_count": sum(
            int(_probe_breached(candidate)) for candidate in candidates
        ),
    }


def _portfolio_selection_key(
    candidates: Sequence[Mapping[str, Any]],
    pool: Mapping[str, Any],
    required_validators: set[str],
) -> tuple[Any, ...]:
    metrics = _portfolio_metrics(candidates, pool, required_validators)
    ids = tuple(sorted(str(candidate["id"]) for candidate in candidates))
    return (
        -int(metrics["family_count"]),
        int(metrics["correlation_penalty"]),
        -int(metrics["live_supported_count"]),
        -int(metrics["live_sample_count"]),
        -float(metrics["mean_reliability"]),
        float(metrics["review_units"]),
        float(metrics["queue_load"]),
        ids,
    )


def _risk_target(work_unit: Mapping[str, Any]) -> int:
    verification = work_unit.get("verification_policy", {})
    minimum = verification.get("minimum_independent_verifiers", 0)
    if isinstance(minimum, bool) or not isinstance(minimum, int):
        minimum = 0
    risk = work_unit.get("security", {}).get("risk_class", "low")
    return max(minimum, RISK_FAMILY_FLOOR.get(str(risk), 1))


def _portfolio_choice(
    candidates: Sequence[Mapping[str, Any]],
    pool: Mapping[str, Any],
    required_validators: set[str],
) -> dict[str, Any]:
    metrics = _portfolio_metrics(candidates, pool, required_validators)
    ids = sorted(str(candidate["id"]) for candidate in candidates)
    reasons: list[str] = [
        f"verifier-count:{len(candidates)}",
        f"distinct-families:{metrics['family_count']}",
        f"required-validator-coverage:{metrics['required_validator_coverage']}/{len(required_validators)}",
    ]
    for candidate in sorted(candidates, key=lambda value: str(value["id"])):
        reasons.extend(
            f"{candidate['id']}:{reason}"
            for reason in _candidate_reason(
                candidate,
                _reliability_evidence(candidate, pool),
            )
        )
    return {
        "id": "portfolio:" + "+".join(ids),
        "class": "verifier-portfolio",
        "reasons": reasons,
        "metrics": {
            "verifier_count": len(candidates),
            "family_count": metrics["family_count"],
            "live_supported_count": metrics["live_supported_count"],
            "live_sample_count": metrics["live_sample_count"],
            "mean_reliability": round(float(metrics["mean_reliability"]), 9),
            "correlation_penalty": metrics["correlation_penalty"],
            "review_units": round(float(metrics["review_units"]), 9),
            "queue_load": round(float(metrics["queue_load"]), 9),
            "probe_breach_count": metrics["probe_breach_count"],
        },
    }


def _baseline_choice(
    evaluator_plan: Mapping[str, Any],
    candidate_by_id: Mapping[str, Mapping[str, Any]],
    pool: Mapping[str, Any],
) -> dict[str, Any]:
    verifier = evaluator_plan.get("verifier", {})
    verifier_id = str(verifier.get("id") or "unknown-verifier")
    candidate = candidate_by_id.get(verifier_id)
    reasons = [
        "current-evaluator-plan-baseline",
        f"evaluator-plan:{evaluator_plan.get('id', 'unknown-plan')}",
        f"verifier:{verifier_id}",
    ]
    metrics: dict[str, Any] = {
        "verifier_count": 1,
        "family_count": 1 if candidate is not None else 0,
        "review_units": (
            round(float(candidate["review_units"]), 9)
            if candidate is not None
            else None
        ),
        "queue_load": (
            round(float(candidate["queue_load"]), 9)
            if candidate is not None
            else None
        ),
        "reliability_basis": (
            candidate["reliability"]["basis"]
            if candidate is not None
            else "unobserved"
        ),
    }
    if candidate is not None:
        reasons.extend(
            _candidate_reason(
                candidate,
                _reliability_evidence(candidate, pool),
            )
        )
    else:
        reasons.append("baseline-verifier-not-present-in-observation-pool")
    return {
        "id": "baseline:evaluator-plan:" + str(
            evaluator_plan.get("id", "unknown-plan")
        ),
        "class": "current-evaluator-plan",
        "reasons": reasons,
        "metrics": metrics,
    }


def build_ave_shadow_plan(
    *,
    repository: str,
    work_unit: Mapping[str, Any],
    evaluator_plan: Mapping[str, Any],
    verifier_pool: Mapping[str, Any],
    maturity: str = "N2",
    input_refs: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    validate_verifier_pool(verifier_pool)
    normalized_pool = _normalized_pool(verifier_pool)
    gates, required_validators = _hard_gates(
        repository=repository,
        work_unit=work_unit,
        evaluator_plan=evaluator_plan,
        pool=normalized_pool,
    )
    hard_pass = all(gate["status"] == "pass" for gate in gates)

    independent_required = (
        work_unit.get("verification_policy", {}).get(
            "independent_from_worker"
        )
        is True
    )
    candidates = [
        candidate
        for candidate in normalized_pool["verifier_candidates"]
        if _is_hard_eligible(candidate, independent_required)
    ]
    candidate_by_id = {
        str(candidate["id"]): candidate for candidate in candidates
    }
    baseline = _baseline_choice(
        evaluator_plan,
        candidate_by_id,
        normalized_pool,
    )
    choices: list[dict[str, Any]] = [baseline]

    target = _risk_target(work_unit)
    selection_candidates = [
        candidate
        for candidate in candidates
        if not _probe_breached(candidate)
    ]

    selected_choice_id: str | None = None
    selected_metrics: dict[str, Any] | None = None
    selection_reasons: list[str] = []
    exploration = False

    if not hard_pass:
        selection_reasons.append(
            "AVE-core abstains because one or more hard gates failed"
        )
    elif len(selection_candidates) < target:
        selection_reasons.append(
            f"AVE-core abstains: {len(selection_candidates)} eligible non-breached verifiers < target {target}"
        )
    else:
        combinations = math.comb(len(selection_candidates), target)
        if combinations > MAX_PORTFOLIOS:
            selection_reasons.append(
                f"AVE-core abstains: portfolio search space {combinations} exceeds safety limit {MAX_PORTFOLIOS}"
            )
        else:
            viable: list[tuple[Mapping[str, Any], ...]] = []
            for combo in itertools.combinations(selection_candidates, target):
                metrics = _portfolio_metrics(
                    combo,
                    normalized_pool,
                    required_validators,
                )
                if not metrics["covers_all_required_validators"]:
                    continue
                # AVE-core is explicitly testing family diversity as a
                # correlated-failure heuristic. A shortfall causes shadow
                # abstention rather than weakening the requested portfolio.
                if int(metrics["family_count"]) < target:
                    continue
                viable.append(combo)

            if not viable:
                selection_reasons.append(
                    "AVE-core abstains: no target-sized family-diverse portfolio covers all required validators"
                )
            else:
                viable.sort(
                    key=lambda combo: _portfolio_selection_key(
                        combo,
                        normalized_pool,
                        required_validators,
                    )
                )
                # Keep the full viable choice set for audit when small enough.
                for combo in viable:
                    choices.append(
                        _portfolio_choice(
                            combo,
                            normalized_pool,
                            required_validators,
                        )
                    )
                best = viable[0]
                best_choice = _portfolio_choice(
                    best,
                    normalized_pool,
                    required_validators,
                )
                selected_choice_id = best_choice["id"]
                selected_metrics = _portfolio_metrics(
                    best,
                    normalized_pool,
                    required_validators,
                )
                selection_reasons.extend(
                    [
                        f"risk-adaptive-target:{target}",
                        "lexicographic-order:family-diversity,correlation-signals,live-domain-evidence,reliability,review-cost,queue-load",
                        "known-bad-probe-passes-do-not-create-positive-reliability",
                        "known-bad-probe-breaches-excluded-from-shadow-selection",
                    ]
                )

    expected_review = (
        float(selected_metrics["review_units"])
        if selected_metrics is not None
        else None
    )
    uncertainty = (
        float(selected_metrics["uncertainty"])
        if selected_metrics is not None
        else None
    )

    refs = list(evidence_refs)
    refs.extend(
        [
            "experiments/E025-learned-verifier-reliability.md",
            "experiments/AVE-2-adversarial-matrix.md",
        ]
    )
    limitations = list(normalized_pool.get("limitations", []))
    limitations.extend(
        [
            "Verifier family labels are routing heuristics, not proof of statistical independence.",
            "Only fresh same-domain live-outcome reliability can positively influence AVE ordering.",
            "Probe-only or synthetic reliability is neutral; a known-bad probe breach can veto AVE shadow selection.",
            "This plan is advisory only and does not modify the canonical EvaluatorPlan.",
        ]
    )

    input_state = {
        "work_unit": work_unit,
        "evaluator_plan": evaluator_plan,
        "verifier_observation_pool": normalized_pool,
        "ave_policy_version": POLICY_VERSION,
    }

    return build_shadow_plan(
        repository=repository,
        source_revision_sha=str(normalized_pool["source_revision"]),
        subsystem="verification-allocation",
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        maturity=maturity,
        input_state=input_state,
        input_refs=list(input_refs),
        hard_gates=gates,
        eligible_choices=choices,
        selected_choice_id=selected_choice_id,
        baseline_choice_id=baseline["id"],
        selection_reasons=selection_reasons,
        exploration=exploration,
        uncertainty=uncertainty,
        compute_units=0.0,
        review_units=expected_review,
        human_attention_units=None,
        evidence_refs=refs,
        limitations=limitations,
    )
