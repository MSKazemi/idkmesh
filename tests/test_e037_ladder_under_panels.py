"""Tests for E037: does E034's direction result survive an imperfect panel?

Everything E030 through E035 concluded was measured with verification that was
exact and free. E037 reruns E034's ladder on two of E027's panels and asks which
conclusions were about the goal geometry and which were about the perfect panel.

Three things can make that comparison say nothing, and each has a test:

1. **the runs must differ only in the panel.** :class:`ComparabilityTest` reads
   every design key out of all three artifacts and refuses any drift, and also
   refuses an artifact whose ``panel`` field disagrees with the name it was
   filed under -- a mislabelled file would otherwise compare a panel with
   itself.
2. **the pairing must be real.** The whole point of holding the shell still is
   that the three panels measure the *same goals*, which makes a paired test
   available. :class:`GoalAlignmentTest` proves the module checks that rather
   than assuming it.
3. **the yardstick must not move unnoticed.** ``lead_over_hypothesis_free`` is
   measured against the best hypothesis-free arm *for that goal*. If a panel
   changes which arm that is, a lead that grew may be a baseline that shrank.
   :class:`ReferenceArmTest` pins the counter that makes this visible.

:class:`PanelFactsTest` pins one detail that is easy to get wrong in exactly the
direction that flatters the record: ``e027.PANELS`` has a ``perfect`` entry, but
the sweep never uses it -- ``e033._panel("perfect")`` returns ``None`` and skips
the verifier draw. Reporting the config would describe a run that never
happened.
"""

from __future__ import annotations

import json
import math
import os
import re
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e033_goal_distance as e033
import sim.e034_goal_direction as e034
import sim.e035_direction_across_shells as e035
import sim.e037_ladder_under_panels as e037

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E037-ladder-under-panels.md")
E035_WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E035-direction-across-shells.md")

PANEL_FILES = {
    "perfect": "E034-goal-direction.json",
    "measured": "E037-panel-measured.json",
    "stress": "E037-panel-stress.json",
}
COMPARISON_FILE = "E037-ladder-under-panels.json"
LEAKAGE_FILE = "E037-panel-leakage.json"


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _reports():
    return {name: _load(path) for name, path in PANEL_FILES.items()}


# --------------------------------------------------------------------------
# Fixtures: an E034-shaped artifact small enough to reason about by hand.
# --------------------------------------------------------------------------

_FIXTURE_GOALS = {
    "adaptability": [(0.2, 0.4, 0.1, 0.2, 0.1), (0.2, 0.41, 0.1, 0.19, 0.1)],
    "efficiency": [(0.2, 0.1, 0.4, 0.2, 0.1), (0.2, 0.1, 0.41, 0.19, 0.1)],
    "reliability": [(0.4, 0.1, 0.2, 0.2, 0.1), (0.41, 0.1, 0.2, 0.19, 0.1)],
    "security": [(0.2, 0.1, 0.2, 0.1, 0.4), (0.2, 0.1, 0.2, 0.09, 0.41)],
    "simplicity": [(0.2, 0.1, 0.2, 0.4, 0.1), (0.2, 0.1, 0.2, 0.41, 0.09)],
}


def _goal_result(goal, lead, *, reference="random", catastrophes=0, qd_mean=20.0):
    return {
        "goal": list(goal),
        "distance_to_supplied": 0.3,
        "distance_from_initial": 0.39,
        "means": {arm: qd_mean for arm in mbe.STRATEGIES},
        "reference_arm": reference,
        "best_hypothesis_free_arm": round(qd_mean - lead, 6),
        "lead_over_hypothesis_free": {"qd": lead, "majority": lead - 1.0},
        "catastrophic_seeds": {arm: catastrophes for arm in mbe.STRATEGIES},
    }


