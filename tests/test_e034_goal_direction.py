"""Tests for E034: is the archive's failure directional, and in which direction?

E033 found two goals that broke the archive and noticed both devalued
``security``, but could not separate that from the distance it was sweeping.
E034's whole claim rests on the shell being genuinely fixed, so the tests here
pin, in order:

1. the trait categories are read off the arena -- ``sim.viable`` and
   ``sim.niche`` -- and not asserted, so an edit to either fails here;
2. every measured goal really sits at one distance and one change size, because
   if the shell leaks the experiment is E033 again with fewer seeds;
3. a cell's goals differ in every direction except the one being held;
4. ``rises``/``falls`` are arithmetic on disjoint intervals, and the honest
   ``unresolved`` is reachable.
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e030_supplied_goal_membership as e030
import sim.e033_goal_distance as e033
import sim.e034_goal_direction as e034

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _cell(weight, mean_lead, half):
    return {
        "target_weight": weight,
        "lead_mean": mean_lead,
        "ci95_low": mean_lead - half,
        "ci95_high": mean_lead + half,
    }


class TraitCategoryTest(unittest.TestCase):
    def test_the_floored_traits_are_the_ones_viability_actually_floors(self):
        # Read off sim.viable rather than trusted: a candidate one step under
        # each floor must be rejected, and one step over accepted.
        for trait in e034.FLOOR_TRAITS:
            index = e034.trait_index(trait)
            floor = (sim.MIN_RELIABILITY, sim.MIN_SECURITY)[
                e034.FLOOR_TRAITS.index(trait)
            ]
            traits = [0.4, 0.4, 0.4, 0.4, 0.4]
            traits[index] = floor - 0.01
            with self.subTest(trait=trait):
                self.assertFalse(sim.viable(sim.Candidate(tuple(traits))))
                traits[index] = floor + 0.01
                self.assertTrue(sim.viable(sim.Candidate(tuple(traits))))

    def test_no_other_trait_is_floored(self):
        for trait in sim.TRAITS:
            if trait in e034.FLOOR_TRAITS:
                continue
            index = e034.trait_index(trait)
            traits = [0.4, 0.4, 0.4, 0.4, 0.4]
            traits[index] = 0.0
            with self.subTest(trait=trait):
                self.assertTrue(sim.viable(sim.Candidate(tuple(traits))))

    def test_the_descriptor_traits_are_the_ones_the_archive_bins_on(self):
        # Moving a descriptor trait must move the niche; moving any other must
        # not. That is what makes "descriptor" a structural category.
        base = [0.4, 0.4, 0.4, 0.4, 0.4]
        origin = sim.niche(sim.Candidate(tuple(base)), 8)
        for trait in sim.TRAITS:
            index = e034.trait_index(trait)
            moved = list(base)
            moved[index] = 0.05
            changed = sim.niche(sim.Candidate(tuple(moved)), 8) != origin
            with self.subTest(trait=trait):
                self.assertEqual(changed, trait in e034.DESCRIPTOR_TRAITS)

    def test_every_trait_has_exactly_one_category(self):
        groups = (
            e034.FLOOR_TRAITS + e034.DESCRIPTOR_TRAITS + e034.UNCONSTRAINED_TRAITS
        )
        self.assertEqual(sorted(groups), sorted(sim.TRAITS))
        self.assertEqual(len(set(groups)), len(groups))

    def test_the_control_trait_is_neither_floored_nor_a_descriptor(self):
        for trait in e034.UNCONSTRAINED_TRAITS:
            with self.subTest(trait=trait):
                self.assertEqual(e034.trait_category(trait), "unconstrained")
                self.assertNotIn(trait, e034.FLOOR_TRAITS)
                self.assertNotIn(trait, e034.DESCRIPTOR_TRAITS)


class ShellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = e033.simplex_pool(draws=200_000, seed=e034.POOL_SEED)
        cls.members = e034.shell(cls.pool)

    def test_the_shell_is_not_empty(self):
        self.assertGreater(len(self.members), 100)

    def test_every_shell_member_holds_both_distances(self):
        for goal in self.members[:500]:
            with self.subTest(goal=goal):
                self.assertLessEqual(
                    abs(
                        e033.distance_to_supplied(goal)
                        - e034.SHELL_DISTANCE_TO_SUPPLIED
                    ),
                    e034.SHELL_TOLERANCE + 1e-9,
                )
                self.assertLessEqual(
                    abs(e033.distance_from_initial(goal) - e034.SHELL_CHANGE_SIZE),
                    e034.SHELL_TOLERANCE + 1e-9,
                )

    def test_the_shell_sits_on_e033s_matched_ladder(self):
        # The shell is a slice of E033's population, not a new one.
        self.assertEqual(e034.SHELL_CHANGE_SIZE, e033.MATCHED_CHANGE_SIZE)
        self.assertIn(e034.SHELL_DISTANCE_TO_SUPPLIED, e033.MATCHED_RINGS)

    def test_a_goal_off_either_distance_is_not_on_the_shell(self):
        self.assertFalse(e034.on_shell(sim.INITIAL_GOAL))
        self.assertFalse(e034.on_shell(e030.UNHELD_GOAL))

    def test_cells_hold_the_swept_weight_and_nothing_else_moves_the_distances(self):
        for trait in sim.TRAITS:
            index = e034.trait_index(trait)
            for cell in e034.ladder(trait, self.members, count=2):
                for entry in cell["goals"]:
                    with self.subTest(trait=trait, weight=cell["target_weight"]):
                        self.assertLessEqual(
                            abs(entry["weight"] - cell["target_weight"]),
                            e034.WEIGHT_TOLERANCE + 1e-9,
                        )
                        self.assertAlmostEqual(
                            entry["goal"][index], entry["weight"], places=6
                        )
                        self.assertLessEqual(
                            abs(
                                entry["distance_to_supplied"]
                                - e034.SHELL_DISTANCE_TO_SUPPLIED
                            ),
                            e034.SHELL_TOLERANCE + 1e-9,
                        )

    def test_a_cells_goals_differ_in_the_directions_not_being_held(self):
        goals = e034.cell_goals(self.members, trait="security", target=0.20, count=3)
        self.assertEqual(len(set(goals)), 3)
        self.assertGreater(
            min(
                math.dist(a, b)
                for i, a in enumerate(goals)
                for b in goals[i + 1 :]
            ),
            0.0,
        )

    def test_cell_selection_is_deterministic(self):
        first = e034.cell_goals(self.members, trait="efficiency", target=0.30, count=3)
        second = e034.cell_goals(self.members, trait="efficiency", target=0.30, count=3)
        self.assertEqual(first, second)

    def test_an_unfillable_cell_raises(self):
        with self.assertRaises(ValueError):
            e034.cell_goals(
                self.members, trait="security", target=0.95, count=2, tolerance=0.001
            )

    def test_an_unknown_trait_raises(self):
        with self.assertRaises(ValueError):
            e034.ladder("elegance", self.members, count=2)


class ClassifyResponseTest(unittest.TestCase):
    def test_a_lead_that_climbs_with_the_weight_rises(self):
        cells = [_cell(w, lead, 0.05) for w, lead in
                 ((0.02, -1.0), (0.20, 1.0), (0.40, 3.0))]
        report = e034.classify_response(cells)
        self.assertEqual(report["response"], "rises")
        self.assertTrue(report["monotone"])
        self.assertAlmostEqual(report["change_across_the_ladder"], 4.0, places=6)

    def test_a_lead_that_falls_with_the_weight_falls(self):
        cells = [_cell(w, lead, 0.05) for w, lead in
                 ((0.02, 3.0), (0.20, 1.0), (0.40, -1.0))]
        self.assertEqual(e034.classify_response(cells)["response"], "falls")

    def test_overlapping_ends_are_unresolved_whatever_the_middle_does(self):
        cells = [_cell(w, lead, 1.5) for w, lead in
                 ((0.02, 0.0), (0.20, 2.0), (0.40, 0.4))]
        report = e034.classify_response(cells)
        self.assertEqual(report["response"], "unresolved")
        self.assertFalse(report["endpoints_separate"])

    def test_a_non_monotone_but_separated_ladder_is_still_called(self):
        cells = [_cell(w, lead, 0.05) for w, lead in
                 ((0.02, 0.0), (0.20, -1.0), (0.40, 3.0))]
        report = e034.classify_response(cells)
        self.assertEqual(report["response"], "rises")
        self.assertFalse(report["monotone"])

    def test_one_cell_cannot_be_classified(self):
        self.assertEqual(
            e034.classify_response([_cell(0.02, 1.0, 0.1)])["response"], "unresolved"
        )

    def test_the_endpoint_margin_is_reported_so_a_null_can_be_judged(self):
        cells = [_cell(0.02, 0.0, 1.0), _cell(0.40, 0.5, 2.0)]
        self.assertAlmostEqual(
            e034.classify_response(cells)["endpoint_margin"], 3.0, places=6
        )


class SweepShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = e034.sweep(
            traits=("security", "simplicity"),
            targets=(0.02, 0.30),
            count=2,
            pool_draws=120_000,
            seeds=2,
            agents=16,
        )

    def test_each_trait_carries_its_category_and_a_response_per_holding_arm(self):
        for trait in ("security", "simplicity"):
            with self.subTest(trait=trait):
                row = self.report["traits"][trait]
                self.assertEqual(row["category"], e034.trait_category(trait))
                self.assertEqual(
                    sorted(row["response"]), sorted(e033.HYPOTHESIS_HOLDING)
                )

    def test_every_cell_records_the_shell_it_was_drawn_from(self):
        for trait, row in self.report["traits"].items():
            for cell in row["cells"]:
                with self.subTest(trait=trait, weight=cell["target_weight"]):
                    self.assertLess(
                        abs(
                            cell["mean_distance_to_supplied"]
                            - e034.SHELL_DISTANCE_TO_SUPPLIED
                        ),
                        e034.SHELL_TOLERANCE,
                    )
                    self.assertLess(
                        abs(
                            cell["mean_distance_from_initial"]
                            - e034.SHELL_CHANGE_SIZE
                        ),
                        e034.SHELL_TOLERANCE,
                    )

    def test_the_arena_constants_the_categories_depend_on_are_recorded(self):
        self.assertEqual(self.report["minimum_reliability"], sim.MIN_RELIABILITY)
        self.assertEqual(self.report["minimum_security"], sim.MIN_SECURITY)

    def test_an_empty_shell_raises_rather_than_reporting_nothing(self):
        with self.assertRaises(ValueError):
            e034.sweep(
                traits=("security",),
                targets=(0.20,),
                count=1,
                pool_draws=2000,
                shell_tolerance=1e-6,
                seeds=1,
                agents=16,
            )


class CliTest(unittest.TestCase):
    def test_defaults_are_the_published_settings(self):
        args = e034.parse_args([])
        self.assertEqual(args.goals_per_cell, e034.GOALS_PER_CELL)
        self.assertEqual(args.distance, e034.SHELL_DISTANCE_TO_SUPPLIED)
        self.assertEqual(args.jobs, 1)

    def test_traits_and_weights_accumulate(self):
        args = e034.parse_args(
            ["--trait", "security", "--trait", "simplicity", "--weight", "0.1"]
        )
        self.assertEqual(args.trait, ["security", "simplicity"])
        self.assertEqual(args.weight, [0.1])


class CategoryViewTest(unittest.TestCase):
    """The hypothesis is about categories, so the pooled view has to be sound."""

    @classmethod
    def setUpClass(cls):
        cls.report = e034.sweep(
            traits=("security", "reliability", "simplicity"),
            targets=(0.02, 0.30),
            count=2,
            pool_draws=120_000,
            seeds=2,
            agents=16,
        )

    def test_a_category_pools_every_goal_of_its_traits(self):
        floored = self.report["categories"]["floored"]
        self.assertEqual(floored["traits"], ["reliability", "security"])
        for cell in floored["cells"]:
            with self.subTest(weight=cell["target_weight"]):
                self.assertEqual(cell["goals"], 4)

    def test_a_one_trait_category_pools_only_that_trait(self):
        control = self.report["categories"]["unconstrained"]
        self.assertEqual(control["traits"], ["simplicity"])
        for cell in control["cells"]:
            self.assertEqual(cell["goals"], 2)

    def test_a_category_absent_from_the_run_is_absent_from_the_view(self):
        self.assertNotIn("descriptor", self.report["categories"])

    def test_the_pooled_mean_is_the_mean_of_the_pooled_goals(self):
        floored = self.report["categories"]["floored"]["cells"][0]
        goals = [
            result["lead_over_hypothesis_free"]["qd"]
            for trait in ("reliability", "security")
            for result in self.report["traits"][trait]["cells"][0]["goal_results"]
        ]
        self.assertAlmostEqual(
            floored["qd"]["lead_mean"], sum(goals) / len(goals), places=5
        )

    def test_the_pooled_interval_is_narrower_than_a_single_traits(self):
        # The whole point of pooling: two traits' worth of goals at one weight.
        pooled = self.report["categories"]["floored"]["cells"][0]["qd"]
        single = self.report["traits"]["simplicity"]["cells"][0]["qd"]
        self.assertGreater(pooled["goals"], single["goals"])


def _welch(a, b):
    """(difference, standard error, t) for two independent samples."""
    mean_a, mean_b = statistics.fmean(a), statistics.fmean(b)
    var = statistics.variance(a) / len(a) + statistics.variance(b) / len(b)
    error = math.sqrt(var)
    return mean_a - mean_b, error, (mean_a - mean_b) / error


class CommittedResultTest(unittest.TestCase):
    """Every claim the write-up makes, read back off the committed artifact.

    The write-up's numbers are transcribed by hand, and the ``categories`` block
    was added to the artifact after the sweep ran, so both are checked against
    the module rather than trusted.
    """

    @classmethod
    def setUpClass(cls):
        cls.report = _load("E034-goal-direction.json")
        cls.traits = cls.report["traits"]
        path = os.path.join(REPO_ROOT, "experiments", "E034-goal-direction.md")
        with open(path, encoding="utf-8") as handle:
            cls.doc = handle.read()
        cls.slots = [
            (name, cell["target_weight"], goal)
            for name, trait in cls.traits.items()
            for cell in trait["cells"]
            for goal in cell["goal_results"]
        ]
        cls.distinct = {tuple(g["goal"]): g for _, _, g in cls.slots}

    def _leads(self, trait, index):
        cell = self.traits[trait]["cells"][index]
        return [g["lead_over_hypothesis_free"]["qd"] for g in cell["goal_results"]]

    def _change(self, trait):
        return _welch(self._leads(trait, -1), self._leads(trait, 0))

    # -- the shell, which every other claim depends on ---------------------

    def test_every_measured_goal_really_sits_on_the_one_shell(self):
        shell = self.report["shell"]
        for name, weight, goal in self.slots:
            with self.subTest(trait=name, weight=weight):
                self.assertLessEqual(
                    abs(goal["distance_to_supplied"] - shell["distance_to_supplied"]),
                    shell["tolerance"],
                )
                self.assertLessEqual(
                    abs(goal["distance_from_initial"] - shell["change_size"]),
                    shell["tolerance"],
                )

    def test_the_sweep_is_the_size_the_write_up_claims(self):
        self.assertEqual(len(self.slots), 400)
        self.assertEqual(len(self.distinct), 385)
        # A goal lands in a cell by the weight it puts on that trait, so a few
        # legitimately appear in two ladders. The write-up states the number.
        shared = sum(
            1
            for key in self.distinct
            if sum(1 for _, _, g in self.slots if tuple(g["goal"]) == key) > 1
        )
        self.assertEqual(shared, 15)

    # -- Result 1 ----------------------------------------------------------

    def test_direction_alone_spans_a_wider_range_than_e033s_whole_distance_sweep(self):
        leads = [g["lead_over_hypothesis_free"]["qd"] for g in self.distinct.values()]
        spread = max(leads) - min(leads)
        self.assertAlmostEqual(min(leads), -4.894, places=3)
        self.assertAlmostEqual(max(leads), 4.471, places=3)
        self.assertAlmostEqual(spread, 9.365, places=3)
        # E033's matched ladder moved the ring mean by 3.309 end to end.
        self.assertGreater(spread, 2 * 3.309)
        negative = sum(1 for x in leads if x < 0)
        self.assertEqual(negative, 93)
        self.assertAlmostEqual(100 * negative / len(leads), 24.2, places=1)

    # -- Result 2 ----------------------------------------------------------

    def test_the_five_ladders_have_the_shapes_the_write_up_reports(self):
        expected = {
            "reliability": "rises",
            "security": "unresolved",
            "adaptability": "rises",
            "efficiency": "falls",
            "simplicity": "falls",
        }
        for trait, shape in expected.items():
            with self.subTest(trait=trait):
                self.assertEqual(self.traits[trait]["response"]["qd"]["response"], shape)

    def test_every_resolved_ladder_survives_bonferroni_over_the_five_tests(self):
        # Five preregistered ladders, so the bar is 0.05/5 = 0.010. The smallest
        # Welch df among them is 18.2, where the two-sided 0.01 critical value is
        # 2.878; requiring |t| > 2.878 of all of them is therefore conservative.
        for trait, shape in [
            ("reliability", "rises"),
            ("adaptability", "rises"),
            ("efficiency", "falls"),
            ("simplicity", "falls"),
        ]:
            with self.subTest(trait=trait):
                _, _, t = self._change(trait)
                self.assertEqual(self.traits[trait]["response"]["qd"]["response"], shape)
                self.assertGreater(abs(t), 2.878)

    def test_the_unresolved_ladder_is_unresolved_by_both_criteria(self):
        # security must fail the classifier's disjoint-interval test *and* the
        # t-test, or the write-up's "one clear effect and one null" is wrong.
        _, _, t = self._change("security")
        self.assertLess(abs(t), 2.042)  # two-sided 0.05, df 22.7
        self.assertFalse(
            self.traits["security"]["response"]["qd"]["endpoints_separate"]
        )

    # -- Result 3, the falsification -------------------------------------

    def test_the_preregistered_control_trait_moved_which_kills_the_floor_story(self):
        # The prediction was that the lead is flat in simplicity. It is not: the
        # ladder resolves, is monotone, and the lead changes sign.
        response = self.traits["simplicity"]["response"]["qd"]
        self.assertEqual(response["response"], "falls")
        self.assertTrue(response["endpoints_separate"])
        self.assertTrue(response["monotone"])
        self.assertGreater(response["lead_at_lowest_weight"], 0)
        self.assertLess(response["lead_at_highest_weight"], 0)

    def test_the_two_identically_floored_traits_do_not_behave_alike(self):
        # sim.viable floors reliability and security on the same constant, so a
        # floor mechanism predicts matching ladders.
        self.assertEqual(sim.MIN_RELIABILITY, sim.MIN_SECURITY)
        reliability, security = self._change("reliability"), self._change("security")
        self.assertGreater(abs(reliability[2]), 2.878)
        self.assertLess(abs(security[2]), 2.042)
        # ...but the write-up only claims the weaker thing, because the contrast
        # between the two ladders is itself unresolved.
        difference = reliability[0] - security[0]
        error = math.hypot(reliability[1], security[1])
        self.assertLess(abs(difference / error), 2.042)

    def test_the_descriptor_category_is_a_cancellation_not_a_group(self):
        adaptability, efficiency = self._change("adaptability"), self._change("efficiency")
        self.assertGreater(adaptability[0], 0)
        self.assertLess(efficiency[0], 0)
        contrast = adaptability[0] - efficiency[0]
        error = math.hypot(adaptability[1], efficiency[1])
        self.assertGreater(contrast / error, 2.878)
        # Averaged together they vanish, which is why the category view is
        # reported only to show that it misleads.
        category = self.report["categories"]["descriptor"]["response"]["qd"]
        self.assertEqual(category["response"], "unresolved")
        self.assertLess(abs(category["change_across_the_ladder"]), 0.01)

    def test_the_committed_category_block_agrees_with_the_module(self):
        # This block was written into the artifact after the sweep, so it has to
        # be reproducible from the per-goal results the sweep did record.
        self.assertEqual(
            self.report["categories"],
            e034.category_rows(self.traits, self.report["weight_targets"]),
        )
        self.assertEqual(self.report["category_order"], list(e034.CATEGORY_ORDER))

    # -- Result 4 ----------------------------------------------------------

    def test_where_the_lead_falls_the_archive_itself_falls_furthest(self):
        # E033's decay had qd flat while the baseline climbed. Not so here.
        for trait in ("simplicity", "efficiency"):
            with self.subTest(trait=trait):
                cells = self.traits[trait]["cells"]
                def mean_of(cell, key):
                    if key == "qd":
                        return statistics.fmean(g["means"]["qd"] for g in cell["goal_results"])
                    return statistics.fmean(
                        g["best_hypothesis_free_arm"] for g in cell["goal_results"]
                    )
                archive = mean_of(cells[-1], "qd") - mean_of(cells[0], "qd")
                baseline = mean_of(cells[-1], "ref") - mean_of(cells[0], "ref")
                self.assertLess(archive, 0)
                self.assertLess(archive, baseline)

    # -- Result 5 ----------------------------------------------------------

    def test_catastrophic_failure_sits_at_the_ends_of_the_ladders(self):
        rows = {
            trait: [c["mean_catastrophic_seeds"]["qd"] for c in report["cells"]]
            for trait, report in self.traits.items()
        }
        # The floored traits break when the goal stops valuing them...
        for trait in ("reliability", "security"):
            with self.subTest(trait=trait):
                self.assertGreater(rows[trait][0], 4.0)
                self.assertEqual(rows[trait][-1], 0.0)
        # ...and the control trait breaks hardest at the other end.
        self.assertEqual(rows["simplicity"][0], 0.0)
        self.assertAlmostEqual(rows["simplicity"][-1], 12.25, places=2)
        for trait in ("reliability", "security"):
            self.assertGreater(rows["simplicity"][-1] / rows[trait][0], 1.9)

    # -- Result 6 ----------------------------------------------------------

    def test_e033s_security_observation_does_not_survive_holding_the_distance(self):
        cell = self.traits["security"]["cells"][0]
        self.assertAlmostEqual(cell["target_weight"], 0.02, places=6)
        self.assertGreater(cell["qd"]["lead_mean"], 0)
        # E033's post-hoc point estimate was -1.362; this interval excludes it.
        self.assertGreater(cell["qd"]["ci95_low"], -1.362)

    def test_weight_on_the_floored_pair_is_not_a_sufficient_statistic(self):
        # It correlates with the lead, but the adaptability ladder falls in
        # floored weight while its lead rises -- so it cannot be the mechanism.
        cells = self.traits["adaptability"]["cells"]

        def floored_weight(cell):
            return statistics.fmean(
                g["goal"][0] + g["goal"][4] for g in cell["goal_results"]
            )

        self.assertLess(floored_weight(cells[-1]), floored_weight(cells[0]))
        self.assertGreater(self._change("adaptability")[0], 0)

    # -- the write-up itself -----------------------------------------------

    def test_the_write_up_tables_match_the_artifact(self):
        def numeric(text):
            match = re.fullmatch(r"`([+-]?\d+\.?\d*)`", text.strip())
            return float(match.group(1)) if match else None

        def table_rows(section, end, width):
            body = self.doc.split(section, 1)[1].split(end, 1)[0]
            for line in body.splitlines():
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) == width and cells[0].strip("`") in self.traits:
                    yield cells

        checked = set()
        for cells in table_rows("## Result 2", "## Result 3", 8):
            trait = cells[0].strip("`")
            checked.add(trait)
            response = self.traits[trait]["response"]["qd"]
            with self.subTest(table="ladders", trait=trait):
                self.assertEqual(cells[1], self.report["trait_categories"][trait])
                self.assertAlmostEqual(
                    numeric(cells[2]), response["lead_at_lowest_weight"], places=3
                )
                self.assertAlmostEqual(
                    numeric(cells[3]), response["lead_at_highest_weight"], places=3
                )
                self.assertEqual(cells[7].strip("* "), response["response"])
        self.assertEqual(checked, set(self.traits))

        checked = set()
        for cells in table_rows("## Result 5", "## Result 6", 6):
            trait = cells[0].strip("`")
            checked.add(trait)
            cells_ = self.traits[trait]["cells"]
            with self.subTest(table="catastrophe", trait=trait):
                for index, text in enumerate(cells[1:]):
                    self.assertAlmostEqual(
                        numeric(text),
                        cells_[index]["mean_catastrophic_seeds"]["qd"],
                        places=2,
                    )
        self.assertEqual(checked, set(self.traits))

    def test_the_write_up_records_the_falsification_rather_than_burying_it(self):
        self.assertIn("falsified", self.doc)
        for fragment in ("9.365", "24.2", "38,643", "Bonferroni", "0.391918"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.doc)
