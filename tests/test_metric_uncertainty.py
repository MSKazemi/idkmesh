import math
import unittest

from scripts.metric_uncertainty import beta_binomial_summary, conservative_lower_bound


class MetricUncertaintyTests(unittest.TestCase):
    def test_zero_trials_is_explicitly_prior_only(self):
        summary = beta_binomial_summary(0, 0)
        self.assertEqual(summary["model"], "beta-binomial-v3")
        self.assertEqual(summary["posterior_mean"], 0.5)
        self.assertEqual(summary["effective_sample_size"], 2.0)
        self.assertEqual(summary["posterior_concentration"], 2.0)
        self.assertEqual(summary["prior_pseudocount_mass"], 2.0)
        self.assertEqual(summary["observed_sample_size"], 0)
        self.assertIsNone(summary["empirical_rate"])
        self.assertEqual(summary["evidence_status"], "prior_only_no_observations")
        self.assertEqual(summary["credible_interval_95"], [0.025, 0.975])
        self.assertEqual(summary["interval_method"], "equal-tail-beta-posterior")
        self.assertEqual(summary["interval_mass"], 0.95)
        self.assertEqual(
            summary["effective_sample_size_semantics"],
            "beta_posterior_concentration_not_observed_sample_size",
        )

    def test_observed_summary_separates_empirical_rate_from_posterior(self):
        summary = beta_binomial_summary(3, 4)
        self.assertEqual(summary["evidence_status"], "observed")
        self.assertEqual(summary["observed_sample_size"], 4)
        self.assertEqual(summary["empirical_rate"], 0.75)
        self.assertEqual(summary["prior_pseudocount_mass"], 2.0)
        self.assertEqual(summary["posterior_concentration"], 6.0)
        self.assertNotEqual(summary["posterior_mean"], summary["empirical_rate"])

    def test_exact_interval_matches_closed_form_beta_two_one(self):
        summary = beta_binomial_summary(1, 1)
        low, high = summary["credible_interval_95"]
        self.assertAlmostEqual(low, math.sqrt(0.025), places=6)
        self.assertAlmostEqual(high, math.sqrt(0.975), places=6)

    def test_more_successes_raise_posterior_mean(self):
        low = beta_binomial_summary(1, 4)
        high = beta_binomial_summary(3, 4)
        self.assertLess(low["posterior_mean"], high["posterior_mean"])

    def test_more_evidence_narrows_interval(self):
        small = beta_binomial_summary(5, 10)
        large = beta_binomial_summary(50, 100)
        small_width = small["credible_interval_95"][1] - small["credible_interval_95"][0]
        large_width = large["credible_interval_95"][1] - large["credible_interval_95"][0]
        self.assertLess(large_width, small_width)

    def test_exact_interval_is_bounded(self):
        for successes in (0, 5, 10):
            summary = beta_binomial_summary(successes, 10)
            self.assertGreaterEqual(summary["credible_interval_95"][0], 0.0)
            self.assertLessEqual(summary["credible_interval_95"][1], 1.0)

    def test_legacy_normal_interval_is_preserved_but_not_authoritative(self):
        summary = beta_binomial_summary(8, 10)
        self.assertEqual(summary["approx_interval_95"], [0.514612, 0.985388])
        self.assertEqual(summary["legacy_normal_interval"], summary["approx_interval_95"])
        self.assertEqual(
            summary["approx_interval_method"],
            "normal-approximation-to-beta-posterior",
        )
        self.assertEqual(summary["credible_interval_95"], [0.482244, 0.939782])
        self.assertEqual(conservative_lower_bound(summary), 0.482244)

    def test_custom_legacy_z_is_not_mislabeled_as_95_percent(self):
        summary = beta_binomial_summary(3, 4, z=1.0)
        self.assertIsNone(summary["approx_interval_95"])
        self.assertIsInstance(summary["legacy_normal_interval"], list)
        self.assertEqual(summary["legacy_normal_z"], 1.0)
        self.assertAlmostEqual(summary["legacy_normal_reference_mass"], 0.682689, places=6)
        self.assertEqual(summary["interval_mass"], 0.95)

    def test_conservative_lower_bound_supports_v2_compatibility(self):
        self.assertEqual(
            conservative_lower_bound({"approx_interval_95": [0.2, 0.9]}),
            0.2,
        )

    def test_invalid_counts_fail(self):
        with self.assertRaises(ValueError):
            beta_binomial_summary(2, 1)

    def test_non_finite_prior_fails(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            beta_binomial_summary(1, 2, alpha_prior=math.inf)

    def test_invalid_z_fails(self):
        with self.assertRaisesRegex(ValueError, "positive finite"):
            beta_binomial_summary(1, 2, z=0.0)
        with self.assertRaisesRegex(ValueError, "positive finite"):
            beta_binomial_summary(1, 2, z=math.nan)


if __name__ == "__main__":
    unittest.main()
