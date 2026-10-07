from copy import deepcopy
import unittest

from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.github_actions_summary import (
    GitHubActionsSummaryError,
    render_github_actions_summary,
)
from idkmesh.product_spine import AttemptProjection, ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
DIGEST_E = "sha256:" + "e" * 64
SOURCE_REVISION = "1" * 40


def _candidate(head_sha="2" * 40):
    return GitHubPullRequestCandidateReference(
        repository="MSKazemi/idkmesh",
        number=123,
        head_sha=head_sha,
    )


def _report(*, check_id="pytest", check_status="passed"):
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-run-evidence-report",
        "run_id": "run-001",
        "source_run_kind": "idkmesh-two-attempt-run",
        "source_run_digest": DIGEST_C,
        "source_config_digest": DIGEST_D,
        "orchestrator_version": "0.2",
        "work_unit": {
            "id": "github/mskazemi/idkmesh/issue-609",
            "version": 1,
            "digest": DIGEST_A,
        },
        "verifier_policy_digest": DIGEST_E,
        "attempts": [
            {
                "attempt_id": "attempt-1",
                "order": 1,
                "worker_adapter": "jules",
                "state": "verified",
                "evidence_state": "supported",
                "worker": {
                    "id": "worker-1",
                    "status": "succeeded",
                    "result_manifest_id": "result-1",
                    "result_manifest_digest": DIGEST_B,
                },
                "verifier": {
                    "id": "verifier-1",
                    "status": "completed",
                    "recommendation": "accept_candidate",
                    "verification_semantic_digest": DIGEST_C,
                    "checks": [
                        {
                            "id": check_id,
                            "status": check_status,
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
            "Generated evidence is decision support only; this report does not select, accept, merge, or integrate a candidate."
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
    attempt = AttemptProjection(
        attempt_id="attempt-1",
        order=1,
        connector_id="jules",
        state="verified",
        candidate_reference_digest=canonical_digest(candidate.to_dict()),
        result_manifest_digest=DIGEST_B,
        verification_semantic_digest=DIGEST_C,
    )
    return ProductSpineRun(
        run_id="run-001",
        request_digest=DIGEST_D,
        project_id="MSKazemi/idkmesh",
        work_unit_id="github/mskazemi/idkmesh/issue-609",
        work_unit_version=1,
        work_unit_digest=DIGEST_A,
        source_revision=SOURCE_REVISION,
        authority_mode="agent_candidate",
        routing_policy_version="routing-v1",
        state="evidence_ready",
        admitted_connectors=("jules",),
        attempts=(attempt,),
        evidence_report_digest=canonical_digest(report),
    )


class GitHubActionsSummaryTests(unittest.TestCase):
    def test_renders_bound_run_candidate_verification_checks_and_authority(self):
        candidate = _candidate()
        report = _report()
        run = _run(candidate=candidate, report=report)

        rendered = render_github_actions_summary(
            run,
            candidates={"attempt-1": candidate},
            evidence_report=report,
            durable_evidence_url=(
                "https://github.com/MSKazemi/idkmesh/blob/main/"
                "results/example/evidence-report.json"
            ),
        )

        self.assertIn("IDKMesh run summary", rendered)
        self.assertIn(run.run_id, rendered)
        self.assertIn(SOURCE_REVISION, rendered)
        self.assertIn("PR #123 @ 222222222222", rendered)
        self.assertIn("accept_candidate", rendered)
        self.assertIn("`pytest` — `passed` (required)", rendered)
        self.assertIn("Canonical-state write: **blocked**", rendered)
        self.assertIn("Merge: **blocked**", rendered)
        self.assertIn("pending explicit human/governance decision", rendered)
        self.assertIn("open retained evidence", rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), 64 * 1024)

    def test_output_is_deterministic(self):
        candidate = _candidate()
        report = _report()
        run = _run(candidate=candidate, report=report)
        first = render_github_actions_summary(
            run,
            candidates={"attempt-1": candidate},
            evidence_report=report,
        )
        second = render_github_actions_summary(
            run,
            candidates={"attempt-1": candidate},
            evidence_report=report,
        )
        self.assertEqual(first, second)

    def test_candidate_must_match_retained_digest(self):
        retained = _candidate()
        report = _report()
        run = _run(candidate=retained, report=report)
        different = _candidate(head_sha="3" * 40)

        with self.assertRaises(GitHubActionsSummaryError) as caught:
            render_github_actions_summary(
                run,
                candidates={"attempt-1": different},
            )

        self.assertIn("does not match retained digest", str(caught.exception))

    def test_evidence_report_must_match_retained_digest(self):
        report = _report()
        run = _run(report=report)
        changed = deepcopy(report)
        changed["warnings"].append("changed after retention")

        with self.assertRaises(GitHubActionsSummaryError) as caught:
            render_github_actions_summary(run, evidence_report=changed)

        self.assertIn("does not match the retained digest", str(caught.exception))

    def test_evidence_detail_must_bind_to_retained_attempt_digests(self):
        report = _report()
        report["attempts"][0]["verifier"]["verification_semantic_digest"] = DIGEST_D
        run = _run(report=report)

        with self.assertRaises(GitHubActionsSummaryError) as caught:
            render_github_actions_summary(run, evidence_report=report)

        self.assertIn("does not match the retained attempt", str(caught.exception))

    def test_untrusted_check_text_is_escaped_before_markdown_rendering(self):
        report = _report(
            check_id="<script>alert(1)</script>|line\nnext",
            check_status="pass|ok",
        )
        run = _run(report=report)

        rendered = render_github_actions_summary(run, evidence_report=report)

        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;\\|line next", rendered)
        self.assertIn("pass\\|ok", rendered)

    def test_non_github_durable_link_fails_closed(self):
        report = _report()
        run = _run(report=report)
        with self.assertRaises(GitHubActionsSummaryError):
            render_github_actions_summary(
                run,
                evidence_report=report,
                durable_evidence_url="https://example.com/evidence.json",
            )

    def test_summary_without_optional_details_remains_truthful(self):
        run = ProductSpineRun(
            run_id="run-early",
            request_digest=DIGEST_D,
            project_id="MSKazemi/idkmesh",
            work_unit_id="github/mskazemi/idkmesh/issue-609",
            work_unit_version=1,
            work_unit_digest=DIGEST_A,
            source_revision=SOURCE_REVISION,
            authority_mode="agent_candidate",
            routing_policy_version="routing-v1",
        )

        rendered = render_github_actions_summary(run)

        self.assertIn("no attempt yet", rendered)
        self.assertIn("Durable evidence link: not supplied", rendered)
        self.assertIn("not yet recorded", rendered)


if __name__ == "__main__":
    unittest.main()
