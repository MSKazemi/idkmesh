"""C10-H: two-GitHub-user acceptance fixture for the #598 authority policy.

Offline and fake-identity only. Every identity below is a synthetic numeric
GitHub actor id in a synthetic binding table; no live GitHub, token, or secret
is touched. The fixture composes the shipped pieces end to end instead of
re-testing each in isolation:

  GithubActorClaims -> actor_context_from_github (E3-B, reviewed binding table)
  -> authorize (E3-A) / LocalTaskClaims (C10-D/E) / authorize_github_dispatch
  (C5-F label lane).

It demonstrates the six acceptance items of #598 for an owner/integrator
("alice"), a worker ("bob"), a second worker ("erin"), a reviewer ("carol") and
a second integrator ("frank"), plus an unbound outsider ("mallory"). It does
not execute work, resolve secrets, or merge anything: every authority object
used here is a decision or a claim record.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.enterprise_authz import (
    ACTIONS,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.enterprise_identity_github import (
    GithubActorClaims,
    GithubIdentityAdapterError,
    actor_context_from_github,
    parse_identity_binding_table,
)
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    TrustedGitHubActor,
    authorize_github_dispatch,
)
from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope
from idkmesh.task_claims import (
    ClaimBinding,
    LocalTaskClaims,
    TaskClaimError,
    TaskClaimPolicy,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

SCOPE = TenantScope("tenant-a", "project-main")
NOW = 1_790_168_400

ALICE, BOB, ERIN, CAROL, FRANK, MALLORY = 1001, 1002, 1003, 1004, 1005, 9999
LOGINS = {
    ALICE: "alice-owner",
    BOB: "bob-worker",
    ERIN: "erin-worker",
    CAROL: "carol-reviewer",
    FRANK: "frank-integrator",
    MALLORY: "mallory-outsider",
}
ROLES = {
    ALICE: ["owner", "integrator"],
    BOB: ["worker"],
    ERIN: ["worker"],
    CAROL: ["reviewer"],
    FRANK: ["integrator"],
}
BINDING = ClaimBinding("sha256:" + "a" * 64, "b" * 40, "sha256:" + "c" * 64)


def _document() -> dict:
    return {
        "kind": "idkmesh-enterprise-github-identity-binding-table",
        "schema_version": "0.1",
        "bindings": [
            {
                "actor_id": actor_id,
                "login": LOGINS[actor_id],
                "actor_type": "human",
                "issuer": "github.com",
                "roles": roles,
                "scopes": [
                    {"tenant_id": SCOPE.tenant_id, "project_id": SCOPE.project_id}
                ],
                "data_clearance": "confidential",
                "identity_revision": "github-identity:1",
                "revoked": False,
                "expires_at_epoch": None,
            }
            for actor_id, roles in ROLES.items()
        ],
    }


def _envelope(sender_id: int, label: str = "agent-ready") -> GitHubWebhookEnvelope:
    return GitHubWebhookEnvelope(
        delivery_id="delivery-1",
        event="issues",
        action="labeled",
        repository="MSKazemi/idkmesh",
        repository_id=123,
        sender_login=LOGINS[sender_id],
        sender_id=sender_id,
        issue_number=598,
        label_name=label,
        installation_id=None,
        payload_digest="sha256:" + "d" * 64,
        payload_bytes=256,
    )


class TwoUserAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.table = parse_identity_binding_table(_document())
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "control.sqlite3"
        self.now = 1000

    # -- helpers ---------------------------------------------------------
    def actor(self, actor_id: int, kind: str = "user"):
        return actor_context_from_github(
            GithubActorClaims(actor_id, LOGINS[actor_id], kind), self.table
        )

    def decide(self, actor_id, action, *, risk="low", approver=None, rid="r-1"):
        return authorize(
            AuthorizationRequest(
                request_id=rid,
                scope=SCOPE,
                resource=ScopedResourceRef(SCOPE, "task", "work-unit-598"),
                actor=self.actor(actor_id),
                action=action,
                risk=risk,
                data_classification="internal",
                evaluated_at_epoch=NOW,
                approver=None if approver is None else self.actor(approver),
                approval_reference=None if approver is None else "review:1",
            ),
            self.policy,
        )

    def coordinator(self):
        return LocalTaskClaims(
            LocalMetadataStore(self.path), self.policy, clock=lambda: self.now
        )

    def c5_policy(self):
        return GitHubDispatchAuthorizationPolicy(
            repository="MSKazemi/idkmesh",
            dispatch_labels=frozenset({"agent-ready"}),
            trusted_actors=(
                TrustedGitHubActor(ALICE, LOGINS[ALICE], "owner"),
            ),
        )

    # -- 1. either user can create/propose a WorkUnit ---------------------
    def test_1_proposing_is_not_an_authority_action_and_any_bound_user_may_read(self):
        # Proposal is deliberately not a policy action: it needs no authority
        # because it grants none. Both proposer and non-proposer read alike.
        self.assertNotIn("propose", ACTIONS)
        for actor_id in (ALICE, BOB):
            with self.subTest(actor=LOGINS[actor_id]):
                self.assertEqual(self.decide(actor_id, "read").effect, "allow")

    def test_1_an_unbound_issue_author_cannot_even_obtain_an_identity(self):
        with self.assertRaises(GithubIdentityAdapterError) as caught:
            self.actor(MALLORY)
        self.assertEqual(caught.exception.code, "unknown_actor_id")

    # -- 2. only an authorized actor crosses the dispatch gate ------------
    def test_2_authoring_the_work_unit_grants_no_dispatch_authority(self):
        self.assertEqual(self.decide(ALICE, "dispatch").effect, "allow")
        for proposer in (BOB, CAROL, FRANK):
            with self.subTest(proposer=LOGINS[proposer]):
                denied = self.decide(proposer, "dispatch")
                self.assertEqual((denied.effect, denied.code), ("deny", "role_denied"))

    def test_2_both_dispatch_lanes_agree_on_who_may_dispatch(self):
        cases = {ALICE: True, BOB: False, CAROL: False, FRANK: False}
        for actor_id, expected in cases.items():
            with self.subTest(actor=LOGINS[actor_id]):
                kernel = self.decide(actor_id, "dispatch").effect == "allow"
                label_lane = authorize_github_dispatch(
                    _envelope(actor_id), self.c5_policy()
                ).authorized
                self.assertEqual(kernel, expected)
                self.assertEqual(label_lane, expected)

    # -- 3. concurrent claims resolve deterministically -------------------
    def test_3_concurrent_claims_by_two_users_admit_exactly_one_persistently(self):
        task = ScopedResourceRef(SCOPE, "task", "claimed-task")
        alice = self.actor(ALICE)
        self.coordinator().configure_task(
            task,
            alice,
            TaskClaimPolicy(ack_seconds=10, lease_seconds=30, progress_seconds=60, hard_seconds=100),
        )
        contenders = {BOB: self.coordinator(), ERIN: self.coordinator()}
        start = threading.Event()

        def attempt(actor_id):
            start.wait(10)
            try:
                grant, created = contenders[actor_id].claim(
                    task, self.actor(actor_id), request_id=f"claim-{actor_id}", binding=BINDING
                )
                return ("won", actor_id, grant, created)
            except TaskClaimError as exc:
                return ("lost", actor_id, exc.code, False)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, BOB), pool.submit(attempt, ERIN)]
            start.set()
            results = [future.result(timeout=30) for future in futures]

        won = [r for r in results if r[0] == "won"]
        lost = [r for r in results if r[0] == "lost"]
        self.assertEqual((len(won), len(lost)), (1, 1))
        self.assertTrue(won[0][3])
        self.assertEqual(lost[0][2], "task_capacity_reserved")

        winner = won[0][1]
        snapshot = self.coordinator().snapshot(task, alice)
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0].owner["principal_id"], f"github:human:{winner}")
        # The persisted outcome is stable: replaying the winner's request
        # returns the same grant, and the loser still cannot claim.
        replay, created = self.coordinator().claim(
            task, self.actor(winner), request_id=f"claim-{winner}", binding=BINDING
        )
        self.assertFalse(created)
        self.assertEqual(replay.to_dict(), won[0][2].to_dict())
        loser = lost[0][1]
        with self.assertRaises(TaskClaimError) as caught:
            self.coordinator().claim(
                task, self.actor(loser), request_id=f"claim-{loser}", binding=BINDING
            )
        self.assertEqual(caught.exception.code, "task_capacity_reserved")

    def test_3_a_reviewer_cannot_claim_worker_slots(self):
        task = ScopedResourceRef(SCOPE, "task", "reviewer-claim")
        self.coordinator().configure_task(task, self.actor(ALICE), TaskClaimPolicy())
        with self.assertRaises(TaskClaimError) as caught:
            self.coordinator().claim(task, self.actor(CAROL), request_id="c", binding=BINDING)
        self.assertEqual(caught.exception.code, "role_denied")

    # -- 4. verification records the actual reviewer identity -------------
    def test_4_verification_decision_names_the_actual_reviewer(self):
        decision = self.decide(CAROL, "verify")
        self.assertEqual(decision.effect, "allow")
        record = decision.to_dict()
        self.assertEqual(record["principal_id"], f"github:human:{CAROL}")
        self.assertEqual(record["identity_revision"], "github-identity:1")
        self.assertEqual(record["action"], "verify")

    def test_4_the_worker_is_not_an_automatic_verifier(self):
        denied = self.decide(BOB, "verify")
        self.assertEqual((denied.effect, denied.code), ("deny", "role_denied"))

    def test_4_a_spoofed_reviewer_login_never_reaches_the_record(self):
        with self.assertRaises(GithubIdentityAdapterError) as caught:
            actor_context_from_github(
                GithubActorClaims(CAROL, LOGINS[BOB], "user"), self.table
            )
        self.assertEqual(caught.exception.code, "actor_login_mismatch")

    # -- 5. protected integration follows repository authority ------------
    def test_5_the_verifier_is_not_an_automatic_integrator(self):
        denied = self.decide(CAROL, "integrate")
        self.assertEqual((denied.effect, denied.code), ("deny", "role_denied"))
        self.assertEqual(self.decide(BOB, "integrate").code, "role_denied")

    def test_5_low_risk_integration_by_an_integrator_needs_no_second_person(self):
        self.assertEqual(self.decide(ALICE, "integrate").effect, "allow")

    def test_5_high_risk_integration_needs_a_distinct_authorized_integrator(self):
        needs = self.decide(ALICE, "integrate", risk="high")
        self.assertEqual((needs.effect, needs.code), ("requires_approval", "distinct_approval_required"))
        self.assertEqual(
            self.decide(ALICE, "integrate", risk="high", approver=ALICE).code,
            "self_approval_forbidden",
        )
        # A reviewer's sign-off is review evidence, not integration authority.
        self.assertEqual(
            self.decide(ALICE, "integrate", risk="high", approver=CAROL).code,
            "approver_role_denied",
        )
        allowed = self.decide(ALICE, "integrate", risk="high", approver=FRANK)
        self.assertEqual(allowed.effect, "allow")
        self.assertEqual(allowed.approved_by, f"github:human:{FRANK}")

    # -- 6. unauthorized input cannot broaden permissions or trigger runs --
    def test_6_an_unauthorized_label_is_denied_with_no_secret_resolution(self):
        for sender in (BOB, MALLORY):
            with self.subTest(sender=LOGINS[sender]):
                decision = authorize_github_dispatch(_envelope(sender), self.c5_policy())
                self.assertFalse(decision.authorized)
                record = decision.to_dict()
                self.assertFalse(record["secret_resolution_allowed"])
                self.assertFalse(record["dispatch_performed"])

    def test_6_a_label_name_or_comment_style_claim_cannot_make_a_role(self):
        # A privileged-sounding label from a non-dispatcher is just a label.
        decision = authorize_github_dispatch(
            _envelope(BOB, label="agent-ready"), self.c5_policy()
        )
        self.assertIn("actor_id_not_trusted", decision.reasons)
        self.assertEqual(self.decide(BOB, "dispatch").effect, "deny")
        self.assertEqual(self.decide(BOB, "manage_policy", risk="high").effect, "deny")

    def test_6_high_risk_dispatch_cannot_be_triggered_without_a_distinct_approver(self):
        self.assertEqual(
            self.decide(ALICE, "dispatch", risk="high").code, "distinct_approval_required"
        )
        # Even the approver cannot be a worker: roles, not the act of
        # volunteering, carry authority.
        self.assertEqual(
            self.decide(ALICE, "dispatch", risk="high", approver=BOB).code,
            "approver_role_denied",
        )
        self.assertEqual(
            self.decide(ALICE, "dispatch", risk="high", approver=FRANK).effect, "allow"
        )


if __name__ == "__main__":
    unittest.main()