def _report(panel, leads, *, reference="random", catastrophes=0, **overrides):
    """An E034-shaped artifact. ``leads`` maps trait -> (low cell, high cell)."""
    traits = {}
    for trait, (low, high) in leads.items():
        cells = []
        for target, values in ((0.02, low), (0.40, high)):
            goals = _FIXTURE_GOALS[trait]
            cells.append(
                {
                    "target_weight": target,
                    "mean_weight": target,
                    "goal_results": [
                        _goal_result(
                            tuple(round(w + target, 9) for w in goal),
                            value,
                            reference=reference,
                            catastrophes=catastrophes,
                        )
                        for goal, value in zip(goals, values)
                    ],
                }
            )
        traits[trait] = {"cells": cells}
    report = {
        "experiment_id": "E034",
        "experiment": "goal-direction-at-fixed-distance-v1",
        "panel": panel,
        "agents": 64,
        "bins": 8,
        "catastrophe_utility_auc_threshold": 16.0,
        "change_at": 25,
        "descriptor_traits": ["adaptability", "efficiency"],
        "floor_traits": ["reliability", "security"],
        "generations": 50,
        "goals_per_cell": 2,
        "hypothesis_free_arms": ["random", "scalar", "planner"],
        "hypothesis_holding_arms": ["qd", "majority"],
        "metric": "post_change_utility_auc",
        "minimum_reliability": 0.25,
        "minimum_security": 0.25,
        "seed_start": 1,
        "seeds": 100,
        "shell": {"distance_to_supplied": 0.3, "tolerance": 0.015},
        "trait_categories": dict(e034.TRAIT_CATEGORIES)
        if hasattr(e034, "TRAIT_CATEGORIES")
        else {t: e034.trait_category(t) for t in sim.TRAITS},
        "unconstrained_traits": ["simplicity"],
        "weight_targets": [0.02, 0.4],
        "weight_tolerance": 0.02,
        "traits": traits,
    }
    report.update(overrides)
    return report


#: A ladder set where every trait rises, so no sign flips and the descriptor
#: contrast is large. Two goals a cell keeps the arithmetic checkable by hand.
_RISING = {
    "adaptability": ([1.0, 1.2], [5.0, 5.2]),
    "efficiency": ([1.0, 1.2], [1.4, 1.6]),
    "reliability": ([1.0, 1.2], [5.0, 5.2]),
    "security": ([1.0, 1.2], [1.1, 1.9]),
    "simplicity": ([1.0, 1.2], [3.0, 3.2]),
}


def _shifted(leads, delta):
    return {
        trait: ([v + delta for v in low], [v + delta for v in high])
        for trait, (low, high) in leads.items()
    }


class ComparabilityTest(unittest.TestCase):
    def test_identical_designs_differ_only_in_panel(self):
        reports = {
            "perfect": _report("perfect", _RISING),
            "measured": _report("measured", _shifted(_RISING, -0.5)),
        }
        block = e037.comparability(reports)
        self.assertTrue(block["differs_only_in_panel"])
        self.assertEqual(block["differing_design_keys"], {})
        self.assertTrue(block["panel_labels_match_artifacts"])

    def test_a_drifted_setting_is_named_not_summarised(self):
        reports = {
            "perfect": _report("perfect", _RISING),
            "measured": _report("measured", _RISING, agents=32, seeds=50),
        }
        block = e037.comparability(reports)
        self.assertFalse(block["differs_only_in_panel"])
        self.assertEqual(block["differing_design_keys"]["measured"], ["agents", "seeds"])

    def test_a_mislabelled_artifact_is_caught(self):
        reports = {
            "perfect": _report("perfect", _RISING),
            # filed as `stress`, but the run was `measured`
            "stress": _report("measured", _RISING),
        }
        block = e037.comparability(reports)
        self.assertFalse(block["panel_labels_match_artifacts"])
        self.assertEqual(block["declared_panels"]["stress"], "measured")

    def test_the_baseline_is_required(self):
        with self.assertRaises(ValueError):
            e037.compare({"measured": _report("measured", _RISING)})

    def test_panel_is_not_a_design_key(self):
        self.assertNotIn("panel", e037.DESIGN_KEYS)

    def test_every_design_key_exists_in_a_real_artifact(self):
        report = _load(PANEL_FILES["perfect"])
        for key in e037.DESIGN_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, report)


