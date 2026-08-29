import hashlib
import json
from pathlib import Path
import unittest

from randomness_lab.r2_factor_sweep import (
    OBSERVATION_LAGS,
    OFFERED_LOAD_TARGETS,
    R2FactorSweepConfig,
    failure_shape_trace,
    run_factor_sweep,
    run_profile,
    saturation_trace,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "results"
    / "experiments"
    / "r2"
    / "reference-factor-isolation-seeds41-45.json"
)
PROFILE_REFERENCE = (
    ROOT
    / "results"
    / "experiments"
    / "r2"
    / "reference-factor-isolation-profile.json"
)
REFERENCE_SHA256 = "988b002bdbbd28a92c34825381ccbe45f09384780494a3300f91457987f680fa"
PROFILE_SHA256 = "0265c4cc971b7e4f8cbf0f8113a2850676378540715a4cbacc44f36b81cdc0ee"


class R2FactorSweepTests(unittest.TestCase):
    def setUp(self):
        self.config = R2FactorSweepConfig(
            trace_seeds=(3,),
            standard_worker_count=30,
            ticks=12,
            drain_ticks=40,
        )

    def test_failure_shapes_match_count_and_duration_but_regional_is_correlated(self):
        independent = failure_shape_trace(seed=3, regional=False, config=self.config)
        regional = failure_shape_trace(seed=3, regional=True, config=self.config)
        self.assertEqual(independent.workers, regional.workers)
        self.assertEqual(independent.tasks, regional.tasks)
        self.assertEqual(len(independent.outages), len(regional.outages))
        self.assertEqual(
            {outage.end_tick - outage.start_tick for outage in independent.outages},
            {6},
        )
        self.assertEqual(
            {outage.end_tick - outage.start_tick for outage in regional.outages},
            {6},
        )
        self.assertGreater(len({outage.start_tick for outage in independent.outages}), 1)
        self.assertEqual(len({outage.start_tick for outage in regional.outages}), 1)
        self.assertEqual(
            len(
                {
                    regional.workers[outage.worker_index].zone
                    for outage in regional.outages
                }
            ),
            1,
        )

    def test_saturation_traces_are_nested_and_increase_offered_work(self):
        low = saturation_trace(seed=3, target=0.25, config=self.config)
        high = saturation_trace(seed=3, target=1.25, config=self.config)
        self.assertEqual(low.workers, high.workers)
        self.assertLess(len(low.tasks), len(high.tasks))
        self.assertTrue({task.id for task in low.tasks} < {task.id for task in high.tasks})
        low_work = sum(task.work_units for task in low.tasks)
        high_work = sum(task.work_units for task in high.tasks)
        self.assertLess(low_work, high_work)

    def test_benchmark_is_reproducible_and_retains_every_seed(self):
        config = R2FactorSweepConfig(
            trace_seeds=(3, 4),
            standard_worker_count=30,
            ticks=12,
            drain_ticks=40,
        )
        first = run_factor_sweep(config)
        second = run_factor_sweep(config)
        self.assertEqual(first, second)
        expected_cells = (
            len(OBSERVATION_LAGS)
            + len(OBSERVATION_LAGS) - 1
            + 2
            + len(OFFERED_LOAD_TARGETS)
        )
        self.assertEqual(len(first["cells"]), expected_cells)
        self.assertEqual(len(first["raw_runs"]), expected_cells * 2)
        self.assertTrue(all(cell["runs"] == 2 for cell in first["cells"]))
        self.assertEqual(first["authority"]["integration_authority"], "none")

    def test_staleness_controls_hold_the_other_lag_at_zero(self):
        report = run_factor_sweep(self.config)
        availability = [
            run for run in report["raw_runs"] if run["factor"] == "availability_lag"
        ]
        load = [run for run in report["raw_runs"] if run["factor"] == "load_lag"]
        self.assertEqual({run["load_observation_lag"] for run in availability}, {0})
        self.assertEqual({run["availability_observation_lag"] for run in load}, {0})
        self.assertEqual(len({run["trace"]["trace_digest"] for run in availability + load}), 1)

    def test_coordination_costs_distinguish_directory_and_sampling_work(self):
        report = run_factor_sweep(self.config)
        run = report["raw_runs"][0]
        random_cost = run["policies"]["one-random"]["coordination_cost"]
        capable_cost = run["policies"]["capability-power-two"]["coordination_cost"]
        oracle_cost = run["policies"]["global-least-loaded"]["coordination_cost"]
        self.assertEqual(random_cost["capability_directory_initialization_operations"], 0)
        self.assertGreater(capable_cost["capability_directory_initialization_operations"], 0)
        self.assertGreaterEqual(
            oracle_cost["metadata_probe_operations"],
            capable_cost["metadata_probe_operations"],
        )
        self.assertEqual(
            capable_cost["modeled_total_messages"],
            capable_cost["modeled_routing_messages"]
            + capable_cost["modeled_directory_messages"],
        )

    def test_profile_keeps_host_measurements_separate(self):
        profile = run_profile(self.config, repetitions=1)
        self.assertIn("environment", profile)
        self.assertIn("host-specific", profile["guardrail"])
        for policy in profile["policies"].values():
            self.assertEqual(len(policy["cpu_time_ms_samples"]), 1)
            self.assertGreater(policy["cpu_time_ms_median"], 0.0)
            self.assertGreater(policy["peak_traced_bytes_median"], 0.0)

    def test_reference_artifacts_preserve_factor_isolation_claims(self):
        raw = REFERENCE.read_bytes()
        profile_raw = PROFILE_REFERENCE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), REFERENCE_SHA256)
        self.assertEqual(hashlib.sha256(profile_raw).hexdigest(), PROFILE_SHA256)
        report = json.loads(raw)
        self.assertEqual(report["authority"]["integration_authority"], "none")
        self.assertEqual(len(report["raw_runs"]), 80)
        cells = {
            (cell["factor"], cell["level"]): cell for cell in report["cells"]
        }

        fresh = cells[("availability_lag", "0")]["aggregate"]
        availability_stale = cells[("availability_lag", "10")]["aggregate"]
        load_stale = cells[("load_lag", "10")]["aggregate"]
        self.assertEqual(
            fresh["capability-power-two"]["metrics"]["failed_unreachable"]["mean"],
            0.0,
        )
        self.assertGreater(
            availability_stale["capability-power-two"]["metrics"]["failed_unreachable"]["mean"],
            0.0,
        )
        self.assertGreater(
            load_stale["capability-power-two"]["metrics"]["p95_response_ticks"]["mean"],
            fresh["capability-power-two"]["metrics"]["p95_response_ticks"]["mean"],
        )
        self.assertGreater(
            fresh["global-least-loaded"]["coordination_cost"]["metadata_probe_operations"]["mean"],
            10
            * fresh["capability-power-two"]["coordination_cost"]["metadata_probe_operations"]["mean"],
        )

        low_load = cells[("offered_load", "0.25")]["aggregate"]
        high_load = cells[("offered_load", "1.25")]["aggregate"]
        self.assertGreater(
            high_load["capability-power-two"]["metrics"]["p95_response_ticks"]["mean"],
            low_load["capability-power-two"]["metrics"]["p95_response_ticks"]["mean"],
        )


if __name__ == "__main__":
    unittest.main()
