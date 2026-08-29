from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.closing_keyword_guard import (
    SCHEMA_VERSION,
    main,
    scan_sources,
    scan_text,
    serialize_report,
)


ROOT = Path(__file__).resolve().parents[1]

# The two texts that actually closed issue 152 on 2026-08-29. They are kept
# verbatim so a future relaxation of the pattern fails loudly.
PR_315_BODY_LINE = (
    "- Related/Closes: Refs #152 (does not close; independent-human gate #167 remains)"
)
COMMIT_6253751_LINES = (
    "PR #315 hit this: it stated twice that it did not close #152, and merging it\n"
    "closed #152 two seconds later."
)


class ClosingKeywordRegressionTests(unittest.TestCase):
    def test_pull_request_body_that_closed_issue_152_is_reported(self) -> None:
        violations = scan_text(PR_315_BODY_LINE, source="body")

        self.assertTrue(violations)
        self.assertIn("#152", {v.reference for v in violations})

    def test_commit_message_that_closed_issue_152_is_reported(self) -> None:
        violations = scan_text(COMMIT_6253751_LINES, source="commit")

        self.assertTrue(violations)
        self.assertIn("#152", {v.reference for v in violations})

    def test_a_parenthetical_disclaimer_does_not_excuse_the_reference(self) -> None:
        violations = scan_text("Closes #152 (does not close)", source="body")

        self.assertEqual(len(violations), 1)


class ClosingKeywordDetectionTests(unittest.TestCase):
    def test_each_keyword_inflection_is_detected(self) -> None:
        for keyword in (
            "close",
            "closes",
            "closed",
            "fix",
            "fixes",
            "fixed",
            "resolve",
            "resolves",
            "resolved",
        ):
            with self.subTest(keyword=keyword):
                self.assertEqual(len(scan_text(f"{keyword} #9", source="s")), 1)

    def test_reference_forms_are_detected(self) -> None:
        for reference in (
            "#9",
            "GH-9",
            "MSKazemi/idkmesh#9",
            "https://github.com/MSKazemi/idkmesh/issues/9",
        ):
            with self.subTest(reference=reference):
                self.assertEqual(len(scan_text(f"Closes {reference}", source="s")), 1)

    def test_the_sanctioned_template_line_is_the_explicit_opt_in(self) -> None:
        line = "- Closes on merge (leave blank unless the merge should close it): #152"

        self.assertEqual(scan_text(line, source="body"), [])

    def test_a_bare_number_without_a_hash_is_not_a_reference(self) -> None:
        text = "PR 315 stated it did not close issue 152; gate 167 stays open."

        self.assertEqual(scan_text(text, source="body"), [])

    def test_a_reference_without_a_keyword_is_allowed(self) -> None:
        self.assertEqual(scan_text("This builds on #152.", source="body"), [])

    def test_a_reference_in_a_later_paragraph_is_not_associated(self) -> None:
        text = "This closes the discussion.\n\nSee #152 for context."

        self.assertEqual(scan_text(text, source="body"), [])

    def test_a_keyword_inside_a_longer_word_is_ignored(self) -> None:
        self.assertEqual(scan_text("disclosed in #152", source="body"), [])

    def test_the_reported_line_number_is_one_based(self) -> None:
        violations = scan_text("intro\nsecond\nCloses #7", source="body")

        self.assertEqual([v.line for v in violations], [3])


class ClosingKeywordReportTests(unittest.TestCase):
    def test_report_is_deterministic_and_serializable(self) -> None:
        sources = [("body", "Closes #7"), ("commit", "Refs #7")]

        first = serialize_report(scan_sources(sources))
        second = serialize_report(scan_sources(sources))

        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["summary"], {"sources": 2, "violations": 1})
        self.assertEqual(payload["sources_scanned"], ["body", "commit"])

    def test_cli_exits_nonzero_only_when_a_violation_is_present(self) -> None:
        self.assertEqual(main(["--text", "body=Closes #7", "--json"]), 1)
        self.assertEqual(main(["--text", "body=Refs #7", "--json"]), 0)

    def test_cli_skips_a_missing_file_rather_than_failing(self) -> None:
        self.assertEqual(main(["--file", "absent=/nonexistent/path.txt", "--json"]), 0)

    def test_cli_reads_a_file_source(self) -> None:
        path = ROOT / "tests" / "fixtures" / "closing_keyword_guard_sample.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Closes #7\n", encoding="utf-8")
        try:
            self.assertEqual(main(["--file", f"sample={path}", "--json"]), 1)
        finally:
            path.unlink()


class PullRequestTemplateTests(unittest.TestCase):
    def test_the_committed_template_cannot_create_a_closing_reference(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(scan_text(template, source="template"), [])

    def test_the_template_offers_both_a_refs_and_a_closes_on_merge_field(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("\n- Refs:", template)
        self.assertIn("\n- Closes on merge", template)
        self.assertLess(
            template.index("\n- Refs:"),
            template.index("\n- Closes on merge"),
            "Refs must precede Closes on merge so a number on Refs is never "
            "preceded by a closing keyword.",
        )


if __name__ == "__main__":
    unittest.main()