class GoalAlignmentTest(unittest.TestCase):
    def test_the_same_shell_gives_identical_goal_sets(self):
        reports = {
            "perfect": _report("perfect", _RISING),
            "measured": _report("measured", _shifted(_RISING, -0.5)),
        }
        block = e037.goal_alignment(reports)
        self.assertTrue(block["identical_goal_sets"])
        self.assertEqual(block["shared_goals"], 20)

    def test_a_different_goal_set_is_reported_not_silently_intersected(self):
        other = _report("measured", _RISING)
        cell = other["traits"]["simplicity"]["cells"][0]
        cell["goal_results"][0]["goal"] = [0.9, 0.025, 0.025, 0.025, 0.025]
        block = e037.goal_alignment({"perfect": _report("perfect", _RISING), "measured": other})
        self.assertFalse(block["identical_goal_sets"])
        self.assertEqual(block["shared_goals"], 19)


class PairedShiftTest(unittest.TestCase):
    def test_a_constant_shift_has_zero_spread_and_infinite_t(self):
        base = _report("perfect", _RISING)
        other = _report("measured", _shifted(_RISING, -0.5))
        block = e037.paired_shift(base, other)
        self.assertEqual(block["pairs"], 20)
        self.assertAlmostEqual(block["mean_difference"], -0.5, places=6)
        self.assertEqual(block["standard_error"], 0.0)
        self.assertTrue(math.isinf(block["t"]))
        self.assertTrue(block["resolved"])
        self.assertEqual(block["goals_where_lead_falls"], 20)
        self.assertEqual(block["share_where_lead_falls"], 1.0)

    def test_no_shift_is_not_resolved(self):
        base = _report("perfect", _RISING)
        block = e037.paired_shift(base, _report("measured", _RISING))
        self.assertEqual(block["mean_difference"], 0.0)
        self.assertFalse(block["resolved"])
        self.assertEqual(block["goals_where_lead_falls"], 0)

    def test_the_pairing_is_by_goal_not_by_position(self):
        base = _report("perfect", _RISING)
        other = _report("measured", _shifted(_RISING, -0.5))
        # reverse every cell's goal order; a positional diff would still be
        # -0.5 here, so scramble the leads too and check the goal wins.
        for trait in other["traits"].values():
            for cell in trait["cells"]:
                cell["goal_results"].reverse()
        block = e037.paired_shift(base, other)
        self.assertAlmostEqual(block["mean_difference"], -0.5, places=6)
        self.assertEqual(block["standard_error"], 0.0)

    def test_the_consensus_arm_is_measurable_too(self):
        base = _report("perfect", _RISING)
        other = _report("measured", _shifted(_RISING, -0.5))
        block = e037.paired_shift(base, other, arm=e037.CONSENSUS_ARM)
        self.assertAlmostEqual(block["mean_difference"], -0.5, places=6)


class ReferenceArmTest(unittest.TestCase):
    def test_a_stable_yardstick_reports_no_transitions(self):
        base = _report("perfect", _RISING)
        other = _report("measured", _RISING)
        block = e037.reference_arm_switches(base, other)
        self.assertTrue(block["yardstick_is_stable"])
        self.assertEqual(block["transitions"], {})
        self.assertEqual(block["share"], 0.0)

    def test_a_moved_yardstick_is_counted_and_named(self):
        base = _report("perfect", _RISING, reference="random")
        other = _report("measured", _RISING, reference="planner")
        block = e037.reference_arm_switches(base, other)
        self.assertFalse(block["yardstick_is_stable"])
        self.assertEqual(block["goals_with_a_different_reference_arm"], 20)
        self.assertEqual(block["transitions"], {"random->planner": 20})
        self.assertEqual(block["share"], 1.0)


