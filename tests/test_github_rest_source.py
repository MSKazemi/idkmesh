import json
import socket
from email.message import Message
from urllib.error import HTTPError, URLError
import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import GitHubPullRequestCandidateReader
from idkmesh.github_rest_source import (
    GitHubRestIdentitySource,
    GitHubRestPullRequestSource,
)


HEAD = "0123456789abcdef0123456789abcdef01234567"


def _pr_payload(**overrides):
    value = {
        "number": 42,
        "html_url": "https://github.com/MSKazemi/idkmesh/pull/42",
        "state": "open",
        "draft": False,
        "base": {"repo": {"full_name": "MSKazemi/idkmesh"}},
        "head": {"sha": HEAD},
    }
    value.update(overrides)
    return value


def _ref_payload(
    *,
    branch="feature/test",
    object_type="commit",
    sha=HEAD,
):
    return {
        "ref": f"refs/heads/{branch}",
        "object": {
            "type": object_type,
            "sha": sha,
        },
    }


class FakeResponse:
    def __init__(self, payload, *, status=200):
        self.payload = payload
        self.status = status
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if size is None or size < 0:
            return self.payload
        return self.payload[:size]


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def _headers(**values):
    message = Message()
    for key, value in values.items():
        message[key.replace("_", "-")] = value
    return message


def _http_error(status, *, headers=None, resource="pull"):
    return HTTPError(
        url=(
            "https://api.github.com/repos/MSKazemi/idkmesh/"
            f"{resource}/synthetic"
        ),
        code=status,
        msg="synthetic",
        hdrs=headers or Message(),
        fp=None,
    )


