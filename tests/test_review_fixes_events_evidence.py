"""Regression tests for the static-review fixes to ADR-0023 / ADR-0024.

Each class pins one fix that landed after a read-only review of the event
source, the SSE server and the retained-evidence read:

* hardened event cursors and distinct blank-filter errors;
* a conditional ``update_run`` so a racing double cancel emits one event;
* the store enforcing the published event envelope (enums, timestamp, source
  revision, run binding) before anything is written;
* atomic rollback when a failure happens after the run row was inserted;
* offline-spine runs being readable but never cancellable (cancel used to be
  able to destroy their retained evidence), and ``get_run_evidence`` using the
  same strict restore as ``status``;
* raw ``sqlite3`` faults surfacing as ``LocalStoreError`` / ``store_error``;
* stream-path method routing, ``OPTIONS`` advertising, and ``retryable`` on
  every overload / drain / too-many-streams 503.

Written without being run (develop-only pass): every expectation below was
derived by reading the code on disk.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh import product_spine_run_store as psrs
from idkmesh.connector_store import (
    EVENT_AUTHORITY_CLASSES,
    EVENT_TYPES,
    LocalMetadataStore,
    LocalStoreConflict,
    LocalStoreError,
)
from idkmesh.control_tower_api import status_document
from idkmesh.product_spine_run_store import (
    ProductSpineRunStore,
    ProductSpineRunStoreError,
)


def _load_sibling(name: str):
    """Import a sibling test module by path (``tests/`` is not a package)."""
    key = f"_sibling_{name}"
    if key in sys.modules:
        return sys.modules[key]
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


_evidence = _load_sibling("test_run_evidence_store")
_events = _load_sibling("test_control_tower_events")

CREATED = _evidence.CREATED
seed_offline_run = _evidence.seed_offline_run
cli_run = _evidence.cli_run
rewrite_metadata = _evidence.rewrite_metadata
wait_until = _events.wait_until
EVENTS = _events.EVENTS
STREAM = _events.STREAM

RUN = "run/cli-1"
GARBAGE = b"this is not a sqlite database" * 64


def store_event(run_id: str = "run-1", **overrides) -> dict:
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


def cancelled_event(run_id: str) -> dict:
    return store_event(
        run_id,
        event_type="run.cancelled",
        payload={"previous_state": "proposed", "state": "cancelled"},
    )


class _DbCase(unittest.TestCase):
    """A fresh SQLite store with its service."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-review-fixes-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "state.sqlite"
        self.store = LocalMetadataStore(self.db)
        self.service = ProductSpineRunStore(self.store)

    def admit(self, run_id: str = "run-1", *, event=None):
        """A raw (non Product Spine shaped) admission, as the store tests do."""
        return self.store.admit_run(
            run_id=run_id,
            idempotency_key=f"key:{run_id}",
            request_digest="sha256:same",
            state="proposed",
            metadata={"run_id": run_id, "projection": {"project_id": "project.test"}},
            created_at=CREATED,
            event=event,
        )

    def create_cli_run(self, run_id: str = RUN):
        return self.service.create(
            cli_run(run_id), idempotency_key=f"k-{run_id}", created_at=CREATED
        )

    def all_events(self, **filters) -> list[dict]:
        page, more = self.store.list_events(limit=200, **filters)
        self.assertFalse(more)
        return page

    def corrupt_database(self) -> None:
        self.db.write_bytes(GARBAGE)


class EventVocabularyTests(unittest.TestCase):
    def test_the_service_reexports_the_single_store_vocabulary(self) -> None:
        self.assertEqual(EVENT_TYPES, {"run.created", "run.cancelled"})
        self.assertEqual(
            EVENT_AUTHORITY_CLASSES,
            {
                "local_control",
                "worker_observation",
                "verifier_recommendation",
                "human_decision",
            },
        )
        # One source of truth: the service must not keep a diverging copy.
        self.assertIs(psrs.EVENT_TYPES, EVENT_TYPES)
        self.assertIs(psrs.EVENT_AUTHORITY_CLASSES, EVENT_AUTHORITY_CLASSES)