class CatastropheTest(unittest.TestCase):
    def test_the_shift_counts_both_directions(self):
        base = _report("perfect", _RISING, catastrophes=5)
        other = _report("measured", _RISING, catastrophes=9)
        block = e037.catastrophe_shift(base, other)
        self.assertEqual(block["baseline_mean"], 5.0)
        self.assertEqual(block["panel_mean"], 9.0)
        self.assertEqual(block["goals_that_get_worse"], 20)
        self.assertEqual(block["goals_that_get_better"], 0)

    def test_a_tie_is_not_strictly_best(self):
        report = _report("perfect", _RISING, catastrophes=3)
        block = e037.arm_catastrophes(report)
        self.assertTrue(block["archive_is_best"])
        self.assertFalse(block["archive_is_strictly_best"])

    @staticmethod
    def _lower(report, arm, value=1):
        for trait in report["traits"].values():
            for cell in trait["cells"]:
                for goal in cell["goal_results"]:
                    goal["catastrophic_seeds"][arm] = value

    def test_a_moved_ranking_is_separated_from_a_losing_archive(self):
        # The archive not topping the catastrophe count can be true at the
        # baseline as well; only a ranking that *moves* is about the panel.
        base = _report("perfect", _RISING, catastrophes=4)
        self._lower(base, "qd")
        other = _report("measured", _RISING, catastrophes=4)
        self._lower(other, "random")
        comparison = e037.compare({"perfect": base, "measured": other})
        self.assertFalse(comparison["archive_is_best_arm_on_every_panel"])
        self.assertFalse(comparison["catastrophe_ranking_is_panel_invariant"])
        self.assertEqual(
            comparison["catastrophe_best_arm_by_panel"],
            {"perfect": "qd", "measured": "random"},
        )

    def test_a_tie_names_the_first_arm_but_still_counts_the_archive_as_best(self):
        # `best_arm` is a min over a dict, so a tie resolves by STRATEGIES
        # order. `archive_is_best` must not inherit that arbitrary choice.
        report = _report("perfect", _RISING, catastrophes=4)
        block = e037.arm_catastrophes(report)
        self.assertEqual(block["best_arm"], mbe.STRATEGIES[0])
        self.assertTrue(block["archive_is_best"])
        self.assertFalse(block["archive_is_strictly_best"])

    def test_an_unmoved_ranking_is_reported_as_invariant(self):
        base = _report("perfect", _RISING, catastrophes=4)
        other = _report("measured", _RISING, catastrophes=9)
        comparison = e037.compare({"perfect": base, "measured": other})
        self.assertTrue(comparison["catastrophe_ranking_is_panel_invariant"])

    def test_the_best_arm_is_named_from_the_totals(self):
        report = _report("perfect", _RISING, catastrophes=4)
        for trait in report["traits"].values():
            for cell in trait["cells"]:
                for goal in cell["goal_results"]:
                    goal["catastrophic_seeds"]["qd"] = 1
        block = e037.arm_catastrophes(report)
        self.assertEqual(block["best_arm"], "qd")
        self.assertTrue(block["archive_is_strictly_best"])


class PanelFactsTest(unittest.TestCase):
    def test_the_perfect_column_records_that_no_verifier_was_drawn(self):
        facts = e037.panel_facts("perfect")
        self.assertFalse(facts["verification_drawn"])
        self.assertEqual(facts["verifiers"], 0)

    def test_the_sweep_really_does_skip_the_draw_for_perfect(self):
        # The reason the column above is not e027.PANELS["perfect"].
        self.assertIsNone(e033._panel("perfect"))
        self.assertIsNotNone(e027.PANELS["perfect"])

    def test_the_imperfect_panels_are_read_from_e027_not_restated(self):
        for name in ("measured", "stress"):
            with self.subTest(panel=name):
                facts = e037.panel_facts(name)
                config = e027.PANELS[name]
                self.assertTrue(facts["verification_drawn"])
                self.assertEqual(facts["verifiers"], config.verifiers)
                self.assertEqual(facts["accuracy"], config.accuracy)
                self.assertEqual(facts["correlation"], config.correlation)
                self.assertEqual(facts["blind_spot"], config.blind_spot)

    def test_measured_and_independent_differ_only_in_correlation(self):
        # E036's headline, restated as the reason `measured` is the panel that
        # matters here rather than a lower-accuracy one.
        measured, independent = e027.PANELS["measured"], e027.PANELS["independent"]
        self.assertEqual(measured.verifiers, independent.verifiers)
        self.assertEqual(measured.accuracy, independent.accuracy)
        self.assertGreater(measured.correlation, independent.correlation)


