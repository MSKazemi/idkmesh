import random
import unittest

from randomness_lab.experiments import run_trials
from randomness_lab.model import Worker
from randomness_lab.policies import POLICIES, make_policy, power_of_d_least_loaded
from randomness_lab.r1 import (
    R1ExperimentConfig,
    build_r1_conditions,
    run_r1_condition,
    run_r1_experiment,
)
from randomness_lab.simulator import SimulationConfig, run_simulation


class AlwaysSuccessEnvironment:
    name = "always-success-test"

    def sample(self, workers, rng):
        del rng
        return {worker.name: True for worker in workers}

    def describe(self):
        return {"name": self.name, "purpose": "test fixture"}


class RandomnessLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workers = [
            Worker("weak", 0.30),
            Worker("middle", 0.55),
            Worker("strong", 0.85),
        ]

    def test_seeded_runs_are_reproducible(self) -> None:
        config = SimulationConfig(rounds=250, seed=17, error_correlation=0.25)
        first = run_simulation(self.workers, make_policy("thompson"), config)
        second = run_simulation(self.workers, make_policy("thompson"), config)
        self.assertEqual(first, second)

    def test_repeated_trials_are_reproducible_and_report_uncertainty(self) -> None:
        kwargs = dict(
            workers=self.workers,
            policy_factory=lambda: make_policy("thompson"),
            rounds=100,
            trials=5,
            base_seed=31,
            error_correlation=0.2,
        )
        first = run_trials(**kwargs)
        second = run_trials(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["trial_count"], 5)
        self.assertEqual(len(first["trials"]), 5)
        self.assertIsNotNone(first["summary"]["normal_approx_95_ci_verified_success_rate"])

    def test_custom_environment_is_swappable(self) -> None:
        result = run_simulation(
            self.workers,
            make_policy("greedy"),
            SimulationConfig(rounds=20, seed=5),
            environment=AlwaysSuccessEnvironment(),
        )
        self.assertEqual(result["environment"]["name"], "always-success-test")
        self.assertEqual(result["metrics"]["verified_success_rate"], 1.0)

    def test_all_registered_policies_run(self) -> None:
        for name in POLICIES:
            with self.subTest(policy=name):
                result = run_simulation(
                    self.workers,
                    make_policy(name),
                    SimulationConfig(rounds=30, seed=3),
                )
                self.assertEqual(result["policy"], name)
                self.assertEqual(sum(result["metrics"]["selected_counts"].values()), 30)

    def test_correlation_control_changes_realized_error_correlation(self) -> None:
        equal_workers = [Worker("a", 0.5), Worker("b", 0.5), Worker("c", 0.5)]
        low = run_simulation(
            equal_workers,
            make_policy("greedy"),
            SimulationConfig(rounds=3000, seed=9, error_correlation=0.0),
        )
        high = run_simulation(
            equal_workers,
            make_policy("greedy"),
            SimulationConfig(rounds=3000, seed=9, error_correlation=1.0),
        )
        low_corr = low["metrics"]["mean_pairwise_error_correlation"]
        high_corr = high["metrics"]["mean_pairwise_error_correlation"]
        self.assertIsNotNone(low_corr)
        self.assertIsNotNone(high_corr)
        self.assertLess(abs(low_corr), 0.10)
        self.assertGreater(high_corr, 0.99)

    def test_thompson_learns_to_prefer_stronger_worker(self) -> None:
        result = run_simulation(
            [Worker("weak", 0.20), Worker("strong", 0.90)],
            make_policy("thompson"),
            SimulationConfig(rounds=1000, seed=101),
        )
        counts = result["metrics"]["selected_counts"]
        self.assertGreater(counts["strong"], counts["weak"])

    def test_power_of_d_can_reduce_to_global_minimum(self) -> None:
        index = power_of_d_least_loaded([10.0, 3.0, 7.0], random.Random(1), d=3)
        self.assertEqual(index, 1)

    def test_r1_experiment_covers_required_conditions_and_raw_trials(self) -> None:
        config = R1ExperimentConfig(
            tasks_per_trial=40,
            trials=3,
            swarm_size=3,
            base_seed=12,
            retain_task_records=False,
        )
        result = run_r1_experiment(config)
        required = {
            "single_deterministic",
            "identical_replication",
            "seed_only",
            "structural_diversity",
            "bandit_selected",
            "diverse_random_verifiers",
        }
        self.assertEqual(set(result["conditions"]), required)
        self.assertEqual(len(result["conditions"]["seed_only"]["raw_trials"]), 3)
        interval = result["conditions"]["seed_only"]["summary"][
            "verified_success_rate"
        ]["normal_approx_95_ci"]
        self.assertEqual(len(interval), 2)

        seed_diversity = result["conditions"]["seed_only"]["summary"][
            "mean_structural_diversity"
        ]["mean"]
        structural_diversity = result["conditions"]["structural_diversity"]["summary"][
            "mean_structural_diversity"
        ]["mean"]
        self.assertGreater(structural_diversity, seed_diversity)
        self.assertIn("lower_success_than_replication", result["comparisons"]["seed_only"])

    def test_r1_is_seed_reproducible(self) -> None:
        config = R1ExperimentConfig(
            tasks_per_trial=20,
            trials=2,
            swarm_size=2,
            base_seed=77,
            retain_task_records=False,
        )
        self.assertEqual(run_r1_experiment(config), run_r1_experiment(config))

    def test_r1_identical_replication_has_identical_base_outcomes(self) -> None:
        config = R1ExperimentConfig(
            tasks_per_trial=10,
            trials=2,
            swarm_size=3,
            base_seed=5,
        )
        identical = next(
            condition
            for condition in build_r1_conditions(config)
            if condition.name == "identical_replication"
        )
        result = run_r1_condition(identical, tasks=20, seed=5, retain_task_records=True)
        for task in result["task_records"]:
            base_outcomes = {candidate["base_success"] for candidate in task["candidates"]}
            self.assertEqual(len(base_outcomes), 1)


if __name__ == "__main__":
    unittest.main()
