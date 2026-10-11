"""Security matrix for the local Control Tower API (#745).

Third qualification slice, after the strict-JSON fuzz (PR #992) and the
header/media-type boundary fuzz (PR #994). It drives the access-control
boundary of the real servers with a fixed matrix rather than random mutation:

* **Host matrix** -- only the loopback names are served (DNS-rebinding guard);
* **token bypass matrix** -- every protected route rejects a missing, empty,
  wrong, padded, truncated, extended, re-cased, non-ASCII or mis-placed
  (query string, cookie) session token with a controlled ``403``, and only the
  exact token is served;
* **method confusion** -- unsupported verbs and override headers never reach a
  handler and never produce a 2xx; every ``405`` names its ``Allow`` set;
* **CORS / CSRF** -- no response grants cross-origin access, a preflight is
  refused, and a "simple" cross-site form POST without the token is rejected
  before its body or media type is looked at.

One real defect was found while building the matrix and is fixed alongside it:
a session-token header holding a non-ASCII byte made ``secrets.compare_digest``
raise ``TypeError`` inside the request handler, so the server dropped the
connection with no response instead of answering ``403``. Both local UIs now
share ``local_ui_security.token_matches``.

Every test is class-based on purpose: the repository's documented test counts
guard module-level ``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from idkmesh.control_tower_ui import SAMPLE_REPORT, TOKEN_ENV, create_server
from idkmesh.gate_audit_ui import create_server as create_audit_server
from idkmesh.local_ui_security import TOKEN_HEADER, token_matches

TOKEN = "t" * 32

PROTECTED_GET_PATHS = (
    "/api/v1/status",
    "/api/v1/openapi.json",
    "/api/v1/metrics",
    "/api/v1/runs",
    "/api/v1/runs/run-1",
    "/api/v1/connections",
    "/api/v1/work-units",
    "/api/v1/events",
    "/api/v1/projects/project-1",
    "/api/v1/this-route-does-not-exist",
)
INSPECT_PATH = "/api/v1/run-evidence/inspect"

BAD_TOKENS = {
    "empty": "",
    "wrong": "x" * 32,
    "prefix": TOKEN[:-1],
    "suffix": TOKEN + "x",
    "padded": f" {TOKEN} ",
    "uppercase": TOKEN.upper(),
    "non-ascii": "t\xe9" * 16,
    "high latin-1": "\xff",
    "bearer scheme": f"Bearer {TOKEN}",
}

BAD_HOSTS = (
    "localhost.evil.example",
    "127.0.0.1.evil.example",
    "evil.example",
    "evil.example:80",
    "[::1]",
    "[::1]:8080",
    "0.0.0.0",
    "127.0.0.2",
    "localhost.",
    "127.0.0.1:0",
    "127.0.0.1:65536",
    "127.0.0.1:abc",
    "127.0.0.1:8080:9",
    b"127.0.0.1:\xd9\xa8\xd9\xa0",  # UTF-8 Arabic-Indic digits, as raw bytes
    "user@127.0.0.1",
    "127.0.0.1/",
    "127.0.0.1, evil.example",
    "",
)
GOOD_HOSTS = ("127.0.0.1", "127.0.0.1:8080", "localhost", "LOCALHOST:8080")


def _exchange(port, method, path, headers, body=None, *, token=TOKEN, host="127.0.0.1"):
    """One request with exact headers; returns (status, headers, body bytes)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        conn.putrequest(method, path, skip_host=True)
        if host is not None:
            conn.putheader("Host", host)
        if token is not None:
            conn.putheader(TOKEN_HEADER, token)
        conn.putheader("Connection", "close")
        for name, value in headers.items():
            conn.putheader(name, value)
        conn.endheaders(body)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def _error_code(raw):
    return (json.loads(raw).get("error") or {}).get("code")


class _Harness(unittest.TestCase):
    def setUp(self) -> None:
        with mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}):
            server = create_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        self.port = server.server_port

    def call(self, method, path, headers=None, body=None, **kwargs):
        return _exchange(self.port, method, path, headers or {}, body, **kwargs)


