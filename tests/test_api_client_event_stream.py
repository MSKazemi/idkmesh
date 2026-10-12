"""The Python client's bounded Server-Sent Events helper (#746).

``ControlTowerClient.stream_events`` is exercised against a real in-process
``create_server`` for everything the server can actually say (ordering, resume,
filters, auth and capacity errors, drain, slot release). Byte-level protocol
violations a correct server never sends are produced by a tiny scripted TCP
peer, because the real handler cannot be told to misbehave.

Teardown follows ``tests/test_control_tower_events.py``: ``server.drain()``
before ``shutdown()``, and the SSE slot is awaited with ``wait_idle`` while the
test keeps producing events, because the server only notices a departed peer
when it writes. Class-based on purpose: ``tests/test_documented_test_counts.py``
counts module-level ``test_*`` functions. Standard library plus ``jsonschema``.
"""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from idkmesh.api_client import (
    ApiResponseError,
    ClientConfigurationError,
    ControlTowerClient,
    EventStream,
    IntegrityError,
    ProtocolError,
    StreamedEvent,
    TransportError,
)
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import create_server
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore

SHA = "0123456789abcdef0123456789abcdef01234567"
SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
EVENT_SCHEMA = json.loads(
    (SCHEMAS / "idkmesh-event-v0.1.schema.json").read_text(encoding="utf-8")
)
IDLE = 5.0


def _run(run_id: str, project_id: str, work_unit_id: str) -> ProductSpineRun:
    return ProductSpineRun(
        run_id=run_id,
        request_digest="sha256:" + "a" * 64,
        project_id=project_id,
        work_unit_id=work_unit_id,
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="c1-v0.1",
        state="proposed",
    )


def wait_until(predicate, *, timeout: float = 10.0, interval: float = 0.05):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise AssertionError("condition not met before the deadline")
        time.sleep(interval)


