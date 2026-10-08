"""Tests for the transport-neutral Human Decision service core (#740)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.enterprise_authz import ActorContext
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
    spec = importlib.util.spec_from_file_location(f"_decision_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_helpers = _load_sibling("test_run_evidence_store")


class HumanDecisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="idkmesh-human-decision-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.run_db = root / "runs.sqlite3"
        self.decision_db = root / "decisions.sqlite3"
        self.seeded = _helpers.seed_offline_run(self.run_db, root, key="idem/decision")
        self.reader = ProductSpineRunStore(LocalMetadataStore(self.run_db))
        self.store = HumanDecisionStore(self.decision_db)
        self.service = HumanDecisionService(evidence_reader=self.reader, store=self.store)
        self.report = self.seeded.evidence_report
        self.digest = canonical_digest(self.report)
        self.actor = ActorContext(
            principal_id="reviewer@example.com",
            actor_type="human",
            issuer="tests",
            roles=frozenset({"reviewer"}),
            scopes=(TenantScope(tenant_id="tenant.test", project_id="project.test"),),
            data_clearance="internal",
            identity_revision="test-v1",
        )

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

    def record(self, request=None, *, key="decision-key-1", actor=None, decided_at=None):
        return self.service.record(
            self.request() if request is None else request,
            idempotency_key=key,
            actor=self.actor if actor is None else actor,
            decided_at=decided_at or "2026-10-08T00:00:00Z",
            evaluated_at_epoch=1_780_000_000,
        )

    def test_records_an_exact_evidence_bound_human_decision(self) -> None:
        result = self.record()
        record = result.decision_record

        self.assertTrue(result.created)
        self.assertFalse(result.replayed)
        self.assertEqual(record["kind"], "idkmesh-human-decision-record")
        self.assertEqual(record["evidence_report"]["digest"], self.digest)
        self.assertEqual(record["evidence_report"]["run_id"], self.report["run_id"])
        self.assertEqual(record["decider"], {"id": self.actor.principal_id, "type": "human"})
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )
        self.assertEqual(result.decision_record_digest, canonical_digest(record))
        response = result.response()
        self.assertEqual(response["kind"], "idkmesh-human-decision-response")
        self.assertTrue(response["ok"])

    def test_exact_idempotent_replay_returns_the_original_logical_result(self) -> None:
        first = self.record(decided_at="2026-10-08T00:00:00Z")
        replay = self.record(decided_at="2026-10-08T01:00:00Z")

        self.assertFalse(replay.created)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.decision_record, first.decision_record)
        self.assertEqual(replay.decision_record_digest, first.decision_record_digest)
        self.assertEqual(replay.decision_record["decided_at"], "2026-10-08T00:00:00Z")
        self.assertEqual(
            self.store.list_for_run(self.report["run_id"]),
            [dict(first.decision_record)],
        )

    def test_same_idempotency_key_with_different_request_is_a_conflict(self) -> None:
        self.record()
        changed = self.request(rationale="A materially different rationale.")
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(changed)
        self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(len(self.store.list_for_run(self.report["run_id"])), 1)

    def test_request_cannot_supply_identity_timestamp_authority_or_id(self) -> None:
        for field, value in (
            ("decider", {"id": "attacker", "type": "human"}),
            ("decided_at", "2026-01-01T00:00:00Z"),
            ("authority", {"merge": True}),
            ("decision_id", "attacker.id"),
            ("idempotency_key", "belongs-in-header"),
        ):
            with self.subTest(field=field):
                request = self.request()
                request[field] = value
                with self.assertRaises(HumanDecisionServiceError) as caught:
                    self.record(request, key=f"key-{field}")
                self.assertEqual(caught.exception.code, "invalid_request")

    def test_wrong_evidence_digest_fails_closed_before_persistence(self) -> None:
        request = self.request()
        request["evidence_report"] = dict(request["evidence_report"])
        request["evidence_report"]["digest"] = "sha256:" + "0" * 64

        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(request)
        self.assertEqual(caught.exception.code, "evidence_mismatch")
        self.assertEqual(self.store.list_for_run(self.report["run_id"]), [])

    def test_unknown_selected_attempt_is_rejected(self) -> None:
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(self.request(selected_attempt_id="attempt-does-not-exist"))
        self.assertEqual(caught.exception.code, "selected_attempt_not_found")

    def test_machine_recommendation_vocabulary_is_not_a_human_decision(self) -> None:
        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.record(self.request(decision="accept_candidate"))
        self.assertEqual(caught.exception.code, "invalid_decision")

    def test_revoked_expired_unauthenticated_and_nonhuman_principals_fail_closed(self) -> None:
        variants = (
            (
                ActorContext(
                    principal_id="revoked@example.com",
                    actor_type="human",
                    issuer="tests",
                    roles=frozenset({"reviewer"}),
                    scopes=self.actor.scopes,
                    data_clearance="internal",
                    identity_revision="test-v1",
                    revoked=True,
                ),
                "principal_revoked",
            ),
            (
                ActorContext(
                    principal_id="expired@example.com",
                    actor_type="human",
                    issuer="tests",
                    roles=frozenset({"reviewer"}),
                    scopes=self.actor.scopes,
                    data_clearance="internal",
                    identity_revision="test-v1",
                    expires_at_epoch=10,
                ),
                "principal_expired",
            ),
            (
                ActorContext(
                    principal_id="anonymous@example.com",
                    actor_type="human",
                    issuer="tests",
                    roles=frozenset({"reviewer"}),
                    scopes=self.actor.scopes,
                    data_clearance="internal",
                    identity_revision="test-v1",
                    authenticated=False,
                ),
                "principal_unauthenticated",
            ),
            (
                ActorContext(
                    principal_id="svc-reviewer",
                    actor_type="service",
                    issuer="tests",
                    roles=frozenset({"reviewer"}),
                    scopes=self.actor.scopes,
                    data_clearance="internal",
                    identity_revision="test-v1",
                ),
                "principal_type_denied",
            ),
        )
        for actor, code in variants:
            with self.subTest(code=code):
                with self.assertRaises(HumanDecisionServiceError) as caught:
                    self.record(actor=actor, key=f"key-{code}")
                self.assertEqual(caught.exception.code, code)

    def test_persisted_decision_rows_are_database_enforced_append_only(self) -> None:
        result = self.record()
        decision_id = result.decision_record["decision_id"]

        conn = sqlite3.connect(self.decision_db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "UPDATE human_decisions SET decided_at = ? WHERE decision_id = ?",
                    ("2026-10-09T00:00:00Z", decision_id),
                )
            conn.rollback()
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "DELETE FROM human_decisions WHERE decision_id = ?",
                    (decision_id,),
                )
        finally:
            conn.close()

        records = self.store.list_for_run(self.report["run_id"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decision_id"], decision_id)

    def test_tampered_persisted_record_is_detected_on_read(self) -> None:
        self.record()
        conn = sqlite3.connect(self.decision_db)
        try:
            conn.execute("DROP TRIGGER human_decisions_no_update")
            row = conn.execute(
                "SELECT decision_id, decision_record_json FROM human_decisions"
            ).fetchone()
            record = json.loads(row[1])
            record["rationale"] = "tampered"
            conn.execute(
                "UPDATE human_decisions SET decision_record_json = ? WHERE decision_id = ?",
                (json.dumps(record), row[0]),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(HumanDecisionServiceError) as caught:
            self.store.list_for_run(self.report["run_id"])
        self.assertEqual(caught.exception.code, "persisted_state_corrupt")


if __name__ == "__main__":
    unittest.main()
