from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import branch_convergence_audit as audit  # noqa: E402


def pr(
    number: int,
    *,
    state: str = "closed",
    merged: bool = False,
    draft: bool = False,
    head_sha: str | None = None,
) -> audit.PullRequestRef:
    return audit.PullRequestRef(
        number=number,
        state=state,
        merged=merged,
        draft=draft,
        head_sha=head_sha or f"{number:040x}"[-40:],
        base_ref="main",
        updated_at="2026-08-28T00:00:00Z",
    )


class BranchConvergenceAuditTests(unittest.TestCase):
    def decide(
        self,
        branch: str,
        status: str,
        ahead: int,
        behind: int,
        prs: list[audit.PullRequestRef] | None = None,
        *,
        head_sha: str | None = None,
    ) -> audit.BranchDecision:
        decision = audit.classify_branch(
            branch=branch,
            default_branch="main",
            comparison=audit.Comparison(status=status, ahead_by=ahead, behind_by=behind),
            prs=prs or [],
            head_sha=head_sha,
        )
        self.assertFalse(decision.direct_merge_allowed)
        return decision

    def test_main_is_canonical_and_never_source_merged(self) -> None:
        decision = self.decide("main", "identical", 0, 0, head_sha="a" * 40)
        self.assertEqual(decision.state, "canonical")
        self.assertFalse(decision.cleanup_eligible)

    def test_open_draft_pr_is_preserved_for_its_gate(self) -> None:
        head = "9" * 40
        decision = self.decide(
            "integration/canonical-node-current",
            "diverged",
            16,
            30,
            [pr(91, state="open", draft=True, head_sha=head)],
            head_sha=head,
        )
        self.assertEqual(decision.state, "active-draft-pr")
        self.assertFalse(decision.cleanup_eligible)
        self.assertIn("exact-SHA", " ".join(decision.notes))

    def test_open_pr_head_mismatch_fails_closed(self) -> None:
        decision = self.decide(
            "feature/current",
            "ahead",
            3,
            0,
            [pr(200, state="open", head_sha="1" * 40)],
            head_sha="2" * 40,
        )
        self.assertEqual(decision.state, "open-pr-head-mismatch")
        self.assertIn("refresh", decision.recommendation)

    def test_open_ready_pr_uses_pr_merge_gate(self) -> None:
        head = "3" * 40
        decision = self.decide(
            "feature/current",
            "ahead",
            2,
            0,
            [pr(200, state="open", draft=False, head_sha=head)],
            head_sha=head,
        )
        self.assertEqual(decision.state, "active-review-pr")
        self.assertIn("PR merge gate", decision.recommendation)

    def test_merged_pr_wins_over_squash_divergence_when_head_matches(self) -> None:
        head = "4" * 40
        decision = self.decide(
            "feature/squash-merged",
            "diverged",
            5,
            20,
            [pr(113, state="closed", merged=True, head_sha=head)],
            head_sha=head,
        )
        self.assertEqual(decision.state, "integrated-via-pr")
        self.assertTrue(decision.cleanup_eligible)
        self.assertIn("do not merge again", decision.recommendation)

    def test_branch_moved_after_merged_pr_is_not_cleanup_eligible(self) -> None:
        decision = self.decide(
            "feature/reused-after-merge",
            "diverged",
            2,
            3,
            [pr(113, state="closed", merged=True, head_sha="5" * 40)],
            head_sha="6" * 40,
        )
        self.assertEqual(decision.state, "post-merge-branch-moved")
        self.assertFalse(decision.cleanup_eligible)
        self.assertIn("do not merge the branch wholesale", decision.recommendation)

    def test_closed_unmerged_without_unique_commits_is_cleanup_eligible(self) -> None:
        decision = self.decide(
            "feature/obsolete",
            "behind",
            0,
            12,
            [pr(101, state="closed", merged=False)],
        )
        self.assertEqual(decision.state, "closed-unmerged-no-unique-commits")
        self.assertTrue(decision.cleanup_eligible)

    def test_closed_unmerged_divergence_requires_extraction_not_merge(self) -> None:
        decision = self.decide(
            "feature/old-implementation",
            "diverged",
            7,
            30,
            [pr(76, state="closed", merged=False)],
        )
        self.assertEqual(decision.state, "closed-unmerged-unique-work")
        self.assertFalse(decision.cleanup_eligible)
        self.assertIn("extract useful pieces", decision.recommendation)

    def test_closed_acceptance_branch_is_evidence_sensitive(self) -> None:
        decision = self.decide(
            "acceptance/old-runtime-evidence",
            "diverged",
            3,
            40,
            [pr(108, state="closed", merged=False)],
        )
        self.assertEqual(decision.state, "closed-unmerged-evidence-branch")
        self.assertIn("provenance", decision.recommendation)

    def test_closed_reference_branch_is_evidence_sensitive(self) -> None:
        decision = self.decide(
            "experiment/r4-reference",
            "diverged",
            1,
            20,
            [pr(101, state="closed", merged=False)],
        )
        self.assertEqual(decision.state, "closed-unmerged-evidence-branch")

    def test_orphan_behind_branch_can_be_cleaned(self) -> None:
        decision = self.decide("old/no-pr", "behind", 0, 8)
        self.assertEqual(decision.state, "orphan-no-unique-commits")
        self.assertTrue(decision.cleanup_eligible)

    def test_orphan_clean_ahead_must_open_pr(self) -> None:
        decision = self.decide("feature/untracked-work", "ahead", 3, 0)
        self.assertEqual(decision.state, "orphan-clean-ahead")
        self.assertFalse(decision.cleanup_eligible)
        self.assertIn("open a normal PR", decision.recommendation)

    def test_orphan_diverged_requires_current_main_replacement(self) -> None:
        decision = self.decide("feature/old-orphan", "diverged", 4, 22)
        self.assertEqual(decision.state, "orphan-diverged")
        self.assertIn("clean replacement", decision.recommendation)

    def test_multiple_open_prs_fail_closed(self) -> None:
        decision = self.decide(
            "feature/ambiguous",
            "ahead",
            2,
            0,
            [pr(201, state="open"), pr(202, state="open")],
        )
        self.assertEqual(decision.state, "ambiguous-open-prs")
        self.assertFalse(decision.cleanup_eligible)

    def test_branch_ref_encoding_keeps_slash_in_one_api_parameter(self) -> None:
        self.assertEqual(
            audit._encode_ref("feature/a b"),
            "feature%2Fa%20b",
        )


if __name__ == "__main__":
    unittest.main()
