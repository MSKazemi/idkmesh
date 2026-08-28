import math
import unittest

from scripts.sequential_evidence import (
    confidence_sequence,
    error_budget,
    importance_weight_effective_sample_size,
    ips_experiment_gate,
    ips_sequence,
    paired_effect_sequence,
    paired_experiment_gate,
)


class SequentialEvidenceTests(unittest.TestCase):
    def test_error_budget_is_summable(self):
        delta = 0.05
        partial = sum(error_budget(delta, t) for t in range(1, 10001))
        self.assertLess(partial, delta)
        self.assertAlmostEqual(partial, delta * (1.0 - 1.0 / 10001.0), places=12)

    def test_confidence_sequence_tightens_for_stable_samples(self):
        rows = confidence_sequence([0.75] * 256, delta=0.05)
        self.assertEqual(len(rows), 256)
        self.assertAlmostEqual(rows[-1]["mean"], 0.75)
        self.assertLess(rows[-1]["radius"], rows[15]["radius"])
        self.assertLessEqual(rows[-1]["lower"], 0.75)
        self.assertGreaterEqual(rows[-1]["upper"], 0.75)

    def test_paired_sequence_uses_candidate_minus_baseline(self):
        rows = paired_effect_sequence([0.9, 0.8], [0.4, 0.3])
        self.assertAlmostEqual(rows[-1]["mean"], 0.5)

    def test_strong_paired_effect_can_nominate_experiment(self):
        result = paired_experiment_gate(
            [1.0] * 128,
            [0.0] * 128,
            min_effect=0.10,
            min_samples=32,
            delta=0.05,
            hard_guard_ok=True,
        )
        self.assertEqual(result["decision"], "experiment_candidate")
        self.assertGreater(result["lower_confidence"], 0.10)
        self.assertEqual(result["authority"], "candidate_only")

    def test_hard_guard_cannot_be_compensated_by_strong_statistics(self):
        result = paired_experiment_gate(
            [1.0] * 256,
            [0.0] * 256,
            min_effect=0.01,
            min_samples=32,
            hard_guard_ok=False,
        )
        self.assertEqual(result["decision"], "guarded")
        self.assertGreater(result["lower_confidence"], 0.01)

    def test_strong_negative_paired_effect_is_insufficient(self):
        result = paired_experiment_gate(
            [0.0] * 128,
            [1.0] * 128,
            min_effect=0.0,
            min_samples=32,
        )
        self.assertEqual(result["decision"], "insufficient_effect")
        self.assertLess(result["upper_confidence"], 0.0)

    def test_importance_weight_effective_sample_size(self):
        self.assertAlmostEqual(importance_weight_effective_sample_size([1.0, 1.0, 1.0]), 3.0)
        self.assertLess(importance_weight_effective_sample_size([10.0, 1.0, 1.0]), 3.0)
        self.assertEqual(importance_weight_effective_sample_size([]), 0.0)

    def test_stable_unclipped_ips_can_nominate_experiment(self):
        result = ips_experiment_gate(
            [0.9] * 128,
            [0.5] * 128,
            [0.5] * 128,
            baseline_value=0.30,
            min_effect=0.10,
            delta=0.05,
            max_weight=1.0,
            min_effective_samples=32.0,
        )
        self.assertTrue(result["valid_target_confidence_sequence"])
        self.assertAlmostEqual(result["effective_sample_size"], 128.0)
        self.assertEqual(result["decision"], "experiment_candidate")
        self.assertGreater(result["lower_confidence"], 0.40)

    def test_clipped_ips_is_observation_only(self):
        result = ips_experiment_gate(
            [1.0] * 64,
            [0.01] * 64,
            [0.90] * 64,
            baseline_value=0.20,
            max_weight=10.0,
            min_effective_samples=16.0,
        )
        self.assertFalse(result["valid_target_confidence_sequence"])
        self.assertEqual(result["clipped_count"], 64)
        self.assertEqual(result["decision"], "observe_clipped")

    def test_low_effective_sample_size_blocks_ips_nomination(self):
        rewards = [1.0] * 64
        behavior = [1.0] * 64
        target = [1.0] + [0.01] * 63
        result = ips_experiment_gate(
            rewards,
            behavior,
            target,
            baseline_value=0.0,
            min_effect=0.0,
            max_weight=1.0,
            min_effective_samples=10.0,
        )
        self.assertTrue(result["valid_target_confidence_sequence"])
        self.assertLess(result["effective_sample_size"], 10.0)
        self.assertEqual(result["decision"], "observe_low_ess")

    def test_ips_sequence_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            ips_sequence([1.0], [0.0], [1.0])

    def test_confidence_sequence_rejects_out_of_range_sample(self):
        with self.assertRaises(ValueError):
            confidence_sequence([0.5, 1.1])

    def test_delta_validation(self):
        with self.assertRaises(ValueError):
            confidence_sequence([0.5], delta=1.0)
        with self.assertRaises(ValueError):
            confidence_sequence([0.5], delta=0.0)


if __name__ == "__main__":
    unittest.main()
