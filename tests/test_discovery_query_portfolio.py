from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.discovery_query_portfolio import load_json, validate


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "config/discovery-query-portfolio-v0.1.json"


class DiscoveryQueryPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = load_json(PORTFOLIO)

    def test_committed_portfolio_is_exactly_100_nonbranded_queries(self):
        result = validate(self.portfolio, ROOT)
        summary = result["summary"]
        self.assertEqual(10, summary["clusters"])
        self.assertEqual(100, summary["queries"])
        self.assertEqual(10, summary["distinct_canonical_targets"])
        self.assertTrue(summary["all_canonical_targets_exist"])
        self.assertTrue(summary["all_evidence_refs_exist"])
        self.assertFalse(result["authority"]["search_demand_claim"])
        self.assertFalse(result["authority"]["ranking_claim"])
        self.assertFalse(result["authority"]["content_creation_authority"])

    def test_analytics_portfolio_is_pinned_to_canonical_seo_queries(self):
        seo = load_json(ROOT / "config/seo-topics-v1.json")
        self.assertEqual(
            "config/seo-topics-v1.json",
            self.portfolio["query_source"],
        )
        portfolio_by_id = {cluster["id"]: cluster for cluster in self.portfolio["clusters"]}
        seo_by_id = {cluster["id"]: cluster for cluster in seo["clusters"]}
        self.assertEqual(set(seo_by_id), set(portfolio_by_id))
        for cluster_id, canonical in seo_by_id.items():
            with self.subTest(cluster=cluster_id):
                analytics = portfolio_by_id[cluster_id]
                self.assertEqual(canonical["queries"], analytics["queries"])
                self.assertEqual(canonical["path"], analytics["canonical_target"])
                self.assertEqual(canonical["title"], analytics["label"])

    def test_semantic_query_drift_fails_closed(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][0]["queries"][0] = "different nonbranded query"
        with self.assertRaisesRegex(ValueError, "canonical SEO query source"):
            validate(changed, ROOT)

    def test_duplicate_query_fails_closed(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][1]["queries"][0] = changed["clusters"][0]["queries"][0]
        with self.assertRaisesRegex(ValueError, "duplicate query"):
            validate(changed, ROOT)

    def test_branded_query_fails_closed(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][0]["queries"][0] = "idkmesh agent verification"
        with self.assertRaisesRegex(ValueError, "branded query"):
            validate(changed, ROOT)

    def test_missing_canonical_target_fails_closed(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][0]["canonical_target"] = "docs/does-not-exist.html"
        with self.assertRaisesRegex(ValueError, "canonical SEO topic path"):
            validate(changed, ROOT)

    def test_missing_evidence_ref_fails_closed(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][0]["evidence_refs"][0] = "experiments/does-not-exist.md"
        with self.assertRaisesRegex(ValueError, "missing evidence refs"):
            validate(changed, ROOT)

    def test_exact_cluster_and_query_counts_are_enforced(self):
        changed = copy.deepcopy(self.portfolio)
        changed["clusters"].pop()
        with self.assertRaisesRegex(ValueError, "expected exactly 10 clusters"):
            validate(changed, ROOT)

        changed = copy.deepcopy(self.portfolio)
        changed["clusters"][0]["queries"].pop()
        with self.assertRaisesRegex(ValueError, "expected exactly 10 queries"):
            validate(changed, ROOT)

    def test_result_is_json_serializable(self):
        json.dumps(validate(self.portfolio, ROOT))


if __name__ == "__main__":
    unittest.main()
