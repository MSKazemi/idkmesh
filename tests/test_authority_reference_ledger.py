from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.authority_reference_ledger import render, validate

TOPICS = {"clusters": [{"id": f"c{i}", "url": f"https://mskazemi.com/idkmesh/topics/p{i}.html"} for i in range(10)]}
BASE = {"id": "ref-01", "source_url": "https://example.org/article", "target_url": "https://mskazemi.com/idkmesh/topics/p0.html", "cluster_id": "c0", "kind": "independent", "review_status": "owner_reviewed", "link_status": "direct_link_checked", "first_observed": "2026-10-11", "note": "Checked publicly reachable direct link to target."}


class AuthorityTests(unittest.TestCase):
    def test_empty_baseline_does_not_mean_zero_real_backlinks(self):
        result = render({"version": 1, "references": []}, TOPICS)
        self.assertIn("**0**", result)
        self.assertIn("does **not** mean there are zero real-world", result)
        self.assertIn("| `c9` | 0 | 0 |", result)

    def test_reviewed_direct_link_counts_once_per_host(self):
        second = dict(BASE, id="ref-02", source_url="https://example.org/another", target_url="https://mskazemi.com/idkmesh/topics/p1.html", cluster_id="c1")
        ledger = {"version": 1, "references": [second, BASE]}
        result = render(ledger, TOPICS)
        self.assertIn("direct-link claims classified independent: **2**", result)
        self.assertIn("referring hosts: **1**", result)
        self.assertIn("of 10**", result)
        self.assertIn("| `c1` | 1 | 1 |", result)
        self.assertEqual(render({"version": 1, "references": [BASE, second]}, TOPICS), result)

    def test_project_authored_syndication_and_unreviewed_are_not_independent(self):
        for kind, status, link in [("project_authored", "owner_reviewed", "direct_link_checked"), ("syndication", "owner_reviewed", "direct_link_checked"), ("independent", "unreviewed", "mention_only"), ("external_unknown", "owner_reviewed", "direct_link_checked")]:
            with self.subTest(kind=kind, status=status):
                row = dict(BASE, kind=kind, review_status=status, link_status=link)
                self.assertIn("direct-link claims classified independent: **0**", render({"version": 1, "references": [row]}, TOPICS))

    def test_reject_claims_without_review(self):
        row = dict(BASE, review_status="unreviewed")
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            validate({"version": 1, "references": [row]}, TOPICS)

    def test_reject_owned_or_local_source_urls(self):
        for url in ["https://mskazemi.com/idkmesh/", "https://github.com/MSKazemi/idkmesh", "http://example.org/x", "https://127.0.0.1/a", "https://localhost.local/x", "https://example.org/?token=private", "https://user:pass@example.org/x"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate({"version": 1, "references": [dict(BASE, source_url=url)]}, TOPICS)

    def test_target_must_match_cluster(self):
        with self.assertRaisesRegex(ValueError, "canonical"):
            validate({"version": 1, "references": [dict(BASE, target_url="https://mskazemi.com/idkmesh/topics/p1.html")]}, TOPICS)

    def test_duplicate_sources_or_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate reference id"):
            validate({"version": 1, "references": [BASE, BASE]}, TOPICS)
        with self.assertRaisesRegex(ValueError, "duplicate source/target"):
            validate({"version": 1, "references": [BASE, dict(BASE, id="ref-02")]}, TOPICS)

    def test_committed_report_matches_ledger(self):
        root = Path(__file__).resolve().parents[1]
        ledger = json.loads((root / "evidence/search-visibility/authority-references.json").read_text())
        topics = json.loads((root / "config/seo-topics-v1.json").read_text())
        report = (root / "evidence/search-visibility/AUTHORITY_REPORT.md").read_text()
        self.assertEqual(report, render(ledger, topics))

    def test_reject_extra_fields_invalid_date_and_multiline_notes(self):
        for row in [dict(BASE, secret="not allowed"), dict(BASE, first_observed="2026-13-01"), dict(BASE, note="line one\nline two")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate({"version": 1, "references": [row]}, TOPICS)

if __name__ == "__main__":
    unittest.main()
