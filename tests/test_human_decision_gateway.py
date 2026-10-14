"""Tests for the authorized, audited Human Decision gateway (#740).

The gateway adds policy authorization (the ``decide`` action) and one audit
event per attempt in front of the immutable decision service.  These tests
prove that nothing is persisted unless the policy kernel allows it, that every
attempt is audited, and that the verifier/automation can never become the
human decider.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.enterprise_audit import LocalEnterpriseAuditLedger
from idkmesh.enterprise_authz import (
    ACTIONS,
    ActorContext,
    AuthorizationPolicy,
    PolicyRule,
)
from idkmesh.human_decision_gateway import (
    AuthorizedHumanDecisionGateway,
    HumanDecisionAuthorizationError,
)
from idkmesh.human_decision_service import (
    HumanDecisionService,
    HumanDecisionServiceError,
    HumanDecisionStore,
)
from idkmesh.product_spine_run_store import ProductSpineRunStore
from idkmesh.tenant_scope import TenantScope
from idkmesh.work_unit_binding import canonical_digest


def _load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_decision_gw_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_helpers = _load_sibling("test_run_evidence_store")

SCOPE = TenantScope(tenant_id="tenant.test", project_id="project.test")
OTHER_SCOPE = TenantScope(tenant_id="tenant.other", project_id="project.test")
NOW = 1_780_000_000


def human(name: str, *roles: str, scope: TenantScope = SCOPE, **extra) -> ActorContext:
    return ActorContext(
        principal_id=name,
        actor_type=extra.pop("actor_type", "human"),
        issuer="tests",
        roles=frozenset(roles),
        scopes=(scope,),
        data_clearance="internal",
        identity_revision="test-v1",
        **extra,
    )


class GatewayCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="idkmesh-decision-gw-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        seeded = _helpers.seed_offline_run(root / "runs.sqlite3", root, key="idem/gw")
        self.report = seeded.evidence_report
        self.digest = canonical_digest(self.report)
        self.store = HumanDecisionStore(root / "decisions.sqlite3")
        self.ledger = LocalEnterpriseAuditLedger(root / "audit.sqlite3")
        self.addCleanup(self.ledger.close)
        self.service = HumanDecisionService(
            evidence_reader=ProductSpineRunStore(
                LocalMetadataStore(root / "runs.sqlite3")
            ),
            store=self.store,
        )
        self.writer = ActorContext(
            principal_id="svc:decision-audit",
            actor_type="service",
            issuer="tests",
            roles=frozenset({"auditor"}),
            scopes=(SCOPE,),
            data_clearance="internal",
            identity_revision="svc-v1",
        )
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.gateway = self.make_gateway()
        self.integrator = human("alice@example.com", "integrator")

    def make_gateway(self, **overrides) -> AuthorizedHumanDecisionGateway:
        kwargs = dict(
            service=self.service,
            policy=self.policy,
            audit_ledger=self.ledger,
            audit_writer=self.writer,
        )
        kwargs.update(overrides)
        return AuthorizedHumanDecisionGateway(**kwargs)

    def request(self, **overrides):
        value = {
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-request",
            "evidence_report": {
                "kind": self.report["kind"],
                "schema_version": self.report["schema_version"],
                "run_id": self.report["run_id"],
                "digest": self.digest,
            },
            "selected_attempt_id": self.report["attempts"][0]["attempt_id"],
            "decision": "accept",
            "rationale": "The selected attempt is supported by the retained evidence.",
        }
        value.update(overrides)
        return value

    def record(self, request=None, **overrides):
        kwargs = dict(
            idempotency_key="decision-key-1",
            actor=self.integrator,
            scope=SCOPE,
            request_id="req-1",
            now_epoch=NOW,
            risk="low",
            data_classification="internal",
        )
        kwargs.update(overrides)
        return self.gateway.record(self.request() if request is None else request, **kwargs)

    def events(self):
        return self.ledger.list_events(tenant_id=SCOPE.tenant_id)

    def decisions(self):
        return self.store.list_for_run(self.report["run_id"])


class AuthorizedRecordingTests(GatewayCase):
    def test_decide_is_a_distinct_kernel_action(self) -> None:
        self.assertIn("decide", ACTIONS)
        self.assertIsNotNone(self.policy.rule_for("decide"))

    def test_authorized_decision_is_recorded_bound_to_evidence_and_audited(self) -> None:
        result = self.record()

        record = result.decision.decision_record
        self.assertTrue(result.decision.created)
        self.assertEqual(record["evidence_report"]["digest"], self.digest)
        self.assertEqual(record["decider"], {"id": "alice@example.com", "type": "human"})
        self.assertEqual(record["decided_at"], "2026-05-28T20:26:40Z")
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )
        self.assertEqual(result.authorization.effect, "allow")
        self.assertEqual(result.authorization.action, "decide")

        events = self.events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["action"], "decide")
        self.assertEqual(event["outcome"], "succeeded")
        self.assertEqual(event["actor"]["principal_id"], "alice@example.com")
        self.assertEqual(event["service"]["principal_id"], "svc:decision-audit")
        self.assertEqual(event["evidence_digest"], self.digest)
        self.assertEqual(event["resource"]["revision"], self.digest)
        self.assertEqual(event["correlation"]["run_id"], self.report["run_id"])
        self.assertEqual(event["correlation"]["request_id"], "req-1")
        self.assertFalse(event["authority"]["merge"])
        self.assertEqual(self.ledger.verify().ok, True)

    def test_replay_returns_same_record_and_is_audited_as_not_executed(self) -> None:
        first = self.record()
        replay = self.record(request_id="req-2", now_epoch=NOW + 60)

        self.assertTrue(replay.decision.replayed)
        self.assertEqual(
            replay.decision.decision_record_digest, first.decision.decision_record_digest
        )
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(
            [e["outcome"] for e in self.events()], ["succeeded", "not_executed"]
        )

    def test_same_key_different_request_is_a_conflict_and_audited_as_failed(self) -> None:
        self.record()
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(self.request(rationale="A materially different rationale."))
        self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual([e["outcome"] for e in self.events()], ["succeeded", "failed"])

    def test_stale_or_swapped_evidence_digest_fails_closed_and_is_audited(self) -> None:
        stale = self.request()
        stale["evidence_report"] = dict(stale["evidence_report"], digest="sha256:" + "0" * 64)
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(stale)
        self.assertEqual(caught.exception.code, "evidence_mismatch")
        self.assertEqual(self.decisions(), [])
        events = self.events()
        self.assertEqual([e["outcome"] for e in events], ["failed"])
        self.assertEqual(events[0]["evidence_digest"], "sha256:" + "0" * 64)

    def test_unknown_selected_attempt_is_rejected_and_nothing_persists(self) -> None:
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(self.request(selected_attempt_id="attempt-does-not-exist"))
        self.assertEqual(caught.exception.code, "selected_attempt_not_found")
        self.assertEqual(self.decisions(), [])

    def test_malformed_requests_are_rejected_before_any_side_effect(self) -> None:
        for bad in (
            {},
            self.request(decision="auto-approve"),
            self.request(rationale="   "),
            dict(self.request(), decider={"id": "attacker", "type": "human"}),
            dict(self.request(), decided_at="2020-01-01T00:00:00Z"),
        ):
            with self.subTest(bad=sorted(bad)):
                with self.assertRaises(HumanDecisionServiceError):
                    self.record(bad)
        self.assertEqual(self.decisions(), [])
        self.assertEqual(self.events(), [])

    def test_decision_row_cannot_be_updated_or_deleted(self) -> None:
        self.record()
        conn = sqlite3.connect(self.store.path)
        self.addCleanup(conn.close)
        for sql in (
            "UPDATE human_decisions SET decision_record_json = '{}'",
            "DELETE FROM human_decisions",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                conn.execute(sql)
        self.assertEqual(len(self.decisions()), 1)


class AuthorizationDenialTests(GatewayCase):
    def assert_denied(self, code: str, **overrides) -> HumanDecisionAuthorizationError:
        with self.assertRaises(HumanDecisionAuthorizationError) as caught:
            self.record(**overrides)
        self.assertEqual(caught.exception.code, "authorization_denied")
        self.assertEqual(caught.exception.decision.code, code)
        self.assertEqual(self.decisions(), [], "a denied attempt must persist nothing")
        events = self.events()
        self.assertEqual(events[-1]["outcome"], "denied")
        self.assertEqual(events[-1]["authorization"]["effect"], "deny")
        self.assertEqual(events[-1]["authorization"]["reason_code"], code)
        return caught.exception

    def test_roles_without_decide_authority_are_denied(self) -> None:
        for role in ("worker", "reviewer", "dispatcher", "node_operator", "auditor"):
            with self.subTest(role=role):
                self.assert_denied("role_denied", actor=human(f"{role}@example.com", role))

    def test_non_human_principals_are_denied_even_with_an_owner_role(self) -> None:
        for actor_type in ("service", "github_app", "github_actions", "provider", "node"):
            with self.subTest(actor_type=actor_type):
                self.assert_denied(
                    "actor_type_denied",
                    actor=human("bot", "owner", actor_type=actor_type),
                )

    def test_cross_tenant_actor_is_denied(self) -> None:
        self.assert_denied(
            "actor_scope_denied",
            actor=human("mallory@example.com", "owner", scope=OTHER_SCOPE),
        )

    def test_unauthenticated_revoked_and_expired_identities_are_denied(self) -> None:
        self.assert_denied(
            "actor_unauthenticated",
            actor=human("a@example.com", "owner", authenticated=False),
        )
        self.assert_denied(
            "actor_revoked", actor=human("b@example.com", "owner", revoked=True)
        )
        self.assert_denied(
            "actor_expired",
            actor=human("c@example.com", "owner", expires_at_epoch=NOW),
        )

    def test_data_classification_above_clearance_is_denied(self) -> None:
        self.assert_denied("data_clearance_denied", data_classification="restricted")

    def test_high_risk_needs_a_distinct_eligible_human_approver(self) -> None:
        with self.assertRaises(HumanDecisionAuthorizationError) as caught:
            self.record(risk="high")
        self.assertEqual(caught.exception.code, "approval_required")
        self.assertEqual(caught.exception.decision.code, "distinct_approval_required")
        self.assertEqual(self.decisions(), [])
        self.assertEqual(self.events()[-1]["outcome"], "not_executed")

        # Self-approval, a non-human approver and an under-privileged approver
        # all stay unauthorized.
        bad_approvers = {
            "self_approval_forbidden": self.integrator,
            "approver_type_denied": human("svc", "owner", actor_type="service"),
            "approver_role_denied": human("rev@example.com", "reviewer"),
        }
        for code, approver in bad_approvers.items():
            with self.subTest(code=code):
                with self.assertRaises(HumanDecisionAuthorizationError) as bad:
                    self.record(risk="high", approver=approver, approval_reference="ref-1")
                self.assertEqual(bad.exception.decision.code, code)
                self.assertEqual(self.decisions(), [])

        approved = self.record(
            risk="high",
            approver=human("bob@example.com", "owner"),
            approval_reference="review-1",
        )
        self.assertEqual(approved.authorization.code, "authorized_with_distinct_approval")
        self.assertEqual(approved.audit_event["authorization"]["approved_by"], "bob@example.com")
        self.assertEqual(len(self.decisions()), 1)

    def test_a_policy_without_a_decide_rule_cannot_build_a_gateway(self) -> None:
        read_only = AuthorizationPolicy(
            policy_id="idkmesh.test.readonly",
            revision="1",
            rules=(PolicyRule("read", frozenset({"owner"}), frozenset({"human"})),),
        )
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.make_gateway(policy=read_only)
        self.assertEqual(caught.exception.code, "invalid_gateway")

    def test_denial_is_not_overridable_by_a_request_body_authority_claim(self) -> None:
        forged = dict(self.request(), authority={"merge": True})
        with self.assertRaises(HumanDecisionServiceError):
            self.record(forged, actor=human("w@example.com", "worker"))
        self.assertEqual(self.decisions(), [])


class AuditFailClosedTests(GatewayCase):
    def test_audit_writer_must_be_a_valid_service_identity(self) -> None:
        for writer in (
            human("h@example.com", "owner"),
            ActorContext(
                principal_id="svc:revoked",
                actor_type="service",
                issuer="tests",
                roles=frozenset({"auditor"}),
                scopes=(SCOPE,),
                data_clearance="internal",
                identity_revision="svc-v1",
                revoked=True,
            ),
            "not-an-actor",
        ):
            with self.subTest(writer=repr(writer)[:30]):
                with self.assertRaises(HumanDecisionServiceError) as caught:
                    self.make_gateway(audit_writer=writer)
                self.assertEqual(caught.exception.code, "invalid_gateway")

    def test_audit_writer_outside_the_scope_refuses_before_persisting(self) -> None:
        wrong_scope_writer = ActorContext(
            principal_id="svc:other",
            actor_type="service",
            issuer="tests",
            roles=frozenset({"auditor"}),
            scopes=(OTHER_SCOPE,),
            data_clearance="internal",
            identity_revision="svc-v1",
        )
        gateway = self.make_gateway(audit_writer=wrong_scope_writer)
        with self.assertRaises(HumanDecisionServiceError) as caught:
            gateway.record(
                self.request(),
                idempotency_key="k",
                actor=self.integrator,
                scope=SCOPE,
                request_id="req-x",
                now_epoch=NOW,
                risk="low",
                data_classification="internal",
            )
        self.assertEqual(caught.exception.code, "audit_unavailable")
        self.assertEqual(self.decisions(), [], "no audit trail means no decision")

    def test_bad_retention_is_rejected_at_construction(self) -> None:
        for value in (0, -1, 36501, True, "365"):
            with self.subTest(value=value):
                with self.assertRaises(HumanDecisionServiceError):
                    self.make_gateway(retention_days=value)

    def test_audit_failure_after_persist_is_reported_and_retry_replays(self) -> None:
        real_append = self.ledger.append
        calls = {"n": 0}

        def flaky(item):
            calls["n"] += 1
            if calls["n"] == 1:
                from idkmesh.enterprise_audit import EnterpriseAuditError

                raise EnterpriseAuditError("audit_store_error", "disk full")
            return real_append(item)

        self.ledger.append = flaky  # type: ignore[method-assign]
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record()
        self.assertEqual(caught.exception.code, "audit_unavailable")
        # The decision is durable; the gap is surfaced, not hidden.
        self.assertEqual(len(self.decisions()), 1)
        retry = self.record(request_id="req-retry")
        self.assertTrue(retry.decision.replayed)
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(self.events()[-1]["outcome"], "not_executed")

    def test_no_network_or_integration_authority_is_exposed(self) -> None:
        for name in dir(AuthorizedHumanDecisionGateway):
            self.assertNotIn(name.lower(), {"merge", "push", "dispatch", "approve"})
        result = self.record()
        self.assertFalse(result.audit_event["authority"]["authorizes_action"])
        self.assertFalse(result.audit_event["authority"]["merge"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
