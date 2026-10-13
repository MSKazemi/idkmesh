---
title: "Comparing Control Tower API metrics snapshots"
description: "Source-backed, offline example and safety rules for the local API's interval evaluator."
---
# Compare API metrics intervals safely

**Source reviewed:** `idkmesh/api_observability.py`, `idkmesh/otel_metrics.py`, `idkmesh/control_tower_ui.py`, and `tests/test_api_observability_intervals.py` on 2026-10-13. This is a local diagnostic, **not** an SLO monitor, telemetry exporter, or authorization mechanism.

## Understand what you are reading

`GET /api/v1/metrics` reports **process-lifetime cumulative** request, latency, operation and admission counters. It does not return "failures in the last five minutes". The endpoint is loopback-only and requires the Control Tower's local session token; it does not identify the server's process incarnation for an external collector.

The pure Python function `idkmesh.otel_metrics.evaluate_api_metrics_interval()` compares two canonical metric documents **only when the caller supplies independently trusted evidence they came from the same process incarnation** and strictly increasing Unix-nanosecond observation times. It does not fetch HTTP, collect process identity, maintain a rolling window, send alerts, emit OTLP, authorize a mutation, or grant merge rights. The separate `render_otlp_metrics_json()` function renders offline output but does not send it.

| Interval output | Interpretation |
| --- | --- |
| `requests` | Number of completed HTTP responses between snapshots, including 4xx and 5xx |
| `server_errors`, `server_error_fraction` | 5xx count and fraction of **all completed responses** |
| `within_1000ms`, `within_1000ms_fraction` | Completed responses at or below the fixed 1000 ms bucket; **not** an exact latency percentile |
| `overload_rejections` | Difference in the recorded overload-admission counter |
| `interval_nanoseconds` | Difference in caller-supplied observation timestamps |
| `authority` | Always `none`; result is an observation, not an acceptance decision |

## Offline, runnable example

This synthetic fixture uses one `ApiMetrics` object for both snapshots, so its epoch string is meaningful **only for this in-memory demonstration**. Do **not** reuse a made-up constant epoch to compare real HTTP responses: the trusted process supervisor or collector must attest the identity separately. The example needs only the installed Python package, with no server or credentials.

```python
from idkmesh.api_observability import ApiMetrics
from idkmesh.otel_metrics import evaluate_api_metrics_interval

metrics = ApiMetrics()

def snapshot():
    return metrics.document(
        service="idkmesh-control-tower",
        service_version="0.1",
        in_flight_requests=0,
        max_concurrent_requests=16,
        event_stream_clients=0,
        max_event_stream_clients=8,
        product_spine_store_configured=False,
    )

before = snapshot()
metrics.record_response(status=200, duration_ms=25)
metrics.record_response(status=404, duration_ms=400)
metrics.record_response(status=503, duration_ms=1500)
metrics.note_admission_rejection("overloaded")
after = snapshot()

result = evaluate_api_metrics_interval(
    before, after,
    before_process_identity="in-memory-fixture-epoch",
    after_process_identity="in-memory-fixture-epoch",
    before_time_unix_nano=1_000_000_000,
    after_time_unix_nano=301_000_000_000,
)
assert result["status"] == "measured"
assert result["authority"] == "none"
assert result["requests"] == 3
assert result["server_errors"] == 1
assert result["server_error_fraction"] == 1 / 3
assert result["within_1000ms"] == 2
assert result["within_1000ms_fraction"] == 2 / 3
assert result["overload_rejections"] == 1
print(result)
```

This deliberately tiny example is **not** measured service performance or proof of a five-minute SLO. HTTP 404 is counted as a completed request, but is not a 5xx server error.

## Reading raw metrics locally

Follow the [API quickstart](API_QUICKSTART.md) to start the local Control Tower, then set the **same** `IDKMESH_CONTROL_TOWER_TOKEN` privately in your second terminal:

```bash
curl --fail-with-body --silent \
  -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/metrics > metrics-before.json
# Perform a known local request, then repeat the same command to obtain metrics-after.json.
```

These are **raw snapshots**, not evidence of a same-process interval on their own. Do not commit the token or private operational files. If you cannot attest that both responses came from the same process, label the comparison **UNKNOWN**.

## UNKNOWN is not zero errors

The evaluator fails closed to `{"status": "unknown", "reason": "...", "authority": "none"}` when a window cannot be justified. The reason vocabulary is checked against the function by `tests/test_api_metrics_interval_docs.py`.

| Reason | Meaning |
| --- | --- |
| `process_identity_missing` | An epoch is absent, invalid, or too long |
| `process_changed` | A restart or another process invalidates the comparison |
| `timestamps_not_increasing` | Observation times are not increasing positive integer Unix nanoseconds |
| `invalid_snapshot` | Canonical counters, fixed histogram, privacy or authority contract fails validation |
| `service_changed` | Service name or version differs |
| `counter_regression` | A monotonic counter, latency sum, or maximum decreased |
| `no_requests` | No completed responses; error and latency fractions would be undefined |
| `inconsistent_interval` | Derived sub-counts do not fit the request total |

A valid measured interval is descriptive, not proof that the planned rolling five-minute error, latency, or overload SLO passed. For intended SLO thresholds, see [API Observability v0.1](../specifications/API_OBSERVABILITY_V0_1.md). For real HTTP service boundaries, see [as-built architecture](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md) and [API limits](API_LIMITS.md). The [Capability Truth Matrix](../CAPABILITY_MATRIX.md) remains authoritative for maturity claims.
