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
        self.assertTrue(all(not workflow.exists() for workflow in CALIBRATION_WORKFLOWS))


if __name__ == "__main__":
    unittest.main()
