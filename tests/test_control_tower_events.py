"""HTTP and SSE surface of the canonical event source (ADR-0023, #741).

Covers ``GET /api/v1/events`` and ``GET /api/v1/events/stream``. The SSE client
here is a small raw-socket reader with explicit deadlines: no test waits on a
long fixed sleep, and every wait is on a condition (a frame arriving, a limiter
slot being taken or released).
"""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from urllib.parse import quote

from jsonschema import Draft202012Validator

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import create_server
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore

SHA = "0123456789abcdef0123456789abcdef01234567"
STREAM = "/api/v1/events/stream"
EVENTS = "/api/v1/events"


def _schema(name: str) -> dict:
    root = Path(__file__).resolve().parents[1] / "schemas"
    schema = json.loads((root / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _validate(name: str, document: dict) -> None:
    Draft202012Validator(_schema(name)).validate(document)


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


def wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02):
    """Poll ``predicate`` until truthy; fail loudly rather than hang."""
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise AssertionError("condition not met before the deadline")
        time.sleep(interval)


class SSEClient:
    """Minimal raw-socket Server-Sent Events reader with deadlines."""

    def __init__(
        self,
        server,
        path: str = STREAM,
        *,
        last_event_id: int | str | None = None,
        token: bool = True,
        accept: str = "text/event-stream",
        timeout: float = 5.0,
    ) -> None:
        self._sock = socket.create_connection(
            ("127.0.0.1", server.server_port), timeout=timeout
        )
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: 127.0.0.1:{server.server_port}",
            f"Accept: {accept}",
        ]
        if token:
            lines.append(f"{TOKEN_HEADER}: {server.ui_token}")
        if last_event_id is not None:
            lines.append(f"Last-Event-ID: {last_event_id}")
        self._sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
        self._buffer = b""
        self.closed = False
        self.status, self.headers = self._read_head(timeout)

    def _recv(self, timeout: float) -> bool:
        """Read more bytes; False on timeout or end of stream."""
        if self.closed:
            return False
        self._sock.settimeout(max(timeout, 0.001))
        try:
            chunk = self._sock.recv(65536)
        except socket.timeout:
            return False
        except OSError:
            self.closed = True
            return False
        if not chunk:
            self.closed = True
            return False
        self._buffer += chunk
        return True

    def _read_head(self, timeout: float):
        deadline = time.monotonic() + timeout
        while b"\r\n\r\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or (not self._recv(remaining) and self.closed):
                raise AssertionError(
                    f"no response head; got {self._buffer[:80]!r}"
                )
        head, _, self._buffer = self._buffer.partition(b"\r\n\r\n")
        status_line, *header_lines = head.decode("latin-1").split("\r\n")
        headers = {}
        for line in header_lines:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        return int(status_line.split()[1]), headers

    @staticmethod
    def _parse(raw: str) -> dict:
        frame = {"id": None, "event": None, "data": None, "comment": None,
                 "retry": None}
        data_lines = []
        for line in raw.split("\n"):
            if line.startswith(":"):
                frame["comment"] = line[1:].strip()
            elif line.startswith("id:"):
                frame["id"] = line[3:].strip()
            elif line.startswith("event:"):
                frame["event"] = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip(" "))
            elif line.startswith("retry:"):
                frame["retry"] = line[6:].strip()
        if data_lines:
            frame["data"] = "\n".join(data_lines)
        return frame

    def next_frame(self, timeout: float = 5.0) -> dict | None:
        """The next complete frame (comments included), or None."""
        deadline = time.monotonic() + timeout
        while True:
            normalised = self._buffer.replace(b"\r\n", b"\n")
            if b"\n\n" in normalised:
                raw, _, rest = normalised.partition(b"\n\n")
                self._buffer = rest
                return self._parse(raw.decode("utf-8"))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            if not self._recv(remaining) and self.closed:
                # Flush a final unterminated frame, if any, then stop.
                if self._buffer.strip():
                    raw = self._buffer.decode("utf-8").replace("\r\n", "\n")
                    self._buffer = b""
                    return self._parse(raw)
                return None

    def next_event(self, timeout: float = 5.0) -> dict | None:
        """The next real event frame, skipping comments and retry hints."""
        deadline = time.monotonic() + timeout
        while True:
            frame = self.next_frame(max(deadline - time.monotonic(), 0.001))
            if frame is None:
                return None
            if frame["id"] is not None or frame["event"] is not None:
                return frame

    def read_events(self, count: int, timeout: float = 5.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        events = []
        while len(events) < count:
            event = self.next_event(max(deadline - time.monotonic(), 0.001))
            if event is None:
                raise AssertionError(
                    f"expected {count} events, got {len(events)}: {events}"
                )
            events.append(event)
        return events

    def drain_frames(self, timeout: float = 5.0) -> list[dict]:
        """Read every remaining frame until the server ends the stream."""
        deadline = time.monotonic() + timeout
        frames = []
        while not self.closed and time.monotonic() < deadline:
            frame = self.next_frame(max(deadline - time.monotonic(), 0.001))
            if frame is not None:
                frames.append(frame)
        # The server may have closed right after its last frame.
        while True:
            frame = self.next_frame(0.05)
            if frame is None:
                break
            frames.append(frame)
        return frames

    def close(self, *, abort: bool = False) -> None:
        """Close the socket; ``abort`` sends a reset so the server's next
        write fails at once instead of waiting for a heartbeat."""
        if abort:
            try:
                self._sock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                )
            except OSError:
                pass
        try:
            self._sock.close()
        except OSError:
            pass
        self.closed = True


