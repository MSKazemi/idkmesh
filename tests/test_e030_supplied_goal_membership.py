"""E030: does the archive's advantage survive losing the supplied answer?

E024 records its own sharpest limitation: the plausible goals are supplied by
the experimenter, and the supplied set *contains* the goal the environment later
switches to. The quality-diversity arm averages its robust quality over that
set and the majority-vote swarm draws each agent's belief from it, so both are
handed the future while `random`, `scalar` and `planner` are not.

E030 changes exactly one bit -- membership -- by leaving the goal set
byte-identical and moving where the environment actually goes.

The dangerous failure is a manipulation that changes more than one thing. Two
ways it could: touching `PLAUSIBLE_GOALS` (which would also change how many
hypotheses an arm holds, not just whether one is right), or reaching only one of
the two module objects that own `CHANGED_GOAL` -- `sim/matched_budget_emergence`
loads `emergence_sim.py` a second time by file path, so a run would then score
its arms against one goal and switch the environment to another. These tests
pin, in order:

1. the substitute goal is admissible and genuinely not a member;
2. the swap reaches every module that owns a copy, and touches nothing else;
3. the swap is fully reversed, including when the block raises and when nested;
4. the `held` condition is the unmodified E024/E026 harness, so the control
   column is a real control;
5. the reported statistic is arithmetic on the paired values, not a story;
6. the committed matrix says what the write-up says it says.

Recomputed sweeps are never compared byte-for-byte: the simulators go through
`exp` and `**`, whose last-place rounding differs across CPUs and C libraries.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sim.e027_defect_propagation as e027
import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
from sim.e030_supplied_goal_membership import (
    CONDITIONS,
    DEFAULT_CHANGE_AT,
    DEFAULT_GENERATIONS,
    EXPERIMENT_ID,
    PANEL_ORDER,
    PANELS,
    UNHELD_GOAL,
    _advantage_table,
    _catastrophe_threshold,
    _dispersion,
    _goal_for,
    _rank,
    _reference_pool,
    _resolve_panels,
    evolved_initial_transfer,
    future_goal,
    goal_difficulty,
    goal_parity,
    matrix,
    paired_sweep,
    per_seed_auc,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = "sim/e030_supplied_goal_membership.py"
MATRIX_RESULT = REPO_ROOT / "experiments/results/E030-supplied-goal-membership.json"
PARITY_RESULT = REPO_ROOT / "experiments/results/E030-goal-parity.json"

# The file-loaded second copy of the landscape. If this ever stops being a
# distinct object the swap becomes trivially safe and several tests below
# become vacuous, so it is asserted rather than assumed.
ARENA = mbe.sim


class SubstituteGoalTest(unittest.TestCase):
    """The substitute has to be a legal goal on this simplex, and unheld."""

    def test_the_substitute_is_not_one_of_the_supplied_hypotheses(self) -> None:
        self.assertNotIn(UNHELD_GOAL, sim.PLAUSIBLE_GOALS)

    def test_the_published_future_goal_is_one_of_them(self) -> None:
        # This is the confound E030 exists to remove; if it ever stopped being
        # true the experiment would have no manipulation left to make.
        self.assertIn(sim.CHANGED_GOAL, sim.PLAUSIBLE_GOALS)

    def test_the_substitute_is_a_weight_vector(self) -> None:
        self.assertAlmostEqual(sum(UNHELD_GOAL), 1.0, places=9)
        self.assertEqual(len(UNHELD_GOAL), len(sim.CHANGED_GOAL))
        for weight in UNHELD_GOAL:
            self.assertGreater(weight, 0.0)
            self.assertLess(weight, 1.0)

    def test_the_substitute_is_not_the_published_goal_in_disguise(self) -> None:
        # It must sit at least as far from the held goal as the supplied set's
        # own members sit from each other, or "unheld" would be a technicality.
        separation = math.dist(sim.CHANGED_GOAL, UNHELD_GOAL)
        self.assertGreaterEqual(separation, _dispersion(sim.PLAUSIBLE_GOALS) / 2)


class GoalParityTest(unittest.TestCase):
    """Parity is measured and reported, so these check the measurement."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parity = goal_parity()

    def test_membership_flags_match_the_goal_set(self) -> None:
        self.assertTrue(self.parity["held_goal_is_a_member"])
        self.assertFalse(self.parity["unheld_goal_is_a_member"])
        self.assertTrue(self.parity["unheld_goal_sums_to_one"])

    def test_change_size_is_matched(self) -> None:
        held = self.parity["distance_from_initial"]["held"]
        unheld = self.parity["distance_from_initial"]["unheld"]
        self.assertAlmostEqual(held, math.dist(sim.INITIAL_GOAL, sim.CHANGED_GOAL), places=5)
        self.assertAlmostEqual(unheld, math.dist(sim.INITIAL_GOAL, UNHELD_GOAL), places=5)
        # Within 10%: the environment must move about as far in both conditions,
        # or a difference in outcome is just a difference in shock size.
        self.assertLess(abs(unheld - held) / held, 0.10)

    def test_isolation_from_the_supplied_set_is_matched(self) -> None:
        nearest = self.parity["distance_to_nearest_held_hypothesis"]
        held, unheld = nearest["held_excluding_itself"], nearest["unheld"]
        self.assertLess(abs(unheld - held) / held, 0.10)

    def test_the_held_goal_is_compared_excluding_itself(self) -> None:
        # A goal is 0.0 from itself; measuring that would make the held arm look
        # infinitely better informed for a reason that is pure bookkeeping.
        self.assertGreater(
            self.parity["distance_to_nearest_held_hypothesis"]["held_excluding_itself"], 0.0
        )

    def test_both_goals_reorder_the_traits(self) -> None:
        ranks = self.parity["trait_rank"]
        self.assertNotEqual(ranks["held"], ranks["initial"])
        self.assertNotEqual(ranks["unheld"], ranks["initial"])

    def test_the_recorded_rank_mismatch_is_real(self) -> None:
        # The write-up names this as a limitation rather than claiming parity.
        # If a future edit ever fixes it, this test fails and the limitation
        # must be removed from the record rather than quietly going stale.
        ranks = self.parity["trait_rank"]
        self.assertEqual(ranks["held"][0], ranks["unheld"][0])
        self.assertNotEqual(ranks["held"], ranks["unheld"])

    def test_rank_orders_by_descending_weight(self) -> None:
        self.assertEqual(_rank((0.1, 0.5, 0.4)), (1, 2, 0))
        self.assertEqual(_rank((0.5, 0.5, 0.0)), (0, 1, 2))

    def test_dispersion_is_the_mean_pairwise_distance(self) -> None:
        self.assertAlmostEqual(_dispersion([(0.0,), (1.0,), (3.0,)]), (1 + 3 + 2) / 3)

    def test_the_parity_report_is_serialisable(self) -> None:
        json.loads(json.dumps(self.parity))