class GitHubRestIdentitySourceTests(unittest.TestCase):
    def test_compatibility_alias_is_preserved(self):
        self.assertIs(GitHubRestPullRequestSource, GitHubRestIdentitySource)

    def test_public_pr_request_uses_fixed_endpoint_and_bounded_read(self):
        payload = json.dumps(_pr_payload()).encode()
        response = FakeResponse(payload)
        opener = FakeOpener(response=response)
        source = GitHubRestIdentitySource(
            opener=opener,
            timeout_seconds=7,
            max_response_bytes=4096,
            user_agent="idkmesh-test",
        )

        result = source.get_pull_request(
            repository="MSKazemi/idkmesh",
            number=42,
        )

        self.assertEqual(result["head"]["sha"], HEAD)
        request, timeout = opener.calls[0]
        self.assertEqual(
            request.full_url,
            "https://api.github.com/repos/MSKazemi/idkmesh/pulls/42",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(timeout, 7.0)
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(
            request.get_header("X-github-api-version"),
            "2022-11-28",
        )
        self.assertEqual(request.get_header("User-agent"), "idkmesh-test")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(response.read_sizes, [4097])

    def test_branch_ref_request_percent_encodes_branch_as_one_ref_parameter(self):
        payload = json.dumps(_ref_payload()).encode()
        response = FakeResponse(payload)
        opener = FakeOpener(response=response)
        source = GitHubRestIdentitySource(
            opener=opener,
            timeout_seconds=9,
            max_response_bytes=4096,
        )

        result = source.get_branch_ref(
            repository="MSKazemi/idkmesh",
            branch="feature/test",
        )

        self.assertEqual(result["ref"], "refs/heads/feature/test")
        request, timeout = opener.calls[0]
        self.assertEqual(
            request.full_url,
            (
                "https://api.github.com/repos/MSKazemi/idkmesh/"
                "git/ref/heads/feature%2Ftest"
            ),
        )
        self.assertEqual(timeout, 9.0)
        self.assertEqual(response.read_sizes, [4097])

    def test_token_is_used_in_memory_but_never_returned(self):
        payload = json.dumps(_pr_payload()).encode()
        opener = FakeOpener(response=FakeResponse(payload))
        source = GitHubRestIdentitySource(
            token="super-secret-token",
            opener=opener,
            connection_id="github-main",
        )

        result = source.get_pull_request(
            repository="MSKazemi/idkmesh",
            number=42,
        )

        request, _ = opener.calls[0]
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer super-secret-token",
        )
        self.assertNotIn("super-secret-token", json.dumps(result))

    def test_pr_source_composes_with_exact_head_identity_reader(self):
        payload = json.dumps(_pr_payload()).encode()
        source = GitHubRestIdentitySource(
            opener=FakeOpener(response=FakeResponse(payload)),
        )

        resolved = GitHubPullRequestCandidateReader(source).resolve(
            repository="MSKazemi/idkmesh",
            number=42,
        )

        self.assertEqual(resolved.reference.head_sha, HEAD)
        self.assertEqual(
            resolved.reference.canonical_url,
            "https://github.com/MSKazemi/idkmesh/pull/42",
        )

    def test_response_size_limit_fails_closed_for_each_resource(self):
        for call in ("pr", "branch"):
            with self.subTest(call=call):
                opener = FakeOpener(response=FakeResponse(b"x" * 33))
                source = GitHubRestIdentitySource(
                    opener=opener,
                    max_response_bytes=32,
                )
                with self.assertRaisesRegex(
                    ConnectorError,
                    "size limit",
                ) as caught:
                    if call == "pr":
                        source.get_pull_request(
                            repository="MSKazemi/idkmesh",
                            number=42,
                        )
                    else:
                        source.get_branch_ref(
                            repository="MSKazemi/idkmesh",
                            branch="feature/test",
                        )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_malformed_json_and_non_object_fail_closed(self):
        for payload in (b"{not-json", b"[]", b"null"):
            with self.subTest(payload=payload):
                source = GitHubRestIdentitySource(
                    opener=FakeOpener(
                        response=FakeResponse(payload)
                    ),
                )
                with self.assertRaises(ConnectorError) as caught:
                    source.get_pull_request(
                        repository="MSKazemi/idkmesh",
                        number=42,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_http_error_mapping_for_pr_and_branch(self):
        cases = [
            (401, Message(), "authentication_error"),
            (403, Message(), "authorization_error"),
            (
                403,
                _headers(X_RateLimit_Remaining="0"),
                "rate_limited",
            ),
            (404, Message(), "not_found"),
            (408, Message(), "timeout"),
            (429, _headers(Retry_After="5"), "rate_limited"),
            (500, Message(), "provider_unavailable"),
            (503, Message(), "provider_unavailable"),
            (418, Message(), "provider_unavailable"),
        ]

        for resource in ("pr", "branch"):
            for status, headers, expected_code in cases:
                with self.subTest(
                    resource=resource,
                    status=status,
                    expected_code=expected_code,
                ):
                    source = GitHubRestIdentitySource(
                        token="secret-token",
                        opener=FakeOpener(
                            error=_http_error(
                                status,
                                headers=headers,
                                resource=resource,
                            )
                        ),
                    )
                    with self.assertRaises(ConnectorError) as caught:
                        if resource == "pr":
                            source.get_pull_request(
                                repository="MSKazemi/idkmesh",
                                number=42,
                            )
                        else:
                            source.get_branch_ref(
                                repository="MSKazemi/idkmesh",
                                branch="feature/test",
                            )

                    error = caught.exception
                    self.assertEqual(error.code, expected_code)
                    self.assertEqual(error.connection_id, "github")
                    self.assertNotIn("secret-token", str(error))
                    self.assertNotIn(
                        "secret-token",
                        json.dumps(error.details),
                    )
                    self.assertEqual(error.details["status"], status)
                    if status == 429:
                        self.assertEqual(error.details["retry_after"], "5")

    def test_network_and_timeout_failures_are_normalized(self):
        cases = [
            (URLError("offline"), "provider_unavailable"),
            (URLError(socket.timeout("slow")), "timeout"),
            (socket.timeout("slow"), "timeout"),
            (OSError("network down"), "provider_unavailable"),
        ]

        for error, expected_code in cases:
            with self.subTest(error=error):
                source = GitHubRestIdentitySource(
                    opener=FakeOpener(error=error),
                )
                with self.assertRaises(ConnectorError) as caught:
                    source.get_branch_ref(
                        repository="MSKazemi/idkmesh",
                        branch="feature/test",
                    )
                self.assertEqual(caught.exception.code, expected_code)

    def test_invalid_identity_fails_before_network_io(self):
        opener = FakeOpener(
            response=FakeResponse(json.dumps(_pr_payload()).encode())
        )
        source = GitHubRestIdentitySource(opener=opener)

        for repository, number in (
            ("not-a-repository", 42),
            ("owner/repo/extra", 42),
            ("owner/repo", 0),
            ("owner/repo", True),
        ):
            with self.subTest(repository=repository, number=number):
                with self.assertRaises(ValueError):
                    source.get_pull_request(
                        repository=repository,
                        number=number,
                    )

        for repository, branch in (
            ("not-a-repository", "main"),
            ("owner/repo", ""),
            ("owner/repo", "../main"),
            ("owner/repo", "feature//double"),
            ("owner/repo", "feature..bad"),
            ("owner/repo", "bad branch"),
            ("owner/repo", "bad?branch"),
        ):
            with self.subTest(repository=repository, branch=branch):
                with self.assertRaises(ValueError):
                    source.get_branch_ref(
                        repository=repository,
                        branch=branch,
                    )

        self.assertEqual(opener.calls, [])

    def test_constructor_guards_transport_configuration(self):
        bad_configs = [
            {"token": ""},
            {"token": "secret\nheader"},
            {"timeout_seconds": 0},
            {"timeout_seconds": float("nan")},
            {"timeout_seconds": 121},
            {"max_response_bytes": 0},
            {"max_response_bytes": 8 * 1024 * 1024 + 1},
            {"opener": "not-callable"},
            {"user_agent": ""},
            {"user_agent": "bad\nagent"},
            {"connection_id": ""},
        ]
        for config in bad_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    GitHubRestIdentitySource(**config)


if __name__ == "__main__":
    unittest.main()
