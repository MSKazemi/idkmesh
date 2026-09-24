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
        line = "- Closes: #152"

        self.assertEqual(scan_text(line, source="body"), [])

    def test_the_opt_in_line_stays_exempt_for_every_reference_form(self) -> None:
        for line in (
            "- Closes:",
            "- Closes: #152",
            "- Closes: #152, #153",
            "- Closes: #152 #153",
            "- CLOSES: #152",
            "Closes: MSKazemi/idkmesh#152",
            "Closes: GH-152",
        ):
            with self.subTest(line=line):
                self.assertEqual(scan_text(line, source="body"), [])

    def test_the_opt_in_line_does_not_shield_a_second_keyword_beside_it(self) -> None:
        """The exemption covers a whole line, so it must not be a blanket pass.

        ``Closes:`` naming no reference of its own, followed by prose that ends
        in an unrelated closing keyword, would have GitHub close the adjacent
        number while the opt-in beside it hid the pair from this guard. The
        exemption therefore applies only while the line carries nothing but
        references. A false positive costs one rephrasing; this false negative
        would silently dissolve a review gate.
        """
        violations = scan_text(
            "Closes: superseded by prose, fixes #500", source="body"
        )

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reference, "#500")

    def test_prose_after_the_opt_in_colon_is_still_reported(self) -> None:
        violations = scan_text("Closes: this supersedes #123", source="body")

        self.assertEqual(len(violations), 1)

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


class GuardSelfConsistencyTests(unittest.TestCase):
    def test_the_guard_source_cannot_create_a_closing_reference(self) -> None:
        """The tool must not carry the pattern it forbids, so quoting it is safe."""
        source = (ROOT / "tools" / "closing_keyword_guard.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(scan_text(source, source="tool"), [])

    def test_the_contributor_guidance_cannot_create_a_closing_reference(self) -> None:
        guidance = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

        self.assertEqual(scan_text(guidance, source="contributing"), [])


class PullRequestTemplateTests(unittest.TestCase):
    def test_the_committed_template_cannot_create_a_closing_reference(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(scan_text(template, source="template"), [])

    def test_the_template_offers_both_a_refs_and_a_closes_field(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("\n- Refs:", template)
        self.assertIn("\n- Closes:", template)
        self.assertLess(
            template.index("\n- Refs:"),
            template.index("\n- Closes:"),
            "Refs must precede Closes so a number on Refs is never "
            "preceded by a closing keyword.",
        )

    def test_the_closes_field_carries_no_text_that_could_break_adjacency(self) -> None:
        """Issue #858: `Closes on merge: #663` never closed the issue, because

        the explanatory words sitting between the keyword and the number kept
        GitHub's linker from recognizing it. The fillable line must therefore
        stay bare, with any instructions kept in the surrounding prose instead
        of on the line a contributor appends the issue number to.
        """
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )

        line = next(
            line for line in template.splitlines() if line.strip().startswith("- Closes:")
        )
        self.assertEqual(line.strip(), "- Closes:")

    def test_the_draft_pr_steward_emits_the_same_closes_field(self) -> None:
        """The steward writes its own pull request body from a separate string.

        Nothing but this assertion keeps the two in step, and the retired
        ``Closes on merge:`` field had to be corrected in both places at once.
        A steward body carrying the old field would reintroduce exactly the
        auto-close miss issue 858 recorded, on every automatically opened
        Draft PR.
        """
        steward = (ROOT / "tools" / "auto_draft_pr_steward.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("\n- Closes:\n", steward)
        self.assertNotIn("Closes on merge", steward)
        self.assertEqual(scan_text(steward, source="steward"), [])


class SelfReferenceTests(unittest.TestCase):
    """`gh pr merge --squash` appends the pull request's own number.

    A title that legitimately uses a closing keyword therefore trips the guard
    on a reference to the pull request being merged. That reference is not an
    issue, so reporting it as a violation trains reviewers to merge past the
    guard -- which is the exact failure the guard exists to prevent.

    PR 362 hit this: its subject was
    "tools: record a registered issue that closed while its precondition
    stayed unmet (#362)".
    """

    SUBJECT = (
        "tools: record a registered issue that closed while its precondition "
        "stayed unmet (#362)"
    )

    def test_the_squash_subject_is_a_violation_without_the_flag(self):
        report = scan_sources([("subject", self.SUBJECT)])
        self.assertEqual(report["summary"]["violations"], 1)
        self.assertEqual(report["violations"][0]["reference"], "#362")

    def test_naming_the_pull_request_suppresses_only_its_own_number(self):
        report = scan_sources([("subject", self.SUBJECT)], self_reference=362)
        self.assertEqual(report["summary"]["violations"], 0)
        self.assertEqual(report["summary"]["suppressed_self_references"], 1)
        self.assertEqual(
            report["suppressed_self_references"][0]["reference"], "#362"
        )

    def test_a_real_issue_reference_survives_the_suppression(self):
        report = scan_sources(
            [("subject", "fix: closed #10 while merging (#362)")],
            self_reference=362,
        )
        self.assertEqual(report["summary"]["violations"], 1)
        self.assertEqual(report["violations"][0]["reference"], "#10")

    def test_a_different_number_is_not_suppressed(self):
        report = scan_sources([("subject", self.SUBJECT)], self_reference=999)
        self.assertEqual(report["summary"]["violations"], 1)
        self.assertEqual(report["summary"]["suppressed_self_references"], 0)

    def test_the_report_omits_the_key_when_no_number_is_given(self):
        report = scan_sources([("subject", self.SUBJECT)])
        self.assertNotIn("self_reference", report)
        self.assertNotIn("suppressed_self_references", report)

    def test_the_report_stays_deterministic_under_suppression(self):
        sources = [("subject", self.SUBJECT)]
        first = serialize_report(scan_sources(sources, self_reference=362))
        second = serialize_report(scan_sources(sources, self_reference=362))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
