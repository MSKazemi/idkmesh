from __future__ import annotations

import unittest

from randomness_lab.r1_scaling import R1ScalingConfig, run_r1_scaling
from randomness_lab.r1_threshold_robustness import (
    BOOTSTRAP_RESAMPLES,
    FAMILYWISE_ALPHA,
    MULTIPLICITY_METHOD,
    audit_threshold_robustness,
    render_markdown,
)


class R1ThresholdRobustnessTests(unittest.TestCase):
    @staticmethod
    def _fixture(seed_rows_by_size: dict[int, list[tuple[int, float]]]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "experiment": "R1-collective-capability-scaling",
            "generator": "fixture",
            "config": {
                "swarm_sizes": list(seed_rows_by_size),
                "difficulty_levels": [["controlled", 0.5]],
            },
            "cells": [
                {
                    "difficulty": "controlled",
                    "family": "homogeneous",
                    "swarm_size": swarm_size,
                    "condition": "fixture",
                    "raw_trials": [
                        {
                            "seed": seed,
                            "metrics": {"verified_success_rate": success_rate},
                        }
                        for seed, success_rate in rows
                    ],
                }
                for swarm_size, rows in seed_rows_by_size.items()
            ],
        }

    def test_integrates_with_seeded_r1_deterministically(self) -> None:
        config = R1ScalingConfig(
            tasks_per_trial=20,
            trials=4,
            base_seed=23,
            swarm_sizes=(1, 2, 5),
            difficulty_levels=(("easy", 0.80), ("hard", 0.40)),
        )

        first = audit_threshold_robustness(run_r1_scaling(config))
        second = audit_threshold_robustness(run_r1_scaling(config))

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(first["base_analysis"], "R1-low-diversity-marginal-threshold")
        self.assertEqual(first["bootstrap"]["resamples"], BOOTSTRAP_RESAMPLES)
        self.assertEqual(first["multiplicity"]["method"], MULTIPLICITY_METHOD)
        self.assertEqual(first["multiplicity"]["alpha"], FAMILYWISE_ALPHA)
        self.assertEqual(first["multiplicity"]["tests_in_family"], 6)
        self.assertEqual(first["swarm_sizes"], [1, 2, 5])
        self.assertEqual(len(first["difficulties"]), 2)
        for difficulty in first["difficulties"]:
            self.assertEqual(difficulty["seeds_used"], [23, 24, 25, 26])
            self.assertEqual(len(difficulty["transitions"]), 2)

    def test_robust_threshold_requires_both_interval_methods(self) -> None:
        audit = audit_threshold_robustness(
            self._fixture(
                {
                    1: [(1, 0.60), (2, 0.60), (3, 0.60)],
                    2: [(1, 0.80), (2, 0.80), (3, 0.80)],
                    5: [(1, 0.65), (2, 0.65), (3, 0.65)],
                }
            )
        )

        controlled = audit["difficulties"][0]
        second_transition = controlled["transitions"][1]

        self.assertEqual(controlled["first_robust_diminishing_to_n"], 5)
        self.assertEqual(controlled["first_robust_negative_to_n"], 5)
        self.assertEqual(second_transition["marginal"]["normal_classification"], "negative")
        self.assertEqual(second_transition["marginal"]["bootstrap_classification"], "negative")
        self.assertEqual(second_transition["marginal"]["robust_classification"], "negative")
        self.assertTrue(second_transition["supported_diminishing_return_robust"])
        self.assertTrue(second_transition["supported_negative_return_robust"])
        self.assertEqual(
            second_transition["marginal"]["familywise_robust_classification"],
            "uncertain",
        )
        self.assertFalse(second_transition["supported_negative_return_familywise"])
        self.assertIsNone(controlled["first_familywise_negative_to_n"])

    def test_bootstrap_can_withhold_small_sample_normal_direction(self) -> None:
        audit = audit_threshold_robustness(
            self._fixture(
                {
                    1: [(1, 0.00), (2, 0.00), (3, 0.00)],
                    2: [(1, 0.00), (2, 0.10), (3, 0.10)],
                }
            )
        )

        marginal = audit["difficulties"][0]["transitions"][0]["marginal"]

        self.assertEqual(marginal["normal_classification"], "positive")
        self.assertEqual(marginal["bootstrap_classification"], "uncertain")
        self.assertFalse(marginal["classification_agrees"])
        self.assertEqual(marginal["robust_classification"], "uncertain")
        self.assertEqual(marginal["familywise_robust_classification"], "uncertain")
        self.assertEqual(audit["classification_disagreements"], 1)
        self.assertEqual(marginal["bootstrap_95_ci"][0], 0.0)

    def test_familywise_label_accepts_strong_consistent_single_question(self) -> None:
        seeds = list(range(1, 11))
        audit = audit_threshold_robustness(
            self._fixture(
                {
                    1: [(seed, 0.80) for seed in seeds],
                    2: [(seed, 0.70) for seed in seeds],
                }
            )
        )

        transition = audit["difficulties"][0]["transitions"][0]
        marginal = transition["marginal"]
        sign_test = marginal["sign_test"]

        self.assertEqual(sign_test["negative"], 10)
        self.assertEqual(sign_test["positive"], 0)
        self.assertEqual(sign_test["zero"], 0)
        self.assertAlmostEqual(sign_test["raw_p_value"], 0.001953125)
        self.assertAlmostEqual(sign_test["holm_adjusted_p_value"], 0.001953125)
        self.assertTrue(sign_test["holm_reject"])
        self.assertEqual(marginal["familywise_robust_classification"], "negative")
        self.assertTrue(transition["supported_negative_return_familywise"])
        self.assertEqual(audit["difficulties"][0]["first_familywise_negative_to_n"], 2)

    def test_holm_correction_withholds_raw_significance_across_family(self) -> None:
        seeds = list(range(1, 7))
        audit = audit_threshold_robustness(
            self._fixture(
                {
                    1: [(seed, 0.20) for seed in seeds],
                    2: [(seed, 0.30) for seed in seeds],
                    3: [(seed, 0.40) for seed in seeds],
                }
            )
        )

        first = audit["difficulties"][0]["transitions"][0]["marginal"]
        second = audit["difficulties"][0]["transitions"][1]["marginal"]

        self.assertEqual(audit["multiplicity"]["tests_in_family"], 3)
        self.assertAlmostEqual(first["sign_test"]["raw_p_value"], 0.03125)
        self.assertAlmostEqual(second["sign_test"]["raw_p_value"], 0.03125)
        self.assertAlmostEqual(first["sign_test"]["holm_adjusted_p_value"], 0.09375)
        self.assertAlmostEqual(second["sign_test"]["holm_adjusted_p_value"], 0.09375)
        self.assertEqual(first["robust_classification"], "positive")
        self.assertEqual(second["robust_classification"], "positive")
        self.assertEqual(first["familywise_robust_classification"], "uncertain")
        self.assertEqual(second["familywise_robust_classification"], "uncertain")

    def test_reuses_base_fail_closed_seed_pairing(self) -> None:
        result = self._fixture(
            {
                1: [(1, 0.10), (2, 0.20), (3, 0.30)],
                2: [(1, 0.20), (3, 0.30), (2, 0.40)],
            }
        )

        with self.assertRaisesRegex(ValueError, "identical ordered seeds"):
            audit_threshold_robustness(result)

    def test_markdown_keeps_method_and_evidence_limits_visible(self) -> None:
        audit = audit_threshold_robustness(
            self._fixture(
                {
                    1: [(1, 0.20), (2, 0.20), (3, 0.20)],
                    2: [(1, 0.30), (2, 0.30), (3, 0.30)],
                }
            )
        )

        report = render_markdown(audit)

        self.assertIn("synthetic mechanism sensitivity only", report)
        self.assertIn("Bootstrap 95% interval", report)
        self.assertIn("Holm-adjusted sign p", report)
        self.assertIn("directional or median consistency", audit["interpretation_guardrail"])
        self.assertIn("real software tasks", audit["interpretation_guardrail"])


if __name__ == "__main__":
    unittest.main()
