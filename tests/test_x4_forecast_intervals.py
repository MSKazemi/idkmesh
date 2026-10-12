"""X4: the forecast-interval report computes what its docstring says.

All fixtures are synthetic and offline. Expected values are derived by hand or
from closed forms, never from the module under test.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import agent_value_forecast as e046  # noqa: E402
import forecast_intervals as x4  # noqa: E402


def _synthetic(agents: int = 24, tasks: int = 120, seed: int = 7) -> dict[str, frozenset]:
    rng = random.Random(seed)
    difficulty = [rng.gauss(0, 2) for _ in range(tasks)]
    rows = {}
    for j in range(agents):
        ability = rng.gauss(0.5, 1)
        rows[f"agent{j:02d}"] = frozenset(
            f"t{t:03d}" for t in range(tasks) if rng.random() < 1 / (1 + math.exp(-(ability - difficulty[t])))
        )
    return rows


class PrimitiveTests(unittest.TestCase):
    def test_percentile_interpolates_linearly(self) -> None:
        values = [0.0, 10.0, 20.0, 30.0]
        self.assertEqual(x4.percentile(values, 0.0), 0.0)
        self.assertEqual(x4.percentile(values, 1.0), 30.0)
        self.assertAlmostEqual(x4.percentile(values, 0.5), 15.0)
        self.assertAlmostEqual(x4.percentile(values, 0.25), 7.5)
        with self.assertRaises(ValueError):
            x4.percentile([], 0.5)

    def test_floor_interval_is_the_reflected_coverage_interval(self) -> None:
        low, high = x4.floor_interval((0.8, 0.9))
        self.assertAlmostEqual(low, 0.1)
        self.assertAlmostEqual(high, 0.2)
        self.assertLessEqual(low, high)

    def test_summary_scores_bias_mae_tolerance_coverage_and_width(self) -> None:
        trials = [
            (0.5, (0.4, 0.6), 0.5),  # exact, covered
            (0.5, (0.1, 0.3), 0.6),  # off by 0.1, not covered
            (0.7, (0.6, 0.8), 0.6),  # off by 0.1, covered on the lower endpoint
        ]
        summary = x4.summarize(trials)
        self.assertEqual(summary["pilots"], 3)
        self.assertAlmostEqual(summary["bias"], 0.0)
        self.assertAlmostEqual(summary["mae"], 0.2 / 3, places=4)
        self.assertAlmostEqual(summary["within_tolerance"], 1 / 3, places=4)
        self.assertAlmostEqual(summary["interval_coverage"], 2 / 3, places=4)
        self.assertAlmostEqual(summary["mean_width"], 0.2, places=4)


class ResamplingTests(unittest.TestCase):
    def test_task_resample_draws_only_observed_counts(self) -> None:
        columns = [[1, 1, 0, 0], [1, 0, 0, 0]]  # per-task counts 2, 1, 0, 0
        rng = random.Random(1)
        for _ in range(20):
            counts = x4.resample_tasks(columns, rng)
            self.assertEqual(len(counts), 4)
            self.assertTrue(set(counts) <= {0, 1, 2})

    def test_agent_resample_of_identical_agents_never_changes_the_counts(self) -> None:
        columns = [[1, 0, 1, 0]] * 3
        rng = random.Random(2)
        for _ in range(20):
            self.assertEqual(x4.resample_agents(columns, rng), [3, 0, 3, 0])

    def test_agent_resample_keeps_k_draws_per_task(self) -> None:
        columns = [[1, 0], [0, 1], [1, 1]]
        rng = random.Random(3)
        for _ in range(20):
            counts = x4.resample_agents(columns, rng)
            self.assertLessEqual(max(counts), 3)
            self.assertGreaterEqual(min(counts), 0)


class IntervalTests(unittest.TestCase):
    def test_identical_agents_give_the_closed_form_point_and_a_zero_width_interval(self) -> None:
        columns = [[1, 0, 1, 0]] * 3  # k = 3, p = 6 / 12 = 0.5
        point, (low, high) = x4.bootstrap_interval(columns, e046.forecast_independence, 5, "agent", random.Random(4), replicates=25)
        self.assertAlmostEqual(point, 1 - 0.5**5)
        self.assertAlmostEqual(low, point)
        self.assertAlmostEqual(high, point)

    def test_constant_counts_have_a_zero_width_task_interval(self) -> None:
        columns = [[1, 1, 1, 1], [0, 0, 0, 0]]  # every task solved by exactly one of two agents
        point, (low, high) = x4.bootstrap_interval(columns, e046.forecast_independence, 4, "task", random.Random(5), replicates=25)
        self.assertAlmostEqual(point, 1 - 0.5**4)
        self.assertAlmostEqual(low, high)

    def test_incidence_at_the_pilot_size_is_the_observed_fraction(self) -> None:
        columns = [[1, 0, 0, 0], [1, 1, 0, 0]]  # 2 of 4 tasks solved by someone
        point, _ = x4.bootstrap_interval(columns, e046.forecast_incidence, 2, "task", random.Random(6), replicates=5)
        self.assertAlmostEqual(point, 0.5)

    def test_higher_level_gives_a_wider_interval_from_the_same_draws(self) -> None:
        rows = _synthetic()
        tasks = [f"t{t:03d}" for t in range(120)]
        columns = [[1 if t in rows[a] else 0 for t in tasks] for a in sorted(rows)[:6]]
        _, (low50, high50) = x4.bootstrap_interval(columns, e046.forecast_beta_binomial, 24, "agent", random.Random(10), replicates=60, level=0.5)
        _, (low95, high95) = x4.bootstrap_interval(columns, e046.forecast_beta_binomial, 24, "agent", random.Random(10), replicates=60, level=0.95)
        self.assertLess(high95 - low95, 1.0)
        self.assertGreater(high95 - low95, high50 - low50)
        self.assertLessEqual(low95, low50)
        self.assertGreaterEqual(high95, high50)

    def test_interval_is_ordered_and_inside_the_unit_range(self) -> None:
        rows = _synthetic()
        agents = sorted(rows)[:10]
        tasks = [f"t{t:03d}" for t in range(120)]
        columns = [[1 if t in rows[a] else 0 for t in tasks] for a in agents]
        for scheme in x4.SCHEMES:
            for forecaster in x4.FORECASTERS.values():
                _, (low, high) = x4.bootstrap_interval(columns, forecaster, 24, scheme, random.Random(7), replicates=30)
                self.assertLessEqual(low, high)
                self.assertGreaterEqual(low, 0.0)
                self.assertLessEqual(high, 1.0 + 1e-12)


class StudyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _synthetic()
        self.agents = sorted(self.rows)
        self.tasks = [f"t{t:03d}" for t in range(120)]

    def test_truth_is_the_union_coverage_of_the_whole_population(self) -> None:
        report = x4.interval_study(self.rows, self.agents, self.tasks, 5, random.Random(8), pilots=3, replicates=5)
        expected = e046.coverage(self.rows, self.agents, frozenset(self.tasks)) / len(self.tasks)
        self.assertAlmostEqual(report["true_coverage"], expected, places=4)
        self.assertAlmostEqual(report["true_floor"], 1 - expected, places=4)
        self.assertEqual(set(report["results"]), {f"{f}/{s}" for f in x4.FORECASTERS for s in x4.SCHEMES})
        for cell in report["results"].values():
            self.assertEqual(cell["pilots"], 3)
            self.assertTrue(0.0 <= cell["interval_coverage"] <= 1.0)
            self.assertGreaterEqual(cell["mean_width"], 0.0)

    def test_study_is_deterministic_for_a_fixed_seed(self) -> None:
        first = x4.interval_study(self.rows, self.agents, self.tasks, 5, random.Random(9), pilots=3, replicates=5)
        second = x4.interval_study(self.rows, self.agents, self.tasks, 5, random.Random(9), pilots=3, replicates=5)
        self.assertEqual(first, second)

    def test_pilot_size_must_leave_agents_outside_the_pilot(self) -> None:
        for bad in (1, len(self.agents)):
            with self.assertRaises(ValueError):
                x4.interval_study(self.rows, self.agents, self.tasks, bad, random.Random(1), pilots=1, replicates=2)

    def test_infeasible_split_is_reported_not_analysed(self) -> None:
        few = {name: self.rows[name] for name in self.agents[:5]}
        report = x4.study_by_k(few, frozenset(self.tasks), pilots=1, replicates=2)
        self.assertEqual(report["feasible"], False)
        self.assertNotIn("by_k", report)

    def test_study_by_k_skips_pilot_sizes_that_use_the_whole_population(self) -> None:
        report = x4.study_by_k(self.rows, frozenset(self.tasks), sizes=(3, 5, 99), pilots=1, replicates=2)
        self.assertTrue(report["feasible"])
        self.assertEqual(set(report["by_k"]), {"3", "5"})


class CliTests(unittest.TestCase):
    def test_cli_writes_a_report_that_binds_the_frozen_analysis_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "toy"
            (cache / "r").mkdir(parents=True)
            ids = [f"t{t:03d}" for t in range(100)]
            for j in range(22):
                solved = [ids[t] for t in range(100) if (t + j) % 4 == 0 or t % (j + 2) == 0]
                record = {"resolved": solved}
                if j == 0:
                    record["no_generation"] = ids
                (cache / "r" / f"agent{j:02d}.json").write_text(json.dumps(record))
            out = Path(directory) / "report.json"

            code = x4.main([str(cache), "--out", str(out), "--pilots", "2", "--replicates", "3"])
            report = json.loads(out.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(report["splits"]["toy"]["feasible"], True)
        self.assertEqual(report["frozen_e046_sha256"], hashlib.sha256(Path(e046.__file__).read_bytes()).hexdigest())
        self.assertIn("exploratory", report["status"])


if __name__ == "__main__":
    unittest.main()
