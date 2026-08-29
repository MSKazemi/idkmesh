from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

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
        if path.endswith("/pulls/1/files"):
            return [{"filename": "sim/emergence_sim.py"}, {"filename": "docs/README.md"}]
        if path.endswith("/pulls/2/files"):
            return [{"filename": "docs/README.md"}, {"filename": "tools/probe.py"}]
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
        # Pull request 1 is the earliest in the window, so nothing is owned yet, and
        # it never merged, so it never becomes an owner either.
        by_number = {row["number"]: row for row in snapshot["pull_requests"]}
        self.assertEqual([], by_number[1]["changed_file_owners"])
        self.assertEqual([], by_number[2]["changed_file_owners"])
        self.assertEqual(2, by_number[2]["unattributed_changed_files"])

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
                request_json=FakeGitHub(remaining=49),
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

    def test_ownership_follows_the_last_merged_toucher(self):
        class Merged(FakeGitHub):
            def __call__(self, path, token, params=None):
                if path.endswith("/pulls"):
                    rows = super().__call__(path, token, params)
                    for row in rows:
                        if row["number"] == 1:
                            row.update(
                                {
                                    "state": "closed",
                                    "closed_at": "2026-08-01T12:00:00Z",
                                    "merged_at": "2026-08-01T12:00:00Z",
                                }
                            )
                    return rows
                return super().__call__(path, token, params)

        snapshot = collect(
            "MSKazemi/idkmesh",
            "token",
            max_pull_requests=10,
            request_json=Merged(),
            now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        by_number = {row["number"]: row for row in snapshot["pull_requests"]}
        owner_of_readme = by_number[1]["author"]
        # Pull request 1 merged first and touched docs/README.md, so pull request 2
        # inherits exactly one attribution for that path and none for its new file.
        self.assertEqual([owner_of_readme], by_number[2]["changed_file_owners"])
        self.assertEqual(1, by_number[2]["unattributed_changed_files"])
        self.assertEqual(
            1, snapshot["collection"]["ownership"]["attributed_files"]
        )

    def test_structural_debt_attaches_to_the_last_pull_request_touching_the_path(self):
        report = {
            "findings": [
                {
                    "category": "orphan_document",
                    "severity": "warning",
                    "source_path": "docs/README.md",
                    "line": 0,
                },
                {
                    "category": "orphan_document",
                    "severity": "warning",
                    "source_path": "docs/never-touched.md",
                    "line": 0,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observatory.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            snapshot = collect(
                "MSKazemi/idkmesh",
                "token",
                max_pull_requests=10,
                request_json=FakeGitHub(),
                now=datetime(2026, 8, 10, tzinfo=timezone.utc),
                structural_debt_report=path,
            )

        by_number = {row["number"]: row for row in snapshot["pull_requests"]}
        # Both pull requests touch docs/README.md; the later one carries the finding.
        self.assertEqual([], by_number[1]["structural_debt_finding_ids"])
        self.assertEqual(1, len(by_number[2]["structural_debt_finding_ids"]))
        debt = snapshot["collection"]["structural_debt"]
        self.assertEqual(2, debt["findings_loaded"])
        self.assertEqual(1, debt["findings_attributed"])
        self.assertEqual(["docs/never-touched.md"], debt["unattributed_paths"])
        # One finding never reached a pull request, so the inventory is not complete
        # and the snapshot must say so rather than let the observable undercount.
        self.assertFalse(snapshot["inventory_complete"])
        self.assertIn(
            "structural_debt_findings_outside_the_window_are_unattributed",
            snapshot["collection"]["limitations"],
        )

        result = analyze(snapshot)
        self.assertEqual(1, result["metrics"]["structural_debt"]["observed_findings"])
        self.assertFalse(result["metrics"]["structural_debt"]["inventory_complete"])

    def test_fully_attributed_report_marks_the_inventory_complete(self):
        report = {
            "findings": [
                {
                    "category": "orphan_document",
                    "severity": "warning",
                    "source_path": "tools/probe.py",
                    "line": 12,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observatory.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            snapshot = collect(
                "MSKazemi/idkmesh",
                "token",
                max_pull_requests=10,
                request_json=FakeGitHub(),
                now=datetime(2026, 8, 10, tzinfo=timezone.utc),
                structural_debt_report=path,
            )
        self.assertTrue(snapshot["inventory_complete"])
        self.assertNotIn(
            "structural_debt_inventory_not_collected",
            snapshot["collection"]["limitations"],
        )

    def test_finding_identity_is_stable_across_repeated_collection(self):
        report = {
            "findings": [
                {
                    "category": "orphan_document",
                    "severity": "warning",
                    "source_path": "tools/probe.py",
                    "line": 12,
                }
            ]
        }
        seen = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observatory.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            for _ in range(2):
                snapshot = collect(
                    "MSKazemi/idkmesh",
                    "token",
                    max_pull_requests=10,
                    request_json=FakeGitHub(),
                    now=datetime(2026, 8, 10, tzinfo=timezone.utc),
                    structural_debt_report=path,
                )
                seen.append(
                    [row["id"] for row in snapshot["collection"]["structural_debt"]["index"]]
                )
        self.assertEqual(seen[0], seen[1])
        self.assertTrue(all(row.startswith("debt:") for row in seen[0]))

    def test_saturated_changed_file_page_is_flagged_not_silently_partial(self):
        class Saturated(FakeGitHub):
            def __call__(self, path, token, params=None):
                if path.endswith("/pulls/2/files"):
                    return [{"filename": f"src/file{index}.py"} for index in range(100)]
                return super().__call__(path, token, params)

        snapshot = collect(
            "MSKazemi/idkmesh",
            "token",
            max_pull_requests=10,
            request_json=Saturated(),
            now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        by_number = {row["number"]: row for row in snapshot["pull_requests"]}
        self.assertTrue(by_number[2]["changed_files_truncated"])
        self.assertFalse(by_number[1]["changed_files_truncated"])
        self.assertEqual([2], snapshot["collection"]["ownership"]["saturated_file_lists"])
        self.assertIn(
            "changed_file_list_saturated_the_bounded_page_for_some_pull_requests",
            snapshot["collection"]["limitations"],
        )


if __name__ == "__main__":
    unittest.main()
