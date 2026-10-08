"""Dependency-free OTLP/HTTP JSON metric serialization for API observability.

This module converts the fixed-cardinality metrics document produced by
:mod:`idkmesh.api_observability` into one OTLP
`ExportMetricsServiceRequest` JSON object.

It intentionally performs no network I/O, collector discovery, retries,
credential handling, span creation, or SDK initialization. Callers remain
responsible for choosing whether and where to transmit the resulting payload.

The adapter accepts only the bounded aggregate document defined by
API Observability v0.1. It does not expose an arbitrary attribute API.
"""

from __future__ import annotations

import json
import math
from typing import Any

OTLP_HTTP_METRICS_PATH = "/v1/metrics"
OTLP_HTTP_JSON_CONTENT_TYPE = "application/json"
OTLP_SCOPE_NAME = "idkmesh.api_observability"
OTLP_SCOPE_VERSION = "0.1"

# opentelemetry.proto.metrics.v1.AggregationTemporality:
# UNSPECIFIED=0, DELTA=1, CUMULATIVE=2.
# OTLP JSON requires enum fields to be encoded as integer values.
OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE = 2

_STATUS_CLASSES = ("1xx", "2xx", "3xx", "4xx", "5xx")
_FORBIDDEN_TELEMETRY_FLAGS = (
    "path_labels",
    "query_labels",
    "request_id_labels",
    "authentication_labels",
    "payload_labels",
)


class OtlpMetricsError(ValueError):
    """The operational metrics document cannot be serialized safely."""


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OtlpMetricsError(f"{field} must be an integer >= 0")
    return value


def _positive_int(value: Any, field: str) -> int:
    value = _non_negative_int(value, field)
    if value == 0:
        raise OtlpMetricsError(f"{field} must be an integer > 0")
    return value


