import json
import tempfile
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # Generic dependency-light suites may omit Phase 0 extras.
    Draft202012Validator = None

from tools.idkgraph_observatory import (
    GRAPH_FILENAME,
    REPORT_FILENAME,
    SUMMARY_FILENAME,
    build_observatory,
    render_health_report,
    write_outputs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "idkgraph_observatory"
VALID_ROOT = FIXTURE_ROOT / "valid"
BROKEN_ROOT = FIXTURE_ROOT / "broken"
SCHEMA_PATH = REPO_ROOT / "schemas" / "idkgraph.schema.json"
OUTPUT_FILES = (GRAPH_FILENAME, SUMMARY_FILENAME, REPORT_FILENAME)


class IDKGraphObservatoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if Draft202012Validator is None:
            cls.validator = None
        else:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            cls.validator = Draft202012Validator(schema)

    def test_clean_fixture_has_zero_seeded_deterministic_errors(self) -> None:
        graph, observatory = build_observatory(
            VALID_ROOT,
            source_revision="fixture:valid",
            revision_method="fixture",
        )

        self.assertEqual(observatory["finding_counts"]["by_severity"].get("error", 0), 0)
        self.assertEqual(observatory["finding_counts"]["by_severity"].get("warning", 0), 0)
        self.assertEqual(observatory["residual_health"]["orphan_document_candidates"], 0)
        self.assertEqual(observatory["residual_health"]["accepted_decisions_without_document_link"], 0)
        self.assertEqual(observatory["research_hypotheses"], [])
        self.assertEqual(observatory["execution"]["work_units"], 1)
        self.assertFalse(observatory["execution"]["cycle_detected"])
        self.assertEqual(len(graph["nodes"]), 3)
        self.assertEqual(observatory["source_revision"], "fixture:valid")
        self.assertEqual(observatory["source_revision_method"], "fixture")

    def test_broken_fixture_reports_two_distinct_actionable_defect_classes(self) -> None:
        _, observatory = build_observatory(
            BROKEN_ROOT,
            source_revision="fixture:broken",
            revision_method="fixture",
        )

        errors = [item for item in observatory["findings"] if item["severity"] == "error"]
        categories = {item["category"] for item in errors}

        self.assertEqual(
            categories,
            {"missing_markdown_file", "missing_markdown_anchor"},
        )
        self.assertEqual(len(errors), 2)
        for finding in errors:
            self.assertEqual(finding["source_path"], "README.md")
            self.assertTrue(finding["source_id"])
            self.assertEqual(finding["evidence"]["producer"], "T2")

    def test_fixed_snapshot_replay_is_byte_identical_for_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first = Path(first_tmp) / "run"
            second = Path(second_tmp) / "run"

            write_outputs(
                VALID_ROOT,
                first,
                source_revision="fixture:replay",
                revision_method="fixture",
            )
            write_outputs(
                VALID_ROOT,
                second,
                source_revision="fixture:replay",
                revision_method="fixture",
            )

            for filename in OUTPUT_FILES:
                with self.subTest(filename=filename):
                    self.assertEqual(
                        (first / filename).read_bytes(),
                        (second / filename).read_bytes(),
                    )

    def test_report_separates_errors_warnings_and_research_hypotheses(self) -> None:
        _, observatory = build_observatory(
            BROKEN_ROOT,
            source_revision="fixture:report",
            revision_method="fixture",
        )
        report = render_health_report(observatory)

        self.assertIn("## Deterministic errors", report)
        self.assertIn("## Deterministic warnings", report)
        self.assertIn("## Research hypotheses", report)
        self.assertIn("missing_markdown_file", report)
        self.assertIn("missing_markdown_anchor", report)
        self.assertIn("Orphan document candidates", report)
        self.assertIn("Accepted decisions without document link", report)
        self.assertIn("None are emitted automatically", report)

    def test_contract_versions_and_authority_are_explicit(self) -> None:
        _, observatory = build_observatory(
            VALID_ROOT,
            source_revision="fixture:contracts",
            revision_method="fixture",
        )

        self.assertTrue(observatory["contracts"]["t1_identity"])
        self.assertTrue(observatory["contracts"]["t2_navigation"])
        self.assertTrue(observatory["contracts"]["t3_repository_mapping"])
        self.assertTrue(observatory["contracts"]["t4_executable_cycles"])
        self.assertTrue(observatory["contracts"]["p0_residual_health"])
        self.assertEqual(
            observatory["authority"],
            {
                "repository_write": False,
                "github_mutation": False,
                "semantic_inference": False,
                "automatic_repair": False,
                "integration": False,
            },
        )

    def test_output_directory_inside_scanned_tree_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the scanned repository tree"):
            write_outputs(
                VALID_ROOT,
                VALID_ROOT / ".generated-observatory",
                source_revision="fixture:invalid-output",
                revision_method="fixture",
            )

    @unittest.skipIf(Draft202012Validator is None, "IDKGraph schema validation requires jsonschema")
    def test_clean_fixture_output_graph_validates_current_schema(self) -> None:
        graph, _ = build_observatory(
            VALID_ROOT,
            source_revision="fixture:schema",
            revision_method="fixture",
        )
        errors = sorted(self.validator.iter_errors(graph), key=lambda error: list(error.absolute_path))
        self.assertEqual([error.message for error in errors], [])


if __name__ == "__main__":
    unittest.main()
