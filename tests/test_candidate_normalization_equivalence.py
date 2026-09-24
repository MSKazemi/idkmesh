import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from idkmesh.candidate_reference import candidate_reference_from_dict
from idkmesh.result_manifest_builder import (
    ResourceUsage,
    WorkerIdentity,
    build_result_manifest,
)
from idkmesh.verification_handoff import prepare_verification_handoff
from idkmesh.work_unit_binding import bind_work_unit_source


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "examples" / "candidate-normalization"
SOURCE_REVISION = "0123456789abcdef0123456789abcdef01234567"


def _load(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _manifest(work_unit, candidate, *, worker):
    binding = bind_work_unit_source(
        work_unit,
        source_revision=SOURCE_REVISION,
    )
    return build_result_manifest(
        work_unit,
        binding,
        candidate,
        manifest_id=f"c6/equivalence/{worker.id}",
        attempt=1,
        worker=worker,
        status="succeeded",
        started_at=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc),
        resources=ResourceUsage(wall_seconds=60),
        self_report=None,
        self_report_source="absent",
        verification_notes="Independent evaluator-owned verification required.",
    )


def _manifest_semantics(manifest):
    artifact = manifest["produced_artifacts"][0]
    return {
        "top_level_keys": tuple(sorted(manifest)),
        "artifact_keys": tuple(sorted(artifact)),
        "artifact_type": artifact["type"],
        "artifact_media_type": artifact["media_type"],
        "verification_request": manifest["verification_request"],
        "work_unit_digest": manifest["provenance"]["work_unit_digest"],
        "source_revision": manifest["provenance"]["source_revision"],
        "normalization": manifest["extensions"]["org.idkmesh.normalization"],
        "self_report": manifest["self_report"],
    }


def _handoff_semantics(handoff):
    encoded = handoff.to_dict()
    candidate_specific = {
        "result_manifest_id",
        "result_manifest_digest",
        "worker_id",
        "candidate_artifact_digest",
    }
    return {
        "keys": tuple(sorted(encoded)),
        "shared_values": {
            key: value
            for key, value in encoded.items()
            if key not in candidate_specific
        },
        "evaluator_binding": handoff.evaluator_binding(),
    }


class CandidateNormalizationEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work_unit = _load("c6-equivalence.work-unit.json")
        cls.pr_candidate = candidate_reference_from_dict(
            _load("pr-candidate-reference.json")
        )
        cls.local_candidate = candidate_reference_from_dict(
            _load("local-candidate-reference.json")
        )

        result_schema = json.loads(
            (ROOT / "schemas" / "result-manifest-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.result_validator = Draft202012Validator(
            result_schema,
            format_checker=FormatChecker(),
        )

    def test_remote_and_local_candidates_share_result_semantics(self):
        remote = _manifest(
            self.work_unit,
            self.pr_candidate,
            worker=WorkerIdentity(
                id="remote-worker",
                type="agent",
                adapter="remote-agent",
            ),
        )
        local = _manifest(
            self.work_unit,
            self.local_candidate,
            worker=WorkerIdentity(
                id="local-worker",
                type="agent",
                adapter="local-agent",
            ),
        )

        for label, manifest in (("remote", remote), ("local", local)):
            with self.subTest(label=label):
                errors = list(self.result_validator.iter_errors(manifest))
                self.assertEqual(
                    errors,
                    [],
                    [error.message for error in errors],
                )

        self.assertEqual(
            _manifest_semantics(remote),
            _manifest_semantics(local),
        )

        remote_reference = remote["extensions"][
            "org.idkmesh.candidate_reference"
        ]["reference"]
        local_reference = local["extensions"][
            "org.idkmesh.candidate_reference"
        ]["reference"]

        self.assertEqual(remote_reference["type"], "github_pull_request")
        self.assertEqual(
            remote_reference["head_sha"],
            "1123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(local_reference["type"], "artifact_bundle")
        self.assertEqual(
            local_reference["digest"],
            "sha256:" + "a" * 64,
        )

    def test_remote_and_local_candidates_share_verification_handoff_semantics(self):
        remote_manifest = _manifest(
            self.work_unit,
            self.pr_candidate,
            worker=WorkerIdentity(
                id="remote-worker",
                type="agent",
                adapter="remote-agent",
            ),
        )
        local_manifest = _manifest(
            self.work_unit,
            self.local_candidate,
            worker=WorkerIdentity(
                id="local-worker",
                type="agent",
                adapter="local-agent",
            ),
        )

        remote = prepare_verification_handoff(
            self.work_unit,
            remote_manifest,
        )
        local = prepare_verification_handoff(
            self.work_unit,
            local_manifest,
        )

        self.assertEqual(
            _handoff_semantics(remote),
            _handoff_semantics(local),
        )

    def test_provider_specific_identity_does_not_change_evaluator_binding(self):
        remote_manifest = _manifest(
            self.work_unit,
            self.pr_candidate,
            worker=WorkerIdentity(
                id="remote-worker",
                type="agent",
                adapter="remote-agent",
            ),
        )
        local_manifest = _manifest(
            self.work_unit,
            self.local_candidate,
            worker=WorkerIdentity(
                id="local-worker",
                type="agent",
                adapter="local-agent",
            ),
        )
        remote = prepare_verification_handoff(
            self.work_unit,
            remote_manifest,
        )
        local = prepare_verification_handoff(
            self.work_unit,
            local_manifest,
        )

        self.assertEqual(remote.evaluator_binding(), local.evaluator_binding())
        self.assertEqual(
            remote.required_validator_ids,
            ("result-schema", "independent-review"),
        )
        self.assertEqual(
            remote.required_validator_ids,
            local.required_validator_ids,
        )
        self.assertTrue(remote.independent_from_worker)
        self.assertTrue(local.independent_from_worker)
        self.assertEqual(remote.minimum_independent_verifiers, 1)
        self.assertEqual(local.minimum_independent_verifiers, 1)

    def test_equivalence_surface_carries_no_integration_authority(self):
        manifest = _manifest(
            self.work_unit,
            self.pr_candidate,
            worker=WorkerIdentity(
                id="remote-worker",
                type="agent",
                adapter="remote-agent",
            ),
        )
        handoff = prepare_verification_handoff(
            self.work_unit,
            manifest,
        ).to_dict()

        forbidden = {
            "accepted",
            "verified",
            "recommendation",
            "human_decision",
            "merge_authorized",
            "integration_authorized",
        }
        self.assertTrue(forbidden.isdisjoint(manifest))
        self.assertTrue(forbidden.isdisjoint(handoff))


if __name__ == "__main__":
    unittest.main()
