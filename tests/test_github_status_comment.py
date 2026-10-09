"""Tests for C14-B idempotently updated GitHub run-status comments."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.github_status_comment import (
    GitHubRestStatusCommentTransport,
    GitHubStatusCommentPublishError,
    GitHubStatusCommentRecoveryRequired,
    render_github_run_status_comment,
    sync_github_run_status_comment,
)
from idkmesh.github_status_update import GitHubIssueComment, GitHubRunStatus


def _status(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "issue_number": 609,
        "run_id": "run-c14-b-001",
        "state": "dispatched",
        "work_unit_id": "github/mskazemi/idkmesh/issue-609",
        "work_unit_digest": "sha256:" + "a" * 64,
        "routing_digest": "sha256:" + "b" * 64,
    }
    values.update(overrides)
    return GitHubRunStatus(**values)


class FakeTransport:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []
        self.fail_create = False
        self.fail_updates_remaining = 0

    def create_issue_comment(self, *, repository, issue_number, body):
        self.create_calls.append((repository, issue_number, body))
        if self.fail_create:
            raise RuntimeError("ambiguous create failure")
        return GitHubIssueComment(
            comment_id=7001,
            html_url=(
                "https://github.com/MSKazemi/idkmesh/"
                "issues/609#issuecomment-7001"
            ),
        )

    def update_issue_comment(
        self,
        *,
        repository,
        issue_number,
        comment_id,
        body,
    ):
        self.update_calls.append(
            (repository, issue_number, comment_id, body)
        )
        if self.fail_updates_remaining:
            self.fail_updates_remaining -= 1
            raise RuntimeError("ambiguous update failure")
        return GitHubIssueComment(
            comment_id=comment_id,
            html_url=(
                "https://github.com/MSKazemi/idkmesh/"
                "issues/609#issuecomment-7001"
            ),
        )


class FakeResponse:
    def __init__(self, payload, *, status):
        self.status = status
        self._payload = payload

    def read(self, amount=-1):
        return self._payload[:amount]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GitHubStatusCommentSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalMetadataStore(
            Path(self.temp.name) / "state.sqlite"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_first_sync_creates_one_comment_and_exact_replay_is_noop(self):
        transport = FakeTransport()
        first = sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
        )
        second = sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:01:00Z",
        )

        self.assertEqual(first.action, "created")
        self.assertEqual(second.action, "replayed")
        self.assertEqual(first.comment_id, second.comment_id)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.update_calls, [])
        self.assertEqual(
            second.to_dict()["github_mutation"],
            "none",
        )
        self.assertFalse(second.to_dict()["merge"])

    def test_changed_state_updates_same_comment_instead_of_creating_second(self):
        transport = FakeTransport()
        first = sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
        )
        updated = sync_github_run_status_comment(
            store=self.store,
            status=_status(state="candidate_observed"),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
            updated_at="2026-10-08T20:02:00Z",
        )

        self.assertEqual(updated.action, "updated")
        self.assertEqual(updated.comment_id, first.comment_id)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(len(transport.update_calls), 1)
        self.assertIn(
            "candidate_observed",
            transport.update_calls[0][3],
        )

    def test_durable_evidence_link_is_repository_scoped_and_updates_in_place(self):
        transport = FakeTransport()
        sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
        )
        url = (
            "https://github.com/MSKazemi/idkmesh/blob/"
            + "1" * 40
            + "/evidence/run-001.json"
        )
        result = sync_github_run_status_comment(
            store=self.store,
            status=_status(state="candidate_observed"),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
            updated_at="2026-10-08T20:03:00Z",
            durable_evidence_url=url,
        )

        self.assertEqual(result.action, "updated")
        self.assertIn(url, transport.update_calls[-1][3])
        bad_urls = (
            "https://example.com/private/evidence",
            (
                "https://github.com/MSKazemi/idkmesh/blob/"
                "main/evidence/run-001.json"
            ),
            (
                "https://github.com/MSKazemi/other/blob/"
                + "1" * 40
                + "/evidence/run-001.json"
            ),
        )
        for bad_url in bad_urls:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(ValueError):
                    render_github_run_status_comment(
                        _status(),
                        durable_evidence_url=bad_url,
                    )

    def test_ambiguous_create_failure_never_automatically_posts_again(self):
        transport = FakeTransport()
        transport.fail_create = True

        with self.assertRaises(GitHubStatusCommentPublishError):
            sync_github_run_status_comment(
                store=self.store,
                status=_status(),
                transport=transport,
                created_at="2026-10-08T20:00:00Z",
            )
        self.assertEqual(len(transport.create_calls), 1)

        transport.fail_create = False
        with self.assertRaises(GitHubStatusCommentRecoveryRequired):
            sync_github_run_status_comment(
                store=self.store,
                status=_status(),
                transport=transport,
                created_at="2026-10-08T20:01:00Z",
            )
        self.assertEqual(len(transport.create_calls), 1)

    def test_failed_patch_can_retry_same_projection_without_second_create(self):
        transport = FakeTransport()
        sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
        )
        transport.fail_updates_remaining = 1
        desired = _status(state="candidate_observed")

        with self.assertRaises(GitHubStatusCommentPublishError):
            sync_github_run_status_comment(
                store=self.store,
                status=desired,
                transport=transport,
                created_at="2026-10-08T20:00:00Z",
                updated_at="2026-10-08T20:02:00Z",
            )

        retry = sync_github_run_status_comment(
            store=self.store,
            status=desired,
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
            updated_at="2026-10-08T20:03:00Z",
        )
        self.assertEqual(retry.action, "updated")
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(len(transport.update_calls), 2)

    def test_different_projection_is_blocked_while_patch_is_unreconciled(self):
        transport = FakeTransport()
        sync_github_run_status_comment(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-10-08T20:00:00Z",
        )
        transport.fail_updates_remaining = 1
        with self.assertRaises(GitHubStatusCommentPublishError):
            sync_github_run_status_comment(
                store=self.store,
                status=_status(state="candidate_observed"),
                transport=transport,
                created_at="2026-10-08T20:00:00Z",
                updated_at="2026-10-08T20:02:00Z",
            )

        with self.assertRaises(GitHubStatusCommentRecoveryRequired):
            sync_github_run_status_comment(
                store=self.store,
                status=_status(state="normalized"),
                transport=transport,
                created_at="2026-10-08T20:00:00Z",
                updated_at="2026-10-08T20:03:00Z",
            )
        self.assertEqual(len(transport.update_calls), 1)

    def test_marker_stays_stable_across_comment_updates(self):
        first = render_github_run_status_comment(_status())
        second = render_github_run_status_comment(
            _status(state="candidate_observed")
        )
        first_marker = first.splitlines()[0]
        second_marker = second.splitlines()[0]
        self.assertEqual(first_marker, second_marker)
        self.assertNotIn(_status().run_id, first_marker)


class GitHubRestStatusCommentTransportTests(unittest.TestCase):
    def test_create_accepts_pull_request_comment_html_url(self):
        seen = {}

        def opener(request, timeout):
            seen["method"] = request.method
            seen["url"] = request.full_url
            seen["headers"] = dict(request.header_items())
            payload = json.dumps(
                {
                    "id": 8123,
                    "html_url": (
                        "https://github.com/MSKazemi/idkmesh/"
                        "pull/609#issuecomment-8123"
                    ),
                }
            ).encode()
            return FakeResponse(payload, status=201)

        token = "status-comment-test-token"
        transport = GitHubRestStatusCommentTransport(
            token=token,
            opener=opener,
        )
        comment = transport.create_issue_comment(
            repository="MSKazemi/idkmesh",
            issue_number=609,
            body="bounded body",
        )

        self.assertEqual(comment.comment_id, 8123)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["url"],
            (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "issues/609/comments"
            ),
        )
        self.assertIn(f"Bearer {token}", seen["headers"].values())

    def test_update_uses_patch_on_retained_comment_and_accepts_pr_url(self):
        seen = {}

        def opener(request, timeout):
            seen["method"] = request.method
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode())
            payload = json.dumps(
                {
                    "id": 8123,
                    "html_url": (
                        "https://github.com/MSKazemi/idkmesh/"
                        "pull/609#issuecomment-8123"
                    ),
                }
            ).encode()
            return FakeResponse(payload, status=200)

        transport = GitHubRestStatusCommentTransport(
            token="status-comment-test-token",
            opener=opener,
        )
        comment = transport.update_issue_comment(
            repository="MSKazemi/idkmesh",
            issue_number=609,
            comment_id=8123,
            body="new bounded status",
        )

        self.assertEqual(comment.comment_id, 8123)
        self.assertEqual(seen["method"], "PATCH")
        self.assertEqual(
            seen["url"],
            (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "issues/comments/8123"
            ),
        )
        self.assertEqual(seen["body"], {"body": "new bounded status"})

    def test_update_rejects_comment_identity_from_other_target(self):
        def opener(request, timeout):
            payload = json.dumps(
                {
                    "id": 8123,
                    "html_url": (
                        "https://github.com/other/repo/"
                        "issues/609#issuecomment-8123"
                    ),
                }
            ).encode()
            return FakeResponse(payload, status=200)

        transport = GitHubRestStatusCommentTransport(
            token="status-comment-test-token",
            opener=opener,
        )
        with self.assertRaises(ConnectorError):
            transport.update_issue_comment(
                repository="MSKazemi/idkmesh",
                issue_number=609,
                comment_id=8123,
                body="new bounded status",
            )


if __name__ == "__main__":
    unittest.main()
