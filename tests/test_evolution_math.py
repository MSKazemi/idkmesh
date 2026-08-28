import math
import unittest

from scripts import evolution_math as em


class EvolutionMathTests(unittest.TestCase):
    def test_beta_evidence_moves_mean_and_reduces_variance(self):
        before_mean = em.beta_mean(4.0, 4.0)
        before_var = em.beta_variance(4.0, 4.0)
        alpha, beta = em.beta_update(4.0, 4.0, 1.0, strength=2.0)
        self.assertGreater(em.beta_mean(alpha, beta), before_mean)
        self.assertLess(em.beta_variance(alpha, beta), before_var)
        self.assertLessEqual(em.beta_lower_confidence(alpha, beta), em.beta_mean(alpha, beta))

    def test_entropy_extremes(self):
        self.assertEqual(em.normalized_entropy([10, 0, 0]), 0.0)
        self.assertAlmostEqual(em.normalized_entropy([1, 1, 1, 1]), 1.0)

    def test_js_divergence(self):
        self.assertAlmostEqual(em.jensen_shannon_divergence([1, 1], [1, 1]), 0.0)
        self.assertAlmostEqual(em.jensen_shannon_divergence([1, 0], [0, 1]), 1.0)

    def test_effective_sample_size_falls_with_correlation(self):
        self.assertEqual(em.effective_sample_size(5, 0.0), 5.0)
        self.assertAlmostEqual(em.effective_sample_size(5, 1.0), 1.0)
        self.assertLess(em.effective_sample_size(5, 0.8), em.effective_sample_size(5, 0.2))

    def test_correlated_group_is_discounted_in_bayesian_vote(self):
        independent = em.bayesian_vote_posterior(
            [1, 1, 0], [0.8, 0.8, 0.7], groups=["a", "b", "c"], within_group_correlation=1.0
        )
        correlated = em.bayesian_vote_posterior(
            [1, 1, 0], [0.8, 0.8, 0.7], groups=["a", "a", "c"], within_group_correlation=1.0
        )
        self.assertLess(correlated["effective_votes"], independent["effective_votes"])
        self.assertLess(correlated["posterior_probability"], independent["posterior_probability"])

    def test_pareto_sort_and_crowding(self):
        points = [
            {"impact": 0.9, "risk": 0.7},
            {"impact": 0.7, "risk": 0.2},
            {"impact": 0.6, "risk": 0.5},
        ]
        fronts = em.nondominated_sort(points, {"impact": 1, "risk": -1})
        self.assertEqual(set(fronts[0]), {0, 1})
        self.assertEqual(fronts[1], [2])
        crowd = em.crowding_distance(fronts[0], points, {"impact": 1, "risk": -1})
        self.assertTrue(all(math.isinf(v) for v in crowd.values()))

    def test_multiplicative_weights_preserves_exploration_and_normalization(self):
        updated = em.multiplicative_weights(
            {"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0}, eta=0.5, exploration_floor=0.1
        )
        self.assertAlmostEqual(sum(updated.values()), 1.0)
        self.assertGreater(updated["a"], updated["b"])
        self.assertGreater(updated["b"], 0.05 - 1e-12)

    def test_ucb_prioritizes_unseen_arm(self):
        selected = em.select_ucb(
            {
                "known": {"mean_reward": 0.95, "pulls": 20},
                "unseen": {"mean_reward": 0.0, "pulls": 0},
            }
        )
        self.assertEqual(selected, "unseen")

    def test_unlock_value_rewards_upstream_tasks(self):
        unlock = em.dag_unlock_values(
            ["A", "B", "C", "D"],
            [("A", "B"), ("A", "C"), ("B", "D")],
            {"A": 1.0, "B": 2.0, "C": 1.5, "D": 4.0},
            decay=0.4,
        )
        self.assertGreater(unlock["A"], unlock["B"])
        self.assertEqual(unlock["D"], 0.0)

    def test_homeostatic_potential_is_lyapunov_like(self):
        before = em.homeostatic_potential(
            {"verification": 0.4, "risk": 0.6},
            {"verification": 0.8, "risk": 0.2},
            {"verification": 0.2, "risk": 0.2},
        )
        after = em.homeostatic_potential(
            {"verification": 0.65, "risk": 0.35},
            {"verification": 0.8, "risk": 0.2},
            {"verification": 0.2, "risk": 0.2},
        )
        self.assertLess(after, before)
        self.assertTrue(em.lyapunov_accept(before, after))
        self.assertFalse(em.lyapunov_accept(after, before))

    def test_demo_is_deterministic_and_complete(self):
        one = em.build_demo()
        two = em.build_demo()
        self.assertEqual(one, two)
        self.assertIn("bayesian", one)
        self.assertIn("pareto_ranking", one)
        self.assertIn("multiplicative_weights", one)
        self.assertIn("homeostasis", one)


if __name__ == "__main__":
    unittest.main()
