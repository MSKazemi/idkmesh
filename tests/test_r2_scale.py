import unittest

from randomness_lab.r2 import R2_POLICIES
from randomness_lab.r2_scale import R2ScaleConfig, run_r2_scale_sweep


class R2ScaleSweepTests(unittest.TestCase):
    def test_scale_sweep_is_reproducible_and_retains_raw_runs(self):
        config = R2ScaleConfig(
            worker_counts=(1, 10),
            trace_seeds=(5, 6),
            regimes=("fresh", "moderate"),
            ticks=6,
            arrival_divisor=10,
            max_arrivals_per_tick=2,
            max_work_units=3,
            drain_ticks=20,
            oracle_max_workers=10,
        )
        first = run_r2_scale_sweep(config)
        second = run_r2_scale_sweep(config)
        self.assertEqual(first, second)
        self.assertEqual(first["cell_count"], 4)

        for cell in first["cells"]:
            self.assertEqual(len(cell["raw_runs"]), 2)
            for raw_run in cell["raw_runs"]:
                digests = {
                    result["trace_digest"]
                    for result in raw_run["policies"].values()
                    if result["status"] == "ok"
                }
                self.assertEqual(len(digests), 1)
            self.assertEqual(set(cell["aggregate"]), set(R2_POLICIES))

    def test_oracle_is_explicitly_skipped_above_threshold(self):
        report = run_r2_scale_sweep(
            R2ScaleConfig(
                worker_counts=(20,),
                trace_seeds=(7,),
                regimes=("fresh",),
                ticks=4,
                arrival_divisor=20,
                max_arrivals_per_tick=1,
                max_work_units=2,
                drain_ticks=10,
                oracle_max_workers=10,
            )
        )
        cell = report["cells"][0]
        raw = cell["raw_runs"][0]
        self.assertEqual(raw["policies"]["global-least-loaded"]["status"], "skipped")
        self.assertIn("exceeds oracle_max_workers", raw["policies"]["global-least-loaded"]["reason"])
        self.assertEqual(cell["aggregate"]["global-least-loaded"]["status"], "skipped")
        for policy in (
            "one-random",
            "power-two",
            "power-three",
            "capability-power-two",
        ):
            self.assertEqual(raw["policies"][policy]["status"], "ok")

    def test_scale_cell_reports_oracle_loss_flags_when_oracle_runs(self):
        report = run_r2_scale_sweep(
            R2ScaleConfig(
                worker_counts=(10,),
                trace_seeds=(11,),
                regimes=("stale",),
                ticks=5,
                arrival_divisor=10,
                max_arrivals_per_tick=2,
                max_work_units=3,
                drain_ticks=20,
                oracle_max_workers=10,
            )
        )
        raw = report["cells"][0]["raw_runs"][0]
        self.assertEqual(raw["policies"]["global-least-loaded"]["status"], "ok")
        for policy in (
            "one-random",
            "power-two",
            "power-three",
            "capability-power-two",
        ):
            comparison = raw["oracle_comparisons"][policy]
            self.assertIn("loses_badly", comparison)
            self.assertIn("local_to_oracle_metadata_probe_ratio", comparison)


if __name__ == "__main__":
    unittest.main()