class PredictionTest(unittest.TestCase):
    def _comparison(self, **flags):
        block = {
            "descriptor_cancellation_survives": True,
            "no_sign_flips": True,
            "floored_pair_asymmetry_survives": True,
            "archive_still_leads": True,
        }
        block.update(flags)
        return block

    def test_all_four_clauses_met_is_supported(self):
        outcome = e037.prediction_outcome(self._comparison())
        self.assertTrue(outcome["supported"])
        self.assertFalse(outcome["partially_supported"])
        self.assertEqual(outcome["met_count"], 4)

    def test_one_broken_clause_is_reported_as_partial_not_as_support(self):
        outcome = e037.prediction_outcome(self._comparison(no_sign_flips=False))
        self.assertFalse(outcome["supported"])
        self.assertTrue(outcome["partially_supported"])
        self.assertEqual(outcome["met_count"], 3)
        self.assertFalse(outcome["met"]["no_trait_sign_flips_across_panels"])

    def test_everything_broken_is_neither_supported_nor_partial(self):
        outcome = e037.prediction_outcome(
            self._comparison(
                descriptor_cancellation_survives=False,
                no_sign_flips=False,
                floored_pair_asymmetry_survives=False,
                archive_still_leads=False,
            )
        )
        self.assertFalse(outcome["supported"])
        self.assertFalse(outcome["partially_supported"])
        self.assertEqual(outcome["met_count"], 0)

    def test_the_prediction_names_where_it_came_from(self):
        self.assertIn("E035", e037.PREDICTION["source"])
        self.assertEqual(
            sorted(e037.PREDICTION["if_the_structure_is_geometric"]),
            sorted(e037.prediction_outcome(self._comparison())["clauses"]),
        )


class VocabularyTest(unittest.TestCase):
    def test_resolved_means_the_same_thing_as_in_e035(self):
        self.assertIs(e037.RESOLVED_T, e035.RESOLVED_T)

    def test_the_verdicts_are_e035s_and_not_a_second_set(self):
        report = _report("perfect", _RISING)
        block = e035.replication([e035.ladder_change(report, "simplicity")])
        self.assertIn(
            block["verdict"], (e035.REPLICATES, e035.CONSISTENT, e035.SIGN_FLIPS)
        )

    def test_a_sign_flip_across_panels_is_reachable(self):
        falling = dict(_RISING)
        falling["simplicity"] = ([3.0, 3.2], [1.0, 1.2])
        reports = {
            "perfect": _report("perfect", _RISING),
            "measured": _report("measured", falling),
        }
        comparison = e037.compare(reports)
        self.assertEqual(
            comparison["trait_replication"]["simplicity"]["verdict"], e035.SIGN_FLIPS
        )
        self.assertFalse(comparison["no_sign_flips"])


def _leakage_rows(**per_panel):
    """A leakage table: panel -> arm -> metrics, every arm the same."""
    return {
        panel: {
            arm: {
                "false_accept_rate": values[0],
                "false_reject_rate": values[1],
                "archive_size": values[2],
            }
            for arm in mbe.STRATEGIES
        }
        for panel, values in per_panel.items()
    }


