import unittest

from experiments.verification_backpressure import ControllerConfig
from experiments.verification_backpressure_benchmark import (
    POLICIES,
    benchmark,
    make_synthetic_candidate,
    schedule_policy,
    simulate,
)


class VerificationBackpressureBenchmarkTests(unittest.TestCase):
    def test_candidate_stream_is_seed_reproducible(self):
        self.assertEqual(
            make_synthetic_candidate(seed=11, index=7),
            make_synthetic_candidate(seed=11, index=7),
        )
        self.assertNotEqual(
            make_synthetic_candidate(seed=11, index=7),
            make_synthetic_candidate(seed=11, index=8),
        )

    def test_every_scheduler_respects_window_capacity(self):
        queue = [make_synthetic_candidate(5, index) for index in range(30)]
        config = ControllerConfig()
        for policy in POLICIES:
            with self.subTest(policy=policy):
                selected = schedule_policy(queue, 5.0, policy, config)
                used = sum(
                    item.candidate.estimated_verification_cost
                    for item in selected
                )
                self.assertLessEqual(used, 5.0 + 1e-9)

    def test_fixed_policies_receive_identical_seeded_workload(self):
        kwargs = dict(
            seed=2,
            steps=25,
            initial_fanout=4,
            verification_capacity_per_window=8.0,
        )
        runs = [
            simulate(policy=policy, **kwargs)
            for policy in (
                "fifo",
                "highest-risk-first",
                "cheapest-first",
                "rwvb-fixed",
            )
        ]
        digests = {run["generated_stream_sha256"] for run in runs}
        generated = {run["generated_candidates"] for run in runs}
        self.assertEqual(len(digests), 1)
        self.assertEqual(len(generated), 1)

    def test_run_is_exactly_reproducible(self):
        kwargs = dict(
            policy="rwvb-adaptive",
            seed=7,
            steps=50,
            initial_fanout=12,
            verification_capacity_per_window=8.0,
        )
        self.assertEqual(simulate(**kwargs), simulate(**kwargs))

    def test_adaptive_rwvb_contracts_overloaded_generation(self):
        kwargs = dict(
            seed=7,
            steps=80,
            initial_fanout=12,
            verification_capacity_per_window=8.0,
        )
        fixed = simulate(policy="rwvb-fixed", **kwargs)
        adaptive = simulate(policy="rwvb-adaptive", **kwargs)

        self.assertLess(
            adaptive["pending_candidates"],
            fixed["pending_candidates"],
        )
        self.assertLess(
            adaptive["final_verification_debt"],
            fixed["final_verification_debt"],
        )
        self.assertLess(
            adaptive["peak_queue_length"],
            fixed["peak_queue_length"],
        )
        self.assertLess(adaptive["final_fanout"], 12)

    def test_adaptive_rwvb_can_use_idle_verification_capacity(self):
        kwargs = dict(
            seed=3,
            steps=60,
            initial_fanout=2,
            verification_capacity_per_window=8.0,
        )
        fixed = simulate(policy="rwvb-fixed", **kwargs)
        adaptive = simulate(policy="rwvb-adaptive", **kwargs)

        self.assertGreater(
            adaptive["generated_candidates"],
            fixed["generated_candidates"],
        )
        self.assertGreater(
            adaptive["verified_candidates"],
            fixed["verified_candidates"],
        )
        self.assertGreater(adaptive["max_fanout"], 2)

    def test_synthetic_verifier_never_has_integration_authority(self):
        run = simulate(
            policy="highest-risk-first",
            seed=1,
            steps=10,
            initial_fanout=4,
            verification_capacity_per_window=8.0,
        )
        self.assertEqual(run["integration_authority"], "none")
        self.assertNotIn("merged_candidates", run)
        self.assertNotIn("accepted_candidates", run)

    def test_benchmark_contains_all_policy_fanout_cells(self):
        result = benchmark(
            seeds=2,
            steps=10,
            fanouts=[2, 8],
            verification_capacity_per_window=8.0,
            include_runs=False,
        )
        cells = {
            (row["initial_fanout"], row["policy"])
            for row in result["summaries"]
        }
        expected = {
            (fanout, policy)
            for fanout in (2, 8)
            for policy in POLICIES
        }
        self.assertEqual(cells, expected)
        self.assertNotIn("runs", result)


if __name__ == "__main__":
    unittest.main()
