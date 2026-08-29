import unittest

from randomness_lab.r1_scaling import (
    R1ScalingConfig,
    render_markdown,
    run_r1_scaling,
)


class R1ScalingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = R1ScalingConfig(
            tasks_per_trial=25,
            trials=3,
            base_seed=17,
            swarm_sizes=(1, 2, 5),
            difficulty_levels=(("easy", 0.80), ("hard", 0.40)),
        )

    def test_replay_is_deterministic_and_retains_seeded_trials(self) -> None:
        first = run_r1_scaling(self.config)
        second = run_r1_scaling(self.config)
        self.assertEqual(first, second)
        self.assertEqual(len(first["cells"]), 18)
        self.assertTrue(all(len(cell["raw_trials"]) == 3 for cell in first["cells"]))

    def test_equal_attempt_comparisons_really_have_equal_resource_proxies(self) -> None:
        result = run_r1_scaling(self.config)
        self.assertEqual(len(result["equal_attempt_budget_comparisons"]), 8)
        for comparison in result["equal_attempt_budget_comparisons"]:
            self.assertTrue(comparison["equal_attempt_count"])
            self.assertTrue(comparison["equal_mean_compute_per_task"])
            self.assertTrue(comparison["equal_mean_human_attention_per_task"])

    def test_marginals_publish_uncertainty_and_negative_values_are_retained(self) -> None:
        result = run_r1_scaling(self.config)
        self.assertEqual(len(result["marginal_curves"]), 12)
        for marginal in result["marginal_curves"]:
            summary = marginal["verified_success_rate_delta"]
            self.assertEqual(len(summary["normal_approx_95_ci"]), 2)
            self.assertIn(
                summary["classification"], {"positive", "negative", "uncertain"}
            )
        all_deltas = [
            trial["metrics"]["verified_success_rate"]
            for cell in result["cells"]
            for trial in cell["raw_trials"]
        ]
        self.assertTrue(all(0.0 <= value <= 1.0 for value in all_deltas))
        self.assertTrue(
            any(
                marginal["verified_success_rate_delta"]["min"] < 0.0
                for marginal in result["marginal_curves"]
            )
        )

    def test_report_and_coverage_refuse_a_real_agent_claim(self) -> None:
        result = run_r1_scaling(self.config)
        report = render_markdown(result)
        self.assertIn("synthetic mechanism only", report)
        self.assertIn("real held-out software tasks", result["issue_13_coverage"]["not_represented"])
        self.assertIn("cannot close issue #13", result["interpretation_guardrail"])

    def test_configuration_rejects_unordered_or_missing_baseline_sizes(self) -> None:
        with self.assertRaises(ValueError):
            R1ScalingConfig(swarm_sizes=(2, 5))
        with self.assertRaises(ValueError):
            R1ScalingConfig(swarm_sizes=(1, 5, 2))


if __name__ == "__main__":
    unittest.main()
