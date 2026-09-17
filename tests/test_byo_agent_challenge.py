import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "byo_agent_challenge.py"
SPEC = importlib.util.spec_from_file_location("byo_agent_challenge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ByoAgentChallengeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.challenge_path = (
            ROOT / "examples" / "challenges" / "byo-agent-001" / "challenge.json"
        )
        cls.challenge = json.loads(cls.challenge_path.read_text(encoding="utf-8"))
        cls.schema_path = ROOT / "schemas" / "result-manifest.schema.json"
        cls.schema_bytes = cls.schema_path.read_bytes()

    def perfect_submission(self):
        expected = {
            "minimal-completed": True,
            "missing-confidence": False,
            "bad-artifact-digest": False,
            "unknown-status": False,
            "evidence-pass": True,
            "confidence-out-of-range": False,
        }
        return {
            "version": 1,
            "challenge_id": self.challenge["challenge_id"],
            "participant": {
                "kind": "ai_agent",
                "tool": "test-fixture",
                "model": "none",
                "source_revision": self.challenge["source_revision"],
            },
            "measurements": {
                "wall_seconds": 1.0,
                "human_review_minutes": 0.0,
            },
            "answers": [
                {
                    "case_id": case["case_id"],
                    "schema_valid": expected[case["case_id"]],
                }
                for case in self.challenge["cases"]
            ],
        }

    def test_challenge_is_bound_to_canonical_result_manifest_schema(self):
        self.assertEqual(
            self.challenge["schema"], "schemas/result-manifest.schema.json"
        )
        MODULE.validate_challenge(copy.deepcopy(self.challenge))

    def test_challenge_pins_exact_schema_blob(self):
        expected = hashlib.sha1(
            f"blob {len(self.schema_bytes)}\0".encode("ascii") + self.schema_bytes
        ).hexdigest()
        self.assertEqual(self.challenge["schema_git_blob_sha"], expected)

    def test_schema_drift_fails_closed_before_scoring(self):
        drifted = self.schema_bytes + b"\n"
        with self.assertRaisesRegex(ValueError, "differs from the challenge pin"):
            MODULE.evaluate(
                copy.deepcopy(self.challenge), self.perfect_submission(), drifted
            )

    def test_reference_classifications_match_canonical_schema(self):
        report = MODULE.evaluate(
            copy.deepcopy(self.challenge),
            self.perfect_submission(),
            self.schema_bytes,
        )
        self.assertEqual(
            report["score"],
            {"correct": 6, "total": 6, "accuracy": 1.0, "passed": True},
        )
        self.assertEqual(
            report["schema_git_blob_sha"], self.challenge["schema_git_blob_sha"]
        )
        self.assertFalse(report["authority"]["hidden_benchmark_evidence"])
        self.assertFalse(report["authority"]["independent_review"])
        self.assertFalse(report["authority"]["integration_authority"])
        self.assertEqual(
            report["measurements"]["status"], "self_reported_unverified"
        )

    def test_wrong_answer_is_scored_without_becoming_structural_error(self):
        submission = self.perfect_submission()
        submission["answers"][0]["schema_valid"] = False
        report = MODULE.evaluate(
            copy.deepcopy(self.challenge), submission, self.schema_bytes
        )
        self.assertEqual(report["score"]["correct"], 5)
        self.assertFalse(report["score"]["passed"])

    def test_duplicate_answer_fails_closed(self):
        submission = self.perfect_submission()
        submission["answers"][1]["case_id"] = submission["answers"][0]["case_id"]
        with self.assertRaisesRegex(ValueError, "duplicate submission case_id"):
            MODULE.evaluate(copy.deepcopy(self.challenge), submission, self.schema_bytes)

    def test_missing_answer_fails_closed(self):
        submission = self.perfect_submission()
        submission["answers"].pop()
        with self.assertRaisesRegex(ValueError, "missing cases"):
            MODULE.evaluate(copy.deepcopy(self.challenge), submission, self.schema_bytes)

    def test_non_finite_or_negative_measurement_fails_closed(self):
        for value in (-1, float("inf"), float("nan"), True):
            with self.subTest(value=value):
                submission = self.perfect_submission()
                submission["measurements"]["wall_seconds"] = value
                with self.assertRaises(ValueError):
                    MODULE.evaluate(
                        copy.deepcopy(self.challenge), submission, self.schema_bytes
                    )

    def test_input_loader_rejects_duplicate_keys_and_non_finite_numbers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            duplicate = tmp / "duplicate.json"
            duplicate.write_text('{"version": 1, "version": 1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key: version"):
                MODULE._load_object(duplicate, "submission")

            non_finite = tmp / "non-finite.json"
            non_finite.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                MODULE._load_object(non_finite, "submission")

    def test_cli_exit_codes_distinguish_pass_wrong_answer_and_invalid_submission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            submission_path = tmp / "submission.json"
            submission_path.write_text(
                json.dumps(self.perfect_submission()), encoding="utf-8"
            )
            self.assertEqual(
                MODULE.main([str(self.challenge_path), str(submission_path)]), 0
            )

            wrong = self.perfect_submission()
            wrong["answers"][0]["schema_valid"] = False
            submission_path.write_text(json.dumps(wrong), encoding="utf-8")
            self.assertEqual(
                MODULE.main([str(self.challenge_path), str(submission_path)]), 1
            )

            invalid = self.perfect_submission()
            invalid["answers"] = []
            submission_path.write_text(json.dumps(invalid), encoding="utf-8")
            self.assertEqual(
                MODULE.main([str(self.challenge_path), str(submission_path)]), 2
            )

    def test_serialization_is_deterministic_and_strict_json(self):
        report = MODULE.evaluate(
            copy.deepcopy(self.challenge),
            self.perfect_submission(),
            self.schema_bytes,
        )
        first = MODULE.serialize(report)
        second = MODULE.serialize(report)
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["score"]["correct"], 6)


if __name__ == "__main__":
    unittest.main()
