"""Tests for E033: how the archive's lead decays with distance from the box.

E030 measured the archive's rescue at one substitute goal. E033 turns that one
point into a ladder, so the tests here have to pin three things that a ladder
can get wrong and a single point cannot:

1. the axis is what it claims -- distance to the *nearest* supplied hypothesis,
   with E030's published substitute landing on its own published ring;
2. the matched ladder really is matched, so a decline along it cannot be the
   change simply getting bigger;
3. the shape label is arithmetic on the intervals, not a reading of the plot.

The ladder is only comparable to E030's finding if it reproduces it, so the
anchors are checked against E030's committed artifact rather than against a
recomputation of E030.
"""

from __future__ import annotations

import json
import math
import os
import random
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e030_supplied_goal_membership as e030
import sim.e033_goal_distance as e033

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _ring(distance, mean_lead, half):
    return {
        "target_distance_to_supplied": distance,
        "lead_mean": mean_lead,
        "ci95_low": mean_lead - half,
        "ci95_high": mean_lead + half,
    }


class GeometryTest(unittest.TestCase):
    def test_a_supplied_member_sits_at_zero(self):
        for goal in sim.PLAUSIBLE_GOALS:
            self.assertEqual(e033.distance_to_supplied(goal), 0.0)

    def test_the_distance_to_the_set_never_exceeds_the_change_size(self):
        # INITIAL_GOAL is a member, so the nearest member is at worst as far as
        # it is. This is why the matched ladder cannot reach 0.40.
        rng = random.Random(3313)
        for _ in range(400):
            raw = [rng.expovariate(1.0) for _ in range(len(sim.INITIAL_GOAL))]
            total = sum(raw)
            goal = tuple(value / total for value in raw)
            self.assertLessEqual(
                e033.distance_to_supplied(goal),
                e033.distance_from_initial(goal) + 1e-12,
            )

    def test_the_e030_substitute_sits_on_its_own_published_ring(self):
        self.assertAlmostEqual(
            e033.distance_to_supplied(e030.UNHELD_GOAL),
            e033.E030_SUBSTITUTE_RING,
            places=6,
        )

    def test_the_matched_change_size_is_the_substitutes_own_change_size(self):
        self.assertAlmostEqual(
            e033.distance_from_initial(e030.UNHELD_GOAL),
            e033.MATCHED_CHANGE_SIZE,
            places=6,
        )

    def test_the_published_ring_is_a_rung_of_the_matched_ladder(self):
        self.assertIn(e033.E030_SUBSTITUTE_RING, e033.MATCHED_RINGS)

    def test_the_pool_is_on_the_simplex(self):
        pool = e033.simplex_pool(draws=500, seed=11)
        for goal in pool:
            self.assertAlmostEqual(sum(goal), 1.0, places=9)
            self.assertTrue(all(weight >= 0.0 for weight in goal))
            self.assertEqual(len(goal), len(sim.INITIAL_GOAL))

    def test_the_pool_is_deterministic(self):
        self.assertEqual(
            e033.simplex_pool(draws=200, seed=5), e033.simplex_pool(draws=200, seed=5)
        )

    def test_a_different_pool_seed_gives_a_different_pool(self):
        self.assertNotEqual(
            e033.simplex_pool(draws=200, seed=5), e033.simplex_pool(draws=200, seed=6)
        )


class LadderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = e033.simplex_pool(draws=60_000, seed=e033.POOL_SEED)

    def test_every_ring_lands_within_tolerance_of_its_target(self):
        for name in e033.LADDERS:
            for rung in e033.ladder(name, pool=self.pool, count=3):
                target = rung["target_distance_to_supplied"]
                for entry in rung["goals"]:
                    with self.subTest(ladder=name, target=target):
                        self.assertLessEqual(
                            abs(entry["distance_to_supplied"] - target),
                            e033.RING_TOLERANCE + 1e-9,
                        )

    def test_the_matched_ladder_holds_the_change_size_in_every_ring(self):
        for rung in e033.ladder("matched", pool=self.pool, count=3):
            for entry in rung["goals"]:
                with self.subTest(target=rung["target_distance_to_supplied"]):
                    self.assertLessEqual(
                        abs(entry["distance_from_initial"] - e033.MATCHED_CHANGE_SIZE),
                        e033.RING_TOLERANCE + 1e-9,
                    )

    def test_the_free_ladder_does_not_hold_the_change_size(self):
        # If it did, the two ladders would be the same experiment run twice.
        spread = [
            entry["distance_from_initial"]
            for rung in e033.ladder("free", pool=self.pool, count=3)
            for entry in rung["goals"]
        ]
        self.assertGreater(max(spread) - min(spread), 2 * e033.RING_TOLERANCE)

    def test_no_ring_goal_is_a_supplied_member(self):
        for name in e033.LADDERS:
            for rung in e033.ladder(name, pool=self.pool, count=3):
                for entry in rung["goals"]:
                    with self.subTest(ladder=name):
                        self.assertFalse(entry["is_supplied_member"])

    def test_a_rings_goals_are_distinct(self):
        for rung in e033.ladder("free", pool=self.pool, count=4):
            goals = [tuple(entry["goal"]) for entry in rung["goals"]]
            self.assertEqual(len(set(goals)), len(goals))

    def test_ring_goals_are_deterministic(self):
        first = e033.ring_goals(self.pool, ring=0.25, matched=False, count=4)
        second = e033.ring_goals(self.pool, ring=0.25, matched=False, count=4)
        self.assertEqual(first, second)

    def test_selection_spreads_further_than_taking_the_band_in_pool_order(self):
        # Farthest-point selection has to earn its complexity: it must beat the
        # naive "first four that qualify", or a ring is one direction sampled
        # four times.
        band = e033.admissible(self.pool, ring=0.25, matched=False)
        naive = band[:4]
        chosen = e033.ring_goals(self.pool, ring=0.25, matched=False, count=4)

        def closest(goals):
            return min(
                math.dist(a, b)
                for i, a in enumerate(goals)
                for b in goals[i + 1 :]
            )

        self.assertGreater(closest(chosen), closest(naive))

    def test_an_infeasible_matched_ring_raises(self):
        # 0.60 from the set while 0.392 from the initial goal is geometrically
        # impossible, and must fail loudly rather than return a thin sample.
        with self.assertRaises(ValueError):
            e033.ring_goals(self.pool, ring=0.60, matched=True, count=3)

    def test_an_unknown_ladder_raises(self):
        with self.assertRaises(ValueError):
            e033.ladder("diagonal", pool=self.pool, count=2)


class LeadTableTest(unittest.TestCase):
    def _values(self, **overrides):
        base = {arm: [10.0] * 4 for arm in mbe.STRATEGIES}
        base.update(overrides)
        return base

    def test_the_arm_partition_matches_e030s_committed_artifact(self):
        cell = _load("E030-supplied-goal-membership.json")["cells"][0]["advantage"]
        self.assertEqual(list(e033.HYPOTHESIS_FREE), cell["hypothesis_free_arms"])
        self.assertEqual(list(e033.HYPOTHESIS_HOLDING), cell["hypothesis_holding_arms"])

    def test_every_arm_is_in_exactly_one_half_of_the_partition(self):
        self.assertEqual(
            sorted(e033.HYPOTHESIS_FREE + e033.HYPOTHESIS_HOLDING),
            sorted(mbe.STRATEGIES),
        )

    def test_the_lead_is_measured_against_the_best_hypothesis_free_arm(self):
        table = e033.lead_table(
            self._values(random=[12.0] * 4, scalar=[9.0] * 4, qd=[15.0] * 4), 16.0
        )
        self.assertEqual(table["reference_arm"], "random")
        self.assertEqual(table["best_hypothesis_free_arm"], 12.0)
        self.assertEqual(table["lead_over_hypothesis_free"]["qd"], 3.0)

    def test_the_reference_arm_can_change_and_is_named_when_it_does(self):
        table = e033.lead_table(
            self._values(random=[5.0] * 4, planner=[13.0] * 4, qd=[15.0] * 4), 16.0
        )
        self.assertEqual(table["reference_arm"], "planner")
        self.assertEqual(table["lead_over_hypothesis_free"]["qd"], 2.0)

    def test_a_lead_can_be_negative(self):
        table = e033.lead_table(
            self._values(random=[20.0] * 4, majority=[15.0] * 4), 16.0
        )
        self.assertEqual(table["lead_over_hypothesis_free"]["majority"], -5.0)

    def test_catastrophic_seeds_count_strictly_below_the_threshold(self):
        table = e033.lead_table(self._values(qd=[15.9, 16.0, 16.1, 0.0]), 16.0)
        self.assertEqual(table["catastrophic_seeds"]["qd"], 2)

    def test_only_hypothesis_holding_arms_get_a_lead(self):
        table = e033.lead_table(self._values(), 16.0)
        self.assertEqual(
            sorted(table["lead_over_hypothesis_free"]), sorted(e033.HYPOTHESIS_HOLDING)
        )


