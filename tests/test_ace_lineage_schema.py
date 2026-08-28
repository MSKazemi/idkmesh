import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "ace-lineage-v0.1.schema.json"
VALID_FIXTURE = ROOT / "examples" / "community" / "ace-lineage-valid.example.json"
INVALID_FIXTURE = ROOT / "examples" / "community" / "ace-lineage-invalid-missing-verification.example.json"


class AceLineageSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())
        cls.valid = json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))
        cls.invalid = json.loads(INVALID_FIXTURE.read_text(encoding="utf-8"))

    def errors(self, instance):
        return list(self.validator.iter_errors(instance))

    def test_valid_verified_lineage_passes(self):
        self.assertEqual(self.errors(self.valid), [])

    def test_verified_lineage_requires_verification_evidence(self):
        self.assertTrue(self.errors(self.invalid))

    def test_candidate_does_not_require_verification(self):
        candidate = copy.deepcopy(self.invalid)
        candidate["status"] = "candidate"
        self.assertEqual(self.errors(candidate), [])

    def test_issue_reference_requires_number_not_sha(self):
        bad = copy.deepcopy(self.valid)
        bad["seed"] = {
            "repo": "MSKazemi/idkmesh",
            "kind": "issue",
            "sha": "abcdef1"
        }
        self.assertTrue(self.errors(bad))

    def test_commit_reference_requires_sha_not_number(self):
        bad = copy.deepcopy(self.valid)
        bad["descendant"] = {
            "repo": "MSKazemi/idkmesh",
            "kind": "commit",
            "number": 48
        }
        self.assertTrue(self.errors(bad))

    def test_invalid_timestamp_is_rejected(self):
        bad = copy.deepcopy(self.valid)
        bad["recorded_at"] = "not-a-timestamp"
        self.assertTrue(self.errors(bad))


if __name__ == "__main__":
    unittest.main()
