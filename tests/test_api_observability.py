"""Tests for the privacy-safe API observability slice (#744)."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from idkmesh.api_observability import ApiMetrics, resolve_traceparent
from idkmesh.control_tower_ui import SAMPLE_REPORT, TOKEN_ENV, create_server
from idkmesh.local_ui_security import TOKEN_HEADER


VALID_TRACEPARENT = (
    "00-4bf92f3577b34da6a3ce929d0e0e4736-"
    "00f067aa0ba902b7-01"
)
TOKEN = "m" * 32


class ApiObservabilityPrimitiveTests(unittest.TestCase):
    def test_traceparent_accepts_only_safe_w3c_v00_context(self) -> None:
        self.assertEqual(resolve_traceparent(VALID_TRACEPARENT), VALID_TRACEPARENT)
        self.assertIsNone(resolve_traceparent(None))
        self.assertIsNone(resolve_traceparent(" " + VALID_TRACEPARENT))
        self.assertIsNone(
            resolve_traceparent(
                "00-" + "0" * 32 + "-00f067aa0ba902b7-01"
            )
        )
        self.assertIsNone(
            resolve_traceparent(
                "00-4bf92f3577b34da6a3ce929d0e0e4736-"
                + "0" * 16
                + "-01"
            )
        )
        self.assertIsNone(
            resolve_traceparent(
                "01-4bf92f3577b34da6a3ce929d0e0e4736-"
                "00f067aa0ba902b7-01"
            )
        )
        self.assertIsNone(resolve_traceparent(VALID_TRACEPARENT.upper()))

    def test_metrics_are_fixed_cardinality_and_schema_valid(self) -> None:
        metrics = ApiMetrics()
        metrics.record_response(status=200, duration_ms=4.0)
        metrics.record_response(status=404, duration_ms=17.0)
        metrics.record_response(status=503, duration_ms=1200.0)
        metrics.note_admission_rejection("overloaded")
        metrics.note_run_evidence_inspection()

        document = metrics.document(
            service="idkmesh-control-tower",
            service_version="0.1",
            in_flight_requests=2,
            max_concurrent_requests=16,
            event_stream_clients=1,
            max_event_stream_clients=8,
            product_spine_store_configured=False,
        )

        self.assertEqual(document["requests"]["total"], 3)
        self.assertEqual(document["requests"]["client_errors_total"], 1)
        self.assertEqual(document["requests"]["server_errors_total"], 1)
        self.assertEqual(document["requests"]["by_status_class"]["2xx"], 1)
        self.assertEqual(
            document["admission"]["overload_rejections_total"], 1
        )
        self.assertEqual(
            document["operations"]["run_evidence_inspections_total"], 1
        )
        self.assertEqual(document["concurrency"]["in_flight_requests"], 2)
        self.assertEqual(document["latency_ms"]["count"], 3)
        self.assertEqual(document["latency_ms"]["max"], 1200.0)

        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (
                root
                / "schemas"
                / "idkmesh-api-operational-metrics-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)

        rendered = json.dumps(document, sort_keys=True).lower()
        for forbidden in (
            "\"authorization\":",
            "x-idkmesh-ui-token",
            "\"request_id\":",
            "\"run_id\":",
            "\"work_unit_id\":",
            "\"prompt\":",
            "\"evidence_report\":",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_metric_input_validation_fails_closed(self) -> None:
        metrics = ApiMetrics()
        with self.assertRaises(ValueError):
            metrics.record_response(status=99, duration_ms=1.0)
        with self.assertRaises(ValueError):
            metrics.record_response(status=200, duration_ms=float("nan"))
        with self.assertRaises(ValueError):
            metrics.note_admission_rejection("queued")


class ControlTowerObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token_patch = mock.patch.dict(
            "os.environ", {TOKEN_ENV: TOKEN}, clear=False
        )
        self.token_patch.start()
        self.server = create_server(port=0)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()
        self.token_patch.stop()

    def request(
        self,
        method: str,
        path: str,
        body: str | None = None,
        *,
        token: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        headers = dict(extra_headers or {})
        if token:
            headers[TOKEN_HEADER] = TOKEN
        encoded = None
        if body is not None:
            encoded = body.encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(encoded))
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        status = response.status
        conn.close()
        return status, response_headers, payload

    def test_metrics_endpoint_is_authenticated_aggregate_and_schema_valid(self) -> None:
        ready_status, _, _ = self.request("GET", "/readyz", token=False)
        self.assertEqual(ready_status, 200)

        status, _headers, body = self.request(
            "GET", "/api/v1/metrics", token=True
        )
        self.assertEqual(status, 200)
        document = json.loads(body)

        self.assertGreaterEqual(document["concurrency"]["in_flight_requests"], 1)
        self.assertGreaterEqual(document["requests"]["total"], 1)
        self.assertGreaterEqual(
            document["requests"]["by_status_class"]["2xx"], 1
        )

        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (
                root
                / "schemas"
                / "idkmesh-api-operational-metrics-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(document)

        rendered = json.dumps(document, sort_keys=True)
        self.assertNotIn(TOKEN, rendered)
        self.assertNotIn(json.loads(SAMPLE_REPORT)["run_id"], rendered)

        no_token_status, _, no_token_body = self.request(
            "GET", "/api/v1/metrics", token=False
        )
        self.assertEqual(no_token_status, 403)
        self.assertEqual(
            json.loads(no_token_body)["error"]["code"],
            "invalid_session_token",
        )

    def test_run_evidence_inspection_counter_counts_framed_requests(self) -> None:
        before_status, _, before_body = self.request(
            "GET", "/api/v1/metrics"
        )
        self.assertEqual(before_status, 200)
        before = json.loads(before_body)["operations"][
            "run_evidence_inspections_total"
        ]

        inspect_status, _, _ = self.request(
            "POST", "/api/v1/run-evidence/inspect", SAMPLE_REPORT
        )
        self.assertEqual(inspect_status, 200)

        after_status, _, after_body = self.request(
            "GET", "/api/v1/metrics"
        )
        self.assertEqual(after_status, 200)
        after = json.loads(after_body)["operations"][
            "run_evidence_inspections_total"
        ]
        self.assertEqual(after, before + 1)

    def test_valid_traceparent_is_propagated_and_invalid_value_is_not(self) -> None:
        status, headers, body = self.request(
            "GET",
            "/api/v1/status",
            extra_headers={"traceparent": VALID_TRACEPARENT},
        )
        self.assertEqual(status, 200)
        lower_headers = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(lower_headers["traceparent"], VALID_TRACEPARENT)
        self.assertNotIn(VALID_TRACEPARENT, body.decode("utf-8"))

        bad_status, bad_headers, _ = self.request(
            "GET",
            "/api/v1/status",
            extra_headers={"traceparent": "00-not-valid"},
        )
        self.assertEqual(bad_status, 200)
        self.assertNotIn(
            "traceparent",
            {key.lower(): value for key, value in bad_headers.items()},
        )


if __name__ == "__main__":
    unittest.main()