class GoalDifficultyTest(unittest.TestCase):
    """Transfer regret is the parity that actually decides the outcome."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.difficulty = goal_difficulty(draws=20_000, seed=20260830)

    def test_the_reference_pool_is_deterministic_and_viable(self) -> None:
        first = _reference_pool(2_000, seed=7)
        second = _reference_pool(2_000, seed=7)
        self.assertEqual(first, second)
        self.assertTrue(first)
        for traits in first[:50]:
            self.assertTrue(sim.viable(sim.Candidate(traits)))

    def test_both_goals_are_reachable_and_the_ceiling_is_a_maximum(self) -> None:
        ceiling = self.difficulty["attainable_ceiling"]
        mean = self.difficulty["mean_over_viable"]
        for name in ("held", "unheld"):
            self.assertGreater(ceiling[name], mean[name])
            self.assertLessEqual(ceiling[name], 1.0)

    def test_transfer_regret_is_the_gap_below_the_ceiling(self) -> None:
        regret = self.difficulty["transfer_regret_from_initial_optimum"]
        for name in ("held", "unheld"):
            self.assertGreater(regret[name], 0.0)
            self.assertLess(regret[name], self.difficulty["attainable_ceiling"][name])

    def test_the_ceiling_is_draw_sensitive_so_parity_needs_the_full_pool(self) -> None:
        # Both quantities are argmax statistics over a sampled pool, so a small
        # pool understates them unevenly. This is why the parity claim is
        # checked against the committed 200k-draw artifact and not against the
        # cheap fixture above -- at 20k draws the two goals' transfer regret
        # differs by ~13%, which would read as a broken match that is not real.
        small = goal_difficulty(draws=2_000, seed=20260830)
        for name in ("held", "unheld"):
            self.assertLessEqual(
                small["attainable_ceiling"][name],
                self.difficulty["attainable_ceiling"][name] + 1e-9,
            )

    def test_the_residual_gap_on_evolved_artifacts_is_reported(self) -> None:
        # The pool argmax is not what a committed arm actually converges to, and
        # the two transfer differently. Reporting only the first would hide the
        # residual mismatch that the scalar and planner arms pay.
        evolved = self.difficulty["evolved_initial_elite_utility"]
        for key in ("seeds", "held", "unheld", "unheld_minus_held"):
            self.assertIn(key, evolved)
        self.assertAlmostEqual(
            evolved["unheld_minus_held"], evolved["unheld"] - evolved["held"], places=5
        )

    def test_the_evolved_transfer_measurement_is_deterministic(self) -> None:
        first = evolved_initial_transfer(seeds=3, agents=16, generations=4)
        second = evolved_initial_transfer(seeds=3, agents=16, generations=4)
        self.assertEqual(first, second)

    def test_the_difficulty_report_is_serialisable(self) -> None:
        json.loads(json.dumps(self.difficulty))


class FutureGoalSwapTest(unittest.TestCase):
    """The manipulation must be exactly one bit, everywhere, and reversible."""

    def test_the_arena_really_is_a_second_module_object(self) -> None:
        # If this fails the swap is trivially global and the tests below stop
        # proving anything -- which is the failure that would be invisible.
        self.assertIsNot(ARENA, sim)
        self.assertEqual(ARENA.__name__, sim.__name__.rsplit(".", 1)[-1])

    def test_the_swap_reaches_both_module_objects(self) -> None:
        with future_goal(UNHELD_GOAL):
            self.assertEqual(sim.CHANGED_GOAL, UNHELD_GOAL)
            self.assertEqual(ARENA.CHANGED_GOAL, UNHELD_GOAL)

    def test_the_supplied_goal_set_is_untouched(self) -> None:
        before = tuple(tuple(goal) for goal in sim.PLAUSIBLE_GOALS)
        arena_before = tuple(tuple(goal) for goal in ARENA.PLAUSIBLE_GOALS)
        with future_goal(UNHELD_GOAL):
            self.assertEqual(tuple(tuple(g) for g in sim.PLAUSIBLE_GOALS), before)
            self.assertEqual(tuple(tuple(g) for g in ARENA.PLAUSIBLE_GOALS), arena_before)
            # Same size, so no arm's hypothesis count changed either.
            self.assertEqual(len(sim.PLAUSIBLE_GOALS), len(before))
        self.assertEqual(tuple(tuple(g) for g in sim.PLAUSIBLE_GOALS), before)

    def test_the_initial_goal_is_untouched(self) -> None:
        before = sim.INITIAL_GOAL
        with future_goal(UNHELD_GOAL):
            self.assertEqual(sim.INITIAL_GOAL, before)
            self.assertEqual(ARENA.INITIAL_GOAL, before)

    def test_the_swap_is_reversed(self) -> None:
        before, arena_before = sim.CHANGED_GOAL, ARENA.CHANGED_GOAL
        with future_goal(UNHELD_GOAL):
            pass
        self.assertEqual(sim.CHANGED_GOAL, before)
        self.assertEqual(ARENA.CHANGED_GOAL, arena_before)

    def test_the_swap_is_reversed_when_the_block_raises(self) -> None:
        before, arena_before = sim.CHANGED_GOAL, ARENA.CHANGED_GOAL
        with self.assertRaises(RuntimeError):
            with future_goal(UNHELD_GOAL):
                raise RuntimeError("boom")
        self.assertEqual(sim.CHANGED_GOAL, before)
        self.assertEqual(ARENA.CHANGED_GOAL, arena_before)

    def test_nested_swaps_unwind_in_order(self) -> None:
        before = sim.CHANGED_GOAL
        other = (0.2, 0.2, 0.2, 0.2, 0.2)
        with future_goal(UNHELD_GOAL):
            with future_goal(other):
                self.assertEqual(sim.CHANGED_GOAL, other)
            self.assertEqual(sim.CHANGED_GOAL, UNHELD_GOAL)
        self.assertEqual(sim.CHANGED_GOAL, before)

    def test_the_swap_stores_a_tuple(self) -> None:
        with future_goal([0.2, 0.2, 0.2, 0.2, 0.2]) as goal:
            self.assertIsInstance(goal, tuple)
            self.assertIsInstance(sim.CHANGED_GOAL, tuple)

    def test_the_held_condition_swaps_in_the_published_goal(self) -> None:
        self.assertEqual(_goal_for("held"), sim.CHANGED_GOAL)
        self.assertEqual(_goal_for("unheld"), UNHELD_GOAL)

    def test_an_unknown_condition_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _goal_for("blind")


class HeldConditionIsTheControlTest(unittest.TestCase):
    """The control column has to be the unmodified E024/E026 harness."""

    KWARGS = dict(seeds=2, seed_start=1, agents=12, generations=8, change_at=4, bins=4)

    def test_the_held_condition_reproduces_the_unpatched_harness(self) -> None:
        patched = per_seed_auc(verification=None, goal=sim.CHANGED_GOAL, **self.KWARGS)
        direct = {arm: [] for arm in mbe.STRATEGIES}
        for offset in range(self.KWARGS["seeds"]):
            record = mbe.run_seed(
                seed=self.KWARGS["seed_start"] + offset,
                agents=self.KWARGS["agents"],
                generations=self.KWARGS["generations"],
                change_at=self.KWARGS["change_at"],
                bins=self.KWARGS["bins"],
            )
            for arm_result in record["results"]:
                direct[arm_result["strategy"]].append(arm_result["post_change_utility_auc"])
        self.assertEqual(patched, direct)

    def test_the_unheld_condition_actually_changes_the_outcome(self) -> None:
        # A no-op swap would pass every reversal test above and produce a
        # perfectly clean, perfectly meaningless matrix.
        held = per_seed_auc(verification=None, goal=sim.CHANGED_GOAL, **self.KWARGS)
        unheld = per_seed_auc(verification=None, goal=UNHELD_GOAL, **self.KWARGS)
        self.assertNotEqual(held, unheld)

    def test_a_paired_sweep_runs_the_same_seeds_in_both_conditions(self) -> None:
        paired = paired_sweep(verification=None, **self.KWARGS)
        self.assertEqual(sorted(paired), sorted(CONDITIONS))
        for condition in CONDITIONS:
            self.assertEqual(sorted(paired[condition]), sorted(mbe.STRATEGIES))
            for arm in mbe.STRATEGIES:
                self.assertEqual(len(paired[condition][arm]), self.KWARGS["seeds"])


class AdvantageTableTest(unittest.TestCase):
    """The reported statistic must be arithmetic on the paired values."""

    PAIRED = {
        "held": {
            "random": [10.0, 12.0], "scalar": [14.0, 16.0], "qd": [20.0, 22.0],
            "planner": [8.0, 10.0], "majority": [18.0, 18.0],
        },
        "unheld": {
            "random": [11.0, 13.0], "scalar": [10.0, 10.0], "qd": [21.0, 21.0],
            "planner": [6.0, 8.0], "majority": [13.0, 13.0],
        },
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.table = _advantage_table(cls.PAIRED, threshold=11.0)

    def test_the_lead_is_measured_against_the_best_hypothesis_free_arm(self) -> None:
        # held: scalar 15.0 beats random 11.0 and planner 9.0.
        self.assertEqual(self.table["held"]["best_hypothesis_free_arm"], 15.0)
        self.assertEqual(self.table["held"]["reference_arm"], "scalar")
        self.assertEqual(self.table["held"]["lead_over_hypothesis_free"]["qd"], 6.0)
        # unheld: scalar collapses to 10.0, so random 12.0 becomes the reference.
        self.assertEqual(self.table["unheld"]["best_hypothesis_free_arm"], 12.0)
        self.assertEqual(self.table["unheld"]["reference_arm"], "random")

    def test_the_reference_arm_is_named_not_only_valued(self) -> None:
        # A lead computed against scalar in one condition and random in the
        # other is not a comparison; naming the arm is what makes that visible.
        for condition in CONDITIONS:
            cell = self.table[condition]
            self.assertEqual(
                cell["means"][cell["reference_arm"]], cell["best_hypothesis_free_arm"]
            )
            self.assertIn(cell["reference_arm"], self.table["hypothesis_free_arms"])

    def test_the_lead_delta_is_the_difference_of_the_two_leads(self) -> None:
        for arm in self.table["hypothesis_holding_arms"]:
            self.assertAlmostEqual(
                self.table["lead_delta_unheld_minus_held"][arm],
                self.table["unheld"]["lead_over_hypothesis_free"][arm]
                - self.table["held"]["lead_over_hypothesis_free"][arm],
                places=6,
            )

    def test_the_mean_delta_is_the_difference_of_the_two_means(self) -> None:
        self.assertEqual(self.table["delta_unheld_minus_held"]["qd"], 0.0)
        self.assertEqual(self.table["delta_unheld_minus_held"]["majority"], -5.0)

    def test_catastrophic_seeds_count_strictly_below_the_threshold(self) -> None:
        self.assertEqual(self.table["held"]["catastrophic_seeds"]["random"], 1)
        self.assertEqual(self.table["held"]["catastrophic_seeds"]["qd"], 0)
        self.assertEqual(self.table["unheld"]["catastrophic_seeds"]["scalar"], 2)

    def test_paired_wins_compare_the_same_seed_in_both_conditions(self) -> None:
        wins = self.table["paired_seed_wins_unheld_over_held"]
        self.assertEqual(wins["random"], 2)   # 11>10 and 13>12
        self.assertEqual(wins["qd"], 1)       # 21>20 but 21<22
        self.assertEqual(wins["scalar"], 0)

    def test_the_two_arm_groups_partition_the_strategies(self) -> None:
        free = self.table["hypothesis_free_arms"]
        holding = self.table["hypothesis_holding_arms"]
        self.assertEqual(sorted(free + holding), sorted(mbe.STRATEGIES))
        self.assertEqual(set(free) & set(holding), set())

    def test_the_hypothesis_holding_arms_are_the_ones_that_read_the_goal_set(self) -> None:
        # This grouping is the whole experiment: if an arm that consults
        # PLAUSIBLE_GOALS were filed as hypothesis-free it would be both the
        # treatment and the baseline.
        source = (REPO_ROOT / "sim/matched_budget_emergence.py").read_text()
        self.assertEqual(
            sorted(self.table["hypothesis_holding_arms"]), ["majority", "qd"]
        )
        self.assertIn("PLAUSIBLE_GOALS", source)


class CatastropheThresholdTest(unittest.TestCase):
    def test_the_threshold_is_e024s_absolute_cutoff(self) -> None:
        threshold = _catastrophe_threshold(DEFAULT_GENERATIONS, DEFAULT_CHANGE_AT)
        self.assertAlmostEqual(threshold, 16.0, places=9)
        self.assertAlmostEqual(
            threshold, mbe.CATASTROPHE_FRACTION * (DEFAULT_GENERATIONS - DEFAULT_CHANGE_AT)
        )


class PanelReuseTest(unittest.TestCase):
    """The panels must be E027's, not a lookalike copy."""

    def test_the_panels_are_e027s_objects(self) -> None:
        self.assertIs(PANELS, e027.PANELS)
        self.assertIs(PANEL_ORDER, e027.PANEL_ORDER)

    def test_every_ordered_panel_exists(self) -> None:
        for name in PANEL_ORDER:
            self.assertIn(name, PANELS)

    def test_selecting_panels_preserves_the_canonical_order(self) -> None:
        chosen = list(PANEL_ORDER)[:2][::-1]
        _, order = _resolve_panels(chosen)
        self.assertEqual(list(order), list(PANEL_ORDER)[:2])

    def test_no_selection_means_every_panel(self) -> None:
        panels, order = _resolve_panels(None)
        self.assertEqual(list(order), list(PANEL_ORDER))
        self.assertEqual(sorted(panels), sorted(PANELS))

    def test_an_unknown_panel_is_rejected(self) -> None:
        with self.assertRaises((KeyError, ValueError, SystemExit)):
            _resolve_panels(["not-a-panel"])


