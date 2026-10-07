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

A collector derives rolling values by differencing process-lifetime counters.

Suggested alerts:

- **API server errors:** 5xx delta / request delta >= 1% for 5 minutes;
- **API slow:** derived p95 leaves the 1000 ms bucket for 5 minutes;
- **API overloaded:** overload-rejection delta > 0 in two consecutive intervals;
- **API concurrency hot:** in-flight requests stay at or above 80% of configured
  maximum for 5 minutes;
- **SSE saturation:** active stream clients reach the configured maximum.

A 4xx is not itself a service failure. `configured_unprobed` is not a health
claim.

## OpenTelemetry boundary

The repository still has no OpenTelemetry SDK dependency and this slice does
not claim OTLP export. #744 remains open for a reviewed optional adapter and for
decision-ingestion telemetry after #740 exists.

Any future adapter must preserve these invariants:

- no payload-derived span/metric attributes;
- no auth/session token attributes;
- bounded, reviewed attribute cardinality;
- W3C trace context is correlation input, never identity or authorization;
- telemetry failure cannot change domain/API correctness.

## Authority

Operational metrics and trace correlation are observations only. They cannot
select a candidate, dispatch work, mutate Product Spine state, push Git, or
merge.
