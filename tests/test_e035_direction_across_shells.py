"""Tests for E035: which of E034's results survive at a second distance?

E034 measured one shell and recorded that as its first limitation. E035 repeats
the ladder at two more distances, so the tests here pin the two things that can
make a replication meaningless:

1. **the shells must differ only in distance.** If the seeds, the agent count,
   the generations, the pool, the change size or the cell width moved between
   runs, a trait "flipping sign" is a confounded comparison, not a finding.
   :meth:`ComparabilityTest.test_the_three_shells_differ_only_in_distance` reads
   every design key out of all three artifacts and refuses any drift.
2. **the verdicts must be reachable.** ``sign_flips`` is the verdict that
   qualifies E034, so :class:`ReplicationTest` proves all three verdicts are
   arithmetic on the changes rather than labels the write-up chose.

The committed numbers are then pinned against the write-up's tables, including
the ones that go against E034 -- the spread that does not grow and the ladder
that flips -- so a later edit cannot quietly restore the tidier story.
"""

from __future__ import annotations

import json
import math
import os
import re
import unittest

import sim.emergence_sim as sim
import sim.e034_goal_direction as e034
import sim.e035_direction_across_shells as e035

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E035-direction-across-shells.md")
E034_WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E034-goal-direction.md")

SHELL_FILES = {
    0.30: "E034-goal-direction.json",
    0.35: "E035-shell-0.350.json",
    0.375: "E035-shell-0.375.json",
}

#: Every key that must be identical across the three runs. Distance is the one
#: thing allowed to move, so it is deliberately absent.
DESIGN_KEYS = (
    "agents",
    "bins",
    "catastrophe_utility_auc_threshold",
    "descriptor_traits",
    "floor_traits",
    "generations",
    "goals_per_cell",
    "hypothesis_free_arms",
    "hypothesis_holding_arms",
    "metric",
    "minimum_reliability",
    "minimum_security",
    "panel",
    "seed_start",
    "seeds",
    "unconstrained_traits",
    "weight_targets",
    "weight_tolerance",
)


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _write_up():
    with open(WRITE_UP, encoding="utf-8") as handle:
        return handle.read()


