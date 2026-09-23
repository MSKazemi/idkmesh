"""Search visibility evidence must stay measurable without inventing a score."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tools.search_visibility_report as svr


class VisibilityLedgerTests(unittest.TestCase):
    def test_target_map_contains_exactly_one_hundred_intents(self) -> None:
        self.assertEqual(100, len(svr.intent_index()))

    def test_committed_ledger_is_semantically_valid(self) -> None:
        self.assertIsInstance(svr.observations(), list)

    def test_committed_report_matches_the_ledger(self) -> None:
        expected = svr.render(svr.observations())
        actual = svr.REPORT.read_text(encoding="utf-8")
        self.assertEqual(expected, actual)

    def test_empty_ledger_does_not_invent_visibility(self) -> None:
        text = svr.render([])
        self.assertIn("Recorded observations: **0**", text)
        self.assertIn("surfaced at least once: **0**", text)
        self.assertIn(
            "No post-deployment search or answer-engine observations", text
        )

    def test_unknown_intent_is_rejected(self) -> None:
        payload = {
            "schema_version": "0.1",
            "observations": [
                {
                    "id": "fixture/unknown",
                    "observed_at": "2026-09-23T12:00:00Z",
                    "engine": "google",
                    "surface": "web_search",
                    "evidence_class": "manual_reproduction",
                    "mapped_intent": "not in the map",
                    "query": "fixture query",
                    "target_url": "https://mskazemi.com/idkmesh/",
                    "surfaced": False,
                    "notes": "fixture",
                }
            ],
        }
        original = svr.LEDGER
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            try:
                svr.LEDGER = path
                with self.assertRaises(svr.VisibilityError):
                    svr.observations()
            finally:
                svr.LEDGER = original

    def test_non_surfaced_observation_cannot_claim_a_citation(self) -> None:
        mapped = next(iter(svr.intent_index()))
        payload = {
            "schema_version": "0.1",
            "observations": [
                {
                    "id": "fixture/citation",
                    "observed_at": "2026-09-23T12:00:00Z",
                    "engine": "chatgpt",
                    "surface": "ai_answer",
                    "evidence_class": "manual_reproduction",
                    "mapped_intent": mapped,
                    "query": mapped,
                    "target_url": "https://mskazemi.com/idkmesh/",
                    "surfaced": False,
                    "citation_url": "https://mskazemi.com/idkmesh/",
                    "notes": "fixture",
                }
            ],
        }
        original = svr.LEDGER
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            try:
                svr.LEDGER = path
                with self.assertRaises(svr.VisibilityError):
                    svr.observations()
            finally:
                svr.LEDGER = original


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
