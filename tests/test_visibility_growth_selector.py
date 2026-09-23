from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.visibility_growth_selector import load_json, select


ROOT = Path(__file__).resolve().parents[1]
POLICY = load_json(ROOT / "config/visibility-growth-policy-v0.1.json")


def visibility(*, technical_coverage=1.0, sitemap=True, external_contributors=0):
    return {
        "site": {
            "technical_coverage": technical_coverage,
            "sitemap": {"present": sitemap, "valid_urlset": sitemap},
        },
        "github": {
            "community_acquisition": {
                "external_commit_contributors_observed": external_contributors
            }
        },
    }


def portfolio():
    return {"summary": {"queries": 100}}


def gsc(*, impressions, ctr, observed_queries):
    clicks = impressions * (ctr or 0)
    return {
        "summary": {
            "nonbranded": {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "impression_weighted_position": 8.0,
            },
            "portfolio_queries_with_observations": observed_queries,
        }
    }


class VisibilityGrowthSelectorTests(unittest.TestCase):
    def test_technical_seo_precedes_growth_actions(self):
        result = select(
            visibility(technical_coverage=0.9),
            portfolio(),
            POLICY,
            search_console=None,
        )
        self.assertEqual("repair-technical-seo", result["selected_experiment"]["id"])

    def test_missing_search_analytics_selects_instrumentation(self):
        result = select(
            visibility(),
            portfolio(),
            POLICY,
            search_console=None,
        )
        self.assertEqual("connect-search-console", result["selected_experiment"]["id"])
        self.assertTrue(result["selected_experiment"]["requires_admin"])

    def test_low_nonbranded_impressions_selects_discovery_diagnosis(self):
        result = select(
            visibility(),
            portfolio(),
            POLICY,
            search_console=gsc(impressions=12, ctr=0.1, observed_queries=4),
        )
        self.assertEqual(
            "investigate-nonbranded-discovery",
            result["selected_experiment"]["id"],
        )

    def test_low_ctr_selects_one_snippet_experiment(self):
        result = select(
            visibility(),
            portfolio(),
            POLICY,
            search_console=gsc(impressions=100, ctr=0.01, observed_queries=4),
        )
        self.assertEqual("improve-serp-snippet", result["selected_experiment"]["id"])

    def test_sparse_portfolio_overlap_selects_calibration(self):
        result = select(
            visibility(),
            portfolio(),
            POLICY,
            search_console=gsc(impressions=100, ctr=0.05, observed_queries=1),
        )
        self.assertEqual("refine-intent-map", result["selected_experiment"]["id"])

    def test_discovery_without_external_contributor_selects_conversion(self):
        result = select(
            visibility(external_contributors=0),
            portfolio(),
            POLICY,
            search_console=gsc(impressions=100, ctr=0.05, observed_queries=5),
        )
        self.assertEqual(
            "improve-contributor-conversion",
            result["selected_experiment"]["id"],
        )

    def test_existing_discovery_and_contributors_select_measurement_expansion(self):
        result = select(
            visibility(external_contributors=2),
            portfolio(),
            POLICY,
            search_console=gsc(impressions=100, ctr=0.05, observed_queries=5),
        )
        self.assertEqual(
            "measure-authority-and-funnel",
            result["selected_experiment"]["id"],
        )
        self.assertEqual(1, result["candidate_count"])
        self.assertTrue(result["authority"]["recommendation_only"])
        self.assertFalse(result["authority"]["automatic_content_publication"])
        self.assertFalse(result["authority"]["automatic_outreach"])
        self.assertFalse(result["authority"]["automatic_issue_creation"])
        self.assertFalse(result["authority"]["merge_authority"])

    def test_policy_authority_cannot_be_relaxed_silently(self):
        changed = copy.deepcopy(POLICY)
        changed["authority"]["automatic_outreach"] = True
        with self.assertRaisesRegex(ValueError, "automatic_outreach"):
            select(visibility(), portfolio(), changed, search_console=None)


if __name__ == "__main__":
    unittest.main()
