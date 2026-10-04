"""Canonical append-only event source, store and service level (ADR-0023, #741).

Written against the ADR-0023 implementation contract:

- ``LocalMetadataStore.admit_run/update_run(..., event=...)`` append an event
  in the same transaction as the run change;
- ``LocalMetadataStore.list_events`` / ``latest_event_sequence``;
- ``ProductSpineRunStore.list_events`` / ``events_after`` /
  ``latest_event_sequence`` and the ``run.created`` / ``run.cancelled`` emitters.
"""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest

from jsonschema import Draft202012Validator

from idkmesh.connector_store import (
    SCHEMA_VERSION,
    LocalMetadataStore,
    LocalStoreError,
)
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import (
    EVENT_AUTHORITY_CLASSES,
    EVENT_TYPES,
    ProductSpineRunStore,
    ProductSpineRunStoreError,
    run_create_request_digest,
)
from idkmesh.work_unit_binding import canonical_digest


SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ENVELOPE_FIELDS = {
    "schema_version", "kind", "event_id", "sequence", "occurred_at",
    "event_type", "principal", "authority_class", "project_id",
    "work_unit_id", "run_id", "attempt_id", "source_revision",
    "evidence_reference", "payload", "payload_digest",
}
INVALID_EVENT_ERRORS = (LocalStoreError, ValueError, TypeError)

# The v1 DDL, copied verbatim from the pre-events store so the migration test
# starts from a database exactly as an older release left it.
V1_DDL = """
CREATE TABLE connections (
    connection_id TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE probes (
    connection_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (connection_id, checked_at)
);
CREATE TABLE routes (
    route_id TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_digest TEXT NOT NULL,
    state TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE idempotency (
    idempotency_key TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
"""


def _event_schema() -> dict:
    root = Path(__file__).resolve().parents[1] / "schemas"
    schema = json.loads(
        (root / "idkmesh-event-v0.1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_event(event: dict) -> None:
    Draft202012Validator(_event_schema()).validate(event)


def _store_event(run_id: str = "run-1", **overrides) -> dict:
    """An ``event=`` mapping as the store contract defines it (no ids/digest)."""
    value = {
        "occurred_at": "2026-10-01T00:00:00Z",
        "event_type": "run.created",
        "principal": {"type": "unauthenticated_local", "id": "local-cli"},
        "authority_class": "local_control",
        "project_id": "project.test",
        "work_unit_id": "work/test-1",
        "run_id": run_id,
        "attempt_id": None,
        "source_revision": "0" * 40,
        "evidence_reference": None,
        "payload": {"state": "proposed", "request_digest": "sha256:" + "a" * 64},
    }
    value.update(overrides)
    return value


def _run(**overrides) -> ProductSpineRun:
    values = {
        "run_id": "run/event-1",
        "request_digest": "sha256:" + "a" * 64,
        "project_id": "project.test",
        "work_unit_id": "work/test-1",
        "work_unit_version": 1,
        "work_unit_digest": "sha256:" + "b" * 64,
        "source_revision": SHA,
        "authority_mode": "agent_candidate",
        "routing_policy_version": "c1-v0.1",
        "state": "proposed",
    }
    values.update(overrides)
    return ProductSpineRun(**values)


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite"
        self.store = LocalMetadataStore(self.path)

    def admit(self, run_id: str, *, event=None, key=None,
              created_at="2026-10-01T00:00:00Z", digest="sha256:same"):
        return self.store.admit_run(
            run_id=run_id,
            idempotency_key=key or f"key:{run_id}",
            request_digest=digest,
            state="proposed",
            metadata={"run_id": run_id,
                      "projection": {"project_id": "project.test"}},
            created_at=created_at,
            event=event,
        )

    def events(self, **kwargs):
        page, has_more = self.store.list_events(limit=200, **kwargs)
        self.assertFalse(has_more)
        return page


class EventMigrationTests(_StoreCase):
    def test_a_fresh_store_is_current_schema_with_an_events_table(self) -> None:
        self.assertGreaterEqual(SCHEMA_VERSION, 2)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION
            )
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("events", names)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.store.latest_event_sequence(), 0)

    def test_a_v1_database_is_migrated_in_place_keeping_its_runs(self) -> None:
        path = Path(self.temp.name) / "legacy.sqlite"
        with closing(sqlite3.connect(path)) as conn:
            conn.executescript(V1_DDL)
            conn.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("run-legacy", "key:legacy", "sha256:same", "proposed",
                 '{"run_id":"run-legacy"}', "2026-09-01T00:00:00Z",
                 "2026-09-01T00:00:00Z"),
            )
            conn.execute(
                "INSERT INTO idempotency VALUES (?, ?, ?, ?)",
                ("key:legacy", "sha256:same", "run-legacy",
                 "2026-09-01T00:00:00Z"),
            )
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        migrated = LocalMetadataStore(path)

        with closing(sqlite3.connect(path)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION
            )
        self.assertEqual(migrated.get_run("run-legacy").state, "proposed")
        self.assertEqual(migrated.list_events(limit=10), ([], False))
        record, created = migrated.admit_run(
            run_id="run-new",
            idempotency_key="key:new",
            request_digest="sha256:new",
            state="proposed",
            metadata={"run_id": "run-new"},
            created_at="2026-10-01T00:00:00Z",
            event=_store_event("run-new"),
        )
        self.assertTrue(created)
        (event,), _ = migrated.list_events(limit=10)
        self.assertEqual(event["sequence"], 1)

    def test_a_newer_schema_is_refused_not_silently_downgraded(self) -> None:
        path = Path(self.temp.name) / "future.sqlite"
        LocalMetadataStore(path)
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
            conn.commit()
        with self.assertRaises(LocalStoreError):
            LocalMetadataStore(path)

    def test_reopening_a_v2_store_keeps_its_events(self) -> None:
        self.admit("run-1", event=_store_event("run-1"))
        reopened = LocalMetadataStore(self.path)
        (event,), _ = reopened.list_events(limit=10)
        self.assertEqual(event["run_id"], "run-1")
        self.assertEqual(reopened.latest_event_sequence(), 1)


