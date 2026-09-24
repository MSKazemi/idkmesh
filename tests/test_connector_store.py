import sqlite3
from pathlib import Path
import tempfile
import threading
import unittest

from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    LocalStoreError,
    UnsafeMetadataError,
    WebhookDeliveryRecord,
)


class LocalMetadataStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "control.db"

    def tearDown(self):
        self.tmp.cleanup()

    def _store(self):
        return LocalMetadataStore(self.db)

    def test_connection_probe_and_route_metadata_survive_restart(self):
        store = self._store()
        store.record_connection(
            "agent-one",
            metadata={"driver": "fake", "secret_ref": "env:PROVIDER_KEY"},
            updated_at="2026-09-22T14:20:00Z",
        )
        store.record_probe(
            "agent-one",
            checked_at="2026-09-22T14:21:00Z",
            status="healthy",
            metadata={"driver_version": "0.1"},
        )
        store.record_route(
            "route-1",
            request_digest="sha256:route",
            metadata={"selected": "agent-one"},
            created_at="2026-09-22T14:22:00Z",
        )

        restarted = self._store()
        self.assertEqual(restarted.get_connection("agent-one")["driver"], "fake")
        self.assertEqual(restarted.latest_probe("agent-one")["status"], "healthy")
        self.assertEqual(restarted.get_route("route-1")["metadata"]["selected"], "agent-one")

    def test_webhook_delivery_survives_restart_and_replay_is_idempotent(self):
        store = self._store()
        first, created_first = store.admit_webhook_delivery(
            delivery_id="delivery-1",
            request_digest="sha256:" + "a" * 64,
            event="issues",
            repository="MSKazemi/idkmesh",
            metadata={
                "action": "labeled",
                "subject_number": 77,
                "payload_digest": "sha256:" + "b" * 64,
            },
            received_at="2026-09-24T01:00:00Z",
        )
        self.assertIsInstance(first, WebhookDeliveryRecord)
        self.assertTrue(created_first)

        restarted = self._store()
        second, created_second = restarted.admit_webhook_delivery(
            delivery_id="delivery-1",
            request_digest="sha256:" + "a" * 64,
            event="issues",
            repository="mskazemi/IDKMESH",
            metadata={"ignored_after_first_admission": True},
            received_at="2026-09-24T01:05:00Z",
        )

        self.assertFalse(created_second)
        self.assertEqual(second.delivery_id, first.delivery_id)
        self.assertEqual(second.metadata["action"], "labeled")
        self.assertEqual(second.received_at, "2026-09-24T01:00:00Z")
        self.assertEqual(
            restarted.get_webhook_delivery("delivery-1").request_digest,
            "sha256:" + "a" * 64,
        )

    def test_webhook_delivery_reuse_with_different_content_conflicts(self):
        store = self._store()
        store.admit_webhook_delivery(
            delivery_id="delivery-conflict",
            request_digest="sha256:" + "a" * 64,
            event="issues",
            repository="MSKazemi/idkmesh",
            metadata={},
            received_at="2026-09-24T01:00:00Z",
        )
        for changes in (
            {"request_digest": "sha256:" + "b" * 64},
            {"event": "issue_comment"},
            {"repository": "other/repo"},
        ):
            kwargs = {
                "delivery_id": "delivery-conflict",
                "request_digest": "sha256:" + "a" * 64,
                "event": "issues",
                "repository": "MSKazemi/idkmesh",
                "metadata": {},
                "received_at": "2026-09-24T01:01:00Z",
            }
            kwargs.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(LocalStoreConflict):
                    store.admit_webhook_delivery(**kwargs)

    def test_webhook_delivery_rejects_non_sha256_request_digest(self):
        with self.assertRaisesRegex(ValueError, "sha256"):
            self._store().admit_webhook_delivery(
                delivery_id="delivery-bad-digest",
                request_digest="payload",
                event="issues",
                repository="MSKazemi/idkmesh",
                metadata={},
                received_at="2026-09-24T01:00:00Z",
            )

    def test_webhook_delivery_metadata_uses_existing_secret_safety_boundary(self):
        store = self._store()
        sentinel = "never-persist-webhook-secret"
        with self.assertRaises(UnsafeMetadataError):
            store.admit_webhook_delivery(
                delivery_id="delivery-secret",
                request_digest="sha256:" + "c" * 64,
                event="issues",
                repository="MSKazemi/idkmesh",
                metadata={"authorization": sentinel},
                received_at="2026-09-24T01:00:00Z",
            )
        self.assertNotIn(sentinel.encode(), self.db.read_bytes())

    def test_schema_v1_migrates_to_v2_without_losing_existing_tables(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript(
                """
                CREATE TABLE connections (
                    connection_id TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO connections(connection_id, metadata_json, updated_at)
                VALUES ('existing', '{}', '2026-09-22T00:00:00Z');
                PRAGMA user_version = 1;
                """
            )

        store = self._store()
        self.assertEqual(store.get_connection("existing"), {})
        with sqlite3.connect(self.db) as conn:
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_deliveries'"
            ).fetchone()
        self.assertEqual(version, 2)
        self.assertIsNotNone(table)

    def test_concurrent_duplicate_webhook_delivery_creates_one_record(self):
        self._store()
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def worker(timestamp):
            try:
                store = self._store()
                barrier.wait(timeout=5)
                record, created = store.admit_webhook_delivery(
                    delivery_id="delivery-concurrent",
                    request_digest="sha256:" + "d" * 64,
                    event="issues",
                    repository="MSKazemi/idkmesh",
                    metadata={"action": "labeled"},
                    received_at=timestamp,
                )
                outcomes.append((record.received_at, created))
            except Exception as exc:
                failures.append(exc)

        threads = [
            threading.Thread(target=worker, args=("2026-09-24T01:00:00Z",)),
            threading.Thread(target=worker, args=("2026-09-24T01:00:01Z",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sum(1 for _, created in outcomes if created), 1)
        self.assertEqual(len({received for received, _ in outcomes}), 1)

    def test_same_idempotency_key_and_digest_returns_existing_run(self):
        store = self._store()
        first, created_first = store.admit_run(
            run_id="run-1",
            idempotency_key="dispatch:wu-1:attempt-1",
            request_digest="sha256:same",
            state="admitted",
            metadata={"connection_id": "agent-one"},
            created_at="2026-09-22T14:23:00Z",
        )
        second, created_second = store.admit_run(
            run_id="run-should-not-replace",
            idempotency_key="dispatch:wu-1:attempt-1",
            request_digest="sha256:same",
            state="admitted",
            metadata={"connection_id": "different-input-is-ignored-after-admission"},
            created_at="2026-09-22T14:24:00Z",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(second.run_id, first.run_id)
        self.assertEqual(second.metadata["connection_id"], "agent-one")

    def test_same_idempotency_key_with_different_digest_conflicts(self):
        store = self._store()
        store.admit_run(
            run_id="run-1",
            idempotency_key="dispatch:key",
            request_digest="sha256:first",
            state="admitted",
            metadata={},
            created_at="2026-09-22T14:25:00Z",
        )
        with self.assertRaises(LocalStoreConflict):
            store.admit_run(
                run_id="run-2",
                idempotency_key="dispatch:key",
                request_digest="sha256:second",
                state="admitted",
                metadata={},
                created_at="2026-09-22T14:26:00Z",
            )

    def test_run_state_survives_process_style_restart(self):
        self._store().admit_run(
            run_id="run-restart",
            idempotency_key="dispatch:restart",
            request_digest="sha256:restart",
            state="admitted",
            metadata={"attempt": 1},
            created_at="2026-09-22T14:27:00Z",
        )

        restarted = self._store()
        record = restarted.get_run("run-restart")
        self.assertEqual(record.state, "admitted")
        self.assertEqual(record.metadata["attempt"], 1)

        updated = restarted.update_run(
            "run-restart",
            state="waiting_for_agent",
            metadata={"attempt": 1, "external_ref": "provider/session-1"},
            updated_at="2026-09-22T14:28:00Z",
        )
        self.assertEqual(updated.state, "waiting_for_agent")
        self.assertEqual(
            self._store().get_run("run-restart").metadata["external_ref"],
            "provider/session-1",
        )

    def test_duplicate_probe_is_idempotent_but_conflicting_rewrite_is_blocked(self):
        store = self._store()
        kwargs = dict(
            connection_id="agent-one",
            checked_at="2026-09-22T14:29:00Z",
            status="healthy",
            metadata={"latency_class": "normal"},
        )
        store.record_probe(**kwargs)
        store.record_probe(**kwargs)
        with self.assertRaises(LocalStoreConflict):
            store.record_probe(
                "agent-one",
                checked_at="2026-09-22T14:29:00Z",
                status="unavailable",
                metadata={"latency_class": "normal"},
            )

    def test_duplicate_route_is_idempotent_but_conflicting_rewrite_is_blocked(self):
        store = self._store()
        kwargs = dict(
            route_id="route-fixed",
            request_digest="sha256:route-fixed",
            metadata={"selected": "agent-one"},
            created_at="2026-09-22T14:30:00Z",
        )
        store.record_route(**kwargs)
        store.record_route(**kwargs)
        with self.assertRaises(LocalStoreConflict):
            store.record_route(
                "route-fixed",
                request_digest="sha256:changed",
                metadata={"selected": "agent-two"},
                created_at="2026-09-22T14:30:00Z",
            )

    def test_concurrent_duplicate_admission_creates_exactly_one_run(self):
        self._store()  # initialize/migrate before racing admission transactions
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def worker(run_id):
            try:
                store = self._store()
                barrier.wait(timeout=5)
                record, created = store.admit_run(
                    run_id=run_id,
                    idempotency_key="dispatch:concurrent",
                    request_digest="sha256:concurrent",
                    state="admitted",
                    metadata={"source": "same-request"},
                    created_at="2026-09-22T14:31:00Z",
                )
                outcomes.append((record.run_id, created))
            except Exception as exc:
                failures.append(exc)

        threads = [
            threading.Thread(target=worker, args=("run-a",)),
            threading.Thread(target=worker, args=("run-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sum(1 for _, created in outcomes if created), 1)
        self.assertEqual(len({run_id for run_id, _ in outcomes}), 1)

    def test_sensitive_metadata_keys_are_rejected_before_persistence(self):
        store = self._store()
        sentinel = "never-write-this-secret"
        with self.assertRaises(UnsafeMetadataError):
            store.record_connection(
                "unsafe",
                metadata={"nested": {"api_key": sentinel}},
                updated_at="2026-09-22T14:32:00Z",
            )
        self.assertNotIn(sentinel.encode(), self.db.read_bytes())

    def test_secret_reference_is_allowed_but_secret_value_object_is_not(self):
        store = self._store()
        store.record_connection(
            "safe",
            metadata={"secret_ref": "env:PROVIDER_KEY"},
            updated_at="2026-09-22T14:33:00Z",
        )

        with self.assertRaises(UnsafeMetadataError):
            store.record_connection(
                "unsafe-ref",
                metadata={"secret_ref": "raw-provider-secret-value"},
                updated_at="2026-09-22T14:33:30Z",
            )

        class SecretValue:
            pass

        with self.assertRaises(UnsafeMetadataError):
            store.record_connection(
                "unsafe-object",
                metadata={"value": SecretValue()},
                updated_at="2026-09-22T14:34:00Z",
            )

    def test_schema_version_newer_than_supported_fails_closed(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("PRAGMA user_version = 999")
        with self.assertRaises(LocalStoreError):
            self._store()

    def test_unknown_run_update_fails(self):
        with self.assertRaises(LocalStoreError):
            self._store().update_run(
                "missing",
                state="failed",
                metadata={},
                updated_at="2026-09-22T14:35:00Z",
            )


if __name__ == "__main__":
    unittest.main()
