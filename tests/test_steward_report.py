"""Tests for the offline Auto Draft PR Steward report consumer."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from idkmesh import cli, steward_report


def candidate(branch: str, head: str) -> dict:
    return {
        "branch": branch,
        "base": "main",
        "head_sha": head,
        "ahead_by": 2,
        "behind_by": 0,
    }


def valid_report() -> dict:
    first = candidate("feat/one", "a" * 40)
    second = candidate("docs/two", "b" * 40)
    return {
        "schema": steward_report.SCHEMA_ID,
        "repository": "MSKazemi/idkmesh",
        "generated_at": "2026-09-22T16:00:00Z",
        "status": "completed",
        "dry_run": False,
        "policy": {
            "path": "config/auto-draft-pr.json",
            "sha256": "c" * 64,
        },
        "provenance": {
            "workflow": "Auto Draft PR Steward",
            "run_id": "123",
            "run_attempt": "1",
            "trusted_head_sha": "d" * 40,
        },
        "authority": dict(steward_report.EXPECTED_AUTHORITY),
        "candidate_count": 2,
        "rate_limit_remaining": 4321,
        "blocked_reason": None,
        "summary": {
            "planned": 2,
            "created": 1,
            "skipped": 1,
        },
        "planned": [first, second],
        "created": [
            {
                **first,
                "number": 701,
                "url": "https://github.com/MSKazemi/idkmesh/pull/701",
            }
        ],
        "skipped": [
            {
                **second,
                "reason": "head_moved",
                "current_head_sha": "e" * 40,
            }
        ],
    }


class StewardReportValidationTests(unittest.TestCase):
    def test_valid_report_is_accepted(self):
        report = valid_report()
        self.assertIs(steward_report.validate_report(report), report)

    def test_repository_owner_name_contract(self):
        report = valid_report()
        steward_report.validate_report(report)

        for invalid in (
            "MSKazemi",
            "/idkmesh",
            "MSKazemi/",
            "MS Kazemi/idkmesh",
            "MSKazemi/idk mesh",
            "MSKazemi/idkmesh/extra",
        ):
            with self.subTest(repository=invalid):
                bad = valid_report()
                bad["repository"] = invalid
                with self.assertRaisesRegex(
                    steward_report.StewardReportInputError,
                    "owner/name",
                ):
                    steward_report.validate_report(bad)

    def test_duplicate_json_keys_are_rejected(self):
        text = json.dumps(valid_report())
        text = text.replace(
            '"status": "completed"',
            '"status": "completed", "status": "blocked"',
            1,
        )
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "duplicate JSON key"
        ):
            steward_report.parse_report_text(text, source="duplicate.json")

    def test_python_only_json_constants_are_rejected(self):
        text = json.dumps(valid_report()).replace(
            '"rate_limit_remaining": 4321',
            '"rate_limit_remaining": NaN',
            1,
        )
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "not valid JSON"
        ):
            steward_report.parse_report_text(text)

    def test_authority_escalation_is_rejected(self):
        report = valid_report()
        report["authority"]["merge"] = True
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "authority block"
        ):
            steward_report.validate_report(report)

    def test_numeric_authority_values_do_not_alias_json_booleans(self):
        for key, value in (("draft_pr_create", 1), ("merge", 0)):
            with self.subTest(key=key, value=value):
                report = valid_report()
                report["authority"][key] = value
                with self.assertRaisesRegex(
                    steward_report.StewardReportInputError, "authority block"
                ):
                    steward_report.validate_report(report)

    def test_summary_count_mismatch_is_rejected(self):
        report = valid_report()
        report["summary"]["created"] = 2
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError,
            "summary.created.*contains 1",
        ):
            steward_report.validate_report(report)

    def test_created_pr_url_must_match_repository_and_number(self):
        report = valid_report()
        report["created"][0]["url"] = (
            "https://github.com/someone/else/pull/999"
        )
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "canonical PR URL"
        ):
            steward_report.validate_report(report)

    def test_outcome_must_correspond_to_a_planned_candidate(self):
        report = valid_report()
        report["skipped"][0]["branch"] = "docs/not-planned"
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError,
            "does not correspond to a planned candidate",
        ):
            steward_report.validate_report(report)

    def test_head_moved_requires_current_head(self):
        report = valid_report()
        del report["skipped"][0]["current_head_sha"]
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "missing required keys"
        ):
            steward_report.validate_report(report)

    def test_pr_already_exists_forbids_unexpected_current_head(self):
        report = valid_report()
        skipped = report["skipped"][0]
        skipped["reason"] = "pr_already_exists"
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError, "unsupported keys"
        ):
            steward_report.validate_report(report)

    def test_disabled_report_is_valid_only_with_zero_work(self):
        report = valid_report()
        report.update(
            status="disabled",
            candidate_count=None,
            rate_limit_remaining=None,
            blocked_reason="policy_disabled",
            planned=[],
            created=[],
            skipped=[],
            summary={"planned": 0, "created": 0, "skipped": 0},
        )
        steward_report.validate_report(report)
        report["planned"] = [candidate("feat/unexpected", "f" * 40)]
        report["summary"]["planned"] = 1
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError,
            "disabled report cannot contain",
        ):
            steward_report.validate_report(report)

    def test_blocked_report_is_valid_only_before_scan_in_v0_1(self):
        report = valid_report()
        report.update(
            status="blocked",
            candidate_count=None,
            blocked_reason=(
                "github_api_budget_low: remaining=1000, required=1500"
            ),
            planned=[],
            created=[],
            skipped=[],
            summary={"planned": 0, "created": 0, "skipped": 0},
        )
        steward_report.validate_report(report)
        report["candidate_count"] = 0
        with self.assertRaisesRegex(
            steward_report.StewardReportInputError,
            "blocked report must have candidate_count null",
        ):
            steward_report.validate_report(report)

    def test_bom_is_tolerated(self):
        parsed = steward_report.parse_report_text(
            "\ufeff" + json.dumps(valid_report()),
            source="bom.json",
        )
        self.assertEqual(parsed["repository"], "MSKazemi/idkmesh")


class StewardReportFileBoundaryTests(unittest.TestCase):
    def test_loader_rejects_oversized_report_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "steward-report.json"
            path.write_bytes(b"{" + b" " * steward_report.MAX_REPORT_BYTES + b"}")
            with self.assertRaisesRegex(
                steward_report.StewardReportInputError,
                "offline-reader limit",
            ):
                steward_report.load_report(path)

    def test_loader_rejects_non_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                steward_report.StewardReportInputError,
                "regular file",
            ):
                steward_report.load_report(Path(tmp))


class StewardReportRenderingTests(unittest.TestCase):
    def test_default_summary_is_concise_and_authority_explicit(self):
        rendered = steward_report.render_summary(valid_report())
        self.assertIn("IDKMesh Auto Draft PR Steward", rendered)
        self.assertIn("Status: completed", rendered)
        self.assertIn("Created Draft PRs: 1", rendered)
        self.assertIn("merge=false", rendered)
        self.assertNotIn("feat/one", rendered)

    def test_details_list_planned_created_and_skipped_items(self):
        rendered = steward_report.render_summary(
            valid_report(), details=True
        )
        self.assertIn("Planned candidates:", rendered)
        self.assertIn('"feat/one"', rendered)
        self.assertIn("Created Draft PRs:", rendered)
        self.assertIn("#701", rendered)
        self.assertIn("Skipped candidates:", rendered)
        self.assertIn("head_moved", rendered)


class StewardReportCliTests(unittest.TestCase):
    def _write(self, directory: str, data: dict) -> Path:
        path = Path(directory) / "steward-report.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_cli_validates_and_summarizes_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, valid_report())
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(["steward-report", str(path), "--details"])
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("Status: completed", stdout.getvalue())
        self.assertIn("#701", stdout.getvalue())

    def test_cli_reports_contract_error_without_traceback(self):
        report = valid_report()
        report["authority"]["merge"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, report)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(["steward-report", str(path)])
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error:", stderr.getvalue())
        self.assertIn("authority block", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_missing_file_is_clean_exit_2(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = cli.main(["steward-report", "/definitely/missing/report.json"])
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("input file not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
