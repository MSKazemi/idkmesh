"""Tests for the local browser interface around idkmesh gate-audit."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from idkmesh import cli, gate_audit
from idkmesh.gate_audit_ui import SAMPLE_INPUT, create_server


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
    def setUp(self) -> None:
        self.server = create_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, body: str | None = None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3)
        headers = {}
        encoded = None
        if body is not None:
            encoded = body.encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Content-Length"] = str(len(encoded))
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        headers_out = dict(response.getheaders())
        conn.close()
        return response.status, headers_out, payload

    def test_home_is_a_self_contained_local_app(self) -> None:
        status, headers, body = self.request("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("IDKMesh · Gate Audit", text)
        self.assertIn("127.0.0.1", text)
        self.assertNotIn("<script src=", text)
        self.assertIn("Content-Security-Policy", headers)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_valid_matrix_returns_the_same_report_as_python_api(self) -> None:
        source = json.dumps(minimal_input())
        status, _, body = self.request("POST", "/api/audit", source)
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["report"], gate_audit.audit(minimal_input()))

    def test_contract_error_is_a_clean_400(self) -> None:
        data = minimal_input()
        del data["evidence_class"]
        status, _, body = self.request(
            "POST", "/api/audit", json.dumps(data))
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("evidence_class", payload["error"])
        self.assertIn("browser input", payload["error"])

    def test_builtin_example_is_valid(self) -> None:
        report = gate_audit.audit_text(SAMPLE_INPUT, source="built-in example")
        self.assertEqual(report["gate_id"], "local-demo")


class GuiCliTests(unittest.TestCase):
    def test_gui_command_starts_loopback_ui_without_browser_when_requested(self) -> None:
        with mock.patch(
            "idkmesh.gate_audit_ui.serve_gate_audit_ui"
        ) as serve:
            rc = cli.main(["gate-audit-ui", "--no-browser", "--port", "9123"])
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


if __name__ == "__main__":
    unittest.main()
