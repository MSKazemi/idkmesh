from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from scripts.collaboration_observables import analyze
from scripts.collaboration_snapshot import GitHubObservationUnavailable, collect


class FakeGitHub:
    def __init__(self, remaining: int = 5000):
        self.remaining = remaining

    def __call__(self, path, _token, _params=None):
        if path == "/rate_limit":
            return {"resources": {"core": {"remaining": self.remaining}}}
        if path.endswith("/pulls"):
            return [
                {
                    "number": 2,
                    "user": {"login": "external-person", "type": "User"},
                    "created_at": "2026-08-02T00:00:00Z",
                    "closed_at": "2026-08-04T00:00:00Z",
                    "merged_at": "2026-08-04T00:00:00Z",
                    "state": "closed",
                    "draft": False,
                    "head": {"sha": "head-2"},
                },
                {
                    "number": 1,
                    "user": {"login": "MSKazemi", "type": "User"},
                    "created_at": "2026-08-01T00:00:00Z",
                    "closed_at": None,
                    "merged_at": None,
                    "state": "open",
                    "draft": False,
                    "head": {"sha": "head-1"},
                },
            ]
        if path.endswith("/issues/1/timeline"):
            return [{"event": "ready_for_review", "created_at": "2026-08-01T06:00:00Z"}]
        if path.endswith("/issues/2/timeline"):
            return []
        if path.endswith("/pulls/1/reviews"):
            return [
                {"state": "APPROVED", "submitted_at": "2026-08-01T07:00:00Z", "body": "", "user": {"login": "MSKazemi", "type": "User"}},
                {"state": "COMMENTED", "submitted_at": "2026-08-01T08:00:00Z", "body": "", "user": {"login": "reviewer", "type": "User"}},
                {"state": "CHANGES_REQUESTED", "submitted_at": "2026-08-01T09:00:00Z", "body": "blocker", "user": {"login": "reviewer", "type": "User"}},
            ]
        if path.endswith("/pulls/2/reviews"):
            return [{"state": "APPROVED", "submitted_at": "2026-08-03T00:00:00Z", "body": "ok", "user": {"login": "MSKazemi", "type": "User"}}]
        if path.endswith("/commits/head-1/check-runs"):
            return {"check_runs": [{"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "failure"}]}
        if path.endswith("/commits/head-2/check-runs"):
            return {"check_runs": [{"status": "completed", "conclusion": "neutral"}]}
        raise AssertionError(path)


class CollaborationSnapshotTests(unittest.TestCase):
    def test_live_window_is_pseudonymized_and_analyzable(self):
        snapshot = collect(
            "MSKazemi/idkmesh",
            "token",
            max_pull_requests=10,
            request_json=FakeGitHub(),
            now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        serialized = json.dumps(snapshot)
        self.assertNotIn("external-person", serialized)
        actors = {
            row["author"]
            for row in snapshot["pull_requests"]
        } | {
            reviewer
            for row in snapshot["pull_requests"]
            for reviewer in row["independent_reviewers"]
        }
        self.assertTrue(all(actor.startswith("actor:") for actor in actors))
        self.assertEqual(2, len(snapshot["pull_requests"]))
        self.assertEqual(1, len(snapshot["contributors"]))
        self.assertFalse(snapshot["inventory_complete"])
        self.assertFalse(snapshot["collection"]["strategy_outcomes_classified"])

        result = analyze(snapshot)
        self.assertEqual(2, result["metrics"]["first_independent_review_latency"]["samples"])
        self.assertEqual(0.5, result["metrics"]["ci_evidence"]["posterior_mean"])
        self.assertEqual([], result["evidence_derived_strategy_priors"])

    def test_insufficient_api_budget_fails_before_collection(self):
        with self.assertRaisesRegex(GitHubObservationUnavailable, "below required reserve"):
            collect(
                "MSKazemi/idkmesh",
                "token",
                max_pull_requests=10,
                request_json=FakeGitHub(remaining=39),
                now=datetime(2026, 8, 10, tzinfo=timezone.utc),
            )

    def test_page_saturation_fails_closed(self):
        class Saturated(FakeGitHub):
            def __call__(self, path, token, params=None):
                if path.endswith("/pulls/1/reviews"):
                    return [{} for _ in range(100)]
                return super().__call__(path, token, params)

        with self.assertRaisesRegex(GitHubObservationUnavailable, "exceeds the bounded page"):
            collect(
                "MSKazemi/idkmesh",
                "token",
                max_pull_requests=10,
                request_json=Saturated(),
                now=datetime(2026, 8, 10, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
