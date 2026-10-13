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
                "keys": ["ai agent verification", "https://mskazemi.com/idkmesh/topics/ai-agent-verification.html"],
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
        self.assertIn("agent-verification", result["portfolio_clusters"])

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

    def test_search_console_http_errors_do_not_echo_sensitive_body(self):
        import io
        import urllib.error
        from unittest.mock import patch
        from scripts.search_console_snapshot import _post_json, _post_form

        def rejected(*_args, **_kwargs):
            return_error = urllib.error.HTTPError(
                "https://example.invalid/SECRET_URL", 403, "SECRET_REASON", {},
                io.BytesIO(b"SECRET_RESPONSE_TOKEN"),
            )
            raise return_error

        with patch("scripts.search_console_snapshot.urllib.request.urlopen", side_effect=rejected):
            for operation in (
                lambda: _post_json("https://example.invalid/", {}, {"Authorization": "Bearer SECRET_HEADER_TOKEN"}),
                lambda: _post_form("https://example.invalid/", {"refresh_token": "SECRET_REFRESH_TOKEN"}),
            ):
                with self.subTest(operation=operation), self.assertRaises(RuntimeError) as raised:
                    operation()
                message = str(raised.exception)
                self.assertIn("HTTP 403", message)
                for secret in ("SECRET_RESPONSE_TOKEN", "SECRET_URL", "SECRET_REASON", "SECRET_HEADER_TOKEN", "SECRET_REFRESH_TOKEN"):
                    self.assertNotIn(secret, message)
                self.assertIsNone(raised.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