class PanelTest(unittest.TestCase):
    def test_the_perfect_panel_is_none_rather_than_a_default_config(self):
        # Not interchangeable: `None` skips the verifier draw, so passing a
        # default VerificationConfig would consume a different rng stream and
        # the anchors would stop reproducing E030.
        self.assertIsNone(e033._panel("perfect"))

    def test_named_panels_come_from_e027(self):
        for name in ("independent", "measured", "stress"):
            with self.subTest(panel=name):
                self.assertIs(e033._panel(name), e027.PANELS[name])

    def test_an_unknown_panel_raises(self):
        with self.assertRaises(ValueError):
            e033._panel("optimistic")


class RingStatisticTest(unittest.TestCase):
    def _results(self, leads):
        return [{"lead_over_hypothesis_free": {"qd": lead}} for lead in leads]

    def test_the_mean_and_range_describe_the_goals_in_the_ring(self):
        stat = e033._ring_statistic(self._results([1.0, 2.0, 3.0]), "qd")
        self.assertEqual(stat["goals"], 3)
        self.assertEqual(stat["lead_mean"], 2.0)
        self.assertEqual(stat["lead_min"], 1.0)
        self.assertEqual(stat["lead_max"], 3.0)

    def test_the_interval_widens_with_the_spread_across_goals(self):
        tight = e033._ring_statistic(self._results([2.0, 2.0, 2.0]), "qd")
        loose = e033._ring_statistic(self._results([0.0, 2.0, 4.0]), "qd")
        self.assertEqual(tight["ci95_high"] - tight["ci95_low"], 0.0)
        self.assertGreater(loose["ci95_high"] - loose["ci95_low"], 0.0)

    def test_one_goal_gives_a_zero_width_interval_rather_than_an_error(self):
        stat = e033._ring_statistic(self._results([3.0]), "qd")
        self.assertEqual(stat["ci95_low"], stat["ci95_high"])

    def test_the_t_quantile_shrinks_with_more_goals(self):
        self.assertGreater(e033._t95(1), e033._t95(5))
        self.assertGreater(e033._t95(5), e033._t95(30))

    def test_the_t_quantile_falls_back_to_the_normal_beyond_the_table(self):
        self.assertEqual(e033._t95(400), 1.96)

    def test_a_t_quantile_needs_at_least_two_observations(self):
        with self.assertRaises(ValueError):
            e033._t95(0)


