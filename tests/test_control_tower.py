"""Tests for the read-only Human Control Tower and local API."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh.control_tower_api import (
    ControlTowerInputError,
    build_snapshot,
    parse_report_text,
    status_document,
    validate_run_evidence_report,
)
from idkmesh.control_tower_ui import SAMPLE_REPORT, create_server
from idkmesh.local_ui_security import TOKEN_HEADER


def sample_report() -> dict:
    return json.loads(SAMPLE_REPORT)


class ControlTowerModelTests(unittest.TestCase):
    def test_sample_report_builds_human_attention_snapshot(self) -> None:
        report = sample_report()
        validate_run_evidence_report(report)
        snapshot = build_snapshot(report)

        self.assertEqual(snapshot["api_version"], "v1")
        self.assertEqual(
            snapshot["kind"], "idkmesh-control-tower-snapshot")
        self.assertEqual(snapshot["summary"]["attempt_count"], 2)
        self.assertTrue(snapshot["summary"]["verification_disagreement"])
        self.assertEqual(snapshot["human_decision"]["status"], "pending")
        self.assertFalse(snapshot["authority"]["merge"])

        codes = {item["code"] for item in snapshot["attention"]}
        self.assertIn("verification_disagreement", codes)
        self.assertIn("human_decision_pending", codes)

        event_types = {item["type"] for item in snapshot["timeline"]}
        self.assertIn("claim", event_types)
        self.assertIn("evidence", event_types)
        self.assertIn("recommendation", event_types)
        self.assertIn("authority", event_types)

    def test_report_that_grants_merge_authority_is_rejected(self) -> None:
        report = sample_report()
        report["authority"]["merge"] = True
        with self.assertRaises(ControlTowerInputError) as ctx:
            validate_run_evidence_report(report)
        self.assertIn("read-only", str(ctx.exception))

    def test_summary_is_recomputed_not_trusted(self) -> None:
        report = sample_report()
        report["summary"]["supported"] = 2
        with self.assertRaises(ControlTowerInputError) as ctx:
            validate_run_evidence_report(report)
        self.assertIn("recomputed value", str(ctx.exception))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        text = SAMPLE_REPORT.replace(
            '"run_id": "two-attempt-evaluator-plan-good-vs-bad"',
            (
                '"run_id": "first", '
                '"run_id": "two-attempt-evaluator-plan-good-vs-bad"'
            ),
            1,
        )
        with self.assertRaises(ControlTowerInputError) as ctx:
            parse_report_text(text, source="test report")
        self.assertIn("duplicate JSON key", str(ctx.exception))
        self.assertIn("test report", str(ctx.exception))

    def test_status_document_is_explicitly_non_actuating(self) -> None:
        status = status_document()
        self.assertEqual(status["api_version"], "v1")
        self.assertTrue(status["capabilities"]["run_evidence_inspection"])
        self.assertFalse(status["capabilities"]["worker_execution"])
        self.assertFalse(status["capabilities"]["canonical_state_write"])
        self.assertFalse(status["capabilities"]["merge"])


class ControlTowerServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
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
        body: str | None = None,
        *,
        token: bool = False,
        content_type: str = "application/json; charset=utf-8",
    ):
        conn = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        headers: dict[str, str] = {}
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
        response_headers = dict(response.getheaders())
        conn.close()
        return response.status, response_headers, payload

    def test_home_is_self_contained_control_tower(self) -> None:
        status, headers, body = self.request("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("IDKMesh Control Tower", text)
        self.assertIn("Human attention", text)
        self.assertIn("Run Evidence", text)
        self.assertIn("Audit Timeline", text)
        self.assertIn("Claim ≠ evidence", text)
        self.assertNotIn("<script src=", text)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", headers)

    def test_status_api_requires_session_token(self) -> None:
        status, _, body = self.request("GET", "/api/v1/status")
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertEqual(
            payload["error"]["code"], "invalid_session_token")

    def test_status_api_describes_versioned_endpoints(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/status", token=True)
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(
            payload["endpoints"]["inspect_run_evidence"],
            "POST /api/v1/run-evidence/inspect",
        )
        self.assertFalse(payload["capabilities"]["merge"])

    def test_inspect_api_returns_snapshot_not_selection(self) -> None:
        status, _, body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        snapshot = payload["snapshot"]
        self.assertEqual(snapshot["summary"]["supported"], 1)
        self.assertEqual(snapshot["summary"]["rejected"], 1)
        self.assertTrue(snapshot["summary"]["verification_disagreement"])
        self.assertIsNone(
            snapshot["human_decision"]["selected_attempt_id"])
        self.assertFalse(snapshot["authority"]["automatic_candidate_selection"])

    def test_invalid_report_returns_structured_error(self) -> None:
        report = sample_report()
        report["authority"]["git_push"] = True
        status, _, body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            json.dumps(report),
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["code"], "invalid_run_evidence")

    def test_api_requires_json_content_type(self) -> None:
        status, _, body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
            content_type="text/plain",
        )
        payload = json.loads(body)
        self.assertEqual(status, 415)
        self.assertEqual(
            payload["error"]["code"], "unsupported_media_type")

    def test_non_loopback_host_header_is_rejected(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        conn.putrequest("GET", "/", skip_host=True)
        conn.putheader("Host", "example.invalid")
        conn.endheaders()
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        self.assertEqual(response.status, 403)
        self.assertEqual(payload["error"]["code"], "invalid_host")

    def test_cross_origin_preflight_is_not_supported(self) -> None:
        status, _, body = self.request(
            "OPTIONS", "/api/v1/run-evidence/inspect")
        payload = json.loads(body)
        self.assertEqual(status, 405)
        self.assertEqual(
            payload["error"]["code"], "preflight_not_supported")


class ControlTowerCliTests(unittest.TestCase):
    def test_control_tower_launches_without_browser(self) -> None:
        with mock.patch(
            "idkmesh.control_tower_ui.serve_control_tower"
        ) as serve:
            rc = cli.main(
                ["control-tower", "--no-browser", "--port", "9124"])
        self.assertEqual(rc, 0)
        serve.assert_called_once_with(
            None,
            port=9124,
            open_browser=False,
        )

    def test_control_tower_preloads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")
            with mock.patch(
                "idkmesh.control_tower_ui.serve_control_tower"
            ) as serve:
                rc = cli.main(
                    ["control-tower", str(path), "--no-browser"])
        self.assertEqual(rc, 0)
        serve.assert_called_once_with(
            SAMPLE_REPORT,
            port=8770,
            open_browser=False,
        )

    def test_control_tower_rejects_invalid_port(self) -> None:
        with mock.patch("idkmesh.cli._fail", return_value=2) as fail:
            rc = cli.main(
                ["control-tower", "--port", "70000"])
        self.assertEqual(rc, 2)
        fail.assert_called_once_with(
            "--port must be between 0 and 65535")


if __name__ == "__main__":
    unittest.main()
