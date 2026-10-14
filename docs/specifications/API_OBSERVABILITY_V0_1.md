---
description: "Privacy-safe telemetry contract for the IDKMesh HTTP service: is it answering, slow, overloaded or draining, and are concurrency limits saturated."
---
# API Observability v0.1

**Status:** experimental, local-service profile  
**Issue:** #744  
**Authority:** operational telemetry only; no execution, acceptance, repository-write, or merge authority.

## Purpose

This contract gives a maintainer enough privacy-safe service telemetry to answer
four operational questions without inspecting evidence or other private
payloads:

1. Is the HTTP service answering requests?
2. Is it slow?
3. Is it overloaded or draining?
4. Are bounded concurrency surfaces saturated?

The first implementation is the loopback Control Tower endpoint
`GET /api/v1/metrics`. It requires the same local session token as other
authenticated Control Tower API reads.

## Privacy boundary

The metrics accumulator has fixed cardinality by construction. Its recording
API accepts only an HTTP status, elapsed milliseconds, and a small fixed set of
named events. It has no arbitrary label/attribute API.

The metrics document must not contain request/response bodies, paths, query
strings, request IDs, authentication/session data, prompts, raw evidence,
project/WorkUnit/run/attempt/candidate identifiers, or secret references.

The response schema is
`schemas/idkmesh-api-operational-metrics-v0.1.schema.json`.

### Optional access-log privacy (distinct from aggregate metrics)

`IDKMESH_HTTP_ACCESS_LOG=1` enables local stderr access logs. Unlike the
aggregate metrics and OTLP documents, those logs include a validated request ID
for operational correlation and a canonical `path` **route template**. The
service runtime replaces all run, WorkUnit and project IDs with placeholders;
unknown routes collapse to `<unmatched>`. Neither raw paths nor query strings
are emitted, even on HTTP errors and unsupported URLs. Unrecognized methods
are emitted as `OTHER`. Tests exercise the real HTTP logging path, not only
the standalone formatter.

The caller-chosen request ID is intentionally still included in optional logs:
never pass a credential or private payload as `X-Request-ID`. Access controls
and retention for stderr output remain the local operator's responsibility.
This hardening does not introduce tracing spans, collector networking, or an
authenticated network-service logging profile.

## Metrics

All counters are process-lifetime counters and reset on process restart.

### HTTP requests and latency

`requests.total` counts completed HTTP responses. Status is aggregated into
five fixed classes (`1xx` through `5xx`), with separate client/server error
totals.

`latency_ms` contains count, sum, max, and cumulative fixed buckets at 5, 10,
25, 50, 100, 250, 500, 1000, 2500, 5000, and 10000 ms. No endpoint/path label
is retained.

### Concurrency and admission

The document exposes current and configured maxima for ordinary in-flight
requests and active SSE clients. It also counts overload and drain rejections.

Per-client rate limiting remains `not_implemented` in the local single-token
profile, matching ADR-0022. The rate-limit counter is pinned to zero rather than
implying a limiter exists.

### Operation counters

The first operation counter records framed
`POST /api/v1/run-evidence/inspect` requests. It increments after HTTP body
framing/UTF-8 decoding succeeds, whether evidence validation later succeeds or
fails.

The Human Decision ingestion counter is explicitly pinned to zero with status
`not_implemented` until #740 lands. This slice does not manufacture telemetry
for an endpoint that does not exist.

### Dependency state

The optional Product Spine store is reported only as `not_configured` or
`configured_unprobed`. Merely having a path configured is not described as
healthy. This metrics read does not open, migrate, or probe the store.

## W3C trace context

A syntactically valid W3C `traceparent` version-00 request header is passed
through on the response. Invalid, whitespace-padded, all-zero-id, uppercase, or
future-version values are ignored rather than reflected.

This v0.1 slice does not invent spans and adds no OpenTelemetry SDK runtime
dependency.

## SLOs and alert conditions

These are **operational targets for the local service profile**, not measured
product claims. For non-streaming requests while below the configured
concurrency limit:

