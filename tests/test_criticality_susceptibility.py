import unittest

from experiments.criticality_susceptibility import (
    QueueConfig,
    benchmark,
    paired_trial,
    simulate,
)


class CriticalitySusceptibilityTests(unittest.TestCase):
    def setUp(self):
        self.config = QueueConfig(steps=100, probe_start=30, probe_steps=20)

    def test_paired_trial_is_exactly_reproducible(self):
        kwargs = {"seed": 11, "base_load": 0.38, "config": self.config}
        self.assertEqual(paired_trial(**kwargs), paired_trial(**kwargs))

    def test_variants_share_latent_workload_and_unperturbed_phases(self):
        trial = paired_trial(seed=3, base_load=0.38, config=self.config)
        control = trial["control"]
        pulse = trial["pulse"]
        stress = trial["stress"]

        self.assertEqual(
            {run["latent_workload_sha256"] for run in (control, pulse, stress)},
            {control["latent_workload_sha256"]},
        )
        self.assertEqual(
            control["arrivals_by_phase"]["pre_probe"],
            pulse["arrivals_by_phase"]["pre_probe"],
        )
        self.assertEqual(
            control["arrivals_by_phase"]["post_probe"],
            pulse["arrivals_by_phase"]["post_probe"],
        )
        self.assertGreaterEqual(
            pulse["arrivals_by_phase"]["probe"],
            control["arrivals_by_phase"]["probe"],
        )

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            simulate(seed=-1, base_load=0.3, mode="control", config=self.config)
        with self.assertRaises(ValueError):
            simulate(seed=1, base_load=0.3, mode="unknown", config=self.config)
        with self.assertRaises(ValueError):
            benchmark(seeds=1, loads=[0.3], config=self.config)

    def test_benchmark_retains_raw_trials_and_uncertainty(self):
        result = benchmark(
            seeds=4,
            loads=[0.34, 0.40],
            config=self.config,
        )
        self.assertEqual(len(result["cells"]), 2)
        for cell in result["cells"]:
            self.assertEqual(len(cell["trials"]), 4)
            backlog = cell["susceptibility"]["mean_total_backlog"]
            self.assertEqual(backlog["n"], 4)
            self.assertIn("ci95_low", backlog)
            self.assertIn("ci95_high", backlog)
            self.assertIn("signals", cell)

    def test_summary_only_omits_raw_trials(self):
        result = benchmark(
            seeds=3,
            loads=[0.35],
            config=self.config,
            include_trials=False,
        )
        self.assertNotIn("trials", result["cells"][0])

    def test_probe_has_no_acceptance_or_integration_authority(self):
        trial = paired_trial(seed=5, base_load=0.39, config=self.config)
        for mode in ("control", "pulse", "stress"):
            self.assertEqual(trial[mode]["integration_authority"], "none")
            self.assertNotIn("accepted_candidates", trial[mode])
        result = benchmark(
            seeds=2,
            loads=[0.39],
            config=self.config,
            include_trials=False,
        )
        self.assertEqual(result["integration_authority"], "none")


if __name__ == "__main__":
    unittest.main()
