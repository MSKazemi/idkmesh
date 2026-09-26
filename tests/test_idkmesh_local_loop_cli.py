"""End-to-end tests for the ``idkmesh local-loop`` product surface.

``idkmesh local-loop`` (``idkmesh/cli.py`` + ``idkmesh/local_loop.py``) is
the first CLI command wiring ROADMAP.md S4's R1 local product loop end to
end: WorkUnit -> two isolated attempts -> independent verification ->
evidence report -> (manual) replay/decision. These tests invoke the real
installed console script's entry point as a subprocess against real
fixtures under ``examples/orchestration/`` -- not mocks -- and load the
produced evidence bundle back with ``experiments/run_evidence_report.py``'s
own validator, so a regression that produces a schema-invalid or unbound
report fails here, not only in ``idkmesh local-loop``'s own eyes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if not HAS_JSONSCHEMA:
    raise unittest.SkipTest(
        "idkmesh local-loop tests require the Phase 0 jsonschema dependency "
        "(experiments/local_verifier.py imports it directly)"
    )

EXPERIMENTS = REPO_ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import run_evidence_report  # noqa: E402

GOOD_VS_BAD_CONFIG = "examples/orchestration/two-attempt-good-vs-bad.json"
EVALUATOR_PLAN_CONFIG = (
    "examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json"
)
WORKER_FAILURE_CONFIG = "examples/orchestration/two-attempt-worker-failure.json"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "idkmesh.cli", *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
    )


class LocalLoopCliEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=REPO_ROOT / "results")
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = (
            Path(self._tmp.name).relative_to(REPO_ROOT).as_posix()
            + "/bundle"
        )

    def test_local_loop_produces_a_valid_evidence_bundle_for_a_real_patch_run(self):
        """A real WorkUnit + two real unified-diff attempts, end to end."""

        proc = run_cli(
            "local-loop", EVALUATOR_PLAN_CONFIG, "--output-dir", self.output_dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        output_dir = REPO_ROOT / self.output_dir
        report_path = output_dir / "evidence-report.json"
        record_path = output_dir / "run-record.json"
        markdown_path = output_dir / "evidence-report.md"
        replay_source_path = output_dir / "replay-source.json"
        next_steps_path = output_dir / "NEXT_STEPS.md"

        for path in (
            report_path, record_path, markdown_path, replay_source_path,
            next_steps_path,
        ):
            self.assertTrue(path.is_file(), f"missing {path}")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        record = json.loads(record_path.read_text(encoding="utf-8"))

        # The load-bearing assertion: the produced report is a real,
        # schema/invariant-valid idkmesh-run-evidence-report bound to the
        # exact run record `idkmesh local-loop` also wrote, not merely "some
        # JSON was written". This is the same validator
        # experiments/record_human_decision.py trusts before recording a
        # decision against a report.
        run_evidence_report.validate_report(report, source_record=record)

        self.assertEqual(report["run_id"], "two-attempt-evaluator-plan-good-vs-bad")
        self.assertEqual(report["work_unit"]["id"], "verification/patch-smoke")
        # This fixture's two attempts are a known-good and a known-bad patch
        # (see examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json);
        # independent verification is expected to disagree on them.
        self.assertEqual(report["summary"]["supported"], 1)
        self.assertEqual(report["summary"]["rejected"], 1)
        self.assertTrue(report["summary"]["verification_disagreement"])
        # Never selects a candidate or claims write/merge authority.
        self.assertIsNone(report["human_decision"]["selected_attempt_id"])
        self.assertFalse(report["authority"]["automatic_candidate_selection"])

        markdown = markdown_path.read_text(encoding="utf-8")
        self.assertIn("attempt-001", markdown)
        self.assertIn("attempt-002", markdown)

        next_steps = next_steps_path.read_text(encoding="utf-8")
        self.assertIn("record_human_decision.py", next_steps)
        self.assertIn("replay_run.py replay", next_steps)
        self.assertIn(str(report_path.relative_to(REPO_ROOT)), next_steps)

        # The printed stdout summary is the same content saved to disk.
        self.assertIn("record_human_decision.py", proc.stdout)
        self.assertIn("replay_run.py replay", proc.stdout)
        self.assertIn("Supported: 1", proc.stdout)

        # The evidence bundle idkmesh local-loop just produced actually
        # replays, using the exact command it itself printed as next steps.
        replay = subprocess.run(
            [sys.executable, "experiments/replay_run.py", "replay",
             "--bundle", str(replay_source_path.relative_to(REPO_ROOT))],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertIn("PASS", replay.stdout)

        # And a human decision can really be recorded against it, using the
        # exact command idkmesh local-loop printed.
        decision_path = output_dir / "human-decision-record.json"
        record_decision = subprocess.run(
            [sys.executable, "experiments/record_human_decision.py", "record",
             "--evidence-report", str(report_path.relative_to(REPO_ROOT)),
             "--output", str(decision_path.relative_to(REPO_ROOT)),
             "--decision-id", "test.decision.001",
             "--decision", "accept",
             "--rationale", "test: attempt-001 was independently accepted",
             "--decider-id", "test-suite"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        self.assertEqual(record_decision.returncode, 0, record_decision.stderr)
        self.assertTrue(decision_path.is_file())

    def test_local_loop_on_legacy_verifier_policy_config_also_produces_a_report(self):
        proc = run_cli("local-loop", GOOD_VS_BAD_CONFIG, "--output-dir", self.output_dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(
            (REPO_ROOT / self.output_dir / "evidence-report.json")
            .read_text(encoding="utf-8")
        )
        run_evidence_report.validate_report(report)
        self.assertEqual(report["summary"]["supported"], 1)
        self.assertEqual(report["summary"]["rejected"], 1)

    def test_local_loop_preserves_a_worker_control_failure_rather_than_hiding_it(self):
        proc = run_cli(
            "local-loop", WORKER_FAILURE_CONFIG, "--output-dir", self.output_dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(
            (REPO_ROOT / self.output_dir / "evidence-report.json")
            .read_text(encoding="utf-8")
        )
        run_evidence_report.validate_report(report)
        self.assertEqual(report["summary"]["control_errors"], 1)
        self.assertEqual(report["summary"]["supported"], 1)

    def test_local_loop_refuses_to_overwrite_a_non_empty_output_dir(self):
        proc = run_cli("local-loop", GOOD_VS_BAD_CONFIG, "--output-dir", self.output_dir)
        self.assertEqual(proc.returncode, 0, proc.stderr)

        second = run_cli("local-loop", GOOD_VS_BAD_CONFIG, "--output-dir", self.output_dir)
        self.assertEqual(second.returncode, 2)
        self.assertIn("already exists and is not empty", second.stderr)

    def test_local_loop_missing_config_exits_2_with_a_clear_message(self):
        proc = run_cli("local-loop", "examples/orchestration/does-not-exist.json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not found", proc.stderr)

    def test_local_loop_malformed_config_exits_2_naming_the_missing_fields(self):
        # Must live inside the repository: resolve_repo_path() refuses any
        # path outside it before validate_config ever runs, and that guard
        # is exercised separately below.
        bad = Path(self._tmp.name) / "bad-orchestration-config.json"
        bad.write_text(json.dumps({"schema_version": "0.1"}), encoding="utf-8")
        proc = run_cli("local-loop", str(bad.relative_to(REPO_ROOT)))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("attempts", proc.stderr)

    def test_local_loop_config_outside_repository_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "orchestration-config.json"
            outside.write_text(json.dumps({"schema_version": "0.1"}), encoding="utf-8")
            proc = run_cli("local-loop", str(outside))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("escapes repository root", proc.stderr)

    def test_local_loop_output_dir_must_stay_under_results(self):
        proc = run_cli(
            "local-loop", GOOD_VS_BAD_CONFIG, "--output-dir", "not-results/escape")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("results", proc.stderr)


class LocalLoopCliHelpTests(unittest.TestCase):
    def test_local_loop_is_listed_alongside_gate_audit(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("gate-audit", proc.stdout)
        self.assertIn("local-loop", proc.stdout)

    def test_local_loop_help_names_the_verify_extra_and_next_steps(self):
        proc = run_cli("local-loop", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("idkmesh[verify]", proc.stdout)
        self.assertIn("record_human_decision.py", proc.stdout)
        self.assertIn("replay_run.py", proc.stdout)


if __name__ == "__main__":
    unittest.main()
