import unittest

from randomness_lab.r1_sweep import R1SweepConfig, run_r1_sweep


class R1SweepTests(unittest.TestCase):
    def test_sweep_is_reproducible_and_retains_raw_trial_pairs(self) -> None:
        config = R1SweepConfig(
            tasks_per_trial=30,
            trials=3,
            base_seed=19,
            worker_correlations=(0.0, 1.0),
            verifier_correlations=(0.5,),
            quality_penalties=(0.0,),
            swarm_sizes=(2,),
        )
        first = run_r1_sweep(config)
        second = run_r1_sweep(config)
        self.assertEqual(first, second)
        self.assertEqual(first["cell_count"], 2)
        for cell in first["cells"]:
            self.assertEqual(len(cell["raw_trial_pairs"]), 3)
            self.assertIn(
                cell["success_delta"]["classification"],
                {"helps", "hurts", "uncertain"},
            )

    def test_sweep_reports_an_obvious_quality_penalty_as_harmful(self) -> None:
        result = run_r1_sweep(
            R1SweepConfig(
                tasks_per_trial=250,
                trials=6,
                base_seed=101,
                base_worker_success_probability=0.85,
                worker_correlations=(1.0,),
                verifier_correlations=(0.0,),
                quality_penalties=(0.65,),
                swarm_sizes=(3,),
            )
        )
        cell = result["cells"][0]
        self.assertLess(cell["success_delta"]["mean_delta"], 0.0)
        self.assertEqual(cell["success_delta"]["classification"], "hurts")
        self.assertEqual(
            result["classification_counts"]["verified_success"]["hurts"], 1
        )


if __name__ == "__main__":
    unittest.main()
