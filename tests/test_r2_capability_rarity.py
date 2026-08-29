import unittest

from randomness_lab.r2 import R2_POLICIES
from randomness_lab.r2_capability_rarity import (
    R2CapabilityRarityConfig,
    run_r2_capability_rarity_sweep,
)


class R2CapabilityRarityTests(unittest.TestCase):
    def small_config(self) -> R2CapabilityRarityConfig:
        return R2CapabilityRarityConfig(
            worker_count=100,
            capability_fractions=(0.50, 0.10, 0.01),
            trace_seeds=(7, 8),
            ticks=20,
            arrivals_per_tick=1,
            drain_ticks=80,
        )

    def test_sweep_is_deterministic_and_matched(self):
        first = run_r2_capability_rarity_sweep(self.small_config())
        second = run_r2_capability_rarity_sweep(self.small_config())
        self.assertEqual(first, second)
        self.assertEqual(first["cell_count"], 3)

        base_by_seed = {}
        capable_by_fraction = {}
        for cell in first["cells"]:
            capable_by_fraction[cell["requested_capability_fraction"]] = set(
                cell["raw_runs"][0]["capable_worker_ids"]
            )
            for run in cell["raw_runs"]:
                base_by_seed.setdefault(run["trace_seed"], run["base_trace_digest"])
                self.assertEqual(base_by_seed[run["trace_seed"]], run["base_trace_digest"])
                policy_digests = {
                    result["trace_digest"] for result in run["policies"].values()
                }
                self.assertEqual(policy_digests, {run["projected_trace_digest"]})

        self.assertGreaterEqual(capable_by_fraction[0.50], capable_by_fraction[0.10])
        self.assertGreaterEqual(capable_by_fraction[0.10], capable_by_fraction[0.01])

    def test_factor_controls_and_exact_worker_counts(self):
        result = run_r2_capability_rarity_sweep(self.small_config())
        self.assertEqual(
            result["controls"],
            {
                "churn_fraction": 0.0,
                "availability_observation_lag": 0,
                "load_observation_lag": 0,
                "burst_probability": 0.0,
                "work_units_per_task": 1,
                "matched_base_trace_across_fractions": True,
                "nested_capable_worker_sets": True,
            },
        )
        self.assertEqual(
            [cell["capable_worker_count"] for cell in result["cells"]],
            [50, 10, 1],
        )
        for cell in result["cells"]:
            self.assertEqual(set(cell["aggregate"]), set(R2_POLICIES))
            for run in cell["raw_runs"]:
                self.assertEqual(run["run_config"]["availability_observation_lag"], 0)
                self.assertEqual(run["run_config"]["load_observation_lag"], 0)

    def test_rare_capability_exposes_oblivious_routing_cost(self):
        result = run_r2_capability_rarity_sweep(self.small_config())
        common, rare = result["cells"][0], result["cells"][-1]
        common_failures = common["aggregate"]["one-random"]["metrics"][
            "failed_capability_mismatch"
        ]["mean"]
        rare_failures = rare["aggregate"]["one-random"]["metrics"][
            "failed_capability_mismatch"
        ]["mean"]
        self.assertGreater(rare_failures, common_failures)
        for cell in result["cells"]:
            aware = cell["aggregate"]["capability-power-two"]["metrics"]
            oracle = cell["aggregate"]["global-least-loaded"]["metrics"]
            self.assertEqual(aware["failed_capability_mismatch"]["mean"], 0.0)
            self.assertEqual(oracle["failed_capability_mismatch"]["mean"], 0.0)

    def test_invalid_configuration_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "in \\(0, 1\\]"):
            R2CapabilityRarityConfig(capability_fractions=(0.0,))
        with self.assertRaisesRegex(ValueError, "unique"):
            R2CapabilityRarityConfig(capability_fractions=(0.1, 0.1))
        with self.assertRaisesRegex(ValueError, "baseline capability"):
            R2CapabilityRarityConfig(rare_capability="gpu")


if __name__ == "__main__":
    unittest.main()
