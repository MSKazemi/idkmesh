"""Fast tests for E050: agent churn at a matched proposal-plus-verification budget.

The properties worth pinning are the ones a reader could silently get wrong:

1. ``f = 0`` is E024 -- every arm's row, trace included, equals the row
   ``matched_budget_emergence.run_seed`` produces, so the churn arms extend E024
   instead of resembling it;
2. what "fresh" means is fixed per arm: under the ``memory`` model only the
   majority swarm has anything to lose, and under ``cold-start`` a fresh agent
   proposes blind while the shared state survives;
3. the churn schedule has a stated size, is deterministic, and draws nothing at
   ``f = 0``;
4. the paired tests and the sign-change rule have fixed, stated directions.

A tiny configuration keeps the module far below the unit tier's CPU budget. The
test that re-derives the committed 100-seed artifact is in
``test_e050_committed_artifact.py`` and runs nightly.
"""

from __future__ import annotations

import random
import unittest

import sim.e050_churn as e050
import sim.matched_budget_emergence as mbe

sim = mbe.sim

AGENTS, GENERATIONS, CHANGE_AT, BINS = 12, 6, 3, 4


_RUNS = {}


def _run(seed, churn, verification=None):
    """Cached: every test below only reads a run, and the arms are deterministic."""
    key = (seed, churn, verification)
    if key not in _RUNS:
        _RUNS[key] = e050.run_churn_seed(
            seed, AGENTS, GENERATIONS, CHANGE_AT, BINS, churn, verification
        )
    return _RUNS[key]


def _e024(seed, verification=None):
    payload = mbe.run_seed(seed, AGENTS, GENERATIONS, CHANGE_AT, BINS, verification)
    return {row["strategy"]: row for row in payload["results"]}


def _walk(value, key):
    """Count how many times ``key`` appears anywhere in a nested report."""
    if isinstance(value, dict):
        return sum((1 if k == key else 0) + _walk(v, key) for k, v in value.items())
    if isinstance(value, list):
        return sum(_walk(v, key) for v in value)
    return 0


class ZeroChurnIsE024Tests(unittest.TestCase):
    def test_every_arm_row_equals_the_e024_row(self):
        for seed in (0, 1):
            self.assertEqual(_run(seed, e050.Churn(0.0)), _e024(seed), seed)

    def test_zero_churn_is_the_same_under_both_models(self):
        self.assertEqual(
            _run(2, e050.Churn(0.0, e050.MEMORY)), _run(2, e050.Churn(0.0, e050.COLD_START))
        )

    def test_equality_also_holds_under_an_imperfect_panel(self):
        panel = mbe.measured_panel()
        self.assertEqual(_run(3, e050.Churn(0.0), panel), _e024(3, panel))

    def test_the_budget_is_matched_at_every_fraction_and_model(self):
        for model in e050.MODELS:
            for fraction in (0.25, 1.0):
                rows = _run(4, e050.Churn(fraction, model))
                for strategy, row in rows.items():
                    self.assertEqual(
                        row["verification_attempts"], AGENTS * GENERATIONS, (model, fraction, strategy)
                    )

    def test_a_run_leaves_e024s_shared_code_alone(self):
        before = dict(mbe.RUNNERS)
        _run(0, e050.Churn(0.5, e050.COLD_START))
        self.assertEqual(mbe.RUNNERS, before)
        self.assertIsNot(e050.RUNNERS, mbe.RUNNERS)
        self.assertEqual(mbe.STRATEGIES, e050.STRATEGIES)

    def test_runs_are_deterministic(self):
        churn = e050.Churn(0.25, e050.COLD_START)
        self.assertEqual(_run(5, churn), _run(5, churn))


