"""Fast tests for E051: the marginal-evidence selector against a known synthetic truth.

What these pin, in order of importance:

1. the controls the issue asks for. An *exact duplicate* of an admitted verifier
   must not be scored as a gain, and a panel-mimic (a verifier whose verdicts equal
   the current panel's decisions) must change no decision and score exactly zero
   panel-error change, while an independent informative verifier scores positive;
2. the study runs the repository's own ``marginal_evidence_benchmark`` and not a
   re-implementation, and the design-only shortcut it uses equals the full held-out
   benchmark's frozen selection;
3. the memoised ``majority_error_independent`` is bit-for-bit the original and is
   always restored;
4. the aggregation arithmetic (abstain counts as zero, regret, paired difference);
5. the committed result is internally consistent. Re-deriving it is a ``sim`` test
   in ``test_e051_committed_artifact.py``.

Everything is synthetic. Nothing here says anything about real verifiers.
"""

from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path

import sim.e051_marginal_selector_sweep as e051
from idkmesh import gate_audit, marginal_evidence
from idkmesh import marginal_evidence_benchmark as meb

if importlib.util.find_spec("pytest") is not None:
    import pytest

    # Research-artifact test: runs in the emergence-sim workflow and nightly, not on
    # the per-PR unit tier (docs/TESTING.md: experiment tests carry `sim`).
    pytestmark = pytest.mark.sim
else:  # pragma: no cover - bare-interpreter jobs take this path
    pass


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments" / "results" / "E051-marginal-selector-sweep.json"


def _matrix(rows: int, *, panel_size: int, shared: float, pool: str, key: str):
    rng = e051._rng("test", key, rows, panel_size, shared, pool)
    truth, errors = e051.sample_error_matrix(
        rng, rows=rows, panel_size=panel_size, shared_weight=shared, pool=pool
    )
    return truth, errors


class GeneratorTests(unittest.TestCase):
    def test_same_key_same_matrix_and_different_key_differs(self):
        a = _matrix(200, panel_size=3, shared=0.2, pool="mixed", key="a")
        again = _matrix(200, panel_size=3, shared=0.2, pool="mixed", key="a")
        other = _matrix(200, panel_size=3, shared=0.2, pool="mixed", key="b")
        self.assertEqual(a, again)
        self.assertNotEqual(a, other)

    def test_exact_duplicate_has_identical_verdicts_to_its_reference(self):
        _, errors = _matrix(500, panel_size=3, shared=0.2, pool="mixed", key="dup")
        self.assertEqual(errors["cand-dup"], errors["cur-1"])

    def test_invalid_parameters_are_refused(self):
        rng = e051._rng("x")
        with self.assertRaises(e051.SweepInputError):
            e051.sample_error_matrix(rng, rows=0, panel_size=3, shared_weight=0.2, pool="mixed")
        with self.assertRaises(e051.SweepInputError):
            e051.sample_error_matrix(rng, rows=10, panel_size=5, shared_weight=0.2, pool="mixed")
        with self.assertRaises(e051.SweepInputError):
            e051.sample_error_matrix(rng, rows=10, panel_size=3, shared_weight=1.5, pool="mixed")
        with self.assertRaises(e051.SweepInputError):
            e051.sample_error_matrix(rng, rows=10, panel_size=3, shared_weight=0.2, pool="nope")
        with self.assertRaises(e051.SweepInputError):
            e051.panel_error([True], {}, [])

    def test_design_matrix_does_not_depend_on_holdout_size(self):
        kwargs = dict(
            panel_size=3, shared_weight=0.2, pool="mixed", n_design=30, replicate=1, seed=5
        )
        d1, h1, _ = e051.draw_cell_matrices(holdout_rows=40, **kwargs)
        d2, h2, _ = e051.draw_cell_matrices(holdout_rows=80, **kwargs)
        self.assertEqual(d1, d2)
        self.assertNotEqual(h1, h2)
        # Design and holdout carry disjoint candidate ids, which the benchmark requires.
        design_ids = {c["id"] for c in d1["candidates"]}
        holdout_ids = {c["id"] for c in h1["candidates"]}
        self.assertFalse(design_ids & holdout_ids)

    def test_panel_error_agrees_with_gate_audit(self):
        truth, errors = _matrix(300, panel_size=4, shared=0.2, pool="mixed", key="ga")
        members = e051.current_ids(4)
        data = e051.build_matrix(truth, errors, gate_id="g", prefix="r")
        subset = dict(data)
        subset["verifiers"] = [v for v in data["verifiers"] if v["id"] in members]
        report = gate_audit.audit(subset)
        self.assertAlmostEqual(
            report["panel"]["error"], e051.panel_error(truth, errors, members), places=12
        )


