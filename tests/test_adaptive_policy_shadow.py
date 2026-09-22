import importlib.util
import json
from pathlib import Path
import unittest

from tools.adaptive_policy_shadow import (
    AdaptivePolicyPlanError,
    build_shadow_plan,
    sha256_digest,
)


ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator


class AdaptivePolicyShadowTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "repository": "MSKazemi/idkmesh",
            "source_revision_sha": "a" * 40,
            "subsystem": "verification-allocation",
            "policy_id": "ave-core",
            "policy_version": "0.1",
            "maturity": "N2",
            "input_state": {
                "work_unit": "wu-1",
                "review_utilization": 0.72,
            },
            "input_refs": ["work-unit:wu-1"],
            "hard_gates": [
                {
                    "id": "work-unit-binding",
                    "status": "pass",
                    "reason": "exact source revision matched",
                },
                {
                    "id": "evaluator-sovereignty",
                    "status": "pass",
                    "reason": "worker cannot modify evaluator plan",
                },
            ],
            "eligible_choices": [
                {
                    "id": "verifier-set-a",
                    "class": "verifier-portfolio",
                    "reasons": ["two distinct verifier families"],
                    "metrics": {
                        "expected_review_units": 2.0,
                        "family_count": 2,
                    },
                },
                {
                    "id": "verifier-set-b",
                    "class": "verifier-portfolio",
                    "reasons": ["baseline single verifier"],
                    "metrics": {
                        "expected_review_units": 1.0,
                        "family_count": 1,
                    },
                },
            ],
            "selected_choice_id": "verifier-set-a",
            "baseline_choice_id": "verifier-set-b",
            "selection_reasons": [
                "shadow-policy-prefers-independent-family-coverage"
            ],
            "uncertainty": 0.35,
            "compute_units": 0.0,
            "review_units": 2.0,
            "human_attention_units": None,
            "evidence_refs": ["experiment:AVE-2"],
            "limitations": [
                "synthetic evidence only; no dispatch authority"
            ],
        }
        values.update(overrides)
        return build_shadow_plan(**values)

    def test_output_is_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(
            first["binding"]["input_digest"],
            sha256_digest(
                {
                    "work_unit": "wu-1",
                    "review_utilization": 0.72,
                }
            ),
        )

    def test_authority_is_fixed_to_shadow_only(self):
        plan = self.build()
        authority = plan["authority"]
        self.assertTrue(authority["advisory_only"])
        self.assertFalse(authority["dispatch"])
        self.assertFalse(authority["execute"])
        self.assertFalse(authority["approve"])
        self.assertFalse(authority["merge"])
        self.assertFalse(authority["repository_write"])
        self.assertFalse(authority["relax_hard_gates"])
        self.assertFalse(authority["modify_required_verification"])
        self.assertFalse(authority["authorize_project_spend"])
        self.assertEqual(
            plan["recommendation"]["expected_cost"]["project_spend_usd"],
            0,
        )

    def test_failed_gate_forces_abstention(self):
        gates = [
            {
                "id": "resource-admission",
                "status": "fail",
                "reason": "no admitted zero-project-cost route",
            }
        ]
        with self.assertRaisesRegex(
            AdaptivePolicyPlanError,
            "failed hard gate",
        ):
            self.build(hard_gates=gates)

        plan = self.build(
            hard_gates=gates,
            selected_choice_id=None,
            baseline_choice_id=None,
            eligible_choices=[],
            selection_reasons=["no eligible route after admission"],
        )
        self.assertIsNone(
            plan["recommendation"]["selected_choice_id"]
        )

    def test_selected_choice_must_be_eligible(self):
        with self.assertRaisesRegex(
            AdaptivePolicyPlanError,
            "selected_choice_id",
        ):
            self.build(selected_choice_id="not-eligible")

    def test_duplicate_choice_ids_are_rejected(self):
        choices = [
            {
                "id": "x",
                "class": "route",
                "reasons": [],
                "metrics": {},
            },
            {
                "id": "x",
                "class": "route",
                "reasons": [],
                "metrics": {},
            },
        ]
        with self.assertRaisesRegex(
            AdaptivePolicyPlanError,
            "duplicate choice",
        ):
            self.build(eligible_choices=choices)

    def test_invalid_uncertainty_is_rejected(self):
        with self.assertRaisesRegex(
            AdaptivePolicyPlanError,
            "uncertainty",
        ):
            self.build(uncertainty=1.2)

    def test_boolean_cannot_impersonate_cost(self):
        with self.assertRaisesRegex(
            AdaptivePolicyPlanError,
            "compute_units",
        ):
            self.build(compute_units=False)

    @unittest.skipUnless(
        HAS_JSONSCHEMA,
        "adaptive policy schema test requires jsonschema",
    )
    def test_plan_matches_schema(self):
        plan = self.build()
        schema = json.loads(
            (
                ROOT
                / "schemas/adaptive-policy-plan-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(plan)


if __name__ == "__main__":
    unittest.main()
