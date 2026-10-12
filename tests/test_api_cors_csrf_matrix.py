"""Cross-origin delta matrix for IDKMesh local UI mutations (issue #745).

``tests/test_api_security_matrix.py`` already pins the Control Tower's CORS
posture (no ``Access-Control-Allow-*`` grants, preflight refusal, cross-site
simple-request rejection) and the gate-audit token/Host guards. This module
adds the coverage that suite does not have, as one contract across the
remaining surface:

- the read-only steward dashboards (history and report) refuse every write
  verb and every preflight under a hostile ``Origin``, and grant no CORS
  header of any kind;
- the gate-audit mutation's CORS posture specifically (preflight refusal, no
  grants on success or refusal, simple content types refused);
- the Control Tower's JSON-only mutation gate: a browser-simple content type
  is refused *even with a valid session token*, so no simple request can ever
  shape a mutation;
- ``Origin: null`` is not a credential on the mutation route;
- no response reflects the attacker's ``Origin`` value into any header, and
  refusal responses keep the browser-isolation headers
  (``Cross-Origin-Resource-Policy``, ``X-Frame-Options``, CSP
  ``form-action 'none'``).

The checks look for *any* ``Access-Control-*`` header rather than only the
``-Allow`` family, so a future ``-Expose-`` or ``-Max-Age`` grant is caught
too.

All probes run against the real loopback servers, in the harness shape the
other local-UI suites use.
"""

from __future__ import annotations

import http.client
import json
import threading
import unittest

from idkmesh.control_tower_ui import create_server as create_control_tower
from idkmesh.gate_audit_ui import SAMPLE_INPUT, create_server as create_gate_audit
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.steward_history_ui import create_server as create_history
from idkmesh.steward_report_ui import create_server as create_report

EVIL_ORIGIN = "https://evil.example"
NULL_ORIGIN = "null"

# A browser "simple request" cannot carry a custom header or a JSON content
# type; these are the shapes a CSRF attacker can send without a preflight.
SIMPLE_CONTENT_TYPES = (
    "application/x-www-form-urlencoded",
    "text/plain",
)

INSPECT_PATH = "/api/v1/run-evidence/inspect"
AUDIT_PATH = "/api/audit"
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _run_report() -> dict:
    """Minimal valid steward report (mirrors the steward UI test fixture)."""
    from idkmesh import steward_report

    return {
        "schema": steward_report.SCHEMA_ID,
        "repository": "MSKazemi/idkmesh",
        "generated_at": "2026-09-23T10:00:00Z",
        "status": "completed",
        "dry_run": False,
        "policy": {"path": "config/auto-draft-pr.json", "sha256": "a" * 64},
        "provenance": {
            "workflow": "Auto Draft PR Steward",
            "run_id": "100",
            "run_attempt": "1",
            "trusted_head_sha": "b" * 40,
        },
        "authority": dict(steward_report.EXPECTED_AUTHORITY),
        "candidate_count": 0,
        "rate_limit_remaining": 4000,
        "blocked_reason": None,
        "summary": {"planned": 0, "created": 0, "skipped": 0},
        "planned": [],
        "created": [],
        "skipped": [],
    }


