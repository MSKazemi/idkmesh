from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.adapters import (  # noqa: E402
    A2AMockAdapter,
    CandidateArtifact,
    LocalAdapter,
    ResultBundle,
    RunContext,
    VerificationContext,
    run_with_adapter,
    verify_result_bundle,
)
from interop.bindings import canonical_digest, canonical_json  # noqa: E402
from interop.bindings import BindingError  # noqa: E402


RUN = RunContext(
    source_revision="0123456789abcdef",
    started_at="2026-08-29T00:00:00Z",
    finished_at="2026-08-29T00:00:01Z",
    wall_seconds=1.0,
)
VERIFY = VerificationContext(
    source_revision="0123456789abcdef",
    started_at="2026-08-29T00:00:02Z",
    finished_at="2026-08-29T00:00:03Z",
    wall_seconds=1.0,
)


def expected_bytes(work_unit: dict) -> bytes:
    return (canonical_json({
        "objective_digest": canonical_digest(work_unit["objective"]),
        "work_unit_id": work_unit["id"],
    }) + "\n").encode("utf-8")


def harmless_handler(work_unit: dict) -> tuple[CandidateArtifact, ...]:
    return (
        CandidateArtifact(
            id="result",
            type="test_result",
            locator="memory://interop/result.json",
            content=expected_bytes(work_unit),
            media_type="application/json",
        ),
    )


class AdapterRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text()
        )
        cls.result_schema = json.loads(
            (ROOT / "schemas/result-manifest-v0.1.schema.json").read_text()
        )
        cls.verification_schema = json.loads(
            (ROOT / "schemas/verification-result-v0.1.schema.json").read_text()
        )

    def test_local_and_a2a_use_one_coordinator_path(self) -> None:
        for adapter in (LocalAdapter(harmless_handler), A2AMockAdapter(harmless_handler)):
            with self.subTest(adapter=adapter.adapter_id):
                bundle = run_with_adapter(adapter, self.work_unit, RUN)
                Draft202012Validator(self.result_schema).validate(bundle.result_manifest)
                self.assertEqual(bundle.artifact_bytes["result"], expected_bytes(self.work_unit))
                self.assertEqual(
                    bundle.result_manifest["extensions"]["org.idkmesh.interop"]["acceptance_status"],
                    "pending_verification",
                )

    def test_a2a_wire_round_trip_is_recorded_without_acceptance(self) -> None:
        bundle = run_with_adapter(A2AMockAdapter(harmless_handler), self.work_unit, RUN)
        extension = bundle.result_manifest["extensions"]["org.idkmesh.interop"]
        self.assertEqual(extension["protocol"], "a2a")
        self.assertEqual(extension["protocol_state"], "TASK_STATE_COMPLETED")
        self.assertRegex(extension["transport_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("verification_result", bundle.result_manifest)

    def test_separate_verifier_emits_schema_valid_evidence(self) -> None:
        bundle = run_with_adapter(A2AMockAdapter(harmless_handler), self.work_unit, RUN)
        verification = verify_result_bundle(
            self.work_unit,
            bundle,
            {"result": expected_bytes(self.work_unit)},
            VERIFY,
        )
        Draft202012Validator(self.verification_schema).validate(verification)
        self.assertEqual(verification["status"], "passed")
        self.assertEqual(verification["decision_support"]["recommendation"], "accept_candidate")
        self.assertTrue(verification["independence"]["independent_from_worker"])
        self.assertFalse(
            verification["extensions"]["org.idkmesh.interop"]["candidate_code_executed_by_verifier"]
        )
        self.assertFalse(
            verification["extensions"]["org.idkmesh.interop"]["integration_authority"]
        )

    def test_tampered_artifact_is_rejected_by_separate_verifier(self) -> None:
        bundle = run_with_adapter(LocalAdapter(harmless_handler), self.work_unit, RUN)
        tampered = ResultBundle(bundle.result_manifest, {"result": b"tampered\n"})
        verification = verify_result_bundle(
            self.work_unit,
            tampered,
            {"result": expected_bytes(self.work_unit)},
            VERIFY,
        )
        self.assertEqual(verification["status"], "failed")
        Draft202012Validator(self.verification_schema).validate(verification)
        self.assertEqual(verification["decision_support"]["recommendation"], "reject_candidate")
        failed = {item["id"] for item in verification["checks"] if item["status"] == "failed"}
        self.assertEqual(failed, {"artifact-digests", "expected-output"})

    def test_adapter_handler_cannot_mutate_canonical_work_unit(self) -> None:
        original = copy.deepcopy(self.work_unit)

        def mutating_handler(work_unit: dict) -> tuple[CandidateArtifact, ...]:
            artifacts = harmless_handler(work_unit)
            work_unit["objective"] = "mutated inside adapter"
            return artifacts

        run_with_adapter(A2AMockAdapter(mutating_handler), self.work_unit, RUN)
        self.assertEqual(self.work_unit, original)

    def test_coordinator_enforces_work_unit_wall_budget(self) -> None:
        over_budget = RunContext(
            source_revision=RUN.source_revision,
            started_at=RUN.started_at,
            finished_at=RUN.finished_at,
            wall_seconds=self.work_unit["budget"]["wall_seconds"] + 0.001,
        )
        with self.assertRaisesRegex(BindingError, "wall budget"):
            run_with_adapter(LocalAdapter(harmless_handler), self.work_unit, over_budget)

    def test_verifier_detects_lost_validator_requirement(self) -> None:
        bundle = run_with_adapter(LocalAdapter(harmless_handler), self.work_unit, RUN)
        altered = copy.deepcopy(bundle.result_manifest)
        altered["verification_request"]["expected_validator_ids"] = ["schema"]
        verification = verify_result_bundle(
            self.work_unit,
            ResultBundle(altered, bundle.artifact_bytes),
            {"result": expected_bytes(self.work_unit)},
            VERIFY,
        )
        self.assertEqual(verification["status"], "failed")
        failed = {item["id"] for item in verification["checks"] if item["status"] == "failed"}
        self.assertIn("validator-requirements", failed)


if __name__ == "__main__":
    unittest.main()
