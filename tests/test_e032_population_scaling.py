"""Tests for E032: returns to population size at a matched evaluation budget."""

from __future__ import annotations

import json
import os
import random
import unittest
from statistics import mean

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e032_population_scaling as e032

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")


class CellContractTest(unittest.TestCase):
    def test_a_cell_must_hold_the_published_post_change_horizon(self):
        with self.assertRaises(ValueError):
            e032.Cell(agents=16, generations=50, change_at=10, bins=8)

    def test_a_cell_with_the_right_horizon_is_accepted(self):
        cell = e032.Cell(agents=16, generations=50, change_at=25, bins=8)
        self.assertEqual(cell.generations - cell.change_at, e032.POST_CHANGE_HORIZON)

    def test_change_at_must_leave_a_pre_change_phase(self):
        with self.assertRaises(ValueError):
            e032.Cell(agents=16, generations=25, change_at=0, bins=8)

    def test_the_catastrophe_threshold_is_the_published_absolute_number(self):
        # E024, E027, E028, E030 and E031 all publish catastrophe as 0.64 of a
        # 25-generation horizon. Holding the horizon fixed is what keeps this
        # experiment's counts comparable with theirs.
        self.assertEqual(e032.POST_CHANGE_HORIZON, 25)
        self.assertAlmostEqual(e032.CATASTROPHE_THRESHOLD, 16.0)
        self.assertAlmostEqual(
            e032.CATASTROPHE_THRESHOLD,
            mbe.CATASTROPHE_FRACTION * e032.POST_CHANGE_HORIZON,
        )


class MatchedCellTest(unittest.TestCase):
    def test_every_matched_cell_spends_exactly_the_same_budget(self):
        cells = e032.matched_cells()
        budgets = {cell.evaluation_budget for cell in cells}
        self.assertEqual(
            budgets,
            {e032.DEFAULT_MATCHED_BUDGET},
            "the matched mode exists to remove the budget confound",
        )

    def test_every_matched_cell_holds_the_horizon(self):
        for cell in e032.matched_cells():
            self.assertEqual(
                cell.generations - cell.change_at, e032.POST_CHANGE_HORIZON
            )

    def test_more_agents_buys_fewer_pre_change_generations(self):
        cells = e032.matched_cells()
        agents = [cell.agents for cell in cells]
        pre_change = [cell.pre_change_generations for cell in cells]
        self.assertEqual(agents, sorted(agents))
        self.assertEqual(pre_change, sorted(pre_change, reverse=True))

    def test_a_budget_that_does_not_divide_is_refused(self):
        with self.assertRaises(ValueError):
            e032.matched_cells(budget=1000, agents=(16, 32, 64))

    def test_a_budget_too_small_to_leave_a_pre_change_phase_is_refused(self):
        with self.assertRaises(ValueError):
            e032.matched_cells(budget=6400, agents=(256,))

    def test_the_default_budget_is_the_largest_unmatched_cell(self):
        # Chosen so the matched sweep runs at the most generous budget the
        # unmatched sweep ever reaches, not at one that flatters the result.
        largest = max(
            cell.evaluation_budget for cell in e032.unmatched_cells()
        )
        self.assertEqual(largest, e032.DEFAULT_MATCHED_BUDGET)


class UnmatchedCellTest(unittest.TestCase):
    def test_the_unmatched_budget_grows_with_the_population(self):
        cells = e032.unmatched_cells()
        budgets = [cell.evaluation_budget for cell in cells]
        self.assertEqual(len(set(budgets)), len(budgets))
        self.assertEqual(budgets, sorted(budgets))

    def test_the_unmatched_sweep_also_holds_the_horizon(self):
        for cell in e032.unmatched_cells():
            self.assertEqual(
                cell.generations - cell.change_at, e032.POST_CHANGE_HORIZON
            )

    def test_capacity_cells_vary_only_the_archive_resolution(self):
        cells = e032.capacity_cells()
        self.assertEqual(len({c.agents for c in cells}), 1)
        self.assertEqual(len({c.generations for c in cells}), 1)
        self.assertEqual(
            [c.archive_capacity for c in cells], [b * b for b in e032.DEFAULT_BIN_GRID]
        )

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            e032.cells_for_mode("whatever")