class AtomicEmissionTests(_StoreCase):
    def test_admit_run_appends_the_event_with_the_run(self) -> None:
        record, created = self.admit("run-1", event=_store_event("run-1"))
        self.assertTrue(created)
        (event,) = self.events()
        self.assertEqual(event["sequence"], 1)
        self.assertEqual(event["run_id"], "run-1")
        self.assertEqual(self.store.get_run("run-1").state, "proposed")

    def test_update_run_appends_the_event_with_the_state_change(self) -> None:
        self.admit("run-1", event=_store_event("run-1"))
        self.store.update_run(
            "run-1",
            state="cancelled",
            metadata={"run_id": "run-1"},
            updated_at="2026-10-01T00:05:00Z",
            event=_store_event(
                "run-1",
                event_type="run.cancelled",
                occurred_at="2026-10-01T00:05:00Z",
                payload={"previous_state": "proposed", "state": "cancelled"},
            ),
        )
        events = self.events()
        self.assertEqual(
            [e["event_type"] for e in events], ["run.created", "run.cancelled"]
        )
        self.assertEqual(self.store.get_run("run-1").state, "cancelled")

    def test_an_invalid_event_rolls_back_the_run_on_admit(self) -> None:
        bad_events = {
            "missing occurred_at": {
                k: v for k, v in _store_event("run-1").items()
                if k != "occurred_at"
            },
            "payload not an object": _store_event("run-1", payload=["x"]),
        }
        for index, (label, bad) in enumerate(bad_events.items()):
            with self.subTest(label):
                store = LocalMetadataStore(
                    Path(self.temp.name) / f"rollback-{index}.sqlite"
                )

                def admit(event):
                    return store.admit_run(
                        run_id="run-1",
                        idempotency_key="key:run-1",
                        request_digest="sha256:same",
                        state="proposed",
                        metadata={"run_id": "run-1"},
                        created_at="2026-10-01T00:00:00Z",
                        event=event,
                    )

                with self.assertRaises(INVALID_EVENT_ERRORS):
                    admit(bad)
                self.assertIsNone(store.get_run("run-1"))
                self.assertEqual(store.list_events(limit=200), ([], False))
                # The idempotency key was not consumed either.
                _, created = admit(_store_event("run-1"))
                self.assertTrue(created)

    def test_an_invalid_event_rolls_back_the_state_change_on_update(self) -> None:
        self.admit("run-1", event=_store_event("run-1"))
        with self.assertRaises(INVALID_EVENT_ERRORS):
            self.store.update_run(
                "run-1",
                state="cancelled",
                metadata={"run_id": "run-1"},
                updated_at="2026-10-01T00:05:00Z",
                event=_store_event("run-1", payload="not-an-object"),
            )
        self.assertEqual(self.store.get_run("run-1").state, "proposed")
        self.assertEqual(len(self.events()), 1)

    def test_an_idempotent_replay_emits_no_second_event(self) -> None:
        self.admit("run-1", event=_store_event("run-1"), key="k1")
        record, created = self.admit(
            "run-1", event=_store_event("run-1"), key="k1"
        )
        self.assertFalse(created)
        self.assertEqual(len(self.events()), 1)

    def test_an_idempotency_conflict_emits_nothing(self) -> None:
        self.admit("run-1", event=_store_event("run-1"), key="k1")
        with self.assertRaises(LocalStoreError):
            self.admit(
                "run-1", event=_store_event("run-1"), key="k1",
                digest="sha256:different",
            )
        self.assertEqual(len(self.events()), 1)

    def test_writers_that_pass_no_event_emit_none(self) -> None:
        # Coverage is stated, not implied (ADR-0023 item 6): the other
        # run-table writers do not emit events yet.
        self.admit("run-plain")
        self.assertEqual(self.events(), [])
        self.assertEqual(self.store.latest_event_sequence(), 0)


