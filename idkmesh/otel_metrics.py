"""Dependency-free OTLP/HTTP JSON and Prometheus text mappings for API metrics.

This module converts the canonical privacy-safe metrics document emitted by
idkmesh.api_observability into an OpenTelemetry Protocol metrics
ExportMetricsServiceRequest-compatible JSON object, or into Prometheus text
exposition format 0.0.4.

The adapters are deliberately transport-free: they perform no network I/O, own
no collector credentials, create no spans, and add no runtime dependency. A
deployment may hand the returned object or text to a reviewed transport.
"""

from __future__ import annotations

import json
import math
import re
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



def validate_api_metrics_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one canonical metrics document and return its parsed fields.

    Raises :class:`OtlpMetricsInputError` for anything inconsistent, including a
    relaxed privacy flag or authority ceiling. Public so sibling observability
    modules share one fail-closed validator instead of re-implementing it.
    """
    return _validate_canonical_document(_mapping(document, "document"))


PROMETHEUS_TEXT_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_PROMETHEUS_LABEL_VALUE_RE = re.compile(r"^[A-Za-z0-9._:+-]{1,128}$")
_PROMETHEUS_DEPENDENCY_STATES = ("not_configured", "configured_unprobed")


def _prometheus_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise OtlpMetricsInputError("Prometheus samples must be finite")
    return repr(float(value))


def _prometheus_bound(bound_ms: float) -> str:
    return format(bound_ms / 1000.0, ".10g")


def _prometheus_label_value(value: str, field: str) -> str:
    # Fail closed on anything outside a tiny alphabet instead of escaping:
    # service identity is configuration, never request-derived data.
    if _PROMETHEUS_LABEL_VALUE_RE.fullmatch(value) is None:
        raise OtlpMetricsInputError(
            f"{field} is not safe to use as a Prometheus label value"
        )
    return value


def render_prometheus_text(document: Mapping[str, Any]) -> str:
    """Render one canonical snapshot as Prometheus text exposition 0.0.4.

    Deterministic, fixed-cardinality output: the only label names are
    ``status_class``, ``le``, ``reason``, ``dependency``, ``state``,
    ``service`` and ``service_version``. Latency is exported in base units
    (seconds). The not-implemented rate-limit and Human Decision counters are
    omitted rather than exported as a misleading zero. Serve the result with
    :data:`PROMETHEUS_TEXT_CONTENT_TYPE`; this module never sends it.
    """
    canonical = _validate_canonical_document(_mapping(document, "document"))
    service = _prometheus_label_value(canonical["service"], "service")
    version = _prometheus_label_value(
        canonical["service_version"], "service_version"
    )

    lines: list[str] = []

    def family(name: str, kind: str, help_text: str) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")

    family(
        "idkmesh_api_build_info", "gauge",
        "Constant 1 labelled with the service identity.",
    )
    lines.append(
        f'idkmesh_api_build_info{{service="{service}",'
        f'service_version="{version}"}} 1'
    )

    family(
        "idkmesh_api_requests_total", "counter",
        "Completed HTTP responses by status class since process start.",
    )
    for status_class in _STATUS_CLASSES:
        lines.append(
            f'idkmesh_api_requests_total{{status_class="{status_class}"}} '
            f"{canonical['status_counts'][status_class]}"
        )

    name = "idkmesh_api_request_duration_seconds"
    family(name, "histogram", "Completed HTTP response latency in seconds.")
    cumulative = 0
    # per_bucket_counts carries one extra overflow slot beyond the fixed
    # bounds; it is represented by the +Inf bucket below, so strict=False.
    for bound, count in zip(
        LATENCY_BUCKETS_MS, canonical["per_bucket_counts"], strict=False
    ):
        cumulative += count
        lines.append(f'{name}_bucket{{le="{_prometheus_bound(bound)}"}} {cumulative}')
    lines.append(f'{name}_bucket{{le="+Inf"}} {canonical["latency_count"]}')
    lines.append(f"{name}_sum {_prometheus_number(canonical['latency_sum'] / 1000.0)}")
    lines.append(f"{name}_count {canonical['latency_count']}")

    gauges = (
        ("idkmesh_api_in_flight_requests", "in_flight_requests",
         "HTTP requests currently being served."),
        ("idkmesh_api_max_concurrent_requests", "max_concurrent_requests",
         "Configured concurrent request ceiling."),
        ("idkmesh_api_event_stream_clients", "event_stream_clients",
         "Open event-stream clients."),
        ("idkmesh_api_max_event_stream_clients", "max_event_stream_clients",
         "Configured event-stream client ceiling."),
    )
    for metric, field, help_text in gauges:
        family(metric, "gauge", help_text)
        lines.append(f"{metric} {canonical['concurrency'][field]}")

    family(
        "idkmesh_api_admission_rejections_total", "counter",
        "Requests rejected before service, by implemented reason.",
    )
    for reason, field, status in _ADMISSION_REASONS:
        if status != "implemented":
            continue
        lines.append(
            f'idkmesh_api_admission_rejections_total{{reason="{reason}"}} '
            f"{canonical['admission'][field]}"
        )

    family(
        "idkmesh_api_run_evidence_inspections_total", "counter",
        "Framed Run Evidence inspections accepted for processing.",
    )
    lines.append(
        "idkmesh_api_run_evidence_inspections_total "
        f"{canonical['operations']['run_evidence_inspection']}"
    )

    family(
        "idkmesh_api_dependency_state", "gauge",
        "Coarse dependency state (state-set); not a health probe.",
    )
    for state in _PROMETHEUS_DEPENDENCY_STATES:
        value = 1 if canonical["dependency_state"] == state else 0
        lines.append(
            'idkmesh_api_dependency_state{dependency="product_spine_store",'
            f'state="{state}"}} {value}'
        )

    return "\n".join(lines) + "\n"


def evaluate_api_metrics_interval(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    before_process_identity: str,
    after_process_identity: str,
    before_time_unix_nano: int,
    after_time_unix_nano: int,
) -> dict[str, Any]:
    """Compare two process-lifetime snapshots, without publishing input IDs.

    Process identity is a *collector-attested* epoch token; a caller cannot
    derive it from an ordinary HTTP request or infer it from service.version.
    Every invalid comparison is UNKNOWN, never interpreted as zero errors.
    This is a pure diagnostic, not an alert daemon or an authorization result.
    """
    def unknown(reason: str) -> dict[str, Any]:
        return {"status": "unknown", "reason": reason, "authority": "none"}

    if (
        not isinstance(before_process_identity, str)
        or not before_process_identity
        or len(before_process_identity) > 128
        or not isinstance(after_process_identity, str)
        or not after_process_identity
        or len(after_process_identity) > 128
    ):
        return unknown("process_identity_missing")
    if before_process_identity != after_process_identity:
        return unknown("process_changed")

    try:
        start = _timestamp(before_time_unix_nano, "before_time_unix_nano")
        end = _timestamp(after_time_unix_nano, "after_time_unix_nano")
        if end <= start:
            return unknown("timestamps_not_increasing")
        first = _validate_canonical_document(_mapping(before, "before"))
        last = _validate_canonical_document(_mapping(after, "after"))
    except OtlpMetricsInputError:
        # Do not reflect malformed fields: they may contain private payloads.
        return unknown("invalid_snapshot")

    if (
        first["service"] != last["service"]
        or first["service_version"] != last["service_version"]
    ):
        return unknown("service_changed")

    counters_before = (
        *first["status_counts"].values(),
        first["client_errors"],
        first["server_errors"],
        first["latency_count"],
        *first["per_bucket_counts"],
        *first["admission"].values(),
        *first["operations"].values(),
    )
    counters_after = (
        *last["status_counts"].values(),
        last["client_errors"],
        last["server_errors"],
        last["latency_count"],
        *last["per_bucket_counts"],
        *last["admission"].values(),
        *last["operations"].values(),
    )
    if (
        any(b < a for a, b in zip(counters_before, counters_after, strict=True))
        or last["latency_sum"] < first["latency_sum"]
        or last["latency_max"] < first["latency_max"]
    ):
        return unknown("counter_regression")

    total = last["latency_count"] - first["latency_count"]
    if total == 0:
        return unknown("no_requests")

    error_count = last["server_errors"] - first["server_errors"]
    fast_bucket_count = LATENCY_BUCKETS_MS.index(1000.0) + 1
    fast_before = sum(first["per_bucket_counts"][:fast_bucket_count])
    fast_after = sum(last["per_bucket_counts"][:fast_bucket_count])
    fast = fast_after - fast_before
    if not 0 <= error_count <= total or not 0 <= fast <= total:
        return unknown("inconsistent_interval")

    overload = (
        last["admission"]["overload_rejections_total"]
        - first["admission"]["overload_rejections_total"]
    )
    return {
        "status": "measured",
        "authority": "none",
        "requests": total,
        "server_errors": error_count,
        "server_error_fraction": error_count / total,
        "within_1000ms": fast,
        "within_1000ms_fraction": fast / total,
        "overload_rejections": overload,
        "interval_nanoseconds": end - start,
    }
