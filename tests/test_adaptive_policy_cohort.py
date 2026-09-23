import importlib.util
import json
from pathlib import Path
import unittest

from tools.adaptive_policy_cohort import (
    AdaptivePolicyCohortError,
    summarize_cohort,
)
from tools.adaptive_policy_outcome import build_outcome_record
from tools.adaptive_policy_shadow import build_shadow_plan


ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator


def plan(index: int, shadow: str, baseline: str):
    return build_shadow_plan(
        repository="MSKazemi/idkmesh",
        source_revision_sha=(hex(index + 1)[2:] * 40)[:40],
        captured_at="2026-09-22T12:00:00Z",
        subsystem="verification-allocation",
        policy_id="ave-core",
        policy_version="0.1",
        maturity="N3",
        input_state={"index": index},
        input_refs=[f"work-unit:{index}"],
        hard_gates=[
            {
                "id": "binding",
                "status": "pass",
                "reason": "exact-bound",
            }
        ],
        eligible_choices=[
            {
                "id": "a",
                "class": "verifier-portfolio",
                "reasons": [],
                "metrics": {},
            },
            {
                "id": "b",
                "class": "verifier-portfolio",
                "reasons": [],
                "metrics": {},
            },
        ],
        selected_choice_id=shadow,
        baseline_choice_id=baseline,
        selection_reasons=["shadow comparison"],
        limitations=["observational shadow plan"],
    )


class AdaptivePolicyCohortTests(unittest.TestCase):
    def test_summary_measures_disagreement_without_causal_effect(self):
        p1 = plan(1, "b", "a")
        p2 = plan(2, "a", "a")
        o1 = build_outcome_record(
            plan=p1,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            verified_utility=0.8,
            escaped_defect=False,
            high_risk_escape=False,
            review_units=1.0,
            limitations=["shadow choice b was not executed"],
        )
        o2 = build_outcome_record(
            plan=p2,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="failed",
            verified_utility=0.0,
            escaped_defect=True,
            high_risk_escape=True,
            review_units=1.0,
            limitations=["observed actual outcome only"],
        )
        summary = summarize_cohort(
            plans=[p1, p2],
            outcomes=[o1, o2],
            limitations=[
                "observational cohort; no randomized policy assignment"
            ],
        )
        self.assertEqual(
            summary["disagreement"]["shadow_vs_baseline_disagree"],
            1,
        )
        self.assertEqual(
            summary["disagreement"][
                "shadow_vs_baseline_disagreement_rate"
            ],
            0.5,
        )
        self.assertIsNone(
            summary["identifiability"]["causal_effect_estimate"]
        )
        self.assertFalse(
            summary["identifiability"][
                "shadow_counterfactual_observed"
            ]
        )

    def test_digest_mismatch_is_rejected(self):
        p = plan(3, "b", "a")
        outcome = build_outcome_record(
            plan=p,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            limitations=["test"],
        )
        outcome["plan_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(
            AdaptivePolicyCohortError,
            "digest mismatch",
        ):
            summarize_cohort(
                plans=[p],
                outcomes=[outcome],
                limitations=["test"],
            )

    def test_duplicate_outcome_is_rejected(self):
        p = plan(4, "b", "a")
        outcome = build_outcome_record(
            plan=p,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            limitations=["test"],
        )
        with self.assertRaisesRegex(
            AdaptivePolicyCohortError,
            "duplicate outcome",
        ):
            summarize_cohort(
                plans=[p],
                outcomes=[outcome, outcome],
                limitations=["test"],
            )

    def test_missing_outcomes_are_reported(self):
        p1 = plan(5, "b", "a")
        p2 = plan(6, "a", "a")
        outcome = build_outcome_record(
            plan=p1,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            limitations=["test"],
        )
        summary = summarize_cohort(
            plans=[p1, p2],
            outcomes=[outcome],
            limitations=["one outcome is pending"],
        )
        self.assertEqual(summary["counts"]["plans"], 2)
        self.assertEqual(summary["counts"]["joined"], 1)
        self.assertEqual(summary["counts"]["missing_outcomes"], 1)

    @unittest.skipUnless(
        HAS_JSONSCHEMA,
        "adaptive cohort schema test requires jsonschema",
    )
    def test_summary_matches_schema(self):
        p = plan(7, "b", "a")
        outcome = build_outcome_record(
            plan=p,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            escaped_defect=False,
            high_risk_escape=False,
            limitations=["test"],
        )
        summary = summarize_cohort(
            plans=[p],
            outcomes=[outcome],
            limitations=["observational only"],
        )
        schema = json.loads(
            (
                ROOT
                / "schemas/adaptive-policy-cohort-summary-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(summary)


    def test_cohort_rejects_outcome_that_predates_plan(self):
        p = plan(8, "b", "a")
        outcome = build_outcome_record(
            plan=p,
            actual_choice_id="a",
            observed_at="2026-09-22T12:05:00Z",
            outcome="succeeded",
            limitations=["test"],
        )
        outcome["observed_process"]["observed_at"] = (
            "2026-09-22T11:59:59Z"
        )
        with self.assertRaisesRegex(
            AdaptivePolicyCohortError,
            "predates frozen plan",
        ):
            summarize_cohort(
                plans=[p],
                outcomes=[outcome],
                limitations=["test"],
            )


if __name__ == "__main__":
    unittest.main()
