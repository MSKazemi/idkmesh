from datetime import datetime, timezone
import copy
import unittest

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.result_manifest_builder import (
    ResourceUsage,
    WorkerIdentity,
    build_result_manifest,
)
from idkmesh.verification_handoff import (
    VerificationHandoffError,
    prepare_verification_handoff,
)
from idkmesh.work_unit_binding import (
    bind_work_unit_source,
    canonical_digest,
)


SOURCE = "0123456789abcdef0123456789abcdef01234567"
HEAD = "1123456789abcdef0123456789abcdef01234567"
BUNDLE_DIGEST = "sha256:" + "a" * 64


def _work_unit():
    return {
        "schema_version": "0.2",
        "id": "test/c6-handoff",
        "version": 1,
        "kind": "coding",
        "objective": "Prepare a verifier-owned handoff.",
        "inputs": [],
        "outputs": [
            {
                "id": "candidate",
                "type": "patch",
                "description": "Candidate implementation.",
            }
        ],
        "dependencies": [],
        "requirements": {
            "capabilities": ["coding"],
            "resources": {
                "cpu_cores_min": 0,
                "memory_mb_min": 0,
                "gpu": "none",
            },
        },
        "constraints": {
            "allowed_paths": [],
            "forbidden_paths": [],
            "policies": [],
        },
        "uncertainty": [],
        "security": {
            "risk_class": "low",
            "data_classification": "public",
            "minimum_worker_trust": "untrusted",
            "sandbox_required": False,
        },
        "permissions": {
            "network": "none",
            "filesystem_write": [],
            "secrets": [],
            "process_execution": False,
        },
        "verification_policy": {
            "strategy": "all_required",
            "independent_from_worker": True,
            "minimum_independent_verifiers": 1,
        },
        "validators": [
            {"id": "tests", "type": "test", "required": True},
            {"id": "review", "type": "review", "required": True},
            {"id": "optional-lint", "type": "lint", "required": False},
        ],
        "evidence_requirements": [
            {"type": "artifact_hash", "required": True}
        ],
        "budget": {
            "project_spend_usd_max": 0,
            "paid_fallback_allowed": False,
        },
        "provenance": {
            "created_by": "test",
            "creator_type": "system",
            "source": "fixture",
            "source_revision": SOURCE,
        },
        "failure_semantics": {
            "retryable": False,
            "max_attempts": 1,
            "on_failure": "stop",
        },
    }


def _manifest(candidate):
    work = _work_unit()
    binding = bind_work_unit_source(work, source_revision=SOURCE)
    return work, build_result_manifest(
        work,
        binding,
        candidate,
        manifest_id="test/result/attempt-1",
        attempt=1,
        worker=WorkerIdentity(
            id="worker-1",
            type="agent",
            adapter="test-adapter",
        ),
        status="succeeded",
        started_at=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc),
        resources=ResourceUsage(wall_seconds=60),
    )


