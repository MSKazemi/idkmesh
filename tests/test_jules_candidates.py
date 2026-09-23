import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_candidates import JulesCandidateDiscoveryService
from idkmesh.jules_sessions import JulesSessionHandle


REVISION = "0123456789abcdef0123456789abcdef01234567"


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        return self.response


def _handle():
    return JulesSessionHandle(
        session_name="sessions/123",
        session_id="123",
        work_unit_id="wu-123",
        source_name="sources/github/MSKazemi/idkmesh",
        repository="MSKazemi/idkmesh",
        starting_branch="idkmesh/wu-123",
        requested_source_revision=REVISION,
        revision_binding="scm_pinned_branch",
        require_plan_approval=True,
        automation_mode=None,
        state="COMPLETED",
    )


def _session(outputs, *, state="COMPLETED", name="sessions/123", session_id="123"):
    return {
        "name": name,
        "id": session_id,
        "state": state,
        "outputs": outputs,
    }


class JulesCandidateDiscoveryTests(unittest.TestCase):
    def test_completed_pr_becomes_hint_not_candidate_reference(self):
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

        hints = service.discover_pull_request_hints(_handle())

        self.assertEqual(len(hints), 1)
        hint = hints[0]
        self.assertEqual(hint.repository, "MSKazemi/idkmesh")
        self.assertEqual(hint.pull_request_number, 42)
        self.assertEqual(hint.url, "https://github.com/MSKazemi/idkmesh/pull/42")
        self.assertTrue(hint.requires_scm_resolution)
        self.assertFalse(hasattr(hint, "head_sha"))
        self.assertFalse(hasattr(hint, "candidate_type"))
        self.assertFalse(hasattr(hint, "title"))
        self.assertFalse(hasattr(hint, "description"))
        self.assertEqual(client.calls, [("/sessions/123", None)])

    def test_repository_is_bound_to_session_handle_not_caller_input(self):
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
            service.discover_pull_request_hints(_handle())
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_repository_case_in_url_is_normalized_to_trusted_handle(self):
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
        hint = JulesCandidateDiscoveryService(
            client, connection_id="jules-main"
        ).discover_pull_request_hints(_handle())[0]
        self.assertEqual(hint.repository, "MSKazemi/idkmesh")
        self.assertEqual(hint.url, "https://github.com/MSKazemi/idkmesh/pull/7")

    def test_noncompleted_session_cannot_emit_final_discovery_hint(self):
        service = JulesCandidateDiscoveryService(
            FakeClient(_session([], state="IN_PROGRESS")),
            connection_id="jules-main",
        )
        with self.assertRaises(ConnectorError) as caught:
            service.discover_pull_request_hints(_handle())
        self.assertEqual(caught.exception.code, "conflict")

    def test_session_identity_mismatch_fails_closed(self):
        for response in (
            _session([], name="sessions/other"),
            _session([], session_id="other"),
        ):
            with self.subTest(response=response):
                service = JulesCandidateDiscoveryService(
                    FakeClient(response),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.discover_pull_request_hints(_handle())
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
                    service.discover_pull_request_hints(_handle())
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_other_outputs_are_ignored_and_duplicate_prs_deduplicated(self):
        pr = {
            "pullRequest": {
                "url": "https://github.com/MSKazemi/idkmesh/pull/9"
            }
        }
        service = JulesCandidateDiscoveryService(
            FakeClient(_session([{"fileOutput": {}}, pr, pr])),
            connection_id="jules-main",
        )
        hints = service.discover_pull_request_hints(_handle())
        self.assertEqual([item.pull_request_number for item in hints], [9])

    def test_malformed_outputs_fail_closed(self):
        cases = [
            [],
            {"name": "sessions/123", "id": "123", "state": "COMPLETED", "outputs": "bad"},
            _session(["bad"]),
            _session([{"pullRequest": "bad"}]),
            _session([{"pullRequest": {}}]),
        ]
        for response in cases:
            with self.subTest(response=response):
                service = JulesCandidateDiscoveryService(
                    FakeClient(response),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.discover_pull_request_hints(_handle())
                self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_handle_repository_validation_fails_before_provider(self):
        bad = JulesSessionHandle(
            session_name="sessions/123",
            session_id="123",
            work_unit_id="wu-123",
            source_name="source",
            repository="not-a-repository",
            starting_branch="main",
            requested_source_revision=REVISION,
            revision_binding="scm_pinned_branch",
            require_plan_approval=True,
            automation_mode=None,
        )
        client = FakeClient(_session([]))
        service = JulesCandidateDiscoveryService(client, connection_id="jules-main")
        with self.assertRaisesRegex(ValueError, "owner/name"):
            service.discover_pull_request_hints(bad)
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
