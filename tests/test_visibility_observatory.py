from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.visibility_observatory import observe


class FakeGitHub:
    def __call__(self, path, _token, _params=None):
        if path == "/repos/MSKazemi/idkmesh":
            return {
                "stargazers_count": 7,
                "forks_count": 3,
                "subscribers_count": 2,
                "topics": ["ai-agents", "verification"],
                "created_at": "2026-08-28T12:46:30Z",
                "updated_at": "2026-09-22T00:00:00Z",
                "pushed_at": "2026-09-22T00:00:00Z",
            }
        if path == "/repos/MSKazemi/idkmesh/contributors":
            return [
                {"login": "MSKazemi", "type": "User"},
                {"login": "external-one", "type": "User"},
                {"login": "dependabot[bot]", "type": "Bot"},
            ]
        raise AssertionError(path)


def _page(title: bool = True, canonical: bool = True) -> str:
    title_tag = "<title>Example</title>" if title else ""
    canonical_tag = '<link rel="canonical" href="https://example.test/">' if canonical else ""
    return f"""<!doctype html>
<html lang="en">
<head>
{title_tag}
<meta name="description" content="Useful description.">
{canonical_tag}
<meta property="og:title" content="Example">
<meta property="og:description" content="Useful description.">
<meta property="og:image" content="https://example.test/social.png">
<script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body><h1>Example</h1></body>
</html>
"""


class VisibilityObservatoryTests(unittest.TestCase):
    def test_observer_separates_discovery_from_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            (docs / "index.html").write_text(_page(), encoding="utf-8")
            (docs / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://example.test/</loc></url>"
                "</urlset>",
                encoding="utf-8",
            )

            result = observe(
                "MSKazemi/idkmesh",
                "token",
                docs,
                request_json=FakeGitHub(),
            )

        discovery = result["github"]["discovery"]
        self.assertEqual(7, discovery["stars"])
        self.assertEqual(3, discovery["forks"])
        self.assertEqual(2, discovery["subscribers"])
        self.assertEqual(
            1,
            result["github"]["community_acquisition"]["external_commit_contributors_observed"],
        )
        self.assertEqual(1.0, result["site"]["technical_coverage"])
        self.assertEqual(1, result["site"]["sitemap"]["url_count"])
        self.assertFalse(result["authority"]["correctness_claim"])
        self.assertFalse(result["authority"]["ranking_claim"])
        self.assertFalse(result["authority"]["github_write"])
        self.assertIn(
            "search_impressions_and_nonbranded_query_coverage_not_collected",
            result["gaps"],
        )

    def test_missing_metadata_is_visible_as_a_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            (docs / "index.html").write_text(
                _page(title=False, canonical=False),
                encoding="utf-8",
            )
            result = observe(
                "MSKazemi/idkmesh",
                "token",
                docs,
                request_json=FakeGitHub(),
            )

        self.assertLess(result["site"]["technical_coverage"], 1.0)
        self.assertIn("technical_seo_metadata_incomplete", result["gaps"])
        self.assertIn("sitemap_missing_or_invalid", result["gaps"])

    def test_contributor_page_saturation_is_reported(self):
        class Saturated(FakeGitHub):
            def __call__(self, path, token, params=None):
                if path == "/repos/MSKazemi/idkmesh/contributors":
                    return [
                        {"login": f"external-{index}", "type": "User"}
                        for index in range(100)
                    ]
                return super().__call__(path, token, params)

        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            (docs / "index.html").write_text(_page(), encoding="utf-8")
            result = observe(
                "MSKazemi/idkmesh",
                "token",
                docs,
                request_json=Saturated(),
            )

        acquisition = result["github"]["community_acquisition"]
        self.assertTrue(acquisition["contributors_page_truncated"])
        self.assertEqual(100, acquisition["external_commit_contributors_observed"])

    def test_output_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            (docs / "index.html").write_text(_page(), encoding="utf-8")
            result = observe(
                "MSKazemi/idkmesh",
                "token",
                docs,
                request_json=FakeGitHub(),
            )
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
