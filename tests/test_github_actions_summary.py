import unittest

from idkmesh.github_actions_summary import (
    GitHubActionsCheck,
    GitHubActionsRunSummary,
)


BASE_SHA = "A" * 40
CANDIDATE_SHA = "B" * 40
DIGEST = "sha256:" + "c" * 64


def _summary(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "work_unit_id": "github/mskazemi/idkmesh/issue-77",
        "work_unit_digest": DIGEST,
        "run_id": "github-dispatch/0123456789abcdef01234567",
        "run_state": "awaiting_human_decision",
        "attempt_id": "attempt-1",
        "attempt_state": "verified",
        "source_revision": BASE_SHA,
        "candidate_revision": CANDIDATE_SHA,
        "connector_id": "agent-a",
        "worker_id": "worker/agent-a",
        "verification_status": "passed",
        "checks": (
            GitHubActionsCheck("unit", "passed", True),
            GitHubActionsCheck("lint", "passed", True),
        ),
        "evidence_reference": "results/runs/run-77/evidence.json",
    }
    values.update(overrides)
    return GitHubActionsRunSummary(**values)


class GitHubActionsRunSummaryTests(unittest.TestCase):
    def test_complete_summary_is_deterministic_and_public_safe(self):
        summary = _summary()
        first = summary.render_markdown()
        second = summary.render_markdown()

        self.assertEqual(first, second)
        self.assertIn("`" + BASE_SHA.lower() + "`", first)
        self.assertIn("`" + CANDIDATE_SHA.lower() + "`", first)
        self.assertIn("`awaiting_human_decision`", first)
        self.assertIn("`passed`", first)
        self.assertIn("`pending`", first)
        self.assertIn("Candidate acceptance | `no`", first)
        self.assertIn("Git push | `no`", first)
        self.assertIn("Merge | `no`", first)
        self.assertNotIn("provider response", first.casefold())
        self.assertNotIn("prompt", first.casefold())
        self.assertNotIn("credential", first.casefold())

    def test_checks_are_sorted_and_duplicate_ids_fail_closed(self):
        summary = _summary(
            checks=(
                GitHubActionsCheck("z-check", "passed", False),
                GitHubActionsCheck("a-check", "failed", True),
            )
        )
        rendered = summary.render_markdown()
        self.assertLess(rendered.index("`a-check`"), rendered.index("`z-check`"))

        with self.assertRaisesRegex(ValueError, "duplicate"):
            _summary(
                checks=(
                    GitHubActionsCheck("same", "passed", True),
                    GitHubActionsCheck("same", "failed", True),
                )
            )

    def test_candidate_sha_is_required_after_candidate_observation(self):
        with self.assertRaisesRegex(ValueError, "candidate_revision"):
            _summary(candidate_revision=None)

        pre_candidate = _summary(
            run_state="dispatched",
            attempt_state="dispatched",
            candidate_revision=None,
            verification_status=None,
            checks=(),
            evidence_reference=None,
        )
        rendered = pre_candidate.render_markdown()
        self.assertIn("Candidate SHA | `not available`", rendered)
        self.assertIn("Candidate state | `not_observed`", rendered)
        self.assertIn("Verification state | `not_started`", rendered)
        self.assertIn("Human decision state | `not_ready`", rendered)

    def test_verification_status_cannot_be_claimed_before_verified_attempt(self):
        with self.assertRaisesRegex(ValueError, "only valid"):
            _summary(
                run_state="verification_requested",
                attempt_state="verification_requested",
                verification_status="passed",
            )
        with self.assertRaisesRegex(ValueError, "requires verification_status"):
            _summary(verification_status=None)

    def test_markdown_delimiters_and_invalid_canonical_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Markdown"):
            _summary(worker_id="bad`worker")
        with self.assertRaisesRegex(ValueError, "owner/name"):
            _summary(repository="not-a-repository")
        with self.assertRaisesRegex(ValueError, "sha256"):
            _summary(work_unit_digest="bad")
        with self.assertRaisesRegex(ValueError, "Git object"):
            _summary(source_revision="main")
        with self.assertRaisesRegex(ValueError, "Product Spine run state"):
            _summary(run_state="merged")

    def test_cancelled_summary_does_not_invent_human_decision(self):
        summary = _summary(
            run_state="cancelled",
            attempt_state="cancelled",
            verification_status=None,
            checks=(),
        )
        rendered = summary.render_markdown()
        self.assertIn("Human decision state | `not_applicable`", rendered)
        self.assertIn("Verification state | `cancelled`", rendered)
        self.assertIn(
            "Candidate state | `retained_before_cancellation`",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
