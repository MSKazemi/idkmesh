"""E027: an accepted defect must be able to persist and do harm.

E026's load-bearing negative result is that E024 has *no* defect-propagation
channel: `utility()` and `robust_quality()` both consult `viable()` directly, so
a falsely accepted artifact scores 0.0 and is discarded by the very predicate
the verifier panel was meant to enforce. E027 adds an opt-in channel that
removes that free oracle.

Four properties are pinned here, because each of them is a way the channel
could be quietly wrong:

1. the matched evaluation budget survives with the channel armed;
2. defect cost 0.0 reproduces the channel-off behaviour exactly;
3. a defective artifact demonstrably persists and harms when the cost is not 0;
4. everything stays deterministic from the seed.

Recomputed sweeps are never compared byte-for-byte: the simulators go through
`exp` and `**`, whose last-place rounding differs across CPUs and C libraries.
Committed artifacts are pinned by sha256 or compared with `math.isclose`.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

import sim.emergence_sim as sim
from sim.e027_defect_propagation import (
    COSTS,
    PANEL_ORDER,
    PANELS,
    audit_qd_defects,
    matrix,
)
from sim.matched_budget_emergence import (
    DEFECT_METRICS,
    DEFECT_PROVENANCE,
    STRATEGIES,
    DefectChannel,
    _apparent_robust_quality,
    _apparent_utility,
    _deliver,
    measured_panel,
    run_seed,
    sweep,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"
REFERENCE = dict(agents=50, generations=50, change_at=25, bins=8)
SMALL = dict(agents=12, generations=10, change_at=5, bins=4)
STRESS = PANELS["stress"]

# A pair chosen so the ordering is decided by the channel and nothing else:
# the defective candidate has no security at all, so it is non-viable, but its
# observable traits make it look better than the viable incumbent.
DEFECTIVE = sim.Candidate((0.10, 0.95, 0.95, 0.95, 0.10))
INCUMBENT = sim.Candidate((0.30, 0.30, 0.30, 0.30, 0.30))


class ExtractedHelpersAreTheOldArithmetic(unittest.TestCase):
    """The unchecked helpers were split out of the gated ones, not rewritten."""

    def test_unchecked_helpers_match_the_gated_ones_on_viable_candidates(self):
        self.assertTrue(sim.viable(INCUMBENT))
        for weights in sim.PLAUSIBLE_GOALS:
            self.assertEqual(
                sim.unchecked_utility(INCUMBENT, weights),
                sim.utility(INCUMBENT, weights),
            )
        self.assertEqual(
            sim.unchecked_robust_quality(INCUMBENT), sim.robust_quality(INCUMBENT)
        )

    def test_unchecked_helpers_still_score_a_non_viable_candidate(self):
        self.assertFalse(sim.viable(DEFECTIVE))
        self.assertEqual(sim.utility(DEFECTIVE, sim.INITIAL_GOAL), 0.0)
        self.assertEqual(sim.robust_quality(DEFECTIVE), 0.0)
        # The whole point: the defect is not worthless to a system that cannot
        # see viability, it is the best-looking thing in the room.
        self.assertGreater(sim.unchecked_robust_quality(DEFECTIVE), 0.0)
        self.assertGreater(
            sim.unchecked_robust_quality(DEFECTIVE), sim.robust_quality(INCUMBENT)
        )


class DefectCostZeroIsTheOldBehaviour(unittest.TestCase):
    def test_apparent_scores_collapse_onto_the_gated_ones_at_cost_zero(self):
        for candidate in (DEFECTIVE, INCUMBENT):
            for weights in sim.PLAUSIBLE_GOALS:
                self.assertEqual(
                    _apparent_utility(candidate, weights, 0.0),
                    sim.utility(candidate, weights),
                )
            self.assertEqual(
                _apparent_robust_quality(candidate, 0.0), sim.robust_quality(candidate)
            )

    def test_delivery_at_cost_zero_is_the_old_best_actual(self):
        population = [DEFECTIVE, INCUMBENT]
        for goal in sim.PLAUSIBLE_GOALS:
            value, _ = _deliver(population, goal, 0.0)
            self.assertEqual(value, sim._best_actual(population, goal))
        self.assertEqual(_deliver([], sim.INITIAL_GOAL, 0.0), (0.0, None))

    def test_armed_at_cost_zero_reproduces_the_channel_off_run_exactly(self):
        # Same process, same machine, same code path, so exact equality is the
        # right assertion here -- this is not a cross-platform recomputation.
        for panel in (sim.VerificationConfig(), measured_panel(), STRESS):
            off = run_seed(7, verification=panel, **SMALL)
            armed = run_seed(
                7, verification=panel, defect=DefectChannel(cost=0.0), **SMALL
            )
            self.assertNotIn("defect_channel", off)
            self.assertEqual(armed["defect_channel"]["cost"], 0.0)
            off_rows = {row["strategy"]: row for row in off["results"]}
            armed_rows = {row["strategy"]: row for row in armed["results"]}
            for strategy in STRATEGIES:
                for key, value in off_rows[strategy].items():
                    self.assertEqual(
                        value, armed_rows[strategy][key], f"{panel} {strategy} {key}"
                    )

    def test_a_perfect_panel_makes_the_cost_irrelevant(self):
        # A panel that never accepts a non-viable candidate never creates a
        # defect, so the knob has nothing to act on. This is the null control.
        baseline = run_seed(3, defect=DefectChannel(cost=0.0), **SMALL)
        for cost in COSTS:
            armed = run_seed(3, defect=DefectChannel(cost=cost), **SMALL)
            self.assertEqual(
                [row["post_change_utility_auc"] for row in armed["results"]],
                [row["post_change_utility_auc"] for row in baseline["results"]],
            )


class MatchedBudgetSurvivesTheChannel(unittest.TestCase):
    def test_every_arm_spends_the_same_units_at_every_cost(self):
        expected = SMALL["agents"] * SMALL["generations"]
        for cost in COSTS:
            for panel in (sim.VerificationConfig(), measured_panel(), STRESS):
                result = run_seed(
                    9, verification=panel, defect=DefectChannel(cost=cost), **SMALL
                )
                contract = result["budget_contract"]
                self.assertEqual(contract["per_strategy"], expected)
                self.assertIs(contract["retry_until_acceptance"], False)
                self.assertEqual(
                    contract["verifier_votes_per_strategy"],
                    expected * panel.verifiers,
                )
                for row in result["results"]:
                    self.assertEqual(row["proposal_attempts"], expected)
                    self.assertEqual(row["verification_attempts"], expected)
                    self.assertEqual(row["matched_evaluation_budget"], expected)
                    self.assertEqual(row["bootstrap_anchors"], 0)

    def test_the_channel_consumes_no_extra_randomness(self):
        # The channel only re-ranks what verification already produced, so the
        # verifier stream must be untouched: identical accept counts at every
        # cost for the arms whose proposals do not depend on what they retain.
        accepts = [
            {
                row["strategy"]: row["verification_accepts"]
                for row in run_seed(
                    4,
                    verification=STRESS,
                    defect=DefectChannel(cost=cost),
                    **SMALL,
                )["results"]
            }
            for cost in COSTS
        ]
        self.assertEqual({a["random"] for a in accepts}, {accepts[0]["random"]})


class DefectsPersistAndDoHarm(unittest.TestCase):
    def test_a_defect_can_evict_a_viable_incumbent_only_when_the_cost_is_armed(self):
        self.assertGreater(
            _apparent_robust_quality(DEFECTIVE, 1.0),
            _apparent_robust_quality(INCUMBENT, 1.0),
        )
        self.assertLess(
            _apparent_robust_quality(DEFECTIVE, 0.0),
            _apparent_robust_quality(INCUMBENT, 0.0),
        )

    def test_a_shipped_defect_delivers_nothing(self):
        value, chosen = _deliver([INCUMBENT, DEFECTIVE], sim.INITIAL_GOAL, 1.0)
        self.assertIs(chosen, DEFECTIVE)
        self.assertEqual(value, 0.0)
        value, chosen = _deliver([INCUMBENT, DEFECTIVE], sim.INITIAL_GOAL, 0.0)
        self.assertIs(chosen, INCUMBENT)
        self.assertGreater(value, 0.0)

    def test_defects_reach_the_qd_archive_only_with_the_channel_armed(self):
        disarmed = audit_qd_defects(
            7, verification=STRESS, defect=DefectChannel(cost=0.0), **REFERENCE
        )
        armed = audit_qd_defects(
            7, verification=STRESS, defect=DefectChannel(cost=1.0), **REFERENCE
        )
        # E026's finding, reproduced, and sharpened. Defects did already drop
        # into *empty* niches under E024/E026 -- `incumbent is None` accepts
        # unconditionally -- but with the free oracle in place they were worth
        # 0.0, so they never displaced a real solution and never shipped.
        self.assertGreater(disarmed["accepted_but_non_viable"], 0)
        self.assertGreater(disarmed["defects_entered_archive"], 0)
        self.assertEqual(disarmed["defects_evicting_a_viable_incumbent"], 0)
        self.assertEqual(disarmed["generations_delivering_a_defect"], 0)
        self.assertEqual(disarmed["non_viable_in_final_archive"], 0)
        # E027's channel: they now evict real solutions, and they ship.
        self.assertGreater(armed["defects_evicting_a_viable_incumbent"], 0)
        self.assertGreater(armed["generations_delivering_a_defect"], 0)
        self.assertGreater(
            armed["peak_defects_in_archive"], disarmed["peak_defects_in_archive"]
        )

    def test_an_arm_is_measurably_hurt_by_the_channel(self):
        # The teeth check. Without this the "QD survives" reading would be
        # indistinguishable from E026's null.
        rows = {
            cost: {
                row["strategy"]: row["post_change_utility_auc"]
                for row in run_seed(
                    7, verification=STRESS, defect=DefectChannel(cost=cost), **REFERENCE
                )["results"]
            }
            for cost in (0.0, 1.0)
        }
        self.assertLess(rows[1.0]["random"], rows[0.0]["random"] - 1.0)

    def test_defect_metrics_appear_only_when_the_channel_is_armed(self):
        off = run_seed(5, verification=measured_panel(), **SMALL)
        armed = run_seed(
            5, verification=measured_panel(), defect=DefectChannel(cost=1.0), **SMALL
        )
        for row in off["results"]:
            for metric in DEFECT_METRICS:
                self.assertNotIn(metric, row)
        for row in armed["results"]:
            for metric in DEFECT_METRICS:
                self.assertIn(metric, row)
            self.assertGreaterEqual(row["retained_defects"], 0)
            self.assertLessEqual(row["retained_defects"], row["retained_artifacts"])


class DeterminismAndValidation(unittest.TestCase):
    def test_a_seed_reproduces_run_for_run(self):
        first = run_seed(
            7, verification=STRESS, defect=DefectChannel(cost=0.7), **SMALL
        )
        second = run_seed(
            7, verification=STRESS, defect=DefectChannel(cost=0.7), **SMALL
        )
        self.assertEqual(first, second)

    def test_the_audit_reproduces_run_for_run(self):
        kwargs = dict(verification=STRESS, defect=DefectChannel(cost=1.0), **REFERENCE)
        self.assertEqual(audit_qd_defects(7, **kwargs), audit_qd_defects(7, **kwargs))

    def test_the_cost_is_bounded(self):
        for cost in (-0.01, 1.01):
            with self.assertRaises(ValueError):
                DefectChannel(cost=cost)

    def test_the_default_cost_is_the_assumption_free_end(self):
        self.assertEqual(DefectChannel().cost, 1.0)
        self.assertEqual(DEFECT_PROVENANCE["default_cost"], 1.0)
        self.assertIn("no defect cost is measured", DEFECT_PROVENANCE["evidence_level"])


class SweepReporting(unittest.TestCase):
    def test_an_armed_sweep_declares_the_knob_and_aggregates_defect_metrics(self):
        report = sweep(
            seeds=3,
            seed_start=0,
            verification=measured_panel(),
            defect=DefectChannel(cost=1.0),
            **SMALL,
        )
        configuration = report["configuration"]
        self.assertEqual(configuration["defect_channel"]["cost"], 1.0)
        self.assertEqual(configuration["defect_provenance"], DEFECT_PROVENANCE)
        for strategy in STRATEGIES:
            for metric in DEFECT_METRICS:
                self.assertEqual(report["aggregate"][strategy][metric]["n"], 3)
        self.assertTrue(
            any("swept dial" in text or "swept across its whole range" in text
                for text in report["limitations"])
        )
        self.assertTrue(
            any("not measured" in text or "not modelled" in text
                for text in report["limitations"])
        )

    def test_a_perfect_panel_with_the_channel_still_reports_catastrophes(self):
        report = sweep(
            seeds=3, seed_start=0, defect=DefectChannel(cost=1.0), **SMALL
        )
        self.assertIn("catastrophic_seeds", report)
        # No imperfect panel means no panel provenance and no panel caveats.
        self.assertNotIn("panel_provenance", report["configuration"])
        self.assertFalse(
            any("blind-spot" in text for text in report["limitations"])
        )

    def test_a_disarmed_sweep_keeps_the_published_schema(self):
        report = sweep(seeds=3, seed_start=0, **SMALL)
        self.assertNotIn("catastrophic_seeds", report)
        self.assertNotIn("defect_channel", report["configuration"])
        for strategy in STRATEGIES:
            for metric in DEFECT_METRICS:
                self.assertNotIn(metric, report["aggregate"][strategy])


class MatrixDriver(unittest.TestCase):
    def test_the_matrix_sweeps_the_knob_including_zero(self):
        self.assertEqual(COSTS[0], 0.0)
        self.assertEqual(COSTS[-1], 1.0)
        self.assertEqual(PANEL_ORDER[0], "perfect")
        report = matrix(
            seeds=2,
            seed_start=0,
            panels=("perfect", "stress"),
            costs=(0.0, 1.0),
            **SMALL,
        )
        self.assertEqual(len(report["cells"]), 4)
        for cell in report["cells"]:
            self.assertIn(cell["panel"], ("perfect", "stress"))
            self.assertEqual(set(cell["post_change_utility_auc"]), set(STRATEGIES))
            self.assertEqual(set(cell["catastrophic_seeds"]), set(STRATEGIES))
        self.assertEqual(
            report["configuration"]["defect_provenance"], DEFECT_PROVENANCE
        )
        self.assertTrue(report["limitations"])


class CommittedArtifacts(unittest.TestCase):
    def test_the_e024_reference_sweep_is_unchanged(self):
        # Pinning the committed file's own digest, not a recomputation: the
        # default must stay perfect-panel, channel-off, byte-for-byte.
        path = RESULTS / "E024-matched-budget-emergence-100-seed-summary.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "c261193d2282a8822fc2a3ae1934a7ad1494803930af27b9601e02fedbe17b8a",
        )
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("defect_channel", result["configuration"])
        self.assertNotIn("catastrophic_seeds", result)

    def test_the_committed_defect_channel_sweep_is_armed_and_honest(self):
        path = RESULTS / "E027-defect-channel-100-seed-summary.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        configuration = result["configuration"]
        self.assertEqual(configuration["seeds"], 100)
        self.assertEqual(configuration["defect_channel"]["cost"], 1.0)
        self.assertEqual(
            configuration["verification"], measured_panel().as_dict()
        )
        self.assertEqual(configuration["defect_provenance"], DEFECT_PROVENANCE)
        for strategy in STRATEGIES:
            for metric in DEFECT_METRICS:
                self.assertEqual(result["aggregate"][strategy][metric]["n"], 100)
        self.assertTrue(
            any("synthetic mechanism" in text for text in result["limitations"])
        )

    def test_the_committed_sensitivity_matrix_spans_panels_and_costs(self):
        path = RESULTS / "E027-defect-cost-sensitivity.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["experiment_id"], "E027")
        self.assertEqual(result["configuration"]["seeds"], 100)
        self.assertEqual(result["configuration"]["defect_costs"], list(COSTS))
        cells = {(cell["panel"], cell["defect_cost"]): cell for cell in result["cells"]}
        self.assertEqual(len(cells), len(PANEL_ORDER) * len(COSTS))
        # The knob must not be a free parameter: the zero column reproduces the
        # E024/E026 behaviour, and E026's own null is recoverable from it.
        e026 = json.loads(
            (RESULTS / "E024-imperfect-panel-100-seed-summary.json").read_text(
                encoding="utf-8"
            )
        )
        for strategy in STRATEGIES:
            self.assertTrue(
                math.isclose(
                    cells[("measured", 0.0)]["post_change_utility_auc"][strategy],
                    e026["aggregate"][strategy]["post_change_utility_auc"]["mean"],
                    rel_tol=1e-9,
                ),
                strategy,
            )
            self.assertEqual(
                cells[("measured", 0.0)]["catastrophic_seeds"][strategy],
                e026["catastrophic_seeds"]["by_strategy"][strategy]["seeds"],
            )
        # The channel has teeth somewhere, which is what licenses reading a
        # survival anywhere else as robustness rather than as another null.
        hurt = [
            strategy
            for strategy in STRATEGIES
            if cells[("stress", 1.0)]["catastrophic_seeds"][strategy]
            > cells[("stress", 0.0)]["catastrophic_seeds"][strategy]
        ]
        self.assertTrue(hurt, "the defect channel changed nothing anywhere")
        # A perfect panel creates no defect for the channel to propagate.
        for cost in COSTS:
            self.assertEqual(
                cells[("perfect", cost)]["post_change_utility_auc"],
                cells[("perfect", 0.0)]["post_change_utility_auc"],
            )


    def test_the_committed_threshold_grid_resolves_the_response_curve(self):
        # The coarse matrix only shows that the response lives above cost 0.75.
        # This artifact is what turns "a step" into a measured curve, and the
        # write-up quotes it, so its shape is pinned here.
        path = RESULTS / "E027-defect-cost-threshold.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["configuration"]["seeds"], 100)
        self.assertEqual(result["configuration"]["defect_costs"], [0.8, 0.85, 0.9, 0.95])
        cells = sorted(result["cells"], key=lambda cell: cell["defect_cost"])
        self.assertEqual([cell["panel"] for cell in cells], ["stress"] * 4)
        shipped = [cell["delivered_defect_rate"]["random"] for cell in cells]
        self.assertEqual(shipped, sorted(shipped))
        self.assertGreater(shipped[-1], shipped[0])
        catastrophes = [cell["catastrophic_seeds"]["random"] for cell in cells]
        self.assertEqual(catastrophes, sorted(catastrophes))
        # The point of the artifact: harm rises smoothly rather than switching
        # on only at the endpoint, and the archive is unharmed throughout.
        self.assertGreater(catastrophes[-1], 0)
        for cell in cells:
            self.assertEqual(cell["catastrophic_seeds"]["qd"], 0)


class CommandLineContract(unittest.TestCase):
    MODULE = ROOT / "sim" / "matched_budget_emergence.py"

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(self.MODULE), *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    def test_defect_cost_requires_the_channel_switch(self):
        completed = self._run("--seeds", "2", "--defect-cost", "0.5")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--defect-channel", completed.stderr)

    def test_defect_cost_is_range_checked(self):
        completed = self._run(
            "--seeds", "2", "--defect-channel", "--defect-cost", "1.5"
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--defect-cost", completed.stderr)

    def test_the_channel_is_off_unless_asked_for(self):
        completed = self._run(
            "--seeds", "2", "--agents", "6", "--generations", "6", "--change-at", "3",
            "--bins", "3",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertNotIn("defect_channel", report["configuration"])

    def test_arming_the_channel_records_it(self):
        completed = self._run(
            "--seeds", "2", "--agents", "6", "--generations", "6", "--change-at", "3",
            "--bins", "3", "--defect-channel",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["configuration"]["defect_channel"]["cost"], 1.0)


if __name__ == "__main__":
    unittest.main()
