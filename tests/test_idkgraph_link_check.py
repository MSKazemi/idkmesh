import json
import tempfile
import unittest
from pathlib import Path

from tools.idkgraph_link_check import check_repository, serialize_report


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "idkgraph_links"


class LinkDiagnosticsTests(unittest.TestCase):
    def test_valid_fixture_has_zero_deterministic_errors(self) -> None:
        report = check_repository(FIXTURES / "valid")

        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(report["external_links_skipped"], 1)
        self.assertEqual(report["links_checked"], 6)
        self.assertEqual(report["excluded_paths"], [])
        self.assertEqual(report["findings"], [])

    def test_broken_fixture_distinguishes_failure_categories(self) -> None:
        report = check_repository(FIXTURES / "broken")
        errors = [item for item in report["findings"] if item["severity"] == "error"]
        warnings = [item for item in report["findings"] if item["severity"] == "warning"]

        self.assertEqual(report["error_count"], 3)
        self.assertEqual(
            {item["category"] for item in errors},
            {"missing_file", "missing_anchor", "outside_repository"},
        )
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["category"], "unsupported_reference_link")

        missing_file = next(item for item in errors if item["category"] == "missing_file")
        self.assertEqual(missing_file["source_document"], "index.md")
        self.assertEqual(missing_file["normalized_target_path"], "missing.md")
        self.assertIsNone(missing_file["target_anchor"])

        missing_anchor = next(item for item in errors if item["category"] == "missing_anchor")
        self.assertEqual(missing_anchor["normalized_target_path"], "existing.md")
        self.assertEqual(missing_anchor["target_anchor"], "does-not-exist")

    def test_report_bytes_and_finding_order_are_stable(self) -> None:
        first = serialize_report(check_repository(FIXTURES / "broken"))
        second = serialize_report(check_repository(FIXTURES / "broken"))

        self.assertEqual(first, second)
        decoded = json.loads(first)
        keys = [
            (item["source_document"], item["line"], item["raw_target"], item["category"])
            for item in decoded["findings"]
        ]
        self.assertEqual(keys, sorted(keys))

    def test_fenced_links_are_ignored_and_explicit_html_id_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.md").write_text(
                """# Home\n\n<a id=\"explicit-anchor\"></a>\n\n[explicit](#explicit-anchor)\n\n```md\n[not-real](missing.md)\n```\n""",
                encoding="utf-8",
            )

            report = check_repository(root)
            self.assertEqual(report["error_count"], 0)
            self.assertEqual(report["warning_count"], 0)
            self.assertEqual(report["links_checked"], 1)

    def test_github_ui_navigation_is_warning_not_filesystem_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "[issue](../../issues/24)\n[pull](../../pull/91)\n",
                encoding="utf-8",
            )

            report = check_repository(root)
            self.assertEqual(report["error_count"], 0)
            self.assertEqual(report["warning_count"], 2)
            self.assertEqual(
                {item["category"] for item in report["findings"]},
                {"github_navigation_link"},
            )

    def test_negative_fixture_can_be_explicitly_excluded_from_health_scan(self) -> None:
        report = check_repository(FIXTURES, excluded_paths=["broken"])

        self.assertEqual(report["excluded_paths"], ["broken"])
        self.assertEqual(report["documents_scanned"], 3)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)


if __name__ == "__main__":
    unittest.main()