class _LiveServerCase(unittest.TestCase):
    """A fresh store with five events (seq 1-4 created, seq 5 cancelled)."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store_path = str(Path(tmp.name) / "product-spine.sqlite3")
        self.service = ProductSpineRunStore(LocalMetadataStore(self.store_path))
        self._live = 0
        for second, (run_id, project, unit) in enumerate(
            [
                ("run/e-1", "project.alpha", "work/a"),
                ("run/e-2", "project.alpha", "work/b"),
                ("run/e-3", "project.beta", "work/a"),
                ("run/e-4", "project.alpha", "work/a"),
            ],
            start=1,
        ):
            self.service.create(
                _run(run_id, project, unit),
                idempotency_key=f"seed-{run_id}",
                created_at=f"2026-10-01T00:00:{second:02d}Z",
            )
        self.service.cancel("run/e-2", updated_at="2026-10-01T00:30:00Z")
        self.assertEqual(self.service.latest_event_sequence(), 5)

    def append_run(self) -> int:
        self._live += 1
        run_id = f"run/live-{self._live}"
        self.service.create(
            _run(run_id, "project.alpha", "work/a"),
            idempotency_key=f"live-{run_id}",
            created_at=f"2026-10-02T00:00:{self._live:02d}Z",
        )
        return self.service.latest_event_sequence()

    def start(self, **kwargs):
        server = create_server(
            port=0, product_spine_store_path=self.store_path, **kwargs
        )
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        thread.start()

        def stop() -> None:
            # Open streams outlive shutdown(); drain() wakes and ends them
            # before the temp directory under their store disappears.
            server.drain(timeout=5.0)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)
        return server, self.client_for(server)

    @staticmethod
    def client_for(server, token: str | None = None) -> ControlTowerClient:
        return ControlTowerClient(
            f"http://127.0.0.1:{server.server_port}",
            token or server.ui_token,
            timeout=2.0,
        )

    def open(self, client, **kwargs) -> EventStream:
        kwargs.setdefault("idle_timeout", IDLE)
        stream = client.stream_events(**kwargs)
        self.addCleanup(stream.close)
        return stream


class StreamAgainstLiveServerTests(_LiveServerCase):
    def test_backlog_arrives_in_order_with_validated_envelopes(self) -> None:
        _server, client = self.start()
        with self.open(client, last_event_id=0, max_events=5) as stream:
            events = list(stream)

        self.assertEqual([e.sequence for e in events], [1, 2, 3, 4, 5])
        self.assertTrue(all(isinstance(e, StreamedEvent) for e in events))
        self.assertEqual(events[-1].event_type, "run.cancelled")
        for item in events:
            Draft202012Validator(EVENT_SCHEMA).validate(item.event)
            self.assertEqual(item.event["sequence"], item.sequence)
            self.assertEqual(item.event["event_type"], item.event_type)
        self.assertEqual(stream.last_event_id, 5)
        self.assertEqual(stream.end_reason, "client-max-events")
        self.assertEqual(stream.retry_ms, 3000)
        self.assertRegex(stream.request_id, r"^req_")

    def test_it_follows_live_events_after_the_connection_is_open(self) -> None:
        _server, client = self.start()
        with self.open(client) as stream:  # no cursor: live tail only
            head = self.append_run()
            first = next(stream)
            self.assertEqual(first.sequence, head)
            self.assertEqual(first.event["run_id"], "run/live-1")
            head = self.append_run()
            self.assertEqual(next(stream).sequence, head)

    def test_resuming_with_last_event_id_replays_only_what_follows(self) -> None:
        _server, client = self.start()
        with self.open(client, last_event_id=3, max_events=2) as stream:
            self.assertEqual([e.sequence for e in stream], [4, 5])
        with self.open(client, last_event_id=5) as stream:
            head = self.append_run()
            self.assertEqual(next(stream).sequence, head)

    def test_filters_narrow_the_stream_and_are_checked_on_receipt(self) -> None:
        _server, client = self.start()
        with self.open(
            client, last_event_id=0, project_id="project.alpha", max_events=4
        ) as stream:
            self.assertEqual(
                [e.event["project_id"] for e in stream], ["project.alpha"] * 4
            )
        with self.open(
            client, last_event_id=0, event_type="run.cancelled", max_events=1
        ) as stream:
            only = list(stream)
        self.assertEqual([e.sequence for e in only], [5])

    def test_a_wrong_token_raises_the_existing_auth_error_without_the_token(
        self,
    ) -> None:
        server, _good = self.start()
        token = "w" * 40
        client = self.client_for(server, token)
        with self.assertRaises(ApiResponseError) as caught:
            client.stream_events(idle_timeout=IDLE)
        error = caught.exception
        self.assertEqual(error.status_code, 403)
        self.assertRegex(error.request_id, r"^req_")
        self.assertNotIn(token, str(error))
        self.assertNotIn(token, repr(error))
        self.assertNotIn(token, repr(error.details))

    def test_errors_sent_before_streaming_keep_the_error_taxonomy(self) -> None:
        _server, client = self.start()
        with self.assertRaises(ApiResponseError) as beyond:
            client.stream_events(idle_timeout=IDLE, last_event_id=99)
        self.assertEqual(beyond.exception.code, "invalid_last_event_id")
        self.assertEqual(beyond.exception.details["latest_sequence"], 5)
        with self.assertRaises(ApiResponseError) as bad_type:
            client.stream_events(idle_timeout=IDLE, event_type="no.such.event")
        self.assertEqual(bad_type.exception.code, "invalid_event_type")

    def test_arguments_are_validated_before_any_network_io(self) -> None:
        client = ControlTowerClient(
            "http://127.0.0.1:1", "t" * 32, timeout=1.0
        )
        with self.assertRaises(TypeError):
            client.stream_events()  # idle_timeout is mandatory
        bad_cases = (
            {"idle_timeout": 0},
            {"idle_timeout": True},
            {"idle_timeout": float("nan")},
            {"idle_timeout": 1, "max_seconds": -1},
            {"idle_timeout": 1, "last_event_id": -1},
            {"idle_timeout": 1, "last_event_id": 10**18},
            {"idle_timeout": 1, "last_event_id": "7"},
            {"idle_timeout": 1, "max_events": 0},
            {"idle_timeout": 1, "max_frame_bytes": 10},
            {"idle_timeout": 1, "run_id": "bad\nid"},
            {"idle_timeout": 1, "project_id": ""},
        )
        with mock.patch("http.client.HTTPConnection") as connection:
            for kwargs in bad_cases:
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ClientConfigurationError):
                        client.stream_events(**kwargs)
        connection.assert_not_called()

    def test_an_unreachable_server_is_a_transport_error_after_one_attempt(
        self,
    ) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        client = ControlTowerClient(
            f"http://127.0.0.1:{port}", "t" * 40, timeout=1.0
        )
        with mock.patch(
            "idkmesh.api_client.http.client.HTTPConnection",
            wraps=http.client.HTTPConnection,
        ) as connection:
            with self.assertRaises(TransportError) as caught:
                client.stream_events(idle_timeout=IDLE)
        self.assertEqual(connection.call_count, 1)
        self.assertNotIn("t" * 40, str(caught.exception))

    def test_a_drained_server_ends_the_stream_with_its_shutdown_marker(
        self,
    ) -> None:
        server, client = self.start()
        with self.open(client) as stream:
            wait_until(lambda: server.sse_limiter.in_flight == 1)
            self.assertTrue(server.drain(timeout=5.0))
            self.assertEqual(list(stream), [])
            self.assertEqual(stream.end_reason, "shutdown")

    def test_closing_early_frees_the_server_slot_for_the_next_stream(self) -> None:
        server, client = self.start(max_sse_clients=1)
        first = self.open(client, last_event_id=0)
        self.assertEqual(next(first).sequence, 1)
        wait_until(lambda: server.sse_limiter.in_flight == 1)

        with self.assertRaises(ApiResponseError) as full:
            client.stream_events(idle_timeout=IDLE)
        self.assertEqual(full.exception.code, "too_many_streams")
        self.assertEqual(full.exception.status_code, 503)
        self.assertTrue(full.exception.retryable)

        first.close()
        first.close()  # idempotent
        self.assertEqual(list(first), [])
        # The server notices a departed peer only when it writes, so keep
        # producing events until the slot is released.
        wait_until(
            lambda: server.sse_limiter.wait_idle(0.05)
            or (self.append_run() and False)
        )
        with self.open(client, last_event_id=0, max_events=1) as second:
            self.assertEqual([e.sequence for e in second], [1])

    def test_leaving_the_with_block_mid_stream_closes_the_connection(self) -> None:
        server, client = self.start(max_sse_clients=1)
        with self.open(client, last_event_id=0) as stream:
            next(stream)
        with self.assertRaises(StopIteration):
            next(stream)
        wait_until(
            lambda: server.sse_limiter.wait_idle(0.05)
            or (self.append_run() and False)
        )


class StreamedEventIntegrityTests(_LiveServerCase):
    """Real server, real frames, one field tampered in the store's reply."""

    def tamper_with(self, mutate):
        """Patch the store's reply so ``mutate(event)`` is what gets framed."""
        self.mutation = mutate
        if getattr(self, "_patched", False):
            return
        self._patched = True
        original = ProductSpineRunStore.events_after

        def tampered(service, after, **kw):
            return [
                self.mutation(dict(event))
                for event in original(service, after, **kw)
            ]

        patcher = mock.patch.object(ProductSpineRunStore, "events_after", tampered)
        patcher.start()
        self.addCleanup(patcher.stop)

    def open_tampered(self, mutate, **kwargs):
        self.tamper_with(mutate)
        if not hasattr(self, "client"):
            _server, self.client = self.start()
        return self.open(self.client, last_event_id=0, **kwargs)

    def test_a_payload_that_does_not_match_its_digest_is_an_integrity_error(
        self,
    ) -> None:
        stream = self.open_tampered(
            lambda e: {**e, "payload": {**e["payload"], "tampered": True}}
        )
        with self.assertRaises(IntegrityError):
            next(stream)
        self.assertEqual(list(stream), [])  # failed streams close themselves

    def test_an_envelope_outside_the_schema_fails_closed(self) -> None:
        for name, mutate in (
            ("extra key", lambda e: {**e, "surprise": 1}),
            ("wrong kind", lambda e: {**e, "kind": "idkmesh-other"}),
            ("wrong schema version", lambda e: {**e, "schema_version": "9.9"}),
            ("bad event id", lambda e: {**e, "event_id": "evt-1"}),
        ):
            with self.subTest(name):
                stream = self.open_tampered(mutate)
                with self.assertRaises(ProtocolError):
                    next(stream)

    def test_an_event_outside_the_requested_filter_is_a_protocol_error(self) -> None:
        stream = self.open_tampered(
            lambda e: {**e, "project_id": "project.elsewhere"},
            project_id="project.alpha",
        )
        with self.assertRaises(ProtocolError) as caught:
            next(stream)
        self.assertIn("project_id", str(caught.exception))

    def test_a_repeated_or_older_sequence_is_a_protocol_error(self) -> None:
        original = ProductSpineRunStore.events_after

        def replay(service, after, **kw):
            events = original(service, after, **kw)
            return events[:1] + events[:1] if events else events

        with mock.patch.object(ProductSpineRunStore, "events_after", replay):
            _server, client = self.start()
            stream = self.open(client, last_event_id=0)
            self.assertEqual(next(stream).sequence, 1)
            with self.assertRaises(ProtocolError):
                next(stream)

    def test_an_oversize_frame_is_bounded_not_buffered(self) -> None:
        _server, client = self.start()
        stream = self.open(client, last_event_id=0, max_frame_bytes=256)
        with self.assertRaises(ProtocolError) as caught:
            next(stream)
        self.assertIn("256", str(caught.exception))
        self.assertEqual(list(stream), [])