class ChurnScheduleTests(unittest.TestCase):
    def test_count_is_floor_of_f_times_agents_plus_a_half(self):
        expected = {0.0: 0, 0.1: 5, 0.25: 13, 0.5: 25, 1.0: 50}
        for fraction, count in expected.items():
            self.assertEqual(e050.Churn(fraction).count(50), count, fraction)

    def test_invalid_settings_are_rejected(self):
        for kwargs in ({"fraction": -0.1}, {"fraction": 1.1}, {"model": "retire"}):
            with self.assertRaises(ValueError):
                e050.Churn(**kwargs)

    def test_generation_zero_replaces_nobody(self):
        rng = random.Random(1)
        self.assertEqual(e050.Churn(1.0).fresh_slots(rng, 8, 0), [])

    def test_zero_fraction_draws_nothing_from_the_churn_stream(self):
        rng = random.Random(7)
        state = rng.getstate()
        for generation in range(5):
            self.assertEqual(e050.Churn(0.0).fresh_slots(rng, 8, generation), [])
        self.assertEqual(rng.getstate(), state)

    def test_slots_are_distinct_sorted_and_in_range(self):
        rng = random.Random(3)
        for generation in range(1, 6):
            slots = e050.Churn(0.5).fresh_slots(rng, 10, generation)
            self.assertEqual(len(slots), 5)
            self.assertEqual(slots, sorted(set(slots)))
            self.assertTrue(all(0 <= slot < 10 for slot in slots))

    def test_full_churn_replaces_every_slot(self):
        self.assertEqual(e050.Churn(1.0).fresh_slots(random.Random(0), 6, 1), list(range(6)))

    def test_the_schedule_is_deterministic_for_a_seed(self):
        first = [e050.Churn(0.25).fresh_slots(random.Random(9), 20, g) for g in (1, 2, 3)]
        second = [e050.Churn(0.25).fresh_slots(random.Random(9), 20, g) for g in (1, 2, 3)]
        self.assertEqual(first, second)


class FreshAgentDefinitionTests(unittest.TestCase):
    def test_redraw_changes_only_the_fresh_slots_and_stays_in_the_plausible_set(self):
        sentinel = (9.0, 9.0, 9.0, 9.0, 9.0)
        beliefs = [sentinel] * 6
        updated = e050.redraw_beliefs(beliefs, [1, 4], random.Random(0))
        self.assertEqual([i for i, b in enumerate(updated) if b != sentinel], [1, 4])
        for slot in (1, 4):
            self.assertIn(updated[slot], sim.PLAUSIBLE_GOALS)
        self.assertEqual(beliefs, [sentinel] * 6)  # the input is not mutated

    def test_cold_start_replaces_only_fresh_slots_with_blind_candidates(self):
        proposals = [sim.Candidate((0.5, 0.5, 0.5, 0.5, 0.5))] * 5
        updated = e050.cold_start_proposals(proposals, [0, 3], random.Random(0), e050.COLD_START)
        changed = [i for i, c in enumerate(updated) if c != proposals[i]]
        self.assertEqual(changed, [0, 3])

    def test_the_memory_model_never_replaces_a_proposal(self):
        proposals = [sim.Candidate((0.5, 0.5, 0.5, 0.5, 0.5))] * 5
        updated = e050.cold_start_proposals(proposals, [0, 1, 2], random.Random(0), e050.MEMORY)
        self.assertEqual(updated, proposals)

    def test_under_memory_churn_the_state_free_arms_are_unchanged(self):
        # random, scalar, qd and planner hold nothing private, so a fresh agent is
        # the old agent. Identity of the whole row, trace included.
        for seed in (0, 1, 2):
            base = _run(seed, e050.Churn(0.0))
            churned = _run(seed, e050.Churn(0.5, e050.MEMORY))
            for arm in e050.STATE_FREE_ARMS:
                self.assertEqual(churned[arm], base[arm], (seed, arm))

    def test_under_memory_churn_the_majority_swarm_is_the_arm_that_moves(self):
        moved = [
            _run(seed, e050.Churn(1.0, e050.MEMORY))["majority"]
            != _run(seed, e050.Churn(0.0))["majority"]
            for seed in range(6)
        ]
        self.assertTrue(any(moved))

    def test_random_search_is_unchanged_even_under_cold_start(self):
        for seed in (0, 1):
            self.assertEqual(
                _run(seed, e050.Churn(1.0, e050.COLD_START))["random"],
                _run(seed, e050.Churn(0.0))["random"],
            )

    def test_cold_start_moves_the_arms_that_keep_state_elsewhere(self):
        for arm in ("scalar", "qd", "planner", "majority"):
            moved = [
                _run(seed, e050.Churn(1.0, e050.COLD_START))[arm]
                != _run(seed, e050.Churn(0.0))[arm]
                for seed in range(4)
            ]
            self.assertTrue(any(moved), arm)


