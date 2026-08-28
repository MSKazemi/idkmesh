import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.ci_shadow_evaluator import (
    CIEvaluationError,
    collect_observation,
    evaluate,
    sha256_digest,
    validate_policy,
)
from tools.ci_shadow_planner import build_plan, build_receipt


ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40


class CIShadowEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planner_policy = json.loads(
            (ROOT / "config/ci-policy-v0.1.json").read_text(encoding="utf-8")
        )
        cls.observation_policy = json.loads(
            (ROOT / "config/ci-observation-policy-v0.1.json").read_text(encoding="utf-8")
        )

    def plan_for(self, changed_files):
        plan = build_plan(
            repository="MSKazemi/idkmesh",
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            changed_files=changed_files,
            policy=self.planner_policy,
        )
        return plan, build_receipt(plan)

    def observation(self, *, gate_311="success", gate_313="success", extra=None):
        checks = [
            self.raw_check(11, "gate (3.11)", gate_311, 101),
            self.raw_check(12, "gate (3.13)", gate_313, 101),
        ]
        workflows = [self.raw_workflow(101, "PR Gate")]
        for check, workflow in extra or []:
            checks.append(check)
            workflows.append(workflow)
        return collect_observation(
            check_runs_payload={"check_runs": checks},
            workflow_runs_payload={"workflow_runs": workflows},
            head_sha=HEAD_SHA,
            policy=self.observation_policy,
        )

    @staticmethod
    def raw_check(run_id, name, conclusion, suite_id, *, status="completed"):
        return {
            "id": run_id,
            "name": name,
            "status": status,
            "conclusion": conclusion,
            "check_suite": {"id": suite_id, "head_sha": HEAD_SHA},
            "app": {"slug": "github-actions"},
            "started_at": "2026-08-29T00:00:00Z",
            "completed_at": "2026-08-29T00:01:00Z" if status == "completed" else None,
            "details_url": f"https://example.invalid/checks/{run_id}",
        }

    @staticmethod
    def raw_workflow(suite_id, name):
        return {"check_suite_id": suite_id, "head_sha": HEAD_SHA, "name": name}

    def test_collector_is_exact_deterministic_and_ignores_its_own_check(self):
        extra = [
            (
                self.raw_check(20, "evaluate", None, 202, status="in_progress"),
                self.raw_workflow(202, "CI Shadow Outcome Evaluator"),
            ),
            (
                self.raw_check(21, "gate (3.11)", "failure", 101),
                self.raw_workflow(101, "PR Gate"),
            ),
        ]
        first = self.observation(extra=extra)
        second = self.observation(extra=list(reversed(extra)))
        self.assertEqual(first, second)
        self.assertEqual([check["check_run_id"] for check in first["checks"]], [21, 12])
        self.assertTrue(first["completeness"]["baseline_complete"])
        self.assertFalse(first["completeness"]["baseline_successful"])
        self.assertEqual(first["completeness"]["pending_observed_checks"], 0)
        self.assertFalse(first["authority"]["merge"])

    def test_selected_mapping_covers_a_failed_specialized_check(self):
        plan, receipt = self.plan_for(["README.md"])
        observation = self.observation(
            extra=[
                (
                    self.raw_check(30, "deterministic-link-integrity", "failure", 303),
                    self.raw_workflow(303, "IDKGraph T2 Link Integrity"),
                )
            ]
        )
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=observation,
            policy=self.observation_policy,
        )
        failure = next(item for item in result["failed_checks"] if item["check_run_id"] == 30)
        self.assertEqual(failure["mapped_logical_check_ids"], ["documentation-integrity"])
        self.assertEqual(failure["covered_by_selected"], ["documentation-integrity"])
        self.assertEqual(result["metrics"]["missed_mapped_failure_count"], 0)
        self.assertFalse(result["promotion"]["eligible"])

    def test_unselected_full_regression_is_a_missed_mapped_failure(self):
        plan, receipt = self.plan_for(["README.md"])
        self.assertNotIn("full-regression", plan["summary"]["mandatory"])
        observation = self.observation(gate_311="failure")
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=observation,
            policy=self.observation_policy,
        )
        self.assertEqual(result["metrics"]["mapped_failure_count"], 1)
        self.assertEqual(result["metrics"]["missed_mapped_failure_count"], 1)
        self.assertEqual(result["metrics"]["mapped_failure_recall"], 0.0)
        self.assertIn("mapped_failure_missed", result["promotion"]["reasons"])

    def test_r3_plan_covers_full_regression_failure(self):
        plan, receipt = self.plan_for([".github/workflows/example.yml"])
        self.assertIn("full-regression", plan["summary"]["mandatory"])
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=self.observation(gate_313="timed_out"),
            policy=self.observation_policy,
        )
        self.assertEqual(result["metrics"]["covered_mapped_failure_count"], 1)
        self.assertEqual(result["metrics"]["mapped_failure_recall"], 1.0)

    def test_unmapped_failure_is_reported_as_attribution_gap(self):
        plan, receipt = self.plan_for(["README.md"])
        observation = self.observation(
            extra=[
                (
                    self.raw_check(40, "new-job", "failure", 404),
                    self.raw_workflow(404, "New Workflow"),
                )
            ]
        )
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=observation,
            policy=self.observation_policy,
        )
        self.assertEqual(result["metrics"]["unattributed_failure_count"], 1)
        self.assertIn("failure_attribution_incomplete", result["promotion"]["reasons"])

    def test_incomplete_baseline_is_provisional(self):
        checks = [self.raw_check(11, "gate (3.11)", None, 101, status="in_progress")]
        observation = collect_observation(
            check_runs_payload={"check_runs": checks},
            workflow_runs_payload={"workflow_runs": [self.raw_workflow(101, "PR Gate")]},
            head_sha=HEAD_SHA,
            policy=self.observation_policy,
        )
        plan, receipt = self.plan_for(["README.md"])
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=observation,
            policy=self.observation_policy,
        )
        self.assertEqual(result["status"], "provisional")
        self.assertIn("required_baseline_incomplete", result["promotion"]["reasons"])

    def test_sha_digest_and_authority_mismatches_fail_closed(self):
        plan, receipt = self.plan_for(["README.md"])
        observation = self.observation()
        bad_observation = copy.deepcopy(observation)
        bad_observation["head_sha"] = "3" * 40
        with self.assertRaisesRegex(CIEvaluationError, "head_sha"):
            evaluate(plan=plan, receipt=receipt, observation=bad_observation, policy=self.observation_policy)
        bad_receipt = copy.deepcopy(receipt)
        bad_receipt["plan_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(CIEvaluationError, "plan_digest"):
            evaluate(plan=plan, receipt=bad_receipt, observation=observation, policy=self.observation_policy)
        bad_plan = copy.deepcopy(plan)
        bad_plan["authority"]["merge"] = True
        with self.assertRaisesRegex(CIEvaluationError, "shadow boundary"):
            evaluate(plan=bad_plan, receipt=receipt, observation=observation, policy=self.observation_policy)

    def test_policy_rejects_unknown_fields_and_non_string_patterns(self):
        bad = copy.deepcopy(self.observation_policy)
        bad["authority"] = False
        with self.assertRaisesRegex(CIEvaluationError, "unknown fields"):
            validate_policy(bad)
        bad = copy.deepcopy(self.observation_policy)
        bad["check_mappings"][0]["check_name_patterns"] = [True]
        with self.assertRaisesRegex(CIEvaluationError, "must contain strings"):
            validate_policy(bad)

    def test_outputs_match_published_schemas(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is not installed")
        plan, receipt = self.plan_for(["README.md"])
        observation = self.observation()
        result = evaluate(
            plan=plan,
            receipt=receipt,
            observation=observation,
            policy=self.observation_policy,
        )
        observation_schema = json.loads(
            (ROOT / "schemas/ci-observation-v0.1.schema.json").read_text(encoding="utf-8")
        )
        evaluation_schema = json.loads(
            (ROOT / "schemas/ci-evaluation-v0.1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(observation_schema).validate(observation)
        Draft202012Validator(evaluation_schema).validate(result)
        self.assertEqual(result["observation_digest"], sha256_digest(observation))


if __name__ == "__main__":
    unittest.main()
