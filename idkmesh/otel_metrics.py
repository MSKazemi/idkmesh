"""Dependency-free OTLP/HTTP JSON mapping for API operational metrics.

This module converts the canonical privacy-safe metrics document emitted by
idkmesh.api_observability into an OpenTelemetry Protocol metrics
ExportMetricsServiceRequest-compatible JSON object.

The adapter is deliberately transport-free: it performs no network I/O, owns no
collector credentials, creates no spans, and adds no runtime dependency. A
deployment may hand the returned object to a reviewed OTLP/HTTP JSON transport.
"""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

from idkmesh.api_observability import (
    LATENCY_BUCKETS_MS,
    METRICS_KIND,
    METRICS_SCHEMA_VERSION,
)

# opentelemetry.proto.metrics.v1.AggregationTemporality: CUMULATIVE = 2.
# OTLP JSON encodes enum fields as their integer values.
AGGREGATION_TEMPORALITY_CUMULATIVE = 2
OTEL_SCOPE_NAME = "idkmesh.api_observability"
OTEL_SCOPE_VERSION = "0.1"
OTLP_HTTP_METRICS_PATH = "/v1/metrics"
OTLP_HTTP_JSON_CONTENT_TYPE = "application/json"

_STATUS_CLASSES = ("1xx", "2xx", "3xx", "4xx", "5xx")
# (reason attribute, source field, implementation status). Rate limiting is
# pinned to zero and ``not_implemented`` in the local single-token profile, so
# its exported point carries that status rather than implying a limiter exists.
_ADMISSION_REASONS = (
    ("overloaded", "overload_rejections_total", "implemented"),
    ("draining", "draining_rejections_total", "implemented"),
    ("rate_limited", "rate_limit_rejections_total", "not_implemented"),
)
_TRACE_CONTEXT_CONTRACT = "w3c-traceparent-v00-pass-through"
_PRIVACY_FLAGS = (
    "path_labels",
    "query_labels",
    "request_id_labels",
    "authentication_labels",
    "payload_labels",
)
_AUTHORITY_FLAGS = ("canonical_state_write", "git_push", "merge")


