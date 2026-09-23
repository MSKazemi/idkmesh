import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.result_manifest_builder import (
    ExecutionEnvironment,
    LogReference,
    ModelIdentity,
    ResourceUsage,
    ResultManifestBuildError,
    SelfReport,
    WorkerIdentity,
    build_result_manifest,
)
from idkmesh.work_unit_binding import (
    bind_work_unit_source,
    canonical_digest,
)


SOURCE = "0123456789abcdef0123456789abcdef01234567"
HEAD = "1123456789abcdef0123456789abcdef01234567"
BUNDLE_DIGEST = "sha256:" + "a" * 64
WORKER_CONFIG_DIGEST = "sha256:" + "b" * 64


def _work_unit():
    return {
        "schema_version": "0.2",
        "id": "test/c6-result-normalization",
        "version": 1,
        "kind": "coding",
        "objective": "Normalize one candidate into ResultManifest.",
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


def _worker():
    return WorkerIdentity(
        id="worker-1",
        type="agent",
        adapter="test-adapter",
        adapter_version="1.2.3",
        model=ModelIdentity(
            provider="test-provider",
            name="model-x",
            version="2026-09",
        ),
    )


def _build(candidate, **overrides):
    work_unit = overrides.pop("work_unit", _work_unit())
    binding = overrides.pop(
        "binding",
        bind_work_unit_source(work_unit, source_revision=SOURCE),
    )
    values = {
        "manifest_id": "test/result/attempt-1",
        "attempt": 1,
        "worker": _worker(),
        "status": "succeeded",
        "started_at": datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc),
        "resources": ResourceUsage(
            wall_seconds=60,
            cpu_seconds=12.5,
            max_rss_mb=256,
            compute_units=0,
            human_minutes=0,
            tokens=123,
        ),
        "self_report": SelfReport(
            summary="Worker reports implementation complete.",
            claims=("Candidate created.",),
            confidence_value=0.8,
            confidence_meaning="uncalibrated",
        ),
        "self_report_source": "worker",
        "logs": (
            LogReference(
                type="stdout",
                locator="artifact://logs/stdout",
                digest="sha256:" + "c" * 64,
            ),
        ),
        "metrics": {
            "files_changed": 2,
            "provider_latency_seconds": 1.25,
            "unknown": None,
        },
        "environment": ExecutionEnvironment(
            platform="linux",
            python="3.13",
            tool_versions={"idkmesh": "0.1"},
        ),
        "worker_config_digest": WORKER_CONFIG_DIGEST,
        "verification_notes": "Evaluate the normalized candidate independently.",
    }
    values.update(overrides)
    return build_result_manifest(
        work_unit,
        binding,
        candidate,
        **values,
    )


class ResultManifestBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "schemas" / "result-manifest-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def assert_schema_valid(self, manifest):
        errors = sorted(
            self.validator.iter_errors(manifest),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual(
            errors,
            [],
            [f"{list(error.absolute_path)}: {error.message}" for error in errors],
        )

    def test_pr_candidate_builds_schema_valid_manifest(self):
        candidate = GitHubPullRequestCandidateReference(
            repository="MSKazemi/idkmesh",
            number=42,
            head_sha=HEAD,
        )
        manifest = _build(candidate)

        self.assert_schema_valid(manifest)
        self.assertEqual(manifest["work_unit_id"], "test/c6-result-normalization")
        self.assertEqual(manifest["work_unit_version"], 1)
        self.assertEqual(
            manifest["verification_request"]["expected_validator_ids"],
            ["tests", "review"],
        )
        self.assertEqual(
            manifest["verification_request"]["evidence_artifact_ids"],
            ["candidate"],
        )
        artifact = manifest["produced_artifacts"][0]
        self.assertEqual(
            artifact["locator"],
            f"https://github.com/MSKazemi/idkmesh/pull/42#idkmesh-head={HEAD}",
        )
        expected_reference_digest = canonical_digest(candidate.to_dict())
        self.assertEqual(artifact["digest"], expected_reference_digest)
        self.assertEqual(
            manifest["extensions"]["org.idkmesh.candidate_reference"][
                "reference_digest"
            ],
            expected_reference_digest,
        )

    def test_local_bundle_uses_same_normalization_profile(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
            media_type="text/x-diff",
        )
        manifest = _build(candidate)

        self.assert_schema_valid(manifest)
        artifact = manifest["produced_artifacts"][0]
        self.assertEqual(artifact["locator"], "file:///tmp/candidate.patch")
        self.assertEqual(artifact["type"], "other")
        self.assertEqual(
            artifact["media_type"],
            "application/vnd.idkmesh.candidate-reference+json",
        )
        self.assertEqual(artifact["digest"], canonical_digest(candidate.to_dict()))
        extension = manifest["extensions"]["org.idkmesh.candidate_reference"]
        self.assertEqual(extension["reference"]["digest"], BUNDLE_DIGEST)
        self.assertEqual(
            extension["digest_semantics"],
            "candidate_reference_envelope",
        )

    def test_remote_and_local_candidates_have_equivalent_canonical_shape(self):
        pr = _build(
            GitHubPullRequestCandidateReference(
                repository="MSKazemi/idkmesh",
                number=7,
                head_sha=HEAD,
            )
        )
        local = _build(
            ArtifactBundleCandidateReference(
                locator="file:///tmp/candidate.patch",
                digest=BUNDLE_DIGEST,
            )
        )

        self.assertEqual(set(pr), set(local))
        self.assertEqual(
            set(pr["produced_artifacts"][0]),
            set(local["produced_artifacts"][0]),
        )
        self.assertEqual(pr["verification_request"], local["verification_request"])
        self.assertEqual(pr["provenance"], local["provenance"])
        self.assertEqual(
            pr["extensions"]["org.idkmesh.normalization"],
            local["extensions"]["org.idkmesh.normalization"],
        )

    def test_work_unit_binding_mismatch_fails_closed(self):
        original = _work_unit()
        binding = bind_work_unit_source(original, source_revision=SOURCE)
        changed = _work_unit()
        changed["objective"] = "Mutated after source binding"

        with self.assertRaisesRegex(
            ResultManifestBuildError,
            "binding validation failed",
        ):
            _build(
                ArtifactBundleCandidateReference(
                    locator="file:///tmp/candidate.patch",
                    digest=BUNDLE_DIGEST,
                ),
                work_unit=changed,
                binding=binding,
            )

    def test_duplicate_validator_ids_fail_closed(self):
        work_unit = _work_unit()
        work_unit["validators"].append(
            {"id": "tests", "type": "lint", "required": True}
        )
        binding = bind_work_unit_source(work_unit, source_revision=SOURCE)

        with self.assertRaisesRegex(
            ResultManifestBuildError,
            "duplicate WorkUnit validator id",
        ):
            _build(
                ArtifactBundleCandidateReference(
                    locator="file:///tmp/candidate.patch",
                    digest=BUNDLE_DIGEST,
                ),
                work_unit=work_unit,
                binding=binding,
            )

    def test_time_order_and_timezone_are_enforced(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
        )
        with self.assertRaisesRegex(
            ResultManifestBuildError,
            "timezone-aware",
        ):
            _build(
                candidate,
                started_at=datetime(2026, 9, 23, 12, 0),
            )

        with self.assertRaisesRegex(
            ResultManifestBuildError,
            "must not be earlier",
        ):
            _build(
                candidate,
                started_at=datetime(2026, 9, 23, 12, 2, tzinfo=timezone.utc),
                finished_at=datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc),
            )

        shifted = _build(
            candidate,
            started_at=datetime(
                2026, 9, 23, 14, 0, tzinfo=timezone(timedelta(hours=2))
            ),
            finished_at=datetime(
                2026, 9, 23, 14, 1, tzinfo=timezone(timedelta(hours=2))
            ),
        )
        self.assertEqual(shifted["started_at"], "2026-09-23T12:00:00Z")
        self.assertEqual(shifted["finished_at"], "2026-09-23T12:01:00Z")

    def test_resource_metric_and_digest_validation_is_fail_closed(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
        )
        bad_calls = [
            {"resources": ResourceUsage(wall_seconds=-1)},
            {"resources": ResourceUsage(wall_seconds=True)},
            {"metrics": {"bad": True}},
            {"metrics": {"bad": float("nan")}},
            {"worker_config_digest": "sha256:" + "A" * 64},
        ]
        for overrides in bad_calls:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ResultManifestBuildError):
                    _build(candidate, **overrides)

    def test_absent_self_report_is_explicit_not_invented(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
        )
        manifest = _build(
            candidate,
            self_report=None,
            self_report_source="absent",
        )
        self.assertEqual(manifest["self_report"]["claims"], [])
        self.assertIn("No worker-authored", manifest["self_report"]["summary"])
        self.assertEqual(
            manifest["extensions"]["org.idkmesh.normalization"][
                "self_report_source"
            ],
            "absent",
        )
        self.assert_schema_valid(manifest)

    def test_self_report_source_must_match_presence(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
        )
        with self.assertRaises(ResultManifestBuildError):
            _build(
                candidate,
                self_report=None,
                self_report_source="worker",
            )
        with self.assertRaises(ResultManifestBuildError):
            _build(
                candidate,
                self_report=SelfReport(summary="x"),
                self_report_source="absent",
            )

    def test_manifest_has_no_verification_or_integration_authority(self):
        manifest = _build(
            GitHubPullRequestCandidateReference(
                repository="MSKazemi/idkmesh",
                number=42,
                head_sha=HEAD,
            )
        )
        forbidden = {
            "accepted",
            "verified",
            "verification_result",
            "merge_authorized",
            "integration_authorized",
            "human_decision",
        }
        self.assertTrue(forbidden.isdisjoint(manifest))
        self.assertTrue(
            forbidden.isdisjoint(
                manifest["extensions"]["org.idkmesh.candidate_reference"]
            )
        )

    def test_worker_and_log_validation_is_strict(self):
        candidate = ArtifactBundleCandidateReference(
            locator="file:///tmp/candidate.patch",
            digest=BUNDLE_DIGEST,
        )
        with self.assertRaises(ResultManifestBuildError):
            _build(
                candidate,
                worker=WorkerIdentity(
                    id="worker",
                    type="root",
                    adapter="adapter",
                ),
            )
        with self.assertRaises(ResultManifestBuildError):
            _build(
                candidate,
                logs=(LogReference(type="secret", locator="x"),),
            )


if __name__ == "__main__":
    unittest.main()
