import itertools
import unittest

from scripts.adversarial_evidence_guard import (
    adversarial_mean_envelope,
    binary_vote_certificate,
    fault_budget_sensitivity,
    threshold_certificate,
)


def mean(values):
    total = 0.0
    for value in values:
        total += float(value)
    return total / len(values)


class AdversarialEvidenceGuardTests(unittest.TestCase):
    def test_zero_fault_envelope_collapses_to_observed_mean(self):
        values = [0.1, 0.3, 0.9]
        result = adversarial_mean_envelope(values, 0)
        self.assertAlmostEqual(result["honest_mean_lower"], mean(values))
        self.assertAlmostEqual(result["honest_mean_upper"], mean(values))
        self.assertAlmostEqual(result["envelope_width"], 0.0)

    def test_envelope_is_exact_over_all_admissible_honest_subsets(self):
        values = [0.1, 0.2, 0.4, 0.8, 0.9]
        f = 2
        result = adversarial_mean_envelope(values, f)
        minimum_size = len(values) - f
        admissible_means = []
        for size in range(minimum_size, len(values) + 1):
            for subset in itertools.combinations(values, size):
                admissible_means.append(mean(subset))
        self.assertAlmostEqual(result["honest_mean_lower"], min(admissible_means))
        self.assertAlmostEqual(result["honest_mean_upper"], max(admissible_means))
        for candidate in admissible_means:
            self.assertGreaterEqual(candidate + 1e-12, result["honest_mean_lower"])
            self.assertLessEqual(candidate - 1e-12, result["honest_mean_upper"])

    def test_central_fault_does_not_break_envelope_guarantee(self):
        honest = [0.1, 0.2, 0.8, 0.9]
        reports = [0.1, 0.2, 0.5, 0.8, 0.9]
        result = adversarial_mean_envelope(reports, 1)
        honest_mean = mean(honest)
        self.assertGreaterEqual(honest_mean, result["honest_mean_lower"])
        self.assertLessEqual(honest_mean, result["honest_mean_upper"])
        self.assertIsNotNone(result["f_trimmed_mean"])

    def test_fault_budget_can_make_naive_support_fragile(self):
        result = threshold_certificate(
            [0.0] + [0.6] * 6,
            1,
            threshold=0.5,
        )
        self.assertEqual(result["naive_direction"], "support")
        self.assertEqual(result["robust_direction"], "uncertain")
        self.assertTrue(result["naive_decision_fragile"])
        self.assertEqual(result["decision"], "observe_adversarial_uncertainty")

    def test_strong_support_survives_two_arbitrary_reports(self):
        result = threshold_certificate(
            [0.0, 0.0] + [0.9] * 7,
            2,
            threshold=0.5,
            margin=0.1,
        )
        self.assertEqual(result["certificate"], "support_certified")
        self.assertEqual(result["decision"], "experiment_candidate")
        self.assertGreater(result["envelope"]["honest_mean_lower"], 0.6)
        self.assertEqual(result["authority"], "candidate_only")

    def test_strong_rejection_survives_two_arbitrary_reports(self):
        result = threshold_certificate(
            [1.0, 1.0] + [0.1] * 7,
            2,
            threshold=0.5,
            margin=0.1,
        )
        self.assertEqual(result["certificate"], "reject_certified")
        self.assertEqual(result["decision"], "insufficient_support")
        self.assertLess(result["envelope"]["honest_mean_upper"], 0.4)

    def test_binary_vote_certificate_proves_honest_support_majority(self):
        result = binary_vote_certificate([1] * 7 + [0] * 3, 2)
        self.assertTrue(result["honest_support_majority_certified"])
        self.assertFalse(result["honest_reject_majority_certified"])
        self.assertTrue(result["at_least_one_honest_support_certified"])
        self.assertEqual(result["certificate"], "support_certified")

    def test_binary_vote_certificate_can_remain_ambiguous(self):
        result = binary_vote_certificate([1] * 6 + [0] * 4, 2)
        self.assertFalse(result["honest_support_majority_certified"])
        self.assertFalse(result["honest_reject_majority_certified"])
        self.assertEqual(result["certificate"], "uncertain_under_fault_budget")

    def test_fault_budget_uncertainty_width_is_monotone(self):
        rows = fault_budget_sensitivity(
            [0.1, 0.2, 0.4, 0.8, 0.9],
            max_faults=4,
        )
        widths = [row["envelope_width"] for row in rows]
        self.assertEqual(len(widths), 5)
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(widths, widths[1:])))
        self.assertTrue(all(row["width_nondecreasing"] for row in rows))

    def test_hard_guard_cannot_be_compensated_by_robust_support(self):
        result = threshold_certificate(
            [0.0, 0.0] + [0.9] * 7,
            2,
            threshold=0.5,
            margin=0.1,
            hard_guard_ok=False,
        )
        self.assertEqual(result["certificate"], "support_certified")
        self.assertEqual(result["decision"], "guarded")

    def test_high_fault_budget_is_reported_without_claiming_consensus(self):
        result = adversarial_mean_envelope([0.9, 0.9, 0.9, 0.9], 2)
        self.assertFalse(result["guaranteed_honest_majority"])
        self.assertFalse(result["byzantine_consensus_claim"])
        self.assertFalse(result["sybil_resistance_claim"])
        self.assertFalse(result["truth_claim"])

    def test_invalid_fault_budgets_fail_closed(self):
        with self.assertRaises(ValueError):
            adversarial_mean_envelope([0.2, 0.8], -1)
        with self.assertRaises(ValueError):
            adversarial_mean_envelope([0.2, 0.8], 2)
        with self.assertRaises(ValueError):
            adversarial_mean_envelope([0.2, 0.8], 0.5)

    def test_out_of_range_reports_fail_closed(self):
        with self.assertRaises(ValueError):
            adversarial_mean_envelope([0.2, 1.2], 0)

    def test_invalid_threshold_margin_fails_closed(self):
        with self.assertRaises(ValueError):
            threshold_certificate([0.5, 0.6], 0, threshold=0.95, margin=0.1)
        with self.assertRaises(ValueError):
            threshold_certificate([0.5, 0.6], 0, margin=-0.1)


if __name__ == "__main__":
    unittest.main()