class _EventCase(unittest.TestCase):
    """A fresh store, five seeded events, and helpers to start servers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_path = str(Path(self._tmp.name) / "product-spine.sqlite3")
        self.service = ProductSpineRunStore(LocalMetadataStore(self.store_path))
        self._live = 0
        self.seed()

    def seed(self) -> None:
        """Five events: seq 1-4 run.created, seq 5 run.cancelled (run/e-2)."""
        for second, (run_id, project, work_unit) in enumerate(
            [
                ("run/e-1", "project.alpha", "work/a"),
                ("run/e-2", "project.alpha", "work/b"),
                ("run/e-3", "project.beta", "work/a"),
                ("run/e-10", "project.alpha", "work/a"),
            ],
            start=1,
        ):
            self.service.create(
                _run(run_id=run_id, project_id=project, work_unit_id=work_unit),
                idempotency_key=f"seed-{run_id}",
                created_at=f"2026-10-01T00:00:{second:02d}Z",
            )
        self.service.cancel("run/e-2", updated_at="2026-10-01T00:30:00Z")
        self.assertEqual(self.service.latest_event_sequence(), 5)

    def append_run(self, run_id: str | None = None, **overrides) -> int:
        """Create one more run (one more event); returns the stream head."""
        self._live += 1
        run_id = run_id or f"run/live-{self._live}"
        self.service.create(
            _run(run_id=run_id, **overrides),
            idempotency_key=f"live-{run_id}",
            created_at=f"2026-10-02T00:{self._live // 60:02d}:{self._live % 60:02d}Z",
        )
        return self.service.latest_event_sequence()

    def start(self, **kwargs):
        kwargs.setdefault("product_spine_store_path", self.store_path)
        server = create_server(port=0, **kwargs)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._stop, server, thread)
        return server

    @staticmethod
    def _stop(server, thread) -> None:
        # Shutting the accept loop down does not end open event streams: their
        # handler threads keep polling the store and would write journal files
        # into the test's temp directory while it is being deleted. drain()
        # wakes and ends them first.
        server.drain(timeout=5.0)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    def stream(self, server, **kwargs) -> SSEClient:
        client = SSEClient(server, **kwargs)
        self.addCleanup(client.close)
        return client

    @staticmethod
    def request(server, path, *, method="GET", token=True, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        sent = {TOKEN_HEADER: server.ui_token} if token else {}
        sent.update(headers or {})
        conn.request(method, path, headers=sent)
        response = conn.getresponse()
        body = response.read()
        result = (response.status, dict(response.getheaders()), body)
        conn.close()
        return result

    def release_stream(self, server, client: SSEClient) -> None:
        """Abort ``client`` and wait for the server to free its SSE slot.

        The server only notices a dead peer when it writes, so keep producing
        events until the slot is released.
        """
        client.close(abort=True)

        def released() -> bool:
            if server.sse_limiter.in_flight == 0:
                return True
            self.append_run()
            return False

        wait_until(released, timeout=10.0, interval=0.1)


class EventListHttpTests(_EventCase):
    def test_lists_events_in_sequence_order_matching_the_schemas(self) -> None:
        server = self.start()
        status, _, body = self.request(server, EVENTS)
        document = json.loads(body)
        self.assertEqual(status, 200)
        _validate("idkmesh-list-v0.1.schema.json", document)
        self.assertEqual(
            [item["sequence"] for item in document["items"]], [1, 2, 3, 4, 5]
        )
        for item in document["items"]:
            _validate("idkmesh-event-v0.1.schema.json", item)
        self.assertEqual(
            [item["event_type"] for item in document["items"]],
            ["run.created"] * 4 + ["run.cancelled"],
        )
        self.assertIsNone(document["page"]["next_cursor"])

    def test_pages_with_an_opaque_cursor_without_overlap(self) -> None:
        server = self.start()
        seen = []
        cursor = None
        for _ in range(10):
            query = f"?limit=2" + (f"&cursor={cursor}" if cursor else "")
            status, _, body = self.request(server, EVENTS + query)
            self.assertEqual(status, 200)
            page = json.loads(body)
            seen += [item["sequence"] for item in page["items"]]
            cursor = page["page"]["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, [1, 2, 3, 4, 5])

    def test_filters_are_exact_match_and_combine(self) -> None:
        server = self.start()

        def sequences(query: str) -> list[int]:
            status, _, body = self.request(server, EVENTS + "?" + query)
            self.assertEqual(status, 200, query)
            return [i["sequence"] for i in json.loads(body)["items"]]

        self.assertEqual(sequences("project_id=project.alpha"), [1, 2, 4, 5])
        self.assertEqual(sequences("project_id=project.beta"), [3])
        self.assertEqual(sequences("run_id=" + quote("run/e-1", safe="")), [1])
        self.assertEqual(sequences("run_id=" + quote("run/e-2", safe="")), [2, 5])
        self.assertEqual(sequences("work_unit_id=" + quote("work/a", safe="")),
                         [1, 3, 4])
        self.assertEqual(sequences("event_type=run.cancelled"), [5])
        self.assertEqual(
            sequences("project_id=project.alpha&event_type=run.created"),
            [1, 2, 4],
        )
        self.assertEqual(sequences("project_id=nobody"), [])

    def test_bad_parameters_fail_explicitly(self) -> None:
        server = self.start()
        cases = (
            ("foo=1", "unexpected_query_parameters"),
            ("limit=1&limit=2", "unexpected_query_parameters"),
            ("limit=0", "invalid_limit"),
            ("limit=201", "invalid_limit"),
            ("limit=abc", "invalid_limit"),
            ("cursor=garbage", "invalid_cursor"),
            ("event_type=run.exploded", "invalid_event_type"),
        )
        for query, code in cases:
            with self.subTest(query):
                status, _, body = self.request(server, f"{EVENTS}?{query}")
                document = json.loads(body)
                self.assertEqual(status, 400)
                self.assertEqual(document["error"]["code"], code)
                _validate("idkmesh-api-error-v0.1.schema.json", document)

    def test_other_listings_cursors_are_rejected(self) -> None:
        server = self.start()
        _, _, body = self.request(server, "/api/v1/runs?limit=1")
        run_cursor = json.loads(body)["page"]["next_cursor"]
        _, _, body = self.request(server, "/api/v1/work-units?limit=1")
        work_unit_cursor = json.loads(body)["page"]["next_cursor"]
        for cursor in (run_cursor, work_unit_cursor):
            self.assertIsNotNone(cursor)
            status, _, body = self.request(
                server, f"{EVENTS}?cursor={cursor}"
            )
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["error"]["code"], "invalid_cursor")

    def test_an_event_written_after_startup_is_listed(self) -> None:
        server = self.start()
        head = self.append_run("run/after-start")
        status, _, body = self.request(
            server, EVENTS + "?run_id=" + quote("run/after-start", safe="")
        )
        (item,) = json.loads(body)["items"]
        self.assertEqual(status, 200)
        self.assertEqual(item["sequence"], head)
        self.assertEqual(item["event_type"], "run.created")

    def test_head_has_headers_and_no_body(self) -> None:
        server = self.start()
        status, headers, body = self.request(server, EVENTS, method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_503_without_a_configured_store(self) -> None:
        server = self.start(product_spine_store_path=None)
        for path in (EVENTS, STREAM):
            status, _, body = self.request(server, path)
            self.assertEqual(status, 503, path)
            self.assertEqual(
                json.loads(body)["error"]["code"],
                "product_spine_store_not_configured",
            )

    def test_a_missing_token_is_forbidden(self) -> None:
        server = self.start()
        for path in (EVENTS, STREAM):
            status, _, _ = self.request(server, path, token=False)
            self.assertEqual(status, 403, path)

    def test_every_write_method_is_not_allowed(self) -> None:
        server = self.start()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            for path in (EVENTS, STREAM):
                status, headers, _ = self.request(server, path, method=method)
                self.assertEqual(status, 405, (method, path))
                self.assertIn("GET", headers.get("Allow", ""), (method, path))

    def test_an_unknown_subpath_is_not_found(self) -> None:
        server = self.start()
        status, _, body = self.request(server, EVENTS + "/other")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"]["code"], "not_found")

    def test_status_and_openapi_advertise_both_endpoints(self) -> None:
        server = self.start(max_sse_clients=3)
        _, _, body = self.request(server, "/api/v1/status")
        status_document = json.loads(body)
        _validate(
            "idkmesh-control-tower-status-v0.1.schema.json", status_document
        )
        advertised = set(status_document["endpoints"].values())
        self.assertIn(f"GET {EVENTS}", advertised)
        self.assertIn(f"GET {STREAM}", advertised)
        limits = status_document["operations"]["limits"]
        self.assertEqual(limits["max_sse_clients"], 3)
        self.assertGreater(limits["sse_heartbeat_seconds"], 0)
        self.assertGreater(limits["sse_max_stream_seconds"], 0)
        _, _, body = self.request(server, "/api/v1/openapi.json")
        paths = json.loads(body)["paths"]
        self.assertIn(EVENTS, paths)
        self.assertIn(STREAM, paths)


class EventStreamHttpTests(_EventCase):
    def test_the_stream_is_event_stream_with_id_event_and_data(self) -> None:
        server = self.start()
        client = self.stream(server, last_event_id=0)
        self.assertEqual(client.status, 200)
        self.assertTrue(
            client.headers["content-type"].startswith("text/event-stream"),
            client.headers,
        )
        first = client.next_event(5)
        expected, _ = self.service.list_events(limit=1)
        self.assertEqual(first["id"], "1")
        self.assertEqual(first["event"], "run.created")
        self.assertNotIn("\n", first["data"])
        envelope = json.loads(first["data"])
        self.assertEqual(envelope, expected[0])
        _validate("idkmesh-event-v0.1.schema.json", envelope)

    def test_resume_delivers_exactly_the_events_after_n_then_the_live_tail(
        self,
    ) -> None:
        server = self.start()
        client = self.stream(server, last_event_id=2)
        backlog = client.read_events(3)
        self.assertEqual([e["id"] for e in backlog], ["3", "4", "5"])
        self.assertEqual(
            [json.loads(e["data"])["sequence"] for e in backlog], [3, 4, 5]
        )
        head = self.append_run()
        live = client.next_event(5)
        self.assertEqual(live["id"], str(head))
        self.assertEqual(live["event"], "run.created")

    def test_resume_from_the_head_replays_nothing(self) -> None:
        server = self.start()
        client = self.stream(server, last_event_id=5)
        head = self.append_run()
        first = client.next_event(5)
        self.assertEqual(first["id"], str(head))

    def test_without_last_event_id_the_stream_starts_at_the_live_tail(self) -> None:
        server = self.start()
        baseline = self.service.latest_event_sequence()
        client = self.stream(server)
        received = []

        def produced_and_received() -> bool:
            self.append_run()
            event = client.next_event(0.6)
            if event is not None:
                received.append(event)
            return bool(received)

        wait_until(produced_and_received, timeout=10.0, interval=0.0)
        # History was not replayed. The server fixes the live-tail position
        # before it sends the response head, so the first event delivered is
        # exactly the first one committed after the client connected.
        self.assertEqual(int(received[0]["id"]), baseline + 1)

    def test_reconnecting_with_the_last_seen_id_never_duplicates(self) -> None:
        server = self.start()
        first = self.stream(server, last_event_id=0)
        seen = [e["id"] for e in first.read_events(2)]
        self.assertEqual(seen, ["1", "2"])
        first.close(abort=True)
        second = self.stream(server, last_event_id=seen[-1])
        seen += [e["id"] for e in second.read_events(3)]
        self.assertEqual(seen, ["1", "2", "3", "4", "5"])
        self.assertEqual(len(set(seen)), len(seen))

    def test_an_invalid_last_event_id_is_a_400(self) -> None:
        server = self.start()
        for value in ("abc", "-1", "1.5", "0x10"):
            with self.subTest(value):
                status, _, body = self.request(
                    server, STREAM,
                    headers={"Last-Event-ID": value,
                             "Accept": "text/event-stream"},
                )
                document = json.loads(body)
                self.assertEqual(status, 400)
                self.assertEqual(
                    document["error"]["code"], "invalid_last_event_id"
                )
                _validate("idkmesh-api-error-v0.1.schema.json", document)

    def test_a_last_event_id_beyond_the_stream_head_is_a_400(self) -> None:
        # A client cannot have seen an event this stream has not committed;
        # accepting the id would silently skip every event up to it.
        server = self.start()
        headers = {"Accept": "text/event-stream"}
        for value in ("6", "999"):
            with self.subTest(value):
                status, _, body = self.request(
                    server, STREAM, headers={**headers, "Last-Event-ID": value}
                )
                document = json.loads(body)
                self.assertEqual(status, 400)
                self.assertEqual(
                    document["error"]["code"], "invalid_last_event_id"
                )
                self.assertEqual(
                    document["error"]["details"]["latest_sequence"], 5
                )
                _validate("idkmesh-api-error-v0.1.schema.json", document)

        # An id equal to the head is the normal "caught up" resume.
        caught_up = self.stream(server, last_event_id=5)
        self.assertEqual(caught_up.status, 200)

        # The bound follows the head: once the stream advances, the id that
        # was beyond it is valid and the next one is rejected.
        head = self.append_run()
        self.assertEqual(head, 6)
        resumed = self.stream(server, last_event_id=6)
        self.assertEqual(resumed.status, 200)
        status, _, body = self.request(
            server, STREAM, headers={**headers, "Last-Event-ID": "7"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"]["details"]["latest_sequence"], 6
        )

    def test_a_rejected_beyond_head_id_does_not_take_a_stream_slot(self) -> None:
        server = self.start(max_sse_clients=1)
        status, _, _ = self.request(
            server, STREAM,
            headers={"Accept": "text/event-stream", "Last-Event-ID": "999"},
        )
        self.assertEqual(status, 400)
        wait_until(lambda: server.sse_limiter.in_flight == 0)
        client = self.stream(server, last_event_id=5)
        self.assertEqual(client.status, 200)

    def test_filters_apply_to_the_backlog(self) -> None:
        server = self.start()
        cases = {
            "run_id=" + quote("run/e-1", safe=""): ["1"],
            "event_type=run.cancelled": ["5"],
            "project_id=project.beta": ["3"],
            "work_unit_id=" + quote("work/a", safe=""): ["1", "3", "4"],
        }
        for query, expected in cases.items():
            with self.subTest(query):
                client = self.stream(
                    server, path=f"{STREAM}?{query}", last_event_id=0
                )
                events = client.read_events(len(expected))
                self.assertEqual([e["id"] for e in events], expected)
                # Nothing else is pending for this filter.
                self.assertIsNone(client.next_event(0.7))
                client.close(abort=True)

    def test_filters_apply_to_the_live_tail(self) -> None:
        server = self.start()
        client = self.stream(
            server,
            path=f"{STREAM}?run_id={quote('run/match', safe='')}",
            last_event_id=5,
        )
        self.append_run("run/other-1")
        matching = self.append_run("run/match")
        event = client.next_event(5)
        self.assertEqual(event["id"], str(matching))
        self.assertEqual(json.loads(event["data"])["run_id"], "run/match")

    def test_unsupported_parameters_and_bad_filters_are_400(self) -> None:
        server = self.start()
        cases = (
            ("foo=1", "unexpected_query_parameters"),
            ("limit=5", "unexpected_query_parameters"),
            ("cursor=abc", "unexpected_query_parameters"),
            ("event_type=run.exploded", "invalid_event_type"),
        )
        for query, code in cases:
            with self.subTest(query):
                status, _, body = self.request(
                    server, f"{STREAM}?{query}",
                    headers={"Accept": "text/event-stream"},
                )
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body)["error"]["code"], code)

    def test_the_stream_is_read_only(self) -> None:
        server = self.start()
        for method in ("HEAD", "POST"):
            status, headers, _ = self.request(server, STREAM, method=method)
            self.assertEqual(status, 405, method)
            self.assertIn("GET", headers.get("Allow", ""), method)


class EventStreamLimitTests(_EventCase):
    def test_beyond_max_sse_clients_is_503_with_retry_after(self) -> None:
        server = self.start(max_sse_clients=1)
        first = self.stream(server, last_event_id=5)
        wait_until(lambda: server.sse_limiter.in_flight == 1)

        status, headers, body = self.request(
            server, STREAM, headers={"Accept": "text/event-stream"}
        )
        document = json.loads(body)

        self.assertEqual(status, 503)
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(document["error"]["code"], "too_many_streams")
        _validate("idkmesh-api-error-v0.1.schema.json", document)
        self.assertEqual(server.sse_limiter.in_flight, 1)

        # Releasing the slot lets a new stream in.
        self.release_stream(server, first)
        again = self.stream(server, last_event_id=5)
        self.assertEqual(again.status, 200)

    def test_a_stream_does_not_consume_a_general_request_slot(self) -> None:
        server = self.start(max_concurrent_requests=1, max_sse_clients=2)
        first = self.stream(server, last_event_id=5)
        wait_until(lambda: server.sse_limiter.in_flight == 1)
        self.assertEqual(server.limiter.in_flight, 0)

        status, _, _ = self.request(server, "/api/v1/status")
        self.assertEqual(status, 200)
        second = self.stream(server, last_event_id=5)
        self.assertEqual(second.status, 200)
        self.assertEqual(first.status, 200)
        # Streams never take a general slot, and the status request's own slot
        # is released just after its response is sent, so wait for idle.
        self.assertTrue(server.limiter.wait_idle(5.0), "slot was not released")

    def test_drain_ends_open_streams_with_a_shutdown_marker(self) -> None:
        server = self.start()
        client = self.stream(server, last_event_id=5)
        wait_until(lambda: server.sse_limiter.in_flight == 1)

        drained = server.drain(timeout=5.0)

        self.assertTrue(drained, "streams did not end promptly on drain")
        frames = client.drain_frames(timeout=5.0)
        comments = [f["comment"] for f in frames if f["comment"]]
        self.assertIn("stream-ended reason=shutdown", comments)
        self.assertTrue(client.closed)
        self.assertEqual(server.sse_limiter.in_flight, 0)

    def test_a_draining_server_refuses_new_streams(self) -> None:
        server = self.start()
        self.assertTrue(server.drain(timeout=2.0))
        status, headers, body = self.request(
            server, STREAM, headers={"Accept": "text/event-stream"}
        )
        self.assertEqual(status, 503)
        self.assertIn("Retry-After", headers)
        self.assertEqual(json.loads(body)["error"]["code"], "shutting_down")


class EventStreamTimingTests(_EventCase):
    """Heartbeat, maximum lifetime and poll interval are per-server tunables
    (``server.limits`` and ``server.sse_poll_seconds``), so these tests shorten
    them instead of waiting out the production defaults."""

    def fast_server(self, *, heartbeat: float = 15.0, lifetime: float = 300.0):
        server = self.start()
        server.sse_poll_seconds = 0.05
        server.limits["sse_heartbeat_seconds"] = heartbeat
        server.limits["sse_max_stream_seconds"] = lifetime
        return server

    def test_an_idle_stream_sends_a_keepalive_comment(self) -> None:
        server = self.fast_server(heartbeat=0.2)
        client = self.stream(server, last_event_id=5)
        comments = []

        def saw_keepalive() -> bool:
            frame = client.next_frame(0.5)
            if frame is not None and frame["comment"]:
                comments.append(frame["comment"])
            return "keepalive" in comments

        wait_until(saw_keepalive, timeout=5.0, interval=0.0)

    def test_a_keepalive_is_not_an_event(self) -> None:
        server = self.fast_server(heartbeat=0.2)
        client = self.stream(server, last_event_id=5)
        # Only comments arrive while nothing is committed.
        self.assertIsNone(client.next_event(1.0))

    def test_a_stream_ends_at_its_maximum_lifetime_and_resumes_cleanly(
        self,
    ) -> None:
        server = self.fast_server(lifetime=0.4)
        first = self.stream(server, last_event_id=0)
        frames = first.drain_frames(timeout=5.0)
        ids = [f["id"] for f in frames if f["id"] is not None]
        comments = [f["comment"] for f in frames if f["comment"]]
        self.assertEqual(ids, ["1", "2", "3", "4", "5"])
        self.assertIn("stream-ended reason=max-duration", comments)
        self.assertTrue(first.closed)
        wait_until(lambda: server.sse_limiter.in_flight == 0)

        # The client reconnects with the last id it saw: nothing is repeated
        # and the next committed event is delivered.
        # Commit the next event first so it arrives as resume backlog, not as a
        # live event racing the shortened stream lifetime.
        head = self.append_run()
        second = self.stream(server, last_event_id=ids[-1])
        event = second.next_event(5)
        self.assertEqual(event["id"], str(head))
        self.assertEqual(int(event["id"]), int(ids[-1]) + 1)

    def test_a_shortened_poll_interval_delivers_live_events_promptly(self) -> None:
        server = self.fast_server()
        client = self.stream(server, last_event_id=5)
        started = time.monotonic()
        head = self.append_run()
        event = client.next_event(5)
        self.assertEqual(event["id"], str(head))
        self.assertLess(time.monotonic() - started, 2.0)

    def test_the_shortened_limits_are_what_status_reports(self) -> None:
        server = self.fast_server(heartbeat=0.2, lifetime=0.4)
        _, _, body = self.request(server, "/api/v1/status")
        limits = json.loads(body)["operations"]["limits"]
        self.assertEqual(limits["sse_heartbeat_seconds"], 0.2)
        self.assertEqual(limits["sse_max_stream_seconds"], 0.4)


if __name__ == "__main__":
    unittest.main()
