"""Bounded service limits for the Control Tower dev server (ADR-0022, #742).

Each documented limit is proven by behaviour, not by reading a constant: the
overload and drain tests hold a handler open on an Event so the outcome is
deterministic, and the stdlib parser bounds are probed with raw sockets so the
documented numbers fail loudly if the stdlib ever changes them.
"""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from idkmesh import cli
from idkmesh.control_tower_api import status_document
from idkmesh.control_tower_ui import create_server
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.service_runtime import (
    ADMITTED,
    DRAINING,
    MAX_HEADER_COUNT,
    MAX_HEADER_LINE_BYTES,
    MAX_REQUEST_LINE_BYTES,
    OVERLOADED,
    RequestLimiter,
    limits_document,
    validate_max_concurrent_requests,
    validate_request_timeout,
)


def _validate(schema_filename: str, document: dict) -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    schema = json.loads((root / schema_filename).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


class RequestLimiterTests(unittest.TestCase):
    def test_admits_up_to_the_cap_then_reports_overloaded(self) -> None:
        limiter = RequestLimiter(2)
        self.assertEqual(limiter.admit(), ADMITTED)
        self.assertEqual(limiter.admit(), ADMITTED)
        self.assertEqual(limiter.admit(), OVERLOADED)
        self.assertEqual(limiter.in_flight, 2)
        limiter.release()
        self.assertEqual(limiter.admit(), ADMITTED)

    def test_overloaded_rejection_does_not_consume_a_slot(self) -> None:
        limiter = RequestLimiter(1)
        limiter.admit()
        for _ in range(5):
            self.assertEqual(limiter.admit(), OVERLOADED)
        self.assertEqual(limiter.in_flight, 1)

    def test_drain_rejects_new_requests_but_lets_inflight_finish(self) -> None:
        limiter = RequestLimiter(4)
        self.assertEqual(limiter.admit(), ADMITTED)
        limiter.begin_drain()
        self.assertTrue(limiter.draining)
        self.assertEqual(limiter.admit(), DRAINING)
        self.assertFalse(limiter.wait_idle(0.05))
        limiter.release()
        self.assertTrue(limiter.wait_idle(0.05))

    def test_wait_idle_wakes_when_the_last_request_releases(self) -> None:
        limiter = RequestLimiter(1)
        limiter.admit()
        threading.Timer(0.1, limiter.release).start()
        started = time.monotonic()
        self.assertTrue(limiter.wait_idle(5.0))
        self.assertLess(time.monotonic() - started, 2.0)

    def test_release_without_admit_is_an_error(self) -> None:
        with self.assertRaises(RuntimeError):
            RequestLimiter(1).release()

    def test_validation_rejects_out_of_range_values(self) -> None:
        for bad in (0, -1, True, 1025, 1.5, "8"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                validate_max_concurrent_requests(bad)
        for bad in (0, 0.01, 301, True, "5", float("nan")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                validate_request_timeout(bad)
        self.assertEqual(validate_request_timeout(5), 5.0)
        self.assertEqual(validate_max_concurrent_requests(16), 16)

    def test_limits_document_reports_the_documented_bounds(self) -> None:
        document = limits_document(
            request_timeout_seconds=10,
            max_concurrent_requests=16,
            max_request_body_bytes=2 * 1024 * 1024,
        )
        self.assertEqual(document["max_request_line_bytes"], 65536)
        self.assertEqual(document["max_header_line_bytes"], 65536)
        self.assertEqual(document["max_header_count"], 99)
        self.assertEqual(document["overload_status"], 503)
        self.assertEqual(document["per_client_rate_limit"], "not_implemented")
        probe = status_document(limits=document)
        _validate("idkmesh-control-tower-status-v0.1.schema.json", probe)

    def test_a_bare_status_document_has_no_limits_and_stays_valid(self) -> None:
        bare = status_document()
        self.assertNotIn("limits", bare["operations"])
        _validate("idkmesh-control-tower-status-v0.1.schema.json", bare)


class _ServerCase(unittest.TestCase):
    """Starts a Control Tower server per test with chosen limits."""

    def start(self, **kwargs):
        server = create_server(port=0, **kwargs)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._stop, server, thread)
        return server

    @staticmethod
    def _stop(server, thread) -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    @staticmethod
    def get(server, path: str, *, token: bool = True):
        conn = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        headers = {TOKEN_HEADER: server.ui_token} if token else {}
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        body = response.read()
        result = (response.status, dict(response.getheaders()), body)
        conn.close()
        return result

    @staticmethod
    def raw(server, payload: bytes, *, timeout: float = 5.0) -> bytes:
        """Send raw bytes and read until the server closes the connection."""
        with socket.create_connection(
            ("127.0.0.1", server.server_port), timeout=timeout
        ) as sock:
            sock.sendall(payload)
            chunks = []
            try:
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
            except (socket.timeout, ConnectionResetError):
                pass
            return b"".join(chunks)

    @staticmethod
    def host(server) -> str:
        return f"127.0.0.1:{server.server_port}"


class StatusPublishesLimitsTests(_ServerCase):
    def test_status_reports_the_limits_in_force(self) -> None:
        server = self.start(request_timeout=2.5, max_concurrent_requests=3)
        status, _, body = self.get(server, "/api/v1/status")
        document = json.loads(body)
        self.assertEqual(status, 200)
        _validate("idkmesh-control-tower-status-v0.1.schema.json", document)
        limits = document["operations"]["limits"]
        self.assertEqual(limits["request_timeout_seconds"], 2.5)
        self.assertEqual(limits["max_concurrent_requests"], 3)
        self.assertEqual(limits, server.limits)

    def test_invalid_limits_are_refused_before_binding(self) -> None:
        with self.assertRaises(ValueError):
            create_server(port=0, request_timeout=0)
        with self.assertRaises(ValueError):
            create_server(port=0, max_concurrent_requests=0)

    def test_cli_rejects_an_invalid_limit_without_serving(self) -> None:
        for flag, value in (
            ("--request-timeout", "0"),
            ("--max-concurrent-requests", "0"),
        ):
            with mock.patch("sys.stderr"):
                rc = cli.main(
                    ["control-tower", "--no-browser", "--port", "0", flag, value]
                )
            self.assertNotEqual(rc, 0, flag)


class OverloadTests(_ServerCase):
    def _hold_open(self, server, count: int, release: threading.Event):
        """Occupy ``count`` slots by blocking the status handler."""
        real = status_document

        def blocked(*args, **kwargs):
            release.wait(10)
            return real(*args, **kwargs)

        results: list[int] = []

        def call():
            status, _, _ = self.get(server, "/api/v1/status")
            results.append(status)

        patcher = mock.patch("idkmesh.control_tower_ui.status_document", blocked)
        patcher.start()
        self.addCleanup(patcher.stop)
        threads = [threading.Thread(target=call) for _ in range(count)]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + 5
        while server.limiter.in_flight < count:
            self.assertLess(time.monotonic(), deadline, "slots never filled")
            time.sleep(0.01)
        return threads, results

    def test_beyond_the_cap_is_503_with_retry_after_then_recovers(self) -> None:
        server = self.start(max_concurrent_requests=2)
        release = threading.Event()
        threads, results = self._hold_open(server, 2, release)

        status, headers, body = self.get(server, "/api/v1/runs")
        document = json.loads(body)

        self.assertEqual(status, 503)
        self.assertEqual(headers["Retry-After"], "1")
        self.assertEqual(document["error"]["code"], "overloaded")
        self.assertEqual(document["error"]["details"]["retry_after_seconds"], 1)
        _validate("idkmesh-api-error-v0.1.schema.json", document)
        self.assertEqual(server.limiter.in_flight, 2)

        release.set()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(sorted(results), [200, 200])
        # The server releases its slot after it has sent the response, so the
        # client can finish first: wait for idle instead of asserting it.
        self.assertTrue(server.limiter.wait_idle(5.0), "slots were not released")
        status, _, _ = self.get(server, "/api/v1/status")
        self.assertEqual(status, 200)

    def test_liveness_is_exempt_from_the_cap(self) -> None:
        server = self.start(max_concurrent_requests=1)
        release = threading.Event()
        threads, _ = self._hold_open(server, 1, release)

        status, _, body = self.get(server, "/healthz")
        self.assertEqual((status, body), (200, b"ok\n"))
        status, _, body = self.get(server, "/readyz")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"]["code"], "overloaded")

        release.set()
        for thread in threads:
            thread.join(timeout=5)

    def test_head_rejection_has_headers_and_no_body(self) -> None:
        server = self.start(max_concurrent_requests=1)
        release = threading.Event()
        threads, _ = self._hold_open(server, 1, release)

        conn = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        conn.request("HEAD", "/api/v1/runs",
                     headers={TOKEN_HEADER: server.ui_token})
        response = conn.getresponse()
        body = response.read()
        conn.close()
        self.assertEqual(response.status, 503)
        self.assertEqual(response.getheader("Retry-After"), "1")
        self.assertEqual(body, b"")

        release.set()
        for thread in threads:
            thread.join(timeout=5)


class DrainTests(_ServerCase):
    def test_draining_rejects_work_and_readiness_but_not_liveness(self) -> None:
        server = self.start()
        server.limiter.begin_drain()

        status, headers, body = self.get(server, "/api/v1/runs")
        self.assertEqual(status, 503)
        self.assertEqual(headers["Retry-After"], "1")
        self.assertEqual(json.loads(body)["error"]["code"], "shutting_down")
        status, _, body = self.get(server, "/readyz")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"]["code"], "shutting_down")
        status, _, _ = self.get(server, "/healthz")
        self.assertEqual(status, 200)

    def test_drain_waits_for_an_inflight_request_to_complete(self) -> None:
        server = self.start()
        release = threading.Event()
        real = status_document
        results: list[int] = []

        def blocked(*args, **kwargs):
            release.wait(10)
            return real(*args, **kwargs)

        patcher = mock.patch("idkmesh.control_tower_ui.status_document", blocked)
        patcher.start()
        self.addCleanup(patcher.stop)
        thread = threading.Thread(
            target=lambda: results.append(self.get(server, "/api/v1/status")[0])
        )
        thread.start()
        deadline = time.monotonic() + 5
        while server.limiter.in_flight < 1:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)

        self.assertFalse(server.drain(timeout=0.2), "drain must report a busy server")
        release.set()
        self.assertTrue(server.drain(timeout=5.0))
        thread.join(timeout=5)
        # The in-flight request finished normally; it was not abandoned.
        self.assertEqual(results, [200])


class SlowClientTests(_ServerCase):
    def test_a_client_that_stalls_mid_request_line_is_dropped(self) -> None:
        server = self.start(request_timeout=0.3)
        started = time.monotonic()
        data = self.raw(server, b"GET /healthz HTTP/1.1\r\nHo", timeout=5.0)
        elapsed = time.monotonic() - started
        self.assertEqual(data, b"")
        self.assertLess(elapsed, 3.0, "server held the stalled connection")
        deadline = time.monotonic() + 2
        while server.limiter.in_flight:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        status, _, _ = self.get(server, "/healthz")
        self.assertEqual(status, 200)

    def test_a_stalled_body_is_answered_408(self) -> None:
        server = self.start(request_timeout=0.3)
        request = (
            "POST /api/v1/run-evidence/inspect HTTP/1.1\r\n"
            f"Host: {self.host(server)}\r\n"
            f"{TOKEN_HEADER}: {server.ui_token}\r\n"
            "Accept: application/json\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 100\r\n\r\n{\"a\":"
        ).encode("ascii")
        data = self.raw(server, request, timeout=5.0)
        head, _, body = data.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.0 408"), head[:40])
        self.assertEqual(json.loads(body)["error"]["code"], "request_timeout")
        self.assertTrue(server.limiter.wait_idle(5.0), "slot was not released")


class ParserBoundTests(_ServerCase):
    """The documented stdlib bounds, pinned so a change cannot go unnoticed."""

    def _status_line(self, data: bytes) -> bytes:
        return data.split(b"\r\n", 1)[0]

    def test_request_line_over_the_limit_is_414(self) -> None:
        server = self.start()
        path = b"/" + b"a" * MAX_REQUEST_LINE_BYTES
        data = self.raw(server, b"GET " + path + b" HTTP/1.1\r\n\r\n")
        self.assertIn(b" 414 ", self._status_line(data))

    def test_more_than_the_header_count_limit_is_431(self) -> None:
        server = self.start()
        # Host plus MAX_HEADER_COUNT extras is one field over the limit.
        headers = b"".join(
            b"X-H%d: 1\r\n" % index for index in range(MAX_HEADER_COUNT)
        )
        payload = (
            f"GET /healthz HTTP/1.1\r\nHost: {self.host(server)}\r\n"
        ).encode("ascii") + headers + b"\r\n"
        data = self.raw(server, payload)
        self.assertIn(b" 431 ", self._status_line(data))

    def test_a_header_line_over_the_limit_is_431(self) -> None:
        server = self.start()
        payload = (
            f"GET /healthz HTTP/1.1\r\nHost: {self.host(server)}\r\n"
        ).encode("ascii") + b"X-Big: " + b"a" * MAX_HEADER_LINE_BYTES + b"\r\n\r\n"
        data = self.raw(server, payload)
        self.assertIn(b" 431 ", self._status_line(data))

    def test_headers_at_the_count_limit_are_still_served(self) -> None:
        server = self.start()
        headers = b"".join(
            b"X-H%d: 1\r\n" % index for index in range(MAX_HEADER_COUNT - 1)
        )
        payload = (
            f"GET /healthz HTTP/1.1\r\nHost: {self.host(server)}\r\n"
        ).encode("ascii") + headers + b"\r\n"
        data = self.raw(server, payload)
        self.assertIn(b" 200 ", self._status_line(data))


class ConnectionPolicyTests(_ServerCase):
    def test_the_connection_closes_after_one_response(self) -> None:
        server = self.start()
        payload = (
            f"GET /healthz HTTP/1.1\r\nHost: {self.host(server)}\r\n"
            "Connection: keep-alive\r\n\r\n"
        ).encode("ascii")
        started = time.monotonic()
        data = self.raw(server, payload, timeout=5.0)
        self.assertIn(b" 200 ", data.split(b"\r\n", 1)[0])
        self.assertEqual(data.count(b"HTTP/1."), 1)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(server.limits["connection_policy"], "close_after_response")


if __name__ == "__main__":
    unittest.main()
