import json
from pathlib import Path
import sys
import unittest

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        "Phase B2 Task 004 evidence tests require requirements-phase0.txt"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "experiments", ROOT / "tools"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import evaluator_plan_runner  # noqa: E402
import benchmark_cohort  # noqa: E402
import phase_b2_successor_task004_evidence as task004  # noqa: E402

EVIDENCE = ROOT / "results/benchmarks/phase-b2-successor-five/task-004/attempt-001"


class PhaseB2SuccessorTask004EvidenceTests(unittest.TestCase):
    def test_unsafe_path_classifier_requires_expected_diagnostic(self) -> None:
        class Result:
            returncode = 2
            stderr = "ERROR: BenchmarkCohort: unsafe path '/tmp/outside.json'\n"

        self.assertTrue(task004.rejects_unsafe_path(Result()))
        Result.returncode = 0
        self.assertFalse(task004.rejects_unsafe_path(Result()))
        Result.returncode = 2
        Result.stderr = "ERROR: unrelated\n"
        self.assertFalse(task004.rejects_unsafe_path(Result()))

    def test_committed_evidence_replays_through_frozen_plan(self) -> None:
        result = json.loads((EVIDENCE / "result-manifest.json").read_text(encoding="utf-8"))
        expected = json.loads((EVIDENCE / "verification-result.json").read_text(encoding="utf-8"))
        observed = evaluator_plan_runner.run_fixture(
            work_unit_path=task004.WORK_UNIT_PATH,
            result_manifest_path=EVIDENCE / "result-manifest.json",
            candidate_root=EVIDENCE,
            plan_path=task004.PLAN_PATH,
        )
        for value in (observed, expected):
            value["started_at"] = "<runtime>"
            value["finished_at"] = "<runtime>"
            value["resources"]["wall_seconds"] = 0.0
            value["provenance"]["environment"] = {"runtime": "normalized"}
        self.assertEqual(observed, expected)
        self.assertEqual(observed["status"], "passed")
        self.assertEqual(observed["decision_support"]["recommendation"], "accept_candidate")
        self.assertEqual(observed["result_manifest_id"], result["id"])

    def test_active_cohort_retains_task004_without_digest_drift(self) -> None:
        cohort = benchmark_cohort.load_json(task004.COHORT_PATH)
        summary = benchmark_cohort.validate_cohort(cohort)
        task = next(item for item in cohort["tasks"] if item["id"] == task004.TASK_ID)
        self.assertEqual(task["evidence"]["status"], "verified")
        self.assertEqual(
            summary["definition_digest"],
            "sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9",
        )


if __name__ == "__main__":
    unittest.main()
