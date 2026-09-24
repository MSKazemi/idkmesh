"""Offline Bing AI Performance exports must normalize without inventing semantics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import bing_ai_performance_import as importer


class BingAIPerformanceImportTests(unittest.TestCase):
    def _csv(self, text: str) -> tuple[tempfile.TemporaryDirectory, Path]:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "export.csv"
        path.write_text(text, encoding="utf-8")
        return tmp, path

    def test_grounding_export_exactly_maps_canonical_query(self) -> None:
        tmp, path = self._csv(
            "Grounding Query,Citations\n"
            "ai agent verification,12\n"
            "agent verification best practice,4\n"
        )
        try:
            result = importer.normalize(
                input_path=path,
                kind="grounding",
                window_start="2026-08-25",
                window_end="2026-09-23",
                citations_column="Citations",
                query_column="Grounding Query",
            )
        finally:
            tmp.cleanup()

        self.assertEqual(2, result["summary"]["rows"])
        self.assertEqual(16, result["summary"]["citation_count_sum"])
        self.assertEqual(1, result["summary"]["portfolio_exact_match_rows"])
        match = result["rows"][0]["portfolio_exact_match"]
        self.assertEqual("ai agent verification", match["mapped_intent"])
        self.assertEqual("agent-verification", match["cluster"])
        self.assertEqual(
            "https://mskazemi.com/idkmesh/topics/ai-agent-verification.html",
            match["canonical_target"],
        )
        self.assertIsNone(result["rows"][1]["portfolio_exact_match"])

    def test_mapping_export_preserves_query_page_and_count(self) -> None:
        tmp, path = self._csv(
            "Query,Page,Citation Count\n"
            "llm as a judge,https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html,7\n"
        )
        try:
            result = importer.normalize(
                input_path=path,
                kind="mapping",
                window_start="2026-09-01",
                window_end="2026-09-23",
                citations_column="Citation Count",
                query_column="Query",
                page_column="Page",
            )
        finally:
            tmp.cleanup()

        row = result["rows"][0]
        self.assertEqual("llm as a judge", row["grounding_query"])
        self.assertEqual(
            "https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html",
            row["page"],
        )
        self.assertEqual(7, row["citations"])
        self.assertEqual(
            "llm-judge-reliability",
            row["portfolio_exact_match"]["cluster"],
        )

    def test_page_export_rejects_non_idkmesh_url(self) -> None:
        tmp, path = self._csv(
            "Page,Citations\nhttps://example.com/not-idkmesh,2\n"
        )
        try:
            with self.assertRaisesRegex(importer.BingAIImportError, "page must be under"):
                importer.normalize(
                    input_path=path,
                    kind="pages",
                    window_start="2026-09-01",
                    window_end="2026-09-23",
                    citations_column="Citations",
                    page_column="Page",
                )
        finally:
            tmp.cleanup()

    def test_timeline_rejects_date_outside_declared_window(self) -> None:
        tmp, path = self._csv("Date,Citations\n2026-08-01,3\n")
        try:
            with self.assertRaisesRegex(importer.BingAIImportError, "outside"):
                importer.normalize(
                    input_path=path,
                    kind="timeline",
                    window_start="2026-09-01",
                    window_end="2026-09-23",
                    citations_column="Citations",
                    date_column="Date",
                )
        finally:
            tmp.cleanup()

    def test_missing_configured_column_fails_closed(self) -> None:
        tmp, path = self._csv("Query,Count\nai agent verification,3\n")
        try:
            with self.assertRaisesRegex(importer.BingAIImportError, "missing configured"):
                importer.normalize(
                    input_path=path,
                    kind="grounding",
                    window_start="2026-09-01",
                    window_end="2026-09-23",
                    citations_column="Citations",
                    query_column="Query",
                )
        finally:
            tmp.cleanup()

    def test_counts_accept_thousands_separator_and_reject_negative(self) -> None:
        tmp, path = self._csv(
            'Query,Citations\n'
            'ai agent verification,"1,234"\n'
        )
        try:
            result = importer.normalize(
                input_path=path,
                kind="grounding",
                window_start="2026-09-01",
                window_end="2026-09-23",
                citations_column="Citations",
                query_column="Query",
            )
        finally:
            tmp.cleanup()
        self.assertEqual(1234, result["summary"]["citation_count_sum"])

        tmp, path = self._csv("Query,Citations\nai agent verification,-1\n")
        try:
            with self.assertRaisesRegex(importer.BingAIImportError, "non-negative"):
                importer.normalize(
                    input_path=path,
                    kind="grounding",
                    window_start="2026-09-01",
                    window_end="2026-09-23",
                    citations_column="Citations",
                    query_column="Query",
                )
        finally:
            tmp.cleanup()

    def test_output_keeps_authority_boundary(self) -> None:
        tmp, path = self._csv("Query,Citations\nai agent verification,1\n")
        try:
            result = importer.normalize(
                input_path=path,
                kind="grounding",
                window_start="2026-09-01",
                window_end="2026-09-23",
                citations_column="Citations",
                query_column="Query",
            )
        finally:
            tmp.cleanup()

        self.assertTrue(result["authority"]["citation_observation"])
        self.assertFalse(result["authority"]["ranking_claim"])
        self.assertFalse(result["authority"]["traffic_claim"])
        self.assertFalse(result["authority"]["causal_claim"])
        self.assertFalse(result["authority"]["content_creation_authority"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