class MatrixReportTest(unittest.TestCase):
    """A tiny matrix, for shape and serialisability only."""

    @classmethod
    def setUpClass(cls) -> None:
        name = PANEL_ORDER[0]
        cls.report = matrix(
            panels={name: PANELS[name]}, panel_order=[name],
            seeds=2, agents=12, generations=8, change_at=4, bins=4,
            difficulty_draws=2_000,
        )

    def test_the_report_carries_its_provenance(self) -> None:
        self.assertEqual(self.report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(self.report["metric"], "post_change_utility_auc")

    def test_the_report_carries_both_parity_controls(self) -> None:
        # The lead is unreadable without them, so they travel with the numbers
        # rather than living only in the write-up.
        self.assertIn("goal_parity", self.report)
        self.assertIn("goal_difficulty", self.report)

    def test_the_report_states_its_limitations(self) -> None:
        text = " ".join(self.report["limitations"]).lower()
        self.assertIn("defect channel is disarmed", text)
        self.assertIn("one point", text)

    def test_every_cell_has_both_conditions(self) -> None:
        for cell in self.report["cells"]:
            for condition in CONDITIONS:
                self.assertIn(condition, cell["advantage"])

    def test_the_report_is_serialisable(self) -> None:
        json.loads(json.dumps(self.report))

    def test_the_swap_is_reversed_after_a_whole_matrix(self) -> None:
        self.assertEqual(sim.CHANGED_GOAL, ARENA.CHANGED_GOAL)
        self.assertIn(sim.CHANGED_GOAL, sim.PLAUSIBLE_GOALS)


class CommittedResultTest(unittest.TestCase):
    """The committed artifact must say what the write-up says it says."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(MATRIX_RESULT.read_text())
        cls.cells = {cell["panel"]: cell["advantage"] for cell in cls.report["cells"]}

    def test_the_committed_matrix_is_the_published_configuration(self) -> None:
        self.assertEqual(self.report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(self.report["seeds"], 100)
        self.assertEqual(self.report["generations"], 50)
        self.assertEqual(self.report["change_at"], 25)
        self.assertAlmostEqual(self.report["catastrophe_utility_auc_threshold"], 16.0)
        self.assertEqual(sorted(self.cells), sorted(PANEL_ORDER))

    def test_the_reference_arm_never_switches(self) -> None:
        # If it did, the lead in one condition would be measured against a
        # different arm than in the other and the delta would be meaningless.
        for panel, cell in self.cells.items():
            for condition in CONDITIONS:
                self.assertEqual(
                    cell[condition]["reference_arm"], "random", msg=f"{panel}/{condition}"
                )

    def test_the_archive_keeps_almost_all_of_its_lead(self) -> None:
        for panel, cell in self.cells.items():
            held = cell["held"]["lead_over_hypothesis_free"]["qd"]
            delta = cell["lead_delta_unheld_minus_held"]["qd"]
            self.assertGreater(held, 3.0, msg=panel)
            self.assertLess(abs(delta) / held, 0.05, msg=panel)

    def test_the_archive_is_never_catastrophic_in_either_condition(self) -> None:
        for panel, cell in self.cells.items():
            for condition in CONDITIONS:
                self.assertEqual(
                    cell[condition]["catastrophic_seeds"]["qd"], 0, msg=f"{panel}/{condition}"
                )

    def test_the_majority_swarms_lead_is_where_the_answer_was_load_bearing(self) -> None:
        for panel, cell in self.cells.items():
            majority = cell["lead_delta_unheld_minus_held"]["majority"]
            archive = cell["lead_delta_unheld_minus_held"]["qd"]
            self.assertLess(majority, -0.8, msg=panel)
            self.assertLess(majority, archive, msg=panel)

    def test_the_committed_parity_report_matches_the_module(self) -> None:
        parity = json.loads(PARITY_RESULT.read_text())
        self.assertEqual(parity["goal_parity"]["unheld_goal"], list(UNHELD_GOAL))
        self.assertFalse(parity["goal_parity"]["unheld_goal_is_a_member"])

    def test_the_published_pool_matches_both_goals_on_difficulty(self) -> None:
        # The parity that decides the outcome, measured on the full 200k-draw
        # pool that the write-up quotes.
        difficulty = json.loads(PARITY_RESULT.read_text())["goal_difficulty"]
        for key in ("attainable_ceiling", "mean_over_viable",
                    "transfer_regret_from_initial_optimum"):
            held, unheld = difficulty[key]["held"], difficulty[key]["unheld"]
            self.assertLess(abs(unheld - held) / held, 0.05, msg=key)

    def test_the_residual_gap_falls_on_the_committed_arms_only(self) -> None:
        # The one parity the pool argmax does not capture. It is negative, so
        # the substitute is harder for an arm locked to the old objective --
        # which is why scalar and planner drop while the reference arm, which
        # commits to nothing, does not.
        evolved = json.loads(PARITY_RESULT.read_text())["goal_difficulty"][
            "evolved_initial_elite_utility"
        ]
        self.assertLess(evolved["unheld_minus_held"], 0.0)
        self.assertLess(abs(evolved["unheld_minus_held"]) / evolved["held"], 0.10)


class CommandLineTest(unittest.TestCase):
    def test_parity_mode_writes_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "parity.json"
            completed = subprocess.run(
                [sys.executable, MODULE, "--mode", "parity", "--draws", "2000",
                 "--output", str(out)],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(out.read_text())
            self.assertIn("goal_parity", report)
            self.assertIn("goal_difficulty", report)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
