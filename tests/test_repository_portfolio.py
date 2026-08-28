import copy
import json
from pathlib import Path
import unittest

from scripts import repository_portfolio as rp

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "state/repository-portfolio-policy.json").read_text())
MATH_POLICY = json.loads((ROOT / "state/evolution-math-policy.json").read_text())


def portfolio_state():
    return {
        "version": 1,
        "updated_at": None,
        "strategy_weights": {name: 1.0 / 6.0 for name in POLICY["strategy_arms"]},
        "arms": {name: {"pulls": 0, "last_opportunity": 0.5} for name in POLICY["strategy_arms"]},
        "last_selected_arm": None,
        "checkpoint_source": "test-seed",
    }


def evolution_state():
    return {
        "fitness": {
            "goal_clarity": 0.55,
            "product_quality": 0.55,
            "community_health": 0.45,
            "verification_strength": 0.50,
            "maintainability": 0.58,
            "exploration_capacity": 0.42,
            "risk_debt": 0.52,
        }
    }


def snapshot():
    return {
        "repository": "example/idkmesh",
        "generated_at": "2026-08-28T12:00:00Z",
        "issues": [
            {
                "number": 1,
                "title": "Protect repository authority boundary",
                "body": "Security ruleset work. This blocks #3. See also #2 for context.",
                "labels": ["P0", "security"],
                "comments_count": 2,
                "created_at": "2026-08-20T00:00:00Z",
                "updated_at": "2026-08-27T00:00:00Z",
                "url": "https://example.test/issues/1",
                "author": "alice",
            },
            {
                "number": 2,
                "title": "Improve newcomer documentation onboarding",
                "body": "A bounded community and docs task. Mention #3 without a dependency phrase.",
                "labels": ["documentation"],
                "comments_count": 1,
                "created_at": "2026-08-25T00:00:00Z",
                "updated_at": "2026-08-27T00:00:00Z",
                "url": "https://example.test/issues/2",
                "author": "bob",
            },
            {
                "number": 3,
                "title": "Add runtime worker adapter",
                "body": "Product execution task; blocked by #1.",
                "labels": [],
                "comments_count": 5,
                "created_at": "2026-08-10T00:00:00Z",
                "updated_at": "2026-08-27T00:00:00Z",
                "url": "https://example.test/issues/3",
                "author": "alice",
            },
        ],
        "pull_requests": [
            {
                "number": 10,
                "title": "Add verifier replay evidence",
                "body": "Verification and evidence changes.",
                "labels": ["verification"],
                "comments_count": 3,
                "created_at": "2026-08-26T00:00:00Z",
                "updated_at": "2026-08-27T00:00:00Z",
                "url": "https://example.test/pulls/10",
                "author": "carol",
                "is_draft": False,
                "review_decision": "",
            },
            {
                "number": 11,
                "title": "Refactor duplicate architecture helpers",
                "body": "Maintenance cleanup.",
                "labels": [],
                "comments_count": 0,
                "created_at": "2026-08-27T00:00:00Z",
                "updated_at": "2026-08-27T00:00:00Z",
                "url": "https://example.test/pulls/11",
                "author": "dave",
                "is_draft": False,
                "review_decision": "",
            },
        ],
    }


class RepositoryPortfolioTests(unittest.TestCase):
    def test_dependency_parser_accepts_only_explicit_phrases(self):
        edges = rp.explicit_dependency_edges(snapshot()["issues"])
        self.assertEqual(edges, [("1", "3")])

    def test_strategy_classification_is_deterministic(self):
        data = snapshot()["issues"]
        self.assertEqual(rp.classify_strategy(data[0], POLICY), "safety")
        self.assertEqual(rp.classify_strategy(data[1], POLICY), "community")
        self.assertEqual(rp.classify_strategy(data[2], POLICY), "product")
        self.assertEqual(rp.classify_strategy(data[2], POLICY), rp.classify_strategy(data[2], POLICY))

    def test_graph_unlock_and_security_priority(self):
        result = rp.build_portfolio(
            snapshot(), portfolio_state(), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        by_number = {item["number"]: item for item in result["top_issue_candidates"]}
        self.assertGreater(by_number[1]["features"]["unlock"], by_number[3]["features"]["unlock"])
        self.assertGreater(by_number[1]["features"]["impact"], by_number[3]["features"]["impact"])
        self.assertGreater(by_number[1]["features"]["risk"], by_number[3]["features"]["risk"])

    def test_bounded_proxy_features_and_complete_pareto_population(self):
        result = rp.build_portfolio(
            snapshot(), portfolio_state(), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        issue_numbers = {item["number"] for item in result["top_issue_candidates"]}
        pr_numbers = {item["number"] for item in result["top_review_attention_candidates"]}
        self.assertEqual(issue_numbers, {1, 2, 3})
        self.assertEqual(pr_numbers, {10, 11})
        for item in result["top_issue_candidates"] + result["top_review_attention_candidates"]:
            for key in ("impact", "information_gain", "unlock", "diversity", "risk", "cost", "review_burden"):
                self.assertGreaterEqual(item["features"][key], 0.0)
                self.assertLessEqual(item["features"][key], 1.0)
            self.assertGreaterEqual(item["pareto_front"], 0)

    def test_attention_weights_are_normalized_and_preserve_exploration(self):
        state = portfolio_state()
        result = rp.build_portfolio(snapshot(), state, evolution_state(), MATH_POLICY, POLICY, "test")
        weights = result["strategy_attention_weights"]
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertTrue(all(value > 0.0 for value in weights.values()))

    def test_ucb_explores_unseen_strategies(self):
        state = portfolio_state()
        state["arms"]["product"]["pulls"] = 20
        state["arms"]["product"]["last_opportunity"] = 0.95
        result = rp.build_portfolio(snapshot(), state, evolution_state(), MATH_POLICY, POLICY, "test")
        self.assertNotEqual(result["ucb_exploration_focus"], "product")

    def test_output_is_deterministic_for_same_inputs(self):
        one = rp.build_portfolio(
            snapshot(), copy.deepcopy(portfolio_state()), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        two = rp.build_portfolio(
            snapshot(), copy.deepcopy(portfolio_state()), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        self.assertEqual(one, two)

    def test_authority_is_strictly_read_only(self):
        result = rp.build_portfolio(
            snapshot(), portfolio_state(), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        authority = result["authority"]
        self.assertTrue(authority["advisory_only"])
        for key in ("repository_write", "issue_write", "pull_request_write", "approval", "merge"):
            self.assertFalse(authority[key])

    def test_markdown_contains_key_diagnostics(self):
        result = rp.build_portfolio(
            snapshot(), portfolio_state(), evolution_state(), MATH_POLICY, POLICY, "test"
        )
        markdown = rp.render_markdown(result)
        self.assertIn("Repository Mathematical Portfolio", markdown)
        self.assertIn("UCB exploration focus", markdown)
        self.assertIn("#1 -> #3", markdown)
        self.assertIn("advisory mathematical attention map", markdown)


if __name__ == "__main__":
    unittest.main()
