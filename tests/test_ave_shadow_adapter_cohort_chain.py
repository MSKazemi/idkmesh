"""AVE shadow plan -> outcome join -> cohort summary: anti-hindsight chain.

Every fixture here is synthetic. These tests pin *compatibility* of the AVE
adapter with the generic adaptive-policy outcome and cohort contracts and the
temporal/digest rules that keep a frozen plan free of hindsight. They are not
N3 evidence and say nothing about whether AVE helps (refs #644).
"""
from __future__ import annotations

import copy
import json
import unittest
from typing import Any

from tools.adaptive_policy_cohort import (
    AdaptivePolicyCohortError,
    summarize_cohort,
)
from tools.adaptive_policy_outcome import (
    AdaptivePolicyOutcomeError,
    build_outcome_record,
)
from tools.ave_shadow_adapter import (
    AVEShadowAdapterError,
    build_ave_shadow_plan,
    canonical_digest,
)

SOURCE = "4" * 40
CAPTURED = "2026-09-22T12:00:00Z"
BASELINE_ID = "baseline:evaluator-plan:verification/chain-plan"
LIMITS = ["synthetic chain fixture; not N3 evidence"]


def work_unit(index: int = 0, risk: str = "medium") -> dict[str, Any]:
    return {
        "schema_version": "0.2",
        "id": f"chain/work-unit-{index}",
        "version": 1,
        "kind": "testing",
        "security": {"risk_class": risk},
        "budget": {
            "project_spend_usd_max": 0,
            "paid_fallback_allowed": False,
        },
        "verification_policy": {
            "strategy": "all_required",
            "independent_from_worker": True,
            "minimum_independent_verifiers": 1,
        },
        "validators": [
            {"id": "schema-check", "type": "schema", "required": True}
        ],
        "provenance": {"source_revision": SOURCE},
    }


def evaluator_plan(wu: dict[str, Any], verifier_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.4",
        "id": "verification/chain-plan",
        "binding": {
            "work_unit_id": wu["id"],
            "work_unit_version": wu["version"],
            "work_unit_digest": canonical_digest(wu),
            "source_revision": SOURCE,
        },
        "verifier": {
            "id": verifier_id,
            "type": "system",
            "adapter": "test",
            "adapter_version": "1",
        },
        "required_validator_ids": ["schema-check"],
        "policy": {"require_verifier_distinct_from_worker": True},
    }


def candidate(verifier_id: str, family: str) -> dict[str, Any]:
    return {
        "id": verifier_id,
        "family": family,
        "provider_family": None,
        "available": True,
        "supported_validator_ids": ["schema-check"],
        "review_units": 1,
        "queue_load": 0,
        "independence": {
            "independent_from_worker": True,
            "shared_model_family": False,
            "shared_runtime": False,
        },
        "reliability": {
            "basis": "live_outcomes",
            "alpha": 6,
            "beta": 4,
            "sample_count": 8,
            "domain": "testing",
            "observed_at": "2026-09-21T12:00:00Z",
            "shift_warning": False,
            "source_refs": ["live-history"],
            "known_bad_probe_trials": 2,
            "known_bad_probe_breaches": 0,
        },
    }


def pool(
    wu: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-verifier-observation-pool",
        "repository": "MSKazemi/idkmesh",
        "source_revision": SOURCE,
        "captured_at": CAPTURED,
        "work_unit_id": wu["id"],
        "task_domain": "testing",
        "worker_id": "worker-1",
        "reliability_max_age_days": 30,
        "verifier_candidates": candidates,
        "limitations": ["synthetic fixture only"],
    }


def freeze(
    index: int = 0,
    *,
    risk: str = "medium",
    baseline_verifier: str = "legacy-verifier",
    candidates: list[dict[str, Any]] | None = None,
    break_work_unit_digest: bool = False,
) -> dict[str, Any]:
    wu = work_unit(index, risk)
    cands = candidates or [
        candidate("alpha", "family-a"),
        candidate("beta", "family-b"),
    ]
    ep = evaluator_plan(wu, baseline_verifier)
    if break_work_unit_digest:
        ep["binding"]["work_unit_digest"] = "sha256:" + "0" * 64
    return build_ave_shadow_plan(
        repository="MSKazemi/idkmesh",
        work_unit=wu,
        evaluator_plan=ep,
        verifier_pool=pool(wu, cands),
        maturity="N3",
        input_refs=[f"work-unit:{wu['id']}"],
    )