class LeakageTest(unittest.TestCase):
    def test_the_probe_goals_come_from_the_committed_sweep(self):
        report = _load(PANEL_FILES["perfect"])
        goals = e037.leakage_goals(report)
        self.assertEqual(sorted(goals), sorted(sim.TRAITS))
        measured = {
            tuple(g["goal"])
            for trait in report["traits"].values()
            for cell in trait["cells"]
            for g in cell["goal_results"]
        }
        for trait, goal in goals.items():
            with self.subTest(trait=trait):
                self.assertIn(goal, measured)

    def test_each_probe_goal_sits_in_the_heavy_cell_of_its_own_trait(self):
        report = _load(PANEL_FILES["perfect"])
        for trait, goal in e037.leakage_goals(report).items():
            with self.subTest(trait=trait):
                self.assertAlmostEqual(
                    goal[e034.trait_index(trait)],
                    e037.LEAKAGE_WEIGHT,
                    delta=e034.WEIGHT_TOLERANCE,
                )

    def test_a_rising_error_rate_is_reported_as_rising(self):
        rows = _leakage_rows(
            perfect=(0.0, 0.0, 64.0),
            measured=(0.18, 0.17, 64.0),
            stress=(0.44, 0.45, 64.0),
        )
        block = e037.leakage_summary(rows, ["perfect", "measured", "stress"])
        self.assertTrue(block["false_accepts_rise_as_the_panel_weakens"])
        self.assertTrue(block["false_rejects_rise_as_the_panel_weakens"])

    def test_a_flat_error_rate_is_not_reported_as_rising(self):
        rows = _leakage_rows(
            perfect=(0.2, 0.2, 64.0),
            measured=(0.2, 0.2, 64.0),
        )
        block = e037.leakage_summary(rows, ["perfect", "measured"])
        self.assertFalse(block["false_accepts_rise_as_the_panel_weakens"])
        self.assertFalse(block["false_rejects_rise_as_the_panel_weakens"])

    def test_a_capacity_bound_archive_is_not_mistaken_for_a_growing_one(self):
        rows = _leakage_rows(
            perfect=(0.0, 0.0, 64.0),
            measured=(0.18, 0.17, 64.0),
            stress=(0.44, 0.45, 64.0),
        )
        block = e037.leakage_summary(rows, ["perfect", "measured", "stress"])
        self.assertTrue(block["archive_is_capacity_bound"])
        self.assertEqual(set(block["archive_size_by_panel"].values()), {64.0})

    def test_a_growing_archive_is_reported_as_not_capacity_bound(self):
        rows = _leakage_rows(
            perfect=(0.0, 0.0, 40.0),
            measured=(0.18, 0.17, 64.0),
        )
        block = e037.leakage_summary(rows, ["perfect", "measured"])
        self.assertFalse(block["archive_is_capacity_bound"])

    def test_the_asymmetry_keeps_its_sign(self):
        rows = _leakage_rows(leaky=(0.30, 0.10, 64.0), blocky=(0.10, 0.30, 64.0))
        block = e037.leakage_summary(rows, ["leaky", "blocky"])
        self.assertAlmostEqual(block["error_asymmetry"]["leaky"], 0.20, places=6)
        self.assertAlmostEqual(block["error_asymmetry"]["blocky"], -0.20, places=6)

    def test_a_panel_that_favours_one_arm_would_be_visible(self):
        rows = _leakage_rows(measured=(0.18, 0.17, 64.0))
        rows["measured"]["qd"]["false_accept_rate"] = 0.40
        block = e037.leakage_summary(rows, ["measured"])
        self.assertAlmostEqual(
            block["widest_false_accept_gap_between_arms"]["measured"], 0.22, places=6
        )


class CommittedLeakageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _load(LEAKAGE_FILE)

    def test_the_verdicts_are_a_function_of_the_committed_rows(self):
        fresh = e037.leakage_summary(self.report["per_panel"], self.report["panels"])
        for key, value in fresh.items():
            with self.subTest(key=key):
                self.assertEqual(self.report[key], value)

    def test_the_probe_ran_on_every_panel_the_comparison_used(self):
        self.assertEqual(self.report["panels"], _load(COMPARISON_FILE)["panels"])

    def test_the_perfect_panel_makes_no_errors_at_all(self):
        row = self.report["per_panel"]["perfect"]
        for arm in mbe.STRATEGIES:
            with self.subTest(arm=arm):
                self.assertEqual(row[arm]["false_accept_rate"], 0.0)
                self.assertEqual(row[arm]["false_reject_rate"], 0.0)

    def test_only_the_archive_arm_reports_an_archive(self):
        for panel in self.report["panels"]:
            row = self.report["per_panel"][panel]
            with self.subTest(panel=panel):
                self.assertGreater(row[e037.ARCHIVE_ARM]["archive_size"], 0)
                for arm in mbe.STRATEGIES:
                    if arm != e037.ARCHIVE_ARM:
                        self.assertEqual(row[arm]["archive_size"], 0)

    def test_the_panel_does_not_favour_any_arm(self):
        # If it did, every cross-arm comparison in E030-E035 is confounded.
        for panel, gap in self.report["widest_false_accept_gap_between_arms"].items():
            with self.subTest(panel=panel):
                self.assertLess(gap, 0.05)


