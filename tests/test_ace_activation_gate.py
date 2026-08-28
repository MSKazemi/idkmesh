import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ace_activation_gate.py"
SPEC = importlib.util.spec_from_file_location("ace_activation_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class AceActivationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = json.loads(
            (ROOT / "examples" / "community" / "ace-activation-gate-current.example.json").read_text(
                encoding="utf-8"
            )
        )

    def healthy_snapshot(self):
        snapshot = copy.deepcopy(self.current)
        for component in snapshot["components"].values():
            component["status"] = "accepted"
        snapshot["descendant_evidence"]["verified_count"] = 2
        snapshot["descendant_evidence"]["independently_verified"] = True
        snapshot["review_capacity"]["capacity"] = 0.8
        snapshot["review_capacity"]["snapshot_age_hours"] = 1.0
        return snapshot

    def test_current_repository_fixture_blocks(self):
        result = MODULE.evaluate(copy.deepcopy(self.current))
        self.assertEqual(result["decision"], "BLOCK")
        self.assertFalse(result["activation_gate_passed"])
        self.assertEqual(result["required_controller_mode_if_blocked"], "SHADOW")
        self.assertIn("review_capacity", result["blockers"])
        self.assertIn("real_verified_descendant_evidence", result["blockers"])

    def test_all_required_evidence_can_pass(self):
        result = MODULE.evaluate(self.healthy_snapshot())
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["activation_gate_passed"])
        self.assertEqual(result["blockers"], [])

    def test_pending_component_blocks(self):
        snapshot = self.healthy_snapshot()
        snapshot["components"]["security"]["status"] = "pending"
        result = MODULE.evaluate(snapshot)
        self.assertFalse(result["activation_gate_passed"])
        self.assertIn("component:security", result["blockers"])

    def test_descendant_activity_requires_independent_verification(self):
        snapshot = self.healthy_snapshot()
        snapshot["descendant_evidence"]["verified_count"] = 99
        snapshot["descendant_evidence"]["independently_verified"] = False
        result = MODULE.evaluate(snapshot)
        self.assertIn("real_verified_descendant_evidence", result["blockers"])

    def test_low_capacity_blocks_even_when_dependencies_are_accepted(self):
        snapshot = self.healthy_snapshot()
        snapshot["review_capacity"]["capacity"] = 0.2
        result = MODULE.evaluate(snapshot)
        self.assertIn("review_capacity", result["blockers"])

    def test_stale_capacity_blocks(self):
        snapshot = self.healthy_snapshot()
        snapshot["review_capacity"]["snapshot_age_hours"] = 48.0
        result = MODULE.evaluate(snapshot)
        self.assertIn("review_capacity", result["blockers"])

    def test_write_budget_above_one_is_blocked(self):
        snapshot = self.healthy_snapshot()
        snapshot["safety"]["public_write_budget"] = 2
        result = MODULE.evaluate(snapshot)
        self.assertIn("bounded_public_write_budget", result["blockers"])

    def test_forbidden_capability_blocks(self):
        snapshot = self.healthy_snapshot()
        snapshot["safety"]["autonomous_merge_enabled"] = True
        result = MODULE.evaluate(snapshot)
        self.assertIn("forbidden_capabilities_disabled", result["blockers"])

    def test_missing_component_fails_closed(self):
        snapshot = self.healthy_snapshot()
        del snapshot["components"]["observer"]
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_deterministic(self):
        snapshot = self.healthy_snapshot()
        self.assertEqual(MODULE.evaluate(copy.deepcopy(snapshot)), MODULE.evaluate(copy.deepcopy(snapshot)))


if __name__ == "__main__":
    unittest.main()
