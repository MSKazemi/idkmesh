"""E028: a landscape where apparent quality cannot see viability.

E027's survival result is bounded by a measured confound: on the E011 landscape
apparent robust quality is itself a ~0.94-AUROC viability classifier, so
elitist selection is a second free verifier and the archive's 0/100 catastrophic
seeds cannot be attributed to retained diversity alone. E028 moves ground truth
into a dimension no goal weights, no descriptor reads and the budget does not
constrain, and asks the same question again.

The dangerous failure here is not a crash. It is a landscape that *looks*
swapped but is not -- the arms load `emergence_sim.py` twice under two module
names, so patching one and not the other would leave two disagreeing
definitions of ground truth inside a single run and quietly produce a number
nobody could reproduce. These tests pin, in order:

1. the latent dimension is genuinely invisible to utility, quality and niche;
2. the landscape swap reaches every module that owns a copy of it;
3. the swap is fully reversed, including when the block raises;
4. the original landscape is bit-for-bit unaffected, so the paired matrix's
   control column really is E027's harness;
5. the constructed base rate and the measured heritability are what the write-up
   claims they are.

Recomputed sweeps are never compared byte-for-byte: the simulators go through
`exp` and `**`, whose last-place rounding differs across CPUs and C libraries.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import unittest
from pathlib import Path

import sim.e027_defect_propagation as e027
import sim.emergence_sim as sim
from sim.e028_latent_defect_dimension import (
    DIAGNOSTIC_PANELS,
    EXPERIMENT_ID,
    INTEGRITY_SIGMA_DEFAULT,
    INTEGRITY_SIGMA_HERITABILITY_MATCHED,
    LANDSCAPE_PROVENANCE,
    LATENT_INDEX,
    MIN_INTEGRITY,
    LatentCandidate,
    _auroc,
    _candidate_class,
    _landscape_modules,
    audit,
    latent_defect_landscape,
    latent_viable,
    matrix,
    parity,
    quality_viability_diagnostic,
    TRUTH_BLIND_PANEL,
    _auroc_or_none,
)
from sim.matched_budget_emergence import STRATEGIES, DefectChannel, run_seed
from sim.matched_budget_emergence import sim as arena_sim

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"
TINY = dict(agents=8, generations=6, change_at=3, bins=4)


def _latent(observable, integrity):
    return LatentCandidate(tuple(observable) + (integrity,))


class TheLatentDimensionIsInvisible(unittest.TestCase):
    """Whatever else changes, the goals must not be able to see integrity."""

    def test_utility_is_identical_for_every_plausible_goal(self):
        observable = (0.40, 0.55, 0.30, 0.45, 0.35)
        low = _latent(observable, 0.01)
        high = _latent(observable, 0.99)
        self.assertNotEqual(latent_viable(low), latent_viable(high))
        for goal in sim.PLAUSIBLE_GOALS:
            self.assertEqual(
                sim.unchecked_utility(low, goal),
                sim.unchecked_utility(high, goal),
            )

    def test_robust_quality_is_identical(self):
        observable = (0.40, 0.55, 0.30, 0.45, 0.35)
        self.assertEqual(
            sim.unchecked_robust_quality(_latent(observable, 0.0)),
            sim.unchecked_robust_quality(_latent(observable, 1.0)),
        )

    def test_the_behaviour_descriptor_is_identical(self):
        observable = (0.40, 0.55, 0.30, 0.45, 0.35)
        self.assertEqual(
            sim.niche(_latent(observable, 0.0), 8),
            sim.niche(_latent(observable, 1.0), 8),
        )

    def test_viability_does_not_move_with_the_observable_traits(self):
        for observable in (
            (0.00, 0.00, 0.00, 0.00, 0.00),
            (0.90, 0.90, 0.60, 0.40, 0.40),
            (0.10, 0.99, 0.99, 0.01, 0.01),
        ):
            self.assertTrue(latent_viable(_latent(observable, 0.75)))
            self.assertFalse(latent_viable(_latent(observable, 0.25)))

    def test_the_budget_does_not_reach_the_latent_dimension(self):
        """Spending the whole budget must not cost a candidate its integrity.

        If the renormaliser touched index 5, integrity would be readable off
        the observable spend and the decoupling would be a fiction.
        """
        child = _latent((1.0, 1.0, 1.0, 1.0, 1.0), 0.9).mutate(random.Random(3))
        self.assertLessEqual(sum(child.traits[:LATENT_INDEX]), sim.BUDGET + 1e-9)
        self.assertGreater(child.traits[LATENT_INDEX], 0.0)

    def test_the_budget_clause_still_guards_a_hand_built_candidate(self):
        self.assertFalse(latent_viable(_latent((1.0, 1.0, 1.0, 1.0, 1.0), 0.99)))


class TheSwapReachesEveryModule(unittest.TestCase):
    """The arms and the audit read two different module objects."""

    def test_the_two_module_objects_are_actually_distinct(self):
        self.assertIsNot(sim, arena_sim)
        self.assertIn(sim, _landscape_modules())
        self.assertIn(arena_sim, _landscape_modules())

    def test_both_modules_are_patched_inside_the_block(self):
        with latent_defect_landscape() as candidate_class:
            for module in (sim, arena_sim):
                self.assertIs(module.viable, latent_viable)
                self.assertIs(module.Candidate, candidate_class)

    def test_both_modules_are_restored_after_the_block(self):
        before = [(m, m.Candidate, m.viable) for m in (sim, arena_sim)]
        with latent_defect_landscape():
            pass
        for module, candidate, viable in before:
            self.assertIs(module.Candidate, candidate)
            self.assertIs(module.viable, viable)

    def test_the_swap_is_reversed_even_when_the_block_raises(self):
        before = [(m, m.Candidate, m.viable) for m in (sim, arena_sim)]
        with self.assertRaises(RuntimeError):
            with latent_defect_landscape():
                raise RuntimeError("boom")
        for module, candidate, viable in before:
            self.assertIs(module.Candidate, candidate)
            self.assertIs(module.viable, viable)

    def test_the_landscape_actually_changes_an_arm(self):
        """A swap that reached nothing would silently report E027's numbers."""
        outside = run_seed(5, **TINY, defect=DefectChannel(cost=1.0))
        with latent_defect_landscape():
            inside = run_seed(5, **TINY, defect=DefectChannel(cost=1.0))
        traces_outside = [row["trace"] for row in outside["results"]]
        traces_inside = [row["trace"] for row in inside["results"]]
        self.assertNotEqual(traces_outside, traces_inside)

    def test_the_original_landscape_is_unchanged_afterwards(self):
        before = run_seed(5, **TINY, defect=DefectChannel(cost=1.0))
        with latent_defect_landscape():
            run_seed(5, **TINY, defect=DefectChannel(cost=1.0))
        after = run_seed(5, **TINY, defect=DefectChannel(cost=1.0))
        self.assertEqual(before, after)