class HostMatrixTests(_Harness):
    def test_only_loopback_hosts_are_served(self):
        for host in GOOD_HOSTS:
            with self.subTest(host=host):
                status, _, _ = self.call("GET", "/api/v1/status", host=host)
                self.assertEqual(status, 200)

    def test_every_other_host_is_refused_before_anything_else(self):
        for host in BAD_HOSTS:
            for method, path in (("GET", "/api/v1/status"), ("POST", INSPECT_PATH)):
                with self.subTest(host=host, method=method):
                    # A valid token must not rescue a hostile Host header.
                    status, _, raw = self.call(
                        method,
                        path,
                        {"Content-Type": "application/json", "Content-Length": "2"}
                        if method == "POST"
                        else {},
                        b"{}" if method == "POST" else None,
                        host=host,
                    )
                    self.assertEqual(status, 403)
                    self.assertEqual(_error_code(raw), "invalid_host")

    def test_missing_host_header_is_refused(self):
        status, _, raw = self.call("GET", "/api/v1/status", host=None)
        self.assertEqual(status, 403)
        self.assertEqual(_error_code(raw), "invalid_host")


class TokenBypassMatrixTests(_Harness):
    def assert_rejected(self, status, raw, context):
        self.assertEqual(status, 403, context)
        self.assertEqual(_error_code(raw), "invalid_session_token", context)

    def test_bad_tokens_are_rejected_on_every_protected_get_route(self):
        for path in PROTECTED_GET_PATHS:
            for label, bad in BAD_TOKENS.items():
                with self.subTest(path=path, token=label):
                    status, _, raw = self.call("GET", path, token=bad)
                    self.assert_rejected(status, raw, f"{path} {label}")

    def test_missing_token_is_rejected_on_every_protected_route(self):
        for method, path in [("GET", p) for p in PROTECTED_GET_PATHS] + [
            ("HEAD", "/api/v1/status"),
            ("POST", INSPECT_PATH),
        ]:
            with self.subTest(method=method, path=path):
                status, _, raw = self.call(method, path, token=None)
                if method == "HEAD":
                    self.assertEqual(status, 403)
                else:
                    self.assert_rejected(status, raw, f"{method} {path}")

    def test_bad_tokens_are_rejected_on_the_mutation_route(self):
        body = json.dumps(SAMPLE_REPORT).encode()
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        for label, bad in BAD_TOKENS.items():
            with self.subTest(token=label):
                status, _, raw = self.call(
                    "POST", INSPECT_PATH, headers, body, token=bad
                )
                self.assert_rejected(status, raw, f"POST {label}")

    def test_token_outside_the_header_is_not_a_credential(self):
        for label, path, headers in (
            ("query string", f"/api/v1/status?token={TOKEN}", {}),
            ("query string alias", f"/api/v1/status?{TOKEN_HEADER}={TOKEN}", {}),
            ("cookie", "/api/v1/status", {"Cookie": f"{TOKEN_HEADER}={TOKEN}"}),
            ("authorization", "/api/v1/status", {"Authorization": f"Bearer {TOKEN}"}),
        ):
            with self.subTest(carrier=label):
                status, _, raw = self.call("GET", path, headers, token=None)
                if label.startswith("query string"):
                    # Queries are not accepted on /status at all; either way
                    # the request is refused and the carried token is inert.
                    self.assertIn(status, (400, 403), label)
                    self.assertEqual(json.loads(raw)["api_version"], "v1")
                else:
                    self.assert_rejected(status, raw, label)

    def test_unauthenticated_requests_learn_nothing_about_routes(self):
        _, _, real = self.call("GET", "/api/v1/runs/run-1", token="x")
        _, _, fake = self.call("GET", "/api/v1/this-route-does-not-exist", token="x")
        self.assertEqual(real, fake)

    def test_exact_token_is_served(self):
        status, _, _ = self.call("GET", "/api/v1/status")
        self.assertEqual(status, 200)

    def test_header_name_is_case_insensitive_but_value_is_exact(self):
        status, _, _ = self.call(
            "GET", "/api/v1/status", {TOKEN_HEADER.lower(): TOKEN}, token=None
        )
        self.assertEqual(status, 200)
        status, _, raw = self.call(
            "GET", "/api/v1/status", {TOKEN_HEADER.lower(): TOKEN.upper()}, token=None
        )
        self.assert_rejected(status, raw, "re-cased value")

    def test_non_ascii_token_gets_a_controlled_403_not_a_dropped_connection(self):
        # Regression: secrets.compare_digest raised TypeError on non-ASCII str,
        # the handler died, and the client saw RemoteDisconnected.
        status, headers, raw = self.call("GET", "/api/v1/status", token="\xe9" * 32)
        self.assert_rejected(status, raw, "non-ascii")
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_server_stays_healthy_after_hostile_tokens(self):
        for bad in BAD_TOKENS.values():
            self.call("GET", "/api/v1/status", token=bad)
        status, _, _ = self.call("GET", "/api/v1/status")
        self.assertEqual(status, 200)


