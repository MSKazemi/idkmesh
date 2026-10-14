"""Nightly test for E051: re-derive part of the committed artifact from scratch.

The fast file ``test_e051_marginal_selector_sweep.py`` checks the record's internal
arithmetic. This one re-runs real replicates -- every verdict matrix is regenerated
and the repository's ``build_selection_plan`` is run on each -- for the smallest
design-sample size of two regimes, and requires the result to equal the committed
cells. It costs tens of seconds, so it is marked ``sim``.

Everything reproduces bit-for-bit across CPython 3.11 and 3.12 except one
baseline: the minimum-mean-pairwise-error-correlation rule. Its argmin sits on
near-ties, and the repository's correlation arithmetic is float-summation
sensitive, so a different interpreter flips a few picks (measured on 3.11 against
a 3.12-generated artifact: 30 leaves in 4 of 16 regimes at the smallest design
size, at most 0.00084 in a mean regret and 2 of 100 replicates in a count). That
baseline is compared within a stated tolerance; the oracle, the marginal selector
under test and every other baseline are still compared exactly.

The oracle is re-derived too, because a committed oracle that no longer matches
the generator would make every regret figure wrong.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import sim.e051_marginal_selector_sweep as e051
from idkmesh import marginal_evidence_benchmark as meb

if importlib.util.find_spec("pytest") is not None:
    import pytest

    pytestmark = pytest.mark.sim
else:  # pragma: no cover - bare-interpreter jobs take this path
    pass

ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "results"
    / "E051-marginal-selector-sweep.json"
)
REGIMES = ("k3-low-mixed", "k4-high-redundant_only")

# Measured maxima were 0.00084 (a mean regret) and 2 (a count of 100); the
# tolerances leave margin without being able to hide a real change in behaviour.
CORRELATION_BASELINE_FLOAT_TOLERANCE = 0.002
CORRELATION_BASELINE_COUNT_TOLERANCE = 3


def within_tolerance(fresh, committed) -> bool:
    """Structural equality with bounded numeric slack (bools and strings are exact)."""
    if isinstance(fresh, dict) and isinstance(committed, dict):
        return fresh.keys() == committed.keys() and all(
            within_tolerance(fresh[k], committed[k]) for k in fresh
        )
    if isinstance(fresh, list) and isinstance(committed, list):
        return len(fresh) == len(committed) and all(
            within_tolerance(a, b) for a, b in zip(fresh, committed)
        )
    if isinstance(fresh, bool) or isinstance(committed, bool):
        return fresh == committed
    if isinstance(fresh, int) and isinstance(committed, int):
        return abs(fresh - committed) <= CORRELATION_BASELINE_COUNT_TOLERANCE
    if isinstance(fresh, (int, float)) and isinstance(committed, (int, float)):
        return abs(fresh - committed) <= CORRELATION_BASELINE_FLOAT_TOLERANCE
    return fresh == committed


def split_correlation_baseline(cell: dict) -> tuple[dict, dict]:
    """Return (cell without the correlation baseline, just that baseline's blocks)."""
    name = meb.STRATEGY_CORRELATION
    rest = {k: v for k, v in cell.items() if k not in ("strategies", "marginal_vs_baselines")}
    rest["strategies"] = {k: v for k, v in cell["strategies"].items() if k != name}
    rest["marginal_vs_baselines"] = {
        k: v for k, v in cell["marginal_vs_baselines"].items() if k != name
    }
    only = {
        "strategies": cell["strategies"][name],
        "marginal_vs_baselines": cell["marginal_vs_baselines"][name],
    }
    return rest, only


class CommittedArtifactRederivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        config = cls.committed["config"]
        smallest = min(config["n_design"])
        cls.fresh = e051.sweep(
            seed=config["seed"],
            replicates=config["replicates"],
            n_design=[smallest],
            regime_ids=list(REGIMES),
            workers=1,
        )
        cls.smallest = smallest

    def test_run_parameters_in_the_record_are_the_module_constants(self):
        config = self.committed["config"]
        self.assertEqual(config["replicates"], e051.REPLICATES)
        self.assertEqual(config["n_design"], list(e051.N_DESIGN))
        self.assertEqual(config["oracle_rows"], e051.ORACLE_ROWS)
        self.assertEqual(config["oracle_tolerance"], e051.ORACLE_TOLERANCE)
        self.assertEqual(config["holdout_rows"], e051.HOLDOUT_ROWS)
        self.assertEqual(config["bootstrap_replicates"], e051.BOOTSTRAP_REPLICATES)

    def test_oracle_and_smallest_cell_rederive_exactly(self):
        committed = {r["id"]: r for r in self.committed["regimes"]}
        for regime in self.fresh["regimes"]:
            with self.subTest(regime=regime["id"]):
                old = committed[regime["id"]]
                self.assertEqual(regime["oracle"], old["oracle"])
                old_cell = next(c for c in old["cells"] if c["n_design"] == self.smallest)
                self.assertEqual(len(regime["cells"]), 1)
                fresh_rest, fresh_corr = split_correlation_baseline(regime["cells"][0])
                old_rest, old_corr = split_correlation_baseline(old_cell)
                self.assertEqual(fresh_rest, old_rest)
                self.assertTrue(
                    within_tolerance(fresh_corr, old_corr),
                    "the minimum-correlation baseline moved by more than the stated tolerance",
                )


class ToleranceHelperControlTests(unittest.TestCase):
    """The tolerance must absorb interpreter noise and nothing larger."""

    def test_absorbs_the_measured_interpreter_differences(self):
        self.assertTrue(within_tolerance({"a": 0.044466750000000006}, {"a": 0.045306250000000006}))
        self.assertTrue(within_tolerance({"n": 43}, {"n": 41}))

    def test_rejects_a_real_change(self):
        self.assertFalse(within_tolerance({"a": 0.05}, {"a": 0.045}))
        self.assertFalse(within_tolerance({"n": 60}, {"n": 41}))
        self.assertFalse(within_tolerance({"flag": True}, {"flag": False}))
        self.assertFalse(within_tolerance({"a": 1.0}, {"b": 1.0}))
        self.assertFalse(within_tolerance([1.0, 2.0], [1.0]))


if __name__ == "__main__":
    unittest.main()
