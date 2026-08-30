"""E031: a consensus swarm whose goal beliefs update from evidence.

E024's caveat had two halves. E030 measured the first -- the supplied goal set
contains the future goal -- and found it load-bearing for the majority-vote
swarm and nearly irrelevant to the archive. This is the second half: the goals
are supplied "rather than learned", so E031 makes them learned.

The dangerous failure here is a learning arm that differs from the baseline in
some way *other* than the learning: a changed vote rule, a different random
stream, an extra draw consumed somewhere. Any of those would produce a
difference that looks like a result. So the arm is built as a strict extension
and the extension is pinned as an identity:

1. at flat likelihood the filter is provably inert and the arm reproduces the
   PUBLISHED ``majority`` row of ``mbe.run_seed`` bit-for-bit -- same seed
   derivation, same rng consumption, same trace;
2. the credibility-weighted vote is exactly the strict-majority rule when the
   weights are uniform, which is what makes (1) possible at all;
3. the placebo consumes its coin flips from a dedicated stream, so it perturbs
   the weights and nothing else;
4. the evidence is ordinal by construction -- the arm never sees a delivered
   artifact's realized value, only whether it beat the previous one;
5. particles stay on the simplex through jitter and resampling, so a drifted
   belief is still a legal goal.

Recomputed sweeps are never compared byte-for-byte across machines: the
simulators go through ``exp`` and ``**``, whose last-place rounding differs
across CPUs and C libraries. The identities above are compared exactly because
they run in one process against one other function.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sim.e027_defect_propagation as e027
import sim.e030_supplied_goal_membership as e030
import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
from sim.e031_learned_goal_filter import (
    ARM,
    CONDITIONS,
    DEFAULT_CHANGE_AT,
    DEFAULT_EPSILON,
    DEFAULT_GENERATIONS,
    EXPERIMENT_ID,
    LEARNED_STRATEGY_OFFSET,
    PANEL_ORDER,
    PANELS,
    UNINFORMATIVE,
    VARIANT_ORDER,
    VARIANTS,
    _belief_spread,
    _effective_sample_size,
    _jitter,
    _learned_swarm_search,
    _normalize,
    _percentile,
    _posterior_mean,
    _resolve_panels,
    _systematic_resample,
    _variant_kwargs,
    belief_tracking,
    matrix,
    run_seed,
    variant_sweep,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = "sim/e031_learned_goal_filter.py"
MATRIX_RESULT = REPO_ROOT / "experiments/results/E031-learned-goal-filter.json"

SMALL = dict(agents=16, generations=10, change_at=5, bins=4)
FILTER_KEYS = ("ordinal_observations", "filter_resamples", "belief_diffusions")


def _comparable(result):
    return {k: v for k, v in result.items() if k not in FILTER_KEYS and k != "strategy"}


class ReductionToMajorityTest(unittest.TestCase):
    """The control is not *like* the baseline; it is the baseline."""

    def test_the_arm_runs_on_majoritys_own_stream(self) -> None:
        self.assertEqual(LEARNED_STRATEGY_OFFSET, mbe.STRATEGIES.index("majority"))

    def test_the_control_reproduces_the_published_majority_row(self) -> None:
        # The identity that makes every other number in E031 attributable.
        for seed in range(1, 6):
            published = next(
                row
                for row in mbe.run_seed(seed=seed, **SMALL)["results"]
                if row["strategy"] == "majority"
            )
            control = run_seed(
                seed=seed, verification=None, epsilon=UNINFORMATIVE, **SMALL
            )
            self.assertEqual(_comparable(published), _comparable(control), msg=f"seed {seed}")

    def test_the_control_reproduces_it_under_an_imperfect_panel_too(self) -> None:
        panel = PANELS[PANEL_ORDER[-1]]
        for seed in range(1, 4):
            published = next(
                row
                for row in mbe.run_seed(seed=seed, verification=panel, **SMALL)["results"]
                if row["strategy"] == "majority"
            )
            control = run_seed(
                seed=seed, verification=panel, epsilon=UNINFORMATIVE, **SMALL
            )
            self.assertEqual(_comparable(published), _comparable(control), msg=f"seed {seed}")

    def test_the_flat_likelihood_consumes_no_random_numbers(self) -> None:
        # If it did, the identity above would hold only by luck of the draw.
        for seed in range(1, 4):
            rng_a = random.Random(seed)
            mbe._majority_search(
                rng_a, random.Random(seed ^ mbe.VERIFIER_STREAM_MASK),
                SMALL["agents"], SMALL["generations"], SMALL["change_at"],
                sim.VerificationConfig(), SMALL["bins"], None,
            )
            rng_b = random.Random(seed)
            _learned_swarm_search(
                rng_b, random.Random(seed ^ mbe.VERIFIER_STREAM_MASK),
                SMALL["agents"], SMALL["generations"], SMALL["change_at"],
                sim.VerificationConfig(), SMALL["bins"], None,
                epsilon=UNINFORMATIVE,
            )
            self.assertEqual(rng_a.random(), rng_b.random(), msg=f"seed {seed}")

    def test_the_control_variant_is_the_flat_likelihood(self) -> None:
        self.assertEqual(VARIANTS["control"]["epsilon"], UNINFORMATIVE)

    def test_learning_actually_changes_something(self) -> None:
        # A reduction test passes just as happily on an arm that does nothing.
        changed = 0
        for seed in range(1, 11):
            control = run_seed(seed=seed, verification=None, epsilon=UNINFORMATIVE, **SMALL)
            learned = run_seed(seed=seed, verification=None, epsilon=DEFAULT_EPSILON, **SMALL)
            if control["post_change_utility_auc"] != learned["post_change_utility_auc"]:
                changed += 1
        self.assertGreater(changed, 0)


class WeightedVoteTest(unittest.TestCase):
    """The weighted vote must BE the strict-majority rule at uniform weights."""

    def test_uniform_mass_above_a_half_is_a_strict_majority(self) -> None:
        for agents in (2, 3, 8, 15, 16, 63, 64):
            uniform = 1.0 / agents
            threshold = agents // 2 + 1
            for count in range(agents + 1):
                passes_mass = math.fsum([uniform] * count) > 0.5
                passes_count = count >= threshold
                self.assertEqual(
                    passes_mass, passes_count, msg=f"agents={agents} count={count}"
                )


class OrdinalEvidenceTest(unittest.TestCase):
    """The channel must stay ordinal; a value channel would be invertible."""

    def test_the_module_never_reads_a_delivered_value_into_the_likelihood(self) -> None:
        source = (REPO_ROOT / MODULE).read_text()
        start = source.index("observed_improvement = value > previous_value")
        end = source.index("total = sum(updated)")
        update = source[start:end]
        # The likelihood may compare utilities; it may not consume `value`
        # itself, which is the quantity that makes the goal solvable.
        self.assertNotIn("value -", update)
        self.assertNotIn("- value", update)
        self.assertNotIn("value /", update)
        self.assertEqual(update.count("value > previous_value"), 1)

    def test_a_particle_that_predicts_the_direction_gains_weight(self) -> None:
        # Constructed directly rather than run: the rule is small enough to
        # check by hand, and a full run would hide it behind sampling.
        better = sim.Candidate((0.30, 0.35, 0.10, 0.10, 0.30))
        worse = sim.Candidate((0.30, 0.05, 0.40, 0.10, 0.30))
        favours_adaptability = (0.10, 0.60, 0.10, 0.10, 0.10)
        favours_efficiency = (0.10, 0.10, 0.60, 0.10, 0.10)
        self.assertGreater(
            sim.unchecked_utility(better, favours_adaptability),
            sim.unchecked_utility(worse, favours_adaptability),
        )
        self.assertLess(
            sim.unchecked_utility(better, favours_efficiency),
            sim.unchecked_utility(worse, favours_efficiency),
        )


class ParticleMechanicsTest(unittest.TestCase):
    """Whatever the filter does, a particle must stay a legal goal."""

    def test_normalize_returns_a_weight_vector(self) -> None:
        normalized = _normalize([0.4, -0.2, 0.9, 0.0, 0.1])
        self.assertAlmostEqual(sum(normalized), 1.0, places=9)
        for weight in normalized:
            self.assertGreater(weight, 0.0)

    def test_jitter_keeps_the_particle_on_the_simplex(self) -> None:
        rng = random.Random(11)
        goal = sim.PLAUSIBLE_GOALS[0]
        for _ in range(200):
            goal = _jitter(goal, rng, 0.2)
            self.assertAlmostEqual(sum(goal), 1.0, places=9)
            self.assertTrue(all(weight > 0.0 for weight in goal))

    def test_zero_jitter_is_the_identity(self) -> None:
        rng = random.Random(3)
        goal = tuple(sim.PLAUSIBLE_GOALS[1])
        self.assertEqual(_jitter(goal, rng, 0.0), goal)

    def test_jitter_lets_a_particle_leave_the_supplied_set(self) -> None:
        # Without this the filter would still be reading the answer key, just
        # with better bookkeeping.
        rng = random.Random(5)
        drifted = _jitter(sim.PLAUSIBLE_GOALS[0], rng, 0.05)
        self.assertNotIn(drifted, sim.PLAUSIBLE_GOALS)

    def test_effective_sample_size_is_the_particle_count_when_uniform(self) -> None:
        self.assertAlmostEqual(_effective_sample_size([0.25] * 4), 4.0)
        self.assertAlmostEqual(_effective_sample_size([1.0, 0.0, 0.0, 0.0]), 1.0)

    def test_resampling_keeps_the_population_size(self) -> None:
        particles = [(0.2,) * 5, (0.4,) * 5, (0.6,) * 5, (0.8,) * 5]
        chosen = _systematic_resample(particles, [0.1, 0.1, 0.1, 0.7], random.Random(1))
        self.assertEqual(len(chosen), len(particles))
        for particle in chosen:
            self.assertIn(particle, particles)

    def test_resampling_concentrates_on_the_heavy_particle(self) -> None:
        particles = [(0.0,), (1.0,), (2.0,), (3.0,)]
        chosen = _systematic_resample(particles, [0.0, 0.0, 1.0, 0.0], random.Random(2))
        self.assertEqual(set(chosen), {(2.0,)})

    def test_resampling_consumes_exactly_one_random_number(self) -> None:
        # Systematic rather than multinomial, so rng consumption does not scale
        # with particle count and stays comparable across agent counts.
        rng_a, rng_b = random.Random(4), random.Random(4)
        _systematic_resample([(0.5,)] * 32, [1.0 / 32] * 32, rng_a)
        rng_b.random()
        self.assertEqual(rng_a.random(), rng_b.random())

    def test_belief_spread_is_dispersion_not_a_distinct_count(self) -> None:
        # Counting distinct hypotheses is the obvious measure and it is the
        # wrong one: jitter makes every particle numerically unique, so a
        # collapsed cluster and a genuinely spread population both count N.
        tight = [(0.2, 0.2, 0.2, 0.2, 0.2 + i * 1e-6) for i in range(5)]
        wide = [tuple(0.04 if j != i else 0.84 for j in range(5)) for i in range(5)]
        self.assertEqual(len(set(tight)), len(set(wide)))  # both fully distinct
        self.assertLess(_belief_spread(tight), _belief_spread(wide) / 100)

    def test_identical_beliefs_have_zero_spread(self) -> None:
        self.assertAlmostEqual(_belief_spread([(0.2,) * 5] * 6), 0.0)

    def test_the_posterior_mean_is_a_weighted_average(self) -> None:
        mean = _posterior_mean([(0.0, 1.0), (1.0, 0.0)], [0.25, 0.75])
        self.assertAlmostEqual(mean[0], 0.75)
        self.assertAlmostEqual(mean[1], 0.25)


class PlaceboTest(unittest.TestCase):
    """The placebo must differ from the filter only in the weights."""

    def test_the_placebo_draws_from_a_dedicated_stream(self) -> None:
        source = (REPO_ROOT / MODULE).read_text()
        self.assertIn("placebo_rng.random() < 0.5", source)
        self.assertIn("placebo_rng = random.Random(rng.random()) if placebo else None", source)

    def test_the_placebo_ignores_the_observation(self) -> None:
        # Same concentration dynamics, zero information. It is the control that
        # separates "concentrated the posterior" from "concentrated it on the
        # goal that is about to stop being true".
        first = run_seed(seed=3, verification=None, epsilon=DEFAULT_EPSILON,
                         placebo=True, **SMALL)
        second = run_seed(seed=3, verification=None, epsilon=DEFAULT_EPSILON,
                          placebo=True, **SMALL)
        self.assertEqual(first, second)
        evidence = run_seed(seed=3, verification=None, epsilon=DEFAULT_EPSILON, **SMALL)
        self.assertNotEqual(first["post_change_utility_auc"],
                            evidence["post_change_utility_auc"])


class DiffusionTest(unittest.TestCase):
    """Diffusion must carry no evidence at all."""

    def test_diffusion_runs_with_a_flat_likelihood(self) -> None:
        self.assertEqual(VARIANTS["diffusion"]["epsilon"], UNINFORMATIVE)
        self.assertGreater(VARIANTS["diffusion"]["diffuse_every"], 0)

    def test_diffusion_makes_no_observations(self) -> None:
        result = run_seed(seed=6, verification=None, epsilon=UNINFORMATIVE,
                          diffuse_every=2, **SMALL)
        self.assertEqual(result["ordinal_observations"], 0)
        self.assertEqual(result["filter_resamples"], 0)
        self.assertGreater(result["belief_diffusions"], 0)

    def test_diffusion_still_changes_the_outcome(self) -> None:
        control = run_seed(seed=6, verification=None, epsilon=UNINFORMATIVE, **SMALL)
        drifted = run_seed(seed=6, verification=None, epsilon=UNINFORMATIVE,
                           diffuse_every=1, **SMALL)
        self.assertNotEqual(control["post_change_utility_auc"],
                            drifted["post_change_utility_auc"])

    def test_diffusion_never_fires_on_the_first_generation(self) -> None:
        result = run_seed(seed=6, verification=None, epsilon=UNINFORMATIVE,
                          diffuse_every=1, **SMALL)
        self.assertEqual(result["belief_diffusions"], SMALL["generations"] - 1)


class VariantLadderTest(unittest.TestCase):
    """Each rung must rule out one alternative explanation for the one above."""

    def test_every_variant_is_ordered_and_resolvable(self) -> None:
        self.assertEqual(sorted(VARIANT_ORDER), sorted(VARIANTS))
        for name in VARIANT_ORDER:
            self.assertIsInstance(_variant_kwargs(name, DEFAULT_CHANGE_AT), dict)

    def test_change_at_placeholders_are_filled_in(self) -> None:
        # A ``None`` reaching the runner would silently mean "from generation 0"
        # for learn_from and "never" for reset_at -- two different bugs.
        for name in ("learned-after-change", "oracle-reset"):
            resolved = _variant_kwargs(name, 25)
            self.assertNotIn(None, resolved.values())
            self.assertIn(25, resolved.values())

    def test_resolving_does_not_mutate_the_registry(self) -> None:
        _variant_kwargs("oracle-reset", 99)
        self.assertIsNone(VARIANTS["oracle-reset"]["reset_at"])

    def test_the_no_jitter_variants_pin_the_particles(self) -> None:
        for name in ("learned-no-jitter", "placebo-no-jitter"):
            self.assertEqual(VARIANTS[name]["jitter"], 0.0, msg=name)

    def test_each_pinned_variant_pairs_with_a_drifting_one(self) -> None:
        # The isolation only works as a PAIR: same everything, jitter on and
        # off. A lone pinned variant would prove nothing about the jitter.
        for pinned, drifting in (
            ("learned-no-jitter", "learned"),
            ("placebo-no-jitter", "placebo"),
        ):
            paired = dict(VARIANTS[pinned])
            paired.pop("jitter")
            self.assertEqual(paired, VARIANTS[drifting], msg=pinned)

    def test_the_frozen_spread_variant_carries_no_evidence_and_never_moves(self) -> None:
        # It is the rung that narrows the claim from "the beliefs must keep
        # moving" to "there must be enough of them", so it must genuinely
        # freeze: one perturbation at generation 0 and nothing after.
        self.assertEqual(VARIANTS["diverse-init"]["epsilon"], UNINFORMATIVE)
        self.assertTrue(VARIANTS["diverse-init"]["diverse_init"])
        self.assertNotIn("diffuse_every", VARIANTS["diverse-init"])
        report = belief_tracking(seed=9, variant="diverse-init", **SMALL)
        spreads = {step["belief_spread"] for step in report["trajectory"]}
        self.assertEqual(len(spreads), 1)

    def test_the_frozen_spread_variant_starts_above_the_control(self) -> None:
        spread_of = lambda name: belief_tracking(seed=9, variant=name, **SMALL)[
            "trajectory"
        ][0]["belief_spread"]
        self.assertGreater(spread_of("diverse-init"), spread_of("control"))

    def test_the_control_holds_only_the_supplied_points(self) -> None:
        # Four hypotheses shared across every agent, however many agents there
        # are. That is the quantity E031 finds is doing the damage.
        report = belief_tracking(seed=9, variant="control", **SMALL)
        self.assertEqual(len(sim.PLAUSIBLE_GOALS), 4)
        self.assertEqual(
            {step["belief_spread"] for step in report["trajectory"]},
            {report["trajectory"][0]["belief_spread"]},
        )

    def test_the_rival_control_touches_no_belief(self) -> None:
        # It must loosen the consensus and nothing else, or it would not be a
        # test of the rival explanation.
        rival = VARIANTS["vote-noise"]
        self.assertEqual(rival["epsilon"], UNINFORMATIVE)
        self.assertGreater(rival["vote_noise"], 0.0)
        self.assertNotIn("diffuse_every", rival)
        self.assertNotIn("placebo", rival)

    def test_the_rival_control_leaves_the_posterior_frozen(self) -> None:
        report = belief_tracking(seed=4, variant="vote-noise", **SMALL)
        means = {tuple(step["posterior_mean"]) for step in report["trajectory"]}
        self.assertEqual(len(means), 1)

    def test_zero_vote_noise_consumes_no_random_number(self) -> None:
        # Otherwise the reduction identity would hold only by luck.
        for seed in range(1, 4):
            plain = run_seed(seed=seed, verification=None, epsilon=UNINFORMATIVE, **SMALL)
            explicit = run_seed(seed=seed, verification=None, epsilon=UNINFORMATIVE,
                                vote_noise=0.0, **SMALL)
            self.assertEqual(plain, explicit)

    def test_the_slow_diffusion_variant_is_strictly_slower(self) -> None:
        # It exists so the diffusion result cannot be read as a tuned rate.
        self.assertGreater(
            VARIANTS["diffusion-slow"]["diffuse_every"],
            VARIANTS["diffusion"]["diffuse_every"],
        )
        self.assertEqual(VARIANTS["diffusion-slow"]["epsilon"], UNINFORMATIVE)

    def test_the_budget_contract_holds_for_every_variant(self) -> None:
        # An arm that quietly bought more evaluations would beat the others for
        # a reason that has nothing to do with beliefs.
        for name in VARIANT_ORDER:
            result = run_seed(
                seed=2, verification=None, **_variant_kwargs(name, SMALL["change_at"]),
                **SMALL,
            )
            self.assertEqual(
                result["verification_attempts"],
                SMALL["agents"] * SMALL["generations"],
                msg=name,
            )


class BeliefTrackingTest(unittest.TestCase):
    """A null result is unreadable without evidence that the filter works."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = belief_tracking(seed=7, variant="learned", **SMALL)

    def test_the_trajectory_covers_every_generation(self) -> None:
        self.assertEqual(len(self.report["trajectory"]), SMALL["generations"])

    def test_each_step_reports_the_distance_to_the_goal_in_force(self) -> None:
        for step in self.report["trajectory"]:
            self.assertGreaterEqual(step["distance_to_true_goal"], 0.0)
            self.assertAlmostEqual(sum(step["posterior_mean"]), 1.0, places=4)

    def test_the_effective_sample_size_never_exceeds_the_particle_count(self) -> None:
        for step in self.report["trajectory"]:
            self.assertLessEqual(step["effective_sample_size"], SMALL["agents"] + 1e-6)

    def test_the_filter_learns_the_pre_change_goal(self) -> None:
        # At full scale this is the 2.7x improvement the record quotes. Here it
        # only has to beat the un-updated control, or the arm is not learning.
        learned = belief_tracking(seed=7, variant="learned", agents=64, generations=50,
                                  change_at=25, bins=8)
        control = belief_tracking(seed=7, variant="control", agents=64, generations=50,
                                  change_at=25, bins=8)
        self.assertLess(
            learned["trajectory"][24]["distance_to_true_goal"],
            control["trajectory"][24]["distance_to_true_goal"],
        )

    def test_the_control_posterior_never_moves(self) -> None:
        control = belief_tracking(seed=7, variant="control", **SMALL)
        means = {tuple(step["posterior_mean"]) for step in control["trajectory"]}
        self.assertEqual(len(means), 1)

    def test_the_trajectory_is_serialisable(self) -> None:
        json.loads(json.dumps(self.report))


class VariantSweepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sweep = variant_sweep(
            variant="learned", seeds=3, seed_start=1, verification=None,
            goal=sim.CHANGED_GOAL, **SMALL,
        )

    def test_the_sweep_reports_the_tail_not_only_the_mean(self) -> None:
        auc = self.sweep["post_change_utility_auc"]
        self.assertLessEqual(auc["min"], auc["p05"])
        self.assertLessEqual(auc["p05"], auc["mean"] + auc["stdev"] + 1e-9)
        self.assertEqual(len(self.sweep["per_seed_auc"]), 3)

    def test_the_sweep_reports_filter_activity(self) -> None:
        for key in ("ordinal_observations", "resamples", "diffusions"):
            self.assertIn(key, self.sweep["filter_activity"])

    def test_the_sweep_restores_the_environment_goal(self) -> None:
        variant_sweep(variant="learned", seeds=1, seed_start=1, verification=None,
                      goal=e030.UNHELD_GOAL, **SMALL)
        self.assertIn(sim.CHANGED_GOAL, sim.PLAUSIBLE_GOALS)
        self.assertNotEqual(sim.CHANGED_GOAL, e030.UNHELD_GOAL)

    def test_percentile_is_nearest_rank(self) -> None:
        self.assertEqual(_percentile([5, 1, 4, 2, 3], 0.2), 1)
        self.assertEqual(_percentile([5, 1, 4, 2, 3], 1.0), 5)


