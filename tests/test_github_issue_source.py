import io
import json
import socket
import unittest
from urllib.error import HTTPError, URLError

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_source import GitHubRestIssueSource


def _issue_payload():
    return {
        "id": 9001,
        "number": 77,
        "title": "Bounded task",
        "body": "Add tests.",
        "state": "open",
        "locked": False,
        "user": {
            "login": "contributor",
            "id": 88,
        },
        "author_association": "CONTRIBUTOR",
        "labels": [{"name": "agent-ready"}],
        "html_url": (
            "https://github.com/MSKazemi/idkmesh/issues/77"
        ),
        "updated_at": "2026-09-24T15:00:00Z",
    }


class FakeResponse:
    def __init__(self, payload, *, status=200):
        self.status = status
        self._payload = payload

    def read(self, amount=-1):
        return self._payload[:amount]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GitHubRestIssueSourceTests(unittest.TestCase):
    def test_fixed_host_get_and_bearer_header(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.method
            seen["headers"] = dict(request.header_items())
            seen["timeout"] = timeout
            return FakeResponse(
                json.dumps(_issue_payload()).encode()
            )

        source = GitHubRestIssueSource(
            token="github-test-token-value",
            opener=opener,
        )
        raw = source.get_issue(
            repository="MSKazemi/idkmesh",
            issue_number=77,
        )

        self.assertEqual(
            seen["url"],
            (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "issues/77"
            ),
        )
        self.assertEqual(seen["method"], "GET")
        self.assertIn(
            "Bearer github-test-token-value",
            seen["headers"].values(),
        )
        self.assertEqual(raw["number"], 77)

    def test_snapshot_composes_with_strict_issue_normalizer(self):
        source = GitHubRestIssueSource(
            opener=lambda request, timeout: FakeResponse(
                json.dumps(_issue_payload()).encode()
            )
        )
        snapshot = source.get_issue_snapshot(
            repository="MSKazemi/idkmesh",
            issue_number=77,
        )
        self.assertEqual(snapshot.number, 77)
        self.assertEqual(
            snapshot.repository,
            "MSKazemi/idkmesh",
        )
        self.assertEqual(
            snapshot.labels,
            ("agent-ready",),
        )

    def test_pull_request_shape_is_rejected_by_snapshot_boundary(self):
        payload = _issue_payload()
        payload["pull_request"] = {
            "url": "https://api.github.com/repos/x/y/pulls/77"
        }
        source = GitHubRestIssueSource(
            opener=lambda request, timeout: FakeResponse(
                json.dumps(payload).encode()
            )
        )
        with self.assertRaises(ConnectorError) as caught:
            source.get_issue_snapshot(
                repository="MSKazemi/idkmesh",
                issue_number=77,
            )
        self.assertEqual(caught.exception.code, "policy_denied")

    def test_auth_error_never_exposes_token_or_provider_body(self):
        token = "never-echo-this-github-token"

        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                401,
                "unauthorized",
                {},
                io.BytesIO(
                    b"provider body containing sensitive text"
                ),
            )

        source = GitHubRestIssueSource(
            token=token,
            opener=opener,
        )
        with self.assertRaises(ConnectorError) as caught:
            source.get_issue(
                repository="MSKazemi/idkmesh",
                issue_number=77,
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

    def test_rate_limit_is_normalized(self):
        class Headers:
            def get(self, name):
                if name == "X-RateLimit-Remaining":
                    return "0"
                if name == "Retry-After":
                    return "30"
                return None

        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                403,
                "forbidden",
                Headers(),
                io.BytesIO(b"ignored"),
            )

        source = GitHubRestIssueSource(opener=opener)
        with self.assertRaises(ConnectorError) as caught:
            source.get_issue(
                repository="MSKazemi/idkmesh",
                issue_number=77,
            )
        self.assertEqual(caught.exception.code, "rate_limited")
        self.assertEqual(
            caught.exception.details["retry_after"],
            "30",
        )

    def test_timeout_and_url_error_are_normalized(self):
        for failure, code in (
            (socket.timeout("slow"), "timeout"),
            (URLError("offline"), "provider_unavailable"),
            (
                URLError(socket.timeout("slow")),
                "timeout",
            ),
        ):
            with self.subTest(code=code, failure=failure):
                source = GitHubRestIssueSource(
                    opener=lambda request, timeout, f=failure: (
                        _raise(f)
                    )
                )
                with self.assertRaises(ConnectorError) as caught:
                    source.get_issue(
                        repository="MSKazemi/idkmesh",
                        issue_number=77,
                    )
                self.assertEqual(caught.exception.code, code)

    def test_response_size_and_json_shape_fail_closed(self):
        cases = (
            (
                b"x" * 20,
                10,
                "result_normalization_error",
            ),
            (
                b"not-json",
                1024,
                "result_normalization_error",
            ),
            (
                b"[]",
                1024,
                "result_normalization_error",
            ),
        )
        for payload, max_bytes, code in cases:
            with self.subTest(payload=payload):
                source = GitHubRestIssueSource(
                    opener=lambda request, timeout, p=payload: (
                        FakeResponse(p)
                    ),
                    max_response_bytes=max_bytes,
                )
                with self.assertRaises(ConnectorError) as caught:
                    source.get_issue(
                        repository="MSKazemi/idkmesh",
                        issue_number=77,
                    )
                self.assertEqual(caught.exception.code, code)

    def test_config_validation_is_fail_closed(self):
        with self.assertRaises(ValueError):
            GitHubRestIssueSource(timeout_seconds=0)
        with self.assertRaises(ValueError):
            GitHubRestIssueSource(max_response_bytes=0)
        with self.assertRaises(ValueError):
            GitHubRestIssueSource(token="")
        source = GitHubRestIssueSource(
            opener=lambda request, timeout: FakeResponse(b"{}")
        )
        with self.assertRaises(ValueError):
            source.get_issue(
                repository="not-a-repo",
                issue_number=77,
            )
        with self.assertRaises(ValueError):
            source.get_issue(
                repository="MSKazemi/idkmesh",
                issue_number=0,
            )


def _raise(exc):
    raise exc


if __name__ == "__main__":
    unittest.main()
