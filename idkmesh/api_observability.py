"""Privacy-safe aggregate HTTP observability primitives for IDKMesh.

Fixed-cardinality service telemetry only. This module does not accept arbitrary
labels, request/response bodies, URLs, query strings, request IDs, identities,
prompts, evidence payloads, run IDs, or WorkUnit IDs.
"""

from __future__ import annotations

import math
import re
import threading
from typing import Any


METRICS_SCHEMA_VERSION = "0.1"
METRICS_KIND = "idkmesh-api-operational-metrics"
TRACEPARENT_HEADER = "traceparent"

LATENCY_BUCKETS_MS = (
    5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0,
    1000.0, 2500.0, 5000.0, 10000.0,
)

_TRACEPARENT_V00_RE = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_ZERO_TRACE_ID = "0" * 32
_ZERO_PARENT_ID = "0" * 16


def resolve_traceparent(value: str | None) -> str | None:
    """Return one valid W3C traceparent v00 value, otherwise None."""
    if value is None or not isinstance(value, str) or value != value.strip():
        return None
    match = _TRACEPARENT_V00_RE.fullmatch(value)
    if match is None:
        return None
    trace_id, parent_id, _flags = match.groups()
    if trace_id == _ZERO_TRACE_ID or parent_id == _ZERO_PARENT_ID:
        return None
    return value


class ApiMetrics:
    """Thread-safe fixed-cardinality service metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._client_errors_total = 0
        self._server_errors_total = 0
        self._status_classes = {
            "1xx": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0,
        }
        self._latency_count = 0
        self._latency_sum_ms = 0.0
        self._latency_max_ms = 0.0
        self._latency_buckets = [0 for _ in LATENCY_BUCKETS_MS]
        self._overload_rejections_total = 0
        self._draining_rejections_total = 0
        self._run_evidence_inspections_total = 0

    def record_response(self, *, status: int, duration_ms: float) -> None:
        if isinstance(status, bool) or not isinstance(status, int):
            raise ValueError("status must be an integer HTTP status")
        if not 100 <= status <= 599:
            raise ValueError("status must be an HTTP status code")
        if (
            isinstance(duration_ms, bool)
            or not isinstance(duration_ms, (int, float))
            or not math.isfinite(float(duration_ms))
            or float(duration_ms) < 0.0
        ):
            raise ValueError("duration_ms must be a finite number >= 0")

        elapsed = float(duration_ms)
        status_class = f"{status // 100}xx"
        with self._lock:
            self._requests_total += 1
            self._status_classes[status_class] += 1
            if 400 <= status <= 499:
                self._client_errors_total += 1
            elif status >= 500:
                self._server_errors_total += 1
            self._latency_count += 1
            self._latency_sum_ms += elapsed
            self._latency_max_ms = max(self._latency_max_ms, elapsed)
            for index, boundary in enumerate(LATENCY_BUCKETS_MS):
                if elapsed <= boundary:
                    self._latency_buckets[index] += 1

    def note_admission_rejection(self, verdict: str) -> None:
        if verdict not in {"overloaded", "draining"}:
            raise ValueError("verdict must be overloaded or draining")
        with self._lock:
            if verdict == "overloaded":
                self._overload_rejections_total += 1
            else:
                self._draining_rejections_total += 1

    def note_run_evidence_inspection(self) -> None:
        with self._lock:
            self._run_evidence_inspections_total += 1

    @staticmethod
    def _gauge(value: int, field: str, *, minimum: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{field} must be an integer >= {minimum}")
        return value

    def document(
        self,
        *,
        service: str,
        service_version: str,
        in_flight_requests: int,
        max_concurrent_requests: int,
        event_stream_clients: int,
        max_event_stream_clients: int,
        product_spine_store_configured: bool,
    ) -> dict[str, Any]:
        """Build one aggregate metrics snapshot with no arbitrary labels."""
        if not isinstance(service, str) or not service:
            raise ValueError("service must be a non-empty string")
        if not isinstance(service_version, str) or not service_version:
            raise ValueError("service_version must be a non-empty string")
        if type(product_spine_store_configured) is not bool:
            raise ValueError("product_spine_store_configured must be boolean")

        gauges = {
            "in_flight_requests": self._gauge(
                in_flight_requests, "in_flight_requests"
            ),
            "max_concurrent_requests": self._gauge(
                max_concurrent_requests, "max_concurrent_requests", minimum=1
            ),
            "event_stream_clients": self._gauge(
                event_stream_clients, "event_stream_clients"
            ),
            "max_event_stream_clients": self._gauge(
                max_event_stream_clients, "max_event_stream_clients", minimum=1
            ),
        }

        with self._lock:
            total = self._requests_total
            client_errors = self._client_errors_total
            server_errors = self._server_errors_total
            status_classes = dict(self._status_classes)
            latency_count = self._latency_count
            latency_sum = self._latency_sum_ms
            latency_max = self._latency_max_ms
            buckets = list(self._latency_buckets)
            overload = self._overload_rejections_total
            draining = self._draining_rejections_total
            inspections = self._run_evidence_inspections_total

        return {
            "schema_version": METRICS_SCHEMA_VERSION,
            "kind": METRICS_KIND,
            "service": service,
            "service_version": service_version,
            "scope": "process_lifetime",
            "requests": {
                "total": total,
                "client_errors_total": client_errors,
                "server_errors_total": server_errors,
                "by_status_class": status_classes,
            },
            "latency_ms": {
                "count": latency_count,
                "sum": round(latency_sum, 3),
                "max": round(latency_max, 3),
                "buckets": [
                    {"le_ms": boundary, "count": count}
                    for boundary, count in zip(
                        LATENCY_BUCKETS_MS, buckets, strict=True
                    )
                ],
            },
            "concurrency": gauges,
            "admission": {
                "overload_rejections_total": overload,
                "draining_rejections_total": draining,
                "rate_limit_rejections_total": 0,
                "rate_limit_status": "not_implemented",
            },
            "operations": {
                "run_evidence_inspections_total": inspections,
                "human_decision_ingestions_total": 0,
                "human_decision_ingestion_status": "not_implemented",
            },
            "dependencies": {
                "product_spine_store": {
                    "state": (
                        "configured_unprobed"
                        if product_spine_store_configured
                        else "not_configured"
                    ),
                    "required_for_core_readiness": False,
                }
            },
            "telemetry": {
                "trace_context": "w3c-traceparent-v00-pass-through",
                "path_labels": False,
                "query_labels": False,
                "request_id_labels": False,
                "authentication_labels": False,
                "payload_labels": False,
            },
            "authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
            },
        }
