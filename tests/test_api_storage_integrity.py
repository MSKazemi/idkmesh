"""Storage integrity, migration and reconstruction tests (issue #750, API-13).

``docs/specifications/API_STORAGE_PROFILES_V0_1.md`` lists the semantics the
API's durable store must keep. The existing suites already pin idempotent
replay, run-projection tamper detection and newer-schema refusal; this module
adds the ones that were not covered:

* **event integrity** -- the append-only triggers stop the *application* from
  rewriting an event, but a damaged or hand-edited database file bypasses
  them, so every read recomputes ``payload_digest`` and checks that the
  indexed columns still agree with the envelope. A mismatch is a controlled
  store error (HTTP 500 ``store_error``) and the altered content is never
  served. This was a real gap: ``payload_digest`` was written but never
  verified, so an edited payload was served as if it were the original;
* **migration replay** -- an older database upgrades in place, keeps its rows,
  and opening it again is a no-op;
* **restart reconstruction** -- run state, the event log and its cursors are
  rebuilt identically from the durable file alone.

Class-based on purpose: the repository's documented test counts guard
module-level ``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from idkmesh.connector_store import (
    SCHEMA_VERSION,
    LocalMetadataStore,
    LocalStoreError,
)
from idkmesh.control_tower_ui import create_server
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import (
    ProductSpineRunStore,
    ProductSpineRunStoreError,
)

SHA = "0123456789abcdef0123456789abcdef01234567"
TAMPER_MARKER = "tampered-payload-marker"


def _run(index: int) -> ProductSpineRun:
    return ProductSpineRun(
        run_id=f"run/storage-{index}",
        request_digest="sha256:" + f"{index:x}" * 64,
        project_id="project.storage" if index % 2 == 0 else "project.other",
        work_unit_id=f"work/storage-{index}",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-storage-")
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "state.sqlite"
        self.service = ProductSpineRunStore(LocalMetadataStore(self.path))

    def seed(self, count: int = 3) -> None:
        for index in range(1, count + 1):
            self.service.create(
                _run(index),
                idempotency_key=f"storage-{index}",
                created_at="2026-10-10T10:00:00Z",
            )

    def edit_event(self, sequence: int, mutate, *, column_updates=None) -> None:
        """Rewrite a stored event the way file damage would: past the triggers."""
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TRIGGER events_no_update")
            row = conn.execute(
                "SELECT envelope_json FROM events WHERE sequence = ?", (sequence,)
            ).fetchone()
            envelope = json.loads(row[0])
            mutate(envelope)
            conn.execute(
                "UPDATE events SET envelope_json = ? WHERE sequence = ?",
                (json.dumps(envelope, sort_keys=True), sequence),
            )
            for column, value in (column_updates or {}).items():
                conn.execute(
                    f"UPDATE events SET {column} = ? WHERE sequence = ?",
                    (value, sequence),
                )

    def reopen(self) -> ProductSpineRunStore:
        return ProductSpineRunStore(LocalMetadataStore(self.path))


class EventIntegrityTests(_StoreCase):
    def test_untouched_events_round_trip_with_a_verified_digest(self) -> None:
        self.seed()
        events, cursor = self.service.list_events()
        self.assertEqual(len(events), 3)
        self.assertIsNone(cursor)
        for event in events:
            self.assertTrue(event["payload_digest"].startswith("sha256:"))

    def test_the_triggers_block_application_level_rewrites(self) -> None:
        self.seed(1)
        with sqlite3.connect(self.path) as conn:
            for statement in (
                "UPDATE events SET event_type = 'run.cancelled'",
                "DELETE FROM events",
            ):
                with self.subTest(statement=statement):
                    with self.assertRaisesRegex(
                        sqlite3.DatabaseError, "append-only"
                    ):
                        conn.execute(statement)

    def test_an_edited_payload_is_detected_and_not_served(self) -> None:
        self.seed()
        self.edit_event(1, lambda e: e["payload"].update(state=TAMPER_MARKER))
        with self.assertRaisesRegex(
            ProductSpineRunStoreError, "does not match its payload_digest"
        ):
            self.reopen().list_events()

    def test_an_edited_payload_digest_is_detected(self) -> None:
        self.seed()
        self.edit_event(2, lambda e: e.update(payload_digest="sha256:" + "0" * 64))
        with self.assertRaisesRegex(
            ProductSpineRunStoreError, "does not match its payload_digest"
        ):
            self.reopen().list_events()

    def test_an_event_moved_to_another_run_is_detected(self) -> None:
        # The filters match the indexed columns; the envelope is what is
        # served. If they disagree, an event could be found under one run and
        # served as another.
        self.seed()
        self.edit_event(
            1,
            lambda e: e.update(run_id="run/storage-2"),
        )
        with self.assertRaisesRegex(ProductSpineRunStoreError, "run_id differs"):
            self.reopen().list_events(run_id="run/storage-1")

    def test_a_substituted_event_type_column_is_detected(self) -> None:
        self.seed()
        self.edit_event(
            1, lambda e: None, column_updates={"event_type": "run.cancelled"}
        )
        with self.assertRaisesRegex(ProductSpineRunStoreError, "event_type differs"):
            self.reopen().list_events()

    def test_a_non_object_payload_is_a_store_error_not_a_crash(self) -> None:
        self.seed()
        self.edit_event(1, lambda e: e.update(payload=["x"] * 3))
        with self.assertRaises(ProductSpineRunStoreError):
            self.reopen().list_events()

    def test_the_low_level_store_raises_a_store_error(self) -> None:
        self.seed()
        self.edit_event(1, lambda e: e["payload"].update(state=TAMPER_MARKER))
        with self.assertRaises(LocalStoreError):
            LocalMetadataStore(self.path).list_events()

    def test_damage_is_contained_to_the_reads_that_touch_it(self) -> None:
        self.seed()
        self.edit_event(3, lambda e: e["payload"].update(state=TAMPER_MARKER))
        service = self.reopen()
        events, _ = service.list_events(run_id="run/storage-1")
        self.assertEqual([e["run_id"] for e in events], ["run/storage-1"])
        self.assertEqual(service.status("run/storage-3").run.run_id, "run/storage-3")


class EventIntegrityOverHttpTests(_StoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.seed()
        self.edit_event(2, lambda e: e["payload"].update(state=TAMPER_MARKER))
        self.server = create_server(
            port=0, product_spine_store_path=str(self.path)
        )
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def stop() -> None:
            self.server.shutdown()
            self.server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)

    def get(self, path: str):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        try:
            conn.request("GET", path, headers={TOKEN_HEADER: self.server.ui_token})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_a_damaged_event_is_a_controlled_500_and_never_served(self) -> None:
        status, body = self.get("/api/v1/events")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"]["code"], "store_error")
        self.assertNotIn(TAMPER_MARKER.encode(), body)

    def test_reads_that_avoid_the_damage_keep_working(self) -> None:
        status, body = self.get("/api/v1/events?run_id=run/storage-1")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["items"]), 1)
        self.assertEqual(self.get("/api/v1/status")[0], 200)


class MigrationReplayTests(unittest.TestCase):
    V1_DDL = """
    CREATE TABLE connections (connection_id TEXT PRIMARY KEY,
        metadata_json TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE probes (connection_id TEXT NOT NULL, checked_at TEXT NOT NULL,
        status TEXT NOT NULL, metadata_json TEXT NOT NULL,
        PRIMARY KEY (connection_id, checked_at));
    CREATE TABLE routes (route_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL,
        metadata_json TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE runs (run_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
        request_digest TEXT NOT NULL, state TEXT NOT NULL,
        metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL);
    CREATE TABLE idempotency (idempotency_key TEXT PRIMARY KEY,
        request_digest TEXT NOT NULL, run_id TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL, FOREIGN KEY (run_id) REFERENCES runs(run_id));
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-migrate-")
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "old.sqlite"
        with sqlite3.connect(self.path) as conn:
            conn.executescript(self.V1_DDL)
            conn.execute(
                "INSERT INTO connections VALUES (?, ?, ?)",
                ("conn-1", '{"id":"conn-1"}', "2026-09-01T00:00:00Z"),
            )
            conn.execute("PRAGMA user_version = 1")

    def version(self) -> int:
        with sqlite3.connect(self.path) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def tables(self) -> set[str]:
        with sqlite3.connect(self.path) as conn:
            return {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

    def test_an_old_database_upgrades_in_place_and_keeps_its_rows(self) -> None:
        self.assertEqual(self.version(), 1)
        store = LocalMetadataStore(self.path)
        self.assertEqual(self.version(), SCHEMA_VERSION)
        self.assertEqual(store.get_connection("conn-1")["id"], "conn-1")
        self.assertLessEqual(
            {"events", "task_claims", "task_claim_policies"}, self.tables()
        )

    def test_the_upgraded_database_enforces_append_only_events(self) -> None:
        LocalMetadataStore(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO events(occurred_at, event_type, project_id, "
                "work_unit_id, run_id, attempt_id, envelope_json) "
                "VALUES ('2026-10-10T10:00:00Z', 'run.created', 'p', 'w', 'r', "
                "NULL, '{}')"
            )
            for statement in ("DELETE FROM events", "UPDATE events SET run_id = 'x'"):
                with self.subTest(statement=statement):
                    with self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
                        conn.execute(statement)

    def test_reopening_is_a_replayable_no_op(self) -> None:
        LocalMetadataStore(self.path)
        with sqlite3.connect(self.path) as conn:
            before = conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY name"
            ).fetchall()
        for _ in range(3):
            LocalMetadataStore(self.path)
        with sqlite3.connect(self.path) as conn:
            after = conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY name"
            ).fetchall()
        self.assertEqual(before, after)
        self.assertEqual(self.version(), SCHEMA_VERSION)

    def test_a_newer_database_is_refused_and_left_untouched(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        with self.assertRaisesRegex(LocalStoreError, "newer than supported"):
            LocalMetadataStore(self.path)
        self.assertEqual(self.version(), SCHEMA_VERSION + 1)
        self.assertNotIn("events", self.tables())


class RestartReconstructionTests(_StoreCase):
    def test_state_events_and_cursors_are_rebuilt_from_the_file_alone(self) -> None:
        self.seed(4)
        self.service.cancel(
            "run/storage-2", updated_at="2026-10-10T11:00:00Z"
        )
        runs_before, _ = self.service.list(limit=50)
        events_before, _ = self.service.list_events(limit=50)
        page_one, cursor = self.service.list_events(limit=2)

        rebuilt = self.reopen()  # a fresh process: nothing but the file
        runs_after, _ = rebuilt.list(limit=50)
        events_after, _ = rebuilt.list_events(limit=50)

        self.assertEqual(runs_after, runs_before)
        self.assertEqual(events_after, events_before)
        self.assertEqual(rebuilt.status("run/storage-2").run.state, "cancelled")
        # A cursor issued before the restart still continues the same stream.
        resumed, end = rebuilt.list_events(limit=50, cursor=cursor)
        self.assertEqual(page_one + resumed, events_before)
        self.assertIsNone(end)
        self.assertEqual(
            [e["sequence"] for e in events_after],
            sorted(e["sequence"] for e in events_after),
        )

    def test_an_online_backup_reconstructs_the_same_state(self) -> None:
        self.seed(3)
        self.service.cancel("run/storage-1", updated_at="2026-10-10T11:00:00Z")
        backup = self.path.with_name("backup.sqlite")
        with sqlite3.connect(self.path) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        restored = ProductSpineRunStore(LocalMetadataStore(backup))
        self.assertEqual(restored.list(limit=50), self.service.list(limit=50))
        self.assertEqual(
            restored.list_events(limit=50), self.service.list_events(limit=50)
        )

    def test_exact_replay_after_restart_returns_the_original_and_adds_no_event(
        self,
    ) -> None:
        self.seed(1)
        count = len(self.service.list_events()[0])
        replay = self.reopen().create(
            _run(1),
            idempotency_key="storage-1",
            created_at="2026-10-10T10:00:00Z",
        )
        self.assertTrue(replay.replayed)
        self.assertFalse(replay.created)
        self.assertEqual(len(self.reopen().list_events()[0]), count)


class ProbeHistoryPruningTests(unittest.TestCase):
    """Retention (#750): only the expendable probe history may be pruned."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = LocalMetadataStore(Path(tmp.name) / "state.sqlite")

    def _probe(self, connection_id: str, checked_at: str) -> None:
        self.store.record_probe(
            connection_id, checked_at=checked_at, status="ok", metadata={}
        )

    def _count(self, table: str) -> int:
        with sqlite3.connect(self.store.path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_keeps_only_the_latest_probe_per_connection(self) -> None:
        for stamp in ("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z", "2026-01-02T00:00:00Z"):
            self._probe("conn-a", stamp)
        self._probe("conn-b", "2026-01-01T00:00:00Z")

        self.assertEqual(self.store.prune_probe_history(), 2)

        self.assertEqual(self._count("probes"), 2)
        self.assertEqual(
            self.store.latest_probe("conn-a")["checked_at"], "2026-01-03T00:00:00Z"
        )
        self.assertEqual(
            self.store.latest_probe("conn-b")["checked_at"], "2026-01-01T00:00:00Z"
        )

    def test_second_call_is_a_no_op_and_empty_store_is_safe(self) -> None:
        self.assertEqual(self.store.prune_probe_history(), 0)
        self._probe("conn-a", "2026-01-01T00:00:00Z")
        self._probe("conn-a", "2026-01-02T00:00:00Z")
        self.assertEqual(self.store.prune_probe_history(), 1)
        self.assertEqual(self.store.prune_probe_history(), 0)

    def test_essential_records_are_never_pruned(self) -> None:
        self._probe("conn-a", "2026-01-01T00:00:00Z")
        self._probe("conn-a", "2026-01-02T00:00:00Z")
        before = {t: self._count(t) for t in ("runs", "idempotency", "events")}
        self.store.prune_probe_history()
        after = {t: self._count(t) for t in ("runs", "idempotency", "events")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
