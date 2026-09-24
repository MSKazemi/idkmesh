import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from idkmesh.connector_errors import ConnectorError
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.github_status_update import (
    GitHubIssueComment,
    GitHubRestIssueCommentTransport,
    GitHubRunStatus,
    GitHubStatusConflict,
    GitHubStatusPublishError,
    GitHubStatusRecoveryRequired,
    publish_github_run_status_once,
)


def _status(**overrides):
    values = {
        "repository": "MSKazemi/idkmesh",
        "issue_number": 77,
        "run_id": "github-dispatch/0123456789abcdef01234567",
        "state": "dispatched",
        "work_unit_id": "github/mskazemi/idkmesh/issue-77",
        "work_unit_digest": "sha256:" + "a" * 64,
        "routing_digest": "sha256:" + "b" * 64,
    }
    values.update(overrides)
    return GitHubRunStatus(**values)


class FakeTransport:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def create_issue_comment(
        self,
        *,
        repository,
        issue_number,
        body,
    ):
        self.calls.append(
            (repository, issue_number, body)
        )
        if self.fail:
            raise RuntimeError("network")
        return GitHubIssueComment(
            comment_id=1234,
            html_url=(
                "https://github.com/MSKazemi/idkmesh/"
                "issues/77#issuecomment-1234"
            ),
        )


