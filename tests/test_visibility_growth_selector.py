from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.visibility_growth_selector import load_json, select


ROOT = Path(__file__).resolve().parents[1]
POLICY = load_json(ROOT / "config/visibility-growth-policy-v0.1.json")
TOPICS = load_json(ROOT / "config/seo-topics-v1.json")


def visibility(*, technical_coverage=1.0, sitemap=True, external_contributors=0):
    return {
        "site": {
            "technical_coverage": technical_coverage,
            "sitemap": {"present": sitemap, "valid_urlset": sitemap},
        },
        "github": {
            "repository": "MSKazemi/idkmesh",
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
        "version": 1,
        "source": {
            "provider": "google_search_console",
            "page_prefix": "https://mskazemi.com/idkmesh/",
            "dimensions": ["query", "page"],
            "search_type": "web",
            "data_state": "final",
            "truncated_by_local_cap": False,
        },
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


    def test_truncated_search_console_blocks_content_optimizations(self):
        evidence = gsc(impressions=600, ctr=0.001, observed_queries=1)
        evidence["source"]["truncated_by_local_cap"] = True
        result = select(visibility(external_contributors=5), portfolio(), POLICY, search_console=evidence)
        self.assertEqual("inspect-truncated-search-evidence", result["selected_experiment"]["id"])
        self.assertTrue(result["evidence"]["search_console"]["locally_truncated"])

    def test_bad_search_metrics_fail_closed_not_as_zero(self):
        for value in (None, -1, float("nan"), float("inf"), True, "10"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s = gsc(impressions=120, ctr=0.04, observed_queries=5)
                s["summary"]["nonbranded"]["impressions"] = value
                select(visibility(), portfolio(), POLICY, search_console=s)
        for ctr in (-0.01, 1.1, float("nan")):
            with self.subTest(ctr=ctr), self.assertRaises(ValueError):
                select(visibility(), portfolio(), POLICY, search_console=gsc(impressions=100, ctr=ctr, observed_queries=4))
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            s = gsc(impressions=2, ctr=0.5, observed_queries=3)
            s["summary"]["nonbranded"]["clicks"] = 5
            select(visibility(), portfolio(), POLICY, search_console=s)

    def test_bad_search_contract_fails_closed(self):
        for changes in ({"provider": "guess"}, {"page_prefix": "https://elsewhere.example/"},
                        {"data_state": "all"}, {"truncated_by_local_cap": "false"},
                        {"dimensions": ["query"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                s = gsc(impressions=100, ctr=0.05, observed_queries=5)
                s["source"].update(changes)
                select(visibility(), portfolio(), POLICY, search_console=s)

    def test_empty_authority_ledger_moves_recommendation_from_generic_collection(self):
        result = select(
            visibility(external_contributors=2), portfolio(), POLICY,
            search_console=gsc(impressions=200, ctr=0.06, observed_queries=7),
            authority_ledger={"version": 1, "references": []},
            authority_topics=TOPICS,
        )
        self.assertEqual("review-one-independent-reference", result["selected_experiment"]["id"])
        self.assertEqual(0, result["evidence"]["authority_references"]["recorded_sources"])
        self.assertIn("does not mean", result["selected_experiment"]["reason"])

    def test_one_attested_reference_and_missing_verified_contribution_stage(self):
        record = {
            "id": "reference-001",
            "source_url": "https://research.example.org/reproduction",
            "target_url": TOPICS["clusters"][0]["url"],
            "cluster_id": TOPICS["clusters"][0]["id"],
            "kind": "independent", "review_status": "owner_reviewed",
            "link_status": "direct_link_checked", "first_observed": "2026-10-13",
            "note": "Synthetic fixture only, not a real-world backlink.",
        }
        funnel = {
            "version": 1, "method": "visibility-funnel-coverage-v0.1",
            "repository": "MSKazemi/idkmesh",
            "summary": {
                "direct_stages_observed": 1, "conversion_rates_estimable": 0,
                "missing_stage_ids": ["first_verified_contribution", "website_visits"],
            },
            "transitions": [{"status": "not_attributable", "rate": None} for _ in range(6)],
        }
        result = select(
            visibility(external_contributors=1), portfolio(), POLICY,
            search_console=gsc(impressions=200, ctr=0.06, observed_queries=5),
            authority_ledger={"version": 1, "references": [record]},
            authority_topics=TOPICS, funnel_coverage=funnel,
        )
        self.assertEqual("design-verified-contribution-cohort", result["selected_experiment"]["id"])
        self.assertEqual(1, result["evidence"]["authority_references"]["owner_attested_independent_direct_link_claims"])
        self.assertEqual(0, result["evidence"]["funnel_coverage"]["conversion_rates_estimable"])
        self.assertNotIn("research.example.org", str(result))

    def test_unreviewed_or_syndicated_mentions_never_count_as_independent(self):
        record = {
            "id": "reference-001",
            "source_url": "https://research.example.org/reproduction",
            "target_url": TOPICS["clusters"][0]["url"],
            "cluster_id": TOPICS["clusters"][0]["id"],
            "kind": "syndication", "review_status": "owner_reviewed",
            "link_status": "direct_link_checked", "first_observed": "2026-10-13",
            "note": "Synthetic syndicated mention.",
        }
        result = select(
            visibility(external_contributors=2), portfolio(), POLICY,
            search_console=gsc(impressions=200, ctr=0.06, observed_queries=5),
            authority_ledger={"version": 1, "references": [record]},
            authority_topics=TOPICS,
        )
        self.assertEqual("review-one-independent-reference", result["selected_experiment"]["id"])
        self.assertEqual(1, result["evidence"]["authority_references"]["recorded_sources"])
        self.assertEqual(0, result["evidence"]["authority_references"]["owner_attested_independent_direct_link_claims"])

    def test_funnel_claiming_conversion_or_wrong_repository_is_rejected(self):
        funnel = {
            "version": 1, "method": "visibility-funnel-coverage-v0.1",
            "repository": "MSKazemi/idkmesh",
            "summary": {"direct_stages_observed": 1, "conversion_rates_estimable": 0,
                        "missing_stage_ids": ["first_verified_contribution"]},
            "transitions": [{"status": "not_attributable", "rate": None} for _ in range(6)],
        }
        for change in ("repository", "rate", "count"):
            with self.subTest(change=change), self.assertRaises(ValueError):
                bad = copy.deepcopy(funnel)
                if change == "repository":
                    bad["repository"] = "other/repository"
                elif change == "rate":
                    bad["transitions"][0]["rate"] = 0.1
                else:
                    bad["summary"]["conversion_rates_estimable"] = 1
                select(visibility(external_contributors=2), portfolio(), POLICY,
                       search_console=gsc(impressions=100, ctr=0.05, observed_queries=5),
                       funnel_coverage=bad)

    def test_policy_thresholds_reject_nan_and_booleans(self):
        for value in (float("nan"), float("inf"), True, -1, "5"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
                altered = copy.deepcopy(POLICY)
                altered["thresholds"]["minimum_nonbranded_impressions_28d"] = value
                select(visibility(), portfolio(), altered, search_console=None)

    def test_explicitly_missing_search_file_is_not_a_silent_unobserved_source(self):
        from tempfile import TemporaryDirectory
        from scripts.visibility_growth_selector import main
        from unittest.mock import patch
        with TemporaryDirectory() as folder:
            output = Path(folder) / "growth.json"
            from json import dumps
            for name, data in (
                ("visibility.json", visibility()),
                ("portfolio.json", portfolio()),
            ):
                (Path(folder) / name).write_text(dumps(data), encoding="utf-8")
            args = [
                "visibility_growth_selector.py",
                "--visibility", str(Path(folder) / "visibility.json"),
                "--portfolio", str(Path(folder) / "portfolio.json"),
                "--policy", str(ROOT / "config/visibility-growth-policy-v0.1.json"),
                "--search-console", str(Path(folder) / "missing.json"),
                "--output", str(output),
            ]
            with patch("sys.argv", args), self.assertRaises(FileNotFoundError):
                main()


if __name__ == "__main__":
    unittest.main()
