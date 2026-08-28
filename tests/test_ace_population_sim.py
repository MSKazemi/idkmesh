import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "ace_population_sim.py"
SPEC = importlib.util.spec_from_file_location("ace_population_sim", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class AceLivePopulationExperimentTests(unittest.TestCase):
    def test_live_open_work_formula_matches_canonical_weights(self):
        state = MODULE.OpenWorkState(
            ready_prs=4,
            draft_prs=2,
            open_growth_seeds=3,
            other_open_issues=50,
        )
        self.assertEqual(MODULE.live_review_load(state), 8.0)

    def test_other_issue_pressure_is_capped_at_twenty(self):
        at_cap = MODULE.OpenWorkState(other_open_issues=20)
        above_cap = MODULE.OpenWorkState(other_open_issues=200)
        self.assertEqual(
            MODULE.live_review_load(at_cap), MODULE.live_review_load(above_cap)
        )

    def test_closing_open_work_recovers_capacity(self):
        high = MODULE.OpenWorkState(
            ready_prs=12,
            draft_prs=4,
            open_growth_seeds=4,
            other_open_issues=50,
        )
        low = MODULE.OpenWorkState(
            ready_prs=2,
            draft_prs=1,
            open_growth_seeds=1,
            other_open_issues=10,
        )
        high_load = MODULE.live_review_load(high)
        low_load = MODULE.live_review_load(low)
        self.assertLess(low_load, high_load)
        self.assertGreater(
            MODULE.capacity(low_load, 8.0, 2.0),
            MODULE.capacity(high_load, 8.0, 2.0),
        )

    def test_historical_event_volume_is_not_state(self):
        state = MODULE.OpenWorkState(
            ready_prs=3,
            draft_prs=2,
            open_growth_seeds=2,
            other_open_issues=7,
        )
        first = MODULE.live_review_load(state)
        for _historical_event_count in (0, 10, 10_000, 1_000_000):
            self.assertEqual(MODULE.live_review_load(state), first)

    def test_default_seed_is_deterministic(self):
        scenario = MODULE.SCENARIOS["overload"]
        first = MODULE.run_scenario(
            scenario, policy="governed", seed=20260828
        )[1]
        second = MODULE.run_scenario(
            scenario, policy="governed", seed=20260828
        )[1]
        self.assertEqual(MODULE.summary_dict(first), MODULE.summary_dict(second))

    def test_under_reproduction_exhausts_ace_work(self):
        summary = MODULE.run_scenario(
            MODULE.SCENARIOS["under-reproduction"],
            policy="governed",
            seed=20260828,
        )[1]
        active = (
            summary.final_open_work.ready_prs
            + summary.final_open_work.draft_prs
            + summary.final_open_work.open_growth_seeds
        )
        self.assertEqual(active, 0)

    def test_healthy_reproduction_stays_bounded(self):
        summary = MODULE.run_scenario(
            MODULE.SCENARIOS["healthy-reproduction"],
            policy="governed",
            seed=20260828,
        )[1]
        self.assertGreater(
            summary.total_spawned_seeds,
            MODULE.SCENARIOS["healthy-reproduction"].initial_seeds,
        )
        self.assertTrue(summary.stable_final_load)
        self.assertLess(summary.peak_review_load, 8.0)

    def test_overload_raw_activity_adds_pressure_not_verified_throughput(self):
        scenario = MODULE.SCENARIOS["overload"]
        governed = MODULE.run_scenario(
            scenario, policy="governed", seed=20260828
        )[1]
        raw = MODULE.run_scenario(scenario, policy="raw", seed=20260828)[1]
        comparison = MODULE.comparison(governed, raw)

        self.assertTrue(comparison["raw_activity_can_be_worse"])
        self.assertGreater(raw.total_public_activity, governed.total_public_activity)
        self.assertGreater(raw.final_review_load, governed.final_review_load)
        self.assertEqual(raw.total_reviewed_prs, governed.total_reviewed_prs)
        self.assertEqual(
            raw.total_verified_descendants,
            governed.total_verified_descendants,
        )
        self.assertTrue(governed.stable_final_load)
        self.assertFalse(raw.stable_final_load)

    def test_default_acceptance_contract(self):
        MODULE.run_acceptance_checks(20260828)

    def test_invalid_open_work_fails_closed(self):
        with self.assertRaises(ValueError):
            MODULE.live_review_load(MODULE.OpenWorkState(ready_prs=-1))


if __name__ == "__main__":
    unittest.main()
