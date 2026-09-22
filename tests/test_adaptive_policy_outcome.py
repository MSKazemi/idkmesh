import importlib.util
import json
from pathlib import Path
import unittest

from tools.adaptive_policy_outcome import (
    AdaptivePolicyOutcomeError,
    build_outcome_record,
    sha256_digest,
)
from tools.adaptive_policy_shadow import build_shadow_plan


ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator


def sample_plan():
    return build_shadow_plan(
        repository="MSKazemi/idkmesh",
        source_revision_sha="b" * 40,
        subsystem="compute-path-routing",
        policy_id="physarum",
        policy_version="0.1",
        maturity="N2",
        input_state={"graph": "admitted-graph-1"},
        input_refs=["admitted-graph:1"],
        hard_gates=[
            {
                "id": "compute-admission",
                "status": "pass",
                "reason": "all choices are already admitted",
            }
        ],
        eligible_choices=[
            {
                "id": "route-a",
                "class": "compute-route",
                "reasons": ["baseline route"],
                "metrics": {"burden": 2.0},
            },
            {
                "id": "route-b",
                "class": "compute-route",
                "reasons": ["shadow alternate route"],
                "metrics": {"burden": 2.4},
            },
        ],
        selected_choice_id="route-b",
        baseline_choice_id="route-a",
        selection_reasons=["shadow conductance prefers route-b"],
        uncertainty=0.4,
        compute_units=2.4,
        limitations=["shadow recommendation only"],
    )


class AdaptivePolicyOutcomeTests(unittest.TestCase):
    def test_outcome_binds_to_exact_plan_digest(self):
        plan = sample_plan()
        record = build_outcome_record(
            plan=plan,
            actual_choice_id="route-a",
            outcome="succeeded",
            compute_units=2.0,
            evidence_refs=["run:123"],
            limitations=["shadow route was not executed"],
        )
        self.assertEqual(record["plan_digest"], sha256_digest(plan))
        self.assertEqual(
            record["binding"]["source_revision_sha"],
            plan["binding"]["source_revision_sha"],
        )

    def test_disagreement_does_not_create_counterfactual_outcome(self):
        record = build_outcome_record(
            plan=sample_plan(),
            actual_choice_id="route-a",
            outcome="succeeded",
            limitations=["shadow route was not executed"],
        )
        comparison = record["comparison"]
        self.assertFalse(comparison["shadow_matches_actual"])
        self.assertTrue(comparison["baseline_matches_actual"])
        self.assertFalse(
            comparison["shadow_counterfactual_observed"]
        )
        self.assertFalse(comparison["causal_claim_allowed"])

    def test_actual_choice_must_have_been_frozen_in_plan(self):
        with self.assertRaisesRegex(
            AdaptivePolicyOutcomeError,
            "frozen in the plan",
        ):
            build_outcome_record(
                plan=sample_plan(),
                actual_choice_id="route-c",
                outcome="succeeded",
                limitations=["test"],
            )

    def test_high_risk_escape_requires_escape(self):
        with self.assertRaisesRegex(
            AdaptivePolicyOutcomeError,
            "requires escaped_defect",
        ):
            build_outcome_record(
                plan=sample_plan(),
                actual_choice_id="route-a",
                outcome="succeeded",
                escaped_defect=False,
                high_risk_escape=True,
                limitations=["test"],
            )

    def test_plan_with_authority_is_rejected(self):
        plan = sample_plan()
        plan["authority"]["dispatch"] = True
        with self.assertRaisesRegex(
            AdaptivePolicyOutcomeError,
            "non-shadow authority",
        ):
            build_outcome_record(
                plan=plan,
                actual_choice_id="route-a",
                outcome="succeeded",
                limitations=["test"],
            )

    @unittest.skipUnless(
        HAS_JSONSCHEMA,
        "adaptive policy outcome schema test requires jsonschema",
    )
    def test_record_matches_schema(self):
        record = build_outcome_record(
            plan=sample_plan(),
            actual_choice_id="route-a",
            outcome="succeeded",
            verified_utility=0.8,
            escaped_defect=False,
            high_risk_escape=False,
            project_spend_usd=0,
            compute_units=2.0,
            review_units=1.0,
            evidence_refs=["run:123"],
            limitations=["shadow route was not executed"],
        )
        schema = json.loads(
            (
                ROOT
                / "schemas/adaptive-policy-outcome-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(record)


if __name__ == "__main__":
    unittest.main()
