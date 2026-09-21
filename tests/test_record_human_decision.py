"""A recorded human decision must bind to the exact evidence report it decides on.

``experiments/run_evidence_report.py`` already renders a machine-suggested
``human_decision`` recommendation, but nothing lets a human record their own
accept/reject/escalate decision back into a persisted artifact. These tests
cover ``experiments/record_human_decision.py``: a valid recording validates
against the new ``human-decision-record-v0.1`` schema, an invalid decision
value is rejected, and a decision record correctly detects a swapped/
corrupted evidence report -- the actual security-relevant property of this
contract.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        "human decision record tests require the Phase 0 jsonschema dependency"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import record_human_decision as MODULE  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402
from run_evidence_report import build_report  # noqa: E402
from two_attempt_orchestrator import run_config  # noqa: E402

CONFIG = ROOT / "examples/orchestration/two-attempt-good-vs-bad.json"


class HumanDecisionRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run_record = run_config(CONFIG)
        cls.report = build_report(cls.run_record)

    def _build(self, **overrides):
        kwargs = dict(
            report=self.report,
            decision_id="test.decision.001",
            decision="accept",
            rationale="attempt-001 passed independent verification with all required checks.",
            decider_id="tester@example.com",
            decider_type="human",
            decider_display_name="Test Reviewer",
            selected_attempt_id="attempt-001",
            decided_at="2026-01-01T00:00:00Z",
        )
        kwargs.update(overrides)
        return MODULE.build_decision_record(**kwargs)

    def test_valid_recording_succeeds_and_validates_against_schema(self):
        record = self._build()
        # build_decision_record already schema-validates; assert again directly
        # against the schema file so the test does not just trust the builder.
        MODULE.validate_decision_record(record)
        self.assertEqual(record["kind"], "idkmesh-human-decision-record")
        self.assertEqual(record["schema_version"], "0.1")
        self.assertEqual(record["decision"], "accept")
        self.assertEqual(record["selected_attempt_id"], "attempt-001")
        self.assertEqual(record["evidence_report"]["run_id"], self.report["run_id"])
        self.assertEqual(record["evidence_report"]["digest"], canonical_digest(self.report))
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )

    def test_invalid_decision_value_is_rejected(self):
        with self.assertRaises(MODULE.HumanDecisionError):
            self._build(decision="approve")

    def test_machine_recommendation_value_is_not_a_valid_decision(self):
        # The point of this contract is an explicit human choice, not an echo
        # of the machine-suggested decision_support.recommendation vocabulary.
        with self.assertRaises(MODULE.HumanDecisionError):
            self._build(decision="accept_candidate")

    def test_unknown_selected_attempt_id_is_rejected(self):
        with self.assertRaises(MODULE.HumanDecisionError):
            self._build(selected_attempt_id="attempt-999")

    def test_empty_rationale_is_rejected(self):
        with self.assertRaises(MODULE.HumanDecisionError):
            self._build(rationale="   ")

    def test_empty_decider_id_is_rejected(self):
        with self.assertRaises(MODULE.HumanDecisionError):
            self._build(decider_id="")

    def test_run_level_decision_may_omit_selected_attempt(self):
        record = self._build(selected_attempt_id=None, decision="escalate")
        self.assertIsNone(record["selected_attempt_id"])
        MODULE.validate_decision_record(record)

    def test_verify_binding_accepts_the_exact_report_it_was_built_against(self):
        record = self._build()
        # Must not raise.
        MODULE.verify_binding(record, self.report)

    def test_verify_binding_detects_a_swapped_or_corrupted_evidence_report(self):
        record = self._build()
        tampered_report = copy.deepcopy(self.report)
        tampered_report["run_id"] += "-tampered"
        with self.assertRaises(MODULE.HumanDecisionError):
            MODULE.verify_binding(record, tampered_report)

    def test_verify_binding_detects_a_completely_different_report(self):
        record = self._build()
        failure_config = ROOT / "examples/orchestration/two-attempt-worker-failure.json"
        other_report = build_report(run_config(failure_config))
        with self.assertRaises(MODULE.HumanDecisionError):
            MODULE.verify_binding(record, other_report)

    def test_cli_record_then_verify_round_trips_through_files(self):
        import json
        import tempfile

        report_path = ROOT / "results" / "test-record-human-decision-report.json"
        output_path = ROOT / "results" / "test-record-human-decision-output.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(self.report, indent=2, sort_keys=True), encoding="utf-8")
        try:
            args = MODULE.build_parser().parse_args(
                [
                    "record",
                    "--evidence-report",
                    str(report_path.relative_to(ROOT)),
                    "--output",
                    str(output_path.relative_to(ROOT)),
                    "--decision-id",
                    "test.decision.cli.001",
                    "--decision",
                    "reject",
                    "--rationale",
                    "attempt-002 was independently rejected; nothing in this run is being integrated.",
                    "--decider-id",
                    "tester@example.com",
                    "--decided-at",
                    "2026-01-01T00:00:00Z",
                ]
            )
            self.assertEqual(args.func(args), 0)
            self.assertTrue(output_path.is_file())

            written = json.loads(output_path.read_text(encoding="utf-8"))
            MODULE.validate_decision_record(written)
            self.assertEqual(written["decision"], "reject")

            verify_args = MODULE.build_parser().parse_args(
                [
                    "verify",
                    "--decision-record",
                    str(output_path.relative_to(ROOT)),
                    "--evidence-report",
                    str(report_path.relative_to(ROOT)),
                ]
            )
            self.assertEqual(verify_args.func(verify_args), 0)

            # Corrupt the on-disk evidence report after the decision was
            # recorded: verification against the file must now fail closed.
            corrupted = json.loads(report_path.read_text(encoding="utf-8"))
            corrupted["run_id"] += "-corrupted"
            report_path.write_text(json.dumps(corrupted, indent=2, sort_keys=True), encoding="utf-8")
            with self.assertRaises(MODULE.HumanDecisionError):
                verify_args.func(verify_args)
        finally:
            report_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def test_cli_rejects_nonexistent_evidence_report(self):
        args = MODULE.build_parser().parse_args(
            [
                "record",
                "--evidence-report",
                "results/does-not-exist-for-test.json",
                "--output",
                "results/test-record-human-decision-never-written.json",
                "--decision-id",
                "test.decision.missing.001",
                "--decision",
                "accept",
                "--rationale",
                "x",
                "--decider-id",
                "tester@example.com",
            ]
        )
        with self.assertRaises(OSError):
            args.func(args)

    def test_self_test_cli_entry_point_passes(self):
        args = MODULE.build_parser().parse_args(["self-test"])
        self.assertEqual(args.func(args), 0)


if __name__ == "__main__":
    unittest.main()
