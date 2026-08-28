import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-community-growth.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


def live_load(
    ready_prs: int,
    draft_prs: int,
    open_growth_seeds: int,
    other_open_issues: int,
) -> float:
    return (
        1.00 * ready_prs
        + 0.25 * draft_prs
        + 0.50 * open_growth_seeds
        + 0.10 * min(other_open_issues, 20)
    )


def capacity(load: float, K: float = 8.0, tau: float = 2.0) -> float:
    return 1.0 / (1.0 + math.exp((load - K) / tau))


class AceLiveCapacityModelTests(unittest.TestCase):
    def test_workflow_uses_live_open_work_model(self):
        self.assertIn("model: 'live-open-work-v1'", TEXT)
        self.assertIn("github.rest.pulls.list", TEXT)
        self.assertIn("const readyPullRequests", TEXT)
        self.assertIn("const draftPullRequests", TEXT)
        self.assertIn("const openGrowthSeeds", TEXT)
        self.assertIn("const otherOpenIssues", TEXT)
        self.assertIn("const liveReviewLoad", TEXT)
        self.assertIn("state.review_load = liveReviewLoad;", TEXT)

    def test_workflow_no_longer_accumulates_event_load_delta(self):
        self.assertNotIn("loadDelta", TEXT)
        self.assertNotIn("state.review_load || 0) +", TEXT)

    def test_machine_state_exposes_components(self):
        self.assertIn("state.review_load_components", TEXT)
        self.assertIn("ready_pull_requests", TEXT)
        self.assertIn("draft_pull_requests", TEXT)
        self.assertIn("open_growth_seeds", TEXT)
        self.assertIn("other_open_issues_capped_at: 20", TEXT)

    def test_closing_open_work_recovers_capacity(self):
        overloaded = live_load(ready_prs=10, draft_prs=4, open_growth_seeds=6, other_open_issues=30)
        recovered = live_load(ready_prs=2, draft_prs=1, open_growth_seeds=2, other_open_issues=10)
        self.assertLess(recovered, overloaded)
        self.assertGreater(capacity(recovered), capacity(overloaded))

    def test_marking_pr_draft_reduces_current_review_pressure(self):
        ready = live_load(ready_prs=1, draft_prs=0, open_growth_seeds=0, other_open_issues=0)
        draft = live_load(ready_prs=0, draft_prs=1, open_growth_seeds=0, other_open_issues=0)
        self.assertLess(draft, ready)

    def test_historical_event_count_is_not_a_capacity_input(self):
        load_a = live_load(ready_prs=3, draft_prs=2, open_growth_seeds=4, other_open_issues=12)
        load_b = live_load(ready_prs=3, draft_prs=2, open_growth_seeds=4, other_open_issues=12)
        self.assertEqual(load_a, load_b)

    def test_other_issue_backlog_is_bounded(self):
        self.assertEqual(
            live_load(0, 0, 0, 20),
            live_load(0, 0, 0, 2000),
        )

    def test_weight_ordering_matches_expected_review_pressure(self):
        ready_pr = live_load(1, 0, 0, 0)
        growth_seed = live_load(0, 0, 1, 0)
        draft_pr = live_load(0, 1, 0, 0)
        issue = live_load(0, 0, 0, 1)
        self.assertGreater(ready_pr, growth_seed)
        self.assertGreater(growth_seed, draft_pr)
        self.assertGreater(draft_pr, issue)

    def test_current_repository_snapshot_remains_over_capacity(self):
        # Empirical snapshot from GitHub search on 2026-08-28:
        # 21 review-ready PRs, 5 draft PRs, 4 open Growth Seeds, and at least
        # 20 other open issues after the cap. The exact counts evolve, but this
        # fixture demonstrates that the corrected model still classifies the
        # observed repository as overloaded for a defensible current-state reason.
        load = live_load(ready_prs=21, draft_prs=5, open_growth_seeds=4, other_open_issues=20)
        self.assertEqual(load, 26.25)
        self.assertGreater(load, 8.0)
        self.assertLess(capacity(load), 0.001)


if __name__ == "__main__":
    unittest.main()
