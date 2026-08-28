import random
import unittest

from randomness_lab.model import Worker
from randomness_lab.policies import POLICIES, make_policy, power_of_d_least_loaded
from randomness_lab.simulator import SimulationConfig, run_simulation


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


if __name__ == "__main__":
    unittest.main()