class DriverEquivalenceTest(unittest.TestCase):
    """E032 walks run_seed itself; it must not perturb what a seed does."""

    @classmethod
    def setUpClass(cls):
        cls.cell = e032.Cell(agents=50, generations=50, change_at=25, bins=8)
        cls.row = e032.run_cell(cls.cell, seeds=8, seed_start=0)
        cls.reference = mbe.sweep(
            seeds=8,
            seed_start=0,
            agents=50,
            generations=50,
            change_at=25,
            bins=8,
            verification=sim.VerificationConfig(),
        )

    def test_every_arm_matches_the_published_pipeline_exactly(self):
        for strategy in mbe.STRATEGIES:
            with self.subTest(strategy=strategy):
                self.assertAlmostEqual(
                    self.row["summary"][strategy]["mean"],
                    self.reference["aggregate"][strategy]["post_change_utility_auc"][
                        "mean"
                    ],
                    places=5,
                    msg="E032 must reproduce mbe.sweep on the same seeds",
                )

    def test_the_per_seed_values_are_kept_for_every_arm(self):
        for strategy in mbe.STRATEGIES:
            values = self.row["per_seed_post_change_utility_auc"][strategy]
            self.assertEqual(len(values), 8)
            self.assertAlmostEqual(
                mean(values), self.row["summary"][strategy]["mean"], places=5
            )

    def test_the_cell_is_the_published_e024_shape(self):
        # mbe.sweep withholds catastrophic_seeds on a perfect panel to keep its
        # frozen artifact schema; this is the reason E032 has its own driver.
        self.assertNotIn("catastrophic_seeds", self.reference)
        self.assertIn("catastrophic_seeds", self.row["summary"]["qd"])

    def test_running_the_same_cell_twice_gives_the_same_numbers(self):
        again = e032.run_cell(self.cell, seeds=8, seed_start=0)
        self.assertEqual(
            again["per_seed_post_change_utility_auc"],
            self.row["per_seed_post_change_utility_auc"],
        )

    def test_a_single_seed_is_refused(self):
        with self.assertRaises(ValueError):
            e032.run_cell(self.cell, seeds=1)


class CapacityIsolationTest(unittest.TestCase):
    """Only the archive arm may see the archive resolution.

    ``bins`` is drawn from the same per-seed streams every arm uses, so a change
    to it that leaked into the shared randomness would move ``random`` or
    ``majority`` too, and the capacity result would be measuring the leak
    instead of the grid.  Every non-archive arm must therefore be bit-identical
    across the whole capacity sweep.
    """

    @classmethod
    def setUpClass(cls):
        cls.report = e032.sweep(
            "capacity", seeds=6, agents=32, generations=50, bin_grid=(4, 8, 16)
        )

    def test_only_the_archive_arm_moves_with_the_archive_resolution(self):
        for strategy in mbe.STRATEGIES:
            values = [
                cell["per_seed_post_change_utility_auc"][strategy]
                for cell in self.report["cells"]
            ]
            with self.subTest(strategy=strategy):
                if strategy == "qd":
                    self.assertNotEqual(
                        values[0], values[-1], "qd must respond to its own grid"
                    )
                else:
                    self.assertEqual(
                        values[0],
                        values[-1],
                        f"{strategy} does not use the archive and must not move",
                    )

    def test_the_capacity_sweep_holds_the_budget_constant(self):
        self.assertTrue(
            self.report["configuration"]["evaluation_budget_is_constant"]
        )

    def test_the_swept_axis_is_named_in_the_report(self):
        self.assertEqual(self.report["configuration"]["swept_axis"], "bins")
        matched = e032.sweep("matched", seeds=2, budget=3200, agents=(32, 64))
        self.assertEqual(matched["configuration"]["swept_axis"], "agents")