class TheCandidateClassCarriesItsOwnSigma(unittest.TestCase):
    def test_the_sigma_is_bound_to_the_class_not_to_the_module(self):
        first = _candidate_class(0.05)
        second = _candidate_class(0.40)
        self.assertEqual(first.INTEGRITY_SIGMA, 0.05)
        self.assertEqual(second.INTEGRITY_SIGMA, 0.40)
        self.assertEqual(LatentCandidate.INTEGRITY_SIGMA, INTEGRITY_SIGMA_DEFAULT)

    def test_children_keep_their_parent_class(self):
        cls = _candidate_class(0.2)
        child = cls.random(random.Random(1)).mutate(random.Random(2))
        self.assertIs(type(child), cls)

    def test_the_sigma_is_range_checked(self):
        for bad in (0.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                _candidate_class(bad)

    def test_a_larger_sigma_moves_integrity_further(self):
        parent = _latent((0.4, 0.4, 0.4, 0.4, 0.4), 0.5)
        def spread(sigma):
            cls = _candidate_class(sigma)
            reborn = cls(parent.traits)
            rng = random.Random(11)
            moves = [
                abs(reborn.mutate(rng).traits[LATENT_INDEX] - 0.5) for _ in range(400)
            ]
            return sum(moves) / len(moves)
        self.assertLess(spread(0.05), spread(0.40))


class TheConstructionMatchesTheClaim(unittest.TestCase):
    """The numbers the write-up leans on, recomputed rather than quoted."""

    def test_the_base_rate_is_one_minus_the_floor_by_construction(self):
        cls = _candidate_class(INTEGRITY_SIGMA_DEFAULT)
        rng = random.Random(20260830)
        draws = [cls.random(rng) for _ in range(40000)]
        rate = sum(latent_viable(c) for c in draws) / len(draws)
        self.assertAlmostEqual(rate, 1.0 - MIN_INTEGRITY, delta=0.01)

    def test_the_matched_sigma_reproduces_the_original_heritability(self):
        claimed = LANDSCAPE_PROVENANCE["held_fixed"][
            "heritability_p_child_viable_given_parent_viable"
        ]
        cls = _candidate_class(INTEGRITY_SIGMA_HERITABILITY_MATCHED)
        rng = random.Random(4242)
        mutation_rng = random.Random(2424)
        kept = parents = 0
        for _ in range(40000):
            parent = cls.random(rng)
            if not latent_viable(parent):
                continue
            parents += 1
            kept += latent_viable(parent.mutate(mutation_rng))
        self.assertGreater(parents, 5000)
        self.assertAlmostEqual(
            kept / parents, claimed["original_measured"], delta=0.015
        )

    def test_the_default_sigma_is_the_shared_trait_sigma(self):
        """The default must add no constant the original model did not have."""
        signature = sim.Candidate.mutate.__defaults__
        self.assertEqual(signature, (INTEGRITY_SIGMA_DEFAULT,))

    def test_the_auroc_helper_is_the_statistic_e027_reports(self):
        positive = [0.9, 0.5, 0.5, 0.2]
        negative = [0.5, 0.4, 0.1]
        self.assertAlmostEqual(
            _auroc(positive, negative), e027._roc_auc(positive, negative), places=12
        )

    def test_the_auroc_is_a_half_on_an_uninformative_score(self):
        self.assertAlmostEqual(_auroc([1.0] * 20, [1.0] * 20), 0.5, places=12)


class ParityReport(unittest.TestCase):
    def test_parity_measures_both_landscapes_and_only_the_auroc_moves(self):
        report = parity(samples=30000, seed=99)
        self.assertEqual(report["experiment_id"], EXPERIMENT_ID)
        original, latent = report["measurements"]
        self.assertEqual(original["landscape"], "original")
        self.assertEqual(latent["landscape"], "latent-defect")

        # Held fixed: difficulty.
        self.assertAlmostEqual(
            original["base_viability_rate"], latent["base_viability_rate"], delta=0.02
        )
        # Deliberately not held fixed at the default sigma, and in the
        # direction that helps the arms rather than the conclusion.
        self.assertGreater(
            latent["heritability"]["value"], original["heritability"]["value"]
        )
        # The one intended change.
        self.assertGreater(
            original["apparent_quality_as_viability_classifier"]["auroc"], 0.70
        )
        self.assertAlmostEqual(
            latent["apparent_quality_as_viability_classifier"]["auroc"],
            0.5,
            delta=0.02,
        )

    def test_parity_leaves_no_landscape_installed(self):
        before = (sim.Candidate, sim.viable, arena_sim.Candidate, arena_sim.viable)
        parity(samples=2000, seed=1)
        self.assertEqual(
            before, (sim.Candidate, sim.viable, arena_sim.Candidate, arena_sim.viable)
        )


class PairedMatrix(unittest.TestCase):
    def test_the_control_column_is_a_live_e027_run(self):
        """The original half must equal a bare E027 matrix, not a stored copy."""
        arguments = dict(
            seeds=3, seed_start=0, agents=8, generations=6, change_at=3, bins=4,
            panels=("stress",), costs=(1.0,),
        )
        paired = matrix(**arguments)
        control = e027.matrix(**arguments)
        for strategy in STRATEGIES:
            self.assertEqual(
                paired["cells"][0]["catastrophic_seeds"][strategy]["original"],
                control["cells"][0]["catastrophic_seeds"][strategy],
            )
            self.assertTrue(
                math.isclose(
                    paired["cells"][0]["post_change_utility_auc"][strategy]["original"],
                    control["cells"][0]["post_change_utility_auc"][strategy],
                    rel_tol=1e-9,
                )
            )

    def test_the_matrix_declares_the_landscape_and_its_limits(self):
        report = matrix(
            seeds=3, seed_start=0, agents=8, generations=6, change_at=3, bins=4,
            panels=("stress",), costs=(1.0,),
        )
        self.assertEqual(report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(
            report["configuration"]["reused_from"],
            "sim.e027_defect_propagation.matrix",
        )
        self.assertEqual(
            report["configuration"]["integrity_sigma"], INTEGRITY_SIGMA_DEFAULT
        )
        self.assertIn("landscape_provenance", report)
        joined = " ".join(report["limitations"]).lower()
        self.assertIn("synthetic", joined)
        self.assertIn("not independent evidence", joined)

    def test_a_perfect_panel_stays_a_null_control_on_the_new_landscape(self):
        """No false accepts means no defects, whatever decides viability."""
        report = matrix(
            seeds=3, seed_start=0, agents=8, generations=6, change_at=3, bins=4,
            panels=("perfect",), costs=(0.0, 1.0),
        )
        for cell in report["cells"]:
            for strategy in STRATEGIES:
                self.assertEqual(
                    cell["delivered_defect_rate"][strategy]["latent"], 0.0
                )


REFERENCE = dict(agents=50, generations=50, change_at=25, bins=8)

# E027's published audit figure for seed 7 under the stress panel at cost 1.0.
# experiments/E027-defect-propagation.md quotes 0.937387 and the caveat that
# bounds E027's whole conclusion rests on it.
E027_PUBLISHED_POOLED_AUROC = 0.937387


class ThePoolingDiagnostic(unittest.TestCase):
    """Whether E027's AUROC is a landscape property or an artifact of drift."""

    def test_the_diagnostic_replays_e027s_own_arm(self):
        """Same accepted candidates, not a second implementation of the loop.

        If the diagnostic drifted from the arm it claims to replay, its AUROC
        would describe a run nobody else ever performs.
        """
        arguments = dict(**REFERENCE, panel="stress", defect_cost=1.0)
        diagnostic = quality_viability_diagnostic(7, **arguments)
        reference = e027.audit_qd_defects(
            7, **REFERENCE, verification=e027.PANELS["stress"],
            defect=DefectChannel(cost=1.0),
        )["selection_as_free_verifier"]
        self.assertEqual(
            diagnostic["accepted_viable"], reference["accepted_viable"]
        )
        self.assertEqual(
            diagnostic["accepted_defects"], reference["accepted_defects"]
        )
        self.assertTrue(
            math.isclose(
                diagnostic["pooled_auroc"]["value"],
                reference["auroc"],
                rel_tol=1e-9,
            )
        )

    def test_the_pooled_figure_is_the_one_e027_published(self):
        diagnostic = quality_viability_diagnostic(
            7, **REFERENCE, panel="stress", defect_cost=1.0
        )
        self.assertTrue(
            math.isclose(
                diagnostic["pooled_auroc"]["value"],
                E027_PUBLISHED_POOLED_AUROC,
                rel_tol=1e-9,
            ),
            diagnostic["pooled_auroc"],
        )

    def test_stratifying_does_not_explain_away_e027s_separation(self):
        """The caveat on E027 survives conditioning on generation."""
        diagnostic = quality_viability_diagnostic(
            7, **REFERENCE, panel="stress", defect_cost=1.0
        )
        self.assertGreater(diagnostic["generation_stratified_auroc"]["value"], 0.80)

    def test_the_latent_landscape_removes_most_of_the_separation(self):
        with latent_defect_landscape():
            diagnostic = quality_viability_diagnostic(
                7, **REFERENCE, panel="stress", defect_cost=1.0
            )
        self.assertLess(diagnostic["generation_stratified_auroc"]["value"], 0.62)

    def test_a_truth_blind_panel_isolates_where_the_residual_comes_from(self):
        """The control that separates landscape leakage from panel leakage.

        A panel at chance accepts independently of ground truth. On the
        original landscape the separation must survive that, because it is a
        property of the landscape. On the latent landscape it must collapse to
        chance, because there the only thing that could have produced a
        residual was a panel better than chance.
        """
        arguments = dict(**REFERENCE, panel="truth-blind", defect_cost=1.0)
        original = quality_viability_diagnostic(7, **arguments)
        with latent_defect_landscape():
            latent = quality_viability_diagnostic(7, **arguments)
        self.assertGreater(original["generation_stratified_auroc"]["value"], 0.80)
        self.assertAlmostEqual(
            latent["generation_stratified_auroc"]["value"], 0.5, delta=0.06
        )

    def test_the_truth_blind_panel_really_is_blind(self):
        self.assertEqual(TRUTH_BLIND_PANEL.accuracy, 0.5)
        self.assertEqual(TRUTH_BLIND_PANEL.blind_spot, 0.0)
        self.assertIn("truth-blind", DIAGNOSTIC_PANELS)
        self.assertNotIn("truth-blind", e027.PANELS)

    def test_an_undefined_auroc_is_reported_as_undefined(self):
        """Zero accepted defects means nothing to separate, not perfect inversion."""
        self.assertIsNone(_auroc_or_none([1.0, 2.0], []))
        self.assertIsNone(_auroc_or_none([], [1.0]))
        with latent_defect_landscape():
            diagnostic = quality_viability_diagnostic(
                7, **REFERENCE, panel="independent", defect_cost=1.0
            )
        self.assertEqual(diagnostic["accepted_defects"], 0)
        self.assertIsNone(diagnostic["pooled_auroc"]["value"])
        self.assertIsNone(diagnostic["generation_stratified_auroc"]["value"])

    def test_the_report_is_json_serialisable(self):
        """A NaN would emit invalid JSON that every reader silently mis-parses."""
        with latent_defect_landscape():
            diagnostic = quality_viability_diagnostic(
                7, agents=8, generations=6, change_at=3, bins=4,
                panel="independent", defect_cost=1.0,
            )
        encoded = json.dumps(diagnostic, allow_nan=False)
        self.assertNotIn("NaN", encoded)


class DeterminismAndCli(unittest.TestCase):
    def test_the_audit_reproduces_run_for_run(self):
        arguments = dict(
            agents=8, generations=6, change_at=3, bins=4,
            panel="stress", defect_cost=1.0,
        )
        self.assertEqual(audit(7, **arguments), audit(7, **arguments))

    def test_the_audit_records_the_landscape_it_ran_on(self):
        report = audit(
            7, agents=8, generations=6, change_at=3, bins=4,
            panel="stress", defect_cost=1.0,
        )
        self.assertEqual(report["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(report["landscape"], "latent-defect")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "sim/e028_latent_defect_dimension.py", *args],
            capture_output=True, text=True, cwd=ROOT,
            env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
        )

    def test_the_parity_mode_runs_from_the_command_line(self):
        completed = self._run("--mode", "parity", "--samples", "2000")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(len(payload["measurements"]), 2)

    def test_the_diagnostic_mode_reports_both_landscapes(self):
        completed = self._run(
            "--mode", "diagnostic", "--seed", "7", "--panel", "truth-blind",
            "--agents", "8", "--generations", "6", "--change-at", "3", "--bins", "4",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            [m["landscape"] for m in payload["measurements"]],
            ["original", "latent-defect"],
        )

    def test_the_truth_blind_control_is_rejected_outside_the_diagnostic(self):
        completed = self._run("--mode", "audit", "--panel", "truth-blind")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("diagnostic-only", completed.stderr)

    def test_the_sigma_is_range_checked_on_the_command_line(self):
        completed = self._run("--mode", "parity", "--integrity-sigma", "0")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("integrity-sigma", completed.stderr)


if __name__ == "__main__":
    unittest.main()
