"""E045: the public agent-dependence pilot reads, measures and extrapolates correctly.

Every test runs on a hand-built cache, never the network, so the expected numbers
can be checked by hand.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import public_agent_dependence as e045  # noqa: E402


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class PublicAgentDependencePilotTests(unittest.TestCase):
    def test_loader_prefers_the_explicit_list_and_drops_an_all_false_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            _write(cache / "r" / "a.json", {"resolved": ["t1", "t2"]})
            _write(cache / "p" / "a.json", {"t1": {"resolved": False}, "t3": {"resolved": True}})
            _write(cache / "p" / "b.json", {"t2": {"resolved": True}, "t3": {"resolved": False}})
            _write(cache / "p" / "missing-evaluation.json", {"t1": {"resolved": False}, "t2": {"resolved": False}})

            rows, digests = e045.load_matrix(cache)

        self.assertEqual(rows, {"a": frozenset({"t1", "t2"}), "b": frozenset({"t2"})})
        self.assertEqual(sorted(digests), ["p/b.json", "r/a.json"])

    def test_phi_matches_the_hand_computed_correlation(self) -> None:
        # Four tasks: a solves {1, 2}, b solves {1, 3}. Both have p = 0.5 and share
        # one success, so phi = (0.25 - 0.25) / 0.25 = 0.
        self.assertAlmostEqual(e045.phi(frozenset({1, 2}), frozenset({1, 3}), 4), 0.0)
        self.assertAlmostEqual(e045.phi(frozenset({1, 2}), frozenset({1, 2}), 4), 1.0)
        self.assertAlmostEqual(e045.phi(frozenset({1, 2}), frozenset({3, 4}), 4), -1.0)
        self.assertIsNone(e045.phi(frozenset(), frozenset({1}), 4))

    def test_chao2_adds_the_unseen_mass_its_singletons_imply(self) -> None:
        rows = {"a": frozenset({1, 2, 3}), "b": frozenset({1, 4}), "c": frozenset({1, 2})}
        # Observed 4 of 10. f1 = 2 (tasks 3, 4), f2 = 1 (task 2), k = 3:
        # 4 + (2/3) * (4 / 2) = 5.333...
        self.assertAlmostEqual(e045.chao2(rows, ["a", "b", "c"], 10), (4 + (2 / 3) * 2) / 10)

    def test_perfectly_dependent_agents_cover_less_than_independence_predicts(self) -> None:
        nested = {f"agent{i}": frozenset(range(10 + i)) for i in range(6)}

        summary = e045.analyze(nested, n=20, seed=1, draws=20)

        self.assertEqual(summary["blind_spot_floor"]["unsolved_by_every_agent"], 5)
        self.assertEqual(summary["blind_spot_floor"]["fraction"], 0.25)
        for point in summary["oracle_coverage_curve"]:
            if point["k"] > 1:
                self.assertLess(point["oracle_coverage_mean"], point["independence_prediction_mean"])

    def test_agents_below_the_competence_floor_are_excluded(self) -> None:
        rows = {"good": frozenset(range(50)), "also-good": frozenset(range(25, 75)), "noise": frozenset({99})}

        summary = e045.analyze(rows, n=100, seed=1, draws=5)

        self.assertEqual(summary["agents_with_results"], 3)
        self.assertEqual(summary["competent_agents"], 2)

    def test_analysis_is_deterministic_for_a_fixed_seed(self) -> None:
        rows = {f"agent{i}": frozenset(j for j in range(40) if (i * 7 + j) % 3) for i in range(12)}

        self.assertEqual(e045.analyze(rows, n=40, seed=3, draws=10), e045.analyze(rows, n=40, seed=3, draws=10))

    def test_retained_pilot_summary_records_its_pinned_upstream(self) -> None:
        retained = Path(__file__).resolve().parents[1] / "experiments" / "results" / "E045-public-agent-dependence-pilot.json"
        summary = json.loads(retained.read_text(encoding="utf-8"))

        self.assertEqual(summary["upstream"]["commit"], e045.PINNED_COMMIT)
        self.assertIn("not confirmatory", summary["evidence_class"])
        self.assertEqual(summary["blind_spot_floor"]["unsolved_by_every_agent"], 26)


if __name__ == "__main__":
    unittest.main()
