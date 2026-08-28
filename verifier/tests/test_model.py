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

    plan = {
        "schema_version": "0.1",
        "id": "verifier/unit-test-plan",
        "verifier": {
            "id": "independent-verifier",
            "adapter": "docker-hidden-checks",
            "adapter_version": "0.1",
        },
        "source_input_id": "source-repository",
        "candidate_artifact_id": "candidate-result",
        "container_image": "python:3.12-alpine",
        "checks": [
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
        ],
    }
    return work_unit, result, plan


class VerifierModelTests(unittest.TestCase):
    def test_valid_context_binds_worker_to_exact_work_unit(self) -> None:
        work_unit, result, plan = fixtures()
        context = parse_context(work_unit, result, plan)
        self.assertEqual(context.source_revision, SOURCE_REVISION)
        self.assertEqual(context.verifier_id, "independent-verifier")
        self.assertEqual(context.candidate_artifact["id"], "candidate-result")

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

    def test_missing_required_validator_check_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        plan["checks"] = [check for check in plan["checks"] if check["id"] != "reproduction"]
        with self.assertRaisesRegex(VerifierError, "missing required/requested"):
            parse_context(work_unit, result, plan)

    def test_non_sandboxed_work_is_rejected(self) -> None:
        work_unit, result, plan = fixtures()
        work_unit["security"]["sandbox_required"] = False
        result["provenance"]["work_unit_digest"] = canonical_digest(work_unit)
        with self.assertRaisesRegex(VerifierError, "sandbox_required"):
            parse_context(work_unit, result, plan)

    def test_high_risk_work_is_rejected_by_mvp(self) -> None:
        work_unit, result, plan = fixtures()
        work_unit["security"]["risk_class"] = "high"
        result["provenance"]["work_unit_digest"] = canonical_digest(work_unit)
        with self.assertRaisesRegex(VerifierError, "low-risk public"):
            parse_context(work_unit, result, plan)

    def test_hidden_container_check_requires_command(self) -> None:
        work_unit, result, plan = fixtures()
        bad = copy.deepcopy(plan)
        del bad["checks"][1]["command"]
        with self.assertRaisesRegex(VerifierError, "VerifierPlan failed schema validation"):
            parse_context(work_unit, result, bad)


if __name__ == "__main__":
    unittest.main()
