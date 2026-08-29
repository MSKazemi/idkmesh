from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
CALIBRATION_WORKFLOWS = tuple(
    ROOT / ".github/workflows" / f"phase-b2-v2-task{number:03d}-calibration.yml"
    for number in range(1, 6)
)


class PhaseB2WorkflowLifecycleTests(unittest.TestCase):
    def test_completed_calibration_does_not_leave_one_shot_ci_active(self) -> None:
        cohort = json.loads(COHORT.read_text(encoding="utf-8"))
        lifecycle = cohort["extensions"]["org.idkmesh.phase_b2_v2"]
        self.assertTrue(lifecycle["freeze_ready"])
        self.assertEqual(lifecycle["calibration_pending_task_ids"], [])
        self.assertEqual(len(lifecycle["calibration_completed"]), 5)
        novelty = lifecycle["pre_freeze_novelty_audit"]
        self.assertEqual(novelty["status"], "failed")
        self.assertFalse(novelty["freeze_allowed"])
        self.assertEqual(
            set(novelty["exposed_task_ids"]),
            {task["id"] for task in cohort["tasks"]},
        )
        report = json.loads((ROOT / novelty["report_path"]).read_text(encoding="utf-8"))
        self.assertEqual(report["audited_revision"], novelty["audited_revision"])
        self.assertFalse(report["summary"]["freeze_allowed"])
        self.assertEqual(report["summary"]["exposed_tasks"], 5)
        self.assertEqual({task["status"] for task in report["tasks"]}, {"solution_public"})
        self.assertEqual(
            {task["task_id"] for task in report["tasks"]},
            {task["id"] for task in cohort["tasks"]},
        )
        for task in report["tasks"]:
            self.assertTrue((ROOT / task["calibration_script"]).is_file())
            self.assertTrue((ROOT / task["evidence_report"]).is_file())
        self.assertTrue(all(not workflow.exists() for workflow in CALIBRATION_WORKFLOWS))


if __name__ == "__main__":
    unittest.main()
