from __future__ import annotations

import unittest

from randomness_lab.r1_low_diversity_threshold import (
    analyze_low_diversity_threshold,
    render_markdown,
)
from randomness_lab.r1_scaling import R1ScalingConfig, run_r1_scaling


class R1LowDiversityThresholdTests(unittest.TestCase):
    @staticmethod
    def _fixture(seed_rows_by_size: dict[int, list[tuple[int, float]]]) -> dict[str, object]:
        cells = []
        for swarm_size, rows in seed_rows_by_size.items():
            cells.append(
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
            )
        return {
            "schema_version": 1,
            "experiment": "R1-collective-capability-scaling",
            "generator": "fixture",
            "config": {
                "swarm_sizes": list(seed_rows_by_size),
                "difficulty_levels": [["controlled", 0.5]],
            },
            "cells": cells,
        }

    def test_integrates_with_seeded_r1_result_deterministically(self) -> None:
        config = R1ScalingConfig(
            tasks_per_trial=25,
            trials=3,
            base_seed=17,
            swarm_sizes=(1, 2, 5),
            difficulty_levels=(("easy", 0.80), ("hard", 0.40)),
        )

        first = analyze_low_diversity_threshold(run_r1_scaling(config))
        second = analyze_low_diversity_threshold(run_r1_scaling(config))

        self.assertEqual(first, second)
        self.assertEqual(first["source_generator"], "randomness_lab.r1_scaling.v1")
        self.assertEqual(first["low_diversity_proxy"], "homogeneous")
        self.assertEqual(first["swarm_sizes"], [1, 2, 5])
        self.assertEqual(len(first["difficulties"]), 2)
        for difficulty in first["difficulties"]:
            self.assertEqual(difficulty["seeds_used"], [17, 18, 19])
            self.assertEqual(len(difficulty["transitions"]), 2)
            for transition in difficulty["transitions"]:
                summary = transition[
                    "marginal_verified_success_per_additional_worker"
                ]
                self.assertEqual(summary["n"], 3)

    def test_detects_supported_diminishing_and_negative_thresholds(self) -> None:
        result = self._fixture(
            {
                1: [(1, 0.10), (2, 0.20), (3, 0.30)],
                2: [(1, 0.40), (2, 0.50), (3, 0.60)],
                5: [(1, 0.55), (2, 0.65), (3, 0.75)],
                10: [(1, 0.45), (2, 0.55), (3, 0.65)],
            }
        )

        analysis = analyze_low_diversity_threshold(result)
        controlled = analysis["difficulties"][0]
        transitions = controlled["transitions"]

        self.assertEqual(controlled["first_supported_diminishing_to_n"], 5)
        self.assertEqual(controlled["first_supported_negative_to_n"], 10)
        self.assertEqual(
            controlled["first_interval_not_strictly_positive_to_n"], 10
        )
        self.assertEqual(
            transitions[0]["marginal_verified_success_per_additional_worker"][
                "classification"
            ],
            "positive",
        )
        self.assertTrue(transitions[1]["supported_diminishing_return"])
        self.assertAlmostEqual(
            transitions[1]["change_from_previous_marginal"]["mean"], -0.25
        )
        self.assertTrue(transitions[2]["supported_negative_return"])
        self.assertAlmostEqual(
            transitions[2]["marginal_verified_success_per_additional_worker"][
                "mean"
            ],
            -0.02,
        )

    def test_rejects_unpaired_seed_rows(self) -> None:
        result = self._fixture(
            {
                1: [(1, 0.10), (2, 0.20), (3, 0.30)],
                2: [(1, 0.30), (3, 0.40), (2, 0.50)],
            }
        )

        with self.assertRaisesRegex(ValueError, "identical ordered seeds"):
            analyze_low_diversity_threshold(result)

    def test_topology_extension_uses_only_flat_cells(self) -> None:
        config = R1ScalingConfig(
            tasks_per_trial=10,
            trials=2,
            base_seed=7,
            swarm_sizes=(1, 2),
            difficulty_levels=(("easy", 0.80),),
        )
        result = run_r1_scaling(config, topologies=("flat", "role_specialized"))

        analysis = analyze_low_diversity_threshold(result)

        self.assertEqual(analysis["source_schema_version"], 2)
        self.assertEqual(analysis["topology"], "flat")
        self.assertEqual(len(analysis["difficulties"][0]["transitions"]), 1)

    def test_markdown_keeps_evidence_boundary_visible(self) -> None:
        analysis = analyze_low_diversity_threshold(
            self._fixture(
                {
                    1: [(1, 0.10), (2, 0.20), (3, 0.30)],
                    2: [(1, 0.40), (2, 0.50), (3, 0.60)],
                    5: [(1, 0.55), (2, 0.65), (3, 0.75)],
                }
            )
        )

        report = render_markdown(analysis)

        self.assertIn("synthetic mechanism only", report)
        self.assertIn("not formal", report)
        self.assertIn("supported diminishing to N: 5", report)
        self.assertIn("cannot establish a real-world scaling law", report)


if __name__ == "__main__":
    unittest.main()