class PanelReuseTest(unittest.TestCase):
    def test_the_panels_are_e027s_objects(self) -> None:
        self.assertIs(PANELS, e027.PANELS)
        self.assertIs(PANEL_ORDER, e027.PANEL_ORDER)

    def test_the_conditions_are_e030s(self) -> None:
        self.assertIs(CONDITIONS, e030.CONDITIONS)

    def test_selecting_panels_preserves_the_canonical_order(self) -> None:
        _, order = _resolve_panels(list(PANEL_ORDER)[:2][::-1])
        self.assertEqual(list(order), list(PANEL_ORDER)[:2])

    def test_an_unknown_panel_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_panels(["not-a-panel"])


class MatrixReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        name = PANEL_ORDER[0]
        cls.report = matrix(
            panels={name: PANELS[name]}, panel_order=[name],
            variants=["control", "diffusion"], seeds=2, **SMALL,
        )

    def test_the_report_carries_its_provenance(self) -> None:
        self.assertEqual(self.report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(self.report["metric"], "post_change_utility_auc")

    def test_every_cell_carries_both_conditions_and_the_live_baseline(self) -> None:
        conditions = {cell["condition"] for cell in self.report["cells"]}
        self.assertEqual(conditions, set(CONDITIONS))
        for cell in self.report["cells"]:
            self.assertEqual(sorted(cell["baseline_arms"]), sorted(mbe.STRATEGIES))

    def test_the_control_matches_the_live_baseline_majority_arm(self) -> None:
        # The baseline is recomputed in the same run rather than quoted, so
        # this is a live check that the control really is that arm.
        for cell in self.report["cells"]:
            control = next(v for v in cell["variants"] if v["variant"] == "control")
            self.assertAlmostEqual(
                control["post_change_utility_auc"]["mean"],
                cell["baseline_arms"]["majority"]["mean"],
                places=6,
                msg=f"{cell['panel']}/{cell['condition']}",
            )
            self.assertEqual(
                control["catastrophic_seeds"],
                cell["baseline_arms"]["majority"]["catastrophic_seeds"],
            )

    def test_the_report_states_its_limitations(self) -> None:
        text = " ".join(self.report["limitations"]).lower()
        self.assertIn("ordinal", text)
        self.assertIn("upper bound", text)

    def test_the_report_is_serialisable(self) -> None:
        json.loads(json.dumps(self.report))

    def test_the_environment_goal_is_restored_after_a_whole_matrix(self) -> None:
        self.assertIn(sim.CHANGED_GOAL, sim.PLAUSIBLE_GOALS)


class CommittedResultTest(unittest.TestCase):
    """The committed artifact must say what the write-up says it says.

    Every claim here is split by goal *condition*, because the matrix says the
    mechanism is: `held` is the regime where the goal the environment moves to
    is one of the four supplied hypotheses, `unheld` is E030's parity-matched
    substitute that is not. Belief spread rescues the swarm in the first and
    hurts it in the second, so a test that quantified over all eight cells
    would be asserting something false.
    """

    NON_LEARNING = ("placebo-no-jitter", "control", "vote-noise",
                    "diverse-init", "placebo", "diffusion-slow", "diffusion")
    SPREAD_ARMS = ("diffusion", "diffusion-slow", "diverse-init", "placebo")

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(MATRIX_RESULT.read_text())
        cls.cells = {
            (cell["panel"], cell["condition"]): {
                variant["variant"]: variant for variant in cell["variants"]
            }
            for cell in cls.report["cells"]
        }
        cls.held = {k: v for k, v in cls.cells.items() if k[1] == "held"}
        cls.unheld = {k: v for k, v in cls.cells.items() if k[1] == "unheld"}

    def test_the_committed_matrix_is_the_published_configuration(self) -> None:
        self.assertEqual(self.report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(self.report["seeds"], 100)
        self.assertEqual(self.report["generations"], 50)
        self.assertEqual(self.report["change_at"], 25)
        self.assertAlmostEqual(self.report["catastrophe_utility_auc_threshold"], 16.0)
        self.assertEqual(len(self.cells), len(PANEL_ORDER) * len(CONDITIONS))
        self.assertEqual(len(self.held), len(PANEL_ORDER))
        self.assertEqual(len(self.unheld), len(PANEL_ORDER))

    # ---- the filter works, and that is the problem -----------------------

    def test_the_filter_demonstrably_learns_the_pre_change_goal(self) -> None:
        # Without this the headline is unattributable between "learning does
        # not help" and "the filter never learned anything".
        for key, variants in self.cells.items():
            self.assertLess(
                variants["learned"]["belief_error"]["at_change"],
                variants["control"]["belief_error"]["at_change"],
                msg=str(key),
            )

    def test_learning_from_generation_zero_is_harmful_in_every_cell(self) -> None:
        # Both conditions, all four panels: the arm that learns from the start
        # fails more often than the control it reduces to, and arrives at the
        # change point with less spread than the control.
        for key, variants in self.cells.items():
            self.assertGreater(
                variants["learned"]["catastrophic_seeds"],
                variants["control"]["catastrophic_seeds"],
                msg=str(key),
            )
            self.assertLess(
                variants["learned"]["belief_spread"]["at_change"],
                variants["control"]["belief_spread"]["at_change"],
                msg=str(key),
            )

    def test_pinning_the_particles_is_worse_still(self) -> None:
        for key, variants in self.cells.items():
            self.assertGreater(
                variants["learned-no-jitter"]["catastrophic_seeds"],
                variants["control"]["catastrophic_seeds"],
                msg=str(key),
            )

    # ---- the headline: it is the timing of the learning -------------------

    def test_learning_only_after_the_change_beats_the_control_everywhere(self) -> None:
        # The one intervention that survives both goal conditions and all four
        # verifier panels: fewer catastrophic seeds AND a higher mean than the
        # published `majority` arm in all eight cells.
        for key, variants in self.cells.items():
            self.assertLess(
                variants["learned-after-change"]["catastrophic_seeds"],
                variants["control"]["catastrophic_seeds"],
                msg=f"{key} tail",
            )
            self.assertGreater(
                variants["learned-after-change"]["post_change_utility_auc"]["mean"],
                variants["control"]["post_change_utility_auc"]["mean"],
                msg=f"{key} mean",
            )

    def test_learning_only_after_the_change_has_the_best_mean_of_any_variant(self) -> None:
        for key, variants in self.cells.items():
            best = max(variants, key=lambda n: variants[n]["post_change_utility_auc"]["mean"])
            self.assertEqual(best, "learned-after-change", msg=str(key))

    def test_post_change_learning_beats_the_free_change_detector(self) -> None:
        # `oracle-reset` is handed the change point and still learns from
        # pre-change evidence. Discarding that evidence outright is better than
        # being told when to discount it, in every cell.
        for key, variants in self.cells.items():
            self.assertLess(
                variants["learned-after-change"]["catastrophic_seeds"],
                variants["oracle-reset"]["catastrophic_seeds"],
                msg=str(key),
            )

    def test_post_change_learning_improves_accuracy_in_both_conditions(self) -> None:
        for key, variants in self.cells.items():
            self.assertLess(
                variants["learned-after-change"]["belief_error"]["at_end"],
                variants["control"]["belief_error"]["at_end"],
                msg=str(key),
            )

    # ---- spread: real, and conditional on the answer being in the set -----

    def test_every_spread_arm_removes_the_failure_mode_when_the_goal_is_held(self) -> None:
        for key, variants in self.held.items():
            for name in self.SPREAD_ARMS:
                self.assertLess(
                    variants[name]["catastrophic_seeds"],
                    variants["control"]["catastrophic_seeds"],
                    msg=f"{key}/{name}",
                )

    def test_every_spread_arm_is_worse_than_the_control_when_the_goal_is_unheld(self) -> None:
        # The inversion. Spreading beliefs around four hypotheses helps only
        # when the goal the environment moves to is one of them.
        for key, variants in self.unheld.items():
            for name in self.SPREAD_ARMS:
                self.assertGreater(
                    variants[name]["catastrophic_seeds"],
                    variants["control"]["catastrophic_seeds"],
                    msg=f"{key}/{name}",
                )

    def test_frozen_one_shot_spread_is_genuinely_frozen(self) -> None:
        # The rung that rules out adaptation: no likelihood, no reweighting,
        # no drift, nothing that could respond to the goal moving.
        for key, variants in self.cells.items():
            self.assertEqual(
                variants["diverse-init"]["belief_spread"]["at_change"],
                variants["diverse-init"]["belief_spread"]["at_end"],
                msg=str(key),
            )
            self.assertEqual(
                variants["diverse-init"]["filter_activity"]["ordinal_observations"],
                0.0, msg=str(key),
            )

    def test_diffusion_makes_no_observations_at_scale(self) -> None:
        for key, variants in self.cells.items():
            for name in ("diffusion", "diffusion-slow"):
                activity = variants[name]["filter_activity"]
                self.assertEqual(activity["ordinal_observations"], 0.0, msg=f"{key}/{name}")
                self.assertEqual(activity["resamples"], 0.0, msg=f"{key}/{name}")
                self.assertGreater(activity["diffusions"], 0.0, msg=f"{key}/{name}")

    def test_spread_orders_the_non_learning_arms_only_when_the_goal_is_held(self) -> None:
        # The mechanism claim as an ordering claim, and its own refutation in
        # the other condition. Among arms whose beliefs carry no evidence, the
        # least- and most-spread arms swap places between the two regimes.
        def ends(variants):
            ranked = sorted(self.NON_LEARNING,
                            key=lambda n: variants[n]["belief_spread"]["at_end"])
            return (variants[ranked[0]]["catastrophic_seeds"],
                    variants[ranked[-1]]["catastrophic_seeds"], ranked)

        for key, variants in self.held.items():
            least, most, ranked = ends(variants)
            self.assertGreater(least, most, msg=f"{key} {ranked}")
        for key, variants in self.unheld.items():
            least, most, ranked = ends(variants)
            self.assertLess(least, most, msg=f"{key} {ranked}")

    def test_the_jitter_is_what_moves_the_tail_not_the_reweighting(self) -> None:
        # The isolating pair: identical coin-flip reweighting, particles
        # drifting or pinned. Free particles help when the goal is held and
        # hurt when it is not; the reweighting is common to both, so it is not
        # the variable in either direction.
        for key, variants in self.held.items():
            self.assertLess(
                variants["placebo"]["catastrophic_seeds"],
                variants["placebo-no-jitter"]["catastrophic_seeds"],
                msg=str(key),
            )
        for key, variants in self.unheld.items():
            self.assertGreater(
                variants["placebo"]["catastrophic_seeds"],
                variants["placebo-no-jitter"]["catastrophic_seeds"],
                msg=str(key),
            )

    def test_belief_spread_beats_loosening_the_consensus_when_the_goal_is_held(self) -> None:
        # The rival explanation, given its best case: the vote-noise level that
        # minimised catastrophic seeds across a 0.02-0.50 sweep. In the held
        # condition diffusion still wins on both the tail and the mean.
        for key, variants in self.held.items():
            self.assertLess(
                variants["diffusion"]["catastrophic_seeds"],
                variants["vote-noise"]["catastrophic_seeds"],
                msg=f"{key} tail",
            )
            self.assertGreater(
                variants["diffusion"]["post_change_utility_auc"]["mean"],
                variants["vote-noise"]["post_change_utility_auc"]["mean"],
                msg=f"{key} mean",
            )

    def test_loosening_the_consensus_never_beats_the_control_on_the_mean(self) -> None:
        for key, variants in self.cells.items():
            self.assertLess(
                variants["vote-noise"]["post_change_utility_auc"]["mean"],
                variants["control"]["post_change_utility_auc"]["mean"],
                msg=str(key),
            )

    # ---- accuracy is not the variable -------------------------------------

    def test_belief_accuracy_does_not_buy_the_outcome_when_the_goal_is_held(self) -> None:
        # `oracle-reset` is handed the change point for free and ends with the
        # most accurate posterior of any arm here, and it still does not beat
        # evidence-free diffusion.
        for key, variants in self.held.items():
            self.assertLess(
                variants["oracle-reset"]["belief_error"]["at_end"],
                variants["diffusion"]["belief_error"]["at_end"],
                msg=f"{key} accuracy",
            )
            self.assertGreater(
                variants["oracle-reset"]["catastrophic_seeds"],
                variants["diffusion"]["catastrophic_seeds"],
                msg=f"{key} outcome",
            )

    def test_the_spread_arms_are_no_more_accurate_than_the_control(self) -> None:
        # Rules out "the drift is quietly finding the new goal".
        for key, variants in self.cells.items():
            for name in self.SPREAD_ARMS:
                self.assertGreater(
                    variants[name]["belief_error"]["at_end"],
                    variants["control"]["belief_error"]["at_end"] - 0.01,
                    msg=f"{key}/{name}",
                )

    # ---- what does and does not move the numbers ---------------------------

    def test_the_verifier_panel_is_not_the_variable(self) -> None:
        # Every variant's catastrophic count is nearly flat across the four
        # E027 panels within a condition, and swings by tens across the two
        # conditions. The goal condition is the axis; the panel is not.
        for condition in CONDITIONS:
            cells = [v for k, v in self.cells.items() if k[1] == condition]
            for name in cells[0]:
                counts = [c[name]["catastrophic_seeds"] for c in cells]
                self.assertLessEqual(max(counts) - min(counts), 10, msg=f"{condition}/{name}")
        for name in ("diffusion", "diverse-init", "diffusion-slow"):
            held = max(v[name]["catastrophic_seeds"] for v in self.held.values())
            unheld = min(v[name]["catastrophic_seeds"] for v in self.unheld.values())
            self.assertGreater(unheld - held, 30, msg=name)

    def test_the_archive_is_still_ahead_of_every_belief_variant(self) -> None:
        for (panel, condition), variants in self.cells.items():
            cell = next(
                c for c in self.report["cells"]
                if c["panel"] == panel and c["condition"] == condition
            )
            archive = cell["baseline_arms"]["qd"]["mean"]
            for name, variant in variants.items():
                self.assertLess(
                    variant["post_change_utility_auc"]["mean"], archive,
                    msg=f"{panel}/{condition}/{name}",
                )

    def test_the_control_reproduces_the_published_majority_row(self) -> None:
        for (panel, condition), variants in self.cells.items():
            cell = next(
                c for c in self.report["cells"]
                if c["panel"] == panel and c["condition"] == condition
            )
            self.assertAlmostEqual(
                variants["control"]["post_change_utility_auc"]["mean"],
                cell["baseline_arms"]["majority"]["mean"], places=5,
                msg=f"{panel}/{condition}",
            )
            self.assertEqual(
                variants["control"]["catastrophic_seeds"],
                cell["baseline_arms"]["majority"]["catastrophic_seeds"],
                msg=f"{panel}/{condition}",
            )


class CommandLineTest(unittest.TestCase):
    def test_trajectory_mode_writes_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "trajectory.json"
            completed = subprocess.run(
                [sys.executable, MODULE, "--mode", "trajectory", "--seed", "7",
                 "--agents", "16", "--generations", "10", "--change-at", "5",
                 "--bins", "4", "--output", str(out)],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(len(report["trajectory"]), 10)

    def test_an_unknown_variant_is_rejected(self) -> None:
        completed = subprocess.run(
            [sys.executable, MODULE, "--mode", "matrix", "--variant", "not-a-variant",
             "--seeds", "1", "--panel", "perfect"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
