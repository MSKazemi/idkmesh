"""Tests for the loopback-only Steward History dashboard."""

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

from idkmesh import cli, steward_history, steward_report
from idkmesh.steward_history_ui import create_server, render_dashboard


def run_report(
    *,
    repository: str = "MSKazemi/idkmesh",
    generated_at: str = "2026-09-23T10:00:00Z",
    run_id: str = "100",
    status: str = "completed",
) -> dict:
    blocked_reason = None
    candidate_count: int | None = 0
    api: int | None = 4000
    if status == "blocked":
        blocked_reason = "github_api_budget_low"
        candidate_count = None
    elif status == "disabled":
        blocked_reason = "policy_disabled"
        candidate_count = None
        api = None

    return {
        "schema": steward_report.SCHEMA_ID,
        "repository": repository,
        "generated_at": generated_at,
        "status": status,
        "dry_run": False,
        "policy": {
            "path": "config/auto-draft-pr.json",
            "sha256": "a" * 64,
        },
        "provenance": {
            "workflow": "Auto Draft PR Steward",
            "run_id": run_id,
            "run_attempt": "1",
            "trusted_head_sha": "b" * 40,
        },
        "authority": dict(steward_report.EXPECTED_AUTHORITY),
        "candidate_count": candidate_count,
        "rate_limit_remaining": api,
        "blocked_reason": blocked_reason,
        "summary": {"planned": 0, "created": 0, "skipped": 0},
        "planned": [],
        "created": [],
        "skipped": [],
    }


def history(*, hostile_source: str | None = None) -> dict:
    source = Path(hostile_source or "run/steward-report.json")
    reports = [
        (
            source,
            run_report(
                generated_at="2026-09-23T10:00:00Z",
                run_id="100",
            ),
        ),
        (
            Path("blocked/steward-report.json"),
            run_report(
                generated_at="2026-09-23T11:00:00Z",
                run_id="101",
                status="blocked",
            ),
        ),
    ]
    return steward_history.build_history(reports)


class StewardHistoryDashboardRenderTests(unittest.TestCase):
    def test_dashboard_is_self_contained_and_descriptive(self):
        page = render_dashboard(history())
        self.assertIn("IDKMesh / Steward History", page)
        self.assertIn("How is the steward behaving over time?", page)
        self.assertIn("Run timeline", page)
        self.assertIn("Capacity &amp; policy", page)
        self.assertIn("Descriptive only:", page)
        self.assertIn("no mutation endpoint", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<link ", page)
        self.assertNotIn("https://fonts.", page)

    def test_dashboard_escapes_source_paths(self):
        page = render_dashboard(
            history(hostile_source="run/<img src=x onerror=alert(1)>.json")
        )
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)

    def test_dashboard_surfaces_status_api_and_policy_counts(self):
        page = render_dashboard(history())
        self.assertIn("validated reports", page)
        self.assertIn("blocked runs", page)
        self.assertIn("Minimum remaining", page)
        self.assertIn("Distinct policies", page)
        self.assertIn("github_api_budget_low", page)
        self.assertIn("Input set digest", page)
        self.assertIn("Report digest", page)


    def test_dashboard_rejects_tampered_history(self):
        tampered = history()
        tampered["status_counts"]["completed"] += 1
        with self.assertRaisesRegex(
            steward_history.StewardHistoryInputError,
            "status_counts.completed",
        ):
            render_dashboard(tampered)

    def test_dashboard_rejects_tampered_integrity_digest(self):
        tampered = history()
        tampered["integrity"]["input_set_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            steward_history.StewardHistoryInputError,
            "does not match run evidence",
        ):
            render_dashboard(tampered)


class StewardHistoryDashboardServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(history(), port=0)
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

    def test_home_has_security_headers(self):
        status, headers, body = self.request("GET")
        page = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("IDKMesh Steward History", page)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")

    def test_non_loopback_and_userinfo_hosts_are_rejected(self):
        for host in ("example.invalid", "example.invalid@127.0.0.1"):
            with self.subTest(host=host):
                status, _, body = self.request("GET", host=host)
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

    def test_preflight_and_unknown_paths_are_rejected(self):
        status, _, body = self.request("OPTIONS")
        self.assertEqual(status, 405)
        self.assertIn("preflight", json.loads(body)["error"])

        status, _, body = self.request("GET", "/api/live")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not found")


class StewardHistoryDashboardCliTests(unittest.TestCase):
    def _write_report(
        self,
        root: Path,
        directory: str,
        payload: dict,
    ) -> None:
        target = root / directory
        target.mkdir()
        (target / steward_history.REPORT_FILENAME).write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def test_cli_starts_dashboard_from_validated_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_report(root, "one", run_report())
            with mock.patch(
                "idkmesh.steward_history_ui.serve_steward_history_ui"
            ) as serve:
                rc = cli.main(
                    [
                        "steward-history-ui",
                        str(root),
                        "--port",
                        "9127",
                        "--no-browser",
                    ]
                )
        self.assertEqual(rc, 0)
        serve.assert_called_once()
        args, kwargs = serve.call_args
        self.assertEqual(args[0]["report_count"], 1)
        self.assertEqual(kwargs, {"port": 9127, "open_browser": False})

    def test_cli_rejects_bad_port_before_loading_history(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = cli.main(
                ["steward-history-ui", "/does/not/matter", "--port", "70000"]
            )
        self.assertEqual(rc, 2)
        self.assertIn("--port must be between 0 and 65535", stderr.getvalue())

    def test_cli_rejects_mixed_repositories_before_server_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_report(
                root,
                "one",
                run_report(run_id="1"),
            )
            self._write_report(
                root,
                "two",
                run_report(
                    repository="someone/else",
                    generated_at="2026-09-23T11:00:00Z",
                    run_id="2",
                ),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch(
                "idkmesh.steward_history_ui.serve_steward_history_ui"
            ) as serve, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(
                    ["steward-history-ui", str(root), "--no-browser"]
                )
        self.assertEqual(rc, 2)
        serve.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("same repository", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
