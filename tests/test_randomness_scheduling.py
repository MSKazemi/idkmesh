import tempfile
import unittest
from pathlib import Path

from randomness_lab.scheduling import (
    POLICIES,
    SimulationConfig,
    TraceSpec,
    load_trace_spec,
    run_policy_comparison,
    run_scheduling_simulation,
    save_trace_spec,
    trace_digest,
)


class SchedulingBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = TraceSpec(
            seed=20260828,
            worker_count=20,
            steps=30,
            base_arrivals_per_step=8,
            burst_probability=0.10,
            burst_multiplier=2,
            churn_probability=0.10,
        )
        self.config = SimulationConfig(observation_lag_steps=1, drain_steps=40)

    def test_same_trace_and_policy_are_reproducible(self) -> None:
        first = run_scheduling_simulation(self.spec, "power-of-two", self.config)
        second = run_scheduling_simulation(self.spec, "power-of-two", self.config)
        self.assertEqual(first, second)

    def test_trace_spec_round_trips_and_preserves_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            save_trace_spec(path, self.spec)
            loaded = load_trace_spec(path)
        self.assertEqual(loaded, self.spec)
        self.assertEqual(trace_digest(loaded), trace_digest(self.spec))

    def test_comparison_replays_one_trace_across_all_policies(self) -> None:
        comparison = run_policy_comparison(self.spec, config=self.config)
        self.assertEqual(comparison["policies"], list(POLICIES))
        digests = {result["trace"]["digest"] for result in comparison["results"]}
        self.assertEqual(digests, {trace_digest(self.spec)})

    def test_capability_aware_policy_avoids_capability_mismatches(self) -> None:
        aware = run_scheduling_simulation(
            self.spec,
            "capability-power-of-two",
            self.config,
        )
        generic = run_scheduling_simulation(self.spec, "power-of-two", self.config)
        self.assertEqual(aware["metrics"]["capability_mismatches"], 0)
        self.assertGreaterEqual(
            generic["metrics"]["capability_mismatches"],
            aware["metrics"]["capability_mismatches"],
        )

    def test_oracle_pays_more_dynamic_state_reads_than_power_of_two(self) -> None:
        oracle = run_scheduling_simulation(
            self.spec,
            "global-least-loaded-oracle",
            self.config,
        )
        power_two = run_scheduling_simulation(self.spec, "power-of-two", self.config)
        self.assertGreater(
            oracle["metrics"]["metadata_reads_per_task"],
            power_two["metrics"]["metadata_reads_per_task"],
        )

    def test_metrics_include_churn_recovery_and_queue_quality(self) -> None:
        result = run_scheduling_simulation(self.spec, "power-of-three", self.config)
        metrics = result["metrics"]
        for key in (
            "completion_rate",
            "failed_assignments",
            "retry_recovery_rate",
            "max_queue_depth",
            "p95_queue_depth",
            "p95_task_system_time_steps",
            "utilization",
            "jain_completion_fairness",
            "metadata_reads_per_task",
        ):
            self.assertIn(key, metrics)
        self.assertGreaterEqual(metrics["completion_rate"], 0.0)
        self.assertLessEqual(metrics["completion_rate"], 1.0)
        self.assertGreaterEqual(metrics["retry_recovery_rate"], 0.0)
        self.assertLessEqual(metrics["retry_recovery_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
