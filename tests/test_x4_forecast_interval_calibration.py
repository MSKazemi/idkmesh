"""X4 synthetic calibration: the harness scores forecasters against a KNOWN truth.

Everything is synthetic and offline. Expected values are derived by hand or from
closed forms, never from the module under test. The committed report
(`experiments/results/X4-synthetic-interval-calibration.json`) is synthetic and
is checked here only for self-consistency and reproducibility, not as evidence
about real coding agents.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import agent_value_forecast as e046  # noqa: E402
import forecast_interval_calibration as cal  # noqa: E402
import forecast_intervals as x4  # noqa: E402

if importlib.util.find_spec("pytest") is not None:
    import pytest

    # Research-artifact test: runs in the emergence-sim workflow and nightly, not on
    # the per-PR unit tier (docs/TESTING.md: experiment tests carry `sim`).
    pytestmark = pytest.mark.sim
else:  # pragma: no cover - bare-interpreter jobs take this path
    pass

REPORT = ROOT / "experiments" / "results" / "X4-synthetic-interval-calibration.json"
DOC = ROOT / "docs" / "research" / "X4_SYNTHETIC_INTERVAL_CALIBRATION.md"

SMALL = dict(agents=24, tasks=80)


def _population(scenario: str, seed: int = 1, **size: int) -> dict[str, frozenset]:
    return cal.simulate_population(scenario, random.Random(seed), **(size or SMALL))


def _oracle(truth: float) -> x4.CountForecaster:
    """Positive control: a 'forecaster' that knows the answer."""
    return lambda counts, k: (lambda m: truth)


def _constant(value: float) -> x4.CountForecaster:
    """Broken control: ignores the pilot entirely."""
    return lambda counts, k: (lambda m: value)


def _shifted(base: x4.CountForecaster, shift: float) -> x4.CountForecaster:
    """Broken control: a sound forecaster with a systematic bias."""
    return lambda counts, k: (lambda m: min(1.0, max(0.0, base(counts, k)(m) + shift)))


class SimulatorTests(unittest.TestCase):
    def test_population_is_deterministic_and_has_the_requested_shape(self) -> None:
        first, second = _population("rasch_moderate", 5), _population("rasch_moderate", 5)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)
        self.assertNotEqual(first, _population("rasch_moderate", 6))
        ids = set(cal.task_ids(80))
        for solved in first.values():
            self.assertTrue(solved <= ids)

    def test_unsolvable_share_is_a_hard_ceiling_on_coverage(self) -> None:
        rows = _population("rasch_unsolvable", 3)
        ids = cal.task_ids(80)
        truth = cal.true_coverage(rows, ids)
        self.assertLessEqual(truth, 1 - 0.10 + 1e-12)  # round(0.10 * 80) = 8 tasks nobody solves
        solved_by_someone = set().union(*rows.values())
        self.assertLessEqual(len(solved_by_someone), 72)

    def test_family_scenario_makes_same_family_agents_agree_more(self) -> None:
        rows = _population("family_clustered", 2, agents=24, tasks=200)
        names = sorted(rows)

        def jaccard(a: str, b: str) -> float:
            return len(rows[a] & rows[b]) / max(1, len(rows[a] | rows[b]))

        same = [jaccard(a, b) for i, a in enumerate(names) for b in names[i + 1 :] if i % 6 == names.index(b) % 6]
        different = [jaccard(a, b) for i, a in enumerate(names) for b in names[i + 1 :] if i % 6 != names.index(b) % 6]
        self.assertGreater(sum(same) / len(same), sum(different) / len(different))

    def test_true_coverage_is_the_union_fraction(self) -> None:
        rows = {"a": frozenset({"t0", "t1"}), "b": frozenset({"t1", "t2"}), "c": frozenset()}
        self.assertAlmostEqual(cal.true_coverage(rows, ["t0", "t1", "t2", "t3"]), 0.75)

    def test_stable_seed_is_label_sensitive_and_reproducible(self) -> None:
        self.assertEqual(cal.stable_seed(1, "a", 2), cal.stable_seed(1, "a", 2))
        self.assertNotEqual(cal.stable_seed(1, "a", 2), cal.stable_seed(1, "a", 3))
        self.assertEqual(cal.stable_seed("x"), int(hashlib.sha256(b"x").hexdigest()[:16], 16))


class ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _population("rasch_moderate", 4)
        self.ids = cal.task_ids(80)
        self.truth = cal.true_coverage(self.rows, self.ids)

    def test_pilot_prefix_does_not_depend_on_the_pilot_count(self) -> None:
        forecasters = {"beta_binomial": e046.forecast_beta_binomial}
        short = cal.run_trials(forecasters, self.rows, self.ids, 5, 99, pilots=2, replicates=8)
        long = cal.run_trials(forecasters, self.rows, self.ids, 5, 99, pilots=4, replicates=8)
        for key in short:
            self.assertEqual(short[key], long[key][:2])

    def test_pilot_size_must_leave_agents_outside_the_pilot(self) -> None:
        for bad in (1, 24):
            with self.assertRaises(ValueError):
                cal.run_trials({"b": e046.forecast_beta_binomial}, self.rows, self.ids, bad, 1, pilots=1, replicates=2)

    def test_oracle_control_scores_perfectly(self) -> None:
        cell = cal.run_cell({"oracle": _oracle(self.truth)}, self.rows, self.ids, 5, 7, pilots=4, replicates=6)
        for row in cell["results"].values():
            self.assertAlmostEqual(row["mae"], 0.0, places=4)
            self.assertEqual(row["interval_coverage"], 1.0)
            self.assertEqual(row["within_tolerance"], 1.0)

    def test_broken_constant_estimator_is_caught_on_accuracy_and_coverage(self) -> None:
        wrong = 0.0 if self.truth > 0.5 else 1.0  # as far from the truth as possible
        cell = cal.run_cell({"broken": _constant(wrong)}, self.rows, self.ids, 5, 7, pilots=4, replicates=6)
        for row in cell["results"].values():
            self.assertGreater(row["mae"], 0.4)
            self.assertEqual(row["interval_coverage"], 0.0)
            self.assertEqual(row["within_tolerance"], 0.0)

    def test_systematic_bias_is_reported_as_bias_and_breaks_the_tolerance(self) -> None:
        shifted = _shifted(e046.forecast_beta_binomial, -0.2)
        sound = cal.run_cell({"b": e046.forecast_beta_binomial}, self.rows, self.ids, 10, 11, pilots=6, replicates=10)
        broken = cal.run_cell({"b": shifted}, self.rows, self.ids, 10, 11, pilots=6, replicates=10)
        for scheme in x4.SCHEMES:
            key = f"b/{scheme}"
            self.assertLess(broken["results"][key]["bias"], sound["results"][key]["bias"] - 0.1)
            self.assertGreater(broken["results"][key]["mae"], cal.TOLERANCE)
            self.assertLess(broken["results"][key]["within_tolerance"], 1.0)

    def test_cell_is_deterministic_for_a_fixed_seed(self) -> None:
        args = (x4.FORECASTERS, self.rows, self.ids, 5, 21)
        self.assertEqual(cal.run_cell(*args, pilots=2, replicates=5), cal.run_cell(*args, pilots=2, replicates=5))

    def test_real_forecasters_report_valid_rates(self) -> None:
        cell = cal.run_cell(x4.FORECASTERS, self.rows, self.ids, 5, 3, pilots=3, replicates=6)
        self.assertEqual(set(cell["results"]), {f"{f}/{s}" for f in x4.FORECASTERS for s in x4.SCHEMES})
        self.assertAlmostEqual(cell["true_coverage"], self.truth, places=4)
        self.assertAlmostEqual(cell["true_floor"], 1 - self.truth, places=4)
        for row in cell["results"].values():
            self.assertTrue(0.0 <= row["interval_coverage"] <= 1.0)
            self.assertTrue(0.0 <= row["within_tolerance"] <= 1.0)


class PoolAndVerdictTests(unittest.TestCase):
    @staticmethod
    def _row(pilots: int, bias: float, mae: float, coverage: float) -> dict:
        return {"pilots": pilots, "bias": bias, "mae": mae, "within_tolerance": 0.5, "interval_coverage": coverage, "mean_width": 0.1}

    def test_pool_weights_populations_by_pilot_count_and_keeps_the_worst_coverage(self) -> None:
        cells = [{"results": {"f/task": self._row(10, 0.0, 0.1, 1.0)}}, {"results": {"f/task": self._row(30, 0.04, 0.02, 0.6)}}]
        pooled = cal.pool(cells)["f/task"]
        self.assertEqual(pooled["pilots"], 40)
        self.assertAlmostEqual(pooled["bias"], 0.03)
        self.assertAlmostEqual(pooled["mae"], (10 * 0.1 + 30 * 0.02) / 40, places=4)
        self.assertAlmostEqual(pooled["interval_coverage"], (10 * 1.0 + 30 * 0.6) / 40, places=4)
        self.assertEqual(pooled["min_population_coverage"], 0.6)

    def test_verdict_falsified_when_nothing_meets_the_tolerance_anywhere(self) -> None:
        primary = {s: {"f/task": self._row(30, 0, 0.05, 0.99)} for s in ("a", "b")}
        self.assertEqual(cal.verdict(primary)["verdict"], "falsified")

    def test_verdict_supported_needs_accuracy_and_calibration_in_every_scenario(self) -> None:
        good = {s: {"f/task": self._row(30, 0, 0.02, 0.95)} for s in ("a", "b")}
        self.assertEqual(cal.verdict(good)["verdict"], "supported")

    def test_verdict_mixed_when_accurate_but_miscalibrated(self) -> None:
        primary = {s: {"f/task": self._row(30, 0, 0.02, 0.5)} for s in ("a", "b")}
        decision = cal.verdict(primary)
        self.assertEqual(decision["verdict"], "mixed")
        self.assertEqual(decision["accurate_and_calibrated_in"], {})
        self.assertEqual(sorted(decision["accurate_in"]["f/task"]), ["a", "b"])

    def test_verdict_mixed_when_one_scenario_fails(self) -> None:
        primary = {"a": {"f/task": self._row(30, 0, 0.02, 0.95)}, "b": {"f/task": self._row(30, 0, 0.06, 0.95)}}
        self.assertEqual(cal.verdict(primary)["verdict"], "mixed")

    def test_broken_estimator_cannot_win_the_verdict_end_to_end(self) -> None:
        forecasters = {"broken": _constant(0.5)}
        report = cal.study(seed=3, scenarios=("rasch_hard_tail",), populations=1, sizes=(10,), pilots=3, replicates=5, forecasters=forecasters, **SMALL)
        pooled = report["scenarios"]["rasch_hard_tail"]["by_k"]["10"]["pooled"]
        self.assertEqual(set(pooled), {"broken/task", "broken/agent"})
        self.assertNotEqual(report["decision"]["verdict"], "supported")


class StudyTests(unittest.TestCase):
    def test_small_study_is_deterministic_and_complete(self) -> None:
        kwargs = dict(seed=5, scenarios=("rasch_moderate", "family_clustered"), populations=2, sizes=(5, 10), pilots=2, replicates=5, **SMALL)
        first, second = cal.study(**kwargs), cal.study(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(set(first["scenarios"]), {"rasch_moderate", "family_clustered"})
        for scenario in first["scenarios"].values():
            self.assertEqual(len(scenario["population_true_coverage"]), 2)
            self.assertEqual(set(scenario["by_k"]), {"5", "10"})
            self.assertEqual(len(scenario["by_k"]["10"]["populations"]), 2)
            self.assertEqual(next(iter(scenario["by_k"]["10"]["pooled"].values()))["pilots"], 4)
        self.assertIn(first["decision"]["verdict"], {"falsified", "mixed", "supported"})

    def test_populations_in_a_scenario_are_distinct_draws(self) -> None:
        draws = [cal.simulate_population("rasch_hard_tail", random.Random(cal.stable_seed(5, "population", "rasch_hard_tail", i)), **SMALL) for i in range(3)]
        self.assertEqual(len({tuple(sorted((name, tuple(sorted(solved))) for name, solved in rows.items())) for rows in draws}), 3)

    def test_cli_writes_a_labelled_synthetic_report(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "report.json"
            code = cal.main(["--populations", "1", "--pilots", "1", "--replicates", "3", "--agents", "24", "--tasks", "80", "--sizes", "5", "10", "--out", str(out)])
            report = json.loads(out.read_text())
        self.assertEqual(code, 0)
        self.assertIn("SYNTHETIC", report["status"])
        self.assertEqual(report["agents"], 24)
        self.assertEqual(report["pilot_sizes"], [5, 10])
        self.assertEqual(report["frozen_e046_sha256"], hashlib.sha256(Path(e046.__file__).read_bytes()).hexdigest())


@unittest.skipUnless(REPORT.exists(), "committed synthetic report not present")
class CommittedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_report_is_labelled_synthetic_and_binds_the_analysis_code(self) -> None:
        self.assertIn("SYNTHETIC", self.report["status"])
        self.assertEqual(self.report["frozen_e046_sha256"], hashlib.sha256((ROOT / "experiments" / "agent_value_forecast.py").read_bytes()).hexdigest())
        self.assertEqual(self.report["forecast_intervals_sha256"], hashlib.sha256((ROOT / "experiments" / "forecast_intervals.py").read_bytes()).hexdigest())

    def test_report_records_the_declared_constants(self) -> None:
        self.assertEqual(self.report["seed"], cal.SEED)
        self.assertEqual(self.report["tolerance"], cal.TOLERANCE)
        self.assertEqual(self.report["calibrated_at_least"], cal.CALIBRATED_AT_LEAST)
        self.assertEqual(self.report["primary_k"], cal.PRIMARY_K)
        self.assertEqual(self.report["pilot_sizes"], list(cal.PILOT_SIZES))
        self.assertEqual({name: scenario["parameters"] for name, scenario in self.report["scenarios"].items()}, {k: dict(v) for k, v in cal.SCENARIOS.items()})

    def test_recorded_decision_is_recomputed_from_the_recorded_cells(self) -> None:
        primary = {name: scenario["by_k"][str(cal.PRIMARY_K)]["pooled"] for name, scenario in self.report["scenarios"].items()}
        self.assertEqual(cal.verdict(primary), self.report["decision"])

    def test_pooled_rows_are_recomputed_from_the_population_cells(self) -> None:
        for scenario in self.report["scenarios"].values():
            for by_k in scenario["by_k"].values():
                self.assertEqual(cal.pool(by_k["populations"]), by_k["pooled"])

    def test_audit_trials_reproduce_from_the_seed(self) -> None:
        audit = self.report["audit_cell"]
        scenario, index, k = audit["scenario"], audit["population"], audit["k"]
        rows = cal.simulate_population(scenario, random.Random(cal.stable_seed(self.report["seed"], "population", scenario, index)))
        trials = cal.run_trials(
            x4.FORECASTERS,
            rows,
            cal.task_ids(),
            k,
            cal.stable_seed(self.report["seed"], "cell", scenario, index, k),
            pilots=len(next(iter(audit["trials"].values()))),
            replicates=self.report["bootstrap_replicates"],
        )
        for key, recorded in audit["trials"].items():
            for (point, (low, high), truth), saved in zip(trials[key], recorded):
                self.assertAlmostEqual(point, saved[0], places=5)
                self.assertAlmostEqual(low, saved[1][0], places=5)
                self.assertAlmostEqual(high, saved[1][1], places=5)
                self.assertAlmostEqual(truth, saved[2], places=5)

    def test_every_documented_table_row_matches_the_report(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        cited = {10: ["beta_binomial/task", "beta_binomial/agent", "incidence/task", "incidence/agent"], 20: ["incidence/task"]}
        checked = 0
        for k, keys in cited.items():
            for scenario, body in self.report["scenarios"].items():
                for key in keys:
                    r = body["by_k"][str(k)]["pooled"][key]
                    row = f"| {scenario} | `{key}` | {r['bias']:+.4f} | {r['mae']:.4f} | {r['within_tolerance']:.2f} | {r['interval_coverage']:.3f} | {r['mean_width']:.3f} |"
                    self.assertIn(row, text)
                    checked += 1
        self.assertEqual(checked, 20)

    def test_documented_verdict_and_headline_claims_hold_in_the_report(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual(self.report["decision"]["verdict"], "mixed")
        self.assertIn("The recorded decision is **mixed**", text)
        pooled = {name: s["by_k"]["10"]["pooled"] for name, s in self.report["scenarios"].items()}
        under = [n for n, rows in pooled.items() if rows["beta_binomial/task"]["mae"] <= cal.TOLERANCE]
        self.assertEqual(len(under), 3)  # "three of four scenarios"
        self.assertEqual(self.report["decision"]["accurate_and_calibrated_in"], {})  # "no accurate and calibrated forecaster"
        calibrated = {(n, key) for n, rows in pooled.items() for key, r in rows.items() if r["interval_coverage"] >= cal.CALIBRATED_AT_LEAST}
        self.assertEqual(calibrated, {("rasch_unsolvable", "beta_binomial/agent")})  # the one biased cell
        self.assertGreater(pooled["rasch_unsolvable"]["beta_binomial/agent"]["mae"], cal.TOLERANCE)
        k20 = [s["by_k"]["20"]["pooled"]["incidence/task"] for s in self.report["scenarios"].values()]
        self.assertTrue(all(r["mae"] <= cal.TOLERANCE and r["interval_coverage"] >= cal.CALIBRATED_AT_LEAST for r in k20))


if __name__ == "__main__":
    unittest.main()