class _UiServerCase(unittest.TestCase):
    """Loopback server harness shared by every local UI in the matrix."""

    @classmethod
    def _build_server(cls):  # pragma: no cover - overridden
        raise NotImplementedError

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = cls._build_server()
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        try:
            data = body.encode("utf-8") if body is not None else None
            conn.request(method, path, body=data, headers=headers or {})
            response = conn.getresponse()
            lowered = {
                name.lower(): value for name, value in response.getheaders()
            }
            return response.status, lowered, response.read()
        finally:
            conn.close()

    # ---- shared assertions ----------------------------------------------

    def assert_no_cors_grant(
        self, headers: dict[str, str], context: str
    ) -> None:
        for name in headers:
            self.assertFalse(
                name.startswith("access-control-"),
                f"{context}: unexpected CORS grant header {name!r}",
            )

    def assert_origin_not_reflected(
        self, headers: dict[str, str], origin: str, context: str
    ) -> None:
        for name, value in headers.items():
            self.assertNotIn(
                origin,
                value,
                f"{context}: Origin value reflected into {name!r}",
            )

    def assert_isolation(self, headers: dict[str, str], context: str) -> None:
        self.assertEqual(
            headers.get("cross-origin-resource-policy"),
            "same-origin",
            f"{context}: CORP weakened",
        )
        self.assertEqual(
            headers.get("x-frame-options"), "DENY", f"{context}: XFO weakened"
        )
        self.assertIn(
            "form-action 'none'",
            headers.get("content-security-policy", ""),
            f"{context}: CSP form-action weakened",
        )

    def assert_simple_refusal(
        self,
        method: str,
        path: str,
        content_type: str,
        *,
        token: str | None = None,
    ) -> None:
        """A browser-simple request must never achieve a mutation."""
        headers = {"Origin": EVIL_ORIGIN, "Content-Type": content_type}
        if token is not None:
            headers[TOKEN_HEADER] = token
        status, resp_headers, _ = self.request(
            method, path, headers=headers, body="a=1"
        )
        context = f"{method} {path} ({content_type})"
        self.assertGreaterEqual(
            status, 400, f"{context}: simple request was not refused"
        )
        self.assertLess(status, 500, f"{context}: refusal must be 4xx")
        self.assert_no_cors_grant(resp_headers, context)
        self.assert_origin_not_reflected(resp_headers, EVIL_ORIGIN, context)
        self.assert_isolation(resp_headers, context)

    def preflight_headers(self, method: str) -> dict[str, str]:
        return {
            "Origin": EVIL_ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": TOKEN_HEADER.lower(),
        }


class ControlTowerCorsDeltaTests(_UiServerCase):
    """The JSON-only mutation gate and reflection gaps the security matrix
    does not pin."""

    @classmethod
    def _build_server(cls):
        return create_control_tower(port=0)

    @property
    def token(self) -> str:
        return self.server.ui_token

    def test_simple_content_types_refused_even_with_token(self) -> None:
        """A simple-content-type request must never be a valid mutation.

        Even with the exact session token, form/text media types are refused,
        so nothing a browser can send without a preflight is ever valid.
        """
        for content_type in SIMPLE_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                self.assert_simple_refusal(
                    "POST", INSPECT_PATH, content_type, token=self.token
                )

    def test_null_origin_is_not_a_credential_on_the_mutation(self) -> None:
        status, headers, _ = self.request(
            "POST",
            INSPECT_PATH,
            headers={
                "Origin": NULL_ORIGIN,
                "Content-Type": "application/json",
            },
            body="{}",
        )
        self.assertEqual(status, 403)
        self.assert_origin_not_reflected(headers, NULL_ORIGIN, "null-origin")

    def test_no_cors_header_of_any_kind_and_no_origin_reflection(self) -> None:
        """Beyond ``-Allow``: no ``-Expose``/``-Max-Age`` grant either."""
        probes = (
            ("GET", "/api/v1/status", {TOKEN_HEADER: self.token}, None),
            ("POST", INSPECT_PATH, {}, "{}"),
            ("OPTIONS", INSPECT_PATH, self.preflight_headers("POST"), None),
        )
        for method, path, extra, body in probes:
            with self.subTest(method=method, path=path):
                headers = {"Origin": EVIL_ORIGIN, **extra}
                status, resp_headers, _ = self.request(
                    method, path, headers=headers, body=body
                )
                self.assert_no_cors_grant(
                    resp_headers, f"{method} {path} -> {status}"
                )
                self.assert_origin_not_reflected(
                    resp_headers, EVIL_ORIGIN, f"{method} {path} -> {status}"
                )