class StatisticsTests(unittest.TestCase):
    def test_the_catastrophe_cutoff_is_e024s_absolute_one(self):
        self.assertEqual(e050.catastrophe_threshold(50, 25), 16.0)
        self.assertEqual(
            e050.catastrophe_threshold(GENERATIONS, CHANGE_AT),
            mbe.CATASTROPHE_FRACTION * (GENERATIONS - CHANGE_AT),
        )
        self.assertTrue(e050.is_catastrophic(15.999, 16.0))
        self.assertFalse(e050.is_catastrophic(16.0, 16.0))

    def test_mcnemar_on_a_hand_built_table(self):
        first = [10, 10, 10, 20, 20]
        second = [20, 20, 10, 10, 20]
        result = e050.paired_catastrophe(first, second, 16.0)
        self.assertEqual(result["first_only_catastrophic"], 2)
        self.assertEqual(result["second_only_catastrophic"], 1)
        self.assertEqual(result["both_catastrophic"], 1)
        self.assertEqual(result["neither"], 1)
        self.assertEqual(result["p_value"], 1.0)

    def test_mcnemar_is_exact_and_two_sided_on_a_lopsided_table(self):
        result = e050.paired_catastrophe([10.0] * 8, [20.0] * 8, 16.0)
        self.assertEqual((result["first_only_catastrophic"], result["second_only_catastrophic"]), (8, 0))
        self.assertAlmostEqual(result["p_value"], 2 * 0.5**8, places=9)
        flipped = e050.paired_catastrophe([20.0] * 8, [10.0] * 8, 16.0)
        self.assertEqual(flipped["p_value"], result["p_value"])

    def test_the_paired_difference_has_a_fixed_direction(self):
        result = e050.paired_difference([3.0, 4.0, 5.0, 5.0], [1.0, 1.0, 6.0, 5.0], "t", 20)
        self.assertEqual(
            (result["first_higher"], result["second_higher"], result["ties"]), (2, 1, 1)
        )
        self.assertEqual(result["mean_difference"]["mean"], 1.0)

    def test_sign_change_is_bracketed_never_interpolated(self):
        change = e050.first_sign_change({0.0: 3.0, 0.5: -1.0, 0.1: 2.0, 0.25: -0.5})
        self.assertEqual(change["first_sign_change_fraction"], 0.25)
        self.assertEqual(change["bracket"], [0.1, 0.25])
        self.assertEqual(change["reference_sign"], 1)

    def test_no_sign_change_is_reported_as_none(self):
        change = e050.first_sign_change({0.0: 3.0, 0.1: 2.0, 0.5: 0.1})
        self.assertIsNone(change["first_sign_change_fraction"])
        self.assertIsNone(change["bracket"])

    def test_a_negative_lead_that_turns_positive_is_also_a_change(self):
        change = e050.first_sign_change({0.0: -2.0, 0.1: -1.0, 0.5: 0.3})
        self.assertEqual(change["first_sign_change_fraction"], 0.5)

    def test_the_comparison_count_formula(self):
        counts = e050.comparison_count(e050.MODELS, e050.FRACTIONS)
        self.assertEqual(counts, {"lead_vs_archive": 72, "own_effect_vs_no_churn": 80, "total": 152})

    def test_a_tiny_report_contains_exactly_the_counted_p_values(self):
        fractions = (0.0, 0.5)
        report = e050.measure(
            seeds=2, agents=AGENTS, generations=GENERATIONS, change_at=CHANGE_AT, bins=BINS,
            fractions=fractions, resamples=10,
        )
        counted = e050.comparison_count(e050.MODELS, fractions)["total"]
        # The f = 0 cell is printed under both models but is one set of tests.
        lead = report["paired_against_archive"]
        listed = _walk(lead, "p_value") - _walk(lead[e050.COLD_START]["0"], "p_value")
        listed += _walk(report["own_effect_of_churn"], "p_value")
        self.assertEqual(listed, counted)
        self.assertEqual(lead[e050.MEMORY]["0"], lead[e050.COLD_START]["0"])
        self.assertEqual(report["multiple_comparisons"]["p_values_reported"]["total"], counted)
        self.assertTrue(
            all(report["reference_check"]["memory_model_arm_rows_identical_to_no_churn"][arm]["0.5"]
                for arm in e050.STATE_FREE_ARMS)
        )


if __name__ == "__main__":
    unittest.main()
