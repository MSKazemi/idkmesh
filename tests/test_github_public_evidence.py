import json
from pathlib import Path
import unittest

import jsonschema

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.github_public_evidence import (
    GitHubPublicEvidenceError,
    GitHubPublicEvidencePolicy,
    build_github_public_evidence_projection,
    render_github_public_evidence_json,
)
from idkmesh.product_spine import AttemptProjection, ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
SOURCE = "1" * 40


def _policy(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "data_classification": "public",
        "public_projection_enabled": True,
    }
    values.update(overrides)
    return GitHubPublicEvidencePolicy(**values)


def _candidate():
    return GitHubPullRequestCandidateReference(
        repository="MSKazemi/idkmesh",
        number=123,
        head_sha="2" * 40,
    )


def _report():
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-run-evidence-report",
        "run_id": "run-609",
        "source_run_kind": "idkmesh-two-attempt-run",
        "source_run_digest": DIGEST_C,
        "source_config_digest": DIGEST_D,
        "orchestrator_version": "0.2",
        "work_unit": {
            "id": "github/mskazemi/idkmesh/issue-609",
            "version": 1,
            "digest": DIGEST_A,
        },
        "verifier_policy_digest": DIGEST_D,
        "attempts": [
            {
                "attempt_id": "attempt-1",
                "order": 1,
                "worker_adapter": "jules",
                "state": "verified",
                "evidence_state": "supported",
                "worker": {
                    "id": "private-worker-identity",
                    "status": "succeeded",
                    "result_manifest_id": "private-result-id",
                    "result_manifest_digest": DIGEST_B,
                },
                "verifier": {
                    "id": "private-verifier-identity",
                    "status": "completed",
                    "recommendation": "accept_candidate",
                    "verification_semantic_digest": DIGEST_C,
                    "checks": [
                        {
                            "id": "private-check-name",
                            "status": "passed-with-private-detail",
                            "required": True,
                        }
                    ],
                },
                "error": None,
            }
        ],
        "summary": {
            "attempt_count": 1,
            "supported": 1,
            "rejected": 0,
            "inconclusive": 0,
            "control_errors": 0,
            "verification_disagreement": False,
            "control_failure_present": False,
        },
        "warnings": [
            "PRIVATE PROMPT OR LOG MATERIAL MUST NEVER REACH THE PUBLIC PROJECTION"
        ],
        "human_decision": {
            "status": "pending",
            "selected_attempt_id": None,
            "integration_authority": "external_human_or_governance",
        },
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }


def _run(*, candidate=None, report=None):
    candidate = candidate or _candidate()
    report = report or _report()
    return ProductSpineRun(
        run_id="run-609",
        request_digest=DIGEST_D,
        project_id="MSKazemi/idkmesh",
        work_unit_id="github/mskazemi/idkmesh/issue-609",
        work_unit_version=1,
        work_unit_digest=DIGEST_A,
        source_revision=SOURCE,
        authority_mode="agent_candidate",
        routing_policy_version="routing-v1",
        state="evidence_ready",
        admitted_connectors=("jules",),
        attempts=(
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="jules",
                state="verified",
                provider_reference="private-provider-session",
                candidate_reference_digest=canonical_digest(
                    candidate.to_dict()
                ),
                result_manifest_digest=DIGEST_B,
                verification_semantic_digest=DIGEST_C,
            ),
        ),
        evidence_report_digest=canonical_digest(report),
    )


class GitHubPublicEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "github-public-evidence-v0.1.schema.json"
        )
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def test_projection_is_schema_valid_and_keeps_only_public_whitelist(self):
        candidate = _candidate()
        report = _report()
        projection = build_github_public_evidence_projection(
            _run(candidate=candidate, report=report),
            policy=_policy(),
            candidates={"attempt-1": candidate},
            evidence_report=report,
        )
        jsonschema.Draft202012Validator(self.schema).validate(projection)

        rendered = render_github_public_evidence_json(projection)
        self.assertIn("accept_candidate", rendered)
        self.assertIn(
            "https://github.com/MSKazemi/idkmesh/pull/123",
            rendered,
        )
        for forbidden in (
            "private-provider-session",
            "private-worker-identity",
            "private-verifier-identity",
            "private-result-id",
            "private-check-name",
            "passed-with-private-detail",
            "PRIVATE PROMPT OR LOG MATERIAL",
        ):
            self.assertNotIn(forbidden, rendered)

        self.assertTrue(projection["privacy"]["projection_only"])
        self.assertFalse(projection["authority"]["merge"])
        self.assertFalse(projection["authority"]["human_decision"])

    def test_artifact_bundle_locator_is_never_projected(self):
        locator = "file:///home/private/project/secret-output.patch"
        candidate = ArtifactBundleCandidateReference(
            locator=locator,
            digest=DIGEST_B,
            media_type="text/x-diff",
        )
        run = ProductSpineRun(
            run_id="run-artifact",
            request_digest=DIGEST_D,
            project_id="MSKazemi/idkmesh",
            work_unit_id="github/mskazemi/idkmesh/issue-609",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
            state="candidate_observed",
            admitted_connectors=("local-agent",),
            attempts=(
                AttemptProjection(
                    attempt_id="attempt-1",
                    order=1,
                    connector_id="local-agent",
                    state="candidate_observed",
                    provider_reference="private-local-runtime",
                    candidate_reference_digest=canonical_digest(
                        candidate.to_dict()
                    ),
                ),
            ),
        )
        projection = build_github_public_evidence_projection(
            run,
            policy=_policy(),
            candidates={"attempt-1": candidate},
        )
        rendered = render_github_public_evidence_json(projection)
        self.assertNotIn(locator, rendered)
        self.assertNotIn("private-local-runtime", rendered)
        self.assertEqual(
            projection["attempts"][0]["candidate"],
            {"type": "artifact_bundle", "digest": DIGEST_B},
        )

    def test_non_public_or_disabled_policy_fails_closed(self):
        run = ProductSpineRun(
            run_id="run-policy",
            request_digest=DIGEST_D,
            project_id="MSKazemi/idkmesh",
            work_unit_id="github/mskazemi/idkmesh/issue-609",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
        )
        for policy in (
            _policy(data_classification="internal"),
            _policy(public_projection_enabled=False),
        ):
            with self.subTest(policy=policy):
                with self.assertRaises(GitHubPublicEvidenceError):
                    build_github_public_evidence_projection(
                        run,
                        policy=policy,
                    )

    def test_project_repository_binding_fails_closed(self):
        run = ProductSpineRun(
            run_id="run-project",
            request_digest=DIGEST_D,
            project_id="other/project",
            work_unit_id="work/unit",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
        )
        with self.assertRaises(GitHubPublicEvidenceError):
            build_github_public_evidence_projection(
                run,
                policy=_policy(),
            )

    def test_cross_repository_pr_candidate_is_rejected(self):
        candidate = GitHubPullRequestCandidateReference(
            repository="other/project",
            number=5,
            head_sha="2" * 40,
        )
        run = ProductSpineRun(
            run_id="run-cross-repo",
            request_digest=DIGEST_D,
            project_id="MSKazemi/idkmesh",
            work_unit_id="work/unit",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
            state="candidate_observed",
            admitted_connectors=("jules",),
            attempts=(
                AttemptProjection(
                    attempt_id="attempt-1",
                    order=1,
                    connector_id="jules",
                    state="candidate_observed",
                    candidate_reference_digest=canonical_digest(
                        candidate.to_dict()
                    ),
                ),
            ),
        )
        with self.assertRaises(GitHubPublicEvidenceError):
            build_github_public_evidence_projection(
                run,
                policy=_policy(),
                candidates={"attempt-1": candidate},
            )

    def test_candidate_and_evidence_digest_mismatch_fail_closed(self):
        candidate = _candidate()
        report = _report()
        run = _run(candidate=candidate, report=report)

        changed_candidate = GitHubPullRequestCandidateReference(
            repository="MSKazemi/idkmesh",
            number=123,
            head_sha="3" * 40,
        )
        with self.assertRaises(GitHubPublicEvidenceError):
            build_github_public_evidence_projection(
                run,
                policy=_policy(),
                candidates={"attempt-1": changed_candidate},
            )

        changed_report = dict(report)
        changed_report["warnings"] = ["changed after retention"]
        with self.assertRaises(GitHubPublicEvidenceError):
            build_github_public_evidence_projection(
                run,
                policy=_policy(),
                evidence_report=changed_report,
            )

    def test_evidence_attempt_must_match_retained_digests(self):
        report = _report()
        report["attempts"][0]["verifier"][
            "verification_semantic_digest"
        ] = DIGEST_D
        run = _run(report=report)
        with self.assertRaises(GitHubPublicEvidenceError):
            build_github_public_evidence_projection(
                run,
                policy=_policy(),
                evidence_report=report,
            )

    def test_without_optional_evidence_projection_remains_valid(self):
        run = ProductSpineRun(
            run_id="run-early",
            request_digest=DIGEST_D,
            project_id="MSKazemi/idkmesh",
            work_unit_id="work/unit",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
        )
        projection = build_github_public_evidence_projection(
            run,
            policy=_policy(),
        )
        jsonschema.Draft202012Validator(self.schema).validate(projection)
        self.assertEqual(projection["attempts"], [])
        self.assertIsNone(projection["evidence_summary"])
        self.assertEqual(
            projection["human_decision_status"],
            "not_recorded",
        )

    def test_json_rendering_is_deterministic(self):
        candidate = _candidate()
        report = _report()
        projection = build_github_public_evidence_projection(
            _run(candidate=candidate, report=report),
            policy=_policy(),
            candidates={"attempt-1": candidate},
            evidence_report=report,
        )
        first = render_github_public_evidence_json(projection)
        second = render_github_public_evidence_json(projection)
        self.assertEqual(first, second)

    def test_policy_accepts_owner_name_and_rejects_malformed_repository(self):
        self.assertEqual(_policy().repository, "MSKazemi/idkmesh")
        for repository in (
            "MSKazemi",
            "MSKazemi/idkmesh/extra",
            "MSKazemi/idkmesh\n",
            "MSKazemi/idkmesh\\Z",
            "",
        ):
            with self.subTest(repository=repository):
                with self.assertRaises(ValueError):
                    _policy(repository=repository)

    def test_renderer_rejects_mapping_outside_public_whitelist(self):
        candidate = _candidate()
        report = _report()
        projection = build_github_public_evidence_projection(
            _run(candidate=candidate, report=report),
            policy=_policy(),
            candidates={"attempt-1": candidate},
            evidence_report=report,
        )

        def mutated(mutate):
            copy = json.loads(json.dumps(projection))
            mutate(copy)
            return copy

        cases = {
            "root_extra": lambda p: p.update(raw_logs="PRIVATE LOG"),
            "run_extra": lambda p: p["run"].update(prompt="PRIVATE PROMPT"),
            "attempt_extra": lambda p: p["attempts"][0].update(
                provider_reference="private-provider-session"
            ),
            "candidate_extra": lambda p: p["attempts"][0]["candidate"].update(
                locator="file:///home/private/out.patch"
            ),
            "summary_extra": lambda p: p["evidence_summary"].update(
                warnings=["private warning"]
            ),
            "authority_raised": lambda p: p["authority"].update(merge=True),
            "authority_falsy_int": lambda p: p["authority"].update(merge=0),
            "privacy_weakened": lambda p: p["privacy"].update(
                raw_logs_included=True
            ),
            "privacy_reclassified": lambda p: p["privacy"].update(
                data_classification="internal"
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(GitHubPublicEvidenceError):
                    render_github_public_evidence_json(mutated(mutate))


if __name__ == "__main__":
    unittest.main()
