from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verifier" / "src"))

from idkmesh_verifier.model import VerifierError, canonical_digest, parse_context  # noqa: E402

SOURCE_REVISION = "0123456789abcdef0123456789abcdef01234567"


def fixtures() -> tuple[dict, dict, dict]:
    work_unit = json.loads(
        (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(encoding="utf-8")
    )
    work_unit["kind"] = "coding"
    work_unit["inputs"] = [
        {
            "id": "source-repository",
            "type": "git_ref",
            "locator": "https://github.com/MSKazemi/idkmesh",
        }
    ]
    work_unit["outputs"] = [
        {
            "id": "candidate-result",
            "type": "patch",
            "description": "Candidate patch for verifier unit tests.",
            "media_type": "text/x-diff",
        }
    ]
    work_unit["constraints"]["allowed_paths"] = ["README.md"]
    work_unit["constraints"]["forbidden_paths"] = [".github/**"]
    work_unit["security"]["sandbox_required"] = True
    work_unit["permissions"]["filesystem_write"] = ["README.md"]
    work_unit["permissions"]["process_execution"] = True
    work_unit["provenance"]["source_revision"] = SOURCE_REVISION

    result = json.loads(
        (ROOT / "examples/results/phase0-smoke.result-manifest.json").read_text(encoding="utf-8")
    )
    result["work_unit_id"] = work_unit["id"]
    result["work_unit_version"] = work_unit["version"]
    result["produced_artifacts"] = [
        {
            "id": "candidate-result",
            "type": "patch",
            "locator": "changes.patch",
            "digest": "sha256:" + "0" * 64,
            "media_type": "text/x-diff",
        }
    ]
    result["provenance"]["work_unit_digest"] = canonical_digest(work_unit)
    result["provenance"]["source_revision"] = SOURCE_REVISION
    result["verification_request"]["evidence_artifact_ids"] = ["candidate-result"]

    checks = [
        {"id": "schema", "type": "schema", "required": True, "mode": "result_schema"},
        {
            "id": "reproduction",
            "type": "reproduction",
            "required": True,
            "mode": "container_command",
            "command": ["python", "-c", "print('hidden check')"],
            "timeout_seconds": 30,
        },
        {
            "id": "artifact-integrity",
            "type": "policy",
            "required": True,
            "mode": "artifact_integrity",
        },
        {
            "id": "scope-policy",
            "type": "policy",
            "required": True,
            "mode": "scope_policy",
        },
    ]
    required_validator_ids = sorted(
        {v["id"] for v in work_unit["validators"] if v["required"]}
        | set(result["verification_request"]["expected_validator_ids"])
    )
    plan = {
        "schema_version": "0.2",
        "id": "evaluator/unit-test-plan",
        "binding": {
            "work_unit_id": work_unit["id"],
            "work_unit_version": work_unit["version"],
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_REVISION,
        },
        "visibility": "hidden",
        "execution_mode": "repository_patch",
        "verifier": {
            "id": "independent-verifier",
            "type": "system",
            "adapter": "docker-hidden-checks",
            "adapter_version": "0.2",
        },
        "required_validator_ids": required_validator_ids,
        "source_input_id": "source-repository",
        "candidate_artifact_id": "candidate-result",
        "container_image": "python:3.12-alpine",
        "checks": checks,
        "policy": {
            "require_plan_outside_candidate_root": True,
            "require_output_outside_candidate_root": True,
            "require_verifier_distinct_from_worker": True,
            "fresh_workspace_per_container_check": True,
        },
    }
    return work_unit, result, plan


class VerifierModelTests(unittest.TestCase):
    def test_valid_context_binds_worker_and_evaluator_to_exact_work_unit(self) -> None:
        work_unit, result, plan = fixtures()
        context = parse_context(work_unit, result, plan)
        self.assertEqual(context.source_revision, SOURCE_REVISION)
        self.assertEqual(context.verifier_id, "independent-verifier")
        self.assertEqual(context.candidate_artifact["id"], "candidate-result")
        self.assertEqual(context.plan["execution_mode"], "repository_patch")

    def test_self_verification_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        plan["verifier"]["id"] = result["worker"]["id"]
        with self.assertRaisesRegex(VerifierError, "identity must differ"):
            parse_context(work_unit, result, plan)

    def test_wrong_work_unit_digest_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        result["provenance"]["work_unit_digest"] = "sha256:" + "9" * 64
        with self.assertRaisesRegex(VerifierError, "exact WorkUnit"):
            parse_context(work_unit, result, plan)

    def test_evaluator_plan_binding_drift_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        plan["binding"]["source_revision"] = "f" * 40
        with self.assertRaisesRegex(VerifierError, "source_revision"):
            parse_context(work_unit, result, plan)

    def test_required_validator_set_must_match_exactly(self) -> None:
        work_unit, result, plan = fixtures()
        plan["required_validator_ids"].append("not-requested")
        with self.assertRaisesRegex(VerifierError, "exactly cover"):
            parse_context(work_unit, result, plan)

    def test_missing_required_validator_check_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        plan["checks"] = [check for check in plan["checks"] if check["id"] != "reproduction"]
        with self.assertRaisesRegex(VerifierError, "missing required"):
            parse_context(work_unit, result, plan)

    def test_duplicate_check_ids_are_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        duplicate = copy.deepcopy(plan["checks"][0])
        plan["checks"].append(duplicate)
        with self.assertRaisesRegex(VerifierError, "check ids must be unique"):
            parse_context(work_unit, result, plan)

    def test_non_sandboxed_work_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        work_unit["security"]["sandbox_required"] = False
        result["provenance"]["work_unit_digest"] = canonical_digest(work_unit)
        plan["binding"]["work_unit_digest"] = canonical_digest(work_unit)
        with self.assertRaisesRegex(VerifierError, "sandbox_required"):
            parse_context(work_unit, result, plan)

    def test_high_risk_work_is_rejected_by_mvp(self) -> None:
        work_unit, result, plan = fixtures()
        work_unit["security"]["risk_class"] = "high"
        result["provenance"]["work_unit_digest"] = canonical_digest(work_unit)
        plan["binding"]["work_unit_digest"] = canonical_digest(work_unit)
        with self.assertRaisesRegex(VerifierError, "low-risk public"):
            parse_context(work_unit, result, plan)

    def test_hidden_container_check_requires_command(self) -> None:
        work_unit, result, plan = fixtures()
        bad = copy.deepcopy(plan)
        del bad["checks"][1]["command"]
        with self.assertRaisesRegex(VerifierError, "EvaluatorPlan failed schema validation"):
            parse_context(work_unit, result, bad)


if __name__ == "__main__":
    unittest.main()