- server-error SLO: less than 1% HTTP 5xx over a rolling 5-minute window;
- latency SLO: at least 95% of completed requests at or below 1000 ms over a
  rolling 5-minute window;
- overload SLO: no sustained overload rejection for two consecutive scrape
  intervals under expected local load.

A trusted collector can derive rolling values by differencing process-lifetime counters, provided the process epoch and timestamps are independently established. The local HTTP service does not itself calculate rolling windows.

Suggested alerts:

- **API server errors:** 5xx delta / request delta >= 1% for 5 minutes;
- **API slow:** derived p95 leaves the 1000 ms bucket for 5 minutes;
- **API overloaded:** overload-rejection delta > 0 in two consecutive intervals;
- **API concurrency hot:** in-flight requests stay at or above 80% of configured
  maximum for 5 minutes;
- **SSE saturation:** active stream clients reach the configured maximum.

A 4xx is not itself a service failure. `configured_unprobed` is not a health
claim.

## Same-process interval evaluator (library only)

`idkmesh.otel_metrics.evaluate_api_metrics_interval()` validates and compares two cumulative service metrics documents when an external trusted collector provides a matching process epoch and strictly increasing Unix-nanosecond observation times. It reports the completed-response 5xx fraction, the share within the fixed 1000 ms latency bucket, overload-rejection deltas, and request count. It returns `status="unknown"` (with no authority) for different epochs, invalid or decreasing counters, empty intervals, and other unsafe comparisons. UNKNOWN **never** means a zero-error interval. This is neither a served HTTP route nor a rolling SLO monitor; see the [runnable interval guide](../reference/API_METRICS_INTERVAL_GUIDE.md) and `tests/test_api_observability_intervals.py`.

## OpenTelemetry / OTLP JSON adapter

The repository still has no OpenTelemetry SDK dependency. The dependency-free
`idkmesh.otel_metrics.build_otlp_metrics_request()` adapter maps one canonical
metrics document into the OTLP metrics JSON shape used by an
`ExportMetricsServiceRequest`.

The adapter is intentionally **transport-free**. It performs no collector
network I/O, owns no endpoint or credential, retries nothing, and creates no
spans. A deployment may hand the returned object to a separately reviewed
OTLP/HTTP JSON transport. `render_otlp_metrics_json()` renders the same request
as deterministic strict JSON (sorted keys, no `NaN`/`Infinity`) intended for a
`POST` to the OTLP `/v1/metrics` path with `Content-Type: application/json`;
the module itself never sends it.

Mapping rules:

- process-lifetime counters become monotonic cumulative OTLP sums;
- request status classes use the fixed `1xx..5xx` vocabulary;
- the source latency buckets are cumulative, so the adapter differences them
  into OTLP per-bucket `bucketCounts` and appends the required overflow bucket;
- concurrency values become gauges;
- admission and operation labels use closed vocabularies only, and each point
  carries `idkmesh.implementation_status`; rate limiting and Human Decision
  ingestion are exported as zero-valued `not_implemented` points so a
  collector cannot mistake them for a working limiter or ingestion path;
- the latency histogram omits the optional `max` field when it has no
  observations instead of reporting a fabricated 0 ms maximum;
- Product Spine dependency state is exported as a coarse gauge with the
  existing `not_configured | configured_unprobed` vocabulary and is not
  promoted into a health claim;
- protobuf 64-bit integer JSON fields such as timestamps, counts, bucket counts,
  and integer points are emitted as decimal strings.

The caller supplies process-start and snapshot timestamps in Unix nanoseconds.
This keeps the mapping deterministic and prevents the adapter from owning a
clock or lifecycle policy.

The adapter fails closed when the source document is internally inconsistent
(for example, request totals do not equal status-class totals, client/server
error totals disagree with the `4xx`/`5xx` classes, a status-class key outside
`1xx..5xx` appears, cumulative histogram buckets decrease, canonical boundaries
change, or a `not_implemented` counter is manufactured). It also fails closed
when the source no longer asserts the v0.1 privacy boundary or authority
ceiling: every `telemetry.*_labels` flag must be `false`, `trace_context` must
remain `w3c-traceparent-v00-pass-through`, and every `authority` flag must be
`false`. The adapter never relaxes these checks to produce partial output.

