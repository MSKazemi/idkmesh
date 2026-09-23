"""Tests for the enterprise E3 authorization kernel."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
    parse_actor_context,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope


ROOT = Path(__file__).resolve().parents[1]
ACTOR_SCHEMA = ROOT / "schemas" / "enterprise-actor-context-v0.1.schema.json"
DECISION_SCHEMA = (
    ROOT / "schemas" / "enterprise-authorization-decision-v0.1.schema.json"
)
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "enterprise_authz"
    / "cross-tenant-authorization.json"
)
NOW = 1790168400


class EnterpriseAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = TenantScope("tenant-a", "project-main")
        self.other_scope = TenantScope("tenant-b", "project-main")
        self.resource = ScopedResourceRef(self.scope, "candidate", "candidate-17")
        self.policy = AuthorizationPolicy.enterprise_baseline()

    def actor(
        self,
        principal="github:user:alice",
        *,
        actor_type="human",
        roles=("worker",),
        scopes=None,
        clearance="confidential",
        authenticated=True,
        revoked=False,
        expires=None,
        revision="identity:1",
    ):
        return ActorContext(
            principal_id=principal,
            actor_type=actor_type,
            issuer="github.com",
            roles=frozenset(roles),
            scopes=tuple(scopes or (self.scope,)),
            data_clearance=clearance,
            identity_revision=revision,
            authenticated=authenticated,
            revoked=revoked,
            expires_at_epoch=expires,
        )

    def request(
        self,
        actor,
        *,
        action="execute",
        risk="low",
        data_classification="internal",
        resource=None,
        scope=None,
        approver=None,
        approval_reference=None,
    ):
        return AuthorizationRequest(
            request_id="request:17",
            scope=scope or self.scope,
            resource=resource or self.resource,
            actor=actor,
            action=action,
            risk=risk,
            data_classification=data_classification,
            evaluated_at_epoch=NOW,
            approver=approver,
            approval_reference=approval_reference,
        )

    def test_worker_can_execute_low_risk_in_own_scope(self):
        decision = authorize(self.request(self.actor()), self.policy)
        self.assertEqual(decision.effect, "allow")
        self.assertEqual(decision.code, "authorized")

    def test_worker_reviewer_provider_and_node_cannot_integrate(self):
        cases = [
            self.actor(roles=("worker",)),
            self.actor(roles=("reviewer",)),
            self.actor(
                principal="provider:session:1",
                actor_type="provider",
                roles=("worker",),
            ),
            self.actor(
                principal="node:gpu-1",
                actor_type="node",
                roles=("node_operator",),
            ),
        ]
        for actor in cases:
            with self.subTest(actor=actor.principal_id):
                decision = authorize(
                    self.request(actor, action="integrate"),
                    self.policy,
                )
                self.assertEqual(decision.effect, "deny")

    def test_integrator_human_can_integrate_low_risk(self):
        actor = self.actor(roles=("integrator",))
        decision = authorize(
            self.request(actor, action="integrate"),
            self.policy,
        )
        self.assertEqual(decision.effect, "allow")

    def test_cross_tenant_resource_is_denied_before_role_can_help(self):
        actor = self.actor(roles=("owner", "integrator"))
        resource = ScopedResourceRef(
            self.other_scope,
            "candidate",
            "candidate-17",
        )
        decision = authorize(
            self.request(actor, action="integrate", resource=resource),
            self.policy,
        )
        self.assertEqual(decision.effect, "deny")
        self.assertEqual(decision.code, "scope_mismatch")

    def test_actor_must_be_bound_to_request_scope(self):
        actor = self.actor(
            scopes=(self.other_scope,),
            roles=("integrator",),
        )
        decision = authorize(
            self.request(actor, action="integrate"),
            self.policy,
        )
        self.assertEqual(decision.code, "actor_scope_denied")

    def test_revoked_unauthenticated_and_expired_actor_fail_closed(self):
        cases = [
            (self.actor(authenticated=False), "actor_unauthenticated"),
            (self.actor(revoked=True), "actor_revoked"),
            (self.actor(expires=NOW), "actor_expired"),
            (self.actor(expires=NOW - 1), "actor_expired"),
        ]
        for actor, code in cases:
            with self.subTest(code=code):
                decision = authorize(self.request(actor), self.policy)
                self.assertEqual(decision.effect, "deny")
                self.assertEqual(decision.code, code)

    def test_identity_is_valid_before_expiry_boundary(self):
        actor = self.actor(expires=NOW + 1)
        self.assertEqual(
            authorize(self.request(actor), self.policy).effect,
            "allow",
        )

    def test_data_clearance_is_non_compensating(self):
        actor = self.actor(
            roles=("owner", "integrator"),
            clearance="internal",
        )
        decision = authorize(
            self.request(
                actor,
                action="integrate",
                data_classification="confidential",
            ),
            self.policy,
        )
        self.assertEqual(decision.effect, "deny")
        self.assertEqual(decision.code, "data_clearance_denied")

    def test_high_risk_execute_requires_distinct_human_approval(self):
        worker = self.actor()
        pending = authorize(
            self.request(worker, risk="high"),
            self.policy,
        )
        self.assertEqual(pending.effect, "requires_approval")
        self.assertEqual(pending.code, "distinct_approval_required")

        approver = self.actor(
            principal="github:user:bob",
            roles=("dispatcher",),
        )
        allowed = authorize(
            self.request(
                worker,
                risk="high",
                approver=approver,
                approval_reference="github:review:44",
            ),
            self.policy,
        )
        self.assertEqual(allowed.effect, "allow")
        self.assertEqual(allowed.code, "authorized_with_distinct_approval")
        self.assertEqual(allowed.approved_by, "github:user:bob")

    def test_self_approval_cannot_satisfy_high_risk_rule(self):
        actor = self.actor(roles=("worker", "dispatcher"))
        decision = authorize(
            self.request(
                actor,
                risk="high",
                approver=actor,
                approval_reference="github:review:self",
            ),
            self.policy,
        )
        self.assertEqual(decision.effect, "requires_approval")
        self.assertEqual(decision.code, "self_approval_forbidden")

    def test_cross_tenant_approver_cannot_satisfy_rule(self):
        worker = self.actor()
        approver = self.actor(
            principal="github:user:bob",
            roles=("dispatcher",),
            scopes=(self.other_scope,),
        )
        decision = authorize(
            self.request(
                worker,
                risk="high",
                approver=approver,
                approval_reference="github:review:44",
            ),
            self.policy,
        )
        self.assertEqual(decision.effect, "requires_approval")
        self.assertEqual(decision.code, "approver_scope_denied")

    def test_provider_cannot_be_high_risk_approver_even_with_role(self):
        worker = self.actor()
        approver = self.actor(
            principal="provider:session:2",
            actor_type="provider",
            roles=("dispatcher",),
        )
        decision = authorize(
            self.request(
                worker,
                risk="high",
                approver=approver,
                approval_reference="provider:approval:2",
            ),
            self.policy,
        )
        self.assertEqual(decision.code, "approver_type_denied")

    def test_policy_management_risk_floor_prevents_caller_downgrade(self):
        admin = self.actor(roles=("admin",))
        decision = authorize(
            self.request(admin, action="manage_policy", risk="low"),
            self.policy,
        )
        self.assertEqual(decision.requested_risk, "low")
        self.assertEqual(decision.effective_risk, "high")
        self.assertEqual(decision.effect, "requires_approval")

    def test_authorization_decision_binds_policy_and_identity_revisions(self):
        actor = self.actor(revision="github-membership:77")
        decision = authorize(self.request(actor), self.policy)
        rendered = decision.to_dict()

        self.assertEqual(
            rendered["policy"],
            {"policy_id": "idkmesh.enterprise.baseline", "revision": "0.1"},
        )
        self.assertEqual(rendered["identity_revision"], "github-membership:77")
        self.assertEqual(
            rendered["authority"],
            {
                "executes_action": False,
                "canonical_state_write": False,
                "merge": False,
            },
        )

    def test_actor_parser_is_strict_and_does_not_accept_task_authority_fields(self):
        data = self.actor().to_dict()
        parsed = parse_actor_context(data)
        self.assertEqual(parsed, self.actor())

        malicious = dict(data)
        malicious["task_requested_role"] = "owner"
        with self.assertRaises(AuthorizationContractError) as caught:
            parse_actor_context(malicious)
        self.assertEqual(caught.exception.code, "unknown_field")

    def test_unknown_role_fails_actor_construction(self):
        with self.assertRaises(AuthorizationContractError) as caught:
            self.actor(roles=("worker", "super_admin"))
        self.assertEqual(caught.exception.code, "unknown_value")

    def test_approval_reference_requires_approver(self):
        with self.assertRaises(AuthorizationContractError) as caught:
            self.request(
                self.actor(),
                risk="high",
                approval_reference="github:review:44",
            )
        self.assertEqual(caught.exception.code, "approval_without_actor")

    def test_retained_cross_tenant_fixture_denies(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        actor = parse_actor_context(fixture["actor"])
        scope = TenantScope(**fixture["request_scope"])
        resource = ScopedResourceRef(
            TenantScope(
                fixture["resource"]["tenant_id"],
                fixture["resource"]["project_id"],
            ),
            fixture["resource"]["resource_type"],
            fixture["resource"]["resource_id"],
        )
        request = AuthorizationRequest(
            request_id="fixture:cross-tenant",
            scope=scope,
            resource=resource,
            actor=actor,
            action=fixture["action"],
            risk=fixture["risk"],
            data_classification=fixture["data_classification"],
            evaluated_at_epoch=fixture["evaluated_at_epoch"],
        )
        decision = authorize(request, self.policy)
        self.assertEqual(decision.effect, fixture["expected_effect"])
        self.assertEqual(decision.code, fixture["expected_code"])


@unittest.skipUnless(HAS_JSONSCHEMA, "schema validation requires jsonschema")
class EnterpriseAuthorizationSchemaTests(unittest.TestCase):
    def test_actor_runtime_projection_matches_schema(self):
        schema = json.loads(ACTOR_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        actor = ActorContext(
            principal_id="github:user:alice",
            actor_type="human",
            issuer="github.com",
            roles=frozenset({"reviewer"}),
            scopes=(TenantScope("tenant-a", "project-main"),),
            data_clearance="internal",
            identity_revision="membership:1",
        )
        Draft202012Validator(schema).validate(actor.to_dict())

    def test_decision_runtime_projection_matches_schema(self):
        schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        scope = TenantScope("tenant-a", "project-main")
        actor = ActorContext(
            principal_id="github:user:alice",
            actor_type="human",
            issuer="github.com",
            roles=frozenset({"reviewer"}),
            scopes=(scope,),
            data_clearance="internal",
            identity_revision="membership:1",
        )
        request = AuthorizationRequest(
            request_id="request:1",
            scope=scope,
            resource=ScopedResourceRef(scope, "candidate", "candidate-1"),
            actor=actor,
            action="verify",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=NOW,
        )
        decision = authorize(
            request,
            AuthorizationPolicy.enterprise_baseline(),
        )
        Draft202012Validator(schema).validate(decision.to_dict())


if __name__ == "__main__":
    unittest.main()