class McNemarTest(unittest.TestCase):
    def test_no_discordant_pairs_is_no_evidence_of_change(self):
        self.assertEqual(e032._mcnemar_exact(0, 0), 1.0)

    def test_a_symmetric_split_is_no_evidence_of_change(self):
        self.assertAlmostEqual(e032._mcnemar_exact(10, 10), 1.0)

    def test_an_entirely_one_sided_split_is_the_binomial_tail(self):
        # 8 discordant pairs all in one direction: 2 * (1/2)**8.
        self.assertAlmostEqual(e032._mcnemar_exact(8, 0), 2 * 0.5**8)

    def test_six_versus_zero_is_the_smallest_significant_one_sided_split(self):
        # 2 * (1/2)**5 is 0.0625, so five discordant pairs all pointing the same
        # way still is not enough. This is why the catastrophe test needs seeds.
        self.assertGreater(e032._mcnemar_exact(5, 0), 0.05)
        self.assertLess(e032._mcnemar_exact(6, 0), 0.05)

    def test_the_test_is_symmetric_in_its_arguments(self):
        self.assertEqual(e032._mcnemar_exact(3, 9), e032._mcnemar_exact(9, 3))


class PairedStepTest(unittest.TestCase):
    def test_a_clear_improvement_is_called_a_gain(self):
        lower = [20.0 + 0.01 * i for i in range(40)]
        upper = [21.0 + 0.01 * i for i in range(40)]
        step = e032._paired_step(lower, upper)
        self.assertEqual(step["verdict"], "gain")
        self.assertAlmostEqual(step["mean_delta"], 1.0)

    def test_a_clear_decline_is_called_a_loss(self):
        lower = [21.0 + 0.01 * i for i in range(40)]
        upper = [20.0 + 0.01 * i for i in range(40)]
        self.assertEqual(e032._paired_step(lower, upper)["verdict"], "loss")

    def test_a_small_shift_under_wide_noise_is_not_called_either_way(self):
        # This is the case that matters: at 40 seeds the majority arm's spread
        # swallows a shift of this size, and reporting it as a decline would be
        # reporting noise.
        rng = random.Random(20320)
        lower = [rng.gauss(16.0, 4.0) for _ in range(40)]
        upper = [rng.gauss(15.6, 4.0) for _ in range(40)]
        step = e032._paired_step(lower, upper)
        self.assertEqual(step["verdict"], "indistinguishable")
        self.assertLess(step["ci95_low"], 0.0)
        self.assertGreater(step["ci95_high"], 0.0)

    def test_catastrophic_movement_is_counted_pairwise(self):
        lower = [10.0] * 6 + [20.0] * 6
        upper = [20.0] * 6 + [20.0] * 6
        step = e032._paired_step(lower, upper)
        self.assertEqual(step["catastrophic_only_in_lower"], 6)
        self.assertEqual(step["catastrophic_only_in_upper"], 0)
        self.assertEqual(step["catastrophic_delta"], -6)
        self.assertEqual(step["catastrophic_verdict"], "changed")

    def test_a_cell_with_the_same_catastrophe_count_but_different_seeds_is_discordant(self):
        # The count is unchanged, so an unpaired test would see nothing; the
        # paired test correctly reports that different seeds failed.
        lower = [10.0] * 5 + [20.0] * 5
        upper = [20.0] * 5 + [10.0] * 5
        step = e032._paired_step(lower, upper)
        self.assertEqual(step["catastrophic_delta"], 0)
        self.assertEqual(step["catastrophic_only_in_lower"], 5)
        self.assertEqual(step["catastrophic_only_in_upper"], 5)

    def test_mismatched_seed_counts_are_refused(self):
        with self.assertRaises(ValueError):
            e032._paired_step([1.0, 2.0], [1.0])


