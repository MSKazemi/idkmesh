import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("free_resource_planner", ROOT / "scripts" / "free_resource_planner.py")
planner = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(planner)


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "examples/resources/free-resource-registry-v0.1.json").read_text())
        cls.task = json.loads((ROOT / "examples/resources/task-public-code-analysis-v0.1.json").read_text())

    def test_registry_validates(self):
        planner.validate_registry(self.registry)

    def test_no_resource_has_write_or_merge_authority(self):
        for offer in self.registry["offers"]:
            self.assertFalse(offer["security"]["repo_write_authority"])
            self.assertFalse(offer["security"]["merge_authority"])

    def test_planner_requires_public_zero_cost_read_only_task(self):
        bad = dict(self.task)
        bad["requires_repo_write"] = True
        with self.assertRaises(ValueError):
            planner.validate_task(bad)

    def test_github_actions_is_eligible_for_deterministic_verification(self):
        task = dict(self.task)
        task.update(task_class="verifier", requires_llm=False, requires_docker=True, external_processing_ok=False, required_capabilities=[])
        result = planner.plan(self.registry, task, 10, dt.date(2026, 8, 28))
        ids = {item["resource_id"] for item in result["selected"]}
        self.assertIn("github-actions-public-standard", ids)

    def test_external_llm_requires_explicit_external_processing(self):
        task = dict(self.task)
        task.update(task_class="researcher", requires_llm=True, external_processing_ok=False, repository_secret_ok=True)
        result = planner.plan(self.registry, task, 20, dt.date(2026, 8, 28))
        selected = {x["resource_id"] for x in result["selected"]}
        self.assertNotIn("gemini-api-free", selected)

    def test_github_models_is_explicitly_excluded(self):
        result = planner.plan(self.registry, self.task, 20, dt.date(2026, 8, 28))
        rejected = {x["resource_id"]: x["reasons"] for x in result["rejected"]}
        self.assertIn("github-models-retired", rejected)
        self.assertTrue(any("excluded" in reason for reason in rejected["github-models-retired"]))

    def test_stale_resource_is_rejected(self):
        registry = json.loads(json.dumps(self.registry))
        registry["offers"][0]["source"]["checked_at"] = "2026-01-01"
        result = planner.plan(registry, self.task, 20, dt.date(2026, 8, 28))
        rejected = {x["resource_id"]: x["reasons"] for x in result["rejected"]}
        self.assertTrue(any("stale" in r for r in rejected[registry["offers"][0]["id"]]))


if __name__ == "__main__":
    unittest.main()
