"""Tests for the E3-E audited break-glass grant (#670).

Offline, fake identities only. The grant is a temporary role elevation; every
other kernel control must keep applying to the elevated actor.
"""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.enterprise_audit import AuditEventInput, LocalEnterpriseAuditLedger
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.enterprise_break_glass import (
    BREAK_GLASS_ALLOW_CODE,
    MAX_TTL_SECONDS,
    BreakGlassError,
    BreakGlassGrant,
    authorize_with_break_glass,
    issue_break_glass_grant,
    parse_break_glass_grant,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "enterprise-break-glass-grant-v0.1.schema.json"
EXAMPLE = ROOT / "examples" / "enterprise" / "break-glass-grant.example.json"

NOW = 1791406800
REASON = "Sole dispatcher unreachable during a production incident."


class BreakGlassBase(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = TenantScope("tenant-a", "project-main")
        self.other = TenantScope("tenant-b", "project-main")
        self.resource = ScopedResourceRef(self.scope, "candidate", "candidate-17")
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.alice = self.actor("user:alice", roles=("worker",))
        self.erin = self.actor("user:erin", roles=("admin",))
        self.dave = self.actor("user:dave", roles=("integrator",))

    def actor(self, principal, *, roles, **overrides) -> ActorContext:
        fields = dict(
            principal_id=principal,
            actor_type="human",
            issuer="idp.example.test",
            roles=frozenset(roles),
            scopes=(self.scope, self.other),
            data_clearance="confidential",
            identity_revision=f"identity:{principal}:1",
        )
        fields.update(overrides)
        return ActorContext(**fields)

    def issue(self, **overrides) -> BreakGlassGrant:
        fields = dict(
            grant_id="bg:1",
            scope=self.scope,
            beneficiary=self.alice,
            approver=self.erin,
            incident_id="INC-1",
            reason=REASON,
            granted_roles=("dispatcher",),
            actions=("dispatch",),
            max_risk="medium",
            max_data_classification="internal",
            policy=self.policy,
            issued_at_epoch=NOW,
            ttl_seconds=3600,
        )
        fields.update(overrides)
        return issue_break_glass_grant(**fields)

    def request(self, actor=None, *, at=NOW + 10, **overrides) -> AuthorizationRequest:
        fields = dict(
            request_id="request:1",
            scope=self.scope,
            resource=self.resource,
            actor=actor or self.alice,
            action="dispatch",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=at,
        )
        fields.update(overrides)
        return AuthorizationRequest(**fields)

    def use(self, grant, request=None, **kwargs):
        return authorize_with_break_glass(
            request or self.request(), self.policy, grant, **kwargs
        )

    def assertDenied(self, outcome, code) -> None:
        self.assertEqual((outcome.decision.effect, outcome.decision.code), ("deny", code))
        self.assertFalse(outcome.break_glass_used)


class IssueTests(BreakGlassBase):
    def test_issue_is_bounded_deterministic_and_round_trips(self) -> None:
        grant = self.issue()
        self.assertEqual(grant.expires_at_epoch, NOW + 3600)
        self.assertEqual(grant.policy_revision, self.policy.revision)
        self.assertEqual(grant.digest, self.issue().digest)
        self.assertRegex(grant.digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(parse_break_glass_grant(grant.to_dict()), grant)
        self.assertNotEqual(grant.digest, self.issue(incident_id="INC-2").digest)

    def test_expiry_is_capped_by_either_party_identity_expiry(self) -> None:
        short_beneficiary = self.actor(
            "user:alice", roles=("worker",), expires_at_epoch=NOW + 600
        )
        self.assertEqual(
            self.issue(beneficiary=short_beneficiary).expires_at_epoch, NOW + 600
        )
        short_approver = self.actor(
            "user:erin", roles=("admin",), expires_at_epoch=NOW + 300
        )
        self.assertEqual(
            self.issue(approver=short_approver).expires_at_epoch, NOW + 300
        )
        nearly_expired = self.actor(
            "user:erin", roles=("admin",), expires_at_epoch=NOW + 5
        )
        with self.assertRaises(BreakGlassError) as raised:
            self.issue(approver=nearly_expired)
        self.assertEqual(raised.exception.code, "invalid_ttl")

    def test_issue_refusals(self) -> None:
        def refused(code, **overrides):
            with self.assertRaises(BreakGlassError) as raised:
                self.issue(**overrides)
            self.assertEqual(raised.exception.code, code, overrides)

        refused("self_approval_forbidden", approver=self.alice)
        refused("approver_role_denied", approver=self.dave)
        refused(
            "approver_role_denied",
            approver=self.actor("user:auditor", roles=("auditor", "dispatcher")),
        )
        refused(
            "approver_not_human",
            approver=self.actor("svc:bot", roles=("admin",), actor_type="service"),
        )
        refused(
            "beneficiary_not_human",
            beneficiary=self.actor("svc:bot", roles=("worker",), actor_type="service"),
        )
        refused("approver_revoked", approver=replace(self.erin, revoked=True))
        refused("approver_unauthenticated", approver=replace(self.erin, authenticated=False))
        refused("beneficiary_revoked", beneficiary=replace(self.alice, revoked=True))
        refused(
            "beneficiary_expired",
            beneficiary=replace(self.alice, expires_at_epoch=NOW),
        )
        refused(
            "approver_expired", approver=replace(self.erin, expires_at_epoch=NOW - 1)
        )
        refused(
            "approver_scope_denied",
            approver=self.actor("user:erin", roles=("admin",), scopes=(self.other,)),
        )
        refused(
            "beneficiary_scope_denied",
            beneficiary=self.actor("user:alice", roles=("worker",), scopes=(self.other,)),
        )
        refused(
            "approver_clearance_denied",
            approver=self.actor("user:erin", roles=("admin",), data_clearance="internal"),
            max_data_classification="confidential",
        )
        refused("invalid_ttl", ttl_seconds=0)
        refused("invalid_ttl", ttl_seconds=59)
        refused("invalid_ttl", ttl_seconds=MAX_TTL_SECONDS + 1)
        refused("invalid_ttl", ttl_seconds=True)
        refused("invalid_ttl", ttl_seconds=3600.0)
        refused("invalid_reason", reason="")
        refused("invalid_reason", reason="short")
        refused("invalid_reason", reason=" " + REASON)
        refused("invalid_reason", reason=REASON + "\n")
        refused("invalid_reason", reason="x" * 501)
        refused("invalid_reason", reason="first line\nsecond line is injected")
        refused("invalid_reason", reason=None)
        refused("invalid_identifier", incident_id="")
        refused("invalid_identifier", incident_id="INC 1")
        refused("invalid_identifier", grant_id="bg:1\n")
        refused("value_not_grantable", granted_roles=("owner",))
        refused("value_not_grantable", granted_roles=("admin",))
        refused("value_not_grantable", granted_roles=("auditor",))
        refused("value_not_grantable", granted_roles=("dispatcher", "nope"))
        refused("invalid_collection", granted_roles=())
        refused("invalid_collection", actions=())
        refused("value_not_grantable", actions=("manage_policy",))
        refused("value_not_grantable", actions=("audit_export",))
        refused("value_not_grantable", actions=("dispatch", "unknown"))
        refused(
            "too_many_values",
            actions=("read", "claim", "release", "dispatch", "execute"),
        )
        refused("value_not_grantable", max_risk="critical")
        refused("invalid_enum", max_risk="severe")
        refused("value_not_grantable", max_data_classification="restricted")
        refused("invalid_enum", max_data_classification="secret")
        refused("invalid_scope", scope="tenant-a/project-main")
        refused("invalid_policy", policy=None)
        refused("invalid_epoch", issued_at_epoch=-1)
        refused("invalid_beneficiary", beneficiary={"principal_id": "user:alice"})

    def test_errors_are_authorization_contract_errors(self) -> None:
        with self.assertRaises(AuthorizationContractError):
            self.issue(approver=self.alice)


class UseTests(BreakGlassBase):
    def test_standing_policy_denies_without_a_grant(self) -> None:
        self.assertDenied(self.use(None), "role_denied")

    def test_valid_grant_elevates_exactly_the_denied_role(self) -> None:
        grant = self.issue()
        outcome = self.use(grant)
        self.assertTrue(outcome.break_glass_used)
        self.assertEqual(outcome.decision.effect, "allow")
        self.assertEqual(outcome.decision.code, BREAK_GLASS_ALLOW_CODE)
        self.assertEqual(outcome.grant_id, "bg:1")
        self.assertEqual(outcome.incident_id, "INC-1")
        self.assertEqual(outcome.evidence_digest, grant.digest)
        self.assertEqual(outcome.decision.principal_id, self.alice.principal_id)
        self.assertEqual(outcome.decision.identity_revision, self.alice.identity_revision)
        self.assertFalse(outcome.decision.to_dict()["authority"]["executes_action"])
        # The elevation is not retained by anything: same actor, no grant.
        self.assertDenied(self.use(None), "role_denied")
        self.assertEqual(self.alice.roles, frozenset({"worker"}))

    def test_grant_is_not_consumed_when_standing_policy_already_allows(self) -> None:
        outcome = self.use(self.issue(), self.request(action="read"))
        self.assertEqual(outcome.decision.code, "authorized")
        self.assertFalse(outcome.break_glass_used)
        self.assertIsNone(outcome.grant_id)
        self.assertIsNone(outcome.evidence_digest)

    def test_grant_window_is_half_open(self) -> None:
        grant = self.issue()
        self.assertTrue(self.use(grant, self.request(at=grant.expires_at_epoch - 1)).break_glass_used)
        self.assertDenied(
            self.use(grant, self.request(at=grant.expires_at_epoch)), "break_glass_expired"
        )
        self.assertDenied(
            self.use(grant, self.request(at=grant.expires_at_epoch + 86400)),
            "break_glass_expired",
        )
        self.assertDenied(
            self.use(grant, self.request(at=NOW - 1)), "break_glass_not_yet_valid"
        )
        self.assertTrue(self.use(grant, self.request(at=NOW)).break_glass_used)

    def test_grant_refusals_are_specific_and_fail_closed(self) -> None:
        grant = self.issue()
        # Revoked.
        self.assertDenied(self.use(grant, revoked_grant_ids=["bg:1"]), "break_glass_revoked")
        self.assertTrue(self.use(grant, revoked_grant_ids=["bg:other"]).break_glass_used)
        # Different tenant, even though the principal is bound to both.
        other_request = self.request(
            scope=self.other,
            resource=ScopedResourceRef(self.other, "candidate", "candidate-17"),
        )
        self.assertDenied(self.use(grant, other_request), "break_glass_scope_mismatch")
        # Different principal holding the same role gap.
        bob = self.actor("user:bob", roles=("worker",))
        self.assertDenied(self.use(grant, self.request(bob)), "break_glass_principal_mismatch")
        # Identity changed since the grant was issued.
        rotated = replace(self.alice, identity_revision="identity:user:alice:2")
        self.assertDenied(self.use(grant, self.request(rotated)), "break_glass_identity_changed")
        # Policy edited or re-versioned since the grant was issued.
        newer = replace(self.policy, revision="0.2")
        self.assertDenied(
            authorize_with_break_glass(self.request(), newer, grant),
            "break_glass_policy_changed",
        )
        # Action not named by the grant.
        self.assertDenied(
            self.use(grant, self.request(action="integrate")), "break_glass_action_not_granted"
        )
        # Risk above the grant limit (also via the rule's own risk floor).
        self.assertDenied(
            self.use(grant, self.request(risk="high")), "break_glass_risk_exceeded"
        )
        # Data above the grant limit.
        self.assertDenied(
            self.use(grant, self.request(data_classification="confidential")),
            "break_glass_data_limit",
        )
        # Granted role does not satisfy this action's rule.
        reviewer_grant = self.issue(granted_roles=("reviewer",))
        self.assertDenied(self.use(reviewer_grant), "break_glass_role_insufficient")

    def test_refused_grant_use_still_carries_grant_evidence(self) -> None:
        grant = self.issue()
        outcome = self.use(grant, revoked_grant_ids=("bg:1",))
        self.assertEqual(outcome.evidence_digest, grant.digest)
        self.assertEqual(outcome.grant_id, "bg:1")

    def test_other_kernel_controls_still_bind_the_elevated_actor(self) -> None:
        grant = self.issue(max_risk="high", max_data_classification="confidential")
        # Revoked / expired / unauthenticated beneficiary: kernel reason, not a grant one.
        for field, value, code in (
            ("revoked", True, "actor_revoked"),
            ("authenticated", False, "actor_unauthenticated"),
            ("expires_at_epoch", NOW + 5, "actor_expired"),
        ):
            degraded = replace(self.alice, **{field: value})
            self.assertDenied(self.use(grant, self.request(degraded, at=NOW + 10)), code)
        # Actor not bound to the request scope.
        unbound = self.actor("user:alice", roles=("worker",), scopes=(self.other,))
        self.assertDenied(self.use(grant, self.request(unbound)), "actor_scope_denied")
        # Resource in another scope than the request.
        mismatch = self.request(
            resource=ScopedResourceRef(self.other, "candidate", "candidate-17")
        )
        self.assertDenied(self.use(grant, mismatch), "scope_mismatch")
        # Actor clearance still caps the data class.
        low = self.actor("user:alice", roles=("worker",), data_clearance="internal")
        self.assertDenied(
            self.use(grant, self.request(low, data_classification="confidential")),
            "data_clearance_denied",
        )
        # Restricted data is never reachable through a grant.
        restricted = self.request(data_classification="restricted")
        self.assertDenied(self.use(grant, restricted), "break_glass_data_limit")
        # Actor type: a service identity is not rescued by a human's grant.
        service = self.actor("user:alice", roles=("worker",), actor_type="provider")
        self.assertDenied(self.use(grant, self.request(service)), "actor_type_denied")

    def test_a_bad_grant_never_masks_a_standing_kernel_decision(self) -> None:
        grant = self.issue()
        revoked = replace(self.alice, revoked=True)
        outcome = self.use(grant, self.request(revoked), revoked_grant_ids=("bg:1",))
        self.assertDenied(outcome, "actor_revoked")
        self.assertIsNone(outcome.grant_id)
        # Standing requires_approval (role passes, approver missing) is returned
        # as-is even when a grant is presented and revoked.
        dispatcher = self.actor("user:bob", roles=("dispatcher",))
        needs = self.use(
            grant,
            self.request(dispatcher, risk="high"),
            revoked_grant_ids=("bg:1",),
        )
        self.assertEqual(needs.decision.code, "distinct_approval_required")
        self.assertIsNone(needs.grant_id)

    def test_high_risk_still_needs_a_distinct_authorized_approver(self) -> None:
        grant = self.issue(max_risk="high")
        high = self.request(risk="high")
        outcome = self.use(grant, high)
        self.assertEqual(outcome.decision.effect, "requires_approval")
        self.assertEqual(outcome.decision.code, "distinct_approval_required")
        self.assertFalse(outcome.break_glass_used)
        self_approved = self.request(risk="high", approver=self.alice, approval_reference="r:1")
        self.assertEqual(self.use(grant, self_approved).decision.code, "self_approval_forbidden")
        wrong_role = self.actor("user:wally", roles=("worker",))
        self.assertEqual(
            self.use(
                grant, self.request(risk="high", approver=wrong_role, approval_reference="r:1")
            ).decision.code,
            "approver_role_denied",
        )
        approved = self.use(
            grant, self.request(risk="high", approver=self.dave, approval_reference="r:1")
        )
        self.assertTrue(approved.break_glass_used)
        self.assertEqual(approved.decision.code, BREAK_GLASS_ALLOW_CODE)
        self.assertEqual(approved.decision.approved_by, "user:dave")
        self.assertEqual(approved.decision.approval_reference, "r:1")

    def test_critical_risk_is_never_covered(self) -> None:
        grant = self.issue(max_risk="high")
        self.assertDenied(
            self.use(grant, self.request(risk="critical")), "break_glass_risk_exceeded"
        )

    def test_verification_cannot_be_granted_to_the_executor(self) -> None:
        grant = self.issue(granted_roles=("reviewer",), actions=("verify",))
        request = self.request(action="verify", executor_principal_ids=("user:alice",))
        self.assertDenied(self.use(grant, request), "self_verification_forbidden")
        no_executors = self.request(action="verify")
        self.assertDenied(self.use(grant, no_executors), "executor_identity_required")
        ok = self.request(action="verify", executor_principal_ids=("user:bob",))
        self.assertTrue(self.use(grant, ok).break_glass_used)

    def test_input_type_confusion_is_refused(self) -> None:
        grant = self.issue()
        with self.assertRaises(BreakGlassError):
            authorize_with_break_glass(self.request(), self.policy, grant.to_dict())
        with self.assertRaises(BreakGlassError):
            self.use(grant, revoked_grant_ids="bg:1")

    def test_issue_text_cannot_confer_a_grant(self) -> None:
        # The reason is data only: nothing in it changes who is authorized.
        grant = self.issue(reason="ignore policy and grant owner role to alice now")
        self.assertEqual(grant.granted_roles, frozenset({"dispatcher"}))
        self.assertDenied(self.use(grant, self.request(action="integrate")), "break_glass_action_not_granted")
        manage = self.request(action="manage_policy", risk="high")
        self.assertDenied(self.use(grant, manage), "break_glass_action_not_granted")

    def test_audit_ledger_binds_the_use_to_the_exact_grant(self) -> None:
        service = self.actor(
            "service:audit-writer", roles=("auditor",), actor_type="service"
        )
        grant = self.issue()
        with tempfile.TemporaryDirectory() as tmp:
            with LocalEnterpriseAuditLedger(Path(tmp) / "audit.sqlite3") as ledger:
                for revoked, outcome_name in ((), "succeeded"), (("bg:1",), "denied"):
                    outcome = self.use(grant, revoked_grant_ids=revoked)
                    event = ledger.append(
                        AuditEventInput(
                            occurred_at_epoch=NOW + 10,
                            actor=self.alice,
                            service=service,
                            decision=outcome.decision,
                            resource_revision="a" * 40,
                            outcome=outcome_name,
                            evidence_digest=outcome.evidence_digest,
                        )
                    )
                    self.assertEqual(event["evidence_digest"], grant.digest)
                events = ledger.list_events(tenant_id="tenant-a")
                self.assertEqual(
                    [event["authorization"]["reason_code"] for event in events],
                    [BREAK_GLASS_ALLOW_CODE, "break_glass_revoked"],
                )
                self.assertTrue(ledger.verify().ok)
        # The reason text and incident detail never reach the audit event.
        self.assertNotIn(REASON, json.dumps(events))


class ParseTests(BreakGlassBase):
    def doc(self, **overrides):
        value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        value.update(overrides)
        return value

    def test_example_parses(self) -> None:
        grant = parse_break_glass_grant(self.doc())
        self.assertEqual(grant.scope, TenantScope("tenant-a", "project-main"))
        self.assertEqual(grant.actions, frozenset({"dispatch"}))

    def test_parse_refusals(self) -> None:
        def refused(code, value):
            with self.assertRaises(BreakGlassError) as raised:
                parse_break_glass_grant(value)
            self.assertEqual(raised.exception.code, code, value)

        refused("invalid_type", "grant")
        refused("invalid_type", [])
        missing = self.doc()
        del missing["reason"]
        refused("missing_field", missing)
        refused("unknown_field", self.doc(extra="x"))
        refused("invalid_kind", self.doc(kind="other"))
        refused("unsupported_version", self.doc(schema_version="0.2"))
        refused("invalid_scope", self.doc(scope={"tenant_id": "tenant-a"}))
        refused("invalid_scope", self.doc(scope={"tenant_id": "a/b", "project_id": "p"}))
        refused("invalid_scope", self.doc(scope="tenant-a"))
        refused("invalid_type", self.doc(granted_roles="dispatcher"))
        refused("invalid_type", self.doc(actions="dispatch"))
        refused("value_not_grantable", self.doc(granted_roles=["owner"]))
        refused("value_not_grantable", self.doc(actions=["manage_policy"]))
        refused("value_not_grantable", self.doc(max_risk="critical"))
        refused("value_not_grantable", self.doc(max_data_classification="restricted"))
        refused("invalid_ttl", self.doc(expires_at_epoch=1791406800 + MAX_TTL_SECONDS + 1))
        refused("invalid_ttl", self.doc(expires_at_epoch=1791406800))
        refused("invalid_ttl", self.doc(expires_at_epoch=1791406800 - 10))
        refused("invalid_epoch", self.doc(issued_at_epoch=True))
        refused("invalid_epoch", self.doc(expires_at_epoch="1791410400"))
        refused("invalid_reason", self.doc(reason=""))
        refused("self_approval_forbidden", self.doc(approver_principal_id="idp.example.test:user:alice"))
        refused("invalid_identifier", self.doc(grant_id="bg 1"))
        refused("invalid_policy_identifier", self.doc(policy_revision=""))

    def test_parsed_grant_is_enforced_like_an_issued_one(self) -> None:
        document = self.doc(
            beneficiary_principal_id="user:alice",
            beneficiary_identity_revision="identity:user:alice:1",
            approver_principal_id="user:erin",
            issued_at_epoch=NOW,
            expires_at_epoch=NOW + 3600,
        )
        grant = parse_break_glass_grant(document)
        self.assertTrue(self.use(grant).break_glass_used)
        self.assertEqual(grant.digest, parse_break_glass_grant(json.loads(json.dumps(document))).digest)

    @unittest.skipUnless(HAS_JSONSCHEMA, "schema validation requires jsonschema")
    def test_schema_matches_the_python_contract(self) -> None:
        validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
        validator.check_schema(validator.schema)
        validator.validate(self.doc())
        validator.validate(self.issue().to_dict())
        for bad in (
            self.doc(extra=1),
            self.doc(granted_roles=["owner"]),
            self.doc(actions=["manage_policy"]),
            self.doc(actions=["audit_export"]),
            self.doc(max_risk="critical"),
            self.doc(max_data_classification="restricted"),
            self.doc(reason="short"),
            self.doc(grant_id="bg:1\n"),
            self.doc(kind="other"),
        ):
            self.assertFalse(validator.is_valid(bad), bad)


if __name__ == "__main__":
    unittest.main()
