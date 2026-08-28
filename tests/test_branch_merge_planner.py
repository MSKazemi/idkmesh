import unittest

from tools.branch_merge_planner import PlanError, build_plan


def base_audit(branches):
    return {
        "schema_version": "0.2",
        "repository": "MSKazemi/idkmesh",
        "default_branch": "main",
        "default_branch_protected": False,
        "generated_at": "2026-08-28T00:00:00Z",
        "authority": {
            "read_only": True,
            "merge": False,
            "delete_branch": False,
            "approve": False,
            "repository_settings": False,
        },
        "branches": branches,
    }


def branch(name, state, *, ahead=0, behind=0, prs=None, direct=False):
    return {
        "branch": name,
        "head_sha": (name.encode("utf-8").hex() + "0" * 40)[:40],
        "state": state,
        "direct_merge_allowed": direct,
        "ahead_by": ahead,
        "behind_by": behind,
        "pull_requests": prs or [],
    }


class BranchMergePlannerTests(unittest.TestCase):
    def test_active_review_is_candidate_but_never_authorized(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch("feature/review", "active-review-pr", ahead=2, prs=[12]),
                ]
            )
        )
        item = next(item for item in plan["items"] if item["branch"] == "feature/review")
        self.assertTrue(item["integration_candidate"])
        self.assertFalse(item["merge_authorized"])
        self.assertFalse(item["direct_branch_merge_allowed"])
        self.assertEqual(plan["queues"]["integration_review"], ["feature/review"])

    def test_integrated_branch_is_retirement_not_merge(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch("feature/already-merged", "integrated-via-pr", ahead=3, behind=5, prs=[7]),
                ]
            )
        )
        item = next(item for item in plan["items"] if item["branch"] == "feature/already-merged")
        self.assertEqual(item["lane"], "retirement")
        self.assertTrue(item["retirement_candidate"])
        self.assertFalse(item["integration_candidate"])

    def test_stale_unique_work_requires_extraction(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch("old/diverged", "orphan-diverged", ahead=4, behind=20),
                    branch("old/closed", "closed-unmerged-unique-work", ahead=2, behind=11, prs=[3]),
                ]
            )
        )
        lanes = {item["branch"]: item["lane"] for item in plan["items"]}
        self.assertEqual(lanes["old/diverged"], "extract-or-retire")
        self.assertEqual(lanes["old/closed"], "extract-or-retire")
        self.assertEqual(plan["summary"]["integration_review_candidates"], 0)

    def test_evidence_branch_is_preserved_before_cleanup(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch(
                        "acceptance/negative-runtime",
                        "closed-unmerged-evidence-branch",
                        ahead=1,
                        behind=30,
                        prs=[99],
                    ),
                ]
            )
        )
        item = next(item for item in plan["items"] if item["branch"] != "main")
        self.assertEqual(item["lane"], "evidence-preservation")
        self.assertFalse(item["retirement_candidate"])
        self.assertFalse(item["integration_candidate"])

    def test_draft_and_head_mismatch_are_holds(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch("feature/draft", "active-draft-pr", prs=[4]),
                    branch("feature/moved", "open-pr-head-mismatch", prs=[5]),
                ]
            )
        )
        holds = set(plan["queues"]["holds"])
        self.assertEqual(holds, {"feature/draft", "feature/moved"})

    def test_direct_merge_signal_fails_closed(self):
        with self.assertRaises(PlanError):
            build_plan(
                base_audit(
                    [
                        branch("main", "canonical"),
                        branch("unsafe", "active-review-pr", prs=[1], direct=True),
                    ]
                )
            )

    def test_missing_read_only_authority_fails_closed(self):
        audit = base_audit([branch("main", "canonical")])
        audit["authority"]["read_only"] = False
        with self.assertRaises(PlanError):
            build_plan(audit)

    def test_unknown_new_state_fails_closed_until_planner_is_updated(self):
        with self.assertRaises(PlanError):
            build_plan(
                base_audit(
                    [
                        branch("main", "canonical"),
                        branch("new/state", "future-unsafe-state"),
                    ]
                )
            )

    def test_lane_order_is_deterministic(self):
        plan = build_plan(
            base_audit(
                [
                    branch("main", "canonical"),
                    branch("retire/z", "integrated-via-pr", behind=100, prs=[9]),
                    branch("review/a", "active-review-pr", behind=2, prs=[1]),
                    branch("extract/b", "orphan-diverged", ahead=1, behind=20),
                    branch("extract/a", "orphan-diverged", ahead=1, behind=5),
                ]
            )
        )
        names = [item["branch"] for item in plan["items"]]
        self.assertLess(names.index("review/a"), names.index("extract/b"))
        self.assertLess(names.index("extract/b"), names.index("extract/a"))
        self.assertLess(names.index("extract/a"), names.index("retire/z"))


if __name__ == "__main__":
    unittest.main()