class WelchTest(unittest.TestCase):
    """The statistic is arithmetic, not a lookup."""

    def test_identical_samples_produce_no_difference(self):
        result = e035.welch([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(result["change"], 0.0)
        self.assertEqual(result["t"], 0.0)
        self.assertFalse(result["resolved"])

    def test_a_shifted_sample_resolves_and_keeps_its_sign(self):
        low = [0.0, 0.1, -0.1, 0.05, -0.05]
        high = [10.0, 10.1, 9.9, 10.05, 9.95]
        rising = e035.welch(high, low)
        self.assertAlmostEqual(rising["change"], 10.0, places=6)
        self.assertGreater(rising["t"], e035.RESOLVED_T)
        self.assertTrue(rising["resolved"])
        falling = e035.welch(low, high)
        self.assertAlmostEqual(falling["change"], -10.0, places=6)
        self.assertTrue(falling["resolved"])
        self.assertAlmostEqual(rising["t"], -falling["t"], places=6)

    def test_a_wide_sample_does_not_resolve_a_real_difference(self):
        """Noise has to be able to hide an effect, or nothing is falsifiable."""
        low = [-9.0, 9.0, -8.0, 8.0, 0.0]
        high = [-8.0, 10.0, -7.0, 9.0, 1.0]
        result = e035.welch(high, low)
        self.assertAlmostEqual(result["change"], 1.0, places=6)
        self.assertFalse(result["resolved"])

    def test_the_bar_is_the_bonferroni_corrected_one(self):
        """0.05 over five preregistered ladders, at the smallest df seen."""
        self.assertAlmostEqual(e035.RESOLVED_T, 2.878, places=3)


class ContrastTest(unittest.TestCase):
    def test_a_contrast_pools_the_two_errors_in_quadrature(self):
        first = {"change": 3.0, "standard_error": 3.0}
        second = {"change": -1.0, "standard_error": 4.0}
        result = e035.contrast(first, second)
        self.assertAlmostEqual(result["contrast"], 4.0, places=6)
        self.assertAlmostEqual(result["standard_error"], 5.0, places=6)
        self.assertAlmostEqual(result["t"], 0.8, places=6)
        self.assertFalse(result["resolved"])

    def test_two_ladders_pointing_apart_can_resolve(self):
        first = {"change": 3.0, "standard_error": 0.3}
        second = {"change": -3.0, "standard_error": 0.4}
        self.assertTrue(e035.contrast(first, second)["resolved"])


class ReplicationTest(unittest.TestCase):
    """All three verdicts must be reachable, or the labels mean nothing."""

    @staticmethod
    def _changes(pairs):
        return [{"change": c, "resolved": r} for c, r in pairs]

    def test_same_sign_and_all_resolved_replicates(self):
        verdict = e035.replication(
            self._changes([(-2.0, True), (-3.0, True), (-2.5, True)])
        )
        self.assertEqual(verdict["verdict"], e035.REPLICATES)
        self.assertEqual(verdict["resolved_count"], 3)

    def test_same_sign_but_not_all_resolved_is_only_consistent(self):
        verdict = e035.replication(
            self._changes([(2.0, True), (1.0, False), (0.5, False)])
        )
        self.assertEqual(verdict["verdict"], e035.CONSISTENT)
        self.assertEqual(verdict["resolved_count"], 1)

    def test_an_opposite_sign_flips_even_when_it_is_the_unresolved_one(self):
        """A flip is about direction, so an unresolved flip still counts."""
        verdict = e035.replication(
            self._changes([(-2.0, True), (-1.0, False), (0.7, False)])
        )
        self.assertEqual(verdict["verdict"], e035.SIGN_FLIPS)

    def test_a_flip_outranks_full_resolution(self):
        verdict = e035.replication(
            self._changes([(2.0, True), (-2.0, True), (2.0, True)])
        )
        self.assertEqual(verdict["verdict"], e035.SIGN_FLIPS)


class WindowTest(unittest.TestCase):
    def test_the_window_is_the_span_of_the_feasible_rows(self):
        rows = [
            {"distance_to_supplied": 0.20, "feasible": False},
            {"distance_to_supplied": 0.28, "feasible": True},
            {"distance_to_supplied": 0.30, "feasible": True},
            {"distance_to_supplied": 0.40, "feasible": False},
        ]
        self.assertEqual(
            e035.window(rows), {"low": 0.28, "high": 0.30, "width": 0.02}
        )

    def test_no_feasible_row_is_reported_as_no_window(self):
        rows = [{"distance_to_supplied": 0.2, "feasible": False}]
        self.assertEqual(
            e035.window(rows), {"low": None, "high": None, "width": None}
        )


class ComparabilityTest(unittest.TestCase):
    """The comparison is only worth anything if the shells are siblings."""

    def setUp(self):
        self.reports = {d: _load(name) for d, name in SHELL_FILES.items()}

    def test_the_three_shells_differ_only_in_distance(self):
        reference = self.reports[0.30]
        for distance, report in self.reports.items():
            for key in DESIGN_KEYS:
                with self.subTest(distance=distance, key=key):
                    self.assertEqual(report[key], reference[key])
            for key in ("change_size", "pool_draws", "pool_seed", "tolerance"):
                with self.subTest(distance=distance, shell_key=key):
                    self.assertEqual(
                        report["shell"][key], reference["shell"][key]
                    )

    def test_each_shell_sits_at_the_distance_it_is_filed_under(self):
        for distance, report in self.reports.items():
            with self.subTest(distance=distance):
                self.assertAlmostEqual(
                    report["shell"]["distance_to_supplied"], distance, places=9
                )

    def test_every_goal_really_sits_on_its_own_shell(self):
        for distance, report in self.reports.items():
            tolerance = report["shell"]["tolerance"]
            change_size = report["shell"]["change_size"]
            for trait, block in report["traits"].items():
                for cell in block["cells"]:
                    for goal in cell["goal_results"]:
                        with self.subTest(distance=distance, trait=trait):
                            self.assertLessEqual(
                                abs(goal["distance_to_supplied"] - distance),
                                tolerance + 1e-9,
                            )
                            self.assertLessEqual(
                                abs(goal["distance_from_initial"] - change_size),
                                tolerance + 1e-9,
                            )

    def test_the_three_shells_measure_the_same_five_traits(self):
        reference = sorted(self.reports[0.30]["traits"])
        self.assertEqual(reference, sorted(sim.TRAITS))
        for distance, report in self.reports.items():
            with self.subTest(distance=distance):
                self.assertEqual(sorted(report["traits"]), reference)

    def test_shells_share_goals_only_where_their_tolerance_bands_intersect(self):
        """The shells are not fully independent, and the artifact says so."""
        overlap = _load("E035-direction-across-shells.json")["shell_overlap"]
        self.assertEqual(len(overlap), 3)
        for row in overlap:
            with self.subTest(pair=tuple(row["distances"])):
                if row["band_intersection"] == 0.0:
                    self.assertTrue(row["disjoint"])
                    self.assertEqual(row["shared_goals"], 0)
                else:
                    self.assertGreater(row["shared_goals"], 0)

    def test_the_only_overlap_is_small_enough_to_be_a_limitation_not_a_defect(self):
        overlap = _load("E035-direction-across-shells.json")["shell_overlap"]
        shared = [row for row in overlap if not row["disjoint"]]
        self.assertEqual(len(shared), 1)
        self.assertEqual(tuple(shared[0]["distances"]), (0.35, 0.375))
        self.assertLess(shared[0]["shared_share"], 0.05)

    def test_the_overlap_is_the_one_geometry_predicts(self):
        """band_intersection = 2*tolerance - separation, or zero."""
        overlap = _load("E035-direction-across-shells.json")["shell_overlap"]
        tolerance = self.reports[0.30]["shell"]["tolerance"]
        for row in overlap:
            with self.subTest(pair=tuple(row["distances"])):
                self.assertAlmostEqual(
                    row["band_intersection"],
                    max(2 * tolerance - row["separation"], 0.0),
                    places=9,
                )

    def test_the_shell_thins_out_as_it_moves_away(self):
        members = [self.reports[d]["shell"]["members"] for d in (0.30, 0.35, 0.375)]
        self.assertEqual(members, sorted(members, reverse=True))


class CommittedComparisonTest(unittest.TestCase):
    def setUp(self):
        self.report = _load("E035-direction-across-shells.json")
        self.shells = self.report["per_shell"]

    def test_the_committed_comparison_agrees_with_the_module(self):
        """Recompute the whole block from the three shells it summarises."""
        recomputed = e035.compare(
            {d: _load(name) for d, name in SHELL_FILES.items()}
        )
        self.assertEqual(recomputed, self.report)

    def test_the_compared_distances_are_the_ones_the_module_names(self):
        self.assertEqual(tuple(self.report["distances"]), e035.SHELLS)
        self.assertIn(e035.E034_SHELL, self.report["distances"])

    def test_the_spread_does_not_grow_with_distance(self):
        """E034 conjectured it would widen. It does not -- this is the answer."""
        spreads = [
            self.shells[str(d)]["direction_spread"]["spread"]
            for d in self.report["distances"]
        ]
        self.assertFalse(self.report["spread_grows_with_distance"])
        self.assertLess(max(spreads) - min(spreads), 0.1)
        for spread in spreads:
            with self.subTest(spread=spread):
                self.assertGreater(spread, 9.3)
                self.assertLess(spread, 9.5)

    def test_every_shell_still_dwarfs_e033s_whole_distance_sweep(self):
        """E034's headline claim -- direction beats distance -- is what holds."""
        for distance in self.report["distances"]:
            with self.subTest(distance=distance):
                self.assertGreater(
                    self.shells[str(distance)]["direction_spread"]["spread"],
                    2.0 * 3.309,
                )

    def test_the_archive_still_leads_on_average_at_every_shell(self):
        for distance in self.report["distances"]:
            spread = self.shells[str(distance)]["direction_spread"]
            with self.subTest(distance=distance):
                self.assertGreater(spread["lead_mean"], 0.0)
                self.assertGreater(spread["negative_share"], 0.15)
                self.assertLess(spread["negative_share"], 0.35)

    def test_efficiency_is_the_only_ladder_that_fully_replicates(self):
        replicating = {
            trait
            for trait, block in self.report["trait_replication"].items()
            if block["verdict"] == e035.REPLICATES
        }
        self.assertEqual(replicating, {"efficiency"})
        efficiency = self.report["trait_replication"]["efficiency"]
        self.assertTrue(all(change < 0 for change in efficiency["changes"]))

    def test_simplicity_is_the_ladder_that_flips(self):
        """E034 leaned on simplicity falling; across the window it does not."""
        flipping = {
            trait
            for trait, block in self.report["trait_replication"].items()
            if block["verdict"] == e035.SIGN_FLIPS
        }
        self.assertEqual(flipping, {"simplicity"})
        changes = self.report["trait_replication"]["simplicity"]["changes"]
        self.assertLess(changes[0], 0.0)
        self.assertGreater(changes[-1], 0.0)

    def test_the_flip_is_measured_across_shells_that_share_no_goals(self):
        """Otherwise the reversal could be two readings of one sample."""
        self.assertTrue(self.report["sign_flip_shells_are_disjoint"])
        endpoints = [
            row
            for row in self.report["shell_overlap"]
            if row["distances"] == [0.3, 0.375]
        ]
        self.assertEqual(len(endpoints), 1)
        self.assertTrue(endpoints[0]["disjoint"])

    def test_the_descriptor_cancellation_replicates_at_every_shell(self):
        """The category finding is the one that survives the window intact."""
        self.assertTrue(self.report["descriptor_cancellation_replicates"])
        for distance in self.report["distances"]:
            block = self.report["descriptor_contrast"][str(distance)]
            with self.subTest(distance=distance):
                self.assertTrue(block["resolved"])
                self.assertGreater(block["contrast"], 4.0)
                self.assertGreater(
                    self.shells[str(distance)]["ladders"]["adaptability"]["change"],
                    0.0,
                )
                self.assertLess(
                    self.shells[str(distance)]["ladders"]["efficiency"]["change"],
                    0.0,
                )

    def test_security_never_resolves_at_any_shell(self):
        """The floor hypothesis needs both floored traits to move. One never does."""
        for distance in self.report["distances"]:
            with self.subTest(distance=distance):
                self.assertFalse(
                    self.shells[str(distance)]["ladders"]["security"]["resolved"]
                )
        self.assertEqual(
            self.report["trait_replication"]["security"]["resolved_count"], 0
        )

    def test_the_floored_pair_contrast_never_resolves_either(self):
        """So E035 records the weaker asymmetry, not a proven difference."""
        for distance in self.report["distances"]:
            with self.subTest(distance=distance):
                self.assertFalse(
                    self.report["floored_contrast"][str(distance)]["resolved"]
                )

    def test_reliability_outruns_security_on_every_shell(self):
        self.assertTrue(self.report["floored_pair_asymmetry_replicates"])
        for distance in self.report["distances"]:
            ladders = self.shells[str(distance)]["ladders"]
            with self.subTest(distance=distance):
                self.assertGreater(
                    ladders["reliability"]["change"], ladders["security"]["change"]
                )

    def test_the_traits_are_the_arenas_own_traits(self):
        for distance in self.report["distances"]:
            with self.subTest(distance=distance):
                self.assertEqual(
                    set(self.shells[str(distance)]["ladders"]), set(sim.TRAITS)
                )


class FeasibilityWindowTest(unittest.TestCase):
    def setUp(self):
        self.report = _load("E035-feasibility-window.json")

    def test_the_window_is_bounded_on_both_sides(self):
        window = self.report["window"]
        self.assertIsNotNone(window["low"])
        self.assertIsNotNone(window["high"])
        self.assertGreater(window["width"], 0.0)

    def test_the_design_is_infeasible_near_the_supplied_set(self):
        """The ladder cannot be run close in -- this is a geometric limit."""
        close = [
            row
            for row in self.report["feasibility"]
            if row["distance_to_supplied"] < self.report["window"]["low"]
        ]
        self.assertTrue(close)
        for row in close:
            with self.subTest(distance=row["distance_to_supplied"]):
                self.assertFalse(row["feasible"])

    def test_both_edges_are_empty_cells_not_thin_ones(self):
        """Holding the change size empties extreme-weight cells at both ends."""
        window = self.report["window"]
        emptied = [
            row
            for row in self.report["feasibility"]
            if row["thinnest_cell_goals"] == 0
        ]
        self.assertTrue(emptied)
        for row in emptied:
            with self.subTest(distance=row["distance_to_supplied"]):
                self.assertFalse(row["feasible"])
                self.assertTrue(
                    row["distance_to_supplied"] < window["low"]
                    or row["distance_to_supplied"] > window["high"]
                )
        below = [r for r in emptied if r["distance_to_supplied"] < window["low"]]
        above = [r for r in emptied if r["distance_to_supplied"] > window["high"]]
        self.assertTrue(below, "the scan must reach past the lower edge")
        self.assertTrue(above, "the scan must reach past the upper edge")
        self.assertNotEqual(
            below[-1]["thinnest_cell_trait"], above[0]["thinnest_cell_trait"]
        )

    def test_the_feasible_span_is_contiguous(self):
        flags = [row["feasible"] for row in self.report["feasibility"]]
        runs = [flag for index, flag in enumerate(flags) if index == 0 or flag != flags[index - 1]]
        self.assertLessEqual(runs.count(True), 1)

    def test_every_compared_shell_sits_inside_the_measured_window(self):
        window = self.report["window"]
        for distance in e035.SHELLS:
            with self.subTest(distance=distance):
                self.assertGreaterEqual(distance, window["low"])
                self.assertLessEqual(distance, window["high"])

    def test_e034s_shell_sits_near_the_lower_edge(self):
        """Worth recording: E034 did not sample the middle of the window."""
        window = self.report["window"]
        midpoint = (window["low"] + window["high"]) / 2.0
        self.assertLess(e035.E034_SHELL, midpoint)

    def test_the_scan_holds_e034s_own_change_size(self):
        self.assertAlmostEqual(
            self.report["change_size"], e034.SHELL_CHANGE_SIZE, places=9
        )
        self.assertEqual(self.report["goals_per_cell"], e035.SHELL_GOALS_PER_CELL)

    def test_the_shells_were_run_at_the_goals_per_cell_the_scan_requires(self):
        for name in SHELL_FILES.values():
            with self.subTest(artifact=name):
                self.assertEqual(
                    _load(name)["goals_per_cell"], e035.SHELL_GOALS_PER_CELL
                )


class WriteUpTest(unittest.TestCase):
    """The prose has to match the artifact, including where it costs E034."""

    def setUp(self):
        self.text = _write_up()
        self.report = _load("E035-direction-across-shells.json")

    def _rows(self, header_fragment):
        rows = {}
        for line in self.text.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            rows.setdefault(cells[0], []).append(cells)
        return rows

    def test_the_spread_table_matches_the_artifact(self):
        rows = self._rows("spread")
        for distance in self.report["distances"]:
            spread = self.report["per_shell"][str(distance)]["direction_spread"]
            key = f"{distance:.3f}"
            with self.subTest(distance=distance):
                self.assertIn(key, rows)
                self.assertTrue(
                    any(
                        f"{spread['spread']:.3f}" in cells
                        and str(spread["goals"]) in cells
                        for cells in rows[key]
                    ),
                    f"no row for {key} carries both the spread and the goal count",
                )

    def test_every_ladder_change_appears_in_the_prose(self):
        for distance in self.report["distances"]:
            ladders = self.report["per_shell"][str(distance)]["ladders"]
            for trait, block in ladders.items():
                with self.subTest(distance=distance, trait=trait):
                    self.assertIn(f"{block['change']:+.3f}", self.text)

    def test_the_write_up_names_every_verdict_it_measured(self):
        for trait, block in self.report["trait_replication"].items():
            with self.subTest(trait=trait):
                self.assertRegex(
                    self.text, rf"`{trait}`[^\n]*`{block['verdict']}`|`{block['verdict']}`[^\n]*`{trait}`"
                )

    def test_the_write_up_states_the_conjecture_was_not_supported(self):
        """E034 predicted a widening spread. Burying that would be the failure."""
        self.assertRegex(self.text, r"(?i)does not (?:grow|widen)")
        self.assertIn("9.365", self.text)
        self.assertIn("9.409", self.text)

    def test_the_write_up_qualifies_e034_rather_than_repeating_it(self):
        self.assertRegex(self.text, r"(?i)simplicity")
        self.assertRegex(self.text, r"(?i)sign")
        self.assertIn("E034", self.text)

    def test_the_write_up_carries_the_geometric_limit(self):
        window = _load("E035-feasibility-window.json")["window"]
        self.assertIn(f"{window['low']:.3f}", self.text)
        self.assertIn(f"{window['high']:.3f}", self.text)

    def test_the_write_up_has_a_reproduction_section(self):
        self.assertRegex(self.text, r"(?m)^## Reproduction")
        self.assertIn("sim/e035_direction_across_shells.py", self.text)

    def test_the_write_up_declares_its_limitations(self):
        self.assertRegex(self.text, r"(?m)^## Limitations")


class SupersededRecordTest(unittest.TestCase):
    """E034's own record must not keep asserting what E035 withdrew.

    A reader who finds E034 first and never reaches E035 would otherwise carry
    forward two claims this experiment removed from circulation.
    """

    def setUp(self):
        with open(E034_WRITE_UP, encoding="utf-8") as handle:
            self.text = handle.read()
        self.report = _load("E035-direction-across-shells.json")

    def test_e034_points_forward_to_this_experiment(self):
        self.assertIn("E035-direction-across-shells.md", self.text)

    def test_e034_marks_the_conjecture_that_did_not_hold(self):
        """It predicted a widening spread; the record must say it was answered."""
        self.assertRegex(self.text, r"(?i)widens with distance")
        self.assertRegex(self.text, r"(?i)Answered by E035")
        for distance in self.report["distances"]:
            spread = self.report["per_shell"][str(distance)]["direction_spread"]
            with self.subTest(distance=distance):
                self.assertIn(f"{spread['spread']:.3f}", self.text)

    def test_e034_warns_against_carrying_the_flipped_ladder_forward(self):
        flipping = [
            trait
            for trait, block in self.report["trait_replication"].items()
            if block["verdict"] == e035.SIGN_FLIPS
        ]
        self.assertTrue(flipping)
        for trait in flipping:
            with self.subTest(trait=trait):
                self.assertRegex(
                    self.text, rf"(?i)do not carry[^.]*`{trait}`"
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
