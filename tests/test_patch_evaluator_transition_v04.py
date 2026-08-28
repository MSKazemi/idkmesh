from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        "transition evaluator tests require the Phase 0 jsonschema dependency"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402

WORK_UNIT = ROOT / "examples/work-units/patch-verifier-smoke.work-unit.json"
BASE_WORKER = ROOT / "examples/verifier/patch/good/result-manifest.json"
PLAN_V04 = ROOT / "verification/fixtures/patch-transition-evaluator-plan-v0.4.json"
CORRECT_PATCH = ROOT / "verification/fixtures/patch-transition/correct.patch"
DECOY_PATCH = ROOT / "verification/fixtures/patch-transition/decoy.patch"


class PatchEvaluatorTransitionV04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = local_verifier.load_json(WORK_UNIT)
        cls.base_worker = local_verifier.load_json(BASE_WORKER)
        cls.plan_v04 = evaluator_plan_runner.load_plan(PLAN_V04)

    def plan_v03(self) -> dict:
        plan = copy.deepcopy(self.plan_v04)
        plan["schema_version"] = "0.3"
        plan["id"] = "verification/patch-transition-plan-v03-calibration"
        plan["verifier"]["adapter_version"] = "0.2.0"
        plan["backend"].pop("required_removed_substrings")
        return plan

    def plan_v02(self) -> dict:
        plan = self.plan_v03()
        plan["schema_version"] = "0.2"
        plan["id"] = "verification/patch-transition-plan-v02-calibration"
        plan["verifier"]["adapter_version"] = "0.1.1"
        added = plan["backend"].pop("required_added_substrings")
        plan["backend"]["required_added_text"] = added
        return plan

    def make_candidate(self, root: Path, patch: bytes, label: str) -> dict:
        stdout = f"transition semantic fixture: {label}\n".encode("utf-8")
        stderr = b""
        (root / "changes.patch").write_bytes(patch)
        (root / "stdout.txt").write_bytes(stdout)
        (root / "stderr.txt").write_bytes(stderr)

        worker = copy.deepcopy(self.base_worker)
        worker["id"] = f"verification/patch-smoke/{label}-attempt-1"
        worker["extensions"] = {"org.idkmesh.transition_fixture": {"kind": label}}
        worker["produced_artifacts"][0]["digest"] = local_verifier.sha256_bytes(patch)
        worker["logs"][0]["digest"] = local_verifier.sha256_bytes(stdout)
        worker["logs"][1]["digest"] = local_verifier.sha256_bytes(stderr)
        return worker

    def verify(self, *, plan: dict, patch_path: Path, label: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="idkmesh-transition-v04-") as raw:
            root = Path(raw)
            worker = self.make_candidate(root, patch_path.read_bytes(), label)
            return evaluator_plan_runner.verify_with_plan(
                work_unit=self.work_unit,
                worker_result=worker,
                plan=plan,
                candidate_root=root,
                plan_path=PLAN_V04,
            )

    @staticmethod
    def evidence_digest(result: dict, evidence_id: str) -> str:
        matches = [
            evidence["digest"]
            for evidence in result["evidence"]
            if evidence["id"] == evidence_id
        ]
        if len(matches) != 1:
            raise AssertionError(f"expected exactly one evidence item {evidence_id!r}")
        return matches[0]

    @staticmethod
    def independent_diagnostics(result: dict) -> dict:
        check = next(
            check for check in result["checks"] if check["id"] == "independent-review"
        )
        return json.loads(check["diagnostics"])

    def test_same_correct_patch_exposes_version_boundary(self) -> None:
        legacy = self.verify(
            plan=self.plan_v02(),
            patch_path=CORRECT_PATCH,
            label="correct-v02",
        )
        substring = self.verify(
            plan=self.plan_v03(),
            patch_path=CORRECT_PATCH,
            label="correct-v03",
        )
        transition = self.verify(
            plan=self.plan_v04,
            patch_path=CORRECT_PATCH,
            label="correct-v04",
        )

        self.assertEqual(legacy["status"], "failed")
        self.assertEqual(legacy["verifier"]["adapter_version"], "0.1.1")
        self.assertEqual(legacy["decision_support"]["recommendation"], "reject_candidate")

        self.assertEqual(substring["status"], "passed")
        self.assertEqual(substring["verifier"]["adapter_version"], "0.2.0")
        self.assertEqual(substring["decision_support"]["recommendation"], "accept_candidate")

        self.assertEqual(transition["status"], "passed")
        self.assertEqual(transition["verifier"]["adapter_version"], "0.3.0")
        self.assertEqual(transition["decision_support"]["recommendation"], "accept_candidate")
        self.assertEqual(
            transition["extensions"]["org.idkmesh.local_verifier.semantic_match_mode"],
            "added_and_removed_line_substring_all",
        )
        self.assertEqual(
            transition["provenance"]["verifier_config_digest"],
            local_verifier.canonical_digest(self.plan_v04),
        )

        digests = {
            self.evidence_digest(result, "candidate-patch-hash")
            for result in (legacy, substring, transition)
        }
        self.assertEqual(len(digests), 1, "version matrix did not evaluate identical patch bytes")

        diagnostics = self.independent_diagnostics(transition)
        self.assertEqual(
            diagnostics["semantic_removed_substrings"]["missing_substrings"],
            [],
        )
        self.assertEqual(
            diagnostics["semantic_removed_substrings"]["observed_removed_lines"],
            ["unsafe_call(args.value)"],
        )

    def test_v03_accepts_goodhart_decoy_but_v04_rejects_it(self) -> None:
        substring = self.verify(
            plan=self.plan_v03(),
            patch_path=DECOY_PATCH,
            label="decoy-v03",
        )
        transition = self.verify(
            plan=self.plan_v04,
            patch_path=DECOY_PATCH,
            label="decoy-v04",
        )

        # Preserve the calibration result discovered after v0.3 was merged:
        # added-substring presence alone can be satisfied by an inert mention.
        self.assertEqual(substring["status"], "passed")
        self.assertEqual(substring["decision_support"]["recommendation"], "accept_candidate")

        self.assertEqual(transition["status"], "failed")
        self.assertEqual(transition["decision_support"]["recommendation"], "reject_candidate")
        self.assertEqual(transition["verifier"]["adapter_version"], "0.3.0")
        diagnostics = self.independent_diagnostics(transition)
        removed = diagnostics["semantic_removed_substrings"]
        self.assertEqual(removed["missing_substrings"], ["unsafe_call("])
        self.assertEqual(removed["observed_removed_lines"], [])
        self.assertTrue(
            any(
                finding["category"] == "correctness"
                and "remove" in finding["summary"].lower()
                for finding in transition["findings"]
            )
        )

    def test_v04_schema_requires_explicit_removed_transition(self) -> None:
        invalid = copy.deepcopy(self.plan_v04)
        invalid["backend"].pop("required_removed_substrings")
        with self.assertRaisesRegex(local_verifier.VerifierError, "required_removed_substrings"):
            local_verifier.validate_schema(
                invalid,
                ROOT / "schemas/evaluator-plan-v0.4.schema.json",
                "EvaluatorPlan v0.4",
            )


if __name__ == "__main__":
    unittest.main()