class EventCursorAndFilterTests(_DbCase):
    def setUp(self) -> None:
        super().setUp()
        self.create_cli_run()

    def forged(self, after: str) -> str:
        return psrs._encode_cursor(after, psrs._EVENT_CURSOR_KIND)

    def test_a_forged_event_cursor_with_a_bad_payload_is_invalid_cursor(self) -> None:
        for after in (
            "²",  # superscript two: str.isdigit() is True, int() raises
            "٣",  # Arabic-Indic three: isdecimal() but not ASCII
            "9" * 19,  # would overflow SQLite's signed 64-bit bind
            "",
            "-5",
            "1.5",
            " 7",
            "1e3",
        ):
            with self.subTest(after=after):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.service.list_events(cursor=self.forged(after))
                self.assertEqual(caught.exception.code, "invalid_cursor")

    def test_a_cursor_of_another_listing_is_invalid_cursor(self) -> None:
        run_cursor = psrs._encode_cursor("run/cli-1")  # the run-list kind
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.list_events(cursor=run_cursor)
        self.assertEqual(caught.exception.code, "invalid_cursor")

    def test_a_well_formed_forged_cursor_is_still_accepted(self) -> None:
        events, next_cursor = self.service.list_events(cursor=self.forged("0"))
        self.assertEqual([e["sequence"] for e in events], [1])
        self.assertIsNone(next_cursor)
        past_the_end, _ = self.service.list_events(cursor=self.forged("9" * 18))
        self.assertEqual(past_the_end, [])

    def test_blank_filters_are_invalid_filter_not_invalid_limit(self) -> None:
        for name in ("project_id", "run_id", "work_unit_id"):
            with self.subTest(filter=name, call="list_events"):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.service.list_events(**{name: ""})
                self.assertEqual(caught.exception.code, "invalid_filter")
            with self.subTest(filter=name, call="events_after"):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    self.service.events_after(0, **{name: ""})
                self.assertEqual(caught.exception.code, "invalid_filter")

    def test_a_blank_event_type_stays_invalid_event_type(self) -> None:
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.list_events(event_type="")
        self.assertEqual(caught.exception.code, "invalid_event_type")

    def test_an_out_of_range_limit_is_still_invalid_limit(self) -> None:
        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.list_events(limit=0)
        self.assertEqual(caught.exception.code, "invalid_limit")


class ConditionalUpdateAndCancelRaceTests(_DbCase):
    def test_a_conditional_update_conflicts_when_the_state_moved(self) -> None:
        self.create_cli_run()
        self.service.cancel(RUN, updated_at="2026-10-02T00:05:00Z")
        before = self.store.get_run(RUN)
        sequence_before = self.store.latest_event_sequence()
        self.assertEqual(sequence_before, 2)

        with self.assertRaises(LocalStoreConflict):
            self.store.update_run(
                RUN,
                state="cancelled",
                metadata={"kind": "would-overwrite"},
                updated_at="2026-10-02T00:06:00Z",
                event=cancelled_event(RUN),
                expected_state="proposed",
            )

        after = self.store.get_run(RUN)
        self.assertEqual(after.metadata, before.metadata)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(self.store.latest_event_sequence(), sequence_before)
        self.assertEqual(
            len(self.all_events(run_id=RUN, event_type="run.cancelled")), 1
        )

    def test_a_conditional_update_applies_when_the_state_matches(self) -> None:
        self.admit("run-1")

        record = self.store.update_run(
            "run-1",
            state="cancelled",
            metadata={"run_id": "run-1"},
            updated_at=CREATED,
            event=cancelled_event("run-1"),
            expected_state="proposed",
        )

        self.assertEqual(record.state, "cancelled")
        (event,) = self.all_events()
        self.assertEqual(event["event_type"], "run.cancelled")
        self.assertEqual(event["sequence"], 1)

    def test_an_unknown_run_is_a_store_error_not_a_conflict(self) -> None:
        with self.assertRaises(LocalStoreError) as caught:
            self.store.update_run(
                "run/missing",
                state="cancelled",
                metadata={},
                updated_at=CREATED,
                expected_state="proposed",
            )
        self.assertNotIsInstance(caught.exception, LocalStoreConflict)
        self.assertIn("unknown run_id", str(caught.exception))

    def test_a_cancel_that_loses_to_another_cancel_returns_it_and_emits_nothing(
        self,
    ) -> None:
        self.create_cli_run()
        rival = ProductSpineRunStore(LocalMetadataStore(self.db))

        def racing(*args, **kwargs):
            rival.cancel(RUN, updated_at="2026-10-02T00:01:00Z")
            raise LocalStoreConflict("raced")

        with mock.patch.object(self.store, "update_run", side_effect=racing):
            result = self.service.cancel(RUN, updated_at="2026-10-02T00:02:00Z")

        self.assertEqual(result.run.state, "cancelled")
        cancelled = self.all_events(run_id=RUN, event_type="run.cancelled")
        self.assertEqual(len(cancelled), 1, "the loser must not emit a second event")
        self.assertEqual(cancelled[0]["occurred_at"], "2026-10-02T00:01:00Z")
        self.assertEqual(self.store.latest_event_sequence(), 2)

    def test_a_cancel_that_loses_to_another_transition_is_cancel_conflict(
        self,
    ) -> None:
        self.create_cli_run()
        rival_store = LocalMetadataStore(self.db)
        rival = ProductSpineRunStore(rival_store)

        def racing(*args, **kwargs):
            persisted = rival.status(RUN)
            moved = persisted.run.transition("previewed")
            rival_store.update_run(
                RUN,
                state=moved.state,
                metadata=psrs._metadata(
                    moved, create_request_digest=persisted.create_request_digest
                ),
                updated_at="2026-10-02T00:01:00Z",
            )
            raise LocalStoreConflict("raced")

        with mock.patch.object(self.store, "update_run", side_effect=racing):
            with self.assertRaises(ProductSpineRunStoreError) as caught:
                self.service.cancel(RUN, updated_at="2026-10-02T00:02:00Z")

        self.assertEqual(caught.exception.code, "cancel_conflict")
        self.assertIn("previewed", str(caught.exception))
        self.assertEqual(
            self.all_events(run_id=RUN, event_type="run.cancelled"), []
        )