class ReturnsShapeTest(unittest.TestCase):
    def _steps(self, *specs):
        # Each spec is (verdict, delta) or (verdict, delta, half_width).
        out = []
        for spec in specs:
            verdict, delta = spec[0], spec[1]
            half = spec[2] if len(spec) > 2 else 0.0
            out.append({
                "verdict": verdict,
                "mean_delta": delta,
                "ci95_low": delta - half,
                "ci95_high": delta + half,
            })
        return out

    def test_all_indistinguishable_is_unresolved_not_saturated(self):
        # The distinction the record depends on: a design that cannot resolve a
        # step has not measured that the step is zero.
        steps = self._steps(
            ("indistinguishable", 0.1), ("indistinguishable", -0.2)
        )
        self.assertEqual(e032.classify_returns(steps), "unresolved")

    def test_any_resolved_decline_is_negative(self):
        steps = self._steps(("gain", 1.0), ("loss", -0.5))
        self.assertEqual(e032.classify_returns(steps), "negative")

    def test_gains_that_stop_resolving_are_saturated(self):
        steps = self._steps(("gain", 1.0), ("gain", 0.5), ("indistinguishable", 0.01))
        self.assertEqual(e032.classify_returns(steps), "saturated")

    def test_shrinking_gains_are_sublinear(self):
        steps = self._steps(("gain", 1.0), ("gain", 0.6), ("gain", 0.3))
        self.assertEqual(e032.classify_returns(steps), "sublinear")

    def test_growing_gains_are_superlinear(self):
        steps = self._steps(("gain", 0.3), ("gain", 0.6), ("gain", 1.0))
        self.assertEqual(e032.classify_returns(steps), "superlinear")

    def test_no_steps_at_all_is_unresolved(self):
        self.assertEqual(e032.classify_returns([]), "unresolved")


    def test_a_trend_smaller_than_its_own_intervals_is_near_linear(self):
        # +0.285 then +0.271, each with a half-width around 0.035: the fall is
        # a fifth of the noise it sits inside and must not be called a trend.
        steps = self._steps(("gain", 0.285, 0.032), ("gain", 0.271, 0.041))
        self.assertEqual(e032.classify_returns(steps), "near-linear")

    def test_a_trend_larger_than_its_intervals_is_still_called(self):
        steps = self._steps(("gain", 0.439, 0.125), ("gain", 0.064, 0.030))
        self.assertEqual(e032.classify_returns(steps), "sublinear")

    def test_the_committed_artifacts_agree_with_the_classifier(self):
        # Guards the tightening itself: if _half_width stopped being read, the
        # scalar arm would silently go back to being called sublinear.
        import json as _json

        with open(os.path.join(RESULTS, "E032-matched-budget.json"), encoding="utf-8") as fh:
            matched = _json.load(fh)
        for arm, shape in matched["returns_shape"].items():
            with self.subTest(arm=arm):
                self.assertEqual(
                    e032.classify_returns(matched["marginal_returns"][arm]), shape
                )

    def test_the_vocabulary_is_the_one_the_issue_asks_for(self):
        allowed = {
            "sublinear",
            "near-linear",
            "superlinear",
            "saturated",
            "negative",
            "unresolved",
        }
        cases = [
            self._steps(("gain", 1.0), ("gain", 0.3)),
            self._steps(("gain", 0.3), ("gain", 1.0)),
            self._steps(("gain", 1.0), ("indistinguishable", 0.0)),
            self._steps(("loss", -1.0)),
            self._steps(("indistinguishable", 0.0)),
            [],
        ]
        for steps in cases:
            self.assertIn(e032.classify_returns(steps), allowed)


class SweepShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = e032.sweep(
            "matched", seeds=4, budget=3200, agents=(32, 64), bins=8
        )

    def test_the_report_names_whether_the_budget_was_held_constant(self):
        self.assertTrue(self.report["configuration"]["evaluation_budget_is_constant"])
        self.assertEqual(self.report["configuration"]["evaluation_budgets"], [3200])

    def test_an_unmatched_report_admits_its_budget_moved(self):
        report = e032.sweep(
            "unmatched", seeds=4, generations=50, agents=(32, 64), bins=8
        )
        self.assertFalse(report["configuration"]["evaluation_budget_is_constant"])
        self.assertEqual(
            report["configuration"]["evaluation_budgets"], [1600, 3200]
        )

    def test_every_arm_gets_a_returns_shape(self):
        self.assertEqual(
            set(self.report["returns_shape"]), set(mbe.STRATEGIES)
        )

    def test_one_step_per_consecutive_pair_per_arm(self):
        for strategy in mbe.STRATEGIES:
            self.assertEqual(len(self.report["marginal_returns"][strategy]), 1)

    def test_the_unmatched_mode_states_its_own_confound_as_a_limitation(self):
        report = e032.sweep(
            "unmatched", seeds=4, generations=50, agents=(32, 64), bins=8
        )
        self.assertTrue(
            any("return to budget" in line for line in report["limitations"]),
            "the unmatched mode must not be quotable without its confound",
        )

    def test_the_matched_mode_states_the_population_versus_time_trade(self):
        self.assertTrue(
            any(
                "fewer pre-change generations" in line
                for line in self.report["limitations"]
            )
        )

    def test_the_perfect_panel_is_declared_a_limitation_in_every_mode(self):
        for mode in e032.MODES:
            with self.subTest(mode=mode):
                self.assertTrue(
                    any(
                        "verifier panel is perfect" in line
                        for line in e032._limitations(mode)
                    )
                )

    def test_the_supplied_goal_set_is_declared_a_limitation_in_every_mode(self):
        for mode in e032.MODES:
            with self.subTest(mode=mode):
                self.assertTrue(
                    any(
                        "supplied rather than discovered" in line
                        for line in e032._limitations(mode)
                    )
                )

    def test_agents_are_not_claimed_to_be_language_models(self):
        for mode in e032.MODES:
            with self.subTest(mode=mode):
                self.assertTrue(
                    any(
                        "not a count of language-model workers" in line
                        for line in e032._limitations(mode)
                    )
                )


