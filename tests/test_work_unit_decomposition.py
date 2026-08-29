from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from experiments.work_unit_decomposition import (
    BenchmarkError,
    JSONSCHEMA_AVAILABLE,
    run_benchmark,
    serialize_report,
    validate_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/benchmarks/work-unit-decomposition-v0.1.json"


@unittest.skipUnless(
    JSONSCHEMA_AVAILABLE,
    "Work Unit decomposition tests require requirements-phase0.txt",
)
class WorkUnitDecompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_covers_five_strategies_and_formal_work_units(self) -> None:
        report = run_benchmark(self.benchmark)

        self.assertEqual(report["evidence_class"], "synthetic_fixture")
        self.assertNotIn("scientific_claim_allowed", report)
        self.assertEqual(
            set(report["arms"]),
            {
                "monolithic",
                "human_subtasks",
                "file_module",
                "dependency_dag",
                "formal_work_units",
            },
        )
        formal = report["arms"]["formal_work_units"]
        self.assertEqual(formal["unit_count"], 4)
        self.assertEqual(formal["completion_success_rate"], 1.0)
        self.assertEqual(formal["hidden_test_success_rate"], 1.0)
        self.assertEqual(formal["executable_without_global_context_rate"], 1.0)

        graph = report["formal_task_evidence_dag"]
        self.assertIn(
            {
                "source": "issue15/example/coding",
                "target": "issue15/example/research",
                "relation": "requires",
            },
            graph["edges"],
        )
        self.assertTrue(
            any(edge["relation"] == "requires_evidence" for edge in graph["edges"])
        )

    def test_report_is_byte_deterministic_under_input_reordering(self) -> None:
        expected = serialize_report(run_benchmark(self.benchmark))
        shuffled = copy.deepcopy(self.benchmark)
        shuffled["arms"].reverse()
        for arm in shuffled["arms"]:
            arm["units"].reverse()
            arm["observations"].reverse()

        self.assertEqual(serialize_report(run_benchmark(shuffled)), expected)

    def test_unknown_dependency_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.benchmark)
        invalid["arms"][0]["units"][0]["dependencies"] = ["missing"]

        with self.assertRaisesRegex(BenchmarkError, "unknown dependencies"):
            validate_benchmark(invalid)

    def test_cycle_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.benchmark)
        arm = next(
            item for item in invalid["arms"] if item["strategy"] == "human_subtasks"
        )
        arm["units"][0]["dependencies"] = ["human/review"]

        with self.assertRaisesRegex(BenchmarkError, "dependency cycle"):
            validate_benchmark(invalid)

    def test_formal_arm_must_match_work_unit_dependencies(self) -> None:
        invalid = copy.deepcopy(self.benchmark)
        arm = next(
            item for item in invalid["arms"] if item["strategy"] == "formal_work_units"
        )
        arm["units"][1]["dependencies"] = []

        with self.assertRaisesRegex(BenchmarkError, "requires dependencies do not match"):
            validate_benchmark(invalid)

    def test_observation_coverage_and_metric_bounds_fail_closed(self) -> None:
        missing = copy.deepcopy(self.benchmark)
        missing["arms"][0]["observations"] = []
        with self.assertRaisesRegex(BenchmarkError, "schema validation failed"):
            validate_benchmark(missing)

        impossible = copy.deepcopy(self.benchmark)
        impossible["arms"][0]["observations"][0]["hidden_tests_passed"] = 6
        with self.assertRaisesRegex(BenchmarkError, "cannot exceed"):
            validate_benchmark(impossible)

    def test_attempt_and_worker_provenance_fail_closed(self) -> None:
        unknown_worker = copy.deepcopy(self.benchmark)
        unknown_worker["arms"][0]["observations"][0]["worker_id"] = "unknown"
        with self.assertRaisesRegex(BenchmarkError, "unknown workers"):
            validate_benchmark(unknown_worker)

        duplicate_attempt = copy.deepcopy(self.benchmark)
        first = duplicate_attempt["arms"][0]["observations"][0]["attempt_id"]
        duplicate_attempt["arms"][1]["observations"][0]["attempt_id"] = first
        with self.assertRaisesRegex(BenchmarkError, "duplicate attempt id"):
            validate_benchmark(duplicate_attempt)

    def test_cli_writes_same_report(self) -> None:
        expected = serialize_report(run_benchmark(self.benchmark), pretty=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "experiments/work_unit_decomposition.py",
                    str(FIXTURE),
                    "--pretty",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