class EventEnvelopeEnforcementTests(_DbCase):
    BAD = (
        ("event_type", "run.exploded"),
        ("event_type", "run.created\nid: 999"),
        ("authority_class", "root"),
        ("occurred_at", "2026-10-01 00:00:00"),
        ("occurred_at", "2026-10-01T00:00:00+00:00"),
        ("occurred_at", "2026-10-01T00:00:00"),
        ("source_revision", "xyz"),
        ("source_revision", "0" * 39),
        ("source_revision", "g" * 40),
        ("run_id", "run-other"),
    )

    def test_admit_rejects_an_invalid_envelope_and_writes_nothing(self) -> None:
        for field, value in self.BAD:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.admit("run-1", event=store_event("run-1", **{field: value}))
                self.assertIsNone(self.store.get_run("run-1"))
                self.assertEqual(self.store.latest_event_sequence(), 0)
                self.assertEqual(self.all_events(), [])

    def test_update_rejects_an_invalid_envelope_and_changes_nothing(self) -> None:
        self.admit("run-1", event=store_event("run-1"))
        before = self.store.get_run("run-1")
        self.assertEqual(self.store.latest_event_sequence(), 1)

        for field, value in self.BAD:
            with self.subTest(field=field, value=value):
                bad = (
                    store_event("run-other")
                    if field == "run_id"
                    else store_event("run-1", **{field: value})
                )
                with self.assertRaises(ValueError):
                    self.store.update_run(
                        "run-1",
                        state="cancelled",
                        metadata={"run_id": "run-1"},
                        updated_at=CREATED,
                        event=bad,
                    )
                after = self.store.get_run("run-1")
                self.assertEqual(after.state, "proposed")
                self.assertEqual(after.metadata, before.metadata)
                self.assertEqual(self.store.latest_event_sequence(), 1)

    def test_the_valid_edges_of_the_envelope_are_still_accepted(self) -> None:
        self.admit("run-a", event=store_event("run-a", source_revision=None))
        self.admit("run-b", event=store_event("run-b", source_revision="a" * 64))
        self.admit(
            "run-c",
            event=store_event("run-c", occurred_at="2026-10-01T00:00:00.123Z"),
        )
        self.assertEqual(
            [e["sequence"] for e in self.all_events()], [1, 2, 3]
        )


