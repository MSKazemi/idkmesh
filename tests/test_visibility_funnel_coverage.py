from __future__ import annotations

import copy
import json
import unittest

from scripts.visibility_funnel_coverage import assess


def visibility(*, contributors=2, truncated=False):
    return {"version": 1, "github": {"repository": "MSKazemi/idkmesh", "community_acquisition": {
        "external_commit_contributors_observed": contributors,
        "contributors_page_truncated": truncated,
    }}}


def gsc(*, impressions=20.0, clicks=2.0, truncated=False):
    return {"version": 1, "source": {
        "provider": "google_search_console", "page_prefix": "https://mskazemi.com/idkmesh/",
        "dimensions": ["query", "page"], "search_type": "web", "data_state": "final",
        "start_date": "2026-09-01", "end_date": "2026-09-28",
        "truncated_by_local_cap": truncated,
    }, "summary": {"nonbranded": {"impressions": impressions, "clicks": clicks},
                    "portfolio_queries_with_observations": 3}}


def traffic(*, count=12, uniques=7):
    return {"version": 1, "source": {"provider": "github_repository_traffic_api",
        "repository": "MSKazemi/idkmesh", "window": "github_rolling_14_days",
        "collected_at_utc": "2026-10-13T08:00:00Z"},
        "views": {"count": count, "uniques": uniques}}


class FunnelCoverageTests(unittest.TestCase):
    def test_absent_analytics_is_unavailable_not_zero(self):
        result = assess(visibility())
        self.assertEqual(0, result["summary"]["direct_stages_observed"])
        self.assertEqual("connect_google_search_console", result["summary"]["next_measurement_action"])
        self.assertIsNone(result["stages"][0]["metric"])
        self.assertEqual("unavailable", result["stages"][2]["status"])
        self.assertEqual("proxy", result["stages"][4]["status"])

    def test_measured_zero_search_not_missing(self):
        result = assess(visibility(), search_console=gsc(impressions=0, clicks=0))
        self.assertEqual("observed", result["stages"][0]["status"])
        self.assertEqual(0, result["stages"][0]["metric"]["impressions"])
        self.assertEqual("connect_read_only_github_traffic", result["summary"]["next_measurement_action"])

    def test_measured_zero_traffic_not_missing(self):
        result = assess(visibility(), github_traffic=traffic(count=0, uniques=0))
        self.assertEqual(0, result["stages"][2]["metric"]["unique_visitors"])
        self.assertEqual("observed", result["stages"][2]["status"])

    def test_complete_aggregate_sources_still_cannot_estimate_conversions(self):
        result = assess(visibility(), search_console=gsc(), github_traffic=traffic())
        self.assertEqual(2, result["summary"]["direct_stages_observed"])
        self.assertEqual("design_privacy_preserving_aggregate_website_visits", result["summary"]["next_measurement_action"])
        self.assertEqual(0, result["summary"]["conversion_rates_estimable"])
        self.assertEqual(6, len(result["transitions"]))
        self.assertTrue(all(t["rate"] is None and t["status"] == "not_attributable" for t in result["transitions"]))
        self.assertEqual(12, result["stages"][2]["metric"]["views"])
        self.assertNotIn("secret", json.dumps(result).lower())
        self.assertFalse(result["authority"]["merge_authority"])

    def test_contributor_saturation_is_not_verified_adoption(self):
        result = assess(visibility(contributors=100, truncated=True))
        self.assertEqual("partial_proxy", result["stages"][4]["status"])
        self.assertEqual("unavailable", result["stages"][5]["status"])

    def test_bad_contributor_count_and_truncation_rejected(self):
        for count in (True, -1, "0", 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                assess(visibility(contributors=count))
        with self.assertRaisesRegex(ValueError, "boolean"):
            assess(visibility(truncated="false"))

    def test_gsc_validation_fails_closed(self):
        for override in ({"provider": "google_analytics"}, {"page_prefix": "https://example.com/"},
                         {"data_state": "all"}, {"dimensions": ["query"]},
                         {"start_date": "2026-09-29", "end_date": "2026-09-28"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                obj = gsc()
                obj["source"].update(override)
                assess(visibility(), search_console=obj)
        for count in (float("nan"), -4, True, "2"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                assess(visibility(), search_console=gsc(impressions=count))

    def test_traffic_validation_fails_closed(self):
        for override in ({"provider": "other"}, {"repository": "elsewhere/repo"},
                         {"window": "lifetime"}, {"collected_at_utc": None}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                obj = traffic()
                obj["source"].update(override)
                assess(visibility(), github_traffic=obj)
        for count, uniques in ((1.5, 1), (True, 0), (1, 2), (-1, 0)):
            with self.subTest(count=count, uniques=uniques), self.assertRaises(ValueError):
                assess(visibility(), github_traffic=traffic(count=count, uniques=uniques))

    def test_deterministic_and_aggregate_only(self):
        inputs = [visibility(), gsc(), traffic()]
        first = assess(copy.deepcopy(inputs[0]), search_console=copy.deepcopy(inputs[1]), github_traffic=copy.deepcopy(inputs[2]))
        second = assess(*[copy.deepcopy(inputs[0])], search_console=copy.deepcopy(inputs[1]), github_traffic=copy.deepcopy(inputs[2]))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual("2026-09-01/2026-09-28", first["stages"][0]["window"])
        self.assertNotIn("rows", first)


if __name__ == "__main__":
    unittest.main()