def outcome(
    plan: dict[str, Any], actual: str | None, **kwargs: Any
) -> dict[str, Any]:
    params: dict[str, Any] = dict(
        observed_at="2026-09-22T13:00:00Z",
        outcome="succeeded",
        limitations=LIMITS,
    )
    params.update(kwargs)
    return build_outcome_record(
        plan=plan, actual_choice_id=actual, **params
    )


class AVEChainTests(unittest.TestCase):
    def test_plan_is_deterministic_and_binding_uses_pool_capture_time(self):
        first = freeze(1)
        second = freeze(1)
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertEqual(first["binding"]["captured_at"], CAPTURED)
        self.assertEqual(first["mode"], "shadow")
        self.assertTrue(first["authority"]["advisory_only"])

    def test_disagreement_flows_into_cohort_without_causal_claim(self):
        plan = freeze(1)
        self.assertEqual(
            plan["recommendation"]["selected_choice_id"],
            "portfolio:alpha+beta",
        )
        self.assertEqual(
            plan["recommendation"]["baseline_choice_id"], BASELINE_ID
        )
        record = outcome(plan, BASELINE_ID, escaped_defect=False)
        self.assertFalse(record["comparison"]["shadow_matches_actual"])
        self.assertTrue(record["comparison"]["baseline_matches_actual"])

        summary = summarize_cohort(
            plans=[plan], outcomes=[record], limitations=LIMITS
        )
        self.assertEqual(summary["counts"]["joined"], 1)
        self.assertEqual(
            summary["disagreement"]["shadow_vs_baseline_disagree"], 1
        )
        self.assertEqual(
            summary["disagreement"]["baseline_matches_actual"], 1
        )
        self.assertEqual(summary["disagreement"]["shadow_matches_actual"], 0)
        self.assertEqual(summary["policy_ids"], ["ave-core"])
        self.assertTrue(summary["identifiability"]["descriptive_only"])
        self.assertIsNone(
            summary["identifiability"]["causal_effect_estimate"]
        )
        self.assertFalse(
            summary["identifiability"]["promotion_decision_automatic"]
        )
        self.assertFalse(summary["authority"]["dispatch"])

    def test_singleton_agreement_is_not_counted_as_disagreement(self):
        plan = freeze(
            2,
            risk="low",
            baseline_verifier="alpha",
            candidates=[candidate("alpha", "family-a")],
        )
        selected = plan["recommendation"]["selected_choice_id"]
        self.assertIsNotNone(selected)
        self.assertEqual(
            selected, plan["recommendation"]["baseline_choice_id"]
        )
        summary = summarize_cohort(
            plans=[plan],
            outcomes=[outcome(plan, selected)],
            limitations=LIMITS,
        )
        self.assertEqual(
            summary["disagreement"]["shadow_vs_baseline_comparable"], 1
        )
        self.assertEqual(
            summary["disagreement"]["shadow_vs_baseline_disagree"], 0
        )

    def test_baseline_verifier_in_pool_shares_semantic_choice_identity(self):
        plan = freeze(16, baseline_verifier="alpha")
        self.assertEqual(
            plan["recommendation"]["baseline_choice_id"], "portfolio:alpha"
        )
        self.assertEqual(
            plan["recommendation"]["selected_choice_id"],
            "portfolio:alpha+beta",
        )
        record = outcome(plan, "portfolio:alpha")
        self.assertTrue(record["comparison"]["baseline_matches_actual"])

    def test_abstained_plan_is_kept_and_not_comparable(self):
        plan = freeze(3, break_work_unit_digest=True)
        self.assertIsNone(plan["recommendation"]["selected_choice_id"])
        record = outcome(plan, None, outcome="unknown")
        summary = summarize_cohort(
            plans=[plan], outcomes=[record], limitations=LIMITS
        )
        self.assertEqual(summary["counts"]["plans"], 1)
        self.assertEqual(summary["counts"]["joined"], 1)
        self.assertEqual(
            summary["disagreement"]["shadow_vs_baseline_comparable"], 0
        )
        self.assertIsNone(
            summary["disagreement"]["shadow_vs_baseline_disagreement_rate"]
        )
        self.assertEqual(summary["observed_outcomes"]["known_outcomes"], 0)

    def test_missing_outcomes_stay_visible_in_the_denominator(self):
        plans = [freeze(i) for i in (4, 5, 6)]
        record = outcome(plans[0], BASELINE_ID)
        summary = summarize_cohort(
            plans=plans, outcomes=[record], limitations=LIMITS
        )
        self.assertEqual(summary["counts"]["plans"], 3)
        self.assertEqual(summary["counts"]["joined"], 1)
        self.assertEqual(summary["counts"]["missing_outcomes"], 2)

    def test_outcome_predating_frozen_plan_is_rejected_on_join(self):
        plan = freeze(7)
        with self.assertRaises(AdaptivePolicyOutcomeError):
            outcome(plan, BASELINE_ID, observed_at="2026-09-22T11:59:59Z")

    def test_outcome_predating_plan_is_rejected_by_cohort_too(self):
        plan = freeze(8)
        forged = copy.deepcopy(outcome(plan, BASELINE_ID))
        forged["observed_process"]["observed_at"] = "2026-09-21T00:00:00Z"
        with self.assertRaises(AdaptivePolicyCohortError):
            summarize_cohort(
                plans=[plan], outcomes=[forged], limitations=LIMITS
            )

    def test_outcome_must_name_a_choice_frozen_before_it_was_known(self):
        plan = freeze(9)
        with self.assertRaises(AdaptivePolicyOutcomeError):
            outcome(plan, "portfolio:invented-after-the-fact")

    def test_plan_edited_after_outcome_breaks_digest_binding(self):
        plan = freeze(10)
        record = outcome(plan, BASELINE_ID)
        tampered = copy.deepcopy(plan)
        tampered["recommendation"]["selected_choice_id"] = BASELINE_ID
        with self.assertRaises(AdaptivePolicyCohortError):
            summarize_cohort(
                plans=[tampered], outcomes=[record], limitations=LIMITS
            )

    def test_duplicate_outcome_for_one_plan_is_rejected(self):
        plan = freeze(11)
        first = outcome(plan, BASELINE_ID)
        second = outcome(
            plan, BASELINE_ID, observed_at="2026-09-22T14:00:00Z"
        )
        with self.assertRaises(AdaptivePolicyCohortError):
            summarize_cohort(
                plans=[plan], outcomes=[first, second], limitations=LIMITS
            )

    def test_outcome_cannot_claim_the_unexecuted_counterfactual(self):
        plan = freeze(12)
        record = outcome(plan, BASELINE_ID)
        for field in ("shadow_counterfactual_observed", "causal_claim_allowed"):
            forged = copy.deepcopy(record)
            forged["comparison"][field] = True
            with self.assertRaises(AdaptivePolicyCohortError, msg=field):
                summarize_cohort(
                    plans=[plan], outcomes=[forged], limitations=LIMITS
                )

    def test_outcome_fields_never_enter_the_plan_inputs(self):
        """No look-ahead: the plan digest is a function of pre-outcome inputs."""
        plan = freeze(13)
        before = canonical_digest(plan)
        outcome(plan, BASELINE_ID, escaped_defect=True, high_risk_escape=True)
        self.assertEqual(canonical_digest(plan), before)
        self.assertEqual(before, canonical_digest(freeze(13)))

    def test_pool_not_bound_to_the_work_unit_abstains_but_is_recorded(self):
        wu = work_unit(14)
        bad_pool = pool(wu, [candidate("alpha", "family-a")])
        bad_pool["work_unit_id"] = "chain/other-work-unit"
        plan = build_ave_shadow_plan(
            repository="MSKazemi/idkmesh",
            work_unit=wu,
            evaluator_plan=evaluator_plan(wu, "alpha"),
            verifier_pool=bad_pool,
            maturity="N3",
            input_refs=["x"],
        )
        self.assertIsNone(plan["recommendation"]["selected_choice_id"])
        self.assertTrue(
            any(gate["status"] == "fail" for gate in plan["hard_gates"])
        )

    def test_malformed_pool_is_rejected_not_silently_planned(self):
        wu = work_unit(15)
        broken = pool(wu, [candidate("alpha", "family-a")])
        broken["captured_at"] = "not-a-time"
        with self.assertRaises((AVEShadowAdapterError, ValueError)):
            build_ave_shadow_plan(
                repository="MSKazemi/idkmesh",
                work_unit=wu,
                evaluator_plan=evaluator_plan(wu, "alpha"),
                verifier_pool=broken,
                maturity="N3",
                input_refs=["x"],
            )


if __name__ == "__main__":
    unittest.main()