class FakeResponse:
    def __init__(self, payload, *, status=201):
        self.status = status
        self._payload = payload

    def read(self, amount=-1):
        return self._payload[:amount]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GitHubRunStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalMetadataStore(
            Path(self.temp.name) / "state.sqlite"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_public_body_is_bounded_and_contains_no_provider_or_issue_text(self):
        status = _status()
        body = status.render_body()
        self.assertLessEqual(len(body.encode()), 4096)
        self.assertIn(status.marker, body)
        self.assertIn(status.run_id, body)
        self.assertIn("dispatched", body)
        self.assertNotIn("provider", body.casefold())
        self.assertNotIn("issue body", body.casefold())
        self.assertNotIn("secret", body.casefold())
        self.assertNotIn("token", body.casefold())

    def test_first_publication_creates_one_comment(self):
        transport = FakeTransport()
        result = publish_github_run_status_once(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-09-24T15:10:00Z",
        )
        self.assertTrue(result.created)
        self.assertFalse(result.replayed)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(result.comment_id, 1234)
        self.assertFalse(result.to_dict()["candidate_accepted"])
        self.assertFalse(result.to_dict()["merge_authority"])

    def test_exact_replay_returns_same_comment_without_network(self):
        transport = FakeTransport()
        first = publish_github_run_status_once(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-09-24T15:10:00Z",
        )
        second = publish_github_run_status_once(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-09-24T15:11:00Z",
        )
        self.assertEqual(len(transport.calls), 1)
        self.assertFalse(second.created)
        self.assertTrue(second.replayed)
        self.assertEqual(second.comment_id, first.comment_id)

    def test_same_run_with_different_status_conflicts_before_network(self):
        transport = FakeTransport()
        publish_github_run_status_once(
            store=self.store,
            status=_status(),
            transport=transport,
            created_at="2026-09-24T15:10:00Z",
        )
        with self.assertRaises(GitHubStatusConflict):
            publish_github_run_status_once(
                store=self.store,
                status=_status(state="candidate_observed"),
                transport=transport,
                created_at="2026-09-24T15:11:00Z",
            )
        self.assertEqual(len(transport.calls), 1)

    def test_failed_publication_is_retained_and_not_retried(self):
        transport = FakeTransport(fail=True)
        with self.assertRaises(GitHubStatusPublishError):
            publish_github_run_status_once(
                store=self.store,
                status=_status(),
                transport=transport,
                created_at="2026-09-24T15:10:00Z",
            )
        self.assertEqual(len(transport.calls), 1)

        with self.assertRaises(GitHubStatusRecoveryRequired):
            publish_github_run_status_once(
                store=self.store,
                status=_status(),
                transport=transport,
                created_at="2026-09-24T15:11:00Z",
            )
        self.assertEqual(len(transport.calls), 1)

    def test_status_marker_is_stable_but_does_not_expose_run_id(self):
        status = _status()
        marker = status.marker
        self.assertEqual(marker, _status().marker)
        self.assertNotIn(status.run_id, marker)

    def test_status_validation_is_fail_closed(self):
        with self.assertRaises(ValueError):
            _status(repository="not-repo")
        with self.assertRaises(ValueError):
            _status(issue_number=0)
        with self.assertRaises(ValueError):
            _status(state="merged")
        with self.assertRaises(ValueError):
            _status(work_unit_digest="bad")


class GitHubRestIssueCommentTransportTests(unittest.TestCase):
    def test_rest_transport_accepts_rendered_multiline_status_body(self):
        seen = {}

        def opener(request, timeout):
            seen["body"] = json.loads(request.data.decode())["body"]
            return FakeResponse(
                json.dumps(
                    {
                        "id": 1234,
                        "html_url": (
                            "https://github.com/MSKazemi/idkmesh/"
                            "issues/77#issuecomment-1234"
                        ),
                    }
                ).encode()
            )

        transport = GitHubRestIssueCommentTransport(
            token="safe-test-token-value",
            opener=opener,
        )
        rendered = _status().render_body()
        transport.create_issue_comment(
            repository="MSKazemi/idkmesh",
            issue_number=77,
            body=rendered,
        )
        self.assertEqual(seen["body"], rendered)
        self.assertIn("\n", rendered)

    def test_fixed_host_post_uses_bearer_only_in_request_header(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.method
            seen["headers"] = dict(request.header_items())
            seen["body"] = request.data
            seen["timeout"] = timeout
            payload = json.dumps(
                {
                    "id": 1234,
                    "html_url": (
                        "https://github.com/MSKazemi/idkmesh/"
                        "issues/77#issuecomment-1234"
                    ),
                }
            ).encode()
            return FakeResponse(payload)

        transport = GitHubRestIssueCommentTransport(
            token="github-test-token-value",
            opener=opener,
        )
        comment = transport.create_issue_comment(
            repository="MSKazemi/idkmesh",
            issue_number=77,
            body="bounded status",
        )
        self.assertEqual(
            seen["url"],
            (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "issues/77/comments"
            ),
        )
        self.assertEqual(seen["method"], "POST")
        self.assertIn("Bearer github-test-token-value", seen["headers"].values())
        self.assertNotIn(
            b"github-test-token-value",
            seen["body"],
        )
        self.assertEqual(comment.comment_id, 1234)

    def test_http_auth_error_does_not_expose_token(self):
        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                401,
                "unauthorized",
                {},
                io.BytesIO(b"provider body with secret-ish text"),
            )

        token = "never-echo-this-github-token"
        transport = GitHubRestIssueCommentTransport(
            token=token,
            opener=opener,
        )
        with self.assertRaises(ConnectorError) as caught:
            transport.create_issue_comment(
                repository="MSKazemi/idkmesh",
                issue_number=77,
                body="bounded status",
            )
        self.assertEqual(
            caught.exception.code,
            "authentication_error",
        )
        self.assertNotIn(token, str(caught.exception))
        self.assertNotIn(
            "provider body",
            str(caught.exception),
        )

    def test_oversized_response_fails_closed(self):
        def opener(request, timeout):
            return FakeResponse(b"x" * 20)

        transport = GitHubRestIssueCommentTransport(
            token="safe-test-token-value",
            opener=opener,
            max_response_bytes=10,
        )
        with self.assertRaises(ConnectorError) as caught:
            transport.create_issue_comment(
                repository="MSKazemi/idkmesh",
                issue_number=77,
                body="bounded status",
            )
        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )

    def test_malformed_or_wrong_issue_comment_response_fails_closed(self):
        payloads = (
            b"not-json",
            json.dumps(
                {
                    "id": 1234,
                    "html_url": (
                        "https://github.com/other/repo/"
                        "issues/77#issuecomment-1234"
                    ),
                }
            ).encode(),
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                transport = GitHubRestIssueCommentTransport(
                    token="safe-test-token-value",
                    opener=lambda request, timeout, p=payload: FakeResponse(p),
                )
                with self.assertRaises(
                    (ConnectorError, ValueError)
                ):
                    transport.create_issue_comment(
                        repository="MSKazemi/idkmesh",
                        issue_number=77,
                        body="bounded status",
                    )


if __name__ == "__main__":
    unittest.main()