class RollbackAfterWriteTests(_DbCase):
    def test_a_failure_after_the_run_insert_leaves_neither_run_nor_event(self) -> None:
        with mock.patch.object(
            LocalMetadataStore, "_append_event", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.admit("run-1", event=store_event("run-1"))

        self.assertIsNone(self.store.get_run("run-1"))
        self.assertEqual(self.store.latest_event_sequence(), 0)

        # The idempotency reservation rolled back with it, and the sequence
        # has no gap: the retry is a fresh admission with sequence 1.
        record, created = self.admit("run-1", event=store_event("run-1"))
        self.assertTrue(created)
        (event,) = self.all_events()
        self.assertEqual(event["sequence"], 1)
        self.assertEqual(event["event_id"], "evt-000000000001")

    def test_a_failure_after_the_update_leaves_state_and_stream_unchanged(self) -> None:
        self.admit("run-1")
        before = self.store.get_run("run-1")

        with mock.patch.object(
            LocalMetadataStore, "_append_event", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.store.update_run(
                    "run-1",
                    state="cancelled",
                    metadata={"run_id": "run-1", "changed": True},
                    updated_at="2026-10-02T00:09:00Z",
                    event=cancelled_event("run-1"),
                )

        after = self.store.get_run("run-1")
        self.assertEqual(after.state, "proposed")
        self.assertEqual(after.metadata, before.metadata)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(self.store.latest_event_sequence(), 0)

        self.store.update_run(
            "run-1",
            state="cancelled",
            metadata={"run_id": "run-1"},
            updated_at=CREATED,
            event=cancelled_event("run-1"),
        )
        (event,) = self.all_events()
        self.assertEqual(event["sequence"], 1)


class OfflineSpineProtectionTests(_DbCase):
    def setUp(self) -> None:
        super().setUp()
        self.result = seed_offline_run(self.db, self.root)
        self.run_id = self.result.run.run_id

    def test_cancel_refuses_an_offline_run_and_leaves_its_row_untouched(self) -> None:
        before = self.store.get_run(self.run_id)
        self.assertIn("evidence_report", before.metadata)
        before_json = json.dumps(before.metadata, sort_keys=True)
        sequence_before = self.store.latest_event_sequence()

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.cancel(self.run_id, updated_at="2026-10-02T00:09:00Z")

        self.assertEqual(caught.exception.code, "cancel_not_allowed")
        after = self.store.get_run(self.run_id)
        self.assertEqual(json.dumps(after.metadata, sort_keys=True), before_json)
        self.assertEqual(after.state, before.state)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(self.store.latest_event_sequence(), sequence_before)
        # The retained evidence is still served, so nothing was destroyed.
        served = self.service.get_run_evidence(self.run_id)
        self.assertEqual(served["evidence_report"], self.result.evidence_report)

    def test_the_offline_run_is_still_readable_through_status_and_list(self) -> None:
        self.assertEqual(self.service.status(self.run_id).run.run_id, self.run_id)
        runs, _ = self.service.list()
        self.assertEqual([run.run_id for run in runs], [self.run_id])

    def test_a_foreign_kind_with_a_valid_projection_is_not_a_run(self) -> None:
        rewrite_metadata(
            self.db,
            self.run_id,
            lambda metadata: metadata.__setitem__(
                "kind", "github-explicit-dispatch-result"
            ),
        )

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(self.run_id)

        self.assertEqual(caught.exception.code, "run_not_found")
        runs, _ = self.service.list()
        self.assertEqual(runs, [])

    def test_a_projection_swapped_from_another_run_is_an_integrity_error(self) -> None:
        rewrite_metadata(
            self.db,
            self.run_id,
            lambda metadata: metadata["projection"].__setitem__(
                "run_id", "run/someone-else"
            ),
        )

        with self.assertRaises(ProductSpineRunStoreError) as caught:
            self.service.get_run_evidence(self.run_id)

        self.assertEqual(caught.exception.code, "evidence_integrity_error")


class StoreFaultTests(_DbCase):
    def test_store_methods_raise_localstoreerror_not_sqlite_errors(self) -> None:
        self.corrupt_database()
        calls = {
            "list_runs": self.store.list_runs,
            "list_events": self.store.list_events,
            "latest_event_sequence": self.store.latest_event_sequence,
            "get_run": lambda: self.store.get_run("run-1"),
            "list_work_units": self.store.list_work_units,
            "get_project_counts": lambda: self.store.get_project_counts("p"),
        }
        for name, call in calls.items():
            with self.subTest(call=name):
                with self.assertRaises(LocalStoreError):
                    call()

    def test_admit_and_update_wrap_database_errors(self) -> None:
        self.admit("run-1")
        self.corrupt_database()

        with self.assertRaises(LocalStoreError):
            self.admit("run-2")
        with self.assertRaises(LocalStoreError):
            self.store.update_run(
                "run-1", state="cancelled", metadata={}, updated_at=CREATED
            )

    def test_constructing_a_store_on_a_corrupt_file_raises_localstoreerror(self) -> None:
        self.corrupt_database()
        with self.assertRaises(LocalStoreError):
            LocalMetadataStore(self.db)

    def test_the_service_maps_store_faults_to_store_error(self) -> None:
        self.corrupt_database()
        calls = {
            "list_events": self.service.list_events,
            "latest_event_sequence": self.service.latest_event_sequence,
            "get_run_evidence": lambda: self.service.get_run_evidence("run-1"),
        }
        for name, call in calls.items():
            with self.subTest(call=name):
                with self.assertRaises(ProductSpineRunStoreError) as caught:
                    call()
                self.assertEqual(caught.exception.code, "store_error")


class EventHttpFaultAndRoutingTests(_events._EventCase):
    """HTTP behaviour fixed by the review; reuses the events test fixtures."""

    def test_a_corrupt_store_answers_500_store_error_not_a_dropped_connection(
        self,
    ) -> None:
        server = self.start()
        Path(self.store_path).write_bytes(GARBAGE)

        status, _, body = self.request(server, EVENTS)

        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"]["code"], "store_error")
        wait_until(lambda: server.limiter.in_flight == 0)

    def test_the_run_listing_already_answers_500_on_a_corrupt_store(self) -> None:
        server = self.start()
        Path(self.store_path).write_bytes(GARBAGE)

        status, _, body = self.request(server, "/api/v1/runs")

        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"]["code"], "store_error")

    def test_options_on_the_stream_path_advertises_get_only(self) -> None:
        server = self.start()

        status, headers, _ = self.request(server, STREAM, method="OPTIONS")

        self.assertEqual(status, 405)
        self.assertEqual(headers.get("Allow"), "GET")

    def test_head_and_post_on_the_stream_path_are_405_even_when_streams_are_full(
        self,
    ) -> None:
        server = self.start(max_sse_clients=1)
        self.stream(server, last_event_id=5)
        wait_until(lambda: server.sse_limiter.in_flight == 1)

        for method in ("HEAD", "POST"):
            with self.subTest(method=method):
                status, _, _ = self.request(
                    server,
                    STREAM,
                    method=method,
                    headers={"Accept": "text/event-stream"},
                )
                self.assertEqual(status, 405)

        # Only a real stream request is refused for lack of a stream slot.
        status, headers, body = self.request(
            server, STREAM, headers={"Accept": "text/event-stream"}
        )
        document = json.loads(body)
        self.assertEqual(status, 503)
        self.assertIn("Retry-After", headers)
        self.assertEqual(document["error"]["code"], "too_many_streams")
        self.assertIs(document["error"]["retryable"], True)
        self.assertEqual(server.sse_limiter.in_flight, 1)

    def test_an_overload_503_is_marked_retryable(self) -> None:
        server = self.start(max_concurrent_requests=1)
        release = threading.Event()
        real = status_document

        def blocked(*args, **kwargs):
            release.wait(10)
            return real(*args, **kwargs)

        patcher = mock.patch("idkmesh.control_tower_ui.status_document", blocked)
        patcher.start()
        holder = threading.Thread(
            target=lambda: self.request(server, "/api/v1/status")
        )
        # Cleanups run last-in first: release the handler, join, then unpatch.
        self.addCleanup(patcher.stop)
        self.addCleanup(holder.join, 5)
        self.addCleanup(release.set)
        holder.start()
        wait_until(lambda: server.limiter.in_flight == 1)

        status, headers, body = self.request(server, EVENTS)
        document = json.loads(body)

        self.assertEqual(status, 503)
        self.assertIn("Retry-After", headers)
        self.assertEqual(document["error"]["code"], "overloaded")
        self.assertIs(document["error"]["retryable"], True)
        release.set()

    def test_a_draining_503_is_marked_retryable(self) -> None:
        server = self.start()
        server.limiter.begin_drain()

        status, headers, body = self.request(server, EVENTS)
        document = json.loads(body)

        self.assertEqual(status, 503)
        self.assertIn("Retry-After", headers)
        self.assertEqual(document["error"]["code"], "shutting_down")
        self.assertIs(document["error"]["retryable"], True)


if __name__ == "__main__":
    unittest.main()