class ClassifyDecayTest(unittest.TestCase):
    def test_a_lead_that_does_not_move_is_flat(self):
        rings = [_ring(d, 3.4, 0.5) for d in (0.05, 0.15, 0.25, 0.35)]
        report = e033.classify_decay(rings)
        self.assertEqual(report["shape"], "flat")
        self.assertTrue(report["could_resolve_a_decline_the_size_of_the_lead"])

    def test_a_ladder_too_noisy_to_see_anything_is_unresolved_not_flat(self):
        # The two must not share a word. Here the lead falls by 4.2 and the
        # ladder simply cannot tell -- reporting that as "flat" would turn an
        # absence of evidence into evidence of absence.
        rings = [
            _ring(0.05, 0.05, 0.29),
            _ring(0.20, -1.00, 2.00),
            _ring(0.35, -4.15, 3.98),
        ]
        report = e033.classify_decay(rings)
        self.assertGreater(report["total_decline"], 4.0)
        self.assertFalse(report["could_resolve_a_decline_the_size_of_the_lead"])
        self.assertEqual(report["shape"], "unresolved")

    def test_one_dominant_resolved_step_is_a_cliff(self):
        rings = [
            _ring(0.05, 3.4, 0.05),
            _ring(0.15, 3.35, 0.05),
            _ring(0.25, 0.30, 0.05),
            _ring(0.35, 0.25, 0.05),
        ]
        report = e033.classify_decay(rings)
        self.assertEqual(report["shape"], "cliff")
        self.assertGreaterEqual(report["largest_step_share"], e033.CLIFF_SHARE)

    def test_an_evenly_spread_resolved_decline_is_smooth(self):
        rings = [
            _ring(0.05, 4.0, 0.02),
            _ring(0.15, 3.0, 0.02),
            _ring(0.25, 2.0, 0.02),
            _ring(0.35, 1.0, 0.02),
        ]
        report = e033.classify_decay(rings)
        self.assertEqual(report["shape"], "smooth")
        self.assertAlmostEqual(report["largest_step_share"], report["uniform_share"], 6)

    def test_a_gradual_decline_is_smooth_even_when_no_single_step_resolves(self):
        # This is the canonical smooth case, and the reason "smooth" is defined
        # on the endpoints rather than on the steps: a decline can be perfectly
        # real and perfectly gradual while every individual rung overlaps its
        # neighbour.
        rings = [
            _ring(0.05, 4.0, 0.30),
            _ring(0.15, 3.5, 0.30),
            _ring(0.25, 3.0, 0.30),
            _ring(0.35, 2.5, 0.30),
        ]
        report = e033.classify_decay(rings)
        self.assertTrue(report["endpoints_separate"])
        self.assertEqual(report["resolved_declining_steps"], 0)
        self.assertLess(report["largest_step_share"], e033.CLIFF_SHARE)
        self.assertEqual(report["shape"], "smooth")

    def test_a_dominant_step_that_does_not_resolve_is_unresolved_not_a_cliff(self):
        # The whole decline sits in one step, but the two rings it spans have
        # intervals wide enough to overlap. The ladder cannot tell a cliff from
        # noise here, and must not claim one.
        rings = [
            _ring(0.05, 3.4, 0.05),
            _ring(0.15, 3.35, 2.0),
            _ring(0.25, 0.30, 2.0),
            _ring(0.35, 0.25, 0.05),
        ]
        report = e033.classify_decay(rings)
        self.assertTrue(report["endpoints_separate"])
        self.assertGreater(report["largest_step_share"], e033.CLIFF_SHARE)
        self.assertEqual(report["resolved_declining_steps"], 0)
        self.assertEqual(report["shape"], "unresolved")

    def test_a_rising_lead_is_not_reported_as_a_decline(self):
        rings = [
            _ring(0.05, 1.0, 0.02),
            _ring(0.15, 2.0, 0.02),
            _ring(0.25, 3.0, 0.02),
        ]
        report = e033.classify_decay(rings)
        self.assertLess(report["total_decline"], 0.0)
        self.assertEqual(report["largest_step_decline"], 0.0)

    def test_the_uniform_share_is_reported_so_the_threshold_can_be_judged(self):
        rings = [_ring(d, 3.0 - d, 0.01) for d in (0.05, 0.15, 0.25, 0.35)]
        self.assertAlmostEqual(e033.classify_decay(rings)["uniform_share"], 1 / 3, 6)

    def test_one_ring_cannot_be_classified(self):
        self.assertEqual(
            e033.classify_decay([_ring(0.05, 3.0, 0.1)])["shape"], "unresolved"
        )

    def test_every_step_is_reported_with_its_endpoints(self):
        rings = [_ring(d, 3.0, 0.1) for d in (0.05, 0.15, 0.25)]
        steps = e033.classify_decay(rings)["steps"]
        self.assertEqual(
            [(s["from_distance"], s["to_distance"]) for s in steps],
            [(0.05, 0.15), (0.15, 0.25)],
        )


