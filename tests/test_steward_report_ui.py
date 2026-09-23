"""Tests for the loopback-only Steward Report dashboard."""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from idkmesh import cli, steward_report
from idkmesh.steward_report_ui import create_server, render_dashboard


def valid_report(*, branch: str = "feat/dashboard") -> dict:
    planned = {
        "branch": branch,
        "base": "main",
        "head_sha": "a" * 40,
        "ahead_by": 2,
        "behind_by": 0,
    }
    return {
        "schema": steward_report.SCHEMA_ID,
        "repository": "MSKazemi/idkmesh",
        "generated_at": "2026-09-22T16:00:00Z",
        "status": "completed",
        "dry_run": False,
        "policy": {
            "path": "config/auto-draft-pr.json",
            "sha256": "b" * 64,
        },
        "provenance": {
            "workflow": "Auto Draft PR Steward",
            "run_id": "123",
            "run_attempt": "1",
            "trusted_head_sha": "c" * 40,
        },
        "authority": dict(steward_report.EXPECTED_AUTHORITY),
        "candidate_count": 1,
        "rate_limit_remaining": 4321,
        "blocked_reason": None,
        "summary": {"planned": 1, "created": 1, "skipped": 0},
        "planned": [planned],
        "created": [
            {
                **planned,
                "number": 701,
                "url": "https://github.com/MSKazemi/idkmesh/pull/701",
            }
        ],
        "skipped": [],
    }


class DashboardRenderTests(unittest.TestCase):
    def test_dashboard_is_self_contained_and_read_only_in_copy(self):
        page = render_dashboard(valid_report())
        self.assertIn("IDKMesh / Steward Report", page)
        self.assertIn("LOCAL · READ ONLY · 127.0.0.1", page)
        self.assertIn("Candidate lifecycle", page)
        self.assertIn("Created Draft PRs", page)
        self.assertIn("Run provenance", page)
        self.assertIn("Raw validated report JSON", page)
        self.assertIn("no mutation endpoint", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<link ", page)
        self.assertNotIn("https://fonts.", page)

    def test_dashboard_escapes_branch_text_and_raw_json(self):
        hostile = "feat/<img src=x onerror=alert(1)>|#123"
        page = render_dashboard(valid_report(branch=hostile))
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertIn("feat/", page)

    def test_dashboard_shows_authority_as_not_allowed(self):
        page = render_dashboard(valid_report())
        self.assertIn("Create Draft PR", page)
        self.assertIn("Merge", page)
        self.assertIn("not allowed", page)


class DashboardServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(valid_report(), port=0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(
        self,
        method: str,
        path: str = "/",
        *,
        host: str | None = None,
    ):
        conn = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        if host is None:
            conn.request(method, path)
        else:
            conn.putrequest(method, path, skip_host=True)
            conn.putheader("Host", host)
            conn.endheaders()
        response = conn.getresponse()
        payload = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, headers, payload

    def test_server_binds_only_to_ipv4_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_home_has_security_headers_and_no_external_script(self):
        status, headers, body = self.request("GET")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("IDKMesh Steward Report", text)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertNotIn("<script", text)

    def test_non_loopback_host_is_rejected(self):
        status, _, body = self.request("GET", host="example.invalid")
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertIn("loopback", payload["error"])

    def test_host_header_userinfo_trick_is_rejected(self):
        status, _, body = self.request(
            "GET",
            host="example.invalid@127.0.0.1",
        )
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertIn("loopback", payload["error"])

    def test_mutation_methods_are_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, _, body = self.request(method)
                payload = json.loads(body)
                self.assertEqual(status, 405)
                self.assertIn("read-only", payload["error"])

    def test_cross_origin_preflight_is_not_supported(self):
        status, _, body = self.request("OPTIONS")
        payload = json.loads(body)
        self.assertEqual(status, 405)
        self.assertIn("preflight", payload["error"])

    def test_unknown_path_is_404(self):
        status, _, body = self.request("GET", "/api/mutate")
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not found")


class DashboardCliTests(unittest.TestCase):
    def _write(self, directory: str, report: dict) -> Path:
        path = Path(directory) / "steward-report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_cli_starts_dashboard_with_validated_report(self):
        report = valid_report()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, report)
            with mock.patch(
                "idkmesh.steward_report_ui.serve_steward_report_ui"
            ) as serve:
                rc = cli.main(
                    [
                        "steward-report-ui",
                        str(path),
                        "--no-browser",
                        "--port",
                        "9124",
                    ]
                )
        self.assertEqual(rc, 0)
        serve.assert_called_once_with(
            report,
            port=9124,
            open_browser=False,
        )

    def test_cli_rejects_out_of_range_port_before_serving(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, valid_report())
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = cli.main(
                    ["steward-report-ui", str(path), "--port", "70000"]
                )
        self.assertEqual(rc, 2)
        self.assertIn("--port must be between 0 and 65535", stderr.getvalue())

    def test_cli_rejects_invalid_report_without_starting_server(self):
        report = valid_report()
        report["authority"]["merge"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, report)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch(
                "idkmesh.steward_report_ui.serve_steward_report_ui"
            ) as serve, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(["steward-report-ui", str(path), "--no-browser"])
        self.assertEqual(rc, 2)
        serve.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("authority block", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
