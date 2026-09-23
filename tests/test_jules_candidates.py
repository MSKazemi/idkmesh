import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_candidates import JulesCandidateDiscoveryService


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        return self.response


def _session(outputs):
    return {
        "name": "sessions/123",
        "id": "123",
        "state": "COMPLETED",
        "outputs": outputs,
    }


class JulesCandidateDiscoveryTests(unittest.TestCase):
    def test_pull_request_is_candidate_locator_only(self):
        client = FakeClient(
            _session(
                [
                    {
                        "pullRequest": {
                            "url": "https://github.com/MSKazemi/idkmesh/pull/42",
                            "title": "provider title",
                            "description": "provider description",
                        }
                    }
                ]
            )
        )
        service = JulesCandidateDiscoveryService(client, connection_id="jules-main")

        candidates = service.discover_pull_requests(
            "sessions/123",
            github_owner="MSKazemi",
            github_repo="idkmesh",
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.candidate_type, "github_pull_request")
        self.assertEqual(candidate.repository, "MSKazemi/idkmesh")
        self.assertEqual(candidate.pull_request_number, 42)
        self.assertIsNone(candidate.head_sha)
        self.assertTrue(candidate.requires_scm_resolution)
        self.assertFalse(hasattr(candidate, "title"))
        self.assertFalse(hasattr(candidate, "description"))
        self.assertEqual(client.calls, [("/sessions/123", None)])

    def test_repository_identity_check_is_case_insensitive(self):
        client = FakeClient(
            _session(
                [
                    {
                        "pullRequest": {
                            "url": "https://github.com/mskazemi/IDKMESH/pull/7"
                        }
                    }
                ]
            )
        )
        service = JulesCandidateDiscoveryService(client, connection_id="jules-main")
        candidate = service.discover_pull_requests(
            "sessions/123",
            github_owner="MSKazemi",
            github_repo="idkmesh",
        )[0]
        self.assertEqual(candidate.pull_request_number, 7)
        self.assertEqual(candidate.repository, "MSKazemi/idkmesh")

    def test_foreign_repository_candidate_fails_closed(self):
        client = FakeClient(
            _session(
                [
                    {
                        "pullRequest": {
                            "url": "https://github.com/other/repo/pull/1"
                        }
                    }
                ]
            )
        )
        service = JulesCandidateDiscoveryService(client, connection_id="jules-main")
        with self.assertRaises(ConnectorError) as caught:
            service.discover_pull_requests(
                "sessions/123",
                github_owner="MSKazemi",
                github_repo="idkmesh",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_noncanonical_or_unsafe_pr_urls_fail_closed(self):
        urls = [
            "http://github.com/MSKazemi/idkmesh/pull/1",
            "https://evil.example/MSKazemi/idkmesh/pull/1",
            "https://github.com/MSKazemi/idkmesh/pull/not-a-number",
            "https://github.com/MSKazemi/idkmesh/pull/0",
            "https://github.com/MSKazemi/idkmesh/pull/1/files",
            "https://github.com/MSKazemi/idkmesh/pull/1?diff=split",
            "https://user:pass@github.com/MSKazemi/idkmesh/pull/1",
        ]
        for url in urls:
            with self.subTest(url=url):
                service = JulesCandidateDiscoveryService(
                    FakeClient(_session([{"pullRequest": {"url": url}}])),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.discover_pull_requests(
                        "sessions/123",
                        github_owner="MSKazemi",
                        github_repo="idkmesh",
                    )
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_other_output_types_are_ignored(self):
        service = JulesCandidateDiscoveryService(
            FakeClient(_session([{"fileOutput": {"name": "artifact.zip"}}])),
            connection_id="jules-main",
        )
        self.assertEqual(
            service.discover_pull_requests(
                "sessions/123",
                github_owner="MSKazemi",
                github_repo="idkmesh",
            ),
            (),
        )

    def test_duplicate_identical_pr_is_deduplicated(self):
        output = {
            "pullRequest": {
                "url": "https://github.com/MSKazemi/idkmesh/pull/9"
            }
        }
        service = JulesCandidateDiscoveryService(
            FakeClient(_session([output, output])),
            connection_id="jules-main",
        )
        candidates = service.discover_pull_requests(
            "sessions/123",
            github_owner="MSKazemi",
            github_repo="idkmesh",
        )
        self.assertEqual([item.pull_request_number for item in candidates], [9])

    def test_candidates_are_sorted_by_pr_number(self):
        service = JulesCandidateDiscoveryService(
            FakeClient(
                _session(
                    [
                        {
                            "pullRequest": {
                                "url": "https://github.com/MSKazemi/idkmesh/pull/20"
                            }
                        },
                        {
                            "pullRequest": {
                                "url": "https://github.com/MSKazemi/idkmesh/pull/3"
                            }
                        },
                    ]
                )
            ),
            connection_id="jules-main",
        )
        candidates = service.discover_pull_requests(
            "sessions/123",
            github_owner="MSKazemi",
            github_repo="idkmesh",
        )
        self.assertEqual([item.pull_request_number for item in candidates], [3, 20])

    def test_malformed_session_or_output_fails_closed(self):
        cases = [
            [],
            {"name": "sessions/other", "outputs": []},
            {"name": "sessions/123", "outputs": "bad"},
            {"name": "sessions/123", "outputs": ["bad"]},
            {"name": "sessions/123", "outputs": [{"pullRequest": "bad"}]},
            {"name": "sessions/123", "outputs": [{"pullRequest": {}}]},
        ]
        for response in cases:
            with self.subTest(response=response):
                service = JulesCandidateDiscoveryService(
                    FakeClient(response),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.discover_pull_requests(
                        "sessions/123",
                        github_owner="MSKazemi",
                        github_repo="idkmesh",
                    )
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_invalid_session_name_and_repository_args_fail_before_provider(self):
        client = FakeClient(_session([]))
        service = JulesCandidateDiscoveryService(client, connection_id="jules-main")

        with self.assertRaises(ConnectorError) as session:
            service.discover_pull_requests(
                "123",
                github_owner="MSKazemi",
                github_repo="idkmesh",
            )
        self.assertEqual(session.exception.code, "configuration_error")

        with self.assertRaisesRegex(ValueError, "github_owner"):
            service.discover_pull_requests(
                "sessions/123",
                github_owner="",
                github_repo="idkmesh",
            )

        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