class GateAuditCorsDeltaTests(_UiServerCase):
    """The audit UI's CORS posture; its token/Host guards are pinned in
    ``test_api_security_matrix.py``."""

    @classmethod
    def _build_server(cls):
        return create_gate_audit(port=0)

    def test_preflight_is_refused(self) -> None:
        status, headers, body = self.request(
            "OPTIONS", AUDIT_PATH, headers=self.preflight_headers("POST")
        )
        self.assertEqual(status, 405)
        self.assertIn(b"preflight is not supported", body)
        self.assert_no_cors_grant(headers, "preflight")
        self.assert_origin_not_reflected(headers, EVIL_ORIGIN, "preflight")

    def test_no_cors_grant_on_success_and_refusal(self) -> None:
        probes = (
            ("GET", "/healthz", {}, None),
            (
                "POST",
                AUDIT_PATH,
                {"Content-Type": "application/json"},
                json.dumps(SAMPLE_INPUT),
            ),
            ("POST", AUDIT_PATH, {}, "{}"),
        )
        for method, path, extra, body in probes:
            with self.subTest(method=method, path=path):
                headers = {"Origin": EVIL_ORIGIN, **extra}
                status, resp_headers, _ = self.request(
                    method, path, headers=headers, body=body
                )
                self.assert_no_cors_grant(
                    resp_headers, f"{method} {path} -> {status}"
                )
                self.assert_origin_not_reflected(
                    resp_headers, EVIL_ORIGIN, f"{method} {path} -> {status}"
                )

    def test_simple_content_types_cannot_mutate_without_token(self) -> None:
        for content_type in SIMPLE_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                self.assert_simple_refusal("POST", AUDIT_PATH, content_type)

    def test_simple_content_types_refused_even_with_token(self) -> None:
        token = self.server.ui_token
        for content_type in SIMPLE_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                status, headers, _ = self.request(
                    "POST",
                    AUDIT_PATH,
                    headers={
                        "Origin": EVIL_ORIGIN,
                        "Content-Type": content_type,
                        TOKEN_HEADER: token,
                    },
                    body=json.dumps(SAMPLE_INPUT),
                )
                self.assertGreaterEqual(
                    status, 400, f"{content_type}: mutation was not refused"
                )
                self.assert_no_cors_grant(headers, content_type)
                self.assert_origin_not_reflected(
                    headers, EVIL_ORIGIN, content_type
                )


class _ReadOnlyDashboardAssertions:
    """The write-refusal contract shared by both read-only steward UIs."""

    def test_every_write_method_is_refused(self) -> None:
        for method in WRITE_METHODS:
            with self.subTest(method=method):
                status, headers, _ = self.request(
                    method,
                    "/",
                    headers={
                        "Origin": EVIL_ORIGIN,
                        "Content-Type": "application/json",
                        TOKEN_HEADER: "not-a-real-token",
                    },
                    body="{}",
                )
                self.assertEqual(status, 405)
                self.assert_no_cors_grant(headers, f"{method} /")
                self.assert_origin_not_reflected(
                    headers, EVIL_ORIGIN, f"{method} /"
                )
                self.assert_isolation(headers, f"{method} /")

    def test_preflight_is_refused(self) -> None:
        status, headers, body = self.request(
            "OPTIONS", "/", headers=self.preflight_headers("POST")
        )
        self.assertEqual(status, 405)
        self.assertIn(b"preflight is not supported", body)
        self.assert_no_cors_grant(headers, "preflight")
        self.assert_origin_not_reflected(headers, EVIL_ORIGIN, "preflight")

    def test_get_grants_nothing_cross_origin(self) -> None:
        status, headers, _ = self.request(
            "GET", "/", headers={"Origin": EVIL_ORIGIN}
        )
        self.assertEqual(status, 200)
        self.assert_no_cors_grant(headers, "GET /")
        self.assert_origin_not_reflected(headers, EVIL_ORIGIN, "GET /")
        self.assert_isolation(headers, "GET /")


class StewardHistoryCorsDeltaTests(
    _ReadOnlyDashboardAssertions, _UiServerCase
):
    @classmethod
    def _build_server(cls):
        from pathlib import Path

        from idkmesh import steward_history

        report = _run_report()
        history = steward_history.build_history(
            [(Path("run/steward-report.json"), report)]
        )
        return create_history(history, port=0)


class StewardReportCorsDeltaTests(
    _ReadOnlyDashboardAssertions, _UiServerCase
):
    @classmethod
    def _build_server(cls):
        return create_report(_run_report(), port=0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