class ControlTests(unittest.TestCase):
    """The duplicate and independent controls, on a large enough sample to be stable."""

    ROWS = 6000

    def _analysis(self, panel_size: int):
        truth, errors = _matrix(
            self.ROWS, panel_size=panel_size, shared=0.2, pool="mixed", key="ctl"
        )
        members = e051.current_ids(panel_size)
        decisions_wrong = []
        for row, is_accept in enumerate(truth):
            accepts = sum(1 for m in members if is_accept != errors[m][row])
            decision = accepts > e051.QUORUM * len(members)
            decisions_wrong.append(decision != is_accept)
        # A verifier whose verdict equals the current panel's decision on every task.
        errors = dict(errors)
        errors["cand-mimic"] = list(decisions_wrong)
        data = e051.build_matrix(truth, errors, gate_id="ctl", prefix="r")
        with e051.memoized_majority_error():
            report = marginal_evidence.analyze(
                data,
                current_verifier_ids=members,
                candidate_verifier_ids=[
                    "cand-dup",
                    "cand-mimic",
                    "cand-indep_strong",
                    "cand-harmful",
                ],
            )
        return {row["id"][5:]: row for row in report["candidates"]}

    def test_panel_mimic_changes_no_decision_in_an_odd_to_odd_style_step(self):
        # 4 -> 5 voters: a verifier equal to the 4-panel's decision cannot flip it.
        rows = self._analysis(4)
        mimic = rows["mimic"]
        self.assertEqual(mimic["transition_counts"]["panel_decisions_changed"], 0)
        self.assertEqual(mimic["panel_error_delta"], 0.0)

    def test_exact_duplicate_is_not_scored_as_a_gain_and_independent_is(self):
        for panel_size in (3, 4):
            with self.subTest(panel_size=panel_size):
                rows = self._analysis(panel_size)
                dup, strong = rows["dup"], rows["indep_strong"]
                self.assertLessEqual(dup["panel_error_delta"], 0.0)
                self.assertGreater(strong["panel_error_delta"], 0.02)
                self.assertGreater(strong["panel_error_delta"], dup["panel_error_delta"])
                self.assertEqual(dup["mean_error_correlation_with_current_panel"] is None, False)

    def test_effective_vote_delta_does_not_track_panel_error_delta(self):
        # Documented finding, pinned so a change in the metric is noticed: a candidate
        # that is worse than a coin flip and raises panel error still raises the
        # effective-vote count. Panel error delta and effective-vote delta must be
        # read as separate columns, exactly as the report already keeps them.
        rows = self._analysis(4)
        harmful = rows["harmful"]
        self.assertLess(harmful["panel_error_delta"], 0.0)
        self.assertGreater(harmful["delta_effective_votes"], rows["dup"]["delta_effective_votes"])


class MemoizationTests(unittest.TestCase):
    def test_memo_is_bit_identical_and_restored(self):
        original = gate_audit.majority_error_independent
        with e051.memoized_majority_error():
            self.assertIsNot(gate_audit.majority_error_independent, original)
            for n in (1, 3, 5, 51, 201):
                for acc in (0.51, 0.7, 0.8333333333333334, 0.999):
                    self.assertEqual(
                        gate_audit.majority_error_independent(n, acc, 0.5),
                        original(n, acc, 0.5),
                    )
        self.assertIs(gate_audit.majority_error_independent, original)

    def test_memo_is_restored_after_an_exception(self):
        original = gate_audit.majority_error_independent
        with self.assertRaises(RuntimeError):
            with e051.memoized_majority_error():
                raise RuntimeError("boom")
        self.assertIs(gate_audit.majority_error_independent, original)

    def test_cell_selections_do_not_depend_on_the_memo(self):
        kwargs = dict(
            panel_size=3, shared_weight=0.2, pool="redundant_only", n_design=20, replicate=0, seed=2
        )
        plain = e051.run_cell(**kwargs)
        with e051.memoized_majority_error():
            memoised = e051.run_cell(**kwargs)
        self.assertEqual(plain, memoised)


