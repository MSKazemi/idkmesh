"""Tests for dependency-free HTTP service runtime primitives."""

from __future__ import annotations

from io import StringIO
import json
import unittest
from unittest import mock

from idkmesh.service_runtime import (
    ACCESS_LOG_ENV,
    REQUEST_ID_HEADER,
    access_logging_enabled,
    build_access_log_event,
    readiness_document,
    resolve_request_id,
    service_headers,
    write_access_log,
)


class ServiceRuntimeTests(unittest.TestCase):
    def test_safe_request_id_is_preserved(self) -> None:
        self.assertEqual(
            resolve_request_id("edge-01:abc_123"),
            "edge-01:abc_123",
        )

    def test_unsafe_or_unbounded_request_id_is_replaced(self) -> None:
        with mock.patch(
            "idkmesh.service_runtime.new_request_id",
            return_value="req_generated",
        ):
            self.assertEqual(
                resolve_request_id("bad\nheader"),
                "req_generated",
            )
            self.assertEqual(
                resolve_request_id("x" * 129),
                "req_generated",
            )
            self.assertEqual(resolve_request_id(None), "req_generated")

    def test_service_headers_are_stable_and_explicit(self) -> None:
        headers = service_headers(
            service="idkmesh-test",
            service_version="1.2.3",
            request_id="req-1",
            read_only=True,
            api_version="v1",
        )

        self.assertEqual(headers[REQUEST_ID_HEADER], "req-1")
        self.assertEqual(headers["X-IDKMesh-Service"], "idkmesh-test")
        self.assertEqual(headers["X-IDKMesh-Service-Version"], "1.2.3")
        self.assertEqual(headers["X-IDKMesh-Read-Only"], "true")
        self.assertEqual(headers["X-IDKMesh-API-Version"], "v1")

    def test_service_headers_reject_control_or_oversized_metadata(self) -> None:
        with self.assertRaises(ValueError):
            service_headers(
                service="bad\nservice",
                service_version="1.0",
                request_id="req-1",
                read_only=True,
            )
        with self.assertRaises(ValueError):
            service_headers(
                service="idkmesh-test",
                service_version="v" * 129,
                request_id="req-1",
                read_only=True,
            )

    def test_readiness_document_contains_no_project_state(self) -> None:
        document = readiness_document(
            service="idkmesh-control-tower",
            service_version="0.1.0",
            mode="local-read-only",
            api_version="v1",
        )

        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["service"], "idkmesh-control-tower")
        self.assertNotIn("run_id", document)
        self.assertNotIn("work_unit", document)
        self.assertNotIn("token", json.dumps(document).lower())
        self.assertNotIn("secret", json.dumps(document).lower())

    def test_access_logging_is_opt_in(self) -> None:
        self.assertFalse(access_logging_enabled({}))
        self.assertTrue(access_logging_enabled({ACCESS_LOG_ENV: "1"}))
        self.assertTrue(access_logging_enabled({ACCESS_LOG_ENV: "true"}))
        self.assertFalse(access_logging_enabled({ACCESS_LOG_ENV: "false"}))

    def test_access_log_has_no_body_headers_or_query(self) -> None:
        event = build_access_log_event(
            service="idkmesh-control-tower",
            request_id="req-123",
            method="POST",
            path="/api/v1/run-evidence/inspect?token=must-not-log",
            status=200,
            response_bytes=1234,
            duration_ms=12.34567,
            occurred_at="2026-09-22T18:30:00.000Z",
        )

        self.assertEqual(
            set(event),
            {
                "event",
                "service",
                "request_id",
                "method",
                "path",
                "status",
                "response_bytes",
                "duration_ms",
                "occurred_at",
            },
        )
        self.assertNotIn("?", event["path"])
        rendered = json.dumps(event)
        self.assertNotIn("authorization", rendered.lower())
        self.assertNotIn("token", rendered.lower())
        self.assertNotIn("body", rendered.lower())

    def test_access_log_writer_emits_one_compact_json_line(self) -> None:
        event = build_access_log_event(
            service="idkmesh-control-tower",
            request_id="req-1",
            method="GET",
            path="/readyz",
            status=200,
            response_bytes=42,
            duration_ms=1.5,
            occurred_at="2026-09-22T18:30:00.000Z",
        )
        stream = StringIO()

        write_access_log(event, stream=stream)

        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), event)


if __name__ == "__main__":
    unittest.main()
