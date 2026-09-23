import unittest

from idkmesh.github_candidate_reader import GitHubPullRequestCandidateReader
from idkmesh.jules_candidate_binding import JulesCandidateBindingService
from idkmesh.jules_candidates import JulesCandidateDiscoveryService
from idkmesh.jules_observation import JulesObservationService
from idkmesh.jules_sessions import (
    JulesSessionRequest,
    JulesSessionService,
    ScmRevisionBinding,
)
from idkmesh.jules_sources import JulesSourceService


SOURCE_REVISION = "0123456789abcdef0123456789abcdef01234567"
CANDIDATE_HEAD = "1123456789abcdef0123456789abcdef01234567"
SOURCE_NAME = "sources/github/MSKazemi/idkmesh"
STARTING_BRANCH = "idkmesh/wu-123"
SESSION_NAME = "sessions/123"
PR_URL = "https://github.com/MSKazemi/idkmesh/pull/42"


class FakeJulesClient:
    def __init__(self, *, outputs=None, final_state="COMPLETED"):
        self.outputs = (
            [{"pullRequest": {"url": PR_URL}}]
            if outputs is None
            else outputs
        )
        self.final_state = final_state
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append(("GET", path, query))
        if path == "/" + SOURCE_NAME:
            return {
                "name": SOURCE_NAME,
                "id": "source-1",
                "githubRepo": {
                    "owner": "MSKazemi",
                    "repo": "idkmesh",
                    "isPrivate": False,
                    "defaultBranch": {"displayName": "main"},
                    "branches": [
                        {"displayName": "main"},
                        {"displayName": STARTING_BRANCH},
                    ],
                },
            }
        if path == "/" + SESSION_NAME:
            return {
                "name": SESSION_NAME,
                "id": "123",
                "state": self.final_state,
                "updateTime": "2026-09-23T12:10:00Z",
                "outputs": self.outputs,
            }
        raise AssertionError(f"unexpected GET: {path}")

    def post_json(self, path, *, body=None):
        self.calls.append(("POST", path, body))
        if path != "/sessions":
            raise AssertionError(f"unexpected POST: {path}")
        return {
            "name": SESSION_NAME,
            "id": "123",
            "state": "PLANNING",
            "url": "https://jules.google/session/123",
            "sourceContext": {
                "source": SOURCE_NAME,
                "githubRepoContext": {
                    "startingBranch": STARTING_BRANCH,
                },
            },
        }


class FakeGitHubSource:
    def __init__(self):
        self.calls = []

    def get_pull_request(self, *, repository, number):
        self.calls.append((repository, number))
        return {
            "number": number,
            "html_url": PR_URL,
            "state": "open",
            "draft": False,
            "base": {
                "repo": {
                    "full_name": "MSKazemi/idkmesh",
                }
            },
            "head": {
                "sha": CANDIDATE_HEAD,
            },
        }


def _create_handle(client):
    source_service = JulesSourceService(
        client,
        connection_id="jules-main",
    )
    session_service = JulesSessionService(
        client,
        source_service,
        connection_id="jules-main",
    )
    request = JulesSessionRequest(
        work_unit_id="wu-123",
        prompt="Implement one bounded low-risk change.",
        title="IDKMesh work unit wu-123",
        source_name=SOURCE_NAME,
        binding=ScmRevisionBinding(
            github_owner="MSKazemi",
            github_repo="idkmesh",
            branch=STARTING_BRANCH,
            revision=SOURCE_REVISION,
            verified=True,
        ),
        automation_mode="AUTO_CREATE_PR",
    )
    return session_service.create_session(request)


class JulesOfflineLifecycleIntegrationTests(unittest.TestCase):
    def test_remote_candidate_lifecycle_stops_at_exact_candidate_identity(self):
        jules = FakeJulesClient()
        handle = _create_handle(jules)

        self.assertEqual(handle.repository, "MSKazemi/idkmesh")
        self.assertEqual(
            handle.requested_source_revision,
            SOURCE_REVISION,
        )
        self.assertTrue(handle.require_plan_approval)
        self.assertEqual(handle.state, "PLANNING")

        observation = JulesObservationService(
            jules,
            connection_id="jules-main",
        ).get_session(handle.session_name)

        self.assertEqual(observation.provider_state, "COMPLETED")
        self.assertEqual(observation.run_state, "worker_completed")
        self.assertEqual(observation.candidate_output_count, 1)
        self.assertNotEqual(observation.run_state, "candidate_ready")
        self.assertNotEqual(observation.run_state, "verified")

        hints = JulesCandidateDiscoveryService(
            jules,
            connection_id="jules-main",
        ).discover_pull_request_hints(handle)

        self.assertEqual(len(hints), 1)
        hint = hints[0]
        self.assertEqual(hint.repository, "MSKazemi/idkmesh")
        self.assertEqual(hint.pull_request_number, 42)
        self.assertFalse(hasattr(hint, "head_sha"))

        github = FakeGitHubSource()
        resolved = JulesCandidateBindingService(
            GitHubPullRequestCandidateReader(github),
            connection_id="jules-main",
        ).resolve_pull_request_hint(hint)

        self.assertEqual(
            github.calls,
            [("MSKazemi/idkmesh", 42)],
        )
        self.assertEqual(
            resolved.reference.repository,
            "MSKazemi/idkmesh",
        )
        self.assertEqual(resolved.reference.number, 42)
        self.assertEqual(
            resolved.reference.head_sha,
            CANDIDATE_HEAD,
        )
        self.assertEqual(
            resolved.reference.canonical_url,
            PR_URL,
        )

        for field in (
            "run_state",
            "candidate_ready",
            "verified",
            "accepted",
            "merge_authorized",
            "integration_authorized",
        ):
            self.assertFalse(hasattr(resolved, field))
            self.assertFalse(hasattr(resolved.reference, field))

    def test_completed_session_without_pr_remains_worker_completed(self):
        jules = FakeJulesClient(outputs=[])
        handle = _create_handle(jules)

        observation = JulesObservationService(
            jules,
            connection_id="jules-main",
        ).get_session(handle.session_name)
        hints = JulesCandidateDiscoveryService(
            jules,
            connection_id="jules-main",
        ).discover_pull_request_hints(handle)

        self.assertEqual(observation.run_state, "worker_completed")
        self.assertEqual(observation.candidate_output_count, 0)
        self.assertEqual(hints, ())

    def test_noncompleted_session_cannot_enter_candidate_discovery(self):
        jules = FakeJulesClient(final_state="IN_PROGRESS")
        handle = _create_handle(jules)

        observation = JulesObservationService(
            jules,
            connection_id="jules-main",
        ).get_session(handle.session_name)
        self.assertEqual(observation.run_state, "waiting_for_agent")

        with self.assertRaisesRegex(
            Exception,
            "completed Session",
        ):
            JulesCandidateDiscoveryService(
                jules,
                connection_id="jules-main",
            ).discover_pull_request_hints(handle)

    def test_session_creation_preserves_manual_plan_approval(self):
        jules = FakeJulesClient()
        handle = _create_handle(jules)

        session_posts = [
            call
            for call in jules.calls
            if call[0] == "POST" and call[1] == "/sessions"
        ]
        self.assertEqual(len(session_posts), 1)
        payload = session_posts[0][2]
        self.assertIs(payload["requirePlanApproval"], True)
        self.assertEqual(payload["automationMode"], "AUTO_CREATE_PR")
        self.assertEqual(
            payload["sourceContext"]["githubRepoContext"][
                "startingBranch"
            ],
            STARTING_BRANCH,
        )


if __name__ == "__main__":
    unittest.main()
