# 2026-10-13 — API-9 optional access-log privacy hardening

## Owner request and chosen issue

The project owner asked to work on an issue in MSKazemi/idkmesh to an
enterprise-quality standard, keeping results in the repository. Selected
[#744](https://github.com/MSKazemi/idkmesh/issues/744), the still-open API-9
observability and privacy issue, for a bounded regression-hardening slice.

## Source-backed finding

The existing `idkmesh/service_runtime.py` access-log builder stripped query
strings but then wrote the remaining request path into a JSON log event.
`idkmesh/control_tower_ui.py` used this builder whenever
`IDKMESH_HTTP_ACCESS_LOG=1`, including on unknown routes and resource-detail
routes whose path segments are caller-supplied identifiers. The existing #744
privacy regression verified aggregate metrics, offline OTLP, and status, but
explicitly did not exercise opt-in access logs.

## Decision and implementation

- Keep the existing log-event field structure so consumers still see method,
  status, latency, response size, timestamp and request ID.
- Restrict the logged `path` value to a finite set of known static routes and
  dynamic route templates. Resource IDs become placeholders, including when a
  resource ID contains slashes or URL-encoded text.
- Map unrecognized routes to `<unmatched>` and unrecognized HTTP methods to
  `OTHER`; do not log raw user-controlled URL strings.
- Add standalone unit cases and an HTTP-level opt-in logging test with a
  sensitive sentinel placed in multiple route and query positions.
- Update the Control Tower API specification, API-9 observability contract,
  as-built architecture and changelog.

This change does not authorize execution, read credentials, modify GitHub
settings, or alter the aggregate metrics/OTLP data model. It is a candidate
change until exact-head CI and normal review are complete.

## Limits and follow-up

- Optional log lines still retain syntactically valid caller-provided
  `X-Request-ID` values for correlation. Clients must not place sensitive
  values in that header; log storage and retention remain operator-controlled.
- Multi-user per-client rate limiting and Human Decision ingestion telemetry
  remain unimplemented under #743 and #740 respectively; #744 remains open.
- No collector network connection, tracing span generation, production service
  deployment or external security certification is claimed.

## Community impact

The route vocabulary is intentionally small, inspectable and regression-tested.
Contributors can run
`python -m unittest tests.test_service_runtime tests.test_api_observability`
to inspect the privacy boundary before extending the logging surface.
