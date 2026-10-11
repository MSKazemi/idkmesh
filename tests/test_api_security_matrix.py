"""Security matrix for the Control Tower local API (issue #745, Security slice).

Closes three Security-section items of the #745 release-qualification
acceptance list against the real server:

- auth/token bypass matrix,
- method confusion,
- CORS/CSRF for mutations.

The v0.1 local API has exactly one privilege: possession of the local UI
session token (``TOKEN_HEADER``). There is no role model, so the permission
matrix is the auth matrix crossed with the advertised endpoint map -- both are
exercised here exhaustively and driven by the server's own ``/api/v1/status``
discovery document rather than a hand-copied route list.

Contract decisions pinned here:

- The token travels in exactly one place: the ``TOKEN_HEADER`` request header.
  Query strings, ``Authorization``, ``Cookie``, and similarly named headers
  are never accepted. The custom-header-only transport is also the CSRF
  defense: a cross-site "simple request" cannot set it without a preflight,
  and preflight is refused (see ``CrossOriginMutationTests``).
- HTTP header *names* are case-insensitive (RFC 9110 section 5.1), so the
  lowercase header name must keep working; the token *value* comparison is
  exact and case-sensitive.
- Every invalid token transport yields the same controlled ``403
  invalid_session_token`` JSON envelope -- including hostile header values
  (non-ASCII, oversized) that must fail closed, never crash the handler.
- Authentication is checked before content negotiation and before body
  parsing, so unauthenticated callers learn nothing from ``Accept`` handling
  or request bodies.
- Methods are a closed set: GET/HEAD/OPTIONS/POST plus explicit 405 handling
  for PUT/PATCH/DELETE/TRACE/CONNECT, and a protocol-layer 501 for anything
  else. TRACE never reflects the request (no XST).
- No response ever grants cross-origin access: no ``Access-Control-*``
  headers on success, client errors, or method errors.

Class-based on purpose: the documented module-level test counts in
``tests/test_documented_test_counts.py`` must not drift.
"""

from __future__ import annotations

import http.client
import json
import threading
import unittest

from idkmesh.control_tower_ui import SAMPLE_REPORT, create_server
from idkmesh.local_ui_security import TOKEN_HEADER

# Methods the protocol layer maps explicitly. TRACE/CONNECT must never be
# answered by reflection or tunneling (XST / proxy abuse).
_WRITE_METHODS = ("PUT", "PATCH", "DELETE", "TRACE", "CONNECT")


