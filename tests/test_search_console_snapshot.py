from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.discovery_query_portfolio import load_json
from scripts.search_console_snapshot import analyze_rows, collect, resolve_access_token


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = load_json(ROOT / "config/discovery-query-portfolio-v0.1.json")


class SearchConsoleSnapshotTests(unittest.TestCase):
    def test_analyze_separates_branded_nonbranded_and_portfolio_queries(self):
        rows = [
            {
                "keys": ["ai agent verification", "https://mskazemi.com/idkmesh/concepts.html"],
                "clicks": 4,
                "impressions": 100,
                "ctr": 0.04,
                "position": 8.0,
            },
            {
                "keys": ["idkmesh", "https://mskazemi.com/idkmesh/"],
                "clicks": 10,
                "impressions": 20,
                "ctr": 0.5,
                "position": 1.0,
            },
            {
                "keys": ["unrelated query", "https://example.com/other"],
                "clicks": 1,
                "impressions": 10,
                "ctr": 0.1,
                "position": 5.0,
            },
        ]
        result = analyze_rows(
            rows,
            PORTFOLIO,
            page_prefix="https://mskazemi.com/idkmesh/",
        )
        self.assertEqual(120.0, result["summary"]["all"]["impressions"])
        self.assertEqual(100.0, result["summary"]["nonbranded"]["impressions"])
        self.assertEqual(20.0, result["summary"]["branded"]["impressions"])
        self.assertEqual(1, result["summary"]["portfolio_queries_with_observations"])
        self.assertIn("ai-agent-verification", result["portfolio_clusters"])

    def test_collect_uses_query_and_page_dimensions(self):
        payloads = []

        def fake_post(_url, payload, headers):
            payloads.append(copy.deepcopy(payload))
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            return {
                "rows": [
                    {
                        "keys": ["ai agent verification", "https://mskazemi.com/idkmesh/concepts.html"],
                        "clicks": 2,
                        "impressions": 50,
                        "ctr": 0.04,
                        "position": 9.0,
                    }
                ]
            }

        result = collect(
            site_url="sc-domain:mskazemi.com",
            access_token="token",
            start_date="2026-08-01",
            end_date="2026-08-28",
            portfolio=PORTFOLIO,
            page_prefix="https://mskazemi.com/idkmesh/",
            max_rows=100,
            post_json=fake_post,
        )
        self.assertEqual(["query", "page"], payloads[0]["dimensions"])
        self.assertEqual("final", payloads[0]["dataState"])
        self.assertEqual("web", payloads[0]["type"])
        self.assertEqual(50.0, result["summary"]["nonbranded"]["impressions"])
        self.assertTrue(result["authority"]["search_demand_observation"])
        self.assertFalse(result["authority"]["causal_claim"])
        self.assertFalse(result["authority"]["content_creation_authority"])

    def test_refresh_token_path_is_supported_without_exposing_credentials(self):
        seen = {}

        def fake_form(url, fields):
            seen["url"] = url
            seen["fields"] = fields
            return {"access_token": "refreshed"}

        token = resolve_access_token(
            None,
            "refresh-secret",
            "client-id",
            "client-secret",
            post_form=fake_form,
        )
        self.assertEqual("refreshed", token)
        self.assertEqual("refresh_token", seen["fields"]["grant_type"])

    def test_direct_access_token_takes_precedence(self):
        token = resolve_access_token(
            "direct",
            "refresh-secret",
            "client-id",
            "client-secret",
            post_form=lambda *_args, **_kwargs: self.fail("refresh should not be called"),
        )
        self.assertEqual("direct", token)

    def test_invalid_ctr_fails_closed(self):
        rows = [
            {
                "keys": ["ai agent verification", "https://mskazemi.com/idkmesh/concepts.html"],
                "clicks": 2,
                "impressions": 10,
                "ctr": 1.2,
                "position": 3,
            }
        ]
        with self.assertRaisesRegex(ValueError, "CTR"):
            analyze_rows(rows, PORTFOLIO, page_prefix=None)


if __name__ == "__main__":
    unittest.main()
