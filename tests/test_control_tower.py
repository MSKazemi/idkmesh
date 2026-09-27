"""Tests for the read-only Human Control Tower and local API."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from idkmesh import cli
from idkmesh.control_tower_api import (
    ControlTowerInputError,
    build_snapshot,
    canonical_digest,
    error_document,
    openapi_document,
    parse_report_text,
    status_document,
    success_document,
    validate_run_evidence_report,
)
from idkmesh.control_tower_ui import (
    SAMPLE_REPORT,
    TOKEN_ENV,
    create_server,
)
from idkmesh.local_ui_security import MAX_BODY_BYTES, TOKEN_HEADER, is_loopback_host


def sample_report() -> dict:
    return json.loads(SAMPLE_REPORT)


def _validate_against_schema(schema_filename: str, document: dict) -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "schemas" / schema_filename).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


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

    def test_snapshot_exposes_explicit_provenance_chain(self) -> None:
        snapshot = build_snapshot(sample_report())
        provenance = snapshot["provenance"]

        self.assertEqual(
            provenance["work_unit"]["digest"],
            snapshot["work_unit"]["digest"],
        )
        self.assertEqual(
            provenance["run"]["source_run_digest"],
            snapshot["source"]["source_run_digest"],
        )
        first = provenance["attempts"][0]
        self.assertEqual(first["attempt_id"], "attempt-001")
        self.assertEqual(
            first["result_manifest"]["result_manifest_id"],
            "verification/patch-smoke/good-attempt-1",
        )
        self.assertEqual(
            first["verification"]["verifier_id"],
            "idkmesh-local-verifier",
        )
        self.assertTrue(
            first["verification"]["identity_distinct_from_worker"]
        )
        self.assertIn(
            "not inferred",
            first["verification"]["independence_claim"],
        )
        self.assertFalse(
            provenance["authority"]["automatic_candidate_selection"]
        )
        self.assertFalse(provenance["authority"]["merge"])

    def test_worker_verifier_identity_overlap_is_attention_not_independence(self) -> None:
        report = sample_report()
        report["attempts"][0]["verifier"]["id"] = report["attempts"][0][
            "worker"
        ]["id"]

        snapshot = build_snapshot(report)

        first = snapshot["provenance"]["attempts"][0]["verification"]
        self.assertFalse(first["identity_distinct_from_worker"])
        codes = {item["code"] for item in snapshot["attention"]}
        self.assertIn("worker_verifier_identity_overlap", codes)

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

    def test_non_finite_json_constants_are_rejected(self) -> None:
        text = SAMPLE_REPORT.replace(
            '"version": 1',
            '"version": NaN',
            1,
        )
        with self.assertRaises(ControlTowerInputError) as ctx:
            parse_report_text(text, source="test report")
        self.assertIn("non-finite JSON constant", str(ctx.exception))

    def test_builtin_sample_matches_committed_replay_fixture(self) -> None:
        root = Path(__file__).resolve().parents[1]
        fixture = (
            root
            / "results"
            / "orchestration"
            / "replay-fixture-evaluator-plan-good-vs-bad"
            / "evidence-report.json"
        )
        self.assertEqual(
            json.loads(SAMPLE_REPORT),
            json.loads(fixture.read_text(encoding="utf-8")),
        )

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

    def test_snapshot_binds_exact_evidence_report_digest(self) -> None:
        report = sample_report()
        snapshot = build_snapshot(report)
        self.assertEqual(
            snapshot["source"]["evidence_report_digest"],
            canonical_digest(report),
        )

    def test_snapshot_matches_published_json_schema(self) -> None:
        _validate_against_schema(
            "control-tower-snapshot-v0.1.schema.json",
            build_snapshot(sample_report()),
        )

    def test_status_document_matches_published_json_schema(self) -> None:
        _validate_against_schema(
            "idkmesh-control-tower-status-v0.1.schema.json",
            status_document(),
        )

    def test_success_envelope_matches_published_json_schema(self) -> None:
        _validate_against_schema(
            "idkmesh-control-tower-inspection-response-v0.1.schema.json",
            success_document(build_snapshot(sample_report())),
        )

    def test_error_document_matches_published_json_schema(self) -> None:
        _validate_against_schema(
            "idkmesh-api-error-v0.1.schema.json",
            error_document("invalid_run_evidence", "example", retryable=True),
        )

    def test_success_envelope_is_deterministic_and_digest_bound(self) -> None:
        snapshot = build_snapshot(sample_report())
        first = success_document(snapshot)
        second = success_document(snapshot)
        self.assertEqual(first, second)
        self.assertEqual(
            first["snapshot_digest"],
            canonical_digest(snapshot),
        )
        self.assertEqual(
            first["kind"],
            "idkmesh-control-tower-inspection-response",
        )

    def test_openapi_document_advertises_read_only_v1_contract(self) -> None:
        document = openapi_document()
        self.assertEqual(document["openapi"], "3.1.0")
        self.assertIn("/healthz", document["paths"])
        self.assertIn("/readyz", document["paths"])
        self.assertIn("/api/v1/status", document["paths"])
        self.assertIn(
            "/api/v1/run-evidence/inspect",
            document["paths"],
        )
        self.assertIn("RequestId", document["components"]["headers"])
        self.assertEqual(
            document["components"]["securitySchemes"]
            ["LocalSessionToken"]["name"],
            "X-IDKMesh-UI-Token",
        )
        inspect_content = (
            document["paths"]["/api/v1/run-evidence/inspect"]
            ["post"]["responses"]["200"]["content"]
        )
        self.assertIn("application/json", inspect_content)
        self.assertIn(
            "application/vnd.idkmesh.control-tower.v1+json",
            inspect_content,
        )

    def test_status_document_is_explicitly_non_actuating(self) -> None:
        status = status_document()
        self.assertEqual(status["api_version"], "v1")
        self.assertEqual(status["schema_version"], "0.1")
        self.assertTrue(status["ok"])
        self.assertIn("openapi", status["endpoints"])
        self.assertEqual(status["endpoints"]["readiness"], "GET /readyz")
        self.assertEqual(
            status["operations"]["request_id_header"],
            "X-Request-ID",
        )
        self.assertFalse(
            status["operations"]["access_logs_include_bodies"]
        )
        self.assertFalse(
            status["operations"]["access_logs_include_authentication"]
        )
        self.assertIn("control_tower_snapshot", status["schemas"])
        self.assertTrue(status["capabilities"]["run_evidence_inspection"])
        self.assertTrue(status["capabilities"]["provenance_chain"])
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
        extra_headers: dict[str, str] | None = None,
    ):
        conn = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        headers: dict[str, str] = dict(extra_headers or {})
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
        self.assertIn("Provenance", text)
        self.assertIn("Attempt provenance chains", text)
        self.assertIn("Audit Timeline", text)
        self.assertIn("Claim ≠ evidence", text)
        self.assertNotIn("<script src=", text)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", headers)

    def test_readiness_is_tokenless_minimal_and_correlated(self) -> None:
        status, headers, body = self.request(
            "GET",
            "/readyz",
            extra_headers={"X-Request-ID": "probe-123"},
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["service"], "idkmesh-control-tower")
        self.assertEqual(payload["mode"], "local-read-only")
        self.assertEqual(payload["api_version"], "v1")
        self.assertNotIn("run_id", payload)
        self.assertNotIn("work_unit", payload)
        self.assertEqual(headers["X-Request-ID"], "probe-123")
        self.assertEqual(
            headers["X-IDKMesh-Service"],
            "idkmesh-control-tower",
        )
        self.assertTrue(headers["X-IDKMesh-Service-Version"])
        self.assertEqual(headers["X-IDKMesh-Read-Only"], "true")

    def test_invalid_request_id_is_not_reflected(self) -> None:
        supplied = "x" * 129
        status, headers, _body = self.request(
            "GET",
            "/readyz",
            extra_headers={"X-Request-ID": supplied},
        )

        self.assertEqual(status, 200)
        self.assertNotEqual(headers["X-Request-ID"], supplied)
        self.assertTrue(headers["X-Request-ID"].startswith("req_"))
        self.assertLessEqual(len(headers["X-Request-ID"]), 128)

    def test_request_id_does_not_change_deterministic_body(self) -> None:
        first_status, _first_headers, first_body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
            extra_headers={"X-Request-ID": "request-a"},
        )
        second_status, _second_headers, second_body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
            extra_headers={"X-Request-ID": "request-b"},
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_body, second_body)

    def test_run_read_is_503_without_a_configured_store(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/some-run", token=True)
        payload = json.loads(body)
        self.assertEqual(status, 503)
        self.assertEqual(
            payload["error"]["code"],
            "product_spine_store_not_configured",
        )

    def test_run_read_requires_session_token(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs/some-run")
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertEqual(
            payload["error"]["code"], "invalid_session_token")

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

    def test_openapi_endpoint_is_machine_readable(self) -> None:
        status, headers, body = self.request(
            "GET",
            "/api/v1/openapi.json",
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertEqual(headers["X-IDKMesh-API-Version"], "v1")
        self.assertEqual(headers["X-IDKMesh-Read-Only"], "true")
        self.assertTrue(headers["ETag"].startswith('"'))
        self.assertTrue(
            headers["X-IDKMesh-Content-Digest"].startswith("sha256:")
        )

    def test_head_status_returns_headers_without_body(self) -> None:
        status, headers, body = self.request(
            "HEAD",
            "/api/v1/status",
            token=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertEqual(headers["X-IDKMesh-Read-Only"], "true")

    def test_head_error_writes_no_body_on_the_wire(self) -> None:
        with socket.create_connection(
            ("127.0.0.1", self.server.server_port), timeout=3
        ) as connection:
            connection.sendall(
                b"HEAD /api/v2/status HTTP/1.0\r\n"
                b"Host: 127.0.0.1\r\n\r\n"
            )
            chunks = []
            while chunk := connection.recv(4096):
                chunks.append(chunk)
        headers, separator, body = b"".join(chunks).partition(b"\r\n\r\n")
        self.assertTrue(separator)
        self.assertIn(b" 404 ", headers)
        self.assertEqual(body, b"")

    def test_api_honors_json_accept_negotiation(self) -> None:
        status, _, body = self.request(
            "GET",
            "/api/v1/status",
            token=True,
            extra_headers={"Accept": "text/html"},
        )
        payload = json.loads(body)
        self.assertEqual(status, 406)
        self.assertEqual(payload["error"]["code"], "not_acceptable")

    def test_vendor_json_media_type_is_accepted(self) -> None:
        status, headers, body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
            content_type=(
                "application/vnd.idkmesh.control-tower.v1+json"
            ),
            extra_headers={
                "Accept": (
                    "application/vnd.idkmesh.control-tower.v1+json"
                )
            },
        )
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(
            headers["Content-Type"].startswith(
                "application/vnd.idkmesh.control-tower.v1+json"
            )
        )
        self.assertEqual(headers["Vary"], "Accept")

    def test_unknown_v1_route_requires_token_before_routing(self) -> None:
        status, _, body = self.request(
            "GET",
            "/api/v1/not-a-real-endpoint",
        )
        payload = json.loads(body)
        self.assertEqual(status, 403)
        self.assertEqual(
            payload["error"]["code"],
            "invalid_session_token",
        )

    def test_head_on_post_only_endpoint_has_no_body(self) -> None:
        status, headers, body = self.request(
            "HEAD",
            "/api/v1/run-evidence/inspect",
            token=True,
        )
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "POST")
        self.assertEqual(body, b"")

    def test_wrong_method_returns_405_and_allow(self) -> None:
        status, headers, body = self.request(
            "GET",
            "/api/v1/run-evidence/inspect",
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "POST")
        self.assertEqual(
            payload["error"]["code"], "method_not_allowed")

    def test_unsupported_api_version_is_explicit(self) -> None:
        status, _, body = self.request(
            "GET",
            "/api/v2/status",
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(
            payload["error"]["code"], "unsupported_api_version")
        self.assertEqual(
            payload["error"]["details"]["supported_versions"],
            ["v1"],
        )

    def test_api_rejects_query_parameters_in_v1(self) -> None:
        status, _, body = self.request(
            "GET",
            "/api/v1/status?expand=all",
            token=True,
        )
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"]["code"],
            "unexpected_query_parameters",
        )

    def test_repeated_inspection_is_byte_deterministic(self) -> None:
        first_status, first_headers, first_body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
        )
        second_status, second_headers, second_body = self.request(
            "POST",
            "/api/v1/run-evidence/inspect",
            SAMPLE_REPORT,
            token=True,
        )
        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_body, second_body)
        self.assertEqual(first_headers["ETag"], second_headers["ETag"])
        self.assertEqual(
            first_headers["X-IDKMesh-Content-Digest"],
            second_headers["X-IDKMesh-Content-Digest"],
        )

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
        self.assertIn("provenance", snapshot)
        self.assertEqual(
            snapshot["provenance"]["attempts"][0]["attempt_id"],
            "attempt-001",
        )

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


class ControlTowerTokenTests(unittest.TestCase):
    def test_loopback_host_rejects_malformed_authorities(self) -> None:
        for host in ("localhost@other.example", "localhost:bad", "localhost:0",
                     "localhost:65536", "localhost:80:81", "localhost /", "[::1]",
                     "localhost:" + "9" * 5000):
            with self.subTest(host=host):
                self.assertFalse(is_loopback_host(host))
        self.assertTrue(is_loopback_host("127.0.0.1:8770"))
        self.assertTrue(is_loopback_host("localhost"))

    def test_headless_client_can_supply_stable_token_via_environment(self) -> None:
        token = "a" * 32
        with mock.patch.dict(
            "os.environ",
            {TOKEN_ENV: token},
            clear=False,
        ):
            server = create_server(port=0)
        try:
            self.assertEqual(server.ui_token, token)
        finally:
            server.server_close()

    def test_environment_token_rejects_html_or_header_unsafe_characters(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {TOKEN_ENV: "a" * 32 + "</script>"},
            clear=False,
        ):
            with self.assertRaises(ValueError) as ctx:
                create_server(port=0)
        self.assertIn("ASCII letters", str(ctx.exception))

    def test_short_environment_token_is_rejected(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {TOKEN_ENV: "too-short"},
            clear=False,
        ):
            with self.assertRaises(ValueError) as ctx:
                create_server(port=0)
        self.assertIn(TOKEN_ENV, str(ctx.exception))


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
            product_spine_store_path=None,
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
            product_spine_store_path=None,
        )

    def test_control_tower_rejects_oversized_preload_before_server_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "too-large.json"
            with path.open("wb") as handle:
                handle.truncate(MAX_BODY_BYTES + 1)
            with mock.patch("idkmesh.control_tower_ui.serve_control_tower") as serve:
                with mock.patch("idkmesh.cli._fail", return_value=2) as fail:
                    rc = cli.main(["control-tower", str(path), "--no-browser"])
            self.assertEqual(rc, 2)
            self.assertIn("2 MiB", fail.call_args.args[0])
            serve.assert_not_called()

    def test_control_tower_reports_invalid_environment_token_cleanly(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {TOKEN_ENV: "bad-token"},
            clear=False,
        ), mock.patch("idkmesh.cli._fail", return_value=2) as fail:
            rc = cli.main(
                ["control-tower", "--no-browser", "--port", "0"])
        self.assertEqual(rc, 2)
        self.assertIn(TOKEN_ENV, fail.call_args.args[0])

    def test_control_tower_rejects_invalid_port(self) -> None:
        with mock.patch("idkmesh.cli._fail", return_value=2) as fail:
            rc = cli.main(
                ["control-tower", "--port", "70000"])
        self.assertEqual(rc, 2)
        fail.assert_called_once_with(
            "--port must be between 0 and 65535")


def _run_projection(**overrides):
    value = {
        "schema_version": "0.1",
        "kind": "idkmesh-product-spine-run",
        "run_id": "run/http-read-1",
        "request_digest": "sha256:" + "a" * 64,
        "project_id": "project.test",
        "work_unit": {
            "id": "work/test-1",
            "version": 1,
            "digest": "sha256:" + "b" * 64,
            "source_revision": "0123456789abcdef0123456789abcdef01234567",
        },
        "routing": {
            "policy_version": "c1-v0.1",
            "authority_mode": "agent_candidate",
            "admitted_connectors": [],
        },
        "state": "proposed",
        "attempts": [],
        "evidence_report_digest": None,
        "human_decision_record_digest": None,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        },
    }
    for key, child in overrides.items():
        if key in {"work_unit", "routing", "authority"}:
            value[key].update(child)
        else:
            value[key] = child
    return value


class ControlTowerRunReadTests(unittest.TestCase):
    """GET /api/v1/runs/{run_id} over a real, configured Product Spine store."""

    @classmethod
    def setUpClass(cls) -> None:
        from idkmesh.connector_store import LocalMetadataStore
        from idkmesh.product_spine_run_store import ProductSpineRunStore

        cls._tmp = tempfile.TemporaryDirectory()
        cls.store_path = str(Path(cls._tmp.name) / "product-spine.sqlite3")
        service = ProductSpineRunStore(LocalMetadataStore(cls.store_path))
        service.create(
            _run_projection(),
            idempotency_key="http-read-test-1",
            created_at="2026-09-27T00:00:00Z",
        )
        # Two more runs, deliberately created out of run_id sort order, so
        # list-endpoint tests can assert deterministic ordering rather than
        # insertion order.
        service.create(
            _run_projection(run_id="run/http-read-3"),
            idempotency_key="http-read-test-3",
            created_at="2026-09-27T00:00:01Z",
        )
        service.create(
            _run_projection(run_id="run/http-read-2"),
            idempotency_key="http-read-test-2",
            created_at="2026-09-27T00:00:02Z",
        )
        cls.server = create_server(
            port=0, product_spine_store_path=cls.store_path
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls._tmp.cleanup()

    def request(self, method: str, path: str, *, token: bool = True):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        headers = {}
        if token:
            headers[TOKEN_HEADER] = self.server.ui_token
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        conn.close()
        return response.status, response_headers, payload

    def test_read_returns_the_created_run_matching_its_schema(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/http-read-1")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        _validate_against_schema(
            "idkmesh-control-tower-run-response-v0.1.schema.json", payload
        )
        _validate_against_schema(
            "idkmesh-product-spine-run-v0.1.schema.json", payload["run"]
        )
        self.assertEqual(payload["run"]["run_id"], "run/http-read-1")
        self.assertEqual(payload["run"]["state"], "proposed")
        # A read is never a create/replay and grants no authority.
        self.assertFalse(payload["created"])
        self.assertFalse(payload["replayed"])
        self.assertFalse(payload["merge_authority"])

    def test_read_matches_the_cli_status_command_exactly(self) -> None:
        """The HTTP surface and the CLI must consume the same service."""
        from idkmesh.connector_store import LocalMetadataStore
        from idkmesh.product_spine_run_store import ProductSpineRunStore

        cli_result = ProductSpineRunStore(
            LocalMetadataStore(self.store_path)
        ).status("run/http-read-1")

        _, _, body = self.request("GET", "/api/v1/runs/run/http-read-1")
        http_result = json.loads(body)

        expected = {
            "api_version": "v1",
            "schema_version": "0.1",
            "kind": "idkmesh-control-tower-run-response",
            "ok": True,
            **cli_result.to_dict(),
        }
        self.assertEqual(http_result, expected)

    def test_unknown_run_id_is_404(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/no-such-run")
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "run_not_found")

    def test_head_returns_headers_without_a_body(self) -> None:
        status, headers, body = self.request(
            "HEAD", "/api/v1/runs/run/http-read-1")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertIn("Content-Length", headers)

    def test_post_is_method_not_allowed(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        conn.request(
            "POST",
            "/api/v1/runs/run/http-read-1",
            headers={TOKEN_HEADER: self.server.ui_token},
        )
        response = conn.getresponse()
        status = response.status
        allow = response.getheader("Allow")
        response.read()
        conn.close()
        self.assertEqual(status, 405)
        self.assertEqual(allow, "GET, HEAD")

    def test_run_id_containing_a_slash_is_read_as_one_literal_id(self) -> None:
        """Product Spine run_ids share WorkUnit's identifier grammar and may
        contain '/'; a plain single-run GET takes everything after the
        prefix as one run_id -- except a trailing "/attempts", "/evidence",
        or "/decisions" segment, which ADR-0019 reserves for the matching
        sub-resource regardless of whether that derived run_id exists."""
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/http-read-1")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["run"]["run_id"], "run/http-read-1")

        # "/attempts" is reserved: this resolves as the attempts
        # sub-resource of run_id "run/http-read-1", not a literal id lookup
        # for "run/http-read-1/attempts" -- run/http-read-1 has no
        # attempts, so the sub-resource exists and returns an empty list,
        # not 404.
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/http-read-1/attempts")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["run_id"], "run/http-read-1")
        self.assertEqual(payload["attempts"], [])

        # A trailing segment outside the reserved set stays a literal id.
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/http-read-1/other")
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "run_not_found")

    def test_list_returns_every_run_ordered_by_run_id(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        _validate_against_schema("idkmesh-list-v0.1.schema.json", payload)
        self.assertEqual(payload["kind"], "idkmesh-list")
        self.assertEqual(
            [item["run_id"] for item in payload["items"]],
            ["run/http-read-1", "run/http-read-2", "run/http-read-3"],
        )
        self.assertIsNone(payload["page"]["next_cursor"])
        self.assertEqual(payload["page"]["limit"], 50)
        for item in payload["items"]:
            _validate_against_schema(
                "idkmesh-product-spine-run-v0.1.schema.json", item
            )

    def test_list_paginates_with_limit_and_cursor(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs?limit=2")
        self.assertEqual(status, 200)
        page1 = json.loads(body)
        self.assertEqual(
            [item["run_id"] for item in page1["items"]],
            ["run/http-read-1", "run/http-read-2"],
        )
        cursor = page1["page"]["next_cursor"]
        self.assertIsNotNone(cursor)

        status, _, body = self.request(
            "GET", f"/api/v1/runs?limit=2&cursor={cursor}")
        self.assertEqual(status, 200)
        page2 = json.loads(body)
        self.assertEqual(
            [item["run_id"] for item in page2["items"]],
            ["run/http-read-3"],
        )
        self.assertIsNone(page2["page"]["next_cursor"])

    def test_list_rejects_an_unknown_query_parameter(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs?filter=x")
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"]["code"], "unexpected_query_parameters")

    def test_list_rejects_an_out_of_bounds_limit(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs?limit=0")
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_limit")

    def test_list_filters_by_project_id(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs?project_id=project.test")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["items"]), 3)

        status, _, body = self.request(
            "GET", "/api/v1/runs?project_id=no-such-project")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], [])

    def test_list_filters_by_state(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs?state=proposed")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["items"]), 3)

        status, _, body = self.request("GET", "/api/v1/runs?state=cancelled")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], [])

    def test_list_rejects_an_unrecognized_state(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs?state=not-a-real-state")
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_state")

    def test_list_post_is_method_not_allowed(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        conn.request(
            "POST", "/api/v1/runs",
            headers={TOKEN_HEADER: self.server.ui_token},
        )
        response = conn.getresponse()
        status = response.status
        allow = response.getheader("Allow")
        response.read()
        conn.close()
        self.assertEqual(status, 405)
        self.assertEqual(allow, "GET, HEAD")


class ControlTowerRunAttemptsTests(unittest.TestCase):
    """GET /api/v1/runs/{run_id}/attempts (ADR-0019 reserved sub-resource)."""

    @classmethod
    def setUpClass(cls) -> None:
        from idkmesh.connector_store import LocalMetadataStore
        from idkmesh.product_spine import AttemptProjection
        from idkmesh.product_spine_run_store import (
            ProductSpineRunStore,
            _restore,
        )

        cls._tmp = tempfile.TemporaryDirectory()
        cls.store_path = str(Path(cls._tmp.name) / "product-spine.sqlite3")
        store = LocalMetadataStore(cls.store_path)
        service = ProductSpineRunStore(store)
        service.create(
            _run_projection(
                run_id="run/attempts-1",
                routing={"admitted_connectors": ["connector.test"]},
            ),
            idempotency_key="attempts-test-1",
            created_at="2026-09-27T00:00:00Z",
        )
        # Drive the run through real lifecycle transitions to get a
        # dispatched run with one real attempt, then persist that
        # projection directly (ProductSpineRunStore.create only accepts
        # state="proposed"; matching
        # test_product_spine_run_store.py's own pattern for seeding a
        # non-proposed fixture run).
        record = store.get_run("run/attempts-1")
        dispatched = (
            _restore(record)
            .transition("previewed")
            .transition("admitted")
            .transition("dispatched")
            .append_attempt(
                AttemptProjection(
                    attempt_id="attempt-1",
                    order=1,
                    connector_id="connector.test",
                    state="created",
                )
            )
        )
        metadata = dict(record.metadata)
        metadata["projection"] = dispatched.to_dict()
        store.update_run(
            "run/attempts-1",
            state=dispatched.state,
            metadata=metadata,
            updated_at="2026-09-27T00:00:02Z",
        )
        # A run_id that itself ends in the reserved "/attempts" suffix --
        # ADR-0019's documented, caller-avoidable collision: it is only
        # reachable as run_id "run/collision", never through the plain
        # single-run GET.
        service.create(
            _run_projection(run_id="run/collision/attempts"),
            idempotency_key="attempts-test-collision",
            created_at="2026-09-27T00:00:01Z",
        )
        cls.server = create_server(
            port=0, product_spine_store_path=cls.store_path
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls._tmp.cleanup()

    def request(self, method: str, path: str, *, token: bool = True):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        headers = {}
        if token:
            headers[TOKEN_HEADER] = self.server.ui_token
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        conn.close()
        return response.status, response_headers, payload

    def test_returns_the_runs_attempts_matching_its_schema(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/attempts-1/attempts")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        _validate_against_schema(
            "idkmesh-control-tower-run-attempts-response-v0.1.schema.json",
            payload,
        )
        self.assertEqual(payload["kind"], "idkmesh-control-tower-run-attempts-response")
        self.assertEqual(payload["run_id"], "run/attempts-1")
        self.assertEqual(len(payload["attempts"]), 1)
        self.assertEqual(payload["attempts"][0]["attempt_id"], "attempt-1")

    def test_unknown_run_id_is_404(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/does-not-exist/attempts")
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "run_not_found")

    def test_run_id_ending_in_reserved_suffix_is_unreachable(self) -> None:
        # A run_id that itself ends in "/attempts" (here
        # "run/collision/attempts", seeded in setUpClass) can never be
        # read again -- the literal path that names it is always
        # resolved as the "attempts" sub-resource of run_id
        # "run/collision" instead (ADR-0019's accepted, documented cost),
        # and "run/collision" was never created, so this 404s rather than
        # silently returning the wrong run or falling back.
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/collision/attempts")
        payload = json.loads(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "run_not_found")

    def test_query_parameters_are_rejected(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/run/attempts-1/attempts?limit=1")
        payload = json.loads(body)
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"]["code"], "unexpected_query_parameters"
        )

    def test_post_is_method_not_allowed(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        conn.request(
            "POST", "/api/v1/runs/run/attempts-1/attempts",
            headers={TOKEN_HEADER: self.server.ui_token},
        )
        response = conn.getresponse()
        status = response.status
        allow = response.getheader("Allow")
        response.read()
        conn.close()
        self.assertEqual(status, 405)
        self.assertEqual(allow, "GET, HEAD")


class ControlTowerRunListWithoutAStoreTests(unittest.TestCase):
    """GET /api/v1/runs (list) also requires --product-spine-store."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_list_is_503_without_a_configured_store(self) -> None:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        conn.request(
            "GET", "/api/v1/runs",
            headers={TOKEN_HEADER: self.server.ui_token},
        )
        response = conn.getresponse()
        status = response.status
        body = response.read()
        conn.close()
        self.assertEqual(status, 503)
        self.assertEqual(
            json.loads(body)["error"]["code"],
            "product_spine_store_not_configured",
        )


if __name__ == "__main__":
    unittest.main()
