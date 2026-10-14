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
        cls.scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "ace_generation_scenarios_v1.json").read_text(encoding="utf-8")
        )
        cls.fixture = json.loads((ROOT / cls.scenarios["base_snapshot"]).read_text(encoding="utf-8"))

    def scenario_snapshot(self, scenario):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["review_load"] = scenario["review_load"]
        statuses = scenario["lineage_statuses"]
        for receipt in snapshot["lineage_receipts"]:
            receipt["status"] = statuses[receipt["identity"]]
            receipt["verified"] = receipt["status"] == "verified"
        return snapshot

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

    def test_duplicate_descendant_under_different_identity_is_rejected(self):
        snapshot = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(snapshot["lineage_receipts"][0])
        duplicate["identity"] = "lineage:duplicate-event-with-new-id"
        snapshot["lineage_receipts"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate descendant artifact"):
            MODULE.evaluate(snapshot)

    def test_descendant_of_ineligible_parent_does_not_enter_reproduction_number(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["parents"][0]["matured"] = False
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["verified_descendants"], 0)
        self.assertEqual(result["eligible_matured_verified_parents"], 1)
        self.assertEqual(result["R_community"], 0.0)
        self.assertEqual(result["R_community_status"], "observed_ratio")

    def test_reproduction_ratio_is_undefined_without_eligible_parent_denominator(self):
        snapshot = copy.deepcopy(self.fixture)
        for parent in snapshot["parents"]:
            parent["matured"] = False

        result = MODULE.evaluate(snapshot)

        self.assertEqual(result["version"], 2)
        self.assertEqual(result["eligible_matured_verified_parents"], 0)
        self.assertEqual(result["verified_descendants"], 0)
        self.assertIsNone(result["R_community"])
        self.assertEqual(result["R_community_status"], "undefined_no_eligible_parents")
        self.assertEqual(result["mode"], "DORMANT")
        self.assertIsNone(result["recommendation"])
        self.assertIsNone(result["public_action"])

    def test_reproduction_ratio_remains_observed_when_denominator_exists(self):
        result = MODULE.evaluate(copy.deepcopy(self.fixture))
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["eligible_matured_verified_parents"], 2)
        self.assertEqual(result["R_community"], 0.5)
        self.assertEqual(result["R_community_status"], "observed_ratio")

    def test_fixed_state_fixture_matrix_is_deterministic(self):
        self.assertEqual(self.scenarios["version"], 1)
        for scenario in self.scenarios["cases"]:
            with self.subTest(scenario=scenario["name"]):
                snapshot = self.scenario_snapshot(scenario)
                first = MODULE.evaluate(copy.deepcopy(snapshot))
                second = MODULE.evaluate(copy.deepcopy(snapshot))
                self.assertEqual(first, second)
                self.assertEqual(first["mode"], scenario["expected"]["mode"])
                self.assertEqual(first["R_community"], scenario["expected"]["R_community"])
                self.assertEqual(
                    first["verified_descendants"],
                    scenario["expected"]["verified_descendants"],
                )
                self.assertIsNone(first["public_action"])

    # --- Properties of the issue #57 formulas that earlier tests left unpinned. ---
    # Each expected value below is derived by hand from the formulas in the issue,
    # not copied from the controller's output.

    def _outcome_row(self, snapshot, identity):
        return next(row for row in snapshot["strategy_outcomes"] if row["lineage_identity"] == identity)

    def test_strategy_fitness_matches_the_documented_formula(self):
        # f = value / (1 + reviewer_min + maintainer_min) - l_lat * latency - l_noise * noise
        # reproduce: 1 / (1 + 8 + 2) - 0.002 * 0.5 - 0.15 * 0 ; challenge is an
        # unverified candidate, so its benefit is 0 and only its latency cost remains.
        fitness = MODULE.strategy_fitness(copy.deepcopy(self.fixture))
        self.assertAlmostEqual(fitness["reproduce"], 1.0 / 11.0 - 0.001, places=12)
        self.assertAlmostEqual(fitness["challenge"], -0.002 * 0.25, places=12)
        for strategy in ("extend", "explain", "review", "onboard", "consolidate"):
            self.assertEqual(fitness[strategy], 0.0)

    def test_every_cost_term_lowers_fitness(self):
        base = MODULE.strategy_fitness(copy.deepcopy(self.fixture))["reproduce"]

        noisy = copy.deepcopy(self.fixture)
        self._outcome_row(noisy, "lineage:pr39-reproduction")["unproductive_public_writes"] = 2
        self.assertAlmostEqual(MODULE.strategy_fitness(noisy)["reproduce"], base - 0.15 * 2, places=12)

        slow = copy.deepcopy(self.fixture)
        self._outcome_row(slow, "lineage:pr39-reproduction")["added_review_latency_hours"] = 10.5
        self.assertAlmostEqual(MODULE.strategy_fitness(slow)["reproduce"], base - 0.002 * 10.0, places=12)

        busy = copy.deepcopy(self.fixture)
        self._outcome_row(busy, "lineage:pr39-reproduction")["maintainer_minutes"] = 22
        self.assertAlmostEqual(
            MODULE.strategy_fitness(busy)["reproduce"], 1.0 / (1.0 + 8 + 22) - 0.001, places=12
        )

        reviewed = copy.deepcopy(self.fixture)
        for receipt in reviewed["lineage_receipts"]:
            if receipt["identity"] == "lineage:pr39-reproduction":
                receipt["reviewer_minutes"] = 28
        self.assertAlmostEqual(
            MODULE.strategy_fitness(reviewed)["reproduce"], 1.0 / (1.0 + 28 + 2) - 0.001, places=12
        )

    def test_selection_moves_mass_toward_the_fitter_strategy(self):
        result = MODULE.evaluate(copy.deepcopy(self.fixture))
        fitness = result["strategy_fitness"]
        weights = result["next_weights"]
        self.assertEqual(max(fitness, key=fitness.get), "reproduce")
        self.assertGreater(weights["reproduce"], 1.0 / len(MODULE.STRATEGIES))
        self.assertGreater(weights["reproduce"], weights["challenge"])
        self.assertLess(weights["challenge"], 1.0 / len(MODULE.STRATEGIES))

    def test_next_weights_match_an_independent_replicator_mutator_computation(self):
        snapshot = copy.deepcopy(self.fixture)
        strategies = MODULE.STRATEGIES
        raw = [float(snapshot["weights"][s]) for s in strategies]
        current = [w / sum(raw) for w in raw]
        fitness = MODULE.strategy_fitness(snapshot)
        eta, mu = snapshot["policy"]["eta"], snapshot["policy"]["mu"]
        mean = sum(c * fitness[s] for c, s in zip(current, strategies))
        selected = [c * math.exp(eta * (fitness[s] - mean)) for c, s in zip(current, strategies)]
        selected = [x / sum(selected) for x in selected]
        expected = [(1.0 - mu) * x + mu / len(strategies) for x in selected]

        result = MODULE.evaluate(snapshot)
        self.assertGreaterEqual(result["capacity"], MODULE.CONSOLIDATE_CAPACITY_THRESHOLD)
        for strategy, want in zip(strategies, expected):
            self.assertAlmostEqual(result["next_weights"][strategy], want, places=8, msg=strategy)

    def test_mutation_floor_holds_for_every_strategy_under_extreme_selection(self):
        # One strategy has overwhelming verified value; selection would otherwise
        # drive every other weight to ~0. The mu/n term must keep all of them alive.
        snapshot = copy.deepcopy(self.fixture)
        self._outcome_row(snapshot, "lineage:pr39-reproduction")["value"] = 1.0e6
        snapshot["policy"]["eta"] = 10.0
        mu = snapshot["policy"]["mu"]
        result = MODULE.evaluate(snapshot)
        self.assertGreaterEqual(result["capacity"], MODULE.CONSOLIDATE_CAPACITY_THRESHOLD)
        floor = mu / len(MODULE.STRATEGIES)
        for strategy, weight in result["next_weights"].items():
            self.assertGreaterEqual(weight, floor - 1e-9, msg=strategy)
        self.assertGreater(result["next_weights"]["reproduce"], 0.9 - 1e-6)

    def test_overload_lowers_but_never_removes_the_exploration_floor(self):
        # The mu/n floor is a property of the learning step. Capacity homeostasis then
        # moves up to 90% of each growth strategy's mass to `consolidate`, so the
        # published floor under full overload is 0.1 * mu/n, not mu/n.
        snapshot = copy.deepcopy(self.fixture)
        snapshot["review_load"] = 1000.0
        mu = snapshot["policy"]["mu"]
        n = len(MODULE.STRATEGIES)
        fitness = MODULE.strategy_fitness(snapshot)
        learned = MODULE.update_weights(snapshot, fitness)
        for strategy, weight in learned.items():
            self.assertGreaterEqual(weight, mu / n - 1e-12, msg=strategy)

        result = MODULE.evaluate(snapshot)
        self.assertLess(result["capacity"], 1e-6)
        for strategy in MODULE.GROWTH_STRATEGIES:
            published = result["next_weights"][strategy]
            self.assertGreaterEqual(published, 0.1 * learned[strategy] - 1e-9, msg=strategy)
            self.assertGreaterEqual(published, 0.1 * mu / n - 1e-9, msg=strategy)
            self.assertLess(published, learned[strategy], msg=strategy)
        self.assertGreater(result["next_weights"]["consolidate"], learned["consolidate"])
        self.assertTrue(math.isclose(sum(result["next_weights"].values()), 1.0, abs_tol=1e-8))

    def test_zero_public_write_budget_suppresses_the_action(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["policy"]["activation_gate_passed"] = True
        snapshot["policy"]["actuation_enabled"] = True
        self.assertIsNotNone(MODULE.evaluate(copy.deepcopy(snapshot))["public_action"])
        snapshot["policy"]["public_write_budget"] = 0
        result = MODULE.evaluate(snapshot)
        self.assertEqual(result["public_write_budget"], 0)
        self.assertIsNotNone(result["recommendation"])
        self.assertIsNone(result["public_action"])

    def test_two_strategy_outcomes_for_one_lineage_identity_are_rejected(self):
        snapshot = copy.deepcopy(self.fixture)
        snapshot["strategy_outcomes"].append(copy.deepcopy(snapshot["strategy_outcomes"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate strategy outcome"):
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