class CommittedComparisonTest(unittest.TestCase):
    """The committed comparison must be what the committed sweeps imply."""

    @classmethod
    def setUpClass(cls):
        cls.reports = _reports()
        cls.committed = _load(COMPARISON_FILE)
        cls.fresh = e037.compare(cls.reports)

    def test_the_runs_differ_only_in_the_panel(self):
        self.assertTrue(self.committed["comparability"]["differs_only_in_panel"])
        self.assertEqual(self.committed["comparability"]["differing_design_keys"], {})
        self.assertTrue(self.committed["comparability"]["panel_labels_match_artifacts"])

    def test_the_three_panels_measured_the_same_goals(self):
        block = self.committed["goal_alignment"]
        self.assertTrue(block["identical_goal_sets"])
        self.assertEqual(
            set(block["goals_per_panel"].values()), {block["shared_goals"]}
        )

    def test_the_pairing_covers_every_goal_in_the_shell(self):
        for name in ("measured", "stress"):
            with self.subTest(panel=name):
                self.assertEqual(
                    self.committed["against_baseline"][name]["lead"]["pairs"],
                    self.committed["goal_alignment"]["shared_goals"],
                )

    def test_every_per_panel_block_reproduces(self):
        for name in self.committed["panels"]:
            with self.subTest(panel=name):
                self.assertEqual(
                    self.committed["per_panel"][name], self.fresh["per_panel"][name]
                )

    def test_every_paired_block_reproduces(self):
        for name in self.committed["against_baseline"]:
            with self.subTest(panel=name):
                self.assertEqual(
                    self.committed["against_baseline"][name],
                    self.fresh["against_baseline"][name],
                )

    def test_the_committed_comparability_is_recomputable_from_the_sweeps(self):
        # Without this, a sweep filed under the wrong panel name is invisible:
        # `panel` is not a design key, so nothing else would notice.
        self.assertEqual(
            self.committed["comparability"], self.fresh["comparability"]
        )
        self.assertEqual(
            self.committed["goal_alignment"], self.fresh["goal_alignment"]
        )

    def test_the_verdicts_reproduce(self):
        for key in (
            "comparability",
            "goal_alignment",
            "catastrophe_ranking_is_panel_invariant",
            "catastrophe_best_arm_by_panel",
            "trait_replication",
            "descriptor_cancellation_survives",
            "floored_pair_asymmetry_survives",
            "no_sign_flips",
            "archive_still_leads",
            "archive_is_best_arm_on_every_panel",
        ):
            with self.subTest(key=key):
                self.assertEqual(self.committed[key], self.fresh[key])

    def test_the_outcome_is_a_function_of_the_committed_comparison(self):
        self.assertEqual(
            self.committed["prediction_outcome"],
            e037.prediction_outcome(self.committed),
        )

    def test_the_perfect_arm_is_e034s_own_committed_artifact(self):
        perfect = self.reports["perfect"]
        self.assertEqual(perfect["experiment_id"], "E034")
        self.assertEqual(perfect["panel"], "perfect")

    def test_the_shell_is_e034s_shell(self):
        for name, report in self.reports.items():
            with self.subTest(panel=name):
                self.assertAlmostEqual(
                    report["shell"]["distance_to_supplied"],
                    e034.SHELL_DISTANCE_TO_SUPPLIED,
                    places=6,
                )