class OtlpMetricsInputError(ValueError):
    """The operational metrics document cannot be safely mapped to OTLP."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OtlpMetricsInputError(f"{field} must be an object")
    return value


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise OtlpMetricsInputError(f"{field} must be a non-empty string")
    return value


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OtlpMetricsInputError(f"{field} must be an integer >= 0")
    return value


def _positive_count(value: Any, field: str) -> int:
    result = _count(value, field)
    if result < 1:
        raise OtlpMetricsInputError(f"{field} must be an integer >= 1")
    return result


def _number(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise OtlpMetricsInputError(f"{field} must be a finite number >= 0")
    return float(value)


def _timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OtlpMetricsInputError(f"{field} must be a positive integer")
    return value


def _attribute(key: str, value: str | bool) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded: dict[str, Any] = {"boolValue": value}
    else:
        encoded = {"stringValue": value}
    return {"key": key, "value": encoded}


def _int_point(
    value: int,
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    point: dict[str, Any] = {
        "startTimeUnixNano": str(start_time_unix_nano),
        "timeUnixNano": str(time_unix_nano),
        "asInt": str(value),
    }
    if attributes:
        point["attributes"] = attributes
    return point


def _counter_metric(
    name: str,
    description: str,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": "{event}",
        "sum": {
            "aggregationTemporality": AGGREGATION_TEMPORALITY_CUMULATIVE,
            "isMonotonic": True,
            "dataPoints": points,
        },
    }


def _gauge_metric(
    name: str,
    description: str,
    value: int,
    *,
    time_unix_nano: int,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    point: dict[str, Any] = {
        "timeUnixNano": str(time_unix_nano),
        "asInt": str(value),
    }
    if attributes:
        point["attributes"] = attributes
    return {
        "name": name,
        "description": description,
        "unit": "{item}",
        "gauge": {"dataPoints": [point]},
    }


def _validate_canonical_document(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != METRICS_SCHEMA_VERSION:
        raise OtlpMetricsInputError(
            f"schema_version must be {METRICS_SCHEMA_VERSION!r}"
        )
    if document.get("kind") != METRICS_KIND:
        raise OtlpMetricsInputError(f"kind must be {METRICS_KIND!r}")
    if document.get("scope") != "process_lifetime":
        raise OtlpMetricsInputError("scope must be 'process_lifetime'")

    service = _nonempty_string(document.get("service"), "service")
    service_version = _nonempty_string(
        document.get("service_version"), "service_version"
    )

    # Fail closed if the source no longer asserts the v0.1 privacy boundary or
    # authority ceiling; the adapter must not launder a relaxed document.
    telemetry = _mapping(document.get("telemetry"), "telemetry")
    if telemetry.get("trace_context") != _TRACE_CONTEXT_CONTRACT:
        raise OtlpMetricsInputError(
            f"telemetry.trace_context must be {_TRACE_CONTEXT_CONTRACT!r}"
        )
    for flag in _PRIVACY_FLAGS:
        if telemetry.get(flag) is not False:
            raise OtlpMetricsInputError(
                f"telemetry.{flag} must be false for OTLP export"
            )
    authority = _mapping(document.get("authority"), "authority")
    for flag in _AUTHORITY_FLAGS:
        if authority.get(flag) is not False:
            raise OtlpMetricsInputError(
                f"authority.{flag} must be false for operational telemetry"
            )

    requests = _mapping(document.get("requests"), "requests")
    request_total = _count(requests.get("total"), "requests.total")
    status_classes = _mapping(
        requests.get("by_status_class"), "requests.by_status_class"
    )
    if set(status_classes) != set(_STATUS_CLASSES):
        raise OtlpMetricsInputError(
            "requests.by_status_class must contain exactly 1xx through 5xx"
        )
    status_counts = {
        status_class: _count(
            status_classes.get(status_class),
            f"requests.by_status_class.{status_class}",
        )
        for status_class in _STATUS_CLASSES
    }
    if sum(status_counts.values()) != request_total:
        raise OtlpMetricsInputError(
            "requests.total must equal the sum of status-class counters"
        )

    client_errors = _count(
        requests.get("client_errors_total"), "requests.client_errors_total"
    )
    server_errors = _count(
        requests.get("server_errors_total"), "requests.server_errors_total"
    )
    if client_errors != status_counts["4xx"]:
        raise OtlpMetricsInputError(
            "requests.client_errors_total must equal the 4xx status-class count"
        )
    if server_errors != status_counts["5xx"]:
        raise OtlpMetricsInputError(
            "requests.server_errors_total must equal the 5xx status-class count"
        )

    latency = _mapping(document.get("latency_ms"), "latency_ms")
    latency_count = _count(latency.get("count"), "latency_ms.count")
    if latency_count != request_total:
        raise OtlpMetricsInputError(
            "latency_ms.count must equal requests.total"
        )
    latency_sum = _number(latency.get("sum"), "latency_ms.sum")
    latency_max = _number(latency.get("max"), "latency_ms.max")
    buckets = latency.get("buckets")
    if not isinstance(buckets, list) or len(buckets) != len(LATENCY_BUCKETS_MS):
        raise OtlpMetricsInputError(
            "latency_ms.buckets must contain the canonical fixed bucket set"
        )

    cumulative_counts: list[int] = []
    previous = 0
    for index, (expected_bound, raw_bucket) in enumerate(
        zip(LATENCY_BUCKETS_MS, buckets, strict=True)
    ):
        bucket = _mapping(raw_bucket, f"latency_ms.buckets[{index}]")
        bound = _number(bucket.get("le_ms"), f"latency_ms.buckets[{index}].le_ms")
        if bound != expected_bound:
            raise OtlpMetricsInputError(
                "latency_ms.buckets must use the canonical fixed boundaries"
            )
        count = _count(
            bucket.get("count"), f"latency_ms.buckets[{index}].count"
        )
        if count < previous:
            raise OtlpMetricsInputError(
                "latency_ms bucket counts must be cumulative and nondecreasing"
            )
        if count > latency_count:
            raise OtlpMetricsInputError(
                "latency_ms bucket counts cannot exceed latency_ms.count"
            )
        cumulative_counts.append(count)
        previous = count

    per_bucket_counts: list[int] = []
    previous = 0
    for cumulative in cumulative_counts:
        per_bucket_counts.append(cumulative - previous)
        previous = cumulative
    per_bucket_counts.append(latency_count - previous)

    concurrency = _mapping(document.get("concurrency"), "concurrency")
    concurrency_values = {
        "in_flight_requests": _count(
            concurrency.get("in_flight_requests"),
            "concurrency.in_flight_requests",
        ),
        "max_concurrent_requests": _positive_count(
            concurrency.get("max_concurrent_requests"),
            "concurrency.max_concurrent_requests",
        ),
        "event_stream_clients": _count(
            concurrency.get("event_stream_clients"),
            "concurrency.event_stream_clients",
        ),
        "max_event_stream_clients": _positive_count(
            concurrency.get("max_event_stream_clients"),
            "concurrency.max_event_stream_clients",
        ),
    }

    admission = _mapping(document.get("admission"), "admission")
    admission_values = {
        field: _count(admission.get(field), f"admission.{field}")
        for _reason, field, _status in _ADMISSION_REASONS
    }
    if admission.get("rate_limit_status") != "not_implemented":
        raise OtlpMetricsInputError(
            "admission.rate_limit_status must remain 'not_implemented'"
        )
    if admission_values["rate_limit_rejections_total"] != 0:
        raise OtlpMetricsInputError(
            "rate-limit rejections must remain zero while rate limiting is not implemented"
        )

    operations = _mapping(document.get("operations"), "operations")
    operation_values = {
        "run_evidence_inspection": _count(
            operations.get("run_evidence_inspections_total"),
            "operations.run_evidence_inspections_total",
        ),
        "human_decision_ingestion": _count(
            operations.get("human_decision_ingestions_total"),
            "operations.human_decision_ingestions_total",
        ),
    }
    if operations.get("human_decision_ingestion_status") != "not_implemented":
        raise OtlpMetricsInputError(
            "operations.human_decision_ingestion_status must remain 'not_implemented'"
        )
    if operation_values["human_decision_ingestion"] != 0:
        raise OtlpMetricsInputError(
            "human-decision ingestion must remain zero while not implemented"
        )

    dependencies = _mapping(document.get("dependencies"), "dependencies")
    product_spine = _mapping(
        dependencies.get("product_spine_store"),
        "dependencies.product_spine_store",
    )
    dependency_state = product_spine.get("state")
    if dependency_state not in {"not_configured", "configured_unprobed"}:
        raise OtlpMetricsInputError(
            "dependencies.product_spine_store.state is not recognized"
        )
    if product_spine.get("required_for_core_readiness") is not False:
        raise OtlpMetricsInputError(
            "product_spine_store must not be represented as required for core readiness"
        )

    return {
        "service": service,
        "service_version": service_version,
        "status_counts": status_counts,
        "client_errors": client_errors,
        "server_errors": server_errors,
        "latency_count": latency_count,
        "latency_sum": latency_sum,
        "latency_max": latency_max,
        "per_bucket_counts": per_bucket_counts,
        "concurrency": concurrency_values,
        "admission": admission_values,
        "operations": operation_values,
        "dependency_state": dependency_state,
    }


def build_otlp_metrics_request(
    document: Mapping[str, Any],
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
) -> dict[str, Any]:
    """Map one canonical metrics snapshot to transport-neutral OTLP JSON."""

    start = _timestamp(start_time_unix_nano, "start_time_unix_nano")
    end = _timestamp(time_unix_nano, "time_unix_nano")
    if end < start:
        raise OtlpMetricsInputError(
            "time_unix_nano must be greater than or equal to start_time_unix_nano"
        )

    canonical = _validate_canonical_document(_mapping(document, "document"))

    counter_points = [
        _int_point(
            canonical["status_counts"][status_class],
            start_time_unix_nano=start,
            time_unix_nano=end,
            attributes=[_attribute("idkmesh.http.status_class", status_class)],
        )
        for status_class in _STATUS_CLASSES
    ]

    admission_points = [
        _int_point(
            canonical["admission"][field],
            start_time_unix_nano=start,
            time_unix_nano=end,
            attributes=[
                _attribute("idkmesh.admission.reason", reason),
                _attribute("idkmesh.implementation_status", status),
            ],
        )
        for reason, field, status in _ADMISSION_REASONS
    ]

    operation_points = [
        _int_point(
            canonical["operations"]["run_evidence_inspection"],
            start_time_unix_nano=start,
            time_unix_nano=end,
            attributes=[
                _attribute("idkmesh.operation", "run_evidence_inspection"),
                _attribute("idkmesh.implementation_status", "implemented"),
            ],
        ),
        _int_point(
            canonical["operations"]["human_decision_ingestion"],
            start_time_unix_nano=start,
            time_unix_nano=end,
            attributes=[
                _attribute("idkmesh.operation", "human_decision_ingestion"),
                _attribute("idkmesh.implementation_status", "not_implemented"),
            ],
        ),
    ]

    histogram_point: dict[str, Any] = {
        "startTimeUnixNano": str(start),
        "timeUnixNano": str(end),
        "count": str(canonical["latency_count"]),
        "sum": canonical["latency_sum"],
        "bucketCounts": [str(value) for value in canonical["per_bucket_counts"]],
        "explicitBounds": list(LATENCY_BUCKETS_MS),
    }
    # OTLP ``max`` is optional; with no observations there is no maximum to
    # report, so the adapter omits it instead of fabricating a 0 ms sample.
    if canonical["latency_count"]:
        histogram_point["max"] = canonical["latency_max"]

    metrics: list[dict[str, Any]] = [
        _counter_metric(
            "idkmesh.api.requests",
            "Completed HTTP responses by fixed status-code class.",
            counter_points,
        ),
        _counter_metric(
            "idkmesh.api.client_errors",
            "Completed HTTP 4xx responses.",
            [
                _int_point(
                    canonical["client_errors"],
                    start_time_unix_nano=start,
                    time_unix_nano=end,
                )
            ],
        ),
        _counter_metric(
            "idkmesh.api.server_errors",
            "Completed HTTP 5xx responses.",
            [
                _int_point(
                    canonical["server_errors"],
                    start_time_unix_nano=start,
                    time_unix_nano=end,
                )
            ],
        ),
        {
            "name": "idkmesh.api.request.duration",
            "description": "Completed request duration using canonical fixed buckets.",
            "unit": "ms",
            "histogram": {
                "aggregationTemporality": AGGREGATION_TEMPORALITY_CUMULATIVE,
                "dataPoints": [histogram_point],
            },
        },
        _gauge_metric(
            "idkmesh.api.in_flight_requests",
            "Current non-streaming requests admitted by the service.",
            canonical["concurrency"]["in_flight_requests"],
            time_unix_nano=end,
        ),
        _gauge_metric(
            "idkmesh.api.max_concurrent_requests",
            "Configured maximum concurrent non-streaming requests.",
            canonical["concurrency"]["max_concurrent_requests"],
            time_unix_nano=end,
        ),
        _gauge_metric(
            "idkmesh.api.event_stream_clients",
            "Current active server-sent-event clients.",
            canonical["concurrency"]["event_stream_clients"],
            time_unix_nano=end,
        ),
        _gauge_metric(
            "idkmesh.api.max_event_stream_clients",
            "Configured maximum server-sent-event clients.",
            canonical["concurrency"]["max_event_stream_clients"],
            time_unix_nano=end,
        ),
        _counter_metric(
            "idkmesh.api.admission_rejections",
            "Admission rejections by the fixed local-service reason vocabulary.",
            admission_points,
        ),
        _counter_metric(
            "idkmesh.api.operations",
            "Bounded operation counters with fixed operation identifiers.",
            operation_points,
        ),
        _gauge_metric(
            "idkmesh.api.dependency_state",
            "Current coarse dependency state; this is not a health probe.",
            1,
            time_unix_nano=end,
            attributes=[
                _attribute("idkmesh.dependency", "product_spine_store"),
                _attribute(
                    "idkmesh.dependency.state", canonical["dependency_state"]
                ),
                _attribute("idkmesh.required_for_core_readiness", False),
            ],
        ),
    ]

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        _attribute("service.name", canonical["service"]),
                        _attribute(
                            "service.version", canonical["service_version"]
                        ),
                        _attribute(
                            "idkmesh.metrics.scope", "process_lifetime"
                        ),
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {
                            "name": OTEL_SCOPE_NAME,
                            "version": OTEL_SCOPE_VERSION,
                        },
                        "metrics": metrics,
                    }
                ],
            }
        ]
    }


def render_otlp_metrics_json(
    document: Mapping[str, Any],
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
    pretty: bool = False,
) -> str:
    """Render one deterministic, strict OTLP/HTTP JSON request body.

    Keys are sorted and non-finite floats are rejected, so identical inputs
    produce byte-identical output suitable for replay or digesting. The body is
    meant for ``POST`` to :data:`OTLP_HTTP_METRICS_PATH` with
    :data:`OTLP_HTTP_JSON_CONTENT_TYPE`; this module never sends it.
    """

    request = build_otlp_metrics_request(
        document,
        start_time_unix_nano=start_time_unix_nano,
        time_unix_nano=time_unix_nano,
    )
    if pretty:
        return json.dumps(
            request, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        ) + "\n"
    return json.dumps(
        request,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
