"""Tests for the local browser interface around idkmesh gate-audit."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from idkmesh import cli, gate_audit
from idkmesh.gate_audit_ui import (
    MAX_BODY_BYTES,
    SAMPLE_INPUT,
    TOKEN_HEADER,
    create_server,
)


def minimal_input() -> dict:
    return {
        "gate_id": "ui-test",
        "evidence_class": "synthetic",
        "candidates": [
            {"id": "c1", "ground_truth": "accept"},
            {"id": "c2", "ground_truth": "accept"},
            {"id": "c3", "ground_truth": "reject"},
            {"id": "c4", "ground_truth": "reject"},
        ],
        "verifiers": [
            {
                "id": "v1",
                "verdicts": {
                    "c1": "accept",
                    "c2": "accept",
                    "c3": "reject",
                    "c4": "accept",
                },
            },
            {
                "id": "v2",
                "verdicts": {
                    "c1": "accept",
                    "c2": "reject",
                    "c3": "reject",
                    "c4": "reject",
                },
            },
            {
                "id": "v3",
                "verdicts": {
                    "c1": "accept",
                    "c2": "accept",
                    "c3": "accept",
                    "c4": "reject",
                },
            },
        ],
    }


class AuditTextTests(unittest.TestCase):
    def test_text_api_reuses_the_normal_audit_contract(self) -> None:
        data = minimal_input()
        expected = gate_audit.audit(data)
        actual = gate_audit.audit_text(json.dumps(data), source="test input")
        self.assertEqual(actual, expected)

    def test_text_api_rejects_duplicate_json_keys(self) -> None:
        source = json.dumps(minimal_input()).replace(
            '"gate_id": "ui-test"',
            '"gate_id": "first", "gate_id": "second"',
            1,
        )
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_text(source, source="browser input")
        self.assertIn("browser input", str(ctx.exception))
        self.assertIn("duplicate JSON key", str(ctx.exception))


class LocalUIServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True)
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
        body: str | None = None,
        *,
        token: bool = False,
        content_type: str = "application/json; charset=utf-8",
    ):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3)
        headers = {}
        encoded = None
        if body is not None:
            encoded = body.encode("utf-8")
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(encoded))
        if token:
            headers[TOKEN_HEADER] = self.server.ui_token
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        headers_out = dict(response.getheaders())
        conn.close()
        return response.status, headers_out, payload

    def test_server_is_bound_only_to_loopback(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_home_is_a_self_contained_dashboard(self) -> None:
        status, headers, body = self.request("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("IDKMesh Gate Audit", text)
        self.assertIn("127.0.0.1", text)
        self.assertIn("Verifier detail", text)
        self.assertIn("Markdown ↓", text)
        self.assertIn("Ctrl/Cmd + Enter", text)
        self.assertNotIn("<script src=", text)
        self.assertIn("Content-Security-Policy", headers)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")

    def test_valid_matrix_returns_report_and_markdown(self) -> None:
        source = json.dumps(minimal_input())
        status, _, body = self.request(
            "POST", "/api/audit", source, token=True)
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["report"], gate_audit.audit(minimal_input()))
        self.assertIn("# Gate audit: ui-test", payload["markdown"])

    def test_api_requires_the_per_session_token(self) -> None:
        status, _, body = self.request(
            "POST", "/api/audit", json.dumps(minimal_input()))
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertFalse(payload["ok"])
        self.assertIn("session token", payload["error"])

    def test_api_requires_application_json(self) -> None:
        status, _, body = self.request(
            "POST",
            "/api/audit",
            json.dumps(minimal_input()),
            token=True,
            content_type="text/plain",
        )
        payload = json.loads(body)
        self.assertEqual(status, 415)
        self.assertIn("application/json", payload["error"])

    def test_oversized_request_is_rejected_before_body_read(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3)
        conn.putrequest("POST", "/api/audit")
        conn.putheader("Content-Type", "application/json")
        conn.putheader(TOKEN_HEADER, self.server.ui_token)
        conn.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
        conn.endheaders()
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        self.assertEqual(response.status, 413)
        self.assertIn("2 MiB", payload["error"])

    def test_contract_error_is_a_clean_400(self) -> None:
        data = minimal_input()
        del data["evidence_class"]
        status, _, body = self.request(
            "POST", "/api/audit", json.dumps(data), token=True)
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("evidence_class", payload["error"])
        self.assertIn("browser input", payload["error"])

    def test_non_loopback_host_header_is_rejected(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3)
        conn.putrequest("GET", "/", skip_host=True)
        conn.putheader("Host", "example.invalid")
        conn.endheaders()
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        self.assertEqual(response.status, 403)
        self.assertIn("loopback", payload["error"])

    def test_cross_origin_preflight_is_not_supported(self) -> None:
        status, _, body = self.request("OPTIONS", "/api/audit")
        payload = json.loads(body)
        self.assertEqual(status, 405)
        self.assertIn("preflight", payload["error"])

    def test_builtin_example_is_valid(self) -> None:
        report = gate_audit.audit_text(
            SAMPLE_INPUT, source="built-in example")
        self.assertEqual(report["gate_id"], "local-demo")


class GuiCliTests(unittest.TestCase):
    def test_gui_command_starts_loopback_ui_without_browser_when_requested(self) -> None:
        with mock.patch(
            "idkmesh.gate_audit_ui.serve_gate_audit_ui"
        ) as serve:
            rc = cli.main(
                ["gate-audit-ui", "--no-browser", "--port", "9123"])
        self.assertEqual(rc, 0)
        serve.assert_called_once_with(
            None, port=9123, open_browser=False)

    def test_gui_command_can_preload_an_input_file(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "votes.json"
            content = json.dumps(minimal_input(), indent=2)
            path.write_text(content, encoding="utf-8")
            with mock.patch(
                "idkmesh.gate_audit_ui.serve_gate_audit_ui"
            ) as serve:
                rc = cli.main(
                    ["gate-audit-ui", str(path), "--no-browser"])
        self.assertEqual(rc, 0)
        serve.assert_called_once_with(
            content, port=8765, open_browser=False)

    def test_gui_command_rejects_out_of_range_port(self) -> None:
        with mock.patch("idkmesh.cli._fail", return_value=2) as fail:
            rc = cli.main(["gate-audit-ui", "--port", "70000"])
        self.assertEqual(rc, 2)
        fail.assert_called_once_with("--port must be between 0 and 65535")


if __name__ == "__main__":
    unittest.main()