class WriteUpTest(unittest.TestCase):
    """The record's numbers must be the artifact's numbers."""

    @classmethod
    def setUpClass(cls):
        with open(WRITE_UP, encoding="utf-8") as handle:
            cls.text = handle.read()
        cls.report = _load(COMPARISON_FILE)

    @staticmethod
    def _cells(line):
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def _ladder_table(self):
        """The per-trait ladder table, read by header rather than by position.

        Located by a header row that names every panel, so reordering the
        columns or inserting one cannot silently make the test compare a trait
        against the wrong panel -- the failure mode a fixed column index has.
        """
        lines = self.text.splitlines()
        panels = self.report["panels"]
        for index, line in enumerate(lines):
            if not line.startswith("|"):
                continue
            header = self._cells(line)
            columns = {}
            for panel in panels:
                matches = [i for i, cell in enumerate(header) if panel in cell]
                if len(matches) == 1:
                    columns[panel] = matches[0]
            if len(columns) != len(panels):
                continue
            rows = {}
            for follower in lines[index + 1 :]:
                if not follower.startswith("|"):
                    break
                cells = self._cells(follower)
                match = re.fullmatch(r"`(\w+)`", cells[0])
                if match and match.group(1) in sim.TRAITS:
                    rows[match.group(1)] = {
                        panel: cells[position] for panel, position in columns.items()
                    }
            if rows:
                return rows
        return {}

    def test_the_ladder_table_names_every_trait(self):
        self.assertEqual(sorted(self._ladder_table()), sorted(sim.TRAITS))

    def test_every_ladder_cell_matches_the_artifact(self):
        table = self._ladder_table()
        self.assertTrue(table, "no ladder table found in the record")
        for trait, cells in table.items():
            for panel, cell in cells.items():
                with self.subTest(trait=trait, panel=panel):
                    ladder = self.report["per_panel"][panel]["ladders"][trait]
                    numbers = [
                        round(float(value), 3)
                        for value in re.findall(r"[-+]?\d+\.\d+", cell)
                    ]
                    self.assertIn(round(ladder["change"], 3), numbers)
                    self.assertIn(round(ladder["t"], 2), [round(n, 2) for n in numbers])

    def test_the_verdict_words_are_the_artifacts_verdicts(self):
        for trait, block in self.report["trait_replication"].items():
            with self.subTest(trait=trait):
                self.assertRegex(
                    self.text, rf"`{trait}`[^\n]*", "trait is not discussed at all"
                )
        for verdict in {b["verdict"] for b in self.report["trait_replication"].values()}:
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, self.text)

    def test_the_prediction_outcome_is_stated_as_measured(self):
        outcome = self.report["prediction_outcome"]
        word = "supported" if outcome["supported"] else (
            "partially supported" if outcome["partially_supported"] else "not supported"
        )
        self.assertIn(word, self.text.lower())
        self.assertIn(
            f"{outcome['met_count']} of {outcome['clause_count']}", self.text
        )

    def test_the_paired_shift_numbers_are_in_the_prose(self):
        for name, block in self.report["against_baseline"].items():
            with self.subTest(panel=name):
                self.assertIn(f"{block['lead']['mean_difference']:+.3f}", self.text)

    def test_the_record_says_which_panel_the_perfect_column_is(self):
        self.assertIn("verification_drawn", self.text)

    def test_the_ruled_out_mechanism_is_stated_as_the_probe_measured_it(self):
        # The record's whole Result 4 rests on the archive NOT growing. If the
        # probe ever says otherwise, the prose must not still say "capacity-bound".
        leakage = _load(LEAKAGE_FILE)
        sizes = set(leakage["archive_size_by_panel"].values())
        if leakage["archive_is_capacity_bound"]:
            self.assertIn("capacity-bound", self.text)
            self.assertIn(f"`{int(sizes.pop())}`", self.text)
        else:
            self.assertNotIn("capacity-bound", self.text)

    def test_the_probe_numbers_are_in_the_prose(self):
        leakage = _load(LEAKAGE_FILE)
        for panel in leakage["panels"]:
            row = leakage["per_panel"][panel][e037.ARCHIVE_ARM]
            for key in ("false_accept_rate", "false_reject_rate"):
                with self.subTest(panel=panel, key=key):
                    self.assertIn(f"{row[key]:.6f}", self.text)

    def test_the_record_carries_a_limitations_section(self):
        self.assertIn("## Limitations", self.text)
        self.assertIn("## Decision", self.text)


class SupersededRecordTest(unittest.TestCase):
    """E035 named this test; its record must say the answer, in place."""

    @classmethod
    def setUpClass(cls):
        with open(E035_WRITE_UP, encoding="utf-8") as handle:
            cls.text = handle.read()

    def test_e035_points_forward_to_e037(self):
        self.assertIn("E037", self.text)
        self.assertIn("E037-ladder-under-panels.md", self.text)

    def test_the_one_panel_limitation_is_marked_answered(self):
        limitation = re.search(r"\*\*One panel\.\*\*(.+?)\n\n", self.text, re.S)
        self.assertIsNotNone(limitation, "E035's one-panel limitation is gone")
        self.assertIn("E037", limitation.group(1))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