def _start_server():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_server(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _raw_request(
    server,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    host: str | None = None,
):
    """Send one raw request and return ``(status, headers, body)``."""
    conn = http.client.HTTPConnection(
        "127.0.0.1", server.server_port, timeout=3
    )
    sent: dict[str, str] = dict(headers or {})
    if host is not None:
        sent["Host"] = host
    if body is not None:
        sent.setdefault("Content-Type", "application/json; charset=utf-8")
        sent.setdefault("Content-Length", str(len(body)))
    conn.request(method, path, body=body, headers=sent)
    response = conn.getresponse()
    payload = response.read()
    response_headers = {k.lower(): v for k, v in response.getheaders()}
    conn.close()
    return response.status, response_headers, payload


def _error_code(body: bytes) -> str | None:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    error = document.get("error")
    return error.get("code") if isinstance(error, dict) else None


class _ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.thread = _start_server()

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    @property
    def token(self) -> str:
        return self.server.ui_token


class AuthBypassMatrixTests(_ServerTestCase):
    """Every non-``TOKEN_HEADER`` transport must fail closed with 403."""

    def assert_rejected(self, status: int, headers: dict, body: bytes) -> None:
        self.assertEqual(status, 403, body)
        self.assertEqual(_error_code(body), "invalid_session_token")
        self.assertEqual(
            headers.get("content-type"), "application/json; charset=utf-8"
        )

    def test_positive_control_header_transport_works(self) -> None:
        # Without this, every negative case below could pass vacuously.
        status, _, body = _raw_request(
            self.server,
            "GET",
            "/api/v1/status",
            headers={TOKEN_HEADER: self.token},
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["ok"], True)

    def test_header_name_is_case_insensitive(self) -> None:
        # RFC 9110 section 5.1: header names are case-insensitive. The token
        # value stays exact, but the name must match in any casing.
        status, _, body = _raw_request(
            self.server,
            "GET",
            "/api/v1/status",
            headers={"x-idkmesh-ui-token": self.token},
        )
        self.assertEqual(status, 200, body)

    def test_token_in_query_string_is_not_authentication(self) -> None:
        for query in (
            f"?token={self.token}",
            f"?X-IDKMesh-UI-Token={self.token}",
        ):
            with self.subTest(query=query.split("=")[0]):
                status, headers, body = _raw_request(
                    self.server, "GET", f"/api/v1/status{query}"
                )
                self.assert_rejected(status, headers, body)

    def test_token_in_authorization_or_cookie_is_not_authentication(
        self,
    ) -> None:
        for header, value in (
            ("Authorization", f"Bearer {self.token}"),
            ("Authorization", f"Basic {self.token}"),
            ("Cookie", f"session={self.token}"),
        ):
            with self.subTest(header=header):
                status, headers, body = _raw_request(
                    self.server,
                    "GET",
                    "/api/v1/status",
                    headers={header: value},
                )
                self.assert_rejected(status, headers, body)

    def test_similar_header_names_are_not_authentication(self) -> None:
        for name in (
            "X-IDKMesh-Token",
            "X-IDKMesh-UI-Tokens",
            "X-IDKMesh-UI-Token-Extra",
            "X-UI-Token",
        ):
            with self.subTest(name=name):
                status, headers, body = _raw_request(
                    self.server,
                    "GET",
                    "/api/v1/status",
                    headers={name: self.token},
                )
                self.assert_rejected(status, headers, body)

    def test_empty_or_missing_header_is_rejected(self) -> None:
        for headers in ({}, {TOKEN_HEADER: ""}):
            with self.subTest(headers=headers):
                status, response_headers, body = _raw_request(
                    self.server, "GET", "/api/v1/status", headers=headers
                )
                self.assert_rejected(status, response_headers, body)

    def test_value_comparison_is_exact_and_case_sensitive(self) -> None:
        token = self.token
        self.assertNotEqual(token.swapcase(), token)
        for value in (token.swapcase(), token.upper(), token.lower()):
            with self.subTest(transform="case"):
                status, headers, body = _raw_request(
                    self.server,
                    "GET",
                    "/api/v1/status",
                    headers={TOKEN_HEADER: value},
                )
                self.assert_rejected(status, headers, body)

    def test_near_miss_values_are_rejected(self) -> None:
        token = self.token
        for value in (
            token[:-1],  # truncated
            token + "x",  # extended
            token + token,  # duplicated
            # Trailing whitespace survives the wire parser and is compared
            # verbatim. (A *leading* space cannot reach the handler: the
            # parser strips optional whitespace after the colon per RFC 9110
            # section 5.6.1, so " " + token is the same field value as token
            # and legitimately authenticates.)
            token + " ",
        ):
            with self.subTest(value=repr(value[:12])):
                status, headers, body = _raw_request(
                    self.server,
                    "GET",
                    "/api/v1/status",
                    headers={TOKEN_HEADER: value},
                )
                self.assert_rejected(status, headers, body)

    def test_hostile_header_values_fail_closed_not_crash(self) -> None:
        # Non-ASCII values reach the handler as latin-1 decoded str. The
        # token comparison must reject them with the normal 403 envelope,
        # never raise (an unhandled exception kills the connection and the
        # 403 contract) and never 500.
        for value in (
            self.token + "\u00e9",  # non-ASCII suffix (latin-1 encodable)
            "\u00e9" + self.token,
            "\u00e9" * 32,
            "A" * 8192,  # oversized junk
            "\x00" + self.token,
        ):
            # Wire-level CRLF inside a header value is structurally
            # impossible (it would end the header line) and the client
            # library refuses control characters outright, so header
            # smuggling itself belongs to the production-adapter smuggling
            # suite, not here.
            with self.subTest(value=repr(value[:12])):
                status, headers, body = _raw_request(
                    self.server,
                    "GET",
                    "/api/v1/status",
                    headers={TOKEN_HEADER: value},
                )
                self.assert_rejected(status, headers, body)

    def test_auth_precedes_content_negotiation(self) -> None:
        # Accept negotiation answers only authenticated callers; an
        # unauthenticated request with an unacceptable Accept must not learn
        # that its Accept was the problem.
        status, headers, body = _raw_request(
            self.server,
            "GET",
            "/api/v1/status",
            headers={
                TOKEN_HEADER: "wrong-token-value-0000000000000000",
                "Accept": "text/html",
            },
        )
        self.assert_rejected(status, headers, body)

    def test_auth_precedes_body_parsing_on_mutations(self) -> None:
        # A garbage body on the mutation endpoint must not produce a parse
        # error for an unauthenticated caller: no body-derived feedback.
        status, headers, body = _raw_request(
            self.server,
            "POST",
            "/api/v1/run-evidence/inspect",
            body=b"{not json at all",
            headers={
                TOKEN_HEADER: "wrong-token-value-0000000000000000",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        self.assert_rejected(status, headers, body)

    def test_version_gate_and_host_gate_precede_auth(self) -> None:
        # Documented ordering: unsupported API versions and non-loopback
        # Host headers are refused before token handling. Neither response
        # contains user data; both are pinned so the order is a decision.
        status, _, body = _raw_request(
            self.server, "GET", "/api/v2/status"
        )
        self.assertEqual(status, 404)
        self.assertEqual(_error_code(body), "unsupported_api_version")

        status, _, body = _raw_request(
            self.server, "GET", "/api/v1/status", host="evil.example"
        )
        self.assertEqual(status, 403)
        self.assertEqual(_error_code(body), "invalid_host")

    def test_health_endpoints_are_token_free_by_design(self) -> None:
        # Liveness/readiness probes carry no user data and are documented as
        # token-free (status document operations.liveness/readiness). Pinned
        # so "add auth everywhere" refactors do not break probes -- and so
        # they keep returning nothing sensitive without a token.
        for path in ("/healthz", "/readyz"):
            with self.subTest(path=path):
                status, _, body = _raw_request(self.server, "GET", path)
                self.assertIn(status, (200,))
                text = body.decode("utf-8")
                self.assertNotIn(self.token, text)


class MethodConfusionMatrixTests(_ServerTestCase):
    """Oracle-driven method matrix over the advertised endpoint map."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        status, _, body = _raw_request(
            cls.server,
            "GET",
            "/api/v1/status",
            headers={TOKEN_HEADER: cls.server.ui_token},
        )
        if status != 200:  # pragma: no cover - harness failure, not a contract
            raise RuntimeError(f"status endpoint unavailable: {status}")
        cls.endpoints = json.loads(body)["endpoints"]

    @staticmethod
    def _concrete_path(template: str) -> str:
        out = template
        for placeholder in ("{run_id}", "{work_unit_id}", "{project_id}"):
            out = out.replace(placeholder, "sample")
        return out

    def _advertised(self):
        for name, spec in sorted(self.endpoints.items()):
            method, _, path = spec.partition(" ")
            yield name, method.upper(), self._concrete_path(path)

    def test_advertised_method_passes_the_gates(self) -> None:
        for name, method, path in self._advertised():
            with self.subTest(endpoint=name, method=method):
                if path.endswith("/events/stream"):
                    # Opening the SSE stream blocks by design; its method
                    # map is covered by the wrong-method cases below.
                    continue
                kwargs: dict = {}
                if method == "POST":
                    kwargs["body"] = SAMPLE_REPORT.encode("utf-8")
                status, _, body = _raw_request(
                    self.server,
                    method,
                    path,
                    headers={TOKEN_HEADER: self.token},
                    **kwargs,
                )
                self.assertNotIn(
                    status,
                    (401, 403, 405),
                    f"{name} {method} {path} blocked at the gates: {body!r}",
                )

    def test_opposite_method_is_405_with_allow(self) -> None:
        opposite = {"GET": "POST", "POST": "GET"}
        for name, method, path in self._advertised():
            wrong = opposite[method]
            with self.subTest(endpoint=name, method=wrong):
                status, headers, body = _raw_request(
                    self.server,
                    wrong,
                    path,
                    headers={TOKEN_HEADER: self.token},
                    body=b"{}" if wrong == "POST" else None,
                )
                self.assertEqual(status, 405, body)
                self.assertEqual(_error_code(body), "method_not_allowed")
                self.assertIn(method, headers.get("allow", ""))

    def test_write_methods_are_405_everywhere(self) -> None:
        for name, method, path in self._advertised():
            for wrong in _WRITE_METHODS:
                with self.subTest(endpoint=name, method=wrong):
                    status, headers, body = _raw_request(
                        self.server,
                        wrong,
                        path,
                        headers={TOKEN_HEADER: self.token},
                    )
                    self.assertEqual(status, 405, body)
                    self.assertEqual(
                        _error_code(body), "method_not_allowed"
                    )
                    self.assertIn(method, headers.get("allow", ""))

    def test_trace_never_reflects_the_request(self) -> None:
        # XST: TRACE responses must not echo request headers back.
        status, _, body = _raw_request(
            self.server,
            "TRACE",
            "/api/v1/status",
            headers={
                TOKEN_HEADER: self.token,
                "X-Security-Matrix": "must-not-be-echoed",
            },
        )
        self.assertEqual(status, 405)
        self.assertNotIn(b"must-not-be-echoed", body)

    def test_unknown_methods_are_refused_by_the_protocol_layer(self) -> None:
        # do_<METHOD> dispatch: anything outside the mapped set (including
        # case variants of real methods) never reaches API logic at all.
        for method in ("FOO", "BREW", "get", "post", "Get"):
            with self.subTest(method=method):
                status, _, body = _raw_request(
                    self.server,
                    method,
                    "/api/v1/status",
                    headers={TOKEN_HEADER: self.token},
                )
                self.assertEqual(status, 501, body)
                # Protocol-layer refusal, not an API envelope that pretends
                # the endpoint exists.
                self.assertIsNone(_error_code(body))

    def test_stream_endpoint_rejects_everything_but_get(self) -> None:
        path = "/api/v1/events/stream"
        for wrong, allow in (
            ("HEAD", "GET"),
            ("POST", "GET"),
            ("PUT", "GET"),
            ("DELETE", "GET"),
        ):
            with self.subTest(method=wrong):
                status, headers, body = _raw_request(
                    self.server,
                    wrong,
                    path,
                    headers={TOKEN_HEADER: self.token},
                )
                self.assertEqual(status, 405, body)
                self.assertEqual(headers.get("allow"), allow)
                if wrong == "HEAD":
                    # HEAD responses carry headers only, by contract.
                    self.assertEqual(body, b"")
                else:
                    self.assertEqual(_error_code(body), "method_not_allowed")


class CrossOriginMutationTests(_ServerTestCase):
    """No response may grant cross-origin access; preflight is refused."""

    CANDIDATE_HEADERS = (
        "access-control-allow-origin",
        "access-control-allow-methods",
        "access-control-allow-headers",
        "access-control-allow-credentials",
    )

    def assert_no_cors_grants(self, headers: dict) -> None:
        for name in self.CANDIDATE_HEADERS:
            self.assertNotIn(name, headers, f"cross-origin grant: {name}")

    def test_success_and_error_responses_grant_no_cors(self) -> None:
        cases = (
            ("GET", "/api/v1/status", None),
            ("GET", "/api/v1/no-such-endpoint", None),
            ("POST", "/api/v1/runs", b"{}"),
        )
        for method, path, body in cases:
            with self.subTest(case=f"{method} {path}"):
                status, headers, _ = _raw_request(
                    self.server,
                    method,
                    path,
                    body=body,
                    headers={TOKEN_HEADER: self.token},
                )
                self.assert_no_cors_grants(headers)

    def test_unauthenticated_error_responses_grant_no_cors(self) -> None:
        status, headers, _ = _raw_request(self.server, "GET", "/api/v1/status")
        self.assertEqual(status, 403)
        self.assert_no_cors_grants(headers)

    def test_preflight_is_refused_without_a_token(self) -> None:
        # Preflight requests never carry custom headers (that is the point of
        # a preflight), so OPTIONS must answer without one -- and the answer
        # must refuse rather than authorize cross-origin use.
        status, headers, body = _raw_request(
            self.server,
            "OPTIONS",
            "/api/v1/run-evidence/inspect",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": TOKEN_HEADER,
            },
        )
        self.assertEqual(status, 405, body)
        self.assertEqual(_error_code(body), "preflight_not_supported")
        self.assertEqual(headers.get("allow"), "POST")
        self.assert_no_cors_grants(headers)

    def test_cross_site_simple_request_cannot_mutate(self) -> None:
        # CSRF: a cross-site "simple request" can set Cookie/Authorization
        # and text/plain bodies but never TOKEN_HEADER. The mutation endpoint
        # must reject it at auth, before any body handling.
        status, headers, body = _raw_request(
            self.server,
            "POST",
            "/api/v1/run-evidence/inspect",
            body=SAMPLE_REPORT.encode("utf-8"),
            headers={
                "Content-Type": "text/plain",
                "Cookie": f"session={self.token}",
                "Authorization": f"Bearer {self.token}",
                "Origin": "https://evil.example",
            },
        )
        self.assert_rejected_for_csrf(status, headers, body)

    def assert_rejected_for_csrf(
        self, status: int, headers: dict, body: bytes
    ) -> None:
        self.assertEqual(status, 403, body)
        self.assertEqual(_error_code(body), "invalid_session_token")
        self.assert_no_cors_grants(headers)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
