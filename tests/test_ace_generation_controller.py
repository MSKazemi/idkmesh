import copy
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ace_generation_controller.py"
SPEC = importlib.util.spec_from_file_location("ace_generation_controller", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class AceGenerationControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "examples" / "community" / "ace-generation-shadow.example.json").read_text(encoding="utf-8")
        )

    def test_weights_normalize_and_mutation_keeps_all_strategies_alive(self):
        result = MODULE.evaluate(copy.deepcopy(self.fixture))
        weights = result["next_weights"]
        self.assertTrue(math.isclose(sum(weights.values()), 1.0, abs_tol=1e-8))
        self.assertTrue(all(value > 0.0 for value in weights.values()))
        self.assertEqual(result["evidence_format"], MODULE.EVIDENCE_FORMAT)

    def test_unverified_lineage_cannot_create_positive_strategy_fitness(self):
        snapshot = copy.deepcopy(self.fixture)
        for receipt in snapshot["lineage_receipts"]:
            receipt["status"] = "candidate"
            receipt["verified"] = False
        for outcome in snapshot["strategy_outcomes"]:
            outcome["value"] = 1000.0
        result = MODULE.evaluate(snapshot)
        self.assertLessEqual(result["strategy_fitness"]["reproduce"], 0.0)
        self.assertLessEqual(result["strategy_fitness"]["challenge"], 0.0)
        self.assertEqual(result["verified_descendants"], 0)

    def test_verified_lineage_counts_reproduction_without_strategy_outcome(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["strategy_outcomes"] = [
            row for row in snapshot["strategy_outcomes"]
            if row["lineage_identity"] != "lineage:pr39-reproduction"
        ]
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["verified_descendants"], 1)
        self.assertEqual(result["R_community"], 0.5)
        self.assertEqual(result["strategy_fitness"]["reproduce"], 0.0)

    def test_strategy_outcome_must_reference_known_lineage(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["strategy_outcomes"][0]["lineage_identity"] = "lineage:missing"
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_verified_flag_must_match_lineage_status(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["lineage_receipts"][0]["verified"] = False
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_reviewer_minutes_cannot_be_duplicated_in_strategy_outcome(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["strategy_outcomes"][0]["reviewer_minutes"] = 8
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_legacy_descendants_input_is_rejected(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["descendants"] = []
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_overload_forces_consolidation_zero_action_and_policy_bias(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["review_load"] = 20.0
        snapshot["policy"]["activation_gate_passed"] = True
        snapshot["policy"]["actuation_enabled"] = True
        prior_consolidate = snapshot["weights"]["consolidate"] / sum(snapshot["weights"].values())

        result = MODULE.evaluate(snapshot)

        self.assertEqual(result["mode"], "CONSOLIDATE")
        self.assertEqual(result["recommendation"], "consolidate")
        self.assertLess(result["capacity"], MODULE.CONSOLIDATE_CAPACITY_THRESHOLD)
        self.assertIsNone(result["public_action"])
        self.assertGreater(result["next_weights"]["consolidate"], prior_consolidate)
        self.assertTrue(all(value > 0.0 for value in result["next_weights"].values()))

    def test_shadow_mode_never_emits_public_action(self):
        result = MODULE.evaluate(copy.deepcopy(self.fixture))
        self.assertFalse(result["activation_gate_passed"])
        self.assertFalse(result["actuation_enabled"])
        self.assertIsNone(result["public_action"])

    def test_activation_gate_blocks_action_even_if_actuation_enabled(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["policy"]["activation_gate_passed"] = False
        snapshot["policy"]["actuation_enabled"] = True
        result = MODULE.evaluate(snapshot)
        self.assertFalse(result["activation_gate_passed"])
        self.assertTrue(result["actuation_enabled"])
        self.assertIsNotNone(result["recommendation"])
        self.assertIsNone(result["public_action"])

    def test_healthy_open_gates_model_at_most_one_bounded_action(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["policy"]["activation_gate_passed"] = True
        snapshot["policy"]["actuation_enabled"] = True
        result = MODULE.evaluate(snapshot)
        self.assertGreaterEqual(result["capacity"], MODULE.ACTION_CAPACITY_FLOOR)
        self.assertNotEqual(result["mode"], "CONSOLIDATE")
        self.assertIsNotNone(result["public_action"])
        self.assertEqual(result["public_action"]["max_public_writes"], 1)

    def test_action_budget_cannot_exceed_one(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["policy"]["public_write_budget"] = 2
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_duplicate_lineage_identities_are_rejected(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["lineage_receipts"].append(copy.deepcopy(snapshot["lineage_receipts"][0]))
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_invalid_activation_gate_type_is_rejected(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["policy"]["activation_gate_passed"] = "yes"
        with self.assertRaises(ValueError):
            MODULE.evaluate(snapshot)

    def test_fixed_snapshot_is_deterministic(self):
        first = MODULE.evaluate(copy.deepcopy(self.fixture))
        second = MODULE.evaluate(copy.deepcopy(self.fixture))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