def _finite_non_negative_number(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise OtlpMetricsError(f"{field} must be a finite number >= 0")
    return float(value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise OtlpMetricsError(f"{field} must be a non-empty string")
    return value


def _timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OtlpMetricsError(f"{field} must be an integer > 0")
    return value


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OtlpMetricsError(f"{field} must be an object")
    return value


def _attribute(key: str, value: str | bool | int) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded: dict[str, Any] = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": str(value)}
    else:
        encoded = {"stringValue": value}
    return {"key": key, "value": encoded}


def _data_point(
    *,
    value: int,
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


def _sum_metric(
    *,
    name: str,
    description: str,
    value: int,
    start_time_unix_nano: int,
    time_unix_nano: int,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": "1",
        "sum": {
            "aggregationTemporality": OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE,
            "isMonotonic": True,
            "dataPoints": [
                _data_point(
                    value=value,
                    start_time_unix_nano=start_time_unix_nano,
                    time_unix_nano=time_unix_nano,
                    attributes=attributes,
                )
            ],
        },
    }


def _gauge_metric(
    *,
    name: str,
    description: str,
    value: int,
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
        "unit": "1",
        "gauge": {"dataPoints": [point]},
    }


def _validate_source(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise OtlpMetricsError("document must be an object")
    if document.get("schema_version") != "0.1":
        raise OtlpMetricsError("document schema_version must be '0.1'")
    if document.get("kind") != "idkmesh-api-operational-metrics":
        raise OtlpMetricsError(
            "document kind must be 'idkmesh-api-operational-metrics'"
        )
    if document.get("scope") != "process_lifetime":
        raise OtlpMetricsError("document scope must be 'process_lifetime'")

    _string(document.get("service"), "service")
    _string(document.get("service_version"), "service_version")

    telemetry = _require_object(document.get("telemetry"), "telemetry")
    for field in _FORBIDDEN_TELEMETRY_FLAGS:
        if telemetry.get(field) is not False:
            raise OtlpMetricsError(
                f"telemetry.{field} must be false for OTLP export"
            )

    authority = _require_object(document.get("authority"), "authority")
    for field in ("canonical_state_write", "git_push", "merge"):
        if authority.get(field) is not False:
            raise OtlpMetricsError(
                f"authority.{field} must be false for operational telemetry"
            )
    return document


def _histogram_metric(
    latency: dict[str, Any],
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
) -> dict[str, Any]:
    count = _non_negative_int(latency.get("count"), "latency_ms.count")
    total = _finite_non_negative_number(latency.get("sum"), "latency_ms.sum")
    maximum = _finite_non_negative_number(latency.get("max"), "latency_ms.max")
    buckets = latency.get("buckets")
    if not isinstance(buckets, list) or not buckets:
        raise OtlpMetricsError("latency_ms.buckets must be a non-empty array")

    explicit_bounds: list[float] = []
    cumulative_counts: list[int] = []
    previous_bound = -math.inf
    previous_count = 0

    for index, item in enumerate(buckets):
        item = _require_object(item, f"latency_ms.buckets[{index}]")
        bound = _finite_non_negative_number(
            item.get("le_ms"), f"latency_ms.buckets[{index}].le_ms"
        )
        cumulative = _non_negative_int(
            item.get("count"), f"latency_ms.buckets[{index}].count"
        )
        if bound <= previous_bound:
            raise OtlpMetricsError(
                "latency_ms bucket bounds must be strictly increasing"
            )
        if cumulative < previous_count:
            raise OtlpMetricsError(
                "latency_ms bucket counts must be cumulative/nondecreasing"
            )
        if cumulative > count:
            raise OtlpMetricsError(
                "latency_ms cumulative bucket count cannot exceed count"
            )
        explicit_bounds.append(bound)
        cumulative_counts.append(cumulative)
        previous_bound = bound
        previous_count = cumulative

    bucket_counts: list[int] = []
    previous = 0
    for cumulative in cumulative_counts:
        bucket_counts.append(cumulative - previous)
        previous = cumulative
    bucket_counts.append(count - previous)

    point: dict[str, Any] = {
        "startTimeUnixNano": str(start_time_unix_nano),
        "timeUnixNano": str(time_unix_nano),
        "count": str(count),
        "sum": total,
        "bucketCounts": [str(value) for value in bucket_counts],
        "explicitBounds": explicit_bounds,
    }
    if count:
        point["max"] = maximum

    return {
        "name": "idkmesh.api.http.request.duration",
        "description": (
            "Process-lifetime HTTP request latency histogram from the "
            "privacy-safe IDKMesh API observability accumulator."
        ),
        "unit": "ms",
        "histogram": {
            "aggregationTemporality": OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE,
            "dataPoints": [point],
        },
    }


def to_otlp_export_request(
    document: dict[str, Any],
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
) -> dict[str, Any]:
    """Convert one API observability document to OTLP metrics JSON.

    The caller supplies both timestamps. The adapter does not fabricate process
    start time or read the system clock, keeping replay deterministic.
    """

    _validate_source(document)
    start = _timestamp(start_time_unix_nano, "start_time_unix_nano")
    observed = _timestamp(time_unix_nano, "time_unix_nano")
    if observed < start:
        raise OtlpMetricsError(
            "time_unix_nano must be greater than or equal to "
            "start_time_unix_nano"
        )

    requests = _require_object(document.get("requests"), "requests")
    statuses = _require_object(
        requests.get("by_status_class"), "requests.by_status_class"
    )
    concurrency = _require_object(document.get("concurrency"), "concurrency")
    admission = _require_object(document.get("admission"), "admission")
    operations = _require_object(document.get("operations"), "operations")
    dependencies = _require_object(document.get("dependencies"), "dependencies")
    product_spine = _require_object(
        dependencies.get("product_spine_store"),
        "dependencies.product_spine_store",
    )

    metrics: list[dict[str, Any]] = []

    metrics.append(
        _sum_metric(
            name="idkmesh.api.http.requests",
            description="Completed HTTP responses since process start.",
            value=_non_negative_int(requests.get("total"), "requests.total"),
            start_time_unix_nano=start,
            time_unix_nano=observed,
        )
    )

    for status_class in _STATUS_CLASSES:
        metrics.append(
            _sum_metric(
                name="idkmesh.api.http.responses",
                description=(
                    "Completed HTTP responses grouped by fixed status class."
                ),
                value=_non_negative_int(
                    statuses.get(status_class),
                    f"requests.by_status_class.{status_class}",
                ),
                start_time_unix_nano=start,
                time_unix_nano=observed,
                attributes=[
                    _attribute("idkmesh.http.status_class", status_class)
                ],
            )
        )

    for name, description, value, field in (
        (
            "idkmesh.api.http.client_errors",
            "HTTP 4xx responses since process start.",
            requests.get("client_errors_total"),
            "requests.client_errors_total",
        ),
        (
            "idkmesh.api.http.server_errors",
            "HTTP 5xx responses since process start.",
            requests.get("server_errors_total"),
            "requests.server_errors_total",
        ),
        (
            "idkmesh.api.admission.overload_rejections",
            "Requests rejected because the service was overloaded.",
            admission.get("overload_rejections_total"),
            "admission.overload_rejections_total",
        ),
        (
            "idkmesh.api.admission.draining_rejections",
            "Requests rejected while the service was draining.",
            admission.get("draining_rejections_total"),
            "admission.draining_rejections_total",
        ),
        (
            "idkmesh.api.operation.run_evidence_inspections",
            "Framed Run Evidence inspection requests since process start.",
            operations.get("run_evidence_inspections_total"),
            "operations.run_evidence_inspections_total",
        ),
        (
            "idkmesh.api.operation.human_decision_ingestions",
            "Human Decision ingestion operations since process start.",
            operations.get("human_decision_ingestions_total"),
            "operations.human_decision_ingestions_total",
        ),
    ):
        metrics.append(
            _sum_metric(
                name=name,
                description=description,
                value=_non_negative_int(value, field),
                start_time_unix_nano=start,
                time_unix_nano=observed,
            )
        )

    for name, description, value, field in (
        (
            "idkmesh.api.concurrency.in_flight_requests",
            "Current in-flight non-streaming requests.",
            concurrency.get("in_flight_requests"),
            "concurrency.in_flight_requests",
        ),
        (
            "idkmesh.api.concurrency.max_requests",
            "Configured maximum in-flight request capacity.",
            concurrency.get("max_concurrent_requests"),
            "concurrency.max_concurrent_requests",
        ),
        (
            "idkmesh.api.concurrency.event_stream_clients",
            "Current active SSE clients.",
            concurrency.get("event_stream_clients"),
            "concurrency.event_stream_clients",
        ),
        (
            "idkmesh.api.concurrency.max_event_stream_clients",
            "Configured maximum SSE client capacity.",
            concurrency.get("max_event_stream_clients"),
            "concurrency.max_event_stream_clients",
        ),
    ):
        metrics.append(
            _gauge_metric(
                name=name,
                description=description,
                value=_non_negative_int(value, field),
                time_unix_nano=observed,
            )
        )

    rate_status = _string(
        admission.get("rate_limit_status"), "admission.rate_limit_status"
    )
    decision_status = _string(
        operations.get("human_decision_ingestion_status"),
        "operations.human_decision_ingestion_status",
    )
    metrics.append(
        _gauge_metric(
            name="idkmesh.api.feature.available",
            description=(
                "Feature availability marker; value 1 means implemented in "
                "the source metrics contract, 0 means unavailable."
            ),
            value=0 if rate_status == "not_implemented" else 1,
            time_unix_nano=observed,
            attributes=[
                _attribute("idkmesh.feature", "rate_limiting"),
                _attribute("idkmesh.feature.status", rate_status),
            ],
        )
    )
    metrics.append(
        _gauge_metric(
            name="idkmesh.api.feature.available",
            description=(
                "Feature availability marker; value 1 means implemented in "
                "the source metrics contract, 0 means unavailable."
            ),
            value=0 if decision_status == "not_implemented" else 1,
            time_unix_nano=observed,
            attributes=[
                _attribute("idkmesh.feature", "human_decision_ingestion"),
                _attribute("idkmesh.feature.status", decision_status),
            ],
        )
    )

    dependency_state = _string(
        product_spine.get("state"), "dependencies.product_spine_store.state"
    )
    if dependency_state not in {"not_configured", "configured_unprobed"}:
        raise OtlpMetricsError(
            "dependencies.product_spine_store.state is unsupported"
        )
    metrics.append(
        _gauge_metric(
            name="idkmesh.api.dependency.configured",
            description=(
                "Configuration presence only; this is not a dependency-health "
                "probe."
            ),
            value=1 if dependency_state == "configured_unprobed" else 0,
            time_unix_nano=observed,
            attributes=[
                _attribute("idkmesh.dependency", "product_spine_store"),
                _attribute("idkmesh.dependency.state", dependency_state),
            ],
        )
    )

    latency = _require_object(document.get("latency_ms"), "latency_ms")
    metrics.append(
        _histogram_metric(
            latency,
            start_time_unix_nano=start,
            time_unix_nano=observed,
        )
    )

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        _attribute("service.name", document["service"]),
                        _attribute(
                            "service.version", document["service_version"]
                        ),
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {
                            "name": OTLP_SCOPE_NAME,
                            "version": OTLP_SCOPE_VERSION,
                        },
                        "metrics": metrics,
                    }
                ],
            }
        ]
    }


def render_otlp_json(
    document: dict[str, Any],
    *,
    start_time_unix_nano: int,
    time_unix_nano: int,
    pretty: bool = False,
) -> str:
    """Render deterministic OTLP JSON for an operational metrics document."""
    request = to_otlp_export_request(
        document,
        start_time_unix_nano=start_time_unix_nano,
        time_unix_nano=time_unix_nano,
    )
    if pretty:
        return json.dumps(
            request,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ) + "\n"
    return json.dumps(
        request,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