class TokenComparisonTests(unittest.TestCase):
    def test_token_matches_is_total_and_exact(self):
        self.assertTrue(token_matches(TOKEN, TOKEN))
        self.assertFalse(token_matches(None, TOKEN))
        self.assertFalse(token_matches("", TOKEN))
        for label, bad in BAD_TOKENS.items():
            with self.subTest(token=label):
                self.assertFalse(token_matches(bad, TOKEN))
        self.assertTrue(token_matches("\xe9", "\xe9"))


class MethodConfusionTests(_Harness):
    UNSUPPORTED = ("PUT", "PATCH", "DELETE", "TRACE")

    def test_unsupported_verbs_get_405_with_allow_on_known_routes(self):
        routes = {
            "/api/v1/status": "GET, HEAD",
            "/api/v1/runs": "GET, HEAD",
            "/api/v1/runs/run-1": "GET, HEAD",
            INSPECT_PATH: "POST",
            "/api/v1/events": "GET, HEAD",
            "/api/v1/events/stream": "GET",
        }
        for path, allow in routes.items():
            for method in self.UNSUPPORTED:
                with self.subTest(method=method, path=path):
                    status, headers, raw = self.call(method, path)
                    self.assertEqual(status, 405)
                    self.assertEqual(headers.get("Allow"), allow)
                    self.assertEqual(_error_code(raw), "method_not_allowed")

    def test_post_to_a_read_only_route_is_405_and_never_executes(self):
        for path in PROTECTED_GET_PATHS[:8]:
            with self.subTest(path=path):
                status, headers, _ = self.call(
                    "POST", path, {"Content-Type": "application/json", "Content-Length": "2"}, b"{}"
                )
                self.assertEqual(status, 405)
                self.assertIn("GET", headers.get("Allow", ""))

    def test_get_on_the_mutation_route_is_405(self):
        status, headers, _ = self.call("GET", INSPECT_PATH)
        self.assertEqual(status, 405)
        self.assertEqual(headers.get("Allow"), "POST")

    def test_unsupported_verbs_need_the_token_too(self):
        for method in self.UNSUPPORTED:
            with self.subTest(method=method):
                status, _, raw = self.call(method, "/api/v1/status", token=None)
                self.assertEqual(status, 403)
                self.assertEqual(_error_code(raw), "invalid_session_token")

    def test_method_override_headers_change_nothing(self):
        _, _, baseline = self.call("GET", "/api/v1/status")
        for header in (
            "X-HTTP-Method-Override",
            "X-HTTP-Method",
            "X-Method-Override",
        ):
            for verb in ("DELETE", "PUT", "POST"):
                with self.subTest(header=header, verb=verb):
                    status, _, raw = self.call(
                        "GET", "/api/v1/status", {header: verb}
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(raw, baseline)

    def test_no_verb_ever_yields_a_2xx_on_an_unknown_route(self):
        for method in ("GET", "POST", *self.UNSUPPORTED):
            with self.subTest(method=method):
                status, _, _ = self.call(
                    method, "/api/v1/not-a-route",
                    {"Content-Type": "application/json", "Content-Length": "2"}
                    if method == "POST" else {},
                    b"{}" if method == "POST" else None,
                )
                self.assertIn(status, (404, 405))


class CrossOriginTests(_Harness):
    EVIL = "https://evil.example"

    def test_no_response_grants_cross_origin_access(self):
        for method, path, headers, body in (
            ("GET", "/", {}, None),
            ("GET", "/api/v1/status", {}, None),
            ("GET", "/api/v1/status", {"Origin": self.EVIL}, None),
            ("GET", "/api/v1/status", {"Origin": "null"}, None),
            ("OPTIONS", "/api/v1/status", {"Origin": self.EVIL}, None),
            ("POST", INSPECT_PATH, {"Origin": self.EVIL}, None),
        ):
            with self.subTest(method=method, path=path, headers=headers):
                _, response_headers, _ = self.call(method, path, headers, body)
                granted = [
                    name for name in response_headers
                    if name.lower().startswith("access-control-allow")
                ]
                self.assertEqual(granted, [])

    def test_preflight_is_refused_for_every_route(self):
        for path in ("/api/v1/status", INSPECT_PATH, "/api/v1/events", "/"):
            with self.subTest(path=path):
                status, headers, raw = self.call(
                    "OPTIONS",
                    path,
                    {
                        "Origin": self.EVIL,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": TOKEN_HEADER,
                    },
                    token=None,
                )
                self.assertEqual(status, 405)
                self.assertEqual(_error_code(raw), "preflight_not_supported")

    def test_cross_site_form_post_without_the_token_is_rejected_first(self):
        # A browser can send this without a preflight (a "simple" request) and
        # cannot add the custom token header; the token gate must run before
        # the body is read or the media type is judged.
        body = b"report=%7B%7D"
        for content_type in (
            "application/x-www-form-urlencoded",
            "multipart/form-data; boundary=x",
            "text/plain",
        ):
            with self.subTest(content_type=content_type):
                status, _, raw = self.call(
                    "POST",
                    INSPECT_PATH,
                    {
                        "Origin": self.EVIL,
                        "Content-Type": content_type,
                        "Content-Length": str(len(body)),
                    },
                    body,
                    token=None,
                )
                self.assertEqual(status, 403)
                self.assertEqual(_error_code(raw), "invalid_session_token")

    def test_error_responses_carry_the_browser_isolation_headers(self):
        for kwargs in ({"token": "bad"}, {"host": "evil.example"}):
            with self.subTest(kwargs=kwargs):
                _, headers, _ = self.call("GET", "/api/v1/status", **kwargs)
                self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(headers.get("Cache-Control"), "no-store")
                self.assertEqual(headers.get("X-Frame-Options"), "DENY")


class GateAuditUiSecurityTests(unittest.TestCase):
    """The audit UI shares the token and Host guards and must agree with them."""

    def setUp(self) -> None:
        server = create_audit_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        self.server = server

    def post(self, **kwargs):
        return _exchange(
            self.server.server_port,
            "POST",
            "/api/audit",
            {"Content-Type": "application/json", "Content-Length": "2"},
            b"{}",
            **kwargs,
        )

    def test_bad_tokens_get_a_controlled_403(self):
        for label, bad in BAD_TOKENS.items():
            with self.subTest(token=label):
                status, _, raw = self.post(token=bad)
                self.assertEqual(status, 403)
                self.assertFalse(json.loads(raw)["ok"])

    def test_missing_token_and_bad_hosts_are_refused(self):
        self.assertEqual(self.post(token=None)[0], 403)
        for host in BAD_HOSTS:
            with self.subTest(host=host):
                self.assertEqual(
                    self.post(token=self.server.ui_token, host=host)[0], 403
                )

    def test_exact_token_passes_the_guard(self):
        status, _, _ = self.post(token=self.server.ui_token)
        self.assertNotEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
