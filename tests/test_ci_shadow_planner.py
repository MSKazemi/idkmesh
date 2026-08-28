import copy
import importlib.util
import json
from pathlib import Path
import unittest

from tools.ci_shadow_planner import (
    CIPlanError,
    build_plan,
    build_receipt,
    path_matches,
    sha256_digest,
    validate_policy,
)


ROOT = Path(__file__).resolve().parents[1]
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator


class CIShadowPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            (ROOT / "config/ci-policy-v0.1.json").read_text(encoding="utf-8")
        )

    def plan(self, paths, *, head="2" * 40, policy=None):
        return build_plan(
            repository="MSKazemi/idkmesh",
            base_sha="1" * 40,
            head_sha=head,
            changed_files=paths,
            policy=policy or self.policy,
        )

    def test_root_markdown_matches_recursive_pattern(self):
        self.assertTrue(path_matches("README.md", "**/*.md"))
        self.assertTrue(path_matches("docs/README.md", "**/*.md"))
        self.assertFalse(path_matches("scripts/tool.py", "**/*.md"))

    def test_document_only_change_keeps_full_baseline_and_hard_gates(self):
        plan = self.plan(["README.md"])
        self.assertEqual(plan["risk"]["class"], "R0")
        self.assertEqual(
            plan["summary"]["mandatory"],
            ["documentation-integrity", "repository-integrity"],
        )
        self.assertTrue(plan["summary"]["full_suite_baseline_required"])
        self.assertFalse(plan["authority"]["skip_required_checks"])

    def test_workflow_change_is_r3_and_requires_full_regression(self):
        plan = self.plan([".github/workflows/ci-shadow-planner.yml"])
        self.assertEqual(plan["risk"]["class"], "R3")
        self.assertIn("ci-control-plane", plan["summary"]["mandatory"])
        self.assertIn("full-regression", plan["summary"]["mandatory"])
        self.assertFalse(plan["authority"]["execute"])
        self.assertFalse(plan["authority"]["merge"])

    def test_optional_selection_is_dependency_closed(self):
        plan = self.plan(["docs/research/new-experiment.md"])
        self.assertIn("research-simulations", plan["summary"]["selected_optional"])
        self.assertIn("core-unit", plan["summary"]["selected_optional"])
        self.assertLessEqual(
            plan["budget"]["selected_optional_seconds"],
            plan["budget"]["optional_seconds"],
        )

    def test_oversized_optional_check_is_not_selected(self):
        plan = self.plan(["README.md"])
        self.assertNotIn("full-regression", plan["summary"]["selected_optional"])
        full = next(check for check in plan["checks"] if check["id"] == "full-regression")
        self.assertEqual(full["lane"], "optional")
        self.assertIn("outside-optional-budget", full["reasons"])

    def test_output_is_deterministic_and_exact_head_bound(self):
        first = self.plan(["scripts/evolution_score.py", "README.md"])
        second = self.plan(["README.md", "scripts/evolution_score.py"])
        self.assertEqual(first, second)
        self.assertEqual(first["head_sha"], "2" * 40)
        self.assertEqual(first["changed_files"], ["README.md", "scripts/evolution_score.py"])

    def test_receipt_is_planning_evidence_not_execution(self):
        plan = self.plan(["tools/ci_shadow_planner.py"])
        receipt = build_receipt(plan)
        self.assertEqual(receipt["plan_digest"], sha256_digest(plan))
        self.assertEqual(receipt["executed_checks"], [])
        self.assertEqual(receipt["actual_cost"]["project_spend_usd"], 0)
        self.assertEqual(receipt["actual_cost"]["check_execution_seconds"], 0)
        self.assertIsNone(receipt["actual_cost"]["planner_execution_seconds"])
        self.assertFalse(receipt["actual_cost"]["external_resource_cost_zero_claim"])
        self.assertFalse(receipt["authority"]["execute"])
        self.assertFalse(receipt["authority"]["merge"])

    def test_boolean_cannot_impersonate_zero_spend(self):
        policy = copy.deepcopy(self.policy)
        policy["project_spend_usd_max"] = False
        with self.assertRaisesRegex(CIPlanError, "spend"):
            validate_policy(policy)

    def test_policy_rejects_unknown_dependency(self):
        policy = copy.deepcopy(self.policy)
        policy["checks"][0]["dependencies"] = ["does-not-exist"]
        with self.assertRaisesRegex(CIPlanError, "unknown check"):
            validate_policy(policy)

    def test_policy_requires_fail_closed_fallback(self):
        policy = copy.deepcopy(self.policy)
        policy["risk_rules"] = [
            rule for rule in policy["risk_rules"] if rule["id"] != "fallback"
        ]
        with self.assertRaisesRegex(CIPlanError, "fallback"):
            validate_policy(policy)

    def test_policy_rejects_unknown_fields(self):
        policy = copy.deepcopy(self.policy)
        policy["budgets"]["optional_minuts"] = 10
        with self.assertRaisesRegex(CIPlanError, "unknown fields"):
            validate_policy(policy)

    def test_policy_rejects_dependency_cycle(self):
        policy = copy.deepcopy(self.policy)
        policy["checks"][0]["dependencies"] = ["documentation-integrity"]
        with self.assertRaisesRegex(CIPlanError, "cycle"):
            validate_policy(policy)

    def test_changed_path_cannot_escape_repository(self):
        with self.assertRaisesRegex(CIPlanError, "escapes repository"):
            self.plan(["../secret.txt"])

    @unittest.skipUnless(HAS_JSONSCHEMA, "CI plan schema tests require jsonschema")
    def test_plan_and_receipt_match_published_schemas(self):
        plan = self.plan([".github/workflows/ci-shadow-planner.yml"])
        receipt = build_receipt(plan)
        plan_schema = json.loads(
            (ROOT / "schemas/ci-plan-v0.1.schema.json").read_text(encoding="utf-8")
        )
        receipt_schema = json.loads(
            (ROOT / "schemas/ci-receipt-v0.1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(plan_schema).validate(plan)
        Draft202012Validator(receipt_schema).validate(receipt)


if __name__ == "__main__":
    unittest.main()
