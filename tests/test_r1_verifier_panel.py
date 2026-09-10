"""The verifier panel added to ``run_r1_condition`` for issue #380.

The panel exists so that hypothesis 2's *verification* half can be asked of the
simulator at all: before it, every candidate was read by exactly one verifier,
so there was no panel for verifiers to be independent within.

Two properties matter more than the feature itself.

``panel_size = 1`` must reproduce the single-verifier behaviour **draw for
draw**, not merely equivalently, because every committed R1 artifact was
generated under it. That is already enforced by the committed-payload replay
tests, which detect a single extra ``rng`` call in the candidate loop; the test
here pins the observable half of it.

And a panel of ``k`` must cost ``k``. ``human_attention`` feeds
``resource_cost``, which feeds ``verified_utility_per_unit_cost`` -- the
equal-budget metric hypothesis 2 is stated in terms of. An unbilled panel would
buy accuracy with human attention nobody charged for and then win a comparison
it was never subjected to.
"""

from __future__ import annotations

import dataclasses
import unittest

from randomness_lab.r1 import (
    R1ExperimentConfig,
    Verifier,
    _panel_accepts,
    build_r1_conditions,
    run_r1_condition,
)


def _arm(**overrides):
    condition = build_r1_conditions(R1ExperimentConfig(swarm_size=5))[0]
    return dataclasses.replace(condition, **overrides)


def _candidates(result):
    return [
        candidate
        for record in result["task_records"]
        for candidate in record["candidates"]
    ]


class PanelAggregationTests(unittest.TestCase):
    """``need = floor(quorum * k) + 1``, the rule E018 uses."""

    def test_a_panel_of_one_accepts_exactly_its_single_vote(self) -> None:
        self.assertTrue(_panel_accepts([True], 0.5))
        self.assertFalse(_panel_accepts([False], 0.5))

    def test_the_default_quorum_is_a_symmetric_majority(self) -> None:
        # k = 3 -> need 2; k = 5 -> need 3.
        self.assertFalse(_panel_accepts([True, False, False], 0.5))
        self.assertTrue(_panel_accepts([True, True, False], 0.5))
        self.assertFalse(_panel_accepts([True, True, False, False, False], 0.5))
        self.assertTrue(_panel_accepts([True, True, True, False, False], 0.5))

    def test_quorum_spans_the_whole_need_range(self) -> None:
        """`need` must reach 1 and k, not just the majority.

        A prior result in this repository survives only on a sub-range of
        `need` and dissolves once the full range is opened, so a quorum that
        could only express the middle would hide exactly the effect worth
        measuring.
        """
        votes = [True, False, False, False, False]
        self.assertTrue(_panel_accepts(votes, 0.0), "quorum 0 should mean need=1")
        self.assertFalse(_panel_accepts([True] * 4 + [False], 0.99), "need should reach k")
        self.assertTrue(_panel_accepts([True] * 5, 0.99))


class PanelDefaultTests(unittest.TestCase):
    def test_the_default_panel_emits_no_panel_fields(self) -> None:
        """Single-verifier payloads must stay byte-identical to the artifacts."""

        result = run_r1_condition(_arm(), tasks=4, seed=11)
        for candidate in _candidates(result):
            self.assertNotIn("verifier_panel", candidate)
            self.assertNotIn("verifier_votes", candidate)

    def test_a_real_panel_records_its_members_and_votes(self) -> None:
        verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 4))
        result = run_r1_condition(
            _arm(verifiers=verifiers, panel_size=3), tasks=4, seed=11
        )
        candidates = _candidates(result)
        self.assertTrue(candidates, "no candidates were produced")
        for candidate in candidates:
            self.assertEqual(len(candidate["verifier_panel"]), 3)
            self.assertEqual(len(candidate["verifier_votes"]), 3)
            # The recorded decision is the quorum over the recorded votes.
            self.assertEqual(
                candidate["accepted"],
                _panel_accepts(candidate["verifier_votes"], 0.5),
            )
            # `verifier` stays the first panellist, so the field keeps its shape.
            self.assertEqual(candidate["verifier"], candidate["verifier_panel"][0])


class PanelCostTests(unittest.TestCase):
    def test_a_panel_of_k_costs_k(self) -> None:
        """The decision most likely to determine hypothesis 2's answer."""

        verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 4))
        for panel_size in (1, 2, 3):
            with self.subTest(panel_size=panel_size):
                condition = _arm(verifiers=verifiers, panel_size=panel_size)
                result = run_r1_condition(condition, tasks=5, seed=23)
                expected = sum(
                    sum(
                        verifier.attention_cost
                        for verifier in condition.verifiers[:panel_size]
                    )
                    for _ in _candidates(result)
                )
                self.assertAlmostEqual(
                    result["metrics"]["total_human_attention_proxy"], expected
                )

    def test_attention_scales_with_panel_size_at_equal_candidate_count(self) -> None:
        verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 4))
        one = run_r1_condition(_arm(verifiers=verifiers, panel_size=1), tasks=1, seed=5)
        three = run_r1_condition(
            _arm(verifiers=verifiers, panel_size=3), tasks=1, seed=5
        )
        # One task, so the candidate set is fixed before any verifier draw.
        self.assertEqual(len(_candidates(one)), len(_candidates(three)))
        self.assertAlmostEqual(
            three["metrics"]["total_human_attention_proxy"],
            3 * one["metrics"]["total_human_attention_proxy"],
        )


class PanelValidationTests(unittest.TestCase):
    def test_panel_size_must_be_at_least_one(self) -> None:
        with self.assertRaises(ValueError):
            _arm(panel_size=0)

    def test_quorum_must_be_a_fraction_below_one(self) -> None:
        for bad in (-0.1, 1.0, 1.5):
            with self.subTest(quorum=bad), self.assertRaises(ValueError):
                _arm(panel_quorum=bad)


if __name__ == "__main__":
    unittest.main()