class SelectionTests(unittest.TestCase):
    def test_design_only_shortcut_equals_full_benchmark_selection(self):
        kwargs = dict(
            panel_size=4, shared_weight=0.7, pool="mixed", n_design=40, replicate=3, seed=9
        )
        with e051.memoized_majority_error():
            shortcut = e051.run_cell(**kwargs)
            full = e051.run_cell(full_benchmark=True, **kwargs)
        self.assertEqual(shortcut, full)
        self.assertEqual(set(shortcut["selections"]), set(meb.STRATEGIES))

    def test_every_strategy_is_reported(self):
        self.assertEqual(
            e051.STRATEGIES,
            (
                meb.STRATEGY_MARGINAL,
                meb.STRATEGY_RANDOM,
                meb.STRATEGY_ACCURACY,
                meb.STRATEGY_FAMILY,
                meb.STRATEGY_CORRELATION,
            ),
        )
        self.assertEqual(len(e051.BASELINES), 4)


def _fake_results(choices):
    return [
        {
            "selections": {
                strategy: {"selected": choice, "reason_code": "r"}
                for strategy, choice in row.items()
            }
        }
        for row in choices
    ]


class AggregationTests(unittest.TestCase):
    ORACLE = {"good": 0.05, "meh": 0.004, "bad": -0.05}

    def _row(self, marginal, other):
        row = {strategy: other for strategy in e051.STRATEGIES}
        row[e051.MARGINAL] = marginal
        return row

    def test_abstaining_counts_as_zero_and_regret_uses_the_best_candidate(self):
        results = _fake_results(
            [self._row("good", "bad"), self._row(None, "bad"), self._row("meh", "bad")]
        )
        cell = e051.summarize_cell(results, self.ORACLE)
        marginal = cell["strategies"][e051.MARGINAL]
        self.assertEqual(marginal["selected"], 2)
        self.assertEqual(marginal["abstained"], 1)
        self.assertEqual(marginal["selected_helpful"], 1)
        self.assertEqual(marginal["selected_redundant"], 1)
        self.assertEqual(marginal["selected_harmful"], 0)
        self.assertAlmostEqual(marginal["mean_oracle_delta_abstain_as_zero"], 0.054 / 3)
        self.assertAlmostEqual(marginal["mean_regret_abstain_as_zero"], 0.05 - 0.054 / 3)
        random_row = cell["strategies"][meb.STRATEGY_RANDOM]
        self.assertEqual(random_row["selected_harmful"], 3)
        self.assertEqual(random_row["selected_counts"], {"bad": 3})
        self.assertEqual(
            marginal["abstain_reason_counts"], {"r": 1}
        )

    def test_paired_difference_sign_and_se(self):
        results = _fake_results([self._row("good", "bad"), self._row("good", "bad")])
        diff = e051.paired_difference(results, self.ORACLE, e051.MARGINAL, meb.STRATEGY_RANDOM)
        self.assertAlmostEqual(diff["mean"], 0.10)
        self.assertEqual(diff["se"], 0.0)
        self.assertEqual(diff["n"], 2)

    def test_classification_boundaries(self):
        self.assertEqual(e051.classify(e051.ORACLE_TOLERANCE + 1e-9), "helpful")
        self.assertEqual(e051.classify(e051.ORACLE_TOLERANCE), "redundant")
        self.assertEqual(e051.classify(-e051.ORACLE_TOLERANCE), "redundant")
        self.assertEqual(e051.classify(-e051.ORACLE_TOLERANCE - 1e-9), "harmful")

    def test_empty_results_are_refused(self):
        with self.assertRaises(e051.SweepInputError):
            e051.summarize_cell([], self.ORACLE)


