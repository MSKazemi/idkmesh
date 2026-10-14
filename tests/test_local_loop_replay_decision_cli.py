"""Fail-closed and delegation tests for ``idkmesh local-loop-replay`` and
``idkmesh local-loop-record-decision`` (refs #16).

Both verbs are thin wrappers over ``experiments/replay_run.py replay`` and
``experiments/record_human_decision.py record``. The success paths are
exercised end to end, against a real ``local-loop`` bundle, by
``tests/test_local_loop_tutorial.py`` (the commands the tutorial documents are
the commands that run). This file covers what that one cannot cheaply cover:
every refusal path, the delegation seam, and the drift guard between the CLI's
``--decision`` / ``--decider-type`` choices and the script's own constants.

Everything runs in-process through ``idkmesh.cli.main`` and uses the committed
bundle under ``results/orchestration/``, so no orchestration run is repeated:
the unit tier has a hard CPU budget. Class-based on purpose, because
``tests/test_documented_test_counts.py`` counts module-level ``test_*``
functions.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

if importlib.util.find_spec("jsonschema") is None:
    raise unittest.SkipTest(
        "local-loop replay/decision tests need the jsonschema dependency "
        "(experiments/local_verifier.py imports it directly)"
    )

from idkmesh import cli, local_loop  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPO_ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import record_human_decision  # noqa: E402

COMMITTED_BUNDLE = "results/orchestration/replay-fixture-evaluator-plan-good-vs-bad"
COMMITTED_REPORT = f"{COMMITTED_BUNDLE}/evidence-report.json"

DECISION_ARGS = [
    "--decision-id", "t.decision.001",
    "--decision", "accept",
    "--rationale", "r",
    "--decider-id", "tester",
]


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class ReplayRefusalTests(unittest.TestCase):
    def test_path_outside_the_repository_is_refused(self) -> None:
        code, out, err = _run(["local-loop-replay", "../replay-source.json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("escapes repository root", err)

    def test_mistyped_file_inside_a_real_bundle_is_not_replayed(self) -> None:
        code, out, err = _run(["local-loop-replay", f"{COMMITTED_BUNDLE}/replay-sourc.json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("not found", err)

    def test_directory_without_a_manifest_is_refused(self) -> None:
        code, out, err = _run(["local-loop-replay", "docs/README.md"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("not part of a captured replay bundle", err)


class RecordDecisionRefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (REPO_ROOT / "results").mkdir(exist_ok=True)
        cls.scratch = REPO_ROOT / "results" / f"local-loop-decision-cli-test-{uuid.uuid4().hex[:8]}"
        cls.scratch.mkdir()
        cls.addClassCleanup(shutil.rmtree, cls.scratch, ignore_errors=True)
        # A private copy, so a broken overwrite guard clobbers this file and
        # never the committed evidence report.
        cls.report = (cls.scratch / "evidence-report.json").relative_to(REPO_ROOT).as_posix()
        shutil.copyfile(REPO_ROOT / COMMITTED_REPORT, REPO_ROOT / cls.report)

    def _record(self, report: str, output: str) -> tuple[int, str, str]:
        return _run(["local-loop-record-decision", report, "--output", output, *DECISION_ARGS])

    def test_output_outside_results_is_refused_without_a_traceback(self) -> None:
        target = REPO_ROOT / "docs" / "local-loop-decision-cli-test-must-not-exist.json"
        self.addCleanup(target.unlink, missing_ok=True)  # never leave a stray file in docs/
        code, out, err = self._record(COMMITTED_REPORT, target.relative_to(REPO_ROOT).as_posix())
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("must be under results/", err)
        self.assertFalse(target.exists())

    def test_output_outside_the_repository_is_refused(self) -> None:
        code, out, err = self._record(COMMITTED_REPORT, "../decision.json")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("escapes repository root", err)

    def test_decision_record_may_not_overwrite_the_evidence_report(self) -> None:
        before = (REPO_ROOT / self.report).read_bytes()
        code, out, err = self._record(self.report, self.report)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("must not overwrite the evidence report", err)
        self.assertEqual((REPO_ROOT / self.report).read_bytes(), before)

    def test_missing_evidence_report_is_refused(self) -> None:
        output = (self.scratch / "never-written.json").relative_to(REPO_ROOT).as_posix()
        code, out, err = self._record(f"{self.scratch.relative_to(REPO_ROOT).as_posix()}/absent.json", output)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ERROR:", err)
        self.assertFalse((REPO_ROOT / output).exists())

    def test_unknown_decision_value_is_rejected_by_the_parser(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.build_parser().parse_args(
                ["local-loop-record-decision", COMMITTED_REPORT, "--output", "results/x.json",
                 "--decision-id", "d", "--decision", "accept_candidate",
                 "--rationale", "r", "--decider-id", "me"]
            )
        self.assertEqual(caught.exception.code, 2)


class DelegationSeamTests(unittest.TestCase):
    def test_cli_choices_equal_the_scripts_constants(self) -> None:
        self.assertEqual(set(cli._LOCAL_LOOP_DECISIONS), record_human_decision.KNOWN_DECISIONS)
        self.assertEqual(set(cli._LOCAL_LOOP_DECIDER_TYPES), record_human_decision.KNOWN_DECIDER_TYPES)

    def test_record_wrapper_passes_every_value_in_flag_equals_form(self) -> None:
        with mock.patch.object(record_human_decision, "main", return_value=0) as script_main:
            code = local_loop.record_decision(
                evidence_report="results/r/evidence-report.json",
                output="results/r/decision.json",
                decision_id="r.decision.001",
                decision="escalate",
                rationale="--looks like an option",
                decider_id="me",
            )
        self.assertEqual(code, 0)
        script_main.assert_called_once_with(
            [
                "record",
                "--evidence-report=results/r/evidence-report.json",
                "--output=results/r/decision.json",
                "--decision-id=r.decision.001",
                "--decision=escalate",
                "--rationale=--looks like an option",
                "--decider-id=me",
            ]
        )

    def test_record_wrapper_forwards_optional_values_only_when_given(self) -> None:
        with mock.patch.object(record_human_decision, "main", return_value=0) as script_main:
            local_loop.record_decision(
                evidence_report="a", output="b", decision_id="c", decision="accept",
                rationale="d", decider_id="e", decider_type="governance_body",
                decider_display_name="Board", selected_attempt_id="attempt-001",
                decided_at="2026-01-01T00:00:00Z",
            )
        argv = script_main.call_args.args[0]
        for expected in (
            "--decider-type=governance_body", "--decider-display-name=Board",
            "--selected-attempt-id=attempt-001", "--decided-at=2026-01-01T00:00:00Z",
        ):
            self.assertIn(expected, argv)

    def test_script_exit_code_is_returned_unchanged(self) -> None:
        with mock.patch.object(record_human_decision, "main", return_value=7):
            self.assertEqual(
                local_loop.record_decision(
                    evidence_report="a", output="b", decision_id="c", decision="accept",
                    rationale="d", decider_id="e"),
                7,
            )

    def test_outside_a_checkout_both_verbs_exit_2_with_the_setup_message(self) -> None:
        with (
            mock.patch.object(local_loop, "_experiments_cache", {}),
            mock.patch.object(local_loop, "_find_experiments_dir", return_value=None),
        ):
            replay = _run(["local-loop-replay", "results/x/replay-source.json"])
            record = _run(["local-loop-record-decision", "results/x/e.json",
                           "--output", "results/x/d.json", *DECISION_ARGS])
        for code, out, err in (replay, record):
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertIn("repository checkout", err)


if __name__ == "__main__":
    unittest.main()
