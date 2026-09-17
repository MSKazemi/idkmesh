from __future__ import annotations

import unittest

from randomness_lab.r1_scaling import R1ScalingConfig, run_r1_scaling
from randomness_lab.r1_threshold_robustness import (
    BOOTSTRAP_RESAMPLES,
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
        self.assertEqual(first["base_analysis"], "R1-low-diversity-marginal-threshold")
        self.assertEqual(first["bootstrap"]["resamples"], BOOTSTRAP_RESAMPLES)
        self.assertEqual(first["swarm_sizes"], [1, 2, 5])
        self.assertEqual(len(first["difficulties"]), 2)
        for difficulty in first["difficulties"]:
            self.assertEqual(difficulty["seeds_used"], [23, 24, 25, 26])
            self.assertEqual(len(difficulty["transitions"]), 2)

    def test_robust_threshold_requires_both_methods_to_support_direction(self) -> None:
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
        self.assertEqual(audit["classification_disagreements"], 1)
        self.assertEqual(marginal["bootstrap_95_ci"][0], 0.0)

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
        self.assertIn("Disagreement is reported as", audit["interpretation_guardrail"])
        self.assertIn("real software tasks", audit["interpretation_guardrail"])


if __name__ == "__main__":
    unittest.main()
