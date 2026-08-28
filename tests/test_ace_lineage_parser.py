import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ace_lineage.py"
SPEC = importlib.util.spec_from_file_location("ace_lineage", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

VALID = json.loads(
    (ROOT / "examples" / "community" / "ace-lineage-valid.example.json").read_text(encoding="utf-8")
)
INVALID = json.loads(
    (ROOT / "examples" / "community" / "ace-lineage-invalid-missing-verification.example.json").read_text(encoding="utf-8")
)


def block(record):
    return "<!-- ACE_LINEAGE\n" + json.dumps(record) + "\nACE_LINEAGE -->"


class AceLineageParserTests(unittest.TestCase):
    def test_extracts_valid_lineage_from_markdown(self):
        records = MODULE.extract_markdown("before\n" + block(VALID) + "\nafter")
        self.assertEqual(len(records), 1)
        receipt = MODULE.receipt(records[0])
        self.assertEqual(receipt["descendant"], "MSKazemi/idkmesh#pr:48")
        self.assertTrue(receipt["verified"])

    def test_plain_markdown_is_quiet_observation(self):
        self.assertEqual(MODULE.extract_markdown("ordinary issue text"), [])

    def test_invalid_verified_record_is_rejected(self):
        with self.assertRaises(MODULE.LineageError):
            MODULE.extract_markdown(block(INVALID))

    def test_invalid_recorded_at_timestamp_is_rejected(self):
        record = json.loads(json.dumps(VALID))
        record["recorded_at"] = "not-a-timestamp"
        with self.assertRaises(MODULE.LineageError):
            MODULE.extract_markdown(block(record))

    def test_invalid_verification_timestamp_is_rejected(self):
        record = json.loads(json.dumps(VALID))
        record["verification"]["verified_at"] = "2026-99-99T99:99:99Z"
        with self.assertRaises(MODULE.LineageError):
            MODULE.extract_markdown(block(record))

    def test_duplicate_lineage_identity_is_rejected(self):
        text = block(VALID) + "\n" + block(VALID)
        with self.assertRaises(MODULE.LineageError):
            MODULE.extract_markdown(text)

    def test_commit_refs_are_normalized(self):
        record = json.loads(json.dumps(VALID))
        record.pop("lineage_id", None)
        record["descendant"] = {
            "repo": "MSKazemi/idkmesh",
            "kind": "commit",
            "sha": "ABCDEF1"
        }
        records = MODULE.extract_markdown(block(record))
        self.assertEqual(
            MODULE.receipt(records[0])["descendant"],
            "MSKazemi/idkmesh#commit:abcdef1"
        )


if __name__ == "__main__":
    unittest.main()