class DriverEquivalenceTest(unittest.TestCase):
    SETTINGS = dict(
        seeds=3,
        seed_start=1,
        agents=16,
        generations=50,
        change_at=25,
        bins=8,
        panel="perfect",
    )

    def test_measure_goal_is_e030s_driver_with_a_lead_table_on_top(self):
        goal = e030.UNHELD_GOAL
        mine = e033.measure_goal({**self.SETTINGS, "goal": goal})
        theirs = e030.per_seed_auc(
            seeds=self.SETTINGS["seeds"],
            seed_start=self.SETTINGS["seed_start"],
            agents=self.SETTINGS["agents"],
            generations=self.SETTINGS["generations"],
            change_at=self.SETTINGS["change_at"],
            bins=self.SETTINGS["bins"],
            verification=None,
            goal=goal,
        )
        expected = e033.lead_table(theirs, 16.0)
        self.assertEqual(mine["means"], expected["means"])
        self.assertEqual(
            mine["lead_over_hypothesis_free"], expected["lead_over_hypothesis_free"]
        )

    def test_the_future_goal_is_restored_after_a_measurement(self):
        before = (sim.CHANGED_GOAL, e030._ARENA.CHANGED_GOAL)
        e033.measure_goal({**self.SETTINGS, "goal": (0.5, 0.2, 0.1, 0.1, 0.1)})
        self.assertEqual((sim.CHANGED_GOAL, e030._ARENA.CHANGED_GOAL), before)

    def test_worker_count_changes_speed_and_not_the_answer(self):
        jobs = [
            {**self.SETTINGS, "goal": e030.UNHELD_GOAL},
            {**self.SETTINGS, "goal": (0.5, 0.2, 0.1, 0.1, 0.1)},
        ]
        self.assertEqual(e033._run_jobs(jobs, 1), e033._run_jobs(jobs, 2))


class SweepShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = e033.sweep(
            "free",
            count=2,
            pool_draws=20_000,
            with_anchors=False,
            seeds=2,
            agents=16,
        )

    def test_the_rings_are_ordered_by_distance(self):
        distances = [
            ring["target_distance_to_supplied"] for ring in self.report["rings"]
        ]
        self.assertEqual(distances, sorted(distances))

    def test_every_ring_carries_its_goals_and_both_holding_arms(self):
        for ring in self.report["rings"]:
            with self.subTest(distance=ring["target_distance_to_supplied"]):
                self.assertEqual(len(ring["goal_results"]), 2)
                for arm in e033.HYPOTHESIS_HOLDING:
                    self.assertIn("lead_mean", ring[arm])

    def test_the_settings_that_produced_it_are_recorded(self):
        self.assertEqual(self.report["seeds"], 2)
        self.assertEqual(self.report["agents"], 16)
        self.assertEqual(self.report["panel"], "perfect")

    def test_a_decay_shape_is_reported_for_each_holding_arm(self):
        self.assertEqual(
            sorted(self.report["decay"]), sorted(e033.HYPOTHESIS_HOLDING)
        )

    def test_the_free_ladder_records_no_matched_change_size(self):
        self.assertIsNone(self.report["matched_change_size"])


