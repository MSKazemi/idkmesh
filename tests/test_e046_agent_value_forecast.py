"""E046: the frozen agent-value forecast analysis computes what its preregistration says.

All fixtures are synthetic and offline. Expected values are derived by hand or
from closed forms, never from the module itself.
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


def _synthetic(agents: int = 24, tasks: int = 120, seed: int = 7) -> dict[str, frozenset]:
    """Agents whose successes depend on a per-task difficulty (Rasch-like)."""
    rng = random.Random(seed)
    difficulty = [rng.gauss(0, 2) for _ in range(tasks)]
    rows = {}
    for j in range(agents):
        ability = rng.gauss(0.5, 1)
        rows[f"agent{j:02d}"] = frozenset(
            f"t{t:03d}" for t in range(tasks) if rng.random() < 1 / (1 + math.exp(-(ability - difficulty[t])))
        )
    return rows


class LoaderTests(unittest.TestCase):
    def test_universe_includes_unresolved_ids_from_every_list_and_flag_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / "r").mkdir()
            (cache / "p").mkdir()
            (cache / "r" / "a.json").write_text(json.dumps({"resolved": ["t1"], "no_generation": ["t2"]}))
            (cache / "p" / "b.json").write_text(json.dumps({"t3": {"resolved": True}, "t4": {"resolved": False}}))
            (cache / "p" / "c.json").write_text(json.dumps({"t5": {"resolved": False}}))

            rows, universe, _ = e046.load_split(cache)

        self.assertEqual(universe, frozenset({"t1", "t2", "t3", "t4", "t5"}))
        self.assertEqual(rows, {"a": frozenset({"t1"}), "b": frozenset({"t3"})})


class PopulationCurveTests(unittest.TestCase):
    def test_exact_curve_matches_enumeration_over_every_subset(self) -> None:
        rows = {"a": frozenset({1, 2}), "b": frozenset({2, 3}), "c": frozenset({4}), "d": frozenset()}
        agents, tasks = sorted(rows), [1, 2, 3, 4, 5]
        from itertools import combinations

        for m in (1, 2, 3, 4):
            subsets = list(combinations(agents, m))
            expected = sum(e046.coverage(rows, s, frozenset(tasks)) for s in subsets) / (len(subsets) * len(tasks))
            self.assertAlmostEqual(e046.population_curve(rows, agents, tasks, [m])[m], expected)


class ForecasterTests(unittest.TestCase):
    def test_kish_and_shared_shock_reduce_to_independence_at_zero_correlation(self) -> None:
        counts, k = [3, 0, 5, 2], 5
        independent = e046.forecast_independence(counts, k)
        for model in (e046.forecast_kish(counts, k, 0.0), e046.forecast_shared_shock(counts, k, 0.0)):
            for m in (1, 3, 10):
                self.assertAlmostEqual(model(m), independent(m))

    def test_shared_shock_at_full_correlation_never_grows(self) -> None:
        model = e046.forecast_shared_shock([2, 2, 0, 0], 4, 1.0)
        self.assertAlmostEqual(model(1), model(50))

    def test_beta_binomial_matches_the_closed_form_moment_fit(self) -> None:
        # Tasks are either always or never solved in a 4-agent pilot: maximal
        # overdispersion, rho clipped to 0.999.
        counts, k = [4, 4, 0, 0], 4
        alpha, beta = e046.beta_binomial_parameters(counts, k)
        self.assertAlmostEqual(alpha / (alpha + beta), 0.5)
        self.assertAlmostEqual(1 / (alpha + beta + 1), 0.999, places=6)

    def test_beta_binomial_falls_back_to_independence_without_overdispersion(self) -> None:
        self.assertIsNone(e046.beta_binomial_parameters([2, 2, 2, 2], 4))

    def test_incidence_rarefaction_reproduces_the_pilot_at_full_size(self) -> None:
        counts = [0, 1, 1, 2, 3, 5]
        self.assertAlmostEqual(e046.forecast_incidence(counts, 5)(5), 5 / 6)

    def test_incidence_extrapolation_follows_chao_2014(self) -> None:
        # Q1 = 2, Q2 = 1, k = 4: Q0 = (3/4) * 4 / 2 = 1.5.
        counts, k = [1, 1, 2, 4, 0, 0], 4
        q0 = 0.75 * 4 / 2
        expected = (4 + q0 * (1 - (1 - 2 / (k * q0 + 2)) ** 3)) / 6
        self.assertAlmostEqual(e046.forecast_incidence(counts, k)(7), expected)

    def test_rasch_forecast_is_a_probability_and_increases_with_ensemble_size(self) -> None:
        rows = _synthetic(agents=10, tasks=40)
        model = e046.forecast_rasch(rows, sorted(rows), [f"t{t:03d}" for t in range(40)], iterations=5)
        values = [model(m) for m in (1, 2, 5, 20)]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in values))
        self.assertEqual(values, sorted(values))


class SelectionTests(unittest.TestCase):
    def test_greedy_prefers_complementary_agents_over_the_two_most_accurate(self) -> None:
        rows = {"big1": frozenset({1, 2, 3, 4}), "big2": frozenset({1, 2, 3, 4}), "niche": frozenset({5, 6, 7})}
        calibration = frozenset(range(1, 8))
        self.assertEqual(e046.select_top_k(rows, sorted(rows), calibration, 2), ["big1", "big2"])
        self.assertEqual(e046.select_greedy(rows, sorted(rows), calibration, 2), ["big1", "niche"])

    def test_exact_mcnemar_matches_hand_values(self) -> None:
        self.assertEqual(e046.exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(e046.exact_mcnemar(0, 5), 2 / 32)
        self.assertAlmostEqual(e046.exact_mcnemar(7, 3), 2 * (1 + 10 + 45 + 120) / 1024)


class DecisionRuleTests(unittest.TestCase):
    def test_small_splits_are_reported_infeasible_not_analysed(self) -> None:
        report = e046.analyze_split(_synthetic(agents=5, tasks=40), frozenset(f"t{t:03d}" for t in range(40)))
        self.assertFalse(report["feasible"])

    def test_cross_split_rules_need_a_majority_and_no_falsification(self) -> None:
        def split(h1: str, h3: str, rasch: bool) -> dict:
            return {"feasible": True, "h1_verdict": h1, "h3": {"verdict": h3}, "h2": {"meets_tolerance": {"rasch": rasch}}}

        decision = e046.combine({"a": split("supported", "supported", True), "b": split("supported", "unresolved", True), "c": split("unresolved", "falsified", False)})
        self.assertEqual(decision["H1"], "supported")
        self.assertEqual(decision["H2"], "falsified")
        self.assertEqual(decision["H3"], "unresolved")
        self.assertEqual(e046.combine({"x": {"feasible": False}})["H1"], "infeasible")

    def test_bootstrap_and_verdict_run_on_a_feasible_split(self) -> None:
        rows = _synthetic()
        tasks = [f"t{t:03d}" for t in range(120)]
        agents = e046.competent(rows, len(tasks))
        boot = e046.bootstrap_h1(rows, agents, tasks, 5, random.Random(1), replicates=3)
        self.assertEqual(set(boot), {"kish", "shared_shock"})
        self.assertIn(e046.h1_verdict({}, boot), {"supported", "falsified", "unresolved"})


class FreezeTests(unittest.TestCase):
    def test_analysis_code_matches_the_digest_frozen_by_the_preregistration(self) -> None:
        """Editing the frozen analysis without registering an amendment fails here."""
        import hashlib
        import re

        root = Path(__file__).resolve().parents[1]
        prereg = (root / "docs" / "research" / "PREREG_AGENT_VALUE_FORECAST_V1.md").read_text(encoding="utf-8")
        frozen = re.search(r"analysis code SHA-256 \| `([0-9a-f]{64})`", prereg)
        self.assertIsNotNone(frozen, "the preregistration no longer states the analysis digest")
        actual = hashlib.sha256((root / "experiments" / "agent_value_forecast.py").read_bytes()).hexdigest()
        self.assertEqual(actual, frozen.group(1), "agent_value_forecast.py changed after its freeze; register an amendment")


    def test_retained_confirmatory_run_used_the_frozen_code(self) -> None:
        root = Path(__file__).resolve().parents[1]
        run = json.loads((root / "experiments" / "results" / "E046-confirmatory.json").read_text(encoding="utf-8"))
        frozen = hashlib.sha256((root / "experiments" / "agent_value_forecast.py").read_bytes()).hexdigest()
        self.assertEqual(run["analysis_sha256"], frozen)
        self.assertEqual(run["decision"]["feasible_splits"], ["lite"])
        self.assertEqual(run["decision"]["H1"], "supported")
        self.assertNotIn("verified", run["splits"])


if __name__ == "__main__":
    unittest.main()
