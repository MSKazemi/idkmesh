"""The webmaster measurement runbook must stay bound to the SEO evidence contract."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "operations" / "WEBMASTER_TOOLS_MEASUREMENT_RUNBOOK.md"
TOPICS = ROOT / "docs" / "topics"


class WebmasterMeasurementRunbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = RUNBOOK.read_text(encoding="utf-8")

    def test_property_and_sitemap_match_the_public_site(self) -> None:
        self.assertIn("https://mskazemi.com/idkmesh/", self.text)
        self.assertIn("https://mskazemi.com/idkmesh/sitemap.xml", self.text)

    def test_all_eleven_topic_urls_are_named(self) -> None:
        expected = {"https://mskazemi.com/idkmesh/topics/"}
        expected.update(
            f"https://mskazemi.com/idkmesh/topics/{path.stem}.html"
            for path in TOPICS.glob("*.md")
            if path.name != "index.md"
        )
        self.assertEqual(11, len(expected))
        missing = sorted(url for url in expected if url not in self.text)
        self.assertEqual([], missing)

    def test_runbook_points_to_canonical_evidence_contract(self) -> None:
        for expected in (
            "config/seo-topics-v1.json",
            "schemas/search-visibility-observation-v0.1.schema.json",
            "evidence/search-visibility/observations.json",
            "tools/search_visibility_report.py",
            "issue #665",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.text)

    def test_google_and_bing_measurement_surfaces_are_distinguished(self) -> None:
        for expected in (
            "URL-prefix property",
            "Search Performance",
            "AI Performance",
            "grounding queries",
            "index_inspection",
            "webmaster_export",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
