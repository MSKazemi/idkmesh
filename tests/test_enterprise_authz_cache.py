"""Tests for the E3-D freshness-bound authorization decision cache (#670)."""

from __future__ import annotations

from dataclasses import replace
import unittest

from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.enterprise_authz_cache import (
    AuthorizationDecisionCache,
    decision_cache_key,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

NOW = 1790168400


class AuthorizationDecisionCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = TenantScope("tenant-a", "project-main")
        self.resource = ScopedResourceRef(self.scope, "candidate", "candidate-17")
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.cache = AuthorizationDecisionCache(max_age_seconds=300)

    def actor(self, principal="github:user:alice", **overrides):
        fields = dict(
            principal_id=principal,
            actor_type="human",
            issuer="github.com",
            roles=frozenset({"worker"}),
            scopes=(self.scope,),
            data_clearance="confidential",
            identity_revision="identity:1",
        )
        fields.update(overrides)
        return ActorContext(**fields)

    def request(self, actor, *, at=NOW, request_id="request:1", **overrides):
        fields = dict(
            request_id=request_id,
            scope=self.scope,
            resource=self.resource,
            actor=actor,
            action="execute",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=at,
        )
        fields.update(overrides)
        return AuthorizationRequest(**fields)

    def test_hit_matches_fresh_evaluation_and_is_restamped(self):
        actor = self.actor()
        first = self.cache.authorize(self.request(actor), self.policy)
        second = self.cache.authorize(
            self.request(actor, at=NOW + 10, request_id="request:2"), self.policy
        )
        self.assertEqual((self.cache.hits, self.cache.misses), (1, 1))
        self.assertEqual(second.request_id, "request:2")
        self.assertEqual(second.evaluated_at_epoch, NOW + 10)
        fresh = authorize(
            self.request(actor, at=NOW + 10, request_id="request:2"), self.policy
        )
        self.assertEqual(second, fresh)
        self.assertEqual(first.effect, "allow")

    def test_revoked_identity_cannot_reuse_cached_allow(self):
        actor = self.actor()
        self.assertEqual(
            self.cache.authorize(self.request(actor), self.policy).effect, "allow"
        )
        revoked = replace(actor, revoked=True)  # same identity_revision string
        decision = self.cache.authorize(self.request(revoked, at=NOW + 1), self.policy)
        self.assertEqual((decision.effect, decision.code), ("deny", "actor_revoked"))
        self.assertEqual(self.cache.hits, 0)

    def test_role_and_scope_change_force_reevaluation_without_revision_bump(self):
        actor = self.actor()
        self.cache.authorize(self.request(actor), self.policy)
        demoted = replace(actor, roles=frozenset({"auditor"}))
        decision = self.cache.authorize(self.request(demoted, at=NOW + 1), self.policy)
        self.assertEqual(decision.code, "role_denied")
        unbound = replace(actor, scopes=(TenantScope("tenant-b", "project-main"),))
        decision = self.cache.authorize(self.request(unbound, at=NOW + 2), self.policy)
        self.assertEqual(decision.code, "actor_scope_denied")
        self.assertEqual(self.cache.hits, 0)

    def test_entry_never_outlives_actor_expiry(self):
        actor = self.actor(expires_at_epoch=NOW + 60)
        self.assertEqual(
            self.cache.authorize(self.request(actor), self.policy).effect, "allow"
        )
        hit = self.cache.authorize(self.request(actor, at=NOW + 59), self.policy)
        self.assertEqual(hit.effect, "allow")
        self.assertEqual(self.cache.hits, 1)
        expired = self.cache.authorize(self.request(actor, at=NOW + 60), self.policy)
        self.assertEqual((expired.effect, expired.code), ("deny", "actor_expired"))
        self.assertEqual(self.cache.hits, 1)

    def test_entry_expires_after_max_age_even_for_non_expiring_identity(self):
        actor = self.actor()
        self.cache.authorize(self.request(actor), self.policy)
        self.cache.authorize(self.request(actor, at=NOW + 299), self.policy)
        self.assertEqual(self.cache.hits, 1)
        self.cache.authorize(self.request(actor, at=NOW + 300), self.policy)
        self.assertEqual(self.cache.hits, 1)
        self.assertEqual(self.cache.misses, 2)

    def test_clock_rewind_cannot_revive_an_entry(self):
        actor = self.actor()
        self.cache.authorize(self.request(actor, at=NOW + 100), self.policy)
        self.cache.authorize(self.request(actor, at=NOW), self.policy)
        self.assertEqual(self.cache.hits, 0)

    def test_approver_expiry_bounds_a_cached_high_risk_allow(self):
        worker = self.actor()
        approver = self.actor(
            "github:user:bob",
            roles=frozenset({"dispatcher"}),
            expires_at_epoch=NOW + 30,
        )
        kwargs = dict(risk="high", approver=approver, approval_reference="review:44")
        first = self.cache.authorize(self.request(worker, **kwargs), self.policy)
        self.assertEqual(first.code, "authorized_with_distinct_approval")
        later = self.cache.authorize(
            self.request(worker, at=NOW + 31, **kwargs), self.policy
        )
        self.assertEqual(
            (later.effect, later.code), ("requires_approval", "approver_expired")
        )
        self.assertEqual(self.cache.hits, 0)

    def test_revoked_approver_is_not_covered_by_a_cached_allow(self):
        worker = self.actor()
        approver = self.actor("github:user:bob", roles=frozenset({"dispatcher"}))
        kwargs = dict(risk="high", approval_reference="review:44")
        self.cache.authorize(
            self.request(worker, approver=approver, **kwargs), self.policy
        )
        revoked = replace(approver, revoked=True)
        decision = self.cache.authorize(
            self.request(worker, at=NOW + 1, approver=revoked, **kwargs), self.policy
        )
        self.assertEqual(decision.code, "approver_revoked")
        self.assertEqual(self.cache.hits, 0)

    def test_policy_edit_without_revision_bump_forces_reevaluation(self):
        actor = self.actor()
        self.cache.authorize(self.request(actor), self.policy)
        stricter_rules = tuple(
            replace(rule, allowed_roles=frozenset({"owner"}))
            if rule.action == "execute"
            else rule
            for rule in self.policy.rules
        )
        stricter = AuthorizationPolicy(
            self.policy.policy_id, self.policy.revision, stricter_rules
        )
        decision = self.cache.authorize(self.request(actor, at=NOW + 1), stricter)
        self.assertEqual(decision.code, "role_denied")
        self.assertEqual(self.cache.hits, 0)

    def test_key_excludes_request_id_and_time_but_includes_risk_and_resource(self):
        actor = self.actor()
        base = decision_cache_key(self.request(actor), self.policy)
        self.assertEqual(
            base,
            decision_cache_key(
                self.request(actor, at=NOW + 5, request_id="other"), self.policy
            ),
        )
        self.assertNotEqual(
            base, decision_cache_key(self.request(actor, risk="high"), self.policy)
        )
        other = ScopedResourceRef(self.scope, "candidate", "candidate-18")
        self.assertNotEqual(
            base, decision_cache_key(self.request(actor, resource=other), self.policy)
        )

    def test_invalidate_principal_drops_actor_and_approver_entries(self):
        worker = self.actor()
        approver = self.actor("github:user:bob", roles=frozenset({"dispatcher"}))
        self.cache.authorize(self.request(worker), self.policy)
        self.cache.authorize(
            self.request(
                worker, risk="high", approver=approver, approval_reference="r:1"
            ),
            self.policy,
        )
        self.assertEqual(len(self.cache), 2)
        self.assertEqual(self.cache.invalidate_principal("github:user:bob"), 1)
        self.assertEqual(self.cache.invalidate_principal("github:user:alice"), 1)
        self.assertEqual(len(self.cache), 0)

    def test_cache_is_bounded_and_evicts_least_recently_used(self):
        cache = AuthorizationDecisionCache(max_entries=2)
        actors = [self.actor(f"github:user:u{i}") for i in range(3)]
        for actor in actors:
            cache.authorize(self.request(actor), self.policy)
        self.assertEqual(len(cache), 2)
        cache.authorize(self.request(actors[0], at=NOW + 1), self.policy)
        self.assertEqual(cache.hits, 0)

    def test_invalid_bounds_are_rejected(self):
        for kwargs in (
            {"max_age_seconds": 0},
            {"max_entries": -1},
            {"max_entries": True},
        ):
            with self.assertRaises(AuthorizationContractError):
                AuthorizationDecisionCache(**kwargs)

    def test_cached_decision_keeps_no_action_authority(self):
        actor = self.actor()
        self.cache.authorize(self.request(actor), self.policy)
        hit = self.cache.authorize(self.request(actor, at=NOW + 1), self.policy)
        self.assertEqual(
            hit.to_dict()["authority"],
            {"executes_action": False, "canonical_state_write": False, "merge": False},
        )


if __name__ == "__main__":
    unittest.main()