class _ScriptedPeer:
    """A one-shot TCP peer that answers any request with canned bytes."""

    def __init__(self, test: unittest.TestCase, body: bytes, *, hold: float = 0.0):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.connections = 0
        self._body = body
        self._hold = hold
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        test.addCleanup(self.close)

    def _serve(self) -> None:
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        self.connections += 1
        with conn:
            conn.settimeout(2.0)
            try:
                buffer = b""
                while b"\r\n\r\n" not in buffer:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buffer += chunk
                conn.sendall(self._body)
                if self._hold:
                    self._stop.wait(self._hold)  # bounded stall for timeout tests
            except OSError:
                return

    def close(self) -> None:
        self._stop.set()
        self.sock.close()
        self._thread.join(timeout=3)


def _head(status: str = "200 OK", content_type: str = "text/event-stream") -> bytes:
    return (
        f"HTTP/1.0 {status}\r\n"
        f"Content-Type: {content_type}\r\n"
        "X-Request-ID: req_scripted\r\n\r\n"
    ).encode("ascii")


class ScriptedPeerTests(unittest.TestCase):
    """Protocol violations a correct server never sends all fail closed."""

    def stream(self, body: bytes, *, head: bytes | None = None, hold=0.0, **kw):
        peer = _ScriptedPeer(self, (head if head is not None else _head()) + body, hold=hold)
        client = ControlTowerClient(
            f"http://127.0.0.1:{peer.port}", "t" * 40, timeout=2.0
        )
        kw.setdefault("idle_timeout", 2.0)
        stream = client.stream_events(**kw)
        self.addCleanup(stream.close)
        return stream, peer

    @staticmethod
    def frame(sequence: int = 1, **overrides) -> bytes:
        payload = {"k": "v"}
        from idkmesh.work_unit_binding import canonical_digest

        envelope = {
            "schema_version": "0.1",
            "kind": "idkmesh-event",
            "event_id": f"evt-{sequence:012d}",
            "sequence": sequence,
            "occurred_at": "2026-10-01T00:00:00Z",
            "event_type": "run.created",
            "principal": {"type": "local", "id": "x"},
            "authority_class": "local_control",
            "project_id": "p",
            "work_unit_id": "w",
            "run_id": "r",
            "attempt_id": None,
            "source_revision": SHA,
            "evidence_reference": None,
            "payload": payload,
            "payload_digest": canonical_digest(payload),
        }
        envelope.update(overrides)
        data = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        return f"id: {sequence}\nevent: run.created\ndata: {data}\n\n".encode()

    def test_a_well_formed_scripted_stream_parses(self) -> None:
        stream, _ = self.stream(
            b"retry: 3000\n\n" + self.frame(1) + b": keepalive\n\n" + self.frame(2)
            + b": stream-ended reason=max-duration\n\n"
        )
        self.assertEqual([e.sequence for e in stream], [1, 2])
        self.assertEqual(stream.end_reason, "max-duration")

    def test_malformed_frames_raise_protocol_error(self) -> None:
        good = self.frame(1)
        cases = {
            "bad json": b"id: 1\nevent: run.created\ndata: {not json}\n\n",
            "duplicate field": good.replace(
                b"event: run.created\n",
                b"event: run.created\nevent: run.created\n",
                1,
            ),
            "unknown field": good.replace(b"event:", b"evnt:", 1),
            "no colon": b"garbage\n\n",
            "missing data": b"id: 1\nevent: run.created\n\n",
            "id not a number": good.replace(b"id: 1", b"id: one", 1),
            "event name mismatch": good.replace(b"event: run.created", b"event: run.cancelled", 1),
            "unknown comment": b": surprise\n\n",
            "multi-line comment": b": keepalive\n: keepalive\n\n",
            "empty frame": b"\n",
            "bad retry": b"retry: soon\n\n",
            "retry with event": b"retry: 3000\n" + good,
            "carriage return": good.replace(b"\n", b"\r\n"),
            "not utf-8": b"id: 1\nevent: run.created\ndata: \xff\xfe\n\n",
            "duplicate-key json": b'id: 1\nevent: run.created\ndata: {"a":1,"a":2}\n\n',
            "data array": b"id: 1\nevent: run.created\ndata: []\n\n",
            "too many lines": b"".join(b": x\n" for _ in range(40)) + b"\n",
        }
        for name, body in cases.items():
            with self.subTest(name):
                stream, _ = self.stream(body)
                with self.assertRaises(ProtocolError):
                    next(stream)
                self.assertEqual(list(stream), [])

    def test_a_second_retry_hint_or_one_after_an_event_is_rejected(self) -> None:
        stream, _ = self.stream(self.frame(1) + b"retry: 3000\n\n")
        next(stream)
        with self.assertRaises(ProtocolError):
            next(stream)

    def test_truncation_is_distinguished_from_a_clean_drop(self) -> None:
        stream, _ = self.stream(self.frame(1)[:-1])  # lost the final blank line
        with self.assertRaises(ProtocolError):
            next(stream)
        stream, _ = self.stream(b"id: 1\nevent: run.created\ndata: {")  # mid-line
        with self.assertRaises(ProtocolError):
            next(stream)
        stream, _ = self.stream(self.frame(1))  # closes at a frame boundary
        self.assertEqual(next(stream).sequence, 1)
        with self.assertRaises(TransportError) as dropped:
            next(stream)
        self.assertIn("last_event_id=1", str(dropped.exception))

    def test_an_oversize_line_is_cut_off_at_the_bound(self) -> None:
        huge = b"data: " + b"x" * 2_000_000 + b"\n\n"
        stream, _ = self.stream(huge, max_frame_bytes=4096)
        with self.assertRaises(ProtocolError) as caught:
            next(stream)
        self.assertIn("4096", str(caught.exception))

    def test_a_frame_of_many_small_lines_hits_the_frame_bound(self) -> None:
        body = b"".join(b": " + b"y" * 60 + b"\n" for _ in range(15)) + b"\n"
        stream, _ = self.stream(body, max_frame_bytes=512)
        with self.assertRaises(ProtocolError) as caught:
            next(stream)
        self.assertIn("512", str(caught.exception))

    def test_wrong_status_media_type_or_request_id_is_a_protocol_error(self) -> None:
        for name, head in {
            "json instead of sse": _head(content_type="application/json"),
            "html": _head(content_type="text/html"),
            "no request id": b"HTTP/1.0 200 OK\r\nContent-Type: text/event-stream\r\n\r\n",
            "bad request id": b"HTTP/1.0 200 OK\r\nContent-Type: text/event-stream\r\nX-Request-ID: no good\r\n\r\n",
            "redirect": b"HTTP/1.0 302 Found\r\nLocation: http://example.com/\r\n\r\n",
            "no content": b"HTTP/1.0 204 No Content\r\nContent-Type: application/json\r\nX-Request-ID: req_x\r\n\r\n",
        }.items():
            with self.subTest(name):
                peer = _ScriptedPeer(self, head)
                client = ControlTowerClient(
                    f"http://127.0.0.1:{peer.port}", "t" * 40, timeout=2.0
                )
                with self.assertRaises(ProtocolError):
                    client.stream_events(idle_timeout=2.0)

    def test_an_error_status_without_the_envelope_is_a_protocol_error(self) -> None:
        peer = _ScriptedPeer(
            self,
            _head("500 Internal Server Error", "application/json") + b"{}",
        )
        client = ControlTowerClient(
            f"http://127.0.0.1:{peer.port}", "t" * 40, timeout=2.0
        )
        with self.assertRaises(ProtocolError):
            client.stream_events(idle_timeout=2.0)

    def test_a_stalled_stream_times_out_as_a_transport_error(self) -> None:
        stream, _ = self.stream(b"retry: 3000\n\n", hold=1.0, idle_timeout=0.15)
        started = time.monotonic()
        with self.assertRaises(TransportError) as caught:
            next(stream)
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertIn("idle", str(caught.exception))

    def test_the_client_side_lifetime_bound_ends_a_stalled_stream_cleanly(
        self,
    ) -> None:
        stream, _ = self.stream(
            b"retry: 3000\n\n", hold=1.0, idle_timeout=5.0, max_seconds=0.15
        )
        started = time.monotonic()
        self.assertEqual(list(stream), [])
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertEqual(stream.end_reason, "client-max-seconds")

    def test_exactly_one_connection_is_made_even_when_the_stream_drops(self) -> None:
        stream, peer = self.stream(self.frame(1))
        next(stream)
        with self.assertRaises(TransportError):
            next(stream)
        self.assertEqual(peer.connections, 1)


if __name__ == "__main__":
    unittest.main()
