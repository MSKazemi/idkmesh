"""Real-run replay must catch a divergence and must not flag expected variance.

``experiments/replay_run.py`` replays the committed real bundle under
``results/orchestration/replay-fixture-evaluator-plan-good-vs-bad/`` (a real
WorkUnit -> two isolated real-patch attempts -> independent verification ->
evidence report run, produced by ``experiments/replay_run.py capture``; see
that directory's README.md) and compares it field by field against a fresh
re-run, partitioned into fields that must match exactly and fields that are
expected to differ (wall-clock timestamps, elapsed time, interpreter/platform
strings -- see the "Field classification" section of
``experiments/replay_run.py``'s module docstring).

A check that can only ever pass is not a regression test, so this module
exercises both directions on copies of the real captured bundle:

* a copy with an untouched must-match field still passing,
* a copy with a must-match field deliberately corrupted failing and naming
  the corrupted field,
* a copy with only expected-to-vary fields tampered still passing (proves the
  tool is not doing a blind byte-for-byte diff), and
* a copy whose config digest no longer matches (config drift) failing closed.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if importlib.util.find_spec("jsonschema") is None:
    raise unittest.SkipTest(
        "replay_run tests require the Phase 0 jsonschema dependency "
        "(experiments/local_verifier.py imports it directly)"
    )

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import replay_run  # noqa: E402

REAL_BUNDLE = ROOT / "results/orchestration/replay-fixture-evaluator-plan-good-vs-bad"
REAL_MANIFEST = REAL_BUNDLE / "replay-source.json"
SCRATCH_ROOT = ROOT / "results" / ".pytest-replay-run-scratch"


class ReplayRunTests(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.scratch_dir = Path(tempfile.mkdtemp(dir=SCRATCH_ROOT))
        self.addCleanup(shutil.rmtree, self.scratch_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)

    def _copy_bundle(self, name: str) -> Path:
        self.assertTrue(
            REAL_MANIFEST.is_file(),
            f"{REAL_MANIFEST} is missing; run "
            "`python experiments/replay_run.py capture --config "
            "examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json "
            f"--output-dir {REAL_BUNDLE.relative_to(ROOT)}` first",
        )
        target = self.scratch_dir / name
        shutil.copytree(REAL_BUNDLE, target)
        return target

    # -- positive case ----------------------------------------------------

    def test_replay_reproduces_the_real_captured_bundle(self) -> None:
        report = replay_run.replay_bundle(REAL_MANIFEST)
        self.assertTrue(report.ok, replay_run.format_report(report))
        self.assertFalse(report.config_drifted)
        labels = {c.label for c in report.comparisons}
        self.assertEqual(
            labels,
            {
                "run-record",
                "evidence-report",
                "verification-result[attempt-001]",
                "verification-result[attempt-002]",
            },
        )
        for comparison in report.comparisons:
            self.assertEqual(comparison.must_match_diffs, [], comparison.label)
        # The raw per-attempt VerificationResult sidecars really do carry
        # non-deterministic fields on a fresh re-run; if this list were ever
        # empty the "expected-to-vary" classification would be untested.
        attempt_comparisons = [
            c for c in report.comparisons if c.label.startswith("verification-result[")
        ]
        for comparison in attempt_comparisons:
            self.assertEqual(sorted(comparison.ignored_present), [
                "$['finished_at']",
                "$['provenance']['environment']['platform']",
                "$['provenance']['environment']['python']",
                "$['resources']['wall_seconds']",
                "$['started_at']",
            ])

    # -- negative case: a must-match field is corrupted --------------------

    def test_replay_detects_a_corrupted_must_match_field(self) -> None:
        bundle = self._copy_bundle("corrupted")
        sidecar = bundle / "verification-result-attempt-001.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "passed")  # sanity: real fixture value before tamper
        data["status"] = "failed"
        data["decision_support"]["recommendation"] = "reject_candidate"
        sidecar.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        report = replay_run.replay_bundle(bundle / "replay-source.json")

        self.assertFalse(report.ok)
        attempt_1 = next(
            c for c in report.comparisons if c.label == "verification-result[attempt-001]"
        )
        self.assertFalse(attempt_1.ok)
        diff_paths = {d.path for d in attempt_1.must_match_diffs}
        self.assertIn("$['status']", diff_paths)
        self.assertIn("$['decision_support']['recommendation']", diff_paths)
        # attempt-002 was not touched and the aggregate layers are unaffected
        # by a raw sidecar's content (they only store the projected summary),
        # so both must still report clean.
        attempt_2 = next(
            c for c in report.comparisons if c.label == "verification-result[attempt-002]"
        )
        self.assertTrue(attempt_2.ok)
        run_record_comparison = next(c for c in report.comparisons if c.label == "run-record")
        self.assertTrue(run_record_comparison.ok)

    # -- expected-to-vary fields must never fail replay --------------------

    def test_replay_ignores_expected_to_vary_fields(self) -> None:
        bundle = self._copy_bundle("volatile-only")
        sidecar = bundle / "verification-result-attempt-002.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["started_at"] = "1999-01-01T00:00:00Z"
        data["finished_at"] = "1999-01-01T00:00:05Z"
        data["resources"]["wall_seconds"] = 999.0
        data["provenance"]["environment"]["platform"] = "some-other-machine"
        data["provenance"]["environment"]["python"] = "9.9.9"
        sidecar.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        report = replay_run.replay_bundle(bundle / "replay-source.json")

        self.assertTrue(report.ok, replay_run.format_report(report))

    # -- fail closed on a mismatched replay path (missing sidecar entry) --

    def test_replay_fails_closed_if_a_saved_verification_result_is_absent_on_replay(
        self,
    ) -> None:
        bundle = self._copy_bundle("missing-attempt")
        manifest_path = bundle / "replay-source.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["verification_results"]["attempt-003-does-not-exist"] = (
            "verification-result-attempt-001.json"
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        with self.assertRaises(replay_run.ReplayError):
            replay_run.replay_bundle(manifest_path)

    # -- config drift is itself a replay failure ---------------------------

    def test_replay_fails_closed_on_config_digest_drift(self) -> None:
        bundle = self._copy_bundle("drifted-config")
        manifest_path = bundle / "replay-source.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["config_digest"] = "sha256:" + "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        report = replay_run.replay_bundle(manifest_path)

        self.assertTrue(report.config_drifted)
        self.assertFalse(report.ok)
        self.assertEqual(report.comparisons, [])

    # -- CLI exit codes ------------------------------------------------------

    def test_cli_exit_codes_match_success_and_failure(self) -> None:
        ok = subprocess.run(
            [sys.executable, str(EXPERIMENTS / "replay_run.py"), "replay", "--bundle", str(REAL_MANIFEST)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("PASS", ok.stdout)

        bundle = self._copy_bundle("cli-corrupted")
        sidecar = bundle / "verification-result-attempt-001.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["status"] = "failed"
        sidecar.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        failing = subprocess.run(
            [
                sys.executable,
                str(EXPERIMENTS / "replay_run.py"),
                "replay",
                "--bundle",
                str(bundle / "replay-source.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(failing.returncode, 1, failing.stdout + failing.stderr)
        self.assertIn("FAIL", failing.stdout)
        self.assertIn("$['status']", failing.stdout)


if __name__ == "__main__":
    unittest.main()