class EnvelopeTests(_StoreCase):
    def test_the_stored_envelope_is_complete_and_schema_valid(self) -> None:
        self.admit("run-1", event=_store_event("run-1"))
        (event,) = self.events()
        self.assertEqual(set(event), ENVELOPE_FIELDS)
        self.assertEqual(event["schema_version"], "0.1")
        self.assertEqual(event["kind"], "idkmesh-event")
        _validate_event(event)

    def test_event_ids_and_sequences_are_monotonic_and_gap_free(self) -> None:
        for index in range(6):
            self.admit(f"run-{index}", event=_store_event(f"run-{index}"))
        events = self.events()
        self.assertEqual([e["sequence"] for e in events], [1, 2, 3, 4, 5, 6])
        for event in events:
            self.assertEqual(
                event["event_id"], f"evt-{event['sequence']:012d}"
            )
        self.assertEqual(len({e["event_id"] for e in events}), 6)
        self.assertEqual(self.store.latest_event_sequence(), 6)

    def test_a_rolled_back_attempt_leaves_no_sequence_gap(self) -> None:
        self.admit("run-1", event=_store_event("run-1"))
        with self.assertRaises(INVALID_EVENT_ERRORS):
            self.admit("run-2", event=_store_event("run-2", payload=None))
        self.admit("run-3", event=_store_event("run-3"))
        self.assertEqual([e["sequence"] for e in self.events()], [1, 2])

    def test_occurred_at_is_exactly_what_the_producer_supplied(self) -> None:
        # Deliberately different from created_at and from the wall clock: the
        # store must not read a clock or reuse another timestamp.
        self.admit(
            "run-1",
            created_at="2026-10-01T09:00:00Z",
            event=_store_event("run-1", occurred_at="2026-09-30T12:34:56Z"),
        )
        (event,) = self.events()
        self.assertEqual(event["occurred_at"], "2026-09-30T12:34:56Z")

    def test_an_event_without_occurred_at_is_rejected_not_defaulted(self) -> None:
        event = _store_event("run-1")
        del event["occurred_at"]
        with self.assertRaises(INVALID_EVENT_ERRORS):
            self.admit("run-1", event=event)
        self.assertEqual(self.events(), [])

    def test_payload_digest_is_the_canonical_digest_of_the_payload(self) -> None:
        payload_a = {"state": "proposed", "request_digest": "sha256:" + "a" * 64}
        payload_b = {"state": "proposed", "request_digest": "sha256:" + "c" * 64}
        self.admit("run-1", event=_store_event("run-1", payload=payload_a))
        self.admit("run-2", event=_store_event("run-2", payload=payload_b))
        first, second = self.events()
        self.assertEqual(first["payload_digest"], canonical_digest(payload_a))
        self.assertEqual(second["payload_digest"], canonical_digest(payload_b))
        self.assertRegex(first["payload_digest"], DIGEST)
        self.assertNotEqual(first["payload_digest"], second["payload_digest"])

    def test_forged_ids_sequences_and_digests_are_rejected_outright(self) -> None:
        # The store accepts exactly the producer-side fields; it alone derives
        # the sequence, event_id, schema_version, kind and payload_digest.
        for field, value in (
            ("payload_digest", "sha256:" + "0" * 64),
            ("event_id", "evt-forged"),
            ("sequence", 99),
            ("schema_version", "9.9"),
            ("kind", "forged"),
            ("unexpected", True),
        ):
            with self.subTest(field):
                event = _store_event("run-1")
                event[field] = value
                with self.assertRaises(INVALID_EVENT_ERRORS):
                    self.admit("run-1", event=event)
                self.assertIsNone(self.store.get_run("run-1"))
                self.assertEqual(self.events(), [])

    def test_a_missing_producer_field_is_rejected(self) -> None:
        for field in ("principal", "authority_class", "project_id",
                      "work_unit_id", "run_id", "event_type", "payload"):
            with self.subTest(field):
                event = _store_event("run-1")
                del event[field]
                with self.assertRaises(INVALID_EVENT_ERRORS):
                    self.admit("run-1", event=event)
                self.assertIsNone(self.store.get_run("run-1"))

    def test_a_malformed_principal_or_evidence_reference_is_rejected(self) -> None:
        bad = (
            {"principal": {"type": "unauthenticated_local"}},
            {"principal": "local-cli"},
            {"evidence_reference": {"kind": "report"}},
            {"evidence_reference": "sha256:abc"},
        )
        for overrides in bad:
            with self.subTest(overrides):
                with self.assertRaises(INVALID_EVENT_ERRORS):
                    self.admit("run-1", event=_store_event("run-1", **overrides))
                self.assertIsNone(self.store.get_run("run-1"))

    def test_a_well_formed_evidence_reference_round_trips(self) -> None:
        reference = {"kind": "run-evidence-report", "digest": "sha256:" + "d" * 64}
        self.admit("run-1", event=_store_event("run-1", evidence_reference=reference))
        (event,) = self.events()
        self.assertEqual(event["evidence_reference"], reference)
        _validate_event(event)


