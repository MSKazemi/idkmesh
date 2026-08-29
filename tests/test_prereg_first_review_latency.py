"""The preregistered analysis must be proven correct before any datum exists.

Every fixture here is synthetic. That is the point: the machinery is validated
against known answers now, so that when real contributors appear the protocol can
be run without anyone touching the code that computes the result.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from scripts.prereg_first_review_latency import (
    ARM_FAST,
    ARM_SLOW,
    LATENCY_BOUNDARY_HOURS,
    MINIMUM_UNITS_PER_ARM,
    STRATUM_NEVER_REVIEWED,
    analyze,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _pull(
    number: int,
    author: str,
    *,
    opened_hours: float = 0.0,
    review_hours: float | None = None,
    closed_days: float = 1.0,
) -> dict[str, object]:
    ready = BASE + timedelta(hours=opened_hours)
    return {
        "number": number,
        "author": author,
        "created_at": _stamp(ready),
        "review_ready_at": _stamp(ready),
        "first_independent_review_at": (
            None if review_hours is None else _stamp(ready + timedelta(hours=review_hours))
        ),
        "closed_at": _stamp(ready + timedelta(days=closed_days)),
    }


def _snapshot(pulls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "version": 1,
        "repository": "MSKazemi/idkmesh",
        "cutoff_at": _stamp(BASE + timedelta(days=400)),
        "pull_requests": pulls,
    }


class PreregisteredAnalysisTests(unittest.TestCase):
    def _population(self, fast_recur: int, slow_recur: int) -> dict[str, object]:
        """Build both arms at exactly the minimum size, with known outcomes."""
        pulls: list[dict[str, object]] = []
        number = 1
        for arm_index, (label, review_hours, recurring) in enumerate(
            [("fast", 1.0, fast_recur), ("slow", 200.0, slow_recur)]
        ):
            for unit in range(MINIMUM_UNITS_PER_ARM):
                author = f"actor:{label}-{unit:03d}"
                offset = float(arm_index * 10_000 + unit)
                pulls.append(
                    _pull(number, author, opened_hours=offset, review_hours=review_hours)
                )
                number += 1
                if unit < recurring:
                    # A second closure ten days after the first, inside the window.
                    pulls.append(
                        _pull(number, author, opened_hours=offset + 240.0, review_hours=None)
                    )
                    number += 1
        return _snapshot(pulls)

    def test_underpowered_snapshot_returns_no_estimate(self) -> None:
        result = analyze(_snapshot([_pull(1, "actor:a", review_hours=1.0)]))
        self.assertFalse(result["analyzable"])
        self.assertNotIn("risk_difference", result)
        self.assertIn("at least", result["not_analyzed_because"])

    def test_a_faster_reviewed_arm_that_recurs_more_moves_the_posterior_up(self) -> None:
        result = analyze(self._population(fast_recur=16, slow_recur=4))
        self.assertTrue(result["analyzable"])
        self.assertEqual(MINIMUM_UNITS_PER_ARM, result["arms"][ARM_FAST]["units"])
        self.assertEqual(MINIMUM_UNITS_PER_ARM, result["arms"][ARM_SLOW]["units"])
        self.assertEqual(16, result["arms"][ARM_FAST]["recurred"])
        self.assertEqual(4, result["arms"][ARM_SLOW]["recurred"])
        difference = result["risk_difference"]
        self.assertGreater(difference["posterior_mean"], 0.4)
        self.assertGreater(difference["posterior_probability_fast_arm_higher"], 0.99)

    def test_the_direction_reverses_when_the_data_reverses(self) -> None:
        forward = analyze(self._population(fast_recur=16, slow_recur=4))["risk_difference"]
        reverse = analyze(self._population(fast_recur=4, slow_recur=16))["risk_difference"]
        self.assertAlmostEqual(
            forward["posterior_mean"], -reverse["posterior_mean"], places=6
        )
        self.assertLess(reverse["posterior_probability_fast_arm_higher"], 0.01)

    def test_no_difference_in_the_data_leaves_the_posterior_centred(self) -> None:
        difference = analyze(self._population(fast_recur=10, slow_recur=10))["risk_difference"]
        self.assertAlmostEqual(0.0, difference["posterior_mean"], places=6)
        # The grid assigns a little mass to an exact tie, which the continuous
        # posterior does not. That mass bounds the discretization error, so the
        # two tails plus the tie must account for all of it.
        tie = difference["grid_tie_mass"]
        self.assertLess(tie, 0.01)
        self.assertAlmostEqual(
            0.5, difference["posterior_probability_fast_arm_higher"] + tie / 2.0, places=5
        )

    def test_the_boundary_is_closed_on_the_slow_side(self) -> None:
        """Exactly 72 hours is slow. The rule cannot be re-read after the fact."""
        at_boundary = analyze(
            _snapshot([_pull(1, "actor:a", review_hours=LATENCY_BOUNDARY_HOURS)])
        )
        just_inside = analyze(
            _snapshot(
                [_pull(1, "actor:a", review_hours=LATENCY_BOUNDARY_HOURS - 0.001)]
            )
        )
        self.assertEqual(1, at_boundary["arms"][ARM_SLOW]["units"])
        self.assertEqual(0, at_boundary["arms"][ARM_FAST]["units"])
        self.assertEqual(1, just_inside["arms"][ARM_FAST]["units"])

    def test_an_unreviewed_unit_is_stratified_out_not_dropped(self) -> None:
        result = analyze(_snapshot([_pull(1, "actor:a", review_hours=None)]))
        self.assertEqual(1, result["arms"][STRATUM_NEVER_REVIEWED]["units"])
        self.assertEqual(0, result["arms"][ARM_FAST]["units"])
        self.assertEqual(0, result["arms"][ARM_SLOW]["units"])

    def test_recurrence_outside_the_window_does_not_count(self) -> None:
        inside = analyze(
            _snapshot(
                [
                    _pull(1, "actor:a", review_hours=1.0, closed_days=1.0),
                    _pull(2, "actor:a", opened_hours=24.0 * 80, review_hours=None, closed_days=1.0),
                ]
            )
        )
        outside = analyze(
            _snapshot(
                [
                    _pull(1, "actor:a", review_hours=1.0, closed_days=1.0),
                    _pull(2, "actor:a", opened_hours=24.0 * 200, review_hours=None, closed_days=1.0),
                ]
            )
        )
        self.assertEqual(1, inside["arms"][ARM_FAST]["recurred"])
        self.assertEqual(0, outside["arms"][ARM_FAST]["recurred"])

    def test_the_result_is_deterministic(self) -> None:
        snapshot = self._population(fast_recur=13, slow_recur=7)
        first = json.dumps(analyze(snapshot), sort_keys=True)
        second = json.dumps(analyze(snapshot), sort_keys=True)
        self.assertEqual(first, second)

    def test_no_authority_is_claimed(self) -> None:
        result = analyze(self._population(fast_recur=16, slow_recur=4))
        self.assertFalse(result["authority"]["causal_claim"])
        self.assertFalse(result["authority"]["policy_activation"])
        self.assertFalse(result["authority"]["github_write"])
        self.assertEqual(
            "descriptive_association_not_a_causal_effect",
            result["risk_difference"]["interpretation"],
        )


if __name__ == "__main__":
    unittest.main()
