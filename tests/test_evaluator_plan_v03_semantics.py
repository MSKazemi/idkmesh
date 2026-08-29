from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        "EvaluatorPlan v0.3 tests require the Phase 0 jsonschema dependency"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import evaluator_plan_v03  # noqa: E402
import local_verifier  # noqa: E402
import patch_verifier_v020  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402

WORK_UNIT = ROOT / "examples/work-units/patch-verifier-smoke.work-unit.json"
PLAN_V02 = ROOT / "verification/fixtures/patch-smoke-evaluator-plan-v0.2.json"
PLAN_V03 = ROOT / "verification/fixtures/patch-smoke-evaluator-plan-v0.3.json"
GOOD_ROOT = ROOT / "examples/verifier/patch/good"


class EvaluatorPlanV03SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = local_verifier.load_json(WORK_UNIT)
        cls.worker = local_verifier.load_json(GOOD_ROOT / "result-manifest.json")
        cls.plan_v02 = evaluator_plan_runner.load_plan(PLAN_V02)
        cls.plan_v03 = evaluator_plan_v03.load_plan(PLAN_V03)

    def verify_v02(self, plan: dict) -> dict:
        return evaluator_plan_runner.verify_with_plan(
            work_unit=self.work_unit,
            worker_result=copy.deepcopy(self.worker),
            plan=plan,
            candidate_root=GOOD_ROOT,
            plan_path=PLAN_V02,
        )

    def verify_v03(self, plan: dict) -> dict:
        return evaluator_plan_v03.verify_with_plan(
            work_unit=self.work_unit,
            worker_result=copy.deepcopy(self.worker),
            plan=plan,
            candidate_root=GOOD_ROOT,
            plan_path=PLAN_V03,
        )

    def test_v02_exact_line_behavior_remains_unchanged(self) -> None:
        result = self.verify_v02(copy.deepcopy(self.plan_v02))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verifier"]["adapter_version"], "0.1.1")
        diagnostics = json.loads(
            next(
                check
                for check in result["checks"]
                if check["id"] == "independent-review"
            )["diagnostics"]
        )
        self.assertEqual(
            diagnostics["semantic"]["required_added_text"],
            ["<!-- patch-evaluator expected -->"],
        )

    def test_same_patch_distinguishes_exact_line_from_substring_semantics(self) -> None:
        # This is the contract defect exposed by the burned Phase B2 cohort:
        # a semantic fragment is present inside a valid added line but is not the
        # complete added line. v0.2 must keep rejecting that interpretation.
        old_fragment_plan = copy.deepcopy(self.plan_v02)
        old_fragment_plan["backend"]["required_added_text"] = [
            "patch-evaluator expected"
        ]
        old_result = self.verify_v02(old_fragment_plan)
        self.assertEqual(old_result["status"], "failed")
        self.assertEqual(old_result["verifier"]["adapter_version"], "0.1.1")

        new_result = self.verify_v03(copy.deepcopy(self.plan_v03))
        self.assertEqual(new_result["status"], "passed")
        self.assertEqual(new_result["verifier"]["adapter_version"], "0.2.0")
        diagnostics = json.loads(
            next(
                check
                for check in new_result["checks"]
                if check["id"] == "independent-review"
            )["diagnostics"]
        )
        semantic = diagnostics["semantic"]
        self.assertEqual(
            semantic["semantic_mode"],
            "substring_in_validated_added_line",
        )
        self.assertEqual(
            semantic["matches"]["patch-evaluator expected"],
            ["<!-- patch-evaluator expected -->"],
        )
        self.assertEqual(semantic["missing_added_substrings"], [])

    def test_missing_v03_substring_rejects_candidate(self) -> None:
        plan = copy.deepcopy(self.plan_v03)
        plan["backend"]["required_added_substrings"] = ["definitely-not-present"]
        result = self.verify_v03(plan)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["decision_support"]["recommendation"], "reject_candidate")
        diagnostics = json.loads(
            next(
                check
                for check in result["checks"]
                if check["id"] == "independent-review"
            )["diagnostics"]
        )
        self.assertEqual(
            diagnostics["semantic"]["missing_added_substrings"],
            ["definitely-not-present"],
        )

    def test_v03_records_exact_plan_digest_and_verifier_version(self) -> None:
        result = self.verify_v03(copy.deepcopy(self.plan_v03))
        digest = canonical_digest(self.plan_v03)
        self.assertEqual(result["provenance"]["verifier_config_digest"], digest)
        self.assertEqual(
            result["extensions"]["org.idkmesh.evaluator_plan.digest"], digest
        )
        self.assertEqual(
            result["provenance"]["environment"]["tool_versions"][
                "deterministic-patch-verifier"
            ],
            "0.2.0",
        )
        self.assertEqual(
            result["extensions"]["org.idkmesh.local_verifier.semantic_match"],
            patch_verifier_v020.SEMANTIC_MODE,
        )

    def test_v03_schema_rejects_old_verifier_version(self) -> None:
        plan = copy.deepcopy(self.plan_v03)
        plan["verifier"]["adapter_version"] = "0.1.1"
        with self.assertRaises(local_verifier.VerifierError):
            local_verifier.validate_schema(
                plan,
                ROOT / "schemas/evaluator-plan-v0.3.schema.json",
                "EvaluatorPlan v0.3",
            )

    def test_v03_semantics_reject_ambiguous_old_field(self) -> None:
        policy = evaluator_plan_v03.operational_policy(self.plan_v03)
        policy["backend"]["required_added_text"] = ["legacy"]
        with self.assertRaisesRegex(
            patch_verifier_v020.SemanticVerifierError,
            "required_added_text",
        ):
            patch_verifier_v020.validate_policy(policy)

    def test_semantic_matching_consumes_parser_added_lines_only(self) -> None:
        malformed = "\n".join(
            [
                "diff --git a/README.md b/README.md",
                "--- a/README.md",
                "+++ b/README.md",
                "+patch-evaluator expected",
                "",
            ]
        )
        with self.assertRaises(local_verifier.VerifierError):
            local_verifier.parse_unified_diff(malformed)


if __name__ == "__main__":
    unittest.main()