class CliTest(unittest.TestCase):
    def test_the_ladder_choice_is_validated(self):
        with self.assertRaises(SystemExit):
            e033.parse_args(["--ladder", "spiral"])

    def test_defaults_are_the_published_settings(self):
        args = e033.parse_args([])
        self.assertEqual(args.ladder, "matched")
        self.assertEqual(args.goals_per_ring, e033.GOALS_PER_RING)
        self.assertEqual(args.jobs, 1)


class DiscriminabilityTest(unittest.TestCase):
    """The control that separates 'diversity stops helping' from 'nothing helps'."""

    @classmethod
    def setUpClass(cls):
        cls.candidates = [
            sim.Candidate(traits) for traits in e030._reference_pool(4000, 1)
        ]

    def test_headroom_is_the_ceiling_over_the_mean(self):
        report = e033.goal_discriminability(sim.CHANGED_GOAL, self.candidates)
        self.assertAlmostEqual(
            report["headroom"],
            report["attainable_ceiling"] - report["mean_over_viable"],
            places=5,
        )

    def test_a_goal_nobody_can_exploit_has_no_headroom(self):
        # Every candidate scores identically under a goal the utility cannot
        # see, so choosing well is worth nothing and headroom must be zero.
        flat = [sim.Candidate((0.5, 0.5, 0.5, 0.5, 0.5))] * 5
        report = e033.goal_discriminability(sim.CHANGED_GOAL, flat)
        self.assertEqual(report["headroom"], 0.0)
        self.assertEqual(report["spread_over_viable"], 0.0)

    def test_the_published_goals_are_scored_on_the_same_pool(self):
        report = e033.ladder_discriminability(
            "matched", count=2, pool_draws=20_000, draws=3000
        )
        self.assertEqual(
            sorted(report["published_goals"]), ["changed", "e030_substitute", "initial"]
        )
        self.assertEqual(len(report["rings"]), len(e033.MATCHED_RINGS))
        self.assertGreater(report["viable_pool"], 0)


