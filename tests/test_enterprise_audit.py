"""Tests for the E4 tamper-evident enterprise audit ledger (#671)."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.enterprise_audit import (
    AuditEventInput,
    EnterpriseAuditError,
    JsonLinesAuditSink,
    LocalEnterpriseAuditLedger,
    retention_state,
    validate_audit_event,
)
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "enterprise-audit-event-v0.1.schema.json"
NOW = 1791406800
REVISION = "a" * 40
EVIDENCE_DIGEST = "sha256:" + "b" * 64


class EnterpriseAuditLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "enterprise-audit.sqlite3"
        self.scope = TenantScope("tenant-a", "project-main")
        self.other_scope = TenantScope("tenant-b", "project-main")
        self.resource = ScopedResourceRef(
            self.scope,
            "candidate",
            "candidate-17",
        )
        self.policy = AuthorizationPolicy.enterprise_baseline()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def actor(
        self,
        *,
        principal_id: str = "github:user:alice",
        actor_type: str = "human",
        roles: tuple[str, ...] = ("worker",),
        scopes: tuple[TenantScope, ...] | None = None,
        revision: str = "identity:actor:1",
        authenticated: bool = True,
        revoked: bool = False,
        expires_at_epoch: int | None = None,
    ) -> ActorContext:
        return ActorContext(
            principal_id=principal_id,
            actor_type=actor_type,
            issuer="idkmesh.test",
            roles=frozenset(roles),
            scopes=scopes or (self.scope,),
            data_clearance="restricted",
            identity_revision=revision,
            authenticated=authenticated,
            revoked=revoked,
            expires_at_epoch=expires_at_epoch,
        )

    def service(
        self,
        *,
        scopes: tuple[TenantScope, ...] | None = None,
    ) -> ActorContext:
        return self.actor(
            principal_id="service:audit-writer",
            actor_type="service",
            roles=("auditor",),
            scopes=scopes or (self.scope,),
            revision="identity:service:1",
        )

    def allow_decision(self, actor: ActorContext | None = None):
        actor = actor or self.actor()
        request = AuthorizationRequest(
            request_id="request:17",
            scope=self.scope,
            resource=self.resource,
            actor=actor,
            action="execute",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=NOW,
        )
        decision = authorize(request, self.policy)
        self.assertEqual(decision.effect, "allow")
        return actor, decision

    def item(
        self,
        *,
        actor: ActorContext | None = None,
        service: ActorContext | None = None,
        outcome: str = "succeeded",
        occurred_at_epoch: int = NOW + 1,
        run_id: str | None = "run:17",
        evidence_digest: str | None = EVIDENCE_DIGEST,
        retention_days: int = 30,
    ) -> AuditEventInput:
        actor, decision = self.allow_decision(actor)
        return AuditEventInput(
            occurred_at_epoch=occurred_at_epoch,
            actor=actor,
            service=service or self.service(),
            decision=decision,
            resource_revision=REVISION,
            outcome=outcome,
            run_id=run_id,
            evidence_digest=evidence_digest,
            retention_days=retention_days,
        )

    def test_append_is_schema_valid_ordered_and_hash_chained(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            first = ledger.append(self.item())
            second = ledger.append(
                self.item(
                    occurred_at_epoch=NOW + 2,
                    outcome="failed",
                )
            )

            self.assertEqual(first["sequence"], 1)
            self.assertEqual(first["event_id"], "audit-000000000001")
            self.assertIsNone(first["previous_event_digest"])
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(
                second["previous_event_digest"],
                first["event_digest"],
            )
            self.assertNotEqual(
                first["event_digest"],
                second["event_digest"],
            )

            verification = ledger.verify()
            self.assertTrue(verification.ok)
            self.assertEqual(verification.event_count, 2)
            self.assertEqual(
                verification.head_digest,
                second["event_digest"],
            )

            if HAS_JSONSCHEMA:
                schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(schema)
                validator = Draft202012Validator(schema)
                validator.validate(first)
                validator.validate(second)

    def test_audit_event_omits_free_form_decision_message_and_extra_payload(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            event = ledger.append(self.item())

        self.assertNotIn("message", event["authorization"])
        self.assertNotIn("payload", event)
        self.assertNotIn("headers", event)
        self.assertNotIn("secret", event)

        tampered = dict(event)
        tampered["authorization_header"] = "Bearer not-allowed"
        with self.assertRaises(EnterpriseAuditError) as ctx:
            validate_audit_event(tampered)
        self.assertEqual(ctx.exception.code, "invalid_event")

    def test_denied_cross_tenant_attempt_is_still_auditable(self) -> None:
        actor = self.actor(
            principal_id="github:user:mallory",
            scopes=(self.other_scope,),
        )
        decision = authorize(
            AuthorizationRequest(
                request_id="request:cross-tenant",
                scope=self.scope,
                resource=self.resource,
                actor=actor,
                action="execute",
                risk="low",
                data_classification="internal",
                evaluated_at_epoch=NOW,
            ),
            self.policy,
        )
        self.assertEqual(decision.effect, "deny")
        self.assertEqual(decision.code, "actor_scope_denied")

        item = AuditEventInput(
            occurred_at_epoch=NOW + 1,
            actor=actor,
            service=self.service(),
            decision=decision,
            resource_revision=REVISION,
            outcome="denied",
            evidence_digest=None,
            retention_days=90,
        )
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            event = ledger.append(item)

        self.assertEqual(event["authorization"]["effect"], "deny")
        self.assertEqual(
            event["authorization"]["reason_code"],
            "actor_scope_denied",
        )
        self.assertEqual(event["outcome"], "denied")
        self.assertEqual(event["scope"]["tenant_id"], "tenant-a")

    def test_unscoped_or_expired_audit_writer_fails_closed(self) -> None:
        with self.assertRaises(EnterpriseAuditError) as ctx:
            self.item(service=self.service(scopes=(self.other_scope,)))
        self.assertEqual(ctx.exception.code, "service_scope_mismatch")

        expired = self.actor(
            principal_id="service:expired",
            actor_type="service",
            roles=("auditor",),
            revision="identity:expired:1",
            expires_at_epoch=NOW + 1,
        )
        with self.assertRaises(EnterpriseAuditError) as ctx:
            self.item(
                service=expired,
                occurred_at_epoch=NOW + 1,
            )
        self.assertEqual(ctx.exception.code, "invalid_service")

    def test_append_only_triggers_reject_rewrite_and_delete(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            ledger.append(self.item())

            external = sqlite3.connect(self.path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    external.execute(
                        "UPDATE enterprise_audit_events "
                        "SET event_id = 'audit-999999999999' "
                        "WHERE sequence = 1"
                    )
                external.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    external.execute(
                        "DELETE FROM enterprise_audit_events "
                        "WHERE sequence = 1"
                    )
                external.rollback()
            finally:
                external.close()

            self.assertTrue(ledger.verify().ok)

    def test_rewrite_is_detected_even_if_append_only_trigger_is_bypassed(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            ledger.append(self.item())
            ledger.append(self.item(occurred_at_epoch=NOW + 2))

            external = sqlite3.connect(self.path)
            try:
                external.execute("DROP TRIGGER enterprise_audit_no_update")
                raw = external.execute(
                    "SELECT event_json FROM enterprise_audit_events "
                    "WHERE sequence = 1"
                ).fetchone()[0]
                event = json.loads(raw)
                event["outcome"] = "failed"
                external.execute(
                    "UPDATE enterprise_audit_events SET event_json = ? "
                    "WHERE sequence = 1",
                    (
                        json.dumps(
                            event,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
                external.commit()
            finally:
                external.close()

            verification = ledger.verify()
            self.assertFalse(verification.ok)
            self.assertTrue(
                any(
                    error.startswith("event_digest_mismatch:1")
                    for error in verification.errors
                )
            )

    def test_interior_and_tail_deletion_are_detected_with_checkpoint(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            for offset in (1, 2, 3):
                ledger.append(
                    self.item(occurred_at_epoch=NOW + offset)
                )
            checkpoint = ledger.checkpoint()

            external = sqlite3.connect(self.path)
            try:
                external.execute("DROP TRIGGER enterprise_audit_no_delete")
                external.execute(
                    "DELETE FROM enterprise_audit_events WHERE sequence = 2"
                )
                external.commit()
            finally:
                external.close()

            middle = ledger.verify(expected_checkpoint=checkpoint)
            self.assertFalse(middle.ok)
            self.assertTrue(
                any(error.startswith("sequence_gap:") for error in middle.errors)
            )
            self.assertTrue(
                any(
                    error.startswith("chain_link_mismatch:3")
                    for error in middle.errors
                )
            )

        tail_path = Path(self.tmp.name) / "tail.sqlite3"
        with LocalEnterpriseAuditLedger(tail_path) as ledger:
            for offset in (1, 2, 3):
                ledger.append(
                    self.item(occurred_at_epoch=NOW + offset)
                )
            checkpoint = ledger.checkpoint()

            external = sqlite3.connect(tail_path)
            try:
                external.execute("DROP TRIGGER enterprise_audit_no_delete")
                external.execute(
                    "DELETE FROM enterprise_audit_events WHERE sequence = 3"
                )
                external.commit()
            finally:
                external.close()

            tail = ledger.verify(expected_checkpoint=checkpoint)
            self.assertFalse(tail.ok)
            self.assertIn(
                "checkpoint_event_count_mismatch:expected=3:actual=2",
                tail.errors,
            )
            self.assertIn("checkpoint_head_digest_mismatch", tail.errors)

    def test_ndjson_export_is_ordered_scoped_and_non_mutating(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            first = ledger.append(self.item())
            second = ledger.append(
                self.item(occurred_at_epoch=NOW + 2)
            )

            other_actor = self.actor(
                principal_id="github:user:bob",
                scopes=(self.other_scope,),
            )
            other_resource = ScopedResourceRef(
                self.other_scope,
                "candidate",
                "candidate-18",
            )
            other_decision = authorize(
                AuthorizationRequest(
                    request_id="request:18",
                    scope=self.other_scope,
                    resource=other_resource,
                    actor=other_actor,
                    action="execute",
                    risk="low",
                    data_classification="internal",
                    evaluated_at_epoch=NOW,
                ),
                self.policy,
            )
            ledger.append(
                AuditEventInput(
                    occurred_at_epoch=NOW + 3,
                    actor=other_actor,
                    service=self.service(scopes=(self.other_scope,)),
                    decision=other_decision,
                    resource_revision="c" * 40,
                    outcome="succeeded",
                    run_id="run:18",
                    evidence_digest="sha256:" + "d" * 64,
                    retention_days=30,
                )
            )
            before = ledger.checkpoint()

            stream = io.StringIO()
            receipt = ledger.export_to_sink(
                JsonLinesAuditSink(stream),
                tenant_id="tenant-a",
                project_id="project-main",
            )
            after = ledger.checkpoint()

        self.assertEqual(before, after)
        self.assertEqual(receipt.exported_count, 2)
        self.assertEqual(receipt.first_sequence, 1)
        self.assertEqual(receipt.last_sequence, 2)
        self.assertEqual(receipt.last_digest, second["event_digest"])
        lines = [
            json.loads(line)
            for line in stream.getvalue().splitlines()
            if line
        ]
        self.assertEqual(
            [item["event_digest"] for item in lines],
            [first["event_digest"], second["event_digest"]],
        )

    def test_export_failure_cannot_change_ledger(self) -> None:
        class FailingSink:
            def write_event(self, _event):
                raise OSError("downstream unavailable")

        with LocalEnterpriseAuditLedger(self.path) as ledger:
            ledger.append(self.item())
            before = ledger.checkpoint()
            with self.assertRaises(OSError):
                ledger.export_to_sink(
                    FailingSink(),
                    tenant_id="tenant-a",
                    project_id="project-main",
                )
            after = ledger.checkpoint()
        self.assertEqual(before, after)

    def test_retention_and_legal_hold_are_explicit_without_delete_authority(self) -> None:
        with LocalEnterpriseAuditLedger(self.path) as ledger:
            event = ledger.append(
                self.item(
                    occurred_at_epoch=NOW,
                    retention_days=30,
                )
            )

        eligible = NOW + 30 * 86400
        self.assertEqual(
            retention_state(event, now_epoch=eligible - 1),
            "retain",
        )
        self.assertEqual(
            retention_state(event, now_epoch=eligible),
            "eligible_for_expiry",
        )
        self.assertEqual(
            retention_state(
                event,
                now_epoch=eligible + 999,
                legal_hold_hook=lambda _event: True,
            ),
            "legal_hold",
        )

    def test_newer_store_version_fails_closed(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("PRAGMA user_version = 2")
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(EnterpriseAuditError) as ctx:
            LocalEnterpriseAuditLedger(self.path)
        self.assertEqual(
            ctx.exception.code,
            "unsupported_audit_store_version",
        )


if __name__ == "__main__":
    unittest.main()