class SweepTests(unittest.TestCase):
    KW = dict(
        seed=3,
        replicates=2,
        n_design=[20],
        regime_ids=["k3-low-mixed", "k4-low-redundant_only"],
        oracle_rows=600,
    )

    def test_report_is_labelled_synthetic_and_diagnostic_only(self):
        report = e051.sweep(**self.KW)
        self.assertEqual(report["evidence_class"], "synthetic")
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(report["schema"], e051.SCHEMA_ID)
        self.assertEqual(report["selection_rule_version"], meb.SELECTION_RULE_VERSION)
        self.assertEqual([r["id"] for r in report["regimes"]], ["k3-low-mixed", "k4-low-redundant_only"])
        self.assertTrue(any("no significance claim" in s for s in report["limitations"]))
        json.dumps(report, allow_nan=False)  # strict JSON: no NaN / Infinity

    def test_report_is_independent_of_worker_count(self):
        serial = e051.sweep(workers=1, **self.KW)
        parallel = e051.sweep(workers=2, **self.KW)
        self.assertEqual(serial, parallel)

    def test_digest_binds_the_body(self):
        report = e051.sweep(**self.KW)
        body = {k: v for k, v in report.items() if k != "digest_sha256"}
        self.assertEqual(report["digest_sha256"], e051._canonical_digest(body))

    def test_bad_arguments_are_refused(self):
        with self.assertRaises(e051.SweepInputError):
            e051.sweep(replicates=0)
        with self.assertRaises(e051.SweepInputError):
            e051.sweep(n_design=[3])
        with self.assertRaises(e051.SweepInputError):
            e051.sweep(workers=0)
        with self.assertRaises(e051.SweepInputError):
            e051.sweep(regime_ids=["no-such-regime"])
        with self.assertRaises(e051.SweepInputError):
            e051.sweep(oracle_rows=10)


class CommittedArtifactConsistencyTests(unittest.TestCase):
    """Arithmetic and structure of the committed record. No simulation is re-run."""

    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_digest_matches_the_body(self):
        body = {k: v for k, v in self.report.items() if k != "digest_sha256"}
        self.assertEqual(self.report["digest_sha256"], e051._canonical_digest(body))

    def test_labels_and_grid(self):
        report = self.report
        self.assertEqual(report["evidence_class"], "synthetic")
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(report["selection_rule_version"], meb.SELECTION_RULE_VERSION)
        self.assertEqual(
            [r["id"] for r in report["regimes"]], [r["id"] for r in e051.regimes()]
        )
        for regime in report["regimes"]:
            self.assertEqual(
                [c["n_design"] for c in regime["cells"]], report["config"]["n_design"]
            )

    def test_counts_add_up_in_every_cell(self):
        replicates = self.report["config"]["replicates"]
        for regime in self.report["regimes"]:
            for cell in regime["cells"]:
                self.assertEqual(cell["replicates"], replicates)
                for name, row in cell["strategies"].items():
                    with self.subTest(regime=regime["id"], n=cell["n_design"], strategy=name):
                        self.assertEqual(row["selected"] + row["abstained"], replicates)
                        self.assertEqual(
                            row["selected_helpful"]
                            + row["selected_redundant"]
                            + row["selected_harmful"],
                            row["selected"],
                        )
                        self.assertEqual(sum(row["selected_counts"].values()), row["selected"])
                        self.assertEqual(
                            sum(row["abstain_reason_counts"].values()), row["abstained"]
                        )
                        self.assertTrue(math.isfinite(row["mean_regret_abstain_as_zero"]))

    def test_random_accuracy_and_family_baselines_never_abstain(self):
        # The correlation baseline can abstain when no pairwise correlation is
        # measurable on tiny design samples, so it is deliberately not in this set.
        for regime in self.report["regimes"]:
            for cell in regime["cells"]:
                for name in (
                    meb.STRATEGY_RANDOM,
                    meb.STRATEGY_ACCURACY,
                    meb.STRATEGY_FAMILY,
                ):
                    self.assertEqual(cell["strategies"][name]["abstained"], 0)

    def test_post_hoc_regimes_are_flagged(self):
        flagged = {r["id"] for r in self.report["regimes"] if r["post_hoc"]}
        self.assertEqual(flagged, {r["id"] for r in e051.regimes() if r["post_hoc"]})
        self.assertTrue(
            all(i.endswith(("no_anti_informative", "accuracy_trap")) for i in flagged)
        )
        self.assertEqual(len(flagged), 8)

    def test_oracle_labels_follow_the_stated_tolerance(self):
        for regime in self.report["regimes"]:
            for cid, entry in regime["oracle"].items():
                self.assertEqual(entry["label"], e051.classify(entry["delta"]), cid)


if __name__ == "__main__":
    unittest.main()
