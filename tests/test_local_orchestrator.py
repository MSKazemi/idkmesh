from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from local_orchestrator import (  # noqa: E402
    OrchestratorError,
    run_orchestration,
    semantic_signature,
)

WORK_UNIT = ROOT / "examples/work-units/orchestrator-smoke.work-unit.json"
POLICY = ROOT / "verification/fixtures/verifier-smoke-policy.json"


class LocalOrchestratorTests(unittest.TestCase):
    def _run(self, base: Path, run_id: str, scenario: str):
        return run_orchestration(
            output_base=base,
            run_id=run_id,
            scenario=scenario,
            work_unit_path=WORK_UNIT,
            policy_path=POLICY,
            allow_external_output=True,
        )

    def test_good_and_bad_candidates_preserve_independent_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report, run_root = self._run(Path(tmp), "test-good-bad", "good-bad")

            self.assertEqual(report["attempt_order"], [1, 2])
            self.assertEqual(len(report["attempts"]), 2)
            good, bad = report["attempts"]

            self.assertEqual(good["worker_status"], "succeeded")
            self.assertEqual(good["verification_status"], "passed")
            self.assertEqual(good["recommendation"], "accept_candidate")

            self.assertEqual(bad["worker_status"], "succeeded")
            self.assertEqual(bad["verification_status"], "failed")
            self.assertEqual(bad["recommendation"], "reject_candidate")

            self.assertFalse(report["integration"]["automatic_integration"])
            self.assertIsNone(report["integration"]["decision"])

            for attempt in (good, bad):
                result_path = run_root / attempt["result_manifest"]
                verification_path = run_root / attempt["verification_result"]
                self.assertTrue(result_path.is_file())
                self.assertTrue(verification_path.is_file())

                result = json.loads(result_path.read_text(encoding="utf-8"))
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
                self.assertEqual(verification["result_manifest_id"], result["id"])
                self.assertEqual(verification["attempt"], result["attempt"])
                self.assertEqual(verification["work_unit_id"], result["work_unit_id"])

    def test_replay_preserves_semantic_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first, _ = self._run(base / "a", "test-replay", "good-bad")
            second, _ = self._run(base / "b", "test-replay", "good-bad")
            self.assertEqual(semantic_signature(first), semantic_signature(second))
            self.assertEqual(first["semantic_signature"], second["semantic_signature"])

    def test_worker_error_does_not_abort_healthy_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report, _ = self._run(Path(tmp), "test-good-error", "good-error")
            self.assertEqual(len(report["attempts"]), 2)
            healthy, failed = report["attempts"]

            self.assertEqual(healthy["worker_status"], "succeeded")
            self.assertEqual(healthy["verification_status"], "passed")
            self.assertEqual(failed["worker_status"], "error")
            self.assertEqual(failed["verification_status"], "not_run")
            self.assertEqual(failed["error"], "fixture-worker-error")

    def test_cleanup_refuses_unowned_existing_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_root = base / "unsafe-existing"
            run_root.mkdir()
            (run_root / "unrelated.txt").write_text("do not delete\n", encoding="utf-8")

            with self.assertRaises(OrchestratorError):
                self._run(base, "unsafe-existing", "good-bad")
            self.assertTrue((run_root / "unrelated.txt").is_file())

    def test_owned_workspace_can_be_replayed_without_touching_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sentinel = base / "parent-sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            first, first_root = self._run(base, "owned-replay", "good-bad")
            second, second_root = self._run(base, "owned-replay", "good-bad")

            self.assertEqual(first_root, second_root)
            self.assertEqual(semantic_signature(first), semantic_signature(second))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")


if __name__ == "__main__":
    unittest.main()