This adapter preserves the v0.1 invariants:

- no payload-derived span/metric attributes;
- no path, query, request-ID, run-ID, WorkUnit-ID, auth/session, prompt, raw
  evidence, or secret-reference attributes;
- bounded, reviewed attribute cardinality;
- W3C trace context remains correlation input only and is not converted into
  identity or authorization;
- telemetry mapping failure cannot change domain/API correctness.

This is an OTLP-compatible mapping layer, not a claim that IDKMesh ships an
OpenTelemetry Collector, SDK instrumentation, OTLP network exporter, or
distributed tracing system. Issue #744 remains open for Human Decision
ingestion telemetry after #740 exists, per-client rate-limit telemetry after
#743, and any separately reviewed transport integration (OTLP push or a served
Prometheus route).

## Prometheus text exposition (library only)

`idkmesh.otel_metrics.render_prometheus_text()` renders the same validated
canonical document as Prometheus text exposition format 0.0.4 (content type
`PROMETHEUS_TEXT_CONTENT_TYPE`). It is transport-free like the OTLP adapter:
there is **no** `/metrics` HTTP route, no scrape authentication story and no
network I/O; a deployment would have to add and review that route separately.

- The label names are a closed set (`status_class`, `le`, `reason`,
  `dependency`, `state`, `service`, `service_version`); no path, query,
  request-ID, identity, run, WorkUnit, prompt or evidence label can exist.
- Latency is exported in base units (seconds) as a cumulative histogram that
  ends with `+Inf` equal to the request count.
- The service identity labels must match `[A-Za-z0-9._:+-]{1,128}`; anything
  else is rejected rather than escaped, so a hostile string can never inject
  exposition lines.
- Rate-limit and Human Decision counters are **omitted** (not exported as a
  misleading zero) because they remain `not_implemented`.
- Dependency state is a state-set gauge with the existing coarse vocabulary;
  `configured_unprobed` is not a health claim.
- The same fail-closed validation as the OTLP adapter applies: a document that
  relaxes a privacy flag or the authority ceiling is refused, never partially
  rendered.

## Machine-readable SLO contract (library only)

The prose targets above are pinned as data by `idkmesh/api_slo.py`
(`default_slo_contract()`, schema
`schemas/idkmesh-api-slo-contract-v0.1.schema.json`,
example `examples/api/api-slo-contract.example.json`,
which a test pins to the default). The contract is explicitly
`operational_target_not_measured_result`, closes the set of objective and alert
ids, carries no labels, endpoints or credentials, and has an all-false
authority ceiling. `validate_slo_contract()` fails closed with
`SloContractError`.

Pure evaluators (no clock, no network, no alert delivery, no state):

- `evaluate_slo_interval(interval)` judges one `measured` result of
  `evaluate_api_metrics_interval()` against the 5xx fraction (`< 1%`), the
  within-1000 ms share (`>= 95%`) and the overload objective (`0` rejections).
  A malformed or non-measured interval, or one shorter than the contract
  window (`300 s`), is `unknown`, never "met". The collector remains
  responsible for attesting the process epoch and timestamps.
- `evaluate_overload_alert(intervals)` fires only when the latest N (default 2)
  consecutive intervals all breached the overload objective; too few or any
  unknown interval is `unknown`, not "quiet".
- `evaluate_saturation_conditions(snapshot)` reports the point-in-time
  concurrency (`>= 80%`) and event-stream (`>= 100%`) conditions. The `for`
  duration is returned with `duration_evaluated: false`: one snapshot cannot
  show how long a gauge stayed high, so the condition is necessary, not
  sufficient, for the documented alert.

These evaluators are not a rolling-window monitor or an alert daemon, and a
passing result is a statement about one supplied interval only. See
`tests/test_api_slo.py`.

## Authority

Operational metrics and trace correlation are observations only. They cannot
select a candidate, dispatch work, mutate Product Spine state, push Git, or
merge.
