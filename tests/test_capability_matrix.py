"""Normal-CI drift guards for the canonical capability truth matrix (#944)."""

from __future__ import annotations

import copy
import json
import unittest

from scripts.check_capability_matrix import (
    DEFAULT_MATRIX,
    REQUIRED_QUESTIONS,
    validate_document,
    validate_generated_surfaces,
    validate_readme_commands,
    validate_release_note_reference,
)


class CapabilityMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))

    def test_canonical_matrix_is_valid(self):
        self.assertEqual([], validate_document(self.document))
        self.assertEqual([], validate_readme_commands())
        self.assertEqual([], validate_generated_surfaces(self.document))

    def test_initial_twenty_questions_are_exact(self):
        first_twenty = self.document["capabilities"][:20]
        self.assertEqual(
            [f"CAP-{index:03d}" for index in range(1, 21)],
            [row["id"] for row in first_twenty],
        )
        self.assertEqual(
            list(REQUIRED_QUESTIONS),
            [row["question"] for row in first_twenty],
        )

    def test_required_question_drift_fails_closed(self):
        document = copy.deepcopy(self.document)
        document["capabilities"][0]["question"] = "A different question?"
        errors = validate_document(document)
        self.assertTrue(any("required engineering question drifted" in e for e in errors))

    def test_implemented_row_requires_code_and_evidence(self):
        document = copy.deepcopy(self.document)
        row = next(
            row for row in document["capabilities"] if row["status"] == "implemented"
        )
        row["implementation_paths"] = []
        row["evidence_paths"] = []
        errors = validate_document(document)
        self.assertTrue(any("implementation path" in e for e in errors))
        self.assertTrue(any("test/evidence path" in e for e in errors))

    def test_unknown_cli_command_fails_closed(self):
        document = copy.deepcopy(self.document)
        document["capabilities"][0]["cli_commands"] = ["removed-command"]
        self.assertTrue(
            any(
                "unknown idkmesh CLI subcommand" in e
                for e in validate_document(document)
            )
        )

    def test_missing_repository_path_fails_closed(self):
        document = copy.deepcopy(self.document)
        document["capabilities"][0]["implementation_paths"] = ["does/not/exist.py"]
        self.assertTrue(
            any(
                "missing implementation_paths path" in e
                for e in validate_document(document)
            )
        )

    def test_level_five_requires_dedicated_qualification_artifact(self):
        document = copy.deepcopy(self.document)
        row = document["capabilities"][0]
        row["evidence_level"] = 5
        row["qualification_artifact"] = None
        self.assertTrue(
            any(
                "dedicated qualification artifact" in e
                for e in validate_document(document)
            )
        )

    def test_level_five_qualification_artifact_must_exist(self):
        document = copy.deepcopy(self.document)
        row = document["capabilities"][0]
        row["evidence_level"] = 5
        row["qualification_artifact"] = "does/not/exist.json"
        self.assertTrue(
            any(
                "missing qualification_artifact path" in e
                for e in validate_document(document)
            )
        )

    def test_release_note_reference_is_present(self):
        self.assertEqual([], validate_release_note_reference())

    def test_claim_freezes_remain_explicit(self):
        by_id = {row["id"]: row for row in self.document["capabilities"]}
        for cap_id in ("CAP-005", "CAP-018", "CAP-019", "CAP-020"):
            self.assertEqual("planned", by_id[cap_id]["status"])
            self.assertEqual(0, by_id[cap_id]["evidence_level"])
        self.assertEqual("experimental", by_id["CAP-015"]["status"])
        self.assertEqual(1, by_id["CAP-015"]["evidence_level"])
        self.assertIn("local executor-admission", by_id["CAP-015"]["public_wording"])
        self.assertIn("loopback-only", by_id["CAP-017"]["public_wording"])


if __name__ == "__main__":
    unittest.main()
