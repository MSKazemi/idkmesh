import unittest

from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import (
    CandidateResolutionError,
    GitHubPullRequestCandidateReader,
    GitHubPullRequestResolution,
)
from idkmesh.jules_candidate_binding import JulesCandidateBindingService
from idkmesh.jules_candidates import JulesPullRequestHint


HEAD = "0123456789abcdef0123456789abcdef01234567"


def _hint(
    *,
    provider="jules",
    session_name="sessions/123",
    repository="MSKazemi/idkmesh",
    number=42,
    url="https://github.com/MSKazemi/idkmesh/pull/42",
):
    return JulesPullRequestHint(
        provider=provider,
        session_name=session_name,
        repository=repository,
        pull_request_number=number,
        url=url,
    )


class FakeGitHubSource:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_pull_request(self, *, repository, number):
        self.calls.append((repository, number))
        return self.response


def _github_pr(
    *,
    repository="MSKazemi/idkmesh",
    number=42,
    head_sha=HEAD,
    html_url="https://github.com/MSKazemi/idkmesh/pull/42",
    state="open",
    draft=False,
):
    return {
        "number": number,
        "html_url": html_url,
        "state": state,
        "draft": draft,
        "base": {"repo": {"full_name": repository}},
        "head": {"sha": head_sha},
    }


class FakeResolver:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def resolve(self, *, repository, number):
        self.calls.append((repository, number))
        if self.error is not None:
            raise self.error
        return self.result


class JulesCandidateBindingTests(unittest.TestCase):
    def test_hint_resolves_exact_head_only_through_github_reader(self):
        source = FakeGitHubSource(_github_pr())
        reader = GitHubPullRequestCandidateReader(source)
        service = JulesCandidateBindingService(
            reader,
            connection_id="jules-main",
        )

        resolved = service.resolve_pull_request_hint(_hint())

        self.assertEqual(
            source.calls,
            [("MSKazemi/idkmesh", 42)],
        )
        self.assertEqual(
            resolved.reference.to_dict(),
            {
                "schema_version": "0.1",
                "type": "github_pull_request",
                "repository": "MSKazemi/idkmesh",
                "number": 42,
                "head_sha": HEAD,
            },
        )
        self.assertEqual(resolved.state, "open")
        self.assertFalse(resolved.draft)

    def test_jules_hint_cannot_supply_or_override_head_sha(self):
        source = FakeGitHubSource(
            _github_pr(
                head_sha="1123456789abcdef0123456789abcdef01234567"
            )
        )
        resolved = JulesCandidateBindingService(
            GitHubPullRequestCandidateReader(source),
            connection_id="jules-main",
        ).resolve_pull_request_hint(_hint())

        self.assertEqual(
            resolved.reference.head_sha,
            "1123456789abcdef0123456789abcdef01234567",
        )
        self.assertFalse(hasattr(_hint(), "head_sha"))

    def test_non_jules_provider_fails_before_scm_lookup(self):
        resolver = FakeResolver()
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        with self.assertRaises(ConnectorError) as caught:
            service.resolve_pull_request_hint(
                _hint(provider="other-agent")
            )

        self.assertEqual(
            caught.exception.code,
            "result_normalization_error",
        )
        self.assertEqual(resolver.calls, [])

    def test_invalid_session_name_fails_before_scm_lookup(self):
        resolver = FakeResolver()
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        with self.assertRaises(ConnectorError):
            service.resolve_pull_request_hint(
                _hint(session_name="not-a-session")
            )

        self.assertEqual(resolver.calls, [])

    def test_hint_url_must_match_bound_repository_and_number(self):
        resolver = FakeResolver()
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )
        cases = [
            _hint(
                url="https://github.com/MSKazemi/idkmesh/pull/43"
            ),
            _hint(
                url="https://github.com/other/repo/pull/42"
            ),
            _hint(
                url="https://github.com/mskazemi/idkmesh/pull/42"
            ),
        ]

        for hint in cases:
            with self.subTest(url=hint.url):
                with self.assertRaises(ConnectorError) as caught:
                    service.resolve_pull_request_hint(hint)
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

        self.assertEqual(resolver.calls, [])

    def test_invalid_hint_number_is_connector_normalization_error(self):
        resolver = FakeResolver()
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        for number in (0, -1, True):
            with self.subTest(number=number):
                with self.assertRaises(ConnectorError) as caught:
                    service.resolve_pull_request_hint(
                        _hint(
                            number=number,
                            url=(
                                "https://github.com/MSKazemi/idkmesh/"
                                f"pull/{number}"
                            ),
                        )
                    )
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

        self.assertEqual(resolver.calls, [])

    def test_scm_resolution_failure_is_translated_without_raw_payload(self):
        resolver = FakeResolver(
            error=CandidateResolutionError(
                "provider payload contained unsafe detail",
                field="head.sha",
                details={"authorization": "Bearer secret"},
            )
        )
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        with self.assertRaises(ConnectorError) as caught:
            service.resolve_pull_request_hint(_hint())

        error = caught.exception
        self.assertEqual(error.code, "result_normalization_error")
        self.assertEqual(error.connection_id, "jules-main")
        self.assertEqual(error.details["scm_field"], "head.sha")
        self.assertNotIn("secret", str(error))
        self.assertNotIn("authorization", error.details)

    def test_postcondition_rejects_mismatched_resolution(self):
        wrong = GitHubPullRequestResolution(
            reference=GitHubPullRequestCandidateReference(
                repository="other/repo",
                number=42,
                head_sha=HEAD,
            ),
            state="open",
            draft=False,
        )
        resolver = FakeResolver(result=wrong)
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        with self.assertRaisesRegex(
            ConnectorError,
            "does not match",
        ):
            service.resolve_pull_request_hint(_hint())

    def test_unexpected_resolver_type_fails_closed(self):
        resolver = FakeResolver(result={"head_sha": HEAD})
        service = JulesCandidateBindingService(
            resolver,
            connection_id="jules-main",
        )

        with self.assertRaisesRegex(
            ConnectorError,
            "unexpected candidate resolution type",
        ):
            service.resolve_pull_request_hint(_hint())

    def test_closed_or_draft_status_remains_descriptive_not_authority(self):
        source = FakeGitHubSource(
            _github_pr(state="closed", draft=True)
        )
        resolved = JulesCandidateBindingService(
            GitHubPullRequestCandidateReader(source),
            connection_id="jules-main",
        ).resolve_pull_request_hint(_hint())

        self.assertEqual(resolved.state, "closed")
        self.assertTrue(resolved.draft)
        for field in (
            "run_state",
            "accepted",
            "verified",
            "merge_authorized",
            "integration_authorized",
        ):
            self.assertFalse(hasattr(resolved, field))
            self.assertFalse(hasattr(resolved.reference, field))

    def test_non_hint_type_is_programmer_error(self):
        service = JulesCandidateBindingService(
            FakeResolver(),
            connection_id="jules-main",
        )
        with self.assertRaises(ValueError):
            service.resolve_pull_request_hint(
                {"repository": "MSKazemi/idkmesh"}
            )


if __name__ == "__main__":
    unittest.main()