class ListEventsStoreTests(_StoreCase):
    def seed(self) -> None:
        rows = [
            ("run/e-1", "project.alpha", "work/a", "run.created"),
            ("run/e-10", "project.alpha", "work/b", "run.created"),
            ("run/e-2", "project.beta", "work/a", "run.created"),
            ("run/e-1", "project.alpha", "work/a", "run.cancelled"),
        ]
        for index, (run_id, project, work_unit, event_type) in enumerate(rows):
            event = _store_event(
                run_id,
                project_id=project,
                work_unit_id=work_unit,
                event_type=event_type,
            )
            if event_type == "run.created":
                self.admit(run_id, event=event, key=f"k{index}")
            else:
                self.store.update_run(
                    run_id,
                    state="cancelled",
                    metadata={"run_id": run_id},
                    updated_at="2026-10-01T00:10:00Z",
                    event=event,
                )

    def test_orders_by_sequence_ascending(self) -> None:
        self.seed()
        self.assertEqual(
            [e["sequence"] for e in self.events()], [1, 2, 3, 4]
        )

    def test_keyset_pagination_by_after_sequence(self) -> None:
        self.seed()
        page1, more1 = self.store.list_events(limit=2)
        page2, more2 = self.store.list_events(
            limit=2, after_sequence=page1[-1]["sequence"]
        )
        self.assertEqual([e["sequence"] for e in page1], [1, 2])
        self.assertTrue(more1)
        self.assertEqual([e["sequence"] for e in page2], [3, 4])
        self.assertFalse(more2)
        again, _ = self.store.list_events(
            limit=2, after_sequence=page1[-1]["sequence"]
        )
        self.assertEqual(again, page2)

    def test_filters_are_exact_match_and_combine_with_and(self) -> None:
        self.seed()
        self.assertEqual(
            [e["sequence"] for e in self.events(project_id="project.alpha")],
            [1, 2, 4],
        )
        # Exact match: "run/e-1" must not also select "run/e-10".
        self.assertEqual(
            [e["sequence"] for e in self.events(run_id="run/e-1")], [1, 4]
        )
        self.assertEqual(
            [e["sequence"] for e in self.events(work_unit_id="work/a")],
            [1, 3, 4],
        )
        self.assertEqual(
            [e["sequence"] for e in self.events(event_type="run.cancelled")],
            [4],
        )
        self.assertEqual(
            [
                e["sequence"]
                for e in self.events(
                    project_id="project.alpha", work_unit_id="work/a"
                )
            ],
            [1, 4],
        )
        self.assertEqual(self.events(project_id="nobody"), [])

    def test_filtered_pagination_keeps_the_filter_across_pages(self) -> None:
        self.seed()
        page1, more1 = self.store.list_events(limit=1, project_id="project.alpha")
        page2, more2 = self.store.list_events(
            limit=1, project_id="project.alpha",
            after_sequence=page1[-1]["sequence"],
        )
        self.assertEqual([e["sequence"] for e in page1 + page2], [1, 2])
        self.assertTrue(more1 and more2)

    def test_limit_must_be_between_1_and_200(self) -> None:
        for bad in (0, -1, 201, True, "5"):
            with self.subTest(limit=bad):
                with self.assertRaises(ValueError):
                    self.store.list_events(limit=bad)
        self.store.list_events(limit=1)
        self.store.list_events(limit=200)

    def test_every_listed_event_validates_against_the_schema(self) -> None:
        self.seed()
        for event in self.events():
            _validate_event(event)


class ProductSpineEventServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite"
        self.service = ProductSpineRunStore(LocalMetadataStore(self.path))

    def create(self, run_id: str, *, project="project.test",
               work_unit="work/test-1", key=None, second=0):
        return self.service.create(
            _run(run_id=run_id, project_id=project, work_unit_id=work_unit),
            idempotency_key=key or f"key-{run_id}",
            created_at=f"2026-10-01T00:00:{second:02d}Z",
        )

    def all_events(self, **filters):
        events, cursor = self.service.list_events(limit=200, **filters)
        self.assertIsNone(cursor)
        return events

    def test_the_documented_vocabularies(self) -> None:
        self.assertEqual(set(EVENT_TYPES), {"run.created", "run.cancelled"})
        self.assertEqual(
            set(EVENT_AUTHORITY_CLASSES),
            {"local_control", "worker_observation",
             "verifier_recommendation", "human_decision"},
        )

    def test_create_emits_exactly_one_run_created_event(self) -> None:
        run = _run(run_id="run/event-1")
        self.service.create(
            run, idempotency_key="k1", created_at="2026-10-01T00:00:07Z"
        )
        (event,) = self.all_events()
        self.assertEqual(event["event_type"], "run.created")
        self.assertEqual(event["run_id"], "run/event-1")
        self.assertEqual(event["project_id"], "project.test")
        self.assertEqual(event["work_unit_id"], "work/test-1")
        self.assertEqual(event["source_revision"], SHA)
        self.assertIsNone(event["attempt_id"])
        self.assertIsNone(event["evidence_reference"])
        self.assertEqual(event["occurred_at"], "2026-10-01T00:00:07Z")
        self.assertEqual(event["authority_class"], "local_control")
        self.assertEqual(
            event["principal"],
            {"type": "unauthenticated_local", "id": "local-cli"},
        )
        self.assertEqual(set(event["payload"]), {"state", "request_digest"})
        self.assertEqual(event["payload"]["state"], "proposed")
        self.assertRegex(event["payload"]["request_digest"], DIGEST)
        self.assertEqual(
            event["payload"]["request_digest"], run_create_request_digest(run)
        )
        self.assertEqual(
            event["payload_digest"], canonical_digest(event["payload"])
        )
        _validate_event(event)

    def test_replaying_a_create_emits_no_second_event(self) -> None:
        first = self.create("run/event-1", key="same")
        replay = self.create("run/event-1", key="same")
        self.assertTrue(first.created)
        self.assertTrue(replay.replayed)
        self.assertEqual(len(self.all_events()), 1)

    def test_a_conflicting_create_emits_no_event(self) -> None:
        self.create("run/event-1", key="same")
        with self.assertRaises(ProductSpineRunStoreError):
            self.service.create(
                _run(run_id="run/event-1", work_unit_id="work/other"),
                idempotency_key="same",
                created_at="2026-10-01T00:00:09Z",
            )
        self.assertEqual(len(self.all_events()), 1)

    def test_create_then_cancel_produce_created_then_cancelled(self) -> None:
        self.create("run/event-1")
        self.service.cancel("run/event-1", updated_at="2026-10-01T00:30:00Z")
        created, cancelled = self.all_events()
        self.assertEqual(created["event_type"], "run.created")
        self.assertEqual(cancelled["event_type"], "run.cancelled")
        self.assertEqual(
            cancelled["payload"],
            {"previous_state": "proposed", "state": "cancelled"},
        )
        self.assertEqual(cancelled["occurred_at"], "2026-10-01T00:30:00Z")
        self.assertEqual(cancelled["run_id"], "run/event-1")
        self.assertEqual(cancelled["authority_class"], "local_control")
        self.assertEqual(
            cancelled["payload_digest"], canonical_digest(cancelled["payload"])
        )
        self.assertEqual([created["sequence"], cancelled["sequence"]], [1, 2])
        _validate_event(cancelled)

    def test_cancelling_an_already_cancelled_run_emits_nothing_new(self) -> None:
        self.create("run/event-1")
        self.service.cancel("run/event-1", updated_at="2026-10-01T00:30:00Z")
        self.service.cancel("run/event-1", updated_at="2026-10-01T00:31:00Z")
        self.assertEqual(
            [e["event_type"] for e in self.all_events()],
            ["run.created", "run.cancelled"],
        )

    def test_cancelling_an_unknown_run_emits_nothing(self) -> None:
        with self.assertRaises(ProductSpineRunStoreError):
            self.service.cancel("run/missing", updated_at="2026-10-01T00:30:00Z")
        self.assertEqual(self.all_events(), [])

    def seed(self) -> None:
        self.create("run/e-1", project="project.alpha", work_unit="work/a", second=1)
        self.create("run/e-10", project="project.alpha", work_unit="work/b", second=2)
        self.create("run/e-2", project="project.beta", work_unit="work/a", second=3)
        self.service.cancel("run/e-1", updated_at="2026-10-01T00:10:00Z")

    def test_list_events_filters_and_orders(self) -> None:
        self.seed()
        self.assertEqual(
            [e["sequence"] for e in self.all_events()], [1, 2, 3, 4]
        )
        self.assertEqual(
            [e["sequence"] for e in self.all_events(run_id="run/e-1")], [1, 4]
        )
        self.assertEqual(
            [e["sequence"] for e in self.all_events(project_id="project.beta")],
            [3],
        )
        self.assertEqual(
            [e["sequence"] for e in self.all_events(work_unit_id="work/a")],
            [1, 3, 4],
        )
        self.assertEqual(
            [e["sequence"] for e in self.all_events(event_type="run.cancelled")],
            [4],
        )

    def test_list_events_pages_with_an_opaque_cursor(self) -> None:
        self.seed()
        page1, cursor = self.service.list_events(limit=3)
        self.assertEqual([e["sequence"] for e in page1], [1, 2, 3])
        self.assertIsInstance(cursor, str)
        page2, last = self.service.list_events(limit=3, cursor=cursor)
        self.assertEqual([e["sequence"] for e in page2], [4])
        self.assertIsNone(last)

    def test_the_cursor_keeps_its_filter_scope_across_pages(self) -> None:
        self.seed()
        page1, cursor = self.service.list_events(
            limit=1, project_id="project.alpha"
        )
        page2, cursor2 = self.service.list_events(
            limit=1, project_id="project.alpha", cursor=cursor
        )
        self.assertEqual([e["sequence"] for e in page1 + page2], [1, 2])
        self.assertIsNotNone(cursor2)

    def test_list_events_rejects_bad_input_with_stable_codes(self) -> None:
        self.seed()
        cases = (
            ({"limit": 0}, "invalid_limit"),
            ({"limit": 201}, "invalid_limit"),
            ({"limit": 5, "cursor": "not-a-cursor"}, "invalid_cursor"),
            ({"limit": 5, "event_type": "run.exploded"}, "invalid_event_type"),
        )
        for kwargs, code in cases:
            with self.subTest(kwargs):
                with self.assertRaises(ProductSpineRunStoreError) as ctx:
                    self.service.list_events(**kwargs)
                self.assertEqual(ctx.exception.code, code)

    def test_the_events_cursor_is_scoped_to_the_events_listing(self) -> None:
        self.seed()
        _, run_cursor = self.service.list(limit=1)
        _, work_unit_cursor = self.service.list_work_units(limit=1)
        _, event_cursor = self.service.list_events(limit=1)
        self.assertIsNotNone(run_cursor)
        self.assertIsNotNone(work_unit_cursor)
        self.assertIsNotNone(event_cursor)
        for foreign in (run_cursor, work_unit_cursor):
            with self.assertRaises(ProductSpineRunStoreError) as ctx:
                self.service.list_events(limit=5, cursor=foreign)
            self.assertEqual(ctx.exception.code, "invalid_cursor")
        # And an events cursor is not accepted by the other listings.
        with self.assertRaises(ProductSpineRunStoreError):
            self.service.list(cursor=event_cursor)
        with self.assertRaises(ProductSpineRunStoreError):
            self.service.list_work_units(cursor=event_cursor)

    def test_events_after_returns_only_later_events_in_order(self) -> None:
        self.seed()
        self.assertEqual(
            [e["sequence"] for e in self.service.events_after(2)], [3, 4]
        )
        self.assertEqual(self.service.events_after(4), [])
        self.assertEqual(
            [e["sequence"] for e in self.service.events_after(0)], [1, 2, 3, 4]
        )

    def test_events_after_honours_filters_and_limit(self) -> None:
        self.seed()
        self.assertEqual(
            [
                e["sequence"]
                for e in self.service.events_after(0, project_id="project.alpha")
            ],
            [1, 2, 4],
        )
        self.assertEqual(
            [e["sequence"] for e in self.service.events_after(0, limit=2)],
            [1, 2],
        )
        self.assertEqual(
            [
                e["sequence"]
                for e in self.service.events_after(1, run_id="run/e-1")
            ],
            [4],
        )

    def test_latest_event_sequence_tracks_the_stream_head(self) -> None:
        self.assertEqual(self.service.latest_event_sequence(), 0)
        self.create("run/e-1", second=1)
        self.assertEqual(self.service.latest_event_sequence(), 1)
        self.service.cancel("run/e-1", updated_at="2026-10-01T00:10:00Z")
        self.assertEqual(self.service.latest_event_sequence(), 2)

    def test_resuming_after_the_last_seen_event_never_duplicates(self) -> None:
        self.seed()
        seen = [e["sequence"] for e in self.service.events_after(0, limit=2)]
        seen += [e["sequence"] for e in self.service.events_after(seen[-1])]
        self.assertEqual(seen, [1, 2, 3, 4])
        self.assertEqual(len(set(seen)), len(seen))

    def test_other_run_state_writes_do_not_invent_events(self) -> None:
        # Listing and reading never emit: events are produced only by the
        # control actions that change state.
        self.create("run/e-1", second=1)
        before = self.service.latest_event_sequence()
        self.service.status("run/e-1")
        self.service.list(limit=5)
        self.service.list_work_units(limit=5)
        self.service.get_project("project.test")
        self.assertEqual(self.service.latest_event_sequence(), before)


if __name__ == "__main__":
    unittest.main()
