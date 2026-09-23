import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_sessions import (
    JulesSessionRequest,
    JulesSessionService,
    ScmRevisionBinding,
)


REVISION = "0123456789abcdef0123456789abcdef01234567"


class FakeClient:
    def __init__(self, response=None):
        self.response = response or {
            "name": "sessions/123",
            "id": "123",
            "state": "QUEUED",
            "url": "https://jules.google.com/session/123",
            "sourceContext": {
                "source": "sources/github/MSKazemi/idkmesh",
                "githubRepoContext": {"startingBranch": "idkmesh/wu-123"},
            },
        }
        self.calls = []

    def post_json(self, path, *, body=None):
        self.calls.append((path, body))
        return self.response


class FakeSourceValidator:
    def __init__(self):
        self.calls = []

    def validate_github_source(self, **kwargs):
        self.calls.append(kwargs)
        return object()


def _binding(*, verified=True):
    return ScmRevisionBinding(
        github_owner="MSKazemi",
        github_repo="idkmesh",
        branch="idkmesh/wu-123",
        revision=REVISION,
        verified=verified,
    )


def _request(*, binding=None, automation_mode=None):
    return JulesSessionRequest(
        work_unit_id="wu-123",
        prompt="Add focused regression tests.",
        title="WU 123: regression tests",
        source_name="sources/github/MSKazemi/idkmesh",
        binding=binding or _binding(),
        automation_mode=automation_mode,
    )


class JulesSessionCreationTests(unittest.TestCase):
    def test_unverified_revision_binding_blocks_before_provider_calls(self):
        client = FakeClient()
        source = FakeSourceValidator()
        service = JulesSessionService(client, source, connection_id="jules-main")

        with self.assertRaises(ConnectorError) as caught:
            service.create_session(_request(binding=_binding(verified=False)))

        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertEqual(source.calls, [])
        self.assertEqual(client.calls, [])

    def test_source_is_validated_before_session_creation(self):
        client = FakeClient()
        source = FakeSourceValidator()
        service = JulesSessionService(client, source, connection_id="jules-main")

        service.create_session(_request())

        self.assertEqual(
            source.calls,
            [
                {
                    "source_name": "sources/github/MSKazemi/idkmesh",
                    "github_owner": "MSKazemi",
                    "github_repo": "idkmesh",
                    "starting_branch": "idkmesh/wu-123",
                }
            ],
        )
        self.assertEqual(client.calls[0][0], "/sessions")

    def test_payload_requires_explicit_plan_approval(self):
        client = FakeClient()
        service = JulesSessionService(
            client, FakeSourceValidator(), connection_id="jules-main"
        )
        service.create_session(_request())
        payload = client.calls[0][1]

        self.assertEqual(payload["requirePlanApproval"], True)
        self.assertEqual(payload["prompt"], "Add focused regression tests.")
        self.assertEqual(payload["title"], "WU 123: regression tests")
        self.assertEqual(
            payload["sourceContext"],
            {
                "source": "sources/github/MSKazemi/idkmesh",
                "githubRepoContext": {"startingBranch": "idkmesh/wu-123"},
            },
        )
        self.assertNotIn("automationMode", payload)
        self.assertNotIn("sourceRevision", payload)

    def test_auto_create_pr_is_only_sent_when_explicit(self):
        client = FakeClient()
        service = JulesSessionService(
            client, FakeSourceValidator(), connection_id="jules-main"
        )
        service.create_session(_request(automation_mode="AUTO_CREATE_PR"))
        self.assertEqual(client.calls[0][1]["automationMode"], "AUTO_CREATE_PR")

    def test_handle_records_local_revision_provenance_truthfully(self):
        service = JulesSessionService(
            FakeClient(), FakeSourceValidator(), connection_id="jules-main"
        )
        handle = service.create_session(_request())
        self.assertEqual(handle.session_name, "sessions/123")
        self.assertEqual(handle.session_id, "123")
        self.assertEqual(handle.work_unit_id, "wu-123")
        self.assertEqual(handle.requested_source_revision, REVISION)
        self.assertEqual(handle.revision_binding, "scm_pinned_branch")
        self.assertTrue(handle.require_plan_approval)
        self.assertEqual(handle.state, "QUEUED")

    def test_response_source_or_branch_mismatch_fails_closed(self):
        cases = [
            {
                "name": "sessions/123",
                "id": "123",
                "sourceContext": {
                    "source": "sources/github/other/repo",
                    "githubRepoContext": {"startingBranch": "idkmesh/wu-123"},
                },
            },
            {
                "name": "sessions/123",
                "id": "123",
                "sourceContext": {
                    "source": "sources/github/MSKazemi/idkmesh",
                    "githubRepoContext": {"startingBranch": "main"},
                },
            },
        ]
        for response in cases:
            with self.subTest(response=response):
                service = JulesSessionService(
                    FakeClient(response),
                    FakeSourceValidator(),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.create_session(_request())
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_malformed_session_identity_or_context_fails_closed(self):
        cases = [
            {"name": "bad", "id": "123", "sourceContext": {}},
            {"name": "sessions/123", "id": "", "sourceContext": {}},
            {"name": "sessions/123", "id": "123"},
            {
                "name": "sessions/123",
                "id": "123",
                "sourceContext": {
                    "source": "sources/github/MSKazemi/idkmesh",
                    "githubRepoContext": {},
                },
            },
        ]
        for response in cases:
            with self.subTest(response=response):
                service = JulesSessionService(
                    FakeClient(response),
                    FakeSourceValidator(),
                    connection_id="jules-main",
                )
                with self.assertRaises(ConnectorError) as caught:
                    service.create_session(_request())
                self.assertEqual(
                    caught.exception.code,
                    "result_normalization_error",
                )

    def test_revision_digest_and_automation_mode_validate_locally(self):
        with self.assertRaisesRegex(ValueError, "revision"):
            ScmRevisionBinding(
                github_owner="MSKazemi",
                github_repo="idkmesh",
                branch="idkmesh/wu-123",
                revision="main",
                verified=True,
            )

        with self.assertRaisesRegex(ValueError, "automation_mode"):
            _request(automation_mode="FULL_AUTO")

    def test_sha256_revision_is_supported_for_future_git_object_format(self):
        binding = ScmRevisionBinding(
            github_owner="MSKazemi",
            github_repo="idkmesh",
            branch="idkmesh/wu-123",
            revision="a" * 64,
            verified=True,
        )
        self.assertEqual(binding.revision, "a" * 64)


if __name__ == "__main__":
    unittest.main()
