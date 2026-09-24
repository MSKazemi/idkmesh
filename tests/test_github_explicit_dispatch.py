from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorization,
)
from idkmesh.github_explicit_dispatch import (
    GitHubDispatchConflict,
    GitHubDispatchExecutionError,
    GitHubDispatchRecoveryRequired,
    GitHubExplicitDispatchRequest,
    dispatch_github_run_once,
    github_dispatch_request_digest,
)


SHA = "0123456789abcdef0123456789abcdef01234567"


def _authorization(**overrides):
    values = {
        "authorized": True,
        "reasons": (),
        "delivery_id": "delivery-123",
        "repository": "MSKazemi/idkmesh",
        "issue_number": 77,
        "actor_id": 42,
        "actor_login": "maintainer",
        "actor_role": "maintainer",
        "label_name": "agent-ready",
        "installation_id": 9001,
    }
    values.update(overrides)
    return GitHubDispatchAuthorization(**values)


def _request(**overrides):
    values = {
        "project_id": "MSKazemi/idkmesh",
        "delivery_run_id": "github/delivery-parent",
        "delivery_id": "delivery-123",
        "delivery_request_digest": "sha256:" + "a" * 64,
        "issue_number": 77,
        "work_unit_id": "github/mskazemi/idkmesh/issue-77",
        "work_unit_version": 1,
        "work_unit_digest": "sha256:" + "b" * 64,
        "source_revision": SHA,
        "routing_digest": "sha256:" + "c" * 64,
        "routing_policy_version": "c1-v0.1",
        "selected_connection_id": "agent-local",
        "policy_revision": "project-policy-v1",
    }
    values.update(overrides)
    return GitHubExplicitDispatchRequest(**values)


class GitHubExplicitDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalMetadataStore(
            Path(self.temp.name) / "state.sqlite"
        )
        self._reserve_parent()

    def tearDown(self):
        self.temp.cleanup()

    def _reserve_parent(self):
        self.store.admit_run(
            run_id="github/delivery-parent",
            idempotency_key="github-webhook:123:delivery-123",
            request_digest="sha256:" + "a" * 64,
            state="proposed",
            metadata={
                "schema_version": "0.1",
                "kind": "github-webhook-delivery-admission",
                "repository": "MSKazemi/idkmesh",
                "repository_id": 123,
                "delivery_id": "delivery-123",
                "event": "issues",
                "action": "labeled",
                "sender_login": "maintainer",
                "sender_id": 42,
                "issue_number": 77,
                "label_name": "agent-ready",
                "installation_id": 9001,
                "payload_digest": "sha256:" + "d" * 64,
                "payload_bytes": 500,
            },
            created_at="2026-09-24T15:00:00Z",
        )

    def test_first_dispatch_calls_selected_connector_once(self):
        calls = []

        def dispatcher(request):
            calls.append(request.selected_connection_id)
            return "provider/session-123"

        result = dispatch_github_run_once(
            store=self.store,
            authorization=_authorization(),
            request=_request(),
            dispatcher=dispatcher,
            created_at="2026-09-24T15:01:00Z",
        )

        self.assertTrue(result.created)
        self.assertFalse(result.replayed)
        self.assertEqual(calls, ["agent-local"])
        self.assertEqual(
            result.provider_reference,
            "provider/session-123",
        )
        stored = self.store.get_run(result.dispatch_run_id)
        self.assertEqual(stored.state, "dispatched")
        self.assertEqual(
            stored.metadata["provider_reference"],
            "provider/session-123",
        )
        self.assertFalse(result.to_dict()["candidate_accepted"])
        self.assertFalse(result.to_dict()["merge_authority"])

    def test_exact_replay_returns_provider_reference_without_dispatch(self):
        calls = []

        def dispatcher(request):
            calls.append(request.selected_connection_id)
            return "provider/session-123"

        first = dispatch_github_run_once(
            store=self.store,
            authorization=_authorization(),
            request=_request(),
            dispatcher=dispatcher,
            created_at="2026-09-24T15:01:00Z",
        )
        second = dispatch_github_run_once(
            store=self.store,
            authorization=_authorization(),
            request=_request(),
            dispatcher=dispatcher,
            created_at="2026-09-24T15:02:00Z",
        )

        self.assertEqual(calls, ["agent-local"])
        self.assertFalse(second.created)
        self.assertTrue(second.replayed)
        self.assertEqual(
            second.dispatch_run_id,
            first.dispatch_run_id,
        )
        self.assertEqual(
            second.provider_reference,
            first.provider_reference,
        )

    def test_same_delivery_with_changed_dispatch_request_conflicts(self):
        calls = []

        def dispatcher(request):
            calls.append(request.work_unit_digest)
            return "provider/session-123"

        dispatch_github_run_once(
            store=self.store,
            authorization=_authorization(),
            request=_request(),
            dispatcher=dispatcher,
            created_at="2026-09-24T15:01:00Z",
        )

        with self.assertRaises(GitHubDispatchConflict):
            dispatch_github_run_once(
                store=self.store,
                authorization=_authorization(),
                request=_request(
                    work_unit_digest="sha256:" + "e" * 64,
                ),
                dispatcher=dispatcher,
                created_at="2026-09-24T15:02:00Z",
            )
        self.assertEqual(len(calls), 1)

    def test_unauthorized_request_never_reserves_or_dispatches(self):
        calls = []
        with self.assertRaisesRegex(
            GitHubDispatchConflict,
            "authorization",
        ):
            dispatch_github_run_once(
                store=self.store,
                authorization=_authorization(
                    authorized=False,
                    reasons=("actor_role_not_authorized",),
                ),
                request=_request(),
                dispatcher=lambda request: calls.append(request),
                created_at="2026-09-24T15:01:00Z",
            )
        self.assertEqual(calls, [])

    def test_parent_delivery_identity_must_match_authorization(self):
        for authorization, request in (
            (
                _authorization(delivery_id="other-delivery"),
                _request(),
            ),
            (
                _authorization(issue_number=88),
                _request(),
            ),
            (
                _authorization(actor_id=99),
                _request(),
            ),
        ):
            with self.subTest(
                authorization=authorization,
                request=request,
            ):
                with self.assertRaises(GitHubDispatchConflict):
                    dispatch_github_run_once(
                        store=self.store,
                        authorization=authorization,
                        request=request,
                        dispatcher=lambda _: "never",
                        created_at="2026-09-24T15:01:00Z",
                    )

    def test_incomplete_preexisting_dispatch_requires_reconciliation(self):
        request = _request()
        authorization = _authorization()
        digest = github_dispatch_request_digest(
            request,
            authorization,
        )
        idempotency_key = (
            "github-dispatch:" + request.delivery_run_id
        )
        run_id = (
            "github-dispatch/"
            + __import__(
                "hashlib"
            ).sha256(
                __import__("json").dumps(
                    {
                        "idempotency_key": idempotency_key,
                        "request_digest": digest,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()[:24]
        )
        # Use the public store contract to model a crash after reservation.
        self.store.admit_run(
            run_id=run_id,
            idempotency_key=idempotency_key,
            request_digest=digest,
            state="admitted",
            metadata={
                "schema_version": "0.1",
                "kind": "github-explicit-dispatch-admission",
            },
            created_at="2026-09-24T15:01:00Z",
        )
        calls = []
        with self.assertRaises(GitHubDispatchRecoveryRequired):
            dispatch_github_run_once(
                store=self.store,
                authorization=authorization,
                request=request,
                dispatcher=lambda r: calls.append(r),
                created_at="2026-09-24T15:02:00Z",
            )
        self.assertEqual(calls, [])

    def test_dispatcher_error_is_retained_and_not_retried_automatically(self):
        calls = []

        def failing(request):
            calls.append(request.selected_connection_id)
            raise RuntimeError("provider unavailable")

        with self.assertRaises(GitHubDispatchExecutionError):
            dispatch_github_run_once(
                store=self.store,
                authorization=_authorization(),
                request=_request(),
                dispatcher=failing,
                created_at="2026-09-24T15:01:00Z",
            )
        self.assertEqual(calls, ["agent-local"])

        with self.assertRaises(GitHubDispatchRecoveryRequired):
            dispatch_github_run_once(
                store=self.store,
                authorization=_authorization(),
                request=_request(),
                dispatcher=failing,
                created_at="2026-09-24T15:02:00Z",
            )
        self.assertEqual(calls, ["agent-local"])

    def test_invalid_provider_reference_fails_closed(self):
        with self.assertRaises(GitHubDispatchExecutionError):
            dispatch_github_run_once(
                store=self.store,
                authorization=_authorization(),
                request=_request(),
                dispatcher=lambda _: "",
                created_at="2026-09-24T15:01:00Z",
            )

    def test_request_digest_binds_authorization_actor_and_policy(self):
        request = _request()
        base = github_dispatch_request_digest(
            request,
            _authorization(),
        )
        actor_changed = github_dispatch_request_digest(
            request,
            _authorization(
                actor_id=43,
                actor_login="other-maintainer",
            ),
        )
        policy_changed = github_dispatch_request_digest(
            _request(policy_revision="project-policy-v2"),
            _authorization(),
        )
        self.assertNotEqual(base, actor_changed)
        self.assertNotEqual(base, policy_changed)


if __name__ == "__main__":
    unittest.main()
