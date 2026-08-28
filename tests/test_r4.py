import random
import unittest

from randomness_lab.r4 import (
    R4_POLICIES,
    StigmergicRoutingPolicy,
    default_r4_environment,
    lockin_r4_environment,
    run_r4_benchmark,
    run_r4_policy,
)


class R4StigmergyTests(unittest.TestCase):
    def test_unverified_activity_cannot_increase_pheromone(self):
        policy = StigmergicRoutingPolicy(
            name="test",
            evaporation_rate=0.0,
            exploration_floor=0.0,
        )
        policy.select("code", ["worker-a"], 0, random.Random(1))
        before = policy.snapshot()["pheromone"]["code"]["worker-a"]
        policy.record_activity("code", "worker-a", 0)
        after = policy.snapshot()["pheromone"]["code"]["worker-a"]
        self.assertEqual(before, after)
        self.assertEqual(policy.unverified_activity_events, 1)
        self.assertEqual(policy.unverified_activity_pheromone_increase, 0.0)

    def test_verified_success_deposits_and_verified_failure_does_not_increase(self):
        policy = StigmergicRoutingPolicy(
            name="test",
            evaporation_rate=0.0,
            exploration_floor=0.0,
            success_deposit=1.5,
            failure_penalty=0.25,
        )
        policy.select("code", ["worker-a"], 0, random.Random(1))
        initial = policy.snapshot()["pheromone"]["code"]["worker-a"]
        policy.record_verified("code", "worker-a", True, 0)
        after_success = policy.snapshot()["pheromone"]["code"]["worker-a"]
        self.assertAlmostEqual(after_success, initial + 1.5)
        policy.record_verified("code", "worker-a", False, 1)
        after_failure = policy.snapshot()["pheromone"]["code"]["worker-a"]
        self.assertLess(after_failure, after_success)
        self.assertEqual(policy.verified_success_deposit_events, 1)
        self.assertEqual(policy.verified_failure_penalty_events, 1)

    def test_evaporation_reduces_existing_pheromone(self):
        policy = StigmergicRoutingPolicy(
            name="test",
            evaporation_rate=0.10,
            exploration_floor=0.0,
        )
        policy.select("code", ["worker-a"], 0, random.Random(1))
        policy.record_verified("code", "worker-a", True, 0)
        before = policy.snapshot()["pheromone"]["code"]["worker-a"]
        policy.before_step(1)
        after = policy.snapshot()["pheromone"]["code"]["worker-a"]
        self.assertLess(after, before)
        self.assertAlmostEqual(after, before * 0.90)

    def test_default_benchmark_replays_same_trace_for_every_policy(self):
        environment = default_r4_environment(
            steps=120,
            shift_step=60,
            task_seed=9,
            outcome_seed=99,
        )
        report = run_r4_benchmark(
            environment,
            policy_seed=7,
            include_events=False,
        )
        self.assertEqual(set(report["policies"]), set(R4_POLICIES))
        digests = {
            result["trace_digest"] for result in report["policies"].values()
        }
        self.assertEqual(len(digests), 1)
        self.assertEqual(report["trace_digest"], next(iter(digests)))

    def test_r4_is_seed_reproducible(self):
        environment = default_r4_environment(
            steps=100,
            shift_step=50,
            task_seed=12,
            outcome_seed=21,
        )
        first = run_r4_policy(
            environment,
            "stigmergy-evap-explore",
            policy_seed=18,
            include_events=True,
        )
        second = run_r4_policy(
            environment,
            "stigmergy-evap-explore",
            policy_seed=18,
            include_events=True,
        )
        self.assertEqual(first, second)

    def test_stigmergy_trace_proves_activity_never_deposits(self):
        environment = default_r4_environment(steps=100, shift_step=50)
        result = run_r4_policy(
            environment,
            "stigmergy-evap-explore",
            policy_seed=3,
            include_events=True,
        )
        metrics = result["metrics"]
        self.assertEqual(metrics["unverified_activity_events"], 100)
        self.assertEqual(metrics["unverified_activity_pheromone_increase"], 0.0)
        self.assertEqual(
            metrics["verified_success_deposit_events"],
            metrics["verified_successes"],
        )
        self.assertTrue(result["integrity"]["pheromone_updates_require_verified_outcome"])
        self.assertFalse(result["integrity"]["routing_weight_can_accept_unverified_result"])

    def test_exploration_condition_gives_newcomers_opportunities(self):
        environment = default_r4_environment(
            steps=240,
            shift_step=120,
            task_seed=4,
            outcome_seed=5,
        )
        result = run_r4_policy(
            environment,
            "stigmergy-evap-explore",
            policy_seed=6,
            include_events=False,
        )
        first_assignments = result["metrics"]["newcomer_first_assignment_step"]
        self.assertIsNotNone(first_assignments["newcomer-strong"])
        self.assertIsNotNone(first_assignments["newcomer-weak"])
        self.assertGreater(result["metrics"]["newcomer_assignment_share"], 0.0)

    def test_lockin_fixture_exposes_no_evaporation_harm(self):
        environment = lockin_r4_environment(
            steps=500,
            shift_step=100,
            task_seed=11,
            outcome_seed=1111,
        )
        no_evap = run_r4_policy(
            environment,
            "stigmergy-no-evap",
            policy_seed=77,
            include_events=False,
        )
        adaptive = run_r4_policy(
            environment,
            "stigmergy-evap-explore",
            policy_seed=77,
            include_events=False,
        )
        self.assertGreater(
            no_evap["metrics"]["cumulative_expected_regret"],
            adaptive["metrics"]["cumulative_expected_regret"],
        )
        self.assertLess(
            no_evap["metrics"]["post_shift_verified_success_rate"],
            adaptive["metrics"]["post_shift_verified_success_rate"],
        )
        self.assertGreater(
            no_evap["metrics"]["longest_failed_same_worker_lockin"],
            adaptive["metrics"]["longest_failed_same_worker_lockin"],
        )

    def test_pheromone_snapshots_are_machine_readable(self):
        environment = default_r4_environment(steps=100, shift_step=50)
        result = run_r4_policy(
            environment,
            "stigmergy-evap",
            policy_seed=2,
            include_events=False,
        )
        self.assertGreater(len(result["pheromone_snapshots"]), 1)
        for snapshot in result["pheromone_snapshots"]:
            self.assertIn("step", snapshot)
            self.assertIn("state", snapshot)
            self.assertIn("pheromone", snapshot["state"])


if __name__ == "__main__":
    unittest.main()
