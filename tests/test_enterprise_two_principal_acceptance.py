"""E3-G: enterprise two-principal acceptance fixture (#670).

Offline, fake identities only. Every identity is a synthetic ``ActorContext``;
no IdP, GitHub, token or secret is touched. The fixture drives the shipped
enterprise kernel together instead of re-testing each piece alone:

    authorize (E3-A) behind AuthorizationDecisionCache (E3-D), with every
    outcome appended to the tamper-evident LocalEnterpriseAuditLedger (E4)
    under a tenant/project TenantScope.

The GitHub two-user case is owned by ``test_c10_two_user_acceptance.py`` (#598).
What this file pins is what that fixture cannot: the enterprise kernel's
proposer / dispatcher / reviewer / integrator paths with high-risk distinct
approval, and the freshness seams around the cache -- a cached ALLOW must not
satisfy a different approver, must not leak across tenants, and must not
survive a revocation, an expiry or a policy edit -- with every denied or
stale outcome recorded in the audit ledger with its reason code and nothing
free-form.

Nothing here wires the cache into live dispatch/API enforcement (E3-F) or
implements break-glass (E3-E). A decision and an audit event are evidence only.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.enterprise_audit import (
    AuditEventInput,
    EnterpriseAuditError,
    LocalEnterpriseAuditLedger,
)
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
)
from idkmesh.enterprise_authz_cache import (
    AuthorizationDecisionCache,
    decision_cache_key,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

NOW = 1791406800
REVISION = "a" * 40
OUTCOME = {"allow": "succeeded", "deny": "denied", "requires_approval": "not_executed"}


class EnterpriseTwoPrincipalAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = LocalEnterpriseAuditLedger(
            Path(self.tmp.name) / "audit.sqlite3"
        )
        self.addCleanup(self.ledger.close)
        self.scope_a = TenantScope("tenant-a", "project-main")
        self.scope_b = TenantScope("tenant-b", "project-main")
        self.res_a = ScopedResourceRef(self.scope_a, "candidate", "candidate-17")
        self.res_b = ScopedResourceRef(self.scope_b, "candidate", "candidate-17")
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.cache = AuthorizationDecisionCache(max_age_seconds=300)
        self.service = self.identity(
            "service:audit-writer",
            actor_type="service",
            roles=("auditor",),
            scopes=(self.scope_a, self.scope_b),
        )
        self.alice = self.identity("github:user:alice", roles=("worker",))
        self.bob = self.identity("github:user:bob", roles=("dispatcher",))
        self.carol = self.identity("github:user:carol", roles=("reviewer",))
        self.dave = self.identity("github:user:dave", roles=("integrator",))
        self.erin = self.identity("github:user:erin", roles=("admin",))
        self._seq = 0

    def identity(
        self,
        principal: str,
        *,
        actor_type: str = "human",
        roles: tuple[str, ...],
        scopes: tuple[TenantScope, ...] | None = None,
        revision: str | None = None,
        **overrides,
    ) -> ActorContext:
        fields = dict(
            principal_id=principal,
            actor_type=actor_type,
            issuer="idp.example.test",
            roles=frozenset(roles),
            scopes=scopes or (self.scope_a,),
            data_clearance="confidential",
            identity_revision=revision or f"identity:{principal}:1",
        )
        fields.update(overrides)
        return ActorContext(**fields)

    def enforce(
        self,
        actor: ActorContext,
        action: str,
        *,
        at: int,
        risk: str = "low",
        approver: ActorContext | None = None,
        ref: str | None = None,
        scope: TenantScope | None = None,
        resource: ScopedResourceRef | None = None,
        policy: AuthorizationPolicy | None = None,
    ) -> tuple[AuthorizationDecision, dict]:
        """A minimal enforcement point: decide through the cache, then audit."""

        self._seq += 1
        request = AuthorizationRequest(
            request_id=f"request:{self._seq}",
            scope=scope or self.scope_a,
            resource=resource or self.res_a,
            actor=actor,
            action=action,
            risk=risk,
            data_classification="internal",
            evaluated_at_epoch=at,
            approver=approver,
            approval_reference=ref if approver is not None else None,
        )
        decision = self.cache.authorize(request, policy or self.policy)
        event = self.ledger.append(
            AuditEventInput(
                occurred_at_epoch=at,
                actor=actor,
                service=self.service,
                decision=decision,
                resource_revision=REVISION,
                outcome=OUTCOME[decision.effect],
            )
        )
        return decision, event

    def codes(self, *pairs: tuple[AuthorizationDecision, dict]) -> list[str]:
        return [decision.code for decision, _ in pairs]

    # -- proposer / dispatcher / reviewer / integrator paths ---------------

    def test_role_paths_with_high_risk_distinct_approval(self) -> None:
        t = NOW
        # Proposer / worker: may read and claim, may not dispatch or integrate.
        self.assertEqual(self.enforce(self.alice, "read", at=t)[0].effect, "allow")
        self.assertEqual(self.enforce(self.alice, "claim", at=t)[0].effect, "allow")
        self.assertEqual(
            self.enforce(self.alice, "dispatch", at=t)[0].code, "role_denied"
        )
        self.assertEqual(
            self.enforce(self.alice, "integrate", at=t)[0].code, "role_denied"
        )

        # Dispatcher: high-risk dispatch needs a distinct authorized approver.
        self.assertEqual(
            self.enforce(self.bob, "dispatch", at=t, risk="high")[0].code,
            "distinct_approval_required",
        )
        d, _ = self.enforce(
            self.bob, "dispatch", at=t, risk="high", approver=self.dave, ref="review:1"
        )
        self.assertEqual((d.effect, d.approved_by), ("allow", "github:user:dave"))

        # Worker execute at high risk: dispatcher approves; reviewer, the worker
        # itself, and a worker-role colleague do not.
        d, _ = self.enforce(
            self.alice, "execute", at=t, risk="high", approver=self.bob, ref="review:2"
        )
        self.assertEqual((d.effect, d.approved_by), ("allow", "github:user:bob"))
        self.assertEqual(
            self.enforce(
                self.alice, "execute", at=t, risk="high",
                approver=self.carol, ref="review:2",
            )[0].code,
            "approver_role_denied",
        )
        both = self.identity(
            "github:user:alice", roles=("worker", "dispatcher"),
            revision="identity:alice:2",
        )
        self.assertEqual(
            self.enforce(
                both, "execute", at=t, risk="high", approver=both, ref="review:2"
            )[0].code,
            "self_approval_forbidden",
        )

        # Reviewer verifies; the worker role cannot.
        self.assertEqual(self.enforce(self.carol, "verify", at=t)[0].effect, "allow")
        self.assertEqual(
            self.enforce(self.alice, "verify", at=t)[0].code, "role_denied"
        )

        # Integrator: high-risk integrate needs a distinct integrator/admin/owner.
        self.assertEqual(
            self.enforce(
                self.dave, "integrate", at=t, risk="high",
                approver=self.alice, ref="review:3",
            )[0].code,
            "approver_role_denied",
        )
        self.assertEqual(
            self.enforce(
                self.dave, "integrate", at=t, risk="high",
                approver=self.dave, ref="review:3",
            )[0].code,
            "self_approval_forbidden",
        )
        d, _ = self.enforce(
            self.dave, "integrate", at=t, risk="high",
            approver=self.erin, ref="review:3",
        )
        self.assertEqual((d.effect, d.approved_by), ("allow", "github:user:erin"))

        # Every outcome above, allowed or not, is in one verifiable ledger.
        events = self.ledger.list_events(tenant_id="tenant-a")
        self.assertEqual(len(events), self._seq)
        self.assertTrue(self.ledger.verify().ok)
        for event in events:
            self.assertEqual(
                event["outcome"], OUTCOME[event["authorization"]["effect"]]
            )

    # -- separation of duties across the cache -----------------------------

    def test_cached_allow_does_not_satisfy_a_different_approver(self) -> None:
        kwargs = dict(risk="high", ref="review:7")
        first, _ = self.enforce(
            self.alice, "execute", at=NOW, approver=self.bob, **kwargs
        )
        self.assertEqual(first.code, "authorized_with_distinct_approval")

        substitutes = {
            "approver_role_denied": self.carol,
            "self_approval_forbidden": self.alice,
            "approver_scope_denied": self.identity(
                "github:user:bob", roles=("dispatcher",), scopes=(self.scope_b,),
                revision="identity:bob:other-tenant",
            ),
            "approver_type_denied": self.identity(
                "provider:acme", actor_type="provider", roles=("dispatcher",)
            ),
        }
        for expected, approver in substitutes.items():
            with self.subTest(expected):
                d, _ = self.enforce(
                    self.alice, "execute", at=NOW + 1, approver=approver, **kwargs
                )
                self.assertEqual((d.effect, d.code), ("requires_approval", expected))
                self.assertIsNone(d.approved_by)
        d, _ = self.enforce(self.alice, "execute", at=NOW + 1, risk="high")
        self.assertEqual(d.code, "distinct_approval_required")
        self.assertEqual(self.cache.hits, 0)

        # Only the identical actor + approver + reference reuses the entry, and
        # the reused decision still names the original approver and reference.
        again, _ = self.enforce(
            self.alice, "execute", at=NOW + 2, approver=self.bob, **kwargs
        )
        self.assertEqual(self.cache.hits, 1)
        self.assertEqual(
            (again.approved_by, again.approval_reference),
            ("github:user:bob", "review:7"),
        )

    def test_demoted_approver_loses_a_cached_approval(self) -> None:
        kwargs = dict(risk="high", ref="review:8")
        self.enforce(self.alice, "execute", at=NOW, approver=self.bob, **kwargs)
        demoted = replace(self.bob, roles=frozenset({"reviewer"}))
        d, _ = self.enforce(
            self.alice, "execute", at=NOW + 1, approver=demoted, **kwargs
        )
        self.assertEqual((d.effect, d.code), ("requires_approval", "approver_role_denied"))
        self.assertEqual(self.cache.hits, 0)

    # -- tenant isolation through the cache --------------------------------

    def test_cached_allow_never_crosses_a_tenant_boundary(self) -> None:
        alice_b = self.identity(
            "github:user:alice", roles=("worker",), scopes=(self.scope_b,),
            revision="identity:alice:tenant-b",
        )
        warm, _ = self.enforce(self.alice, "execute", at=NOW)
        self.assertEqual(warm.tenant_id, "tenant-a")

        # Same principal id, same resource id, other tenant: its own entry.
        other, _ = self.enforce(
            alice_b, "execute", at=NOW + 1, scope=self.scope_b, resource=self.res_b
        )
        self.assertEqual((other.effect, other.tenant_id), ("allow", "tenant-b"))

        # Tenant-A identity cannot ride the warm entry into tenant B, whether
        # the request or only the resource points there.
        into_b, _ = self.enforce(
            self.alice, "execute", at=NOW + 2, scope=self.scope_b, resource=self.res_b
        )
        self.assertEqual(into_b.code, "actor_scope_denied")
        mixed_resource, _ = self.enforce(
            self.alice, "execute", at=NOW + 3, scope=self.scope_a, resource=self.res_b
        )
        self.assertEqual(mixed_resource.code, "scope_mismatch")
        mixed_scope, _ = self.enforce(
            self.alice, "execute", at=NOW + 4, scope=self.scope_b, resource=self.res_a
        )
        self.assertEqual(mixed_scope.code, "scope_mismatch")
        self.assertEqual(self.cache.hits, 0)

        # Tenant/project concatenation ambiguity cannot collapse two keys.
        k1 = decision_cache_key(
            AuthorizationRequest(
                "request:k1", TenantScope("tenant-a", "x-y"),
                ScopedResourceRef(TenantScope("tenant-a", "x-y"), "candidate", "c"),
                self.alice, "read", "low", "internal", NOW,
            ),
            self.policy,
        )
        k2 = decision_cache_key(
            AuthorizationRequest(
                "request:k2", TenantScope("tenant-a-x", "y"),
                ScopedResourceRef(TenantScope("tenant-a-x", "y"), "candidate", "c"),
                self.alice, "read", "low", "internal", NOW,
            ),
            self.policy,
        )
        self.assertNotEqual(k1, k2)

        # The ledger is tenant-partitioned: tenant B sees only its own events.
        b_events = self.ledger.list_events(tenant_id="tenant-b")
        self.assertEqual(
            {e["scope"]["tenant_id"] for e in b_events}, {"tenant-b"}
        )
        self.assertEqual(
            [e["authorization"]["reason_code"] for e in b_events],
            ["authorized", "actor_scope_denied", "scope_mismatch"],
        )
        self.assertEqual(
            {e["scope"]["tenant_id"] for e in self.ledger.list_events(tenant_id="tenant-a")},
            {"tenant-a"},
        )
        self.assertTrue(self.ledger.verify().ok)

        # An identity bound only to tenant B cannot be audited into tenant A
        # by a writer that is not bound to tenant A.
        a_only_writer = replace(self.service, scopes=(self.scope_a,))
        with self.assertRaises(EnterpriseAuditError) as ctx:
            AuditEventInput(
                occurred_at_epoch=NOW + 5,
                actor=alice_b,
                service=a_only_writer,
                decision=other,
                resource_revision=REVISION,
                outcome="succeeded",
            )
        self.assertEqual(ctx.exception.code, "service_scope_mismatch")

    # -- revocation and expiry end to end ----------------------------------

    def test_revocation_denies_immediately_and_is_audited(self) -> None:
        allowed, _ = self.enforce(self.alice, "execute", at=NOW)
        self.assertEqual(allowed.effect, "allow")

        revoked = replace(
            self.alice, revoked=True, identity_revision="identity:alice:2"
        )
        # A revocation feed may drop entries eagerly; correctness must not
        # depend on it, so assert both with and without invalidation.
        for invalidate in (False, True):
            with self.subTest(invalidate=invalidate):
                if invalidate:
                    # The warm ALLOW and the cached revoked-DENY entry.
                    self.assertEqual(
                        self.cache.invalidate_principal("github:user:alice"), 2
                    )
                    self.assertEqual(len(self.cache), 0)
                d, event = self.enforce(revoked, "execute", at=NOW + 10 + invalidate)
                self.assertEqual((d.effect, d.code), ("deny", "actor_revoked"))
                self.assertEqual(event["outcome"], "denied")
                self.assertEqual(event["authorization"]["reason_code"], "actor_revoked")
                self.assertEqual(event["actor"]["identity_revision"], "identity:alice:2")
        self.assertEqual(self.cache.hits, 0)

        # The stale ALLOW cannot be re-audited as the revoked identity's decision.
        with self.assertRaises(EnterpriseAuditError) as ctx:
            AuditEventInput(
                occurred_at_epoch=NOW + 20,
                actor=revoked,
                service=self.service,
                decision=allowed,
                resource_revision=REVISION,
                outcome="succeeded",
            )
        self.assertEqual(ctx.exception.code, "actor_decision_mismatch")
        self.assertTrue(self.ledger.verify().ok)

    def test_invalidate_principal_drops_standing_entries_for_actor_and_approver(
        self,
    ) -> None:
        self.enforce(
            self.alice, "execute", at=NOW, risk="high",
            approver=self.bob, ref="review:9",
        )
        self.enforce(self.bob, "claim", at=NOW)
        self.assertEqual(len(self.cache), 2)
        self.assertEqual(self.cache.invalidate_principal("github:user:bob"), 2)
        revoked_bob = replace(self.bob, revoked=True)
        d, event = self.enforce(
            self.alice, "execute", at=NOW + 1, risk="high",
            approver=revoked_bob, ref="review:9",
        )
        self.assertEqual((d.effect, d.code), ("requires_approval", "approver_revoked"))
        self.assertEqual(event["outcome"], "not_executed")
        self.assertIsNone(event["authorization"]["approved_by"])

    def test_expired_identity_loses_cached_authority_at_the_boundary(self) -> None:
        short = self.identity(
            "github:user:alice", roles=("worker",), expires_at_epoch=NOW + 60,
        )
        self.enforce(short, "execute", at=NOW)
        hit, _ = self.enforce(short, "execute", at=NOW + 59)
        self.assertEqual((hit.effect, self.cache.hits), ("allow", 1))
        d, event = self.enforce(short, "execute", at=NOW + 60)
        self.assertEqual((d.effect, d.code), ("deny", "actor_expired"))
        self.assertEqual(event["authorization"]["reason_code"], "actor_expired")
        self.assertEqual(self.cache.hits, 1)

    # -- policy edits end to end -------------------------------------------

    def test_policy_edits_are_not_served_from_stale_entries(self) -> None:
        before, event_before = self.enforce(self.alice, "execute", at=NOW)
        self.assertEqual(before.effect, "allow")

        # Tightening: low-risk execute now needs a distinct approver.
        tighter = AuthorizationPolicy(
            self.policy.policy_id,
            "0.2",
            tuple(
                replace(r, distinct_approval_at_risk="low")
                if r.action == "execute" else r
                for r in self.policy.rules
            ),
        )
        after, event_after = self.enforce(
            self.alice, "execute", at=NOW + 1, policy=tighter
        )
        self.assertEqual((after.effect, after.code), ("requires_approval", "distinct_approval_required"))
        self.assertEqual(event_before["authorization"]["policy_revision"], "0.1")
        self.assertEqual(event_after["authorization"]["policy_revision"], "0.2")
        self.assertEqual(self.cache.hits, 0)

        # Tightening with no revision bump still cannot reuse the old ALLOW.
        unbumped = AuthorizationPolicy(
            self.policy.policy_id, "0.1", tighter.rules
        )
        d, event = self.enforce(self.alice, "execute", at=NOW + 2, policy=unbumped)
        self.assertEqual(d.code, "distinct_approval_required")
        self.assertEqual(event["authorization"]["effect"], "requires_approval")
        self.assertEqual(self.cache.hits, 0)

        # Reverting to the original policy is a legitimate hit on the old entry
        # (same content digest), and is still re-stamped for this request.
        back, _ = self.enforce(self.alice, "execute", at=NOW + 3)
        self.assertEqual((back.effect, self.cache.hits), ("allow", 1))
        self.assertEqual(back.evaluated_at_epoch, NOW + 3)
        self.assertTrue(self.ledger.verify().ok)

    # -- the ledger holds reasons, not free text or identity material ------

    def test_audit_records_reasons_without_messages_or_identity_claims(self) -> None:
        self.enforce(self.alice, "dispatch", at=NOW)
        self.enforce(self.bob, "dispatch", at=NOW, risk="high")
        d, _ = self.enforce(
            self.alice, "execute", at=NOW,
            risk="high", approver=self.alice, ref="review:10",
        )
        messages = {
            "resource tenant/project scope does not match request scope",
            d.message,
        }
        events = self.ledger.list_events(tenant_id="tenant-a")
        text = json.dumps(events, sort_keys=True)
        for message in messages:
            self.assertNotIn(message, text)
        for event in events:
            self.assertNotIn("message", event["authorization"])
            self.assertEqual(
                set(event["actor"]),
                {"principal_id", "actor_type", "issuer", "identity_revision"},
            )
            self.assertFalse(event["authority"]["authorizes_action"])
        for claim in ("data_clearance", "scopes", '"roles"', "authenticated"):
            self.assertNotIn(claim, text)
        self.assertEqual(
            [e["authorization"]["reason_code"] for e in events],
            ["role_denied", "distinct_approval_required", "self_approval_forbidden"],
        )


if __name__ == "__main__":
    unittest.main()
