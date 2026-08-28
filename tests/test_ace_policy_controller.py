import unittest

from experiments.ace_policy_controller import (
    ControllerConfig,
    Evidence,
    STRATEGIES,
    advance_generation,
    compute_fitness,
    deduplicate_evidence,
    fixture_scenarios,
    uniform_weights,
)


class ACEPolicyControllerTests(unittest.TestCase):
    def test_weights_normalize_and_keep_exploration_nonzero(self):
        fixture = fixture_scenarios()["healthy-reproduction"]
        decision = advance_generation(
            uniform_weights(),
            fixture["evidence"],
            review_load=fixture["review_load"],
            eligible_parent_count=fixture["eligible_parent_count"],
        )
        self.assertAlmostEqual(sum(decision.next_weights.values()), 1.0, places=12)
        self.assertTrue(all(weight > 0 for weight in decision.next_weights.values()))

    def test_no_verified_descendant_creates_no_positive_fitness(self):
        evidence = [
            Evidence(
                evidence_id="candidate-1",
                strategy="extend",
                verified=False,
                reviewer_minutes=2,
                public_writes=1,
            ),
            Evidence(
                evidence_id="candidate-2",
                strategy="onboard",
                verified=False,
                reviewer_minutes=1,
            ),
        ]
        fitness = compute_fitness(evidence, ControllerConfig())
        self.assertTrue(all(value <= 0 for value in fitness.values()))

        decision = advance_generation(
            uniform_weights(),
            evidence,
            review_load=2,
            eligible_parent_count=5,
            activation_gate_passed=True,
            actuation_enabled=True,
        )
        self.assertEqual(decision.mode, "EXPLORE")
        self.assertIsNone(decision.recommendation)
        self.assertEqual(decision.public_actions, ())

    def test_identical_duplicate_evidence_is_counted_once(self):
        item = Evidence(
            evidence_id="lineage:pr-100",
            strategy="reproduce",
            verified=True,
            verified_value=1.0,
            reviewer_minutes=1,
        )
        unique = deduplicate_evidence([item, item, item])
        self.assertEqual(unique, [item])

        decision = advance_generation(
            uniform_weights(),
            [item, item, item],
            review_load=2,
            eligible_parent_count=1,
        )
        self.assertEqual(decision.unique_evidence, 1)
        self.assertEqual(decision.verified_descendants, 1)
        self.assertEqual(decision.r_community, 1.0)

    def test_conflicting_duplicate_evidence_fails_closed(self):
        first = Evidence(
            evidence_id="lineage:pr-100",
            strategy="reproduce",
            verified=False,
        )
        conflicting = Evidence(
            evidence_id="lineage:pr-100",
            strategy="reproduce",
            verified=True,
            verified_value=1.0,
        )
        with self.assertRaises(ValueError):
            deduplicate_evidence([first, conflicting])

    def test_healthy_reproduction_can_recommend_at_most_one_action(self):
        fixture = fixture_scenarios()["healthy-reproduction"]
        decision = advance_generation(
            uniform_weights(),
            fixture["evidence"],
            review_load=fixture["review_load"],
            eligible_parent_count=fixture["eligible_parent_count"],
            activation_gate_passed=True,
            actuation_enabled=True,
        )
        self.assertEqual(decision.mode, "GROW")
        self.assertGreaterEqual(decision.r_community, 1.0)
        self.assertLessEqual(len(decision.public_actions), 1)
        self.assertEqual(len(decision.public_actions), 1)
        self.assertIn(decision.public_actions[0], STRATEGIES)

    def test_overload_forces_consolidation_and_zero_public_actions(self):
        fixture = fixture_scenarios()["overload"]
        previous = uniform_weights()
        decision = advance_generation(
            previous,
            fixture["evidence"],
            review_load=fixture["review_load"],
            eligible_parent_count=fixture["eligible_parent_count"],
            activation_gate_passed=True,
            actuation_enabled=True,
        )
        self.assertEqual(decision.mode, "CONSOLIDATE")
        self.assertEqual(decision.recommendation, "consolidate")
        self.assertEqual(decision.public_actions, ())
        self.assertLess(decision.capacity, ControllerConfig().consolidate_capacity_threshold)
        self.assertGreater(decision.next_weights["consolidate"], previous["consolidate"])
        self.assertTrue(all(weight > 0 for weight in decision.next_weights.values()))

    def test_activation_gate_blocks_action_even_when_healthy(self):
        fixture = fixture_scenarios()["healthy-reproduction"]
        decision = advance_generation(
            uniform_weights(),
            fixture["evidence"],
            review_load=fixture["review_load"],
            eligible_parent_count=fixture["eligible_parent_count"],
            activation_gate_passed=False,
            actuation_enabled=True,
        )
        self.assertEqual(decision.mode, "GROW")
        self.assertEqual(decision.public_actions, ())
        self.assertIn("activation gate not passed", decision.reason)

    def test_action_budget_cannot_exceed_one(self):
        with self.assertRaises(ValueError):
            ControllerConfig(max_public_actions=2)

    def test_fixture_results_are_deterministic(self):
        fixture = fixture_scenarios()["healthy-reproduction"]
        kwargs = dict(
            review_load=fixture["review_load"],
            eligible_parent_count=fixture["eligible_parent_count"],
            activation_gate_passed=True,
            actuation_enabled=True,
        )
        first = advance_generation(uniform_weights(), fixture["evidence"], **kwargs)
        second = advance_generation(uniform_weights(), fixture["evidence"], **kwargs)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
