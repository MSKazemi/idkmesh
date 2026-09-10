"""Verifier-panel contracts for issue #380.

The panel exists so hypothesis 2's verification half can be asked of the
simulator at all. The legacy ``panel_size = 1`` path remains draw-for-draw
compatible with committed R1 evidence, while non-legacy panels must be
self-describing, use distinct members, and expose the attention-billing
counterfactual required by the issue design.
"""

from __future__ import annotations

import dataclasses
import random
import unittest

from randomness_lab.r1 import (
    R1ExperimentConfig,
    Verifier,
    _panel_accepts,
    _select_panel,
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
        self.assertFalse(_panel_accepts([True, False, False], 0.5))
        self.assertTrue(_panel_accepts([True, True, False], 0.5))
        self.assertFalse(_panel_accepts([True, True, False, False, False], 0.5))
        self.assertTrue(_panel_accepts([True, True, True, False, False], 0.5))

    def test_quorum_spans_the_whole_need_range(self) -> None:
        votes = [True, False, False, False, False]
        self.assertTrue(_panel_accepts(votes, 0.0), "quorum 0 should mean need=1")
        self.assertFalse(
            _panel_accepts([True] * 4 + [False], 0.99),
            "need should reach k",
        )
        self.assertTrue(_panel_accepts([True] * 5, 0.99))


class PanelDefaultTests(unittest.TestCase):
    def test_the_default_panel_emits_no_panel_fields_or_metadata(self) -> None:
        """Legacy single-verifier payloads must stay byte-identical."""

        result = run_r1_condition(_arm(), tasks=4, seed=11)
        for candidate in _candidates(result):
            self.assertNotIn("verifier_panel", candidate)
            self.assertNotIn("verifier_votes", candidate)
        for field in ("panel_size", "panel_quorum", "panel_attention_billing"):
            self.assertNotIn(field, result["condition"])

    def test_a_real_panel_records_members_votes_and_configuration(self) -> None:
        verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 4))
        result = run_r1_condition(
            _arm(verifiers=verifiers, panel_size=3), tasks=4, seed=11
        )
        candidates = _candidates(result)
        self.assertTrue(candidates, "no candidates were produced")
        for candidate in candidates:
            self.assertEqual(len(candidate["verifier_panel"]), 3)
            self.assertEqual(len(candidate["verifier_votes"]), 3)
            self.assertEqual(len(set(candidate["verifier_panel"])), 3)
            self.assertEqual(
                candidate["accepted"],
                _panel_accepts(candidate["verifier_votes"], 0.5),
            )
            self.assertEqual(candidate["verifier"], candidate["verifier_panel"][0])
        self.assertEqual(result["condition"]["panel_size"], 3)
        self.assertEqual(result["condition"]["panel_quorum"], 0.5)
        self.assertEqual(
            result["condition"]["panel_attention_billing"], "per_verifier"
        )


class PanelMembershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 5))

    def test_fixed_panel_uses_distinct_prefix_members(self) -> None:
        condition = _arm(verifiers=self.verifiers, panel_size=3)
        self.assertEqual(_select_panel(condition, random.Random(7)), self.verifiers[:3])

    def test_random_panel_samples_without_replacement(self) -> None:
        condition = _arm(
            verifiers=self.verifiers,
            panel_size=3,
            verifier_assignment="random",
        )
        rng = random.Random(17)
        for _ in range(25):
            panel = _select_panel(condition, rng)
            self.assertEqual(len({verifier.name for verifier in panel}), 3)

    def test_random_panel_of_one_keeps_legacy_choice_rng_state(self) -> None:
        condition = _arm(
            verifiers=self.verifiers,
            panel_size=1,
            verifier_assignment="random",
        )
        panel_rng = random.Random(23)
        legacy_rng = random.Random(23)
        self.assertEqual(
            _select_panel(condition, panel_rng)[0],
            legacy_rng.choice(self.verifiers),
        )
        self.assertEqual(panel_rng.getstate(), legacy_rng.getstate())


class PanelCostTests(unittest.TestCase):
    def test_default_panel_bills_every_verifier(self) -> None:
        verifiers = tuple(Verifier(f"verifier-{i}") for i in range(1, 4))
        condition = _arm(verifiers=verifiers, panel_size=3)
        result = run_r1_condition(condition, tasks=1, seed=5)
        expected = len(_candidates(result)) * sum(
            verifier.attention_cost for verifier in verifiers
        )
        self.assertAlmostEqual(
            result["metrics"]["total_human_attention_proxy"], expected
        )

    def test_per_candidate_billing_is_explicit_and_rng_neutral(self) -> None:
        verifiers = (
            Verifier("verifier-1", attention_cost=0.05),
            Verifier("verifier-2", attention_cost=0.10),
            Verifier("verifier-3", attention_cost=0.15),
        )
        per_verifier = run_r1_condition(
            _arm(
                verifiers=verifiers,
                panel_size=3,
                panel_attention_billing="per_verifier",
            ),
            tasks=1,
            seed=5,
        )
        per_candidate = run_r1_condition(
            _arm(
                verifiers=verifiers,
                panel_size=3,
                panel_attention_billing="per_candidate",
            ),
            tasks=1,
            seed=5,
        )
        self.assertEqual(per_verifier["task_records"], per_candidate["task_records"])
        candidate_count = len(_candidates(per_candidate))
        one_equivalent_read = sum(v.attention_cost for v in verifiers) / len(verifiers)
        self.assertAlmostEqual(
            per_candidate["metrics"]["total_human_attention_proxy"],
            candidate_count * one_equivalent_read,
        )
        self.assertAlmostEqual(
            per_verifier["metrics"]["total_human_attention_proxy"],
            3 * per_candidate["metrics"]["total_human_attention_proxy"],
        )
        self.assertEqual(
            per_candidate["condition"]["panel_attention_billing"], "per_candidate"
        )


class PanelValidationTests(unittest.TestCase):
    def test_panel_size_must_be_a_positive_integer_within_the_pool(self) -> None:
        verifiers = (Verifier("v1"), Verifier("v2"))
        for bad in (0, -1, True, 3):
            with self.subTest(panel_size=bad), self.assertRaises(ValueError):
                _arm(verifiers=verifiers, panel_size=bad)

    def test_verifier_names_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _arm(verifiers=(Verifier("same"), Verifier("same")), panel_size=2)

    def test_quorum_must_be_a_fraction_below_one(self) -> None:
        for bad in (-0.1, 1.0, 1.5):
            with self.subTest(quorum=bad), self.assertRaises(ValueError):
                _arm(panel_quorum=bad)

    def test_attention_billing_mode_is_explicit(self) -> None:
        for mode in ("per_verifier", "per_candidate"):
            with self.subTest(mode=mode):
                self.assertEqual(_arm(panel_attention_billing=mode).panel_attention_billing, mode)
        with self.assertRaises(ValueError):
            _arm(panel_attention_billing="free")


if __name__ == "__main__":
    unittest.main()
