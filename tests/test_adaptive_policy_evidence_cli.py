import json
from pathlib import Path
import tempfile
import unittest

from tools import adaptive_policy_evidence_cli as cli


def plan_request():
    return {
        "repository": "MSKazemi/idkmesh",
        "source_revision_sha": "c" * 40,
        "captured_at": "2026-09-22T12:00:00Z",
        "subsystem": "verification-allocation",
        "policy": {
            "id": "ave-core",
            "version": "0.1",
            "maturity": "N3",
        },
        "input_state": {
            "work_unit": "wu-100",
            "review_utilization": 0.8,
        },
        "input_refs": ["work-unit:wu-100"],
        "hard_gates": [
            {
                "id": "binding",
                "status": "pass",
                "reason": "exact-bound",
            }
        ],
        "eligible_choices": [
            {
                "id": "a",
                "class": "verifier-portfolio",
                "reasons": ["baseline"],
                "metrics": {"families": 1},
            },
            {
                "id": "b",
                "class": "verifier-portfolio",
                "reasons": ["shadow"],
                "metrics": {"families": 2},
            },
        ],
        "recommendation": {
            "selected_choice_id": "b",
            "baseline_choice_id": "a",
            "reasons": ["shadow comparison"],
            "exploration": False,
            "uncertainty": 0.4,
            "expected_cost": {
                "compute_units": 0,
                "review_units": 2,
                "human_attention_units": None,
            },
        },
        "evidence_refs": ["experiment:AVE-2"],
        "limitations": ["observational shadow only"],
    }


class AdaptivePolicyEvidenceCLITests(unittest.TestCase):
    def test_build_plan_from_request(self):
        plan = cli.build_plan_from_request(plan_request())
        self.assertEqual(
            plan["recommendation"]["selected_choice_id"],
            "b",
        )
        self.assertFalse(plan["authority"]["dispatch"])

    def test_plan_outcome_cohort_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_path = root / "request.json"
            plan_path = root / "plan.json"
            observation_path = root / "observation.json"
            outcome_path = root / "outcome.json"
            cohort_request_path = root / "cohort.json"
            cohort_path = root / "cohort-summary.json"

            request_path.write_text(
                json.dumps(plan_request()),
                encoding="utf-8",
            )
            self.assertEqual(
                cli.main(
                    [
                        "plan",
                        "--request",
                        str(request_path),
                        "--output",
                        str(plan_path),
                    ]
                ),
                0,
            )

            observation_path.write_text(
                json.dumps(
                    {
                        "actual_choice_id": "a",
                        "observed_at": "2026-09-22T12:05:00Z",
                        "outcome": "succeeded",
                        "verified_utility": 0.7,
                        "escaped_defect": False,
                        "high_risk_escape": False,
                        "actual_cost": {
                            "project_spend_usd": 0,
                            "compute_units": 0,
                            "review_units": 1,
                            "human_attention_units": None,
                        },
                        "evidence_refs": ["verification:real-1"],
                        "limitations": [
                            "shadow choice b was not executed"
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                cli.main(
                    [
                        "outcome",
                        "--plan",
                        str(plan_path),
                        "--observation",
                        str(observation_path),
                        "--output",
                        str(outcome_path),
                    ]
                ),
                0,
            )

            cohort_request_path.write_text(
                json.dumps(
                    {
                        "plans": [str(plan_path)],
                        "outcomes": [str(outcome_path)],
                        "limitations": [
                            "single observational example"
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                cli.main(
                    [
                        "cohort",
                        "--request",
                        str(cohort_request_path),
                        "--output",
                        str(cohort_path),
                    ]
                ),
                0,
            )
            summary = json.loads(
                cohort_path.read_text(encoding="utf-8")
            )
            self.assertEqual(summary["counts"]["joined"], 1)
            self.assertEqual(
                summary["disagreement"][
                    "shadow_vs_baseline_disagree"
                ],
                1,
            )
            self.assertIsNone(
                summary["identifiability"][
                    "causal_effect_estimate"
                ]
            )

    def test_refuses_to_overwrite_evidence_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "evidence.json"
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(
                cli.EvidenceCLIError,
                "overwrite",
            ):
                cli.write_json({"x": 1}, str(path))


if __name__ == "__main__":
    unittest.main()
