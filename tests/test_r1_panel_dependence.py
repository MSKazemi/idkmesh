"""Panel dependence in ``run_r1_condition``, checked against E018's closed form.

Issue #380's acceptance criterion is that the two dependence shapes "agree at
correlation 0 and 1". This module turns that from an assertion into a
measurement: the sampler in ``randomness_lab.r1`` is run against the analytic
error probabilities in ``sim/e018_dependence_models.py``, which are computed
independently of it.

The samplers are meant to *be* E018's models, not to resemble them:

* ``shared_shock`` -- with probability ``rho`` the whole panel is judged on one
  draw, otherwise each panellist draws independently.
* ``item_difficulty`` -- the candidate draws a difficulty
  ``p ~ Beta(mu*s, (1-mu)*s)`` with ``s = (1-rho)/rho``, and panellists then err
  independently at ``p``. That Beta has mean ``mu`` and intra-class correlation
  ``1/(alpha+beta+1) = rho``, so the parameter means what it says.

Tolerances are Monte-Carlo, not aspirational: at N draws the standard error of a
proportion is at most ``0.5/sqrt(N)``, so the bounds below are several standard
errors wide and the seeds are fixed.
"""

from __future__ import annotations

import importlib.util
import math
import random
import unittest

from randomness_lab.r1 import (
    PANEL_DEPENDENCE_SHAPES,
    Verifier,
    _dependent_panel_votes,
    _panel_accepts,
)
from sim.e018_dependence_models import (
    independent_error,
    item_difficulty_error,
    shared_shock_error,
)

# Marked `sim`: this module replays a committed experiment artifact or runs a
# parameter sweep, so it costs seconds rather than milliseconds. `make test`
# (the pre-commit tier) runs `-m "not sim"` and skips it; `make nightly` runs
# `-m sim`. CI is unaffected -- the PR gate runs a plain `pytest` with no marker
# filter, so coverage there is unchanged.
#
# The import is guarded the way tests/test_schema_validity.py guards
# `jsonschema`. Narrow workflow jobs run this module through
# `python -m unittest` on a bare interpreter, and a module-scope
# `import pytest` there makes the job fail to collect the file at all rather
# than run it. The marker is a tier hint for pytest, never a precondition for
# the assertions, so without pytest it degrades to no marker.
if importlib.util.find_spec("pytest") is not None:
    import pytest

    pytestmark = pytest.mark.sim
else:  # pragma: no cover - the bare-interpreter CI jobs take this path
    pytestmark = ()


DRAWS = 40_000
SEED = 20260910


def _panel(size, accuracy):
    """A homogeneous panel whose per-verifier accuracy on a good candidate is `accuracy`."""

    return tuple(
        Verifier(f"verifier-{index}", sensitivity=accuracy)
        for index in range(1, size + 1)
    )


def _measured_error(size, accuracy, correlation, shape, quorum=0.5, draws=DRAWS):
    """Fraction of candidates the panel gets *wrong*, by simulation."""

    rng = random.Random(SEED)
    panel = _panel(size, accuracy)
    wrong = 0
    for _ in range(draws):
        votes = _dependent_panel_votes(True, panel, rng, correlation, shape)
        # The candidate is good, so a wrong panel is one that fails to accept.
        if not _panel_accepts(votes, quorum):
            wrong += 1
    return wrong / draws


class PanelDependenceMatchesE018Tests(unittest.TestCase):
    """The sampler must reproduce the analytic model, not merely resemble it."""

    def test_shared_shock_matches_its_closed_form(self) -> None:
        for size in (3, 5):
            for accuracy in (0.70, 0.85):
                for correlation in (0.25, 0.5875, 0.75):
                    with self.subTest(k=size, acc=accuracy, rho=correlation):
                        measured = _measured_error(
                            size, accuracy, correlation, "shared_shock"
                        )
                        expected = shared_shock_error(size, accuracy, correlation)
                        self.assertAlmostEqual(measured, expected, delta=0.01)

    def test_item_difficulty_matches_its_closed_form(self) -> None:
        for size in (3, 5):
            for accuracy in (0.70, 0.85):
                for correlation in (0.25, 0.5875, 0.75):
                    with self.subTest(k=size, acc=accuracy, rho=correlation):
                        measured = _measured_error(
                            size, accuracy, correlation, "item_difficulty"
                        )
                        expected = item_difficulty_error(size, accuracy, correlation)
                        self.assertAlmostEqual(measured, expected, delta=0.01)


class ShapesAgreeAtTheEndpointsTests(unittest.TestCase):
    """#380's acceptance criterion, measured rather than asserted."""

    def test_at_correlation_one_both_shapes_are_the_single_verifier_error(self) -> None:
        for size in (3, 5):
            for accuracy in (0.70, 0.85):
                with self.subTest(k=size, acc=accuracy):
                    shock = _measured_error(size, accuracy, 1.0, "shared_shock")
                    item = _measured_error(size, accuracy, 1.0, "item_difficulty")
                    # A perfectly dependent panel is one verifier.
                    self.assertAlmostEqual(shock, 1 - accuracy, delta=0.01)
                    self.assertAlmostEqual(item, 1 - accuracy, delta=0.01)
                    self.assertAlmostEqual(shock, item, delta=0.015)

    def test_the_analytic_models_agree_exactly_at_both_endpoints(self) -> None:
        # No sampling here: this is the property the samplers are checked against.
        for size in (1, 3, 5, 9):
            for accuracy in (0.55, 0.70, 0.85, 0.95):
                with self.subTest(k=size, acc=accuracy):
                    self.assertAlmostEqual(
                        shared_shock_error(size, accuracy, 0.0),
                        item_difficulty_error(size, accuracy, 0.0),
                        places=12,
                    )
                    self.assertAlmostEqual(
                        shared_shock_error(size, accuracy, 0.0),
                        independent_error(size, accuracy),
                        places=12,
                    )
                    self.assertAlmostEqual(
                        shared_shock_error(size, accuracy, 1.0),
                        item_difficulty_error(size, accuracy, 1.0),
                        places=12,
                    )


