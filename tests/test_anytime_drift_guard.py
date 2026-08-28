import math
import unittest

from scripts.anytime_drift_guard import (
    anytime_change_scan,
    drift_guarded_paired_experiment_gate,
    multi_metric_change_scan,
    reciprocal_square_tail,
    split_error_budget,
    two_window_hoeffding_threshold,
)


class AnytimeDriftGuardTests(unittest.TestCase):
    def test_split_error_budget_sums_below_delta_on_large_finite_horizon(self):
        delta = 0.05
        min_window = 4
        spent = 0.0
        for t in range(2 * min_window, 1000):
            for k in range(min_window, t - min_window + 1):
                spent += split_error_budget(delta, t, k, min_window)
        self.assertLess(spent, delta)
        self.assertGreater(spent, 0.049)

    def test_reciprocal_square_tail_matches_direct_partial_plus_remainder_identity(self):
        start = 8
        tail = reciprocal_square_tail(start)
        prefix = sum(1.0 / (t * t) for t in range(1, start))
        self.assertAlmostEqual(prefix + tail, math.pi * math.pi / 6.0, places=14)

    def test_threshold_decreases_with_larger_balanced_windows(self):
        small = two_window_hoeffding_threshold(16, 16, 1e-4)
        large = two_window_hoeffding_threshold(128, 128, 1e-4)
        self.assertLess(large, small)

    def test_constant_stream_has_no_alarm(self):
        result = anytime_change_scan([0.5] * 256, delta=0.05, min_window=16)
        self.assertFalse(result["detected_change"])
        self.assertEqual(result["authority"], "observation_only")
        self.assertFalse(result["automatic_history_deletion"])

    def test_persistent_shift_is_detected(self):
        result = anytime_change_scan(
            [0.2] * 256 + [0.9] * 256,
            delta=0.05,
            min_window=32,
        )
        self.assertTrue(result["detected_change"])
        self.assertIsNotNone(result["first_alarm"])
        self.assertEqual(result["first_alarm"]["direction"], "increase")
        self.assertGreater(result["first_alarm"]["threshold_ratio"], 1.0)

    def test_persistent_downward_shift_direction(self):
        result = anytime_change_scan(
            [0.9] * 256 + [0.1] * 256,
            delta=0.05,
            min_window=32,
        )
        self.assertTrue(result["detected_change"])
        self.assertEqual(result["first_alarm"]["direction"], "decrease")

    def test_short_stream_is_observation_only_not_stationarity_proof(self):
        result = anytime_change_scan([0.5] * 10, min_window=8)
        self.assertFalse(result["detected_change"])
        self.assertEqual(result["tested_splits"], 0)
        self.assertIn("not proven", result["interpretation"])

    def test_multi_metric_scan_spends_delta_across_metrics(self):
        result = multi_metric_change_scan(
            {
                "quality": [0.5] * 512,
                "risk": [0.1] * 256 + [0.8] * 256,
            },
            delta=0.04,
            min_window=32,
        )
        self.assertAlmostEqual(result["per_metric_delta"], 0.02)
        self.assertTrue(result["detected_change"])
        self.assertEqual(result["detected_metrics"], ["risk"])

    def test_stable_strong_effect_can_reach_existing_evidence_gate(self):
        result = drift_guarded_paired_experiment_gate(
            [0.9] * 128,
            [0.1] * 128,
            min_effect=0.10,
            total_delta=0.05,
            min_samples=32,
            min_window=16,
        )
        self.assertFalse(result["drift"]["detected_change"])
        self.assertEqual(result["decision"], "experiment_candidate")
        self.assertEqual(result["authority"], "candidate_only")

    def test_drift_blocks_nomination_even_when_pooled_effect_is_strong(self):
        result = drift_guarded_paired_experiment_gate(
            [0.6] * 256 + [1.0] * 256,
            [0.5] * 256 + [0.1] * 256,
            min_effect=0.05,
            total_delta=0.05,
            min_samples=32,
            min_window=32,
        )
        self.assertTrue(result["drift"]["detected_change"])
        self.assertEqual(result["decision"], "observe_drift")
        self.assertFalse(result["automatic_history_deletion"])
        self.assertEqual(
            result["history_policy"],
            "preserve_all_evidence_and_review_regime_boundary",
        )

    def test_hard_guard_still_dominates_drift_and_statistics(self):
        result = drift_guarded_paired_experiment_gate(
            [0.6] * 256 + [1.0] * 256,
            [0.5] * 256 + [0.1] * 256,
            min_effect=0.0,
            min_samples=32,
            min_window=32,
            hard_guard_ok=False,
        )
        self.assertEqual(result["decision"], "guarded")

    def test_invalid_samples_fail_closed(self):
        with self.assertRaises(ValueError):
            anytime_change_scan([0.1, 1.1], min_window=1)

    def test_invalid_split_budget_rejected(self):
        with self.assertRaises(ValueError):
            split_error_budget(0.05, t=10, k=1, min_window=4)
        with self.assertRaises(ValueError):
            split_error_budget(0.05, t=4, k=2, min_window=4)


if __name__ == "__main__":
    unittest.main()
