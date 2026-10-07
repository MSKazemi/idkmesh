"""Composed C5 GitHub dispatch exit-gate proof for issue #578."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_routing import (
    ConnectorProfile,
    RoutingDecision,
    resolve_routes,
)
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.github_delivery_idempotency import admit_github_delivery
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    TrustedGitHubActor,
    authorize_github_dispatch,
)
from idkmesh.github_explicit_dispatch import (
    GitHubExplicitDispatchRequest,
    dispatch_github_run_once,
)
from idkmesh.github_issue_preview import (
    GitHubIssueWorkPolicy,
    parse_github_issue_snapshot,
    preview_github_issue_work_unit,
)
from idkmesh.github_routing_projection import project_routing_to_github
from idkmesh.github_status_update import (
    GitHubIssueComment,
    GitHubRunStatus,
    publish_github_run_status_once,
)
from idkmesh.github_webhook_ingress import GitHubWebhookReceiver


REPOSITORY = "MSKazemi/idkmesh"
ISSUE_NUMBER = 77
DELIVERY_ID = "550e8400-e29b-41d4-a716-446655440000"
WEBHOOK_SECRET = "test-webhook-secret-material-32-bytes"
SOURCE_REVISION = "0123456789abcdef0123456789abcdef01234567"

WEBHOOK_PAYLOAD = {
    "action": "labeled",
    "repository": {"id": 123, "full_name": REPOSITORY},
    "sender": {"id": 42, "login": "TrustedMaintainer"},
    "issue": {
        "number": ISSUE_NUMBER,
        "title": "Untrusted webhook copy of the issue",
        "body": "Webhook issue text is not task authority.",
    },
    "label": {"name": "agent-ready"},
    "installation": {"id": 9001},
}

ISSUE_SNAPSHOT = {
    "id": 9001,
    "number": ISSUE_NUMBER,
    "title": "Add a bounded integration fixture",
    "body": "Exercise the composed GitHub dispatch bridge once and replay it.",
    "state": "open",
    "locked": False,
    "user": {"login": "contributor", "id": 88},
    "author_association": "CONTRIBUTOR",
    "labels": [{"name": "agent-ready"}, {"name": "testing"}],
    "html_url": f"https://github.com/{REPOSITORY}/issues/{ISSUE_NUMBER}",
    "updated_at": "2026-09-24T01:00:00Z",
}


class _IssueCommentTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def create_issue_comment(
        self,
        *,
        repository: str,
        issue_number: int,
        body: str,
    ) -> GitHubIssueComment:
        self.calls.append((repository, issue_number, body))
        return GitHubIssueComment(
            comment_id=1234,
            html_url=(
                f"https://github.com/{repository}/issues/"
                f"{issue_number}#issuecomment-1234"
            ),
        )


def _webhook_request() -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        WEBHOOK_PAYLOAD,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return body, {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": DELIVERY_ID,
        "X-GitHub-Event": "issues",
    }


def _routing_projection():
    decision = RoutingDecision(
        required_capability_tier="T2",
        authority_mode="agent_candidate",
        risk_class="low",
        task_classes=frozenset({"coding"}),
        required_tools=frozenset({"git"}),
        allowed_connector_kinds=frozenset({"agent"}),
        external_processing_allowed=False,
        project_spend_usd_max=0,
        prefer_zero_cost=True,
        independent_reviewer_required=True,
    )
    connector = ConnectorProfile(
        connection_id="agent-local",
        kind="agent",
        driver="fixture",
        capability_tiers=frozenset({"T2"}),
        task_classes=frozenset({"coding"}),
        tools=frozenset({"git"}),
        max_risk="low",
        external_processing=False,
        project_cost_usd=0,
    )
    return project_routing_to_github(
        decision,
        resolve_routes(decision, [connector]),
    )


class GitHubDispatchBridgeIntegrationTests(unittest.TestCase):
    def test_authorized_action_dispatches_and_publishes_exactly_once_on_replay(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMetadataStore(Path(temp_dir) / "state.sqlite")
            receiver = GitHubWebhookReceiver(
                expected_repository=REPOSITORY,
                webhook_secret=WEBHOOK_SECRET,
                allowed_event_actions={"issues": {"labeled"}},
            )
            body, headers = _webhook_request()

            envelope = receiver.receive(body=body, headers=headers)
            delivery = admit_github_delivery(
                store=store,
                envelope=envelope,
                received_at="2026-09-24T15:00:00Z",
            )

            snapshot = parse_github_issue_snapshot(
                ISSUE_SNAPSHOT,
                repository=REPOSITORY,
                expected_number=ISSUE_NUMBER,
            )
            preview = preview_github_issue_work_unit(
                snapshot,
                source_revision=SOURCE_REVISION,
                policy=GitHubIssueWorkPolicy(
                    repository=REPOSITORY,
                    allowed_paths=("idkmesh/**", "tests/**"),
                    forbidden_paths=(".github/**", "SECURITY.md"),
                ),
            )
            self.assertIn(ISSUE_SNAPSHOT["body"], preview.work_unit["objective"])
            self.assertNotIn(
                WEBHOOK_PAYLOAD["issue"]["body"],
                preview.work_unit["objective"],
            )

            routing = _routing_projection()
            self.assertEqual(routing.selected_connection_id, "agent-local")
            self.assertFalse(routing.to_dict()["github_mutation_performed"])

            authorization = authorize_github_dispatch(
                envelope,
                GitHubDispatchAuthorizationPolicy(
                    repository=REPOSITORY,
                    dispatch_labels=frozenset({"agent-ready"}),
                    trusted_actors=(
                        TrustedGitHubActor(
                            actor_id=42,
                            login="TrustedMaintainer",
                            role="maintainer",
                        ),
                    ),
                    allowed_installation_ids=frozenset({9001}),
                ),
            )
            self.assertTrue(authorization.authorized)

            request = GitHubExplicitDispatchRequest(
                project_id=REPOSITORY,
                delivery_run_id=delivery.record.run_id,
                delivery_id=envelope.delivery_id,
                delivery_request_digest=delivery.request_digest,
                issue_number=ISSUE_NUMBER,
                work_unit_id=preview.work_unit["id"],
                work_unit_version=preview.work_unit["version"],
                work_unit_digest=preview.work_unit_digest,
                source_revision=preview.source_revision,
                routing_digest=routing.routing_digest,
                routing_policy_version="c5-integration-v0.1",
                selected_connection_id=routing.selected_connection_id,
                policy_revision="project-policy-v1",
            )

            dispatch_calls: list[str] = []

            def dispatcher(candidate: GitHubExplicitDispatchRequest) -> str:
                dispatch_calls.append(candidate.selected_connection_id)
                return "provider/session-123"

            first_dispatch = dispatch_github_run_once(
                store=store,
                authorization=authorization,
                request=request,
                dispatcher=dispatcher,
                created_at="2026-09-24T15:01:00Z",
            )
            self.assertTrue(first_dispatch.created)
            self.assertEqual(dispatch_calls, ["agent-local"])
            self.assertFalse(first_dispatch.to_dict()["candidate_accepted"])
            self.assertFalse(first_dispatch.to_dict()["merge_authority"])

            status = GitHubRunStatus(
                repository=REPOSITORY,
                issue_number=ISSUE_NUMBER,
                run_id=first_dispatch.dispatch_run_id,
                state="dispatched",
                work_unit_id=preview.work_unit["id"],
                work_unit_digest=preview.work_unit_digest,
                routing_digest=routing.routing_digest,
            )
            transport = _IssueCommentTransport()
            first_publication = publish_github_run_status_once(
                store=store,
                status=status,
                transport=transport,
                created_at="2026-09-24T15:02:00Z",
            )
            self.assertTrue(first_publication.created)
            self.assertEqual(len(transport.calls), 1)
            self.assertFalse(
                first_publication.to_dict()["candidate_accepted"]
            )
            self.assertFalse(first_publication.to_dict()["merge_authority"])

            replay_envelope = receiver.receive(body=body, headers=headers)
            replay_delivery = admit_github_delivery(
                store=LocalMetadataStore(store.path),
                envelope=replay_envelope,
                received_at="2026-09-24T15:03:00Z",
            )
            self.assertTrue(replay_delivery.replayed)
            self.assertEqual(
                replay_delivery.record.run_id,
                delivery.record.run_id,
            )

            replay_dispatch = dispatch_github_run_once(
                store=LocalMetadataStore(store.path),
                authorization=authorize_github_dispatch(
                    replay_envelope,
                    GitHubDispatchAuthorizationPolicy(
                        repository=REPOSITORY,
                        dispatch_labels=frozenset({"agent-ready"}),
                        trusted_actors=(
                            TrustedGitHubActor(
                                actor_id=42,
                                login="TrustedMaintainer",
                                role="maintainer",
                            ),
                        ),
                        allowed_installation_ids=frozenset({9001}),
                    ),
                ),
                request=request,
                dispatcher=dispatcher,
                created_at="2026-09-24T15:04:00Z",
            )
            self.assertTrue(replay_dispatch.replayed)
            self.assertEqual(
                replay_dispatch.dispatch_run_id,
                first_dispatch.dispatch_run_id,
            )
            self.assertEqual(dispatch_calls, ["agent-local"])

            replay_publication = publish_github_run_status_once(
                store=LocalMetadataStore(store.path),
                status=status,
                transport=transport,
                created_at="2026-09-24T15:05:00Z",
            )
            self.assertTrue(replay_publication.replayed)
            self.assertEqual(
                replay_publication.comment_id,
                first_publication.comment_id,
            )
            self.assertEqual(len(transport.calls), 1)

            runs, has_more = LocalMetadataStore(store.path).list_runs(limit=10)
            self.assertFalse(has_more)
            self.assertEqual(len(runs), 3)
            self.assertEqual(
                sorted(run.state for run in runs),
                ["dispatched", "proposed", "published"],
            )


if __name__ == "__main__":
    unittest.main()