class VerificationHandoffTests(unittest.TestCase):
    def test_handoff_binds_exact_work_result_and_candidate(self):
        work, manifest = _manifest(
            GitHubPullRequestCandidateReference(
                repository="MSKazemi/idkmesh",
                number=42,
                head_sha=HEAD,
            )
        )

        handoff = prepare_verification_handoff(work, manifest)

        self.assertEqual(handoff.work_unit_id, work["id"])
        self.assertEqual(handoff.work_unit_version, work["version"])
        self.assertEqual(handoff.work_unit_digest, canonical_digest(work))
        self.assertEqual(
            handoff.result_manifest_digest,
            canonical_digest(manifest),
        )
        self.assertEqual(handoff.candidate_artifact_id, "candidate")
        self.assertEqual(
            handoff.candidate_artifact_digest,
            manifest["produced_artifacts"][0]["digest"],
        )
        self.assertEqual(
            handoff.required_validator_ids,
            ("tests", "review"),
        )
        self.assertEqual(
            handoff.evaluator_binding(),
            {
                "work_unit_id": work["id"],
                "work_unit_version": work["version"],
                "work_unit_digest": canonical_digest(work),
                "source_revision": SOURCE,
            },
        )

    def test_local_and_remote_candidates_enter_same_handoff_shape(self):
        work_pr, manifest_pr = _manifest(
            GitHubPullRequestCandidateReference(
                repository="MSKazemi/idkmesh",
                number=42,
                head_sha=HEAD,
            )
        )
        work_local, manifest_local = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )

        pr = prepare_verification_handoff(work_pr, manifest_pr).to_dict()
        local = prepare_verification_handoff(
            work_local,
            manifest_local,
        ).to_dict()

        self.assertEqual(set(pr), set(local))
        for field in (
            "work_unit_id",
            "work_unit_version",
            "work_unit_digest",
            "source_revision",
            "result_manifest_id",
            "attempt",
            "worker_id",
            "candidate_artifact_id",
            "required_validator_ids",
            "verification_strategy",
            "independent_from_worker",
            "minimum_independent_verifiers",
        ):
            self.assertEqual(pr[field], local[field])

    def test_handoff_contains_no_verifier_selection_or_decision_authority(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        encoded = prepare_verification_handoff(work, manifest).to_dict()

        forbidden = {
            "verifier",
            "verifier_id",
            "evaluator_plan",
            "status",
            "recommendation",
            "confidence",
            "accepted",
            "verified",
            "merge_authorized",
            "integration_authorized",
        }
        self.assertTrue(forbidden.isdisjoint(encoded))

    def test_result_manifest_work_binding_tamper_fails_closed(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        tampered = copy.deepcopy(manifest)
        tampered["provenance"]["work_unit_digest"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            VerificationHandoffError,
            "exact WorkUnit content",
        ):
            prepare_verification_handoff(work, tampered)

    def test_required_validator_omission_fails_closed(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        manifest["verification_request"]["expected_validator_ids"] = [
            "tests",
            "optional-lint",
        ]

        with self.assertRaisesRegex(
            VerificationHandoffError,
            "omits required validator",
        ):
            prepare_verification_handoff(work, manifest)

    def test_optional_validator_is_not_promoted_to_required(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        handoff = prepare_verification_handoff(work, manifest)
        self.assertNotIn("optional-lint", handoff.required_validator_ids)

    def test_multiple_evidence_artifacts_require_explicit_selection(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        extra = copy.deepcopy(manifest["produced_artifacts"][0])
        extra["id"] = "secondary"
        extra["digest"] = "sha256:" + "b" * 64
        manifest["produced_artifacts"].append(extra)
        manifest["verification_request"]["evidence_artifact_ids"].append(
            "secondary"
        )

        with self.assertRaisesRegex(
            VerificationHandoffError,
            "candidate_artifact_id is required",
        ):
            prepare_verification_handoff(work, manifest)

        handoff = prepare_verification_handoff(
            work,
            manifest,
            candidate_artifact_id="candidate",
        )
        self.assertEqual(handoff.candidate_artifact_id, "candidate")

    def test_candidate_artifact_must_exist_exactly_once(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        manifest["produced_artifacts"] = []

        with self.assertRaisesRegex(
            VerificationHandoffError,
            "exactly one produced artifact",
        ):
            prepare_verification_handoff(work, manifest)

    def test_independence_policy_is_retained_and_consistent(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        handoff = prepare_verification_handoff(work, manifest)
        self.assertTrue(handoff.independent_from_worker)
        self.assertEqual(handoff.minimum_independent_verifiers, 1)

        contradictory = copy.deepcopy(work)
        contradictory["verification_policy"][
            "minimum_independent_verifiers"
        ] = 0
        contradictory_manifest = copy.deepcopy(manifest)
        contradictory_manifest["provenance"][
            "work_unit_digest"
        ] = canonical_digest(contradictory)

        with self.assertRaisesRegex(
            VerificationHandoffError,
            "at least one independent verifier",
        ):
            prepare_verification_handoff(
                contradictory,
                contradictory_manifest,
            )

    def test_quorum_policy_is_preserved_without_selecting_verifier(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        work["verification_policy"] = {
            "strategy": "quorum",
            "independent_from_worker": True,
            "minimum_independent_verifiers": 2,
            "quorum": 2,
        }
        manifest["provenance"]["work_unit_digest"] = canonical_digest(work)

        handoff = prepare_verification_handoff(work, manifest)
        self.assertEqual(handoff.verification_strategy, "quorum")
        self.assertEqual(handoff.quorum, 2)

    def test_result_manifest_authority_fields_fail_closed(self):
        work, manifest = _manifest(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )
        manifest["accepted"] = True
        with self.assertRaisesRegex(
            VerificationHandoffError,
            "forbidden authority field",
        ):
            prepare_verification_handoff(work, manifest)


if __name__ == "__main__":
    unittest.main()
