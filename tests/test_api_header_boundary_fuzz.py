"""Header and media-type boundary fuzz for the Control Tower API (#745).

The first fuzz slice (``tests/test_api_qualification_fuzz.py``, PR #992)
qualified the strict-JSON parsers. This slice qualifies the header boundary
around them:

* request ``Content-Type`` (the 415 ``unsupported_media_type`` gate);
* request ``Accept`` negotiation (the 406 ``not_acceptable`` gate and the
  response media type selection);
* request ``Content-Length`` / ``Transfer-Encoding`` (the 400/411/413 gates);
* the Python client's response ``Content-Type`` check.

The property under test is totality: every header value a client can put on
the wire gets a complete, controlled JSON document back -- a status below 500
and a stable ``error.code`` on rejection -- never an unhandled exception, a
hung connection, or a dead worker. A second property is boundary agreement:
the two sides of the same media-type decision must normalize values the same
way, and RFC 9110 case-insensitivity/optional whitespace must not turn a
valid response into a ``ProtocolError``.

Three boundary bugs found while qualifying this surface are fixed alongside
this suite (see CHANGELOG): explicit ``q=0`` Accept entries were served
anyway, the client rejected case/whitespace variants of valid response media
types, and ``Content-Length`` accepted any spelling ``int()`` parses (such as
``+2``) instead of RFC 9110 ``1*DIGIT``.

Every test is class-based on purpose: the repository's documented test counts
guard module-level ``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import http.client
import json
import random
import socket
import threading
import unittest
from unittest import mock

from idkmesh.api_client import ControlTowerClient, ProtocolError
from idkmesh.control_tower_ui import SAMPLE_REPORT, TOKEN_ENV, create_server
from idkmesh.gate_audit_ui import MAX_BODY_BYTES as AUDIT_MAX_BODY_BYTES
from idkmesh.gate_audit_ui import create_server as create_audit_server
from idkmesh.local_ui_security import MAX_BODY_BYTES, TOKEN_HEADER
from idkmesh.work_unit_binding import canonical_digest

TOKEN = "t" * 32
SEED = 20261010

INSPECT_PATH = "/api/v1/run-evidence/inspect"
STATUS_PATH = "/api/v1/status"
VENDOR_TYPE = "application/vnd.idkmesh.control-tower.v1+json"

# Values http.client can put on the wire (no bare CR/LF/NUL -- those belong to
# the raw-socket class). Odd latin-1 bytes and a fullwidth digit exercise the
# normalization paths.
MUTATION_ALPHABET = 'Aa0 ;,q="\\/*+-_%\t\xc9\xa9\xb2\xbd\xff '

CONTENT_TYPE_CORPUS = (
    "application/json",
    "Application/JSON",
    "APPLICATION/JSON",
    "APPLICATION/JSON ; charset=utf-8",
    "application/json ;charset=utf-8",
    "  application/json  ",
    "application/json;charset=utf-8; charset=utf-8",
    'application/json; charset="utf-8"',
    "application/json;q=0",
    VENDOR_TYPE,
    "text/plain",
    "",
    "application/json" + ";x=" + "y" * 5000,
    "application/json;" + ";".join(f"p{i}=v" for i in range(200)),
    ",application/json",
    "application/json, text/plain",
    "\tapplication/json\t",
)

ACCEPT_CORPUS = (
    "*/*",
    "application/json",
    "text/html",
    "",
    VENDOR_TYPE,
    "APPLICATION/VND.IDKMESH.CONTROL-TOWER.V1+JSON",
    "," * 500,
    "application/json" + ",application/json" * 200,
    "application/json;q=" + "9" * 200,
    "application/json;q=nan",
    "application/json;",
    "application/json;=",
    ";q=0.5",
    "text/html, application/xhtml+xml, */*;q=0.8",
)


class _ServerHarness(unittest.TestCase):
    def start_server(self):
        with mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}):
            server = create_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        return server

    def send(self, server, method, path, headers, body=None):
        """One request with exact headers; returns (status, headers, body)."""
        conn = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        try:
            conn.putrequest(method, path, skip_host=True)
            conn.putheader("Host", "127.0.0.1")
            conn.putheader(TOKEN_HEADER, TOKEN)
            conn.putheader("Connection", "close")
            for name, value in headers.items():
                conn.putheader(name, value)
            conn.endheaders(body)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def assert_controlled(self, status, raw, context):
        """A controlled answer: status < 500 and a well-formed JSON document."""
        self.assertLess(status, 500, f"{context}: status {status}")
        payload = json.loads(raw)
        if status >= 400:
            code = (payload.get("error") or {}).get("code")
            self.assertIsInstance(code, str, f"{context}: {payload!r}")
            self.assertTrue(code, f"{context}: empty error code")


def _mutate(rng: random.Random, base: str) -> str:
    chars = list(base)
    for _ in range(rng.randint(1, 4)):
        op = rng.randrange(3)
        if op == 0 and chars:
            del chars[rng.randrange(len(chars))]
        elif op == 1 or not chars:
            chars.insert(rng.randrange(len(chars) + 1), rng.choice(MUTATION_ALPHABET))
        else:
            chars[rng.randrange(len(chars))] = rng.choice(MUTATION_ALPHABET)
    # Bare CR/LF would be header injection; http.client refuses to send them
    # and request-line smuggling is a separate boundary.
    return "".join(chars).replace("\r", "?").replace("\n", "?")


class RequestMediaTypeTests(_ServerHarness):
    """The 415 gate: case-insensitive, parameter-tolerant, fail-closed."""

    def setUp(self) -> None:
        self.server = self.start_server()

    def test_media_type_matching_is_case_and_whitespace_insensitive(self):
        for content_type in (
            "application/json",
            "Application/JSON",
            "APPLICATION/JSON ; charset=utf-8",
            "application/json ;charset=utf-8",
            'application/json; charset="utf-8"',
            "\tapplication/json\t",
        ):
            with self.subTest(content_type=content_type):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {"Content-Type": content_type, "Content-Length": "2"},
                    b"{}",
                )
                # 400 invalid_run_evidence proves the body got past the
                # media-type gate to request validation.
                payload = json.loads(raw)
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["code"], "invalid_run_evidence"
                )

    def test_a_valid_vendor_content_type_reaches_the_endpoint(self):
        body = SAMPLE_REPORT.encode("utf-8")
        status, _, raw = self.send(
            self.server,
            "POST",
            INSPECT_PATH,
            {
                "Content-Type": f"{VENDOR_TYPE}; charset=utf-8",
                "Content-Length": str(len(body)),
            },
            body,
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["ok"])

    def test_non_json_media_types_still_fail_closed(self):
        for content_type in ("text/plain", "application/jsonp", "*/*", "json"):
            with self.subTest(content_type=content_type):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {"Content-Type": content_type, "Content-Length": "2"},
                    b"{}",
                )
                payload = json.loads(raw)
                self.assertEqual(status, 415)
                self.assertEqual(
                    payload["error"]["code"], "unsupported_media_type"
                )

    def test_seeded_content_type_mutations_stay_total(self):
        rng = random.Random(SEED)
        bases = ("application/json", VENDOR_TYPE, "application/json; charset=utf-8")
        for index in range(120):
            value = _mutate(rng, bases[index % len(bases)])
            with self.subTest(index=index, value=value[:60]):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {"Content-Type": value, "Content-Length": "2"},
                    b"{}",
                )
                self.assert_controlled(status, raw, f"content-type {value!r}")


class AcceptNegotiationTests(_ServerHarness):
    """The 406 gate and response media-type selection."""

    def setUp(self) -> None:
        self.server = self.start_server()

    def test_vendor_accept_matching_is_case_and_whitespace_insensitive(self):
        for accept in (
            VENDOR_TYPE,
            "APPLICATION/VND.IDKMESH.CONTROL-TOWER.V1+JSON",
            f" {VENDOR_TYPE} ; q=1",
            f"{VENDOR_TYPE.upper()}\t",
        ):
            with self.subTest(accept=accept):
                status, headers, raw = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": accept}
                )
                self.assertEqual(status, 200)
                self.assertTrue(
                    headers["Content-Type"].startswith(VENDOR_TYPE),
                    headers["Content-Type"],
                )
                self.assert_controlled(status, raw, f"accept {accept!r}")

    def test_explicit_zero_quality_marks_an_entry_unacceptable(self):
        for accept in (
            "application/json;q=0",
            "application/json;q=0.0",
            "application/json;q=0.000",
            f"{VENDOR_TYPE};q=0",
            "*/*;q=0",
        ):
            with self.subTest(accept=accept):
                status, _, raw = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": accept}
                )
                payload = json.loads(raw)
                self.assertEqual(status, 406)
                self.assertEqual(payload["error"]["code"], "not_acceptable")

    def test_zero_quality_only_disqualifies_its_own_entry(self):
        for accept in (
            "application/json;q=0, application/json;q=0.5",
            "application/json;q=0, */*",
            "text/html;q=0, application/json",
        ):
            with self.subTest(accept=accept):
                status, _, _ = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": accept}
                )
                self.assertEqual(status, 200)

    def test_malformed_quality_stays_lenient(self):
        for accept in (
            "application/json;q=bogus",
            "application/json;q=nan",
            "application/json;q=-1",
            "application/json;=",
            "application/json;",
        ):
            with self.subTest(accept=accept):
                status, _, _ = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": accept}
                )
                self.assertEqual(status, 200)

    def test_zero_quality_vendor_type_falls_back_to_plain_json(self):
        status, headers, _ = self.send(
            self.server,
            "GET",
            STATUS_PATH,
            {"Accept": f"{VENDOR_TYPE};q=0, */*"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertFalse(headers["Content-Type"].startswith(VENDOR_TYPE))

    def test_unacceptable_accept_still_fails_closed(self):
        for accept in ("text/html", "application/xml", "image/png"):
            with self.subTest(accept=accept):
                status, _, raw = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": accept}
                )
                payload = json.loads(raw)
                self.assertEqual(status, 406)
                self.assertEqual(payload["error"]["code"], "not_acceptable")

    def test_seeded_accept_mutations_stay_total(self):
        rng = random.Random(SEED + 1)
        bases = ("application/json", "*/*", VENDOR_TYPE, "text/html")
        for index in range(120):
            value = _mutate(rng, bases[index % len(bases)])
            with self.subTest(index=index, value=value[:60]):
                status, _, raw = self.send(
                    self.server, "GET", STATUS_PATH, {"Accept": value}
                )
                self.assert_controlled(status, raw, f"accept {value!r}")


class ContentLengthBoundaryTests(_ServerHarness):
    """411/400/413 gates: Content-Length is 1*ASCII DIGIT (RFC 9110)."""

    def setUp(self) -> None:
        self.server = self.start_server()

    def test_ascii_digit_lengths_reach_request_validation(self):
        for raw_length in ("2", " 2", "2 ", "02", "0002"):
            with self.subTest(content_length=raw_length):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {"Content-Type": "application/json", "Content-Length": raw_length},
                    b"{}",
                )
                payload = json.loads(raw)
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["code"], "invalid_run_evidence"
                )

    def test_content_length_rejects_every_non_digit_spelling(self):
        # "+2" and "-0" are the wire-reachable leniencies int() used to
        # accept; a strict fronting proxy rejects them, and that parser
        # disagreement is request-smuggling surface.
        for raw_length in (
            "+2",
            "-0",
            "-1",
            "2.0",
            "2e0",
            "2,2",
            "0x2",
            "",
            " ",
            "1 1",
            "\xb22",
            "2\xbd",
        ):
            with self.subTest(content_length=raw_length):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {"Content-Type": "application/json", "Content-Length": raw_length},
                    b"{}",
                )
                payload = json.loads(raw)
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["code"], "invalid_content_length"
                )

    def test_missing_content_length_is_411(self):
        status, _, raw = self.send(
            self.server,
            "POST",
            INSPECT_PATH,
            {"Content-Type": "application/json"},
        )
        payload = json.loads(raw)
        self.assertEqual(status, 411)
        self.assertEqual(payload["error"]["code"], "length_required")

    def test_any_transfer_encoding_is_rejected_before_the_body(self):
        for value in ("chunked", "identity", "gzip, chunked"):
            with self.subTest(transfer_encoding=value):
                status, _, raw = self.send(
                    self.server,
                    "POST",
                    INSPECT_PATH,
                    {
                        "Content-Type": "application/json",
                        "Transfer-Encoding": value,
                        "Content-Length": "2",
                    },
                    b"{}",
                )
                payload = json.loads(raw)
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["code"], "unsupported_transfer_encoding"
                )

    def test_oversized_content_length_is_413_before_the_read(self):
        status, _, raw = self.send(
            self.server,
            "POST",
            INSPECT_PATH,
            {
                "Content-Type": "application/json",
                "Content-Length": str(MAX_BODY_BYTES + 1),
            },
        )
        payload = json.loads(raw)
        self.assertEqual(status, 413)
        self.assertEqual(payload["error"]["code"], "payload_too_large")


class RawByteBoundaryTests(_ServerHarness):
    """Byte-level hostility: the worker survives and the server keeps serving."""

    def setUp(self) -> None:
        self.server = self.start_server()

    def raw_status_line(self, hostile_header_line: bytes):
        request = (
            b"GET /api/v1/status HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + f"{TOKEN_HEADER}: {TOKEN}\r\n".encode("ascii")
            + hostile_header_line
            + b"\r\nConnection: close\r\n\r\n"
        )
        with socket.create_connection(
            ("127.0.0.1", self.server.server_port), timeout=3
        ) as connection:
            connection.sendall(request)
            chunks = []
            try:
                while chunk := connection.recv(4096):
                    chunks.append(chunk)
            except OSError:
                pass
        first_line = b"".join(chunks).split(b"\r\n", 1)[0]
        # Either a complete status line or a clean drop by the HTTP layer
        # (for example an over-long header line). Never a 5xx.
        if not first_line.startswith(b"HTTP/"):
            return None
        return int(first_line.split(b" ", 2)[1])

    def test_control_bytes_and_oversized_lines_never_kill_the_server(self):
        hostile = (
            b"Accept: a\x00b",
            b"Content-Type: application/json\x00",
            b"Content-Length: 2\x00",
            b"X-Trace: \x7f\x1b[31m",
            b"Accept: a\rb",
            b"Accept: " + b"a" * 70000,
        )
        for line in hostile:
            with self.subTest(line=line[:40]):
                code = self.raw_status_line(line)
                if code is not None:
                    self.assertLess(code, 500)

        # Liveness: the server still answers a normal request.
        status, _, raw = self.send(
            self.server, "GET", STATUS_PATH, {"Accept": "application/json"}
        )
        self.assert_controlled(status, raw, "liveness after hostile bytes")


class ClientResponseMediaTypeTests(unittest.TestCase):
    """The client's response gate must agree with the server's normalization."""

    @staticmethod
    def client():
        return ControlTowerClient(
            "http://127.0.0.1:8770", TOKEN, timeout=1.0
        )

    def stubbed_status(self, content_type):
        payload = {"kind": "idkmesh-control-tower-status", "ok": True}
        response = _StubResponse(payload, content_type)
        client = self.client()
        with mock.patch(
            "idkmesh.api_client.http.client.HTTPConnection",
            return_value=_StubConnection(response),
        ):
            return client.status()

    def test_response_media_type_is_case_and_whitespace_insensitive(self):
        for content_type in (
            "application/json",
            "Application/JSON",
            "APPLICATION/JSON ; charset=utf-8",
            "application/json ;charset=utf-8",
            " application/json ",
            "Application/Vnd.Idkmesh.Control-Tower.V1+Json; charset=utf-8",
            f"{VENDOR_TYPE} ; charset=utf-8",
        ):
            with self.subTest(content_type=content_type):
                result = self.stubbed_status(content_type)
                self.assertTrue(result.value["ok"])

    def test_wrong_response_media_types_still_fail_closed(self):
        for content_type in (
            "text/html",
            "application/jsonp",
            "",
            "application/json charset=utf-8",
            "application/jsonx",
        ):
            with self.subTest(content_type=content_type):
                with self.assertRaises(ProtocolError):
                    self.stubbed_status(content_type)

    def test_missing_response_media_type_fails_closed(self):
        payload = {"kind": "idkmesh-control-tower-status", "ok": True}
        response = _StubResponse(payload, "application/json")
        response._headers.pop("Content-Type")
        client = self.client()
        with mock.patch(
            "idkmesh.api_client.http.client.HTTPConnection",
            return_value=_StubConnection(response),
        ):
            with self.assertRaises(ProtocolError):
                client.status()


class GateAuditContentLengthTests(unittest.TestCase):
    """The gate-audit UI shares the request boundary; keep it in lockstep."""

    def setUp(self) -> None:
        # The audit UI mints its own session token; requests carry
        # server.ui_token below.
        server = create_audit_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        self.server = server

    def post(self, raw_length, body=b"{}"):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        try:
            conn.putrequest("POST", "/api/audit", skip_host=True)
            conn.putheader("Host", "127.0.0.1")
            conn.putheader(TOKEN_HEADER, self.server.ui_token)
            conn.putheader("Content-Type", "application/json")
            if raw_length is not None:
                conn.putheader("Content-Length", raw_length)
            conn.putheader("Connection", "close")
            conn.endheaders(body)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_content_length_rejects_non_digit_spellings(self):
        for raw_length in ("+2", "-1", "2.0", "", "2,2"):
            with self.subTest(content_length=raw_length):
                status, raw = self.post(raw_length)
                payload = json.loads(raw)
                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])

    def test_digit_length_reaches_audit_validation(self):
        status, raw = self.post("2", b"{}")
        payload = json.loads(raw)
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertNotIn("larger than", payload["error"])

    def test_oversized_content_length_is_still_413(self):
        status, raw = self.post(str(AUDIT_MAX_BODY_BYTES + 1))
        payload = json.loads(raw)
        self.assertEqual(status, 413)
        self.assertFalse(payload["ok"])


class _StubResponse:
    def __init__(self, payload, content_type):
        self.status = 200
        self._raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self._headers = {
            "Content-Type": content_type,
            "X-Request-ID": "req_test",
            "X-IDKMesh-Content-Digest": canonical_digest(payload),
        }

    def read(self):
        return self._raw

    def getheader(self, name):
        return self._headers.get(name)


class _StubConnection:
    def __init__(self, response):
        self.response = response

    def request(self, method, path, body=None, headers=None):
        pass

    def getresponse(self):
        return self.response

    def close(self):
        pass
