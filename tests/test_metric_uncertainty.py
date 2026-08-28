import unittest

from scripts.metric_uncertainty import beta_binomial_summary, conservative_lower_bound


class MetricUncertaintyTests(unittest.TestCase):
    def test_zero_trials_uses_prior(self):
        summary = beta_binomial_summary(0, 0)
        self.assertEqual(summary["model"], "beta-binomial-v1")
        self.assertEqual(summary["posterior_mean"], 0.5)
        self.assertEqual(summary["effective_sample_size"], 2.0)

    def test_more_successes_raise_posterior_mean(self):
        low = beta_binomial_summary(1, 4)
        high = beta_binomial_summary(3, 4)
        self.assertLess(low["posterior_mean"], high["posterior_mean"])

    def test_more_evidence_narrows_interval(self):
        small = beta_binomial_summary(5, 10)
        large = beta_binomial_summary(50, 100)
        small_width = small["approx_interval_95"][1] - small["approx_interval_95"][0]
        large_width = large["approx_interval_95"][1] - large["approx_interval_95"][0]
        self.assertLess(large_width, small_width)

    def test_interval_is_bounded(self):
        summary = beta_binomial_summary(10, 10)
        self.assertGreaterEqual(summary["approx_interval_95"][0], 0.0)
        self.assertLessEqual(summary["approx_interval_95"][1], 1.0)

    def test_conservative_lower_bound(self):
        summary = beta_binomial_summary(8, 10)
        self.assertEqual(conservative_lower_bound(summary), summary["approx_interval_95"][0])

    def test_invalid_counts_fail(self):
        with self.assertRaises(ValueError):
            beta_binomial_summary(2, 1)


if __name__ == "__main__":
    unittest.main()
