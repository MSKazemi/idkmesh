from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        "patch evaluator safety tests require the Phase 0 jsonschema dependency"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402

WORK_UNIT = ROOT / "examples/work-units/patch-verifier-smoke.work-unit.json"
PLAN = ROOT / "verification/fixtures/patch-smoke-evaluator-plan-v0.2.json"
GOOD_ROOT = ROOT / "examples/verifier/patch/good"


class PatchEvaluatorSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = local_verifier.load_json(WORK_UNIT)
        cls.plan = evaluator_plan_runner.load_plan(PLAN)
        cls.good_worker = local_verifier.load_json(GOOD_ROOT / "result-manifest.json")

    def verify(self, worker: dict) -> dict:
        return evaluator_plan_runner.verify_with_plan(
            work_unit=self.work_unit,
            worker_result=worker,
            plan=self.plan,
            candidate_root=GOOD_ROOT,
            plan_path=PLAN,
        )

    def test_known_good_fixture_still_passes(self) -> None:
        result = self.verify(copy.deepcopy(self.good_worker))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verifier"]["adapter_version"], "0.1.1")

    def test_required_semantic_text_outside_hunk_is_rejected(self) -> None:
        malicious = "\n".join(
            [
                "diff --git a/README.md b/README.md",
                "index 1111111..2222222 100644",
                "--- a/README.md",
                "+++ b/README.md",
                "+<!-- patch-evaluator expected -->",
                "",
            ]
        )
        with self.assertRaisesRegex(local_verifier.VerifierError, "hunk|unexpected content"):
            local_verifier.parse_unified_diff(malicious)

    def test_hunk_line_counts_must_balance(self) -> None:
        malformed = "\n".join(
            [
                "diff --git a/README.md b/README.md",
                "index 1111111..2222222 100644",
                "--- a/README.md",
                "+++ b/README.md",
                "@@ -1 +1 @@",
                "-# IDKMesh",
                "+<!-- patch-evaluator expected -->",
                "+extra undeclared line",
                "",
            ]
        )
        with self.assertRaisesRegex(local_verifier.VerifierError, "line counts|exceeded"):
            local_verifier.parse_unified_diff(malformed)

    def test_missing_required_logs_fail_closed(self) -> None:
        worker = copy.deepcopy(self.good_worker)
        worker["logs"] = []
        result = self.verify(worker)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(
            any(
                finding["category"] == "provenance"
                and "logs" in finding["summary"].lower()
                for finding in result["findings"]
            )
        )
        diagnostics = json.loads(
            next(check for check in result["checks"] if check["id"] == "independent-review")[
                "diagnostics"
            ]
        )
        self.assertEqual(
            diagnostics["logs"]["coverage_violations"],
            ["required log type missing: stdout", "required log type missing: stderr"],
        )

    def test_missing_log_digest_is_rejection_not_crash(self) -> None:
        worker = copy.deepcopy(self.good_worker)
        worker["logs"][0].pop("digest")
        result = self.verify(worker)
        self.assertEqual(result["status"], "failed")
        diagnostics = json.loads(
            next(check for check in result["checks"] if check["id"] == "independent-review")[
                "diagnostics"
            ]
        )
        self.assertEqual(
            diagnostics["logs"]["logs"][0]["error"],
            "log digest is required by evaluator policy",
        )

    def test_duplicate_required_log_type_fails_closed(self) -> None:
        worker = copy.deepcopy(self.good_worker)
        duplicate = copy.deepcopy(worker["logs"][0])
        duplicate["locator"] = worker["logs"][1]["locator"]
        worker["logs"][1] = duplicate
        result = self.verify(worker)
        self.assertEqual(result["status"], "failed")
        diagnostics = json.loads(
            next(check for check in result["checks"] if check["id"] == "independent-review")[
                "diagnostics"
            ]
        )
        self.assertIn(
            "required log type must appear exactly once: stdout (observed 2)",
            diagnostics["logs"]["coverage_violations"],
        )
        self.assertIn(
            "required log type missing: stderr",
            diagnostics["logs"]["coverage_violations"],
        )


if __name__ == "__main__":
    unittest.main()