class CommittedResultTest(unittest.TestCase):
    """Every claim the write-up makes, read back off the committed artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.matched = _load("E033-matched-change-size.json")
        cls.free = _load("E033-free-ring.json")
        cls.discrimination = _load("E033-discriminability-matched.json")
        cls.e030 = _load("E030-supplied-goal-membership.json")

    def test_both_ladders_reproduce_e030s_published_cell_exactly(self):
        cell = [c for c in self.e030["cells"] if c["panel"] == "perfect"][0]["advantage"]
        for report in (self.matched, self.free):
            for condition in ("held", "unheld"):
                with self.subTest(ladder=report["ladder"], condition=condition):
                    anchor = report["anchors"][condition]
                    self.assertEqual(anchor["means"], cell[condition]["means"])
                    self.assertEqual(
                        anchor["lead_over_hypothesis_free"],
                        cell[condition]["lead_over_hypothesis_free"],
                    )
                    self.assertEqual(
                        anchor["catastrophic_seeds"], cell[condition]["catastrophic_seeds"]
                    )

    def test_the_matched_ladder_really_holds_the_change_size(self):
        for ring in self.matched["rings"]:
            with self.subTest(distance=ring["target_distance_to_supplied"]):
                self.assertLess(
                    abs(ring["mean_distance_from_initial"] - e033.MATCHED_CHANGE_SIZE),
                    e033.RING_TOLERANCE,
                )

    def test_the_free_ladder_lets_the_change_size_grow_with_the_distance(self):
        # This is the confound the matched ladder exists to remove, so it has to
        # be visibly present in the ladder that does not control for it.
        rings = self.free["rings"]
        self.assertGreater(
            rings[-1]["mean_distance_from_initial"]
            - rings[0]["mean_distance_from_initial"],
            0.4,
        )

    def test_the_archives_lead_decays_smoothly_and_not_off_a_cliff(self):
        decay = self.matched["decay"]["qd"]
        self.assertEqual(decay["shape"], "smooth")
        self.assertTrue(decay["endpoints_separate"])
        self.assertLess(decay["largest_step_share"], e033.CLIFF_SHARE)

    def test_the_archives_lead_falls_monotonically_to_nearly_nothing(self):
        leads = [ring["qd"]["lead_mean"] for ring in self.matched["rings"]]
        self.assertEqual(leads, sorted(leads, reverse=True))
        self.assertGreater(leads[0], 3.4)
        self.assertLess(leads[-1], 0.5)

    def test_the_lead_vanishes_because_the_simple_arms_rise_not_because_the_archive_falls(self):
        rings = self.matched["rings"]

        def mean_of(ring, key):
            values = [result[key] for result in ring["goal_results"]]
            return sum(values) / len(values)

        def archive(ring):
            values = [result["means"]["qd"] for result in ring["goal_results"]]
            return sum(values) / len(values)

        self.assertLess(abs(archive(rings[-1]) - archive(rings[0])), 1.0)
        self.assertGreater(
            mean_of(rings[-1], "best_hypothesis_free_arm")
            - mean_of(rings[0], "best_hypothesis_free_arm"),
            2.5,
        )

    def test_distant_goals_are_more_discriminating_not_less(self):
        # The alternative explanation for a shrinking lead -- that out here
        # nothing helps anyone -- is false in the measured direction.
        rings = self.discrimination["rings"]
        self.assertGreater(rings[-1]["mean_headroom"], rings[0]["mean_headroom"])
        self.assertGreater(
            rings[-1]["mean_attainable_ceiling"], rings[0]["mean_attainable_ceiling"]
        )

    def test_e030s_substitute_is_a_favourable_draw_from_its_own_ring(self):
        ring = [
            r
            for r in self.matched["rings"]
            if r["target_distance_to_supplied"] == e033.E030_SUBSTITUTE_RING
        ][0]
        published = self.matched["anchors"]["unheld"]["lead_over_hypothesis_free"]["qd"]
        self.assertGreater(published, ring["qd"]["lead_mean"])
        self.assertGreater(published, ring["qd"]["lead_max"] * 0.7)

    def test_the_spread_across_goals_widens_with_distance(self):
        rings = self.matched["rings"]

        def span(ring):
            return ring["qd"]["lead_max"] - ring["qd"]["lead_min"]

        self.assertGreater(span(rings[-1]), 4 * span(rings[0]))

    def test_individual_goals_can_break_the_archive_outright(self):
        # Smooth in the ring mean is not safe per goal: at least one goal takes
        # the archive to a fully catastrophic 100/100.
        worst = max(
            result["catastrophic_seeds"]["qd"]
            for ring in self.matched["rings"]
            for result in ring["goal_results"]
        )
        self.assertEqual(worst, self.matched["seeds"])

    def test_the_uncontrolled_ladder_cannot_see_the_decay_at_all(self):
        # The methodological finding: sweeping distance without holding the
        # change size returns "unresolved" for the archive, which is why the
        # matched ladder is the one that answers the question.
        self.assertEqual(self.free["decay"]["qd"]["shape"], "unresolved")
        self.assertEqual(self.matched["decay"]["qd"]["shape"], "smooth")

    def test_the_consensus_swarm_never_recovers_a_lead_at_any_distance(self):
        for report in (self.matched, self.free):
            for ring in report["rings"]:
                with self.subTest(
                    ladder=report["ladder"],
                    distance=ring["target_distance_to_supplied"],
                ):
                    self.assertLess(ring["majority"]["lead_mean"], 0.1)

    def test_the_committed_shapes_agree_with_the_classifier(self):
        # The artifacts' labels are a pure function of their own ring statistics,
        # so a hand-edited shape has to fail here.
        for report in (self.matched, self.free):
            for arm in e033.HYPOTHESIS_HOLDING:
                with self.subTest(ladder=report["ladder"], arm=arm):
                    recomputed = e033.classify_decay(
                        [
                            {
                                "target_distance_to_supplied": ring[
                                    "target_distance_to_supplied"
                                ],
                                **ring[arm],
                            }
                            for ring in report["rings"]
                        ]
                    )
                    self.assertEqual(recomputed, report["decay"][arm])