class EndpointsAreOneImplementationTests(unittest.TestCase):
    """At rho 0 and rho 1 the shapes must be the same code, not merely close.

    Every assertion here failed before the endpoints were shared. They were
    reachable only by calling the sampler directly -- `run_r1_condition` guards
    `correlation <= 0.0` and never enters this function at rho 0 -- so the
    defects sat behind a green suite. Surfaced by the parallel implementation in
    PR #424, which had shared endpoints from the start.
    """

    PANEL = tuple(Verifier(f"panelist-{i}", sensitivity=0.8) for i in range(1, 4))

    def test_the_shapes_return_the_same_vector_at_both_endpoints(self) -> None:
        for correlation in (0.0, 1.0):
            with self.subTest(correlation=correlation):
                shock = _dependent_panel_votes(
                    True, self.PANEL, random.Random(7), correlation, "shared_shock"
                )
                item = _dependent_panel_votes(
                    True, self.PANEL, random.Random(7), correlation, "item_difficulty"
                )
                self.assertEqual(shock, item)

    def test_the_shapes_consume_the_same_rng_at_both_endpoints(self) -> None:
        """Equal output from unequal draws would re-phase everything after it."""

        for correlation in (0.0, 1.0):
            with self.subTest(correlation=correlation):
                left, right = random.Random(7), random.Random(7)
                _dependent_panel_votes(
                    True, self.PANEL, left, correlation, "shared_shock"
                )
                _dependent_panel_votes(
                    True, self.PANEL, right, correlation, "item_difficulty"
                )
                self.assertEqual(left.getstate(), right.getstate())

    def test_zero_correlation_does_not_divide_by_zero(self) -> None:
        """`item_difficulty` computes (1 - rho) / rho."""

        votes = _dependent_panel_votes(
            True, self.PANEL, random.Random(3), 0.0, "item_difficulty"
        )
        self.assertEqual(len(votes), len(self.PANEL))

    def test_a_degenerate_accuracy_does_not_raise_from_inside_betavariate(self) -> None:
        """A Beta with a zero parameter is undefined; gammavariate says so obscurely."""

        for sensitivity in (0.0, 1.0):
            panel = tuple(
                Verifier(f"p{i}", sensitivity=sensitivity) for i in range(1, 4)
            )
            with self.subTest(sensitivity=sensitivity):
                votes = _dependent_panel_votes(
                    True, panel, random.Random(1), 0.5, "item_difficulty"
                )
                self.assertEqual(votes, [bool(sensitivity)] * 3)


class ShapeSeparationTests(unittest.TestCase):
    def test_the_beta_binomial_tail_is_heavier_between_the_endpoints(self) -> None:
        """The direction E017 reports: a flat shock understates joint failure.

        This asserts the ordering only. It deliberately does not claim to
        reproduce E017's 1.71x, which is a figure for the *unanimous* tail on a
        measured 25-verifier panel, not for majority error here.
        """
        for size in (3, 5):
            for accuracy in (0.70, 0.85):
                with self.subTest(k=size, acc=accuracy):
                    self.assertGreater(
                        item_difficulty_error(size, accuracy, 0.5875),
                        shared_shock_error(size, accuracy, 0.5875),
                    )


class DependenceContractTests(unittest.TestCase):
    def test_both_shapes_are_registered(self) -> None:
        self.assertEqual(
            sorted(PANEL_DEPENDENCE_SHAPES), ["item_difficulty", "shared_shock"]
        )

    def test_item_difficulty_refuses_a_heterogeneous_panel(self) -> None:
        """Guessing a copula would produce a number with no stated meaning."""

        panel = (
            Verifier("verifier-1", sensitivity=0.90),
            Verifier("verifier-2", sensitivity=0.70),
        )
        with self.assertRaises(ValueError):
            _dependent_panel_votes(True, panel, random.Random(1), 0.5, "item_difficulty")

    def test_shared_shock_accepts_a_heterogeneous_panel(self) -> None:
        # A shared draw against each verifier's own threshold is well defined.
        panel = (
            Verifier("verifier-1", sensitivity=0.90),
            Verifier("verifier-2", sensitivity=0.70),
        )
        votes = _dependent_panel_votes(
            True, panel, random.Random(1), 0.5, "shared_shock"
        )
        self.assertEqual(len(votes), 2)

    def test_dependence_applies_to_the_error_not_the_acceptance(self) -> None:
        """A bad candidate's correct outcome is a *rejection*.

        If dependence were applied to the accept event instead of the error
        event, a strongly dependent panel would converge on accepting bad
        candidates rather than rejecting them, and the shape would invert.
        """
        panel = _panel(5, 0.85)  # false_positive_rate defaults low
        rng = random.Random(SEED)
        wrongly_accepted = 0
        for _ in range(DRAWS):
            votes = _dependent_panel_votes(False, panel, rng, 0.9, "shared_shock")
            if _panel_accepts(votes, 0.5):
                wrongly_accepted += 1
        rate = wrongly_accepted / DRAWS
        expected = panel[0].false_positive_rate
        self.assertAlmostEqual(rate, expected, delta=0.02)


if __name__ == "__main__":
    unittest.main()