class CliTest(unittest.TestCase):
    def test_the_default_mode_is_the_one_the_issue_asks_for(self):
        self.assertEqual(e032.parse_args([]).mode, "matched")

    def test_agents_is_repeatable(self):
        args = e032.parse_args(["--agents", "16", "--agents", "64"])
        self.assertEqual(args.agents, [16, 64])

    def test_an_unknown_mode_is_rejected_at_the_command_line(self):
        with self.assertRaises(SystemExit):
            e032.parse_args(["--mode", "nonsense"])

    def test_main_writes_valid_json_to_the_requested_path(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.json")
            e032.main(
                [
                    "--mode",
                    "matched",
                    "--seeds",
                    "2",
                    "--budget",
                    "3200",
                    "--agents",
                    "32",
                    "--agents",
                    "64",
                    "--output",
                    path,
                ]
            )
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        self.assertEqual(payload["experiment_id"], "E032")
        self.assertEqual(len(payload["cells"]), 2)


if __name__ == "__main__":
    unittest.main()


class CommittedResultTest(unittest.TestCase):
    """What the record claims, asserted against the artifacts it claims it from."""

    @classmethod
    def setUpClass(cls):
        def load(name):
            with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
                return json.load(handle)

        cls.matched = load("E032-matched-budget.json")
        cls.unmatched = load("E032-unmatched-budget.json")
        cls.capacity = load("E032-archive-capacity.json")
        cls.by_agents = {
            mode: {c["cell"]["agents"]: c for c in report["cells"]}
            for mode, report in (
                ("matched", cls.matched), ("unmatched", cls.unmatched)
            )
        }

    def test_every_artifact_used_the_published_seed_count(self):
        for report in (self.matched, self.unmatched, self.capacity):
            self.assertEqual(report["configuration"]["seeds"], 100)

    def test_the_matched_artifact_really_held_the_budget(self):
        self.assertTrue(self.matched["configuration"]["evaluation_budget_is_constant"])
        self.assertEqual(self.matched["configuration"]["evaluation_budgets"], [12800])

    def test_the_unmatched_artifact_really_did_not(self):
        self.assertFalse(
            self.unmatched["configuration"]["evaluation_budget_is_constant"]
        )

    def test_the_two_sweeps_share_one_cell_and_it_reproduces_exactly(self):
        # N=256 is the matched budget and the largest unmatched cell, so the two
        # sweeps overlap in exactly one place. If the driver were sensitive to
        # anything but (agents, generations, change_at, bins), this would drift.
        matched = self.by_agents["matched"][256]
        unmatched = self.by_agents["unmatched"][256]
        self.assertEqual(matched["cell"], unmatched["cell"])
        self.assertEqual(
            matched["per_seed_post_change_utility_auc"],
            unmatched["per_seed_post_change_utility_auc"],
        )

    def test_the_archive_gains_nothing_from_population_at_a_fixed_budget(self):
        # Result 2's headline. Stated as a bound rather than as five numbers so
        # it survives a rerun on another libm.
        means = [c["summary"]["qd"]["mean"] for c in self.matched["cells"]]
        self.assertLess(
            max(means) - min(means),
            0.05,
            "qd moved measurably with population at a fixed budget",
        )
        for step in self.matched["marginal_returns"]["qd"]:
            self.assertEqual(step["verdict"], "indistinguishable")

    def test_the_archive_appears_to_gain_when_the_budget_is_allowed_to_move(self):
        # The same arm, the same seeds, the opposite conclusion. This pair is
        # the reason the record refuses to quote an unmatched sweep alone.
        verdicts = [s["verdict"] for s in self.unmatched["marginal_returns"]["qd"]]
        self.assertEqual(verdicts, ["gain"] * 4)
        self.assertEqual(self.unmatched["returns_shape"]["qd"], "sublinear")
        self.assertEqual(self.matched["returns_shape"]["qd"], "unresolved")

    def test_the_scalar_arm_gains_from_population_all_the_way_up(self):
        for step in self.matched["marginal_returns"]["scalar"]:
            self.assertEqual(step["verdict"], "gain")
        self.assertEqual(self.matched["returns_shape"]["scalar"], "near-linear")

    def test_population_takes_the_scalar_arm_from_every_seed_failing_to_none(self):
        counts = [
            self.by_agents["matched"][n]["summary"]["scalar"]["catastrophic_seeds"]
            for n in (16, 32, 64, 128, 256)
        ]
        self.assertEqual(counts[0], 100)
        self.assertEqual(counts[-1], 0)
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_no_arm_shows_a_resolved_negative_return_to_population(self):
        # Hypothesis 1 predicts one. Neither sweep produces one.
        for report in (self.matched, self.unmatched):
            for arm, steps in report["marginal_returns"].items():
                for step in steps:
                    with self.subTest(mode=report["mode"], arm=arm):
                        self.assertNotEqual(step["verdict"], "loss")

    def test_the_only_resolved_negative_return_is_on_the_archive_axis(self):
        verdicts = [s["verdict"] for s in self.capacity["marginal_returns"]["qd"]]
        self.assertEqual(verdicts, ["gain", "loss", "loss"])
        self.assertEqual(self.capacity["returns_shape"]["qd"], "negative")

    def test_the_published_bin_count_is_the_measured_optimum(self):
        means = {
            c["cell"]["bins"]: c["summary"]["qd"]["mean"]
            for c in self.capacity["cells"]
        }
        self.assertEqual(max(means, key=means.get), 8, "bins=8 is not a convention")

    def test_the_archive_is_never_catastrophic_at_any_capacity_or_population(self):
        for report in (self.matched, self.unmatched, self.capacity):
            for cell in report["cells"]:
                with self.subTest(mode=report["mode"], cell=cell["cell"]):
                    self.assertEqual(cell["summary"]["qd"]["catastrophic_seeds"], 0)

    def test_the_consensus_swarm_is_the_one_arm_population_does_not_stabilise(self):
        # Result 4. Every other arm's per-seed spread shrinks with N; majority's
        # does not, which is why its mean is the wrong statistic for it.
        for arm in ("random", "scalar", "qd", "planner"):
            spreads = [
                self.by_agents["unmatched"][n]["summary"][arm]["stdev"]
                for n in (16, 256)
            ]
            with self.subTest(arm=arm):
                self.assertLess(spreads[1], spreads[0] / 2.0)
        majority = [
            self.by_agents["unmatched"][n]["summary"]["majority"]["stdev"]
            for n in (16, 256)
        ]
        self.assertGreater(majority[1], majority[0])

    def test_no_step_of_the_consensus_swarm_resolves_in_either_sweep(self):
        # The claim withdrawn from the preliminary 40-seed grid. It must not
        # creep back in as a trend read off the point estimates.
        for report in (self.matched, self.unmatched):
            for step in report["marginal_returns"]["majority"]:
                with self.subTest(mode=report["mode"]):
                    self.assertEqual(step["verdict"], "indistinguishable")
                    self.assertGreater(step["catastrophic_mcnemar_p"], 0.05)

    def test_the_record_states_the_perfect_panel_and_supplied_goal_caveats(self):
        path = os.path.join(REPO_ROOT, "experiments", "E032-population-scaling.md")
        with open(path, encoding="utf-8") as handle:
            record = handle.read()
        for phrase in (
            "verifier panel is **perfect**",
            "supplied rather than discovered",
            "not a\n  count of language-model workers",
            "closes no issue",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, record)
