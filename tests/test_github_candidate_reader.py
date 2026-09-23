import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import GitHubPullRequestCandidateReader


HEAD = "0123456789abcdef0123456789abcdef01234567"


class FakeSource:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_pull_request(self, *, repository, number):
        self.calls.append((repository, number))
        return self.response


def _pr(
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


class GitHubPullRequestCandidateReaderTests(unittest.TestCase):
    def test_exact_head_becomes_candidate_reference(self):
        source = FakeSource(_pr())
        result = GitHubPullRequestCandidateReader(source).resolve(
            repository="MSKazemi/idkmesh",
            number=42,
        )

        self.assertEqual(
            result.reference.to_dict(),
            {
                "schema_version": "0.1",
                "type": "github_pull_request",
                "repository": "MSKazemi/idkmesh",
                "number": 42,
                "head_sha": HEAD,
            },
        )
        self.assertEqual(result.run_state, "candidate_ready")
        self.assertEqual(result.state, "open")
        self.assertFalse(result.draft)
        self.assertEqual(source.calls, [("MSKazemi/idkmesh", 42)])

    def test_target_repository_matching_is_case_insensitive(self):
        result = GitHubPullRequestCandidateReader(
            FakeSource(
                _pr(
                    repository="mskazemi/IDKMESH",
                    html_url="https://github.com/mskazemi/IDKMESH/pull/42",
                )
            )
        ).resolve(repository="MSKazemi/idkmesh", number=42)
        self.assertEqual(result.reference.repository, "MSKazemi/idkmesh")

    def test_foreign_target_repository_fails_closed(self):
        source = FakeSource(_pr(repository="other/repo"))
        with self.assertRaises(ConnectorError) as caught:
            GitHubPullRequestCandidateReader(source).resolve(
                repository="MSKazemi/idkmesh",
                number=42,
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_wrong_pr_number_fails_closed(self):
        source = FakeSource(_pr(number=43))
        with self.assertRaises(ConnectorError) as caught:
            GitHubPullRequestCandidateReader(source).resolve(
                repository="MSKazemi/idkmesh",
                number=42,
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_mutable_branch_name_cannot_substitute_for_head_sha(self):
        source = FakeSource(_pr(head_sha="feature-branch"))
        with self.assertRaises(ConnectorError) as caught:
            GitHubPullRequestCandidateReader(source).resolve(
                repository="MSKazemi/idkmesh",
                number=42,
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_noncanonical_or_mismatched_html_url_fails_closed(self):
        urls = [
            "http://github.com/MSKazemi/idkmesh/pull/42",
            "https://evil.example/MSKazemi/idkmesh/pull/42",
            "https://github.com/MSKazemi/idkmesh/pull/43",
            "https://github.com/MSKazemi/other/pull/42",
            "https://github.com/MSKazemi/idkmesh/pull/42/files",
            "https://github.com/MSKazemi/idkmesh/pull/42?diff=split",
            "https://user:pass@github.com/MSKazemi/idkmesh/pull/42",
        ]
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ConnectorError):
                    GitHubPullRequestCandidateReader(
                        FakeSource(_pr(html_url=url))
                    ).resolve(
                        repository="MSKazemi/idkmesh",
                        number=42,
                    )

    def test_closed_or_draft_candidate_is_identity_not_acceptance(self):
        result = GitHubPullRequestCandidateReader(
            FakeSource(_pr(state="closed", draft=True))
        ).resolve(repository="MSKazemi/idkmesh", number=42)
        self.assertEqual(result.state, "closed")
        self.assertTrue(result.draft)
        self.assertEqual(result.run_state, "candidate_ready")
        self.assertFalse(hasattr(result, "accepted"))
        self.assertFalse(hasattr(result, "verified"))

    def test_unknown_state_or_malformed_draft_fails_closed(self):
        for response in (
            _pr(state="merged"),
            _pr(draft=None),
        ):
            with self.subTest(response=response):
                with self.assertRaises(ConnectorError):
                    GitHubPullRequestCandidateReader(
                        FakeSource(response)
                    ).resolve(repository="MSKazemi/idkmesh", number=42)

    def test_malformed_provider_shape_fails_closed(self):
        cases = [
            [],
            {},
            {**_pr(), "base": None},
            {**_pr(), "base": {"repo": None}},
            {**_pr(), "head": None},
            {**_pr(), "head": {}},
        ]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(ConnectorError):
                    GitHubPullRequestCandidateReader(
                        FakeSource(response)
                    ).resolve(repository="MSKazemi/idkmesh", number=42)

    def test_invalid_request_fails_before_source_lookup(self):
        source = FakeSource(_pr())
        reader = GitHubPullRequestCandidateReader(source)
        for repository, number in (
            ("not-a-repository", 42),
            ("owner/repo", 0),
            ("owner/repo", True),
        ):
            with self.subTest(repository=repository, number=number):
                with self.assertRaises(ValueError):
                    reader.resolve(repository=repository, number=number)
        self.assertEqual(source.calls, [])


if __name__ == "__main__":
    unittest.main()
