---
title: "Control Tower API Error Catalog"
description: "Every stable error code the local Control Tower HTTP API can return, with its HTTP status, retryability, trigger and recommended client action, plus the Python client's exception taxonomy."
---
# Control Tower API error catalog

Every non-2xx answer from `/api/v1/...` is one JSON error envelope, frozen by
[`schemas/idkmesh-api-error-v0.1.schema.json`](https://github.com/MSKazemi/idkmesh/blob/main/schemas/idkmesh-api-error-v0.1.schema.json):

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-api-error",
  "ok": false,
  "error": {"code": "run_not_found", "message": "unknown run_id: run/x", "retryable": false}
}
```

**Branch on `error.code`, never on `message`.** `code` is a compatibility
contract ([API v1 beta guide](../API_V1_BETA_MIGRATION_GUIDE.md)); `message` is
explanatory text and may change. `error.retryable` says whether an identical
retry could plausibly succeed without the caller changing anything; it is `true`
only for the three capacity rejections at the end of the catalog, each of which
also carries a `Retry-After` header and `error.details.retry_after_seconds`.
`error.details` is optional and bounded; it never carries secrets.

This is the **local, loopback, read/inspect profile**. It has no per-client
identity, so there is no `429`; server-wide saturation is `503` (see
[service limits](API_LIMITS.md)).

**How this page stays true.** `tests/test_api_reference_docs.py` extracts the
codes from `idkmesh/control_tower_ui.py` and the run-store modules and fails if
a code is in the source but not here, or here but not in the source. It then
reproduces every row against a live server and fails if the HTTP status,
`retryable` value or `Retry-After` header differs. The tests that follow are
the only authority for the "Status" and "Retry" columns.

Columns: **Status** is the HTTP status; **Retry** is the value of
`error.retryable`.

## Request, authentication and routing

| Code | Status | Retry | When it is returned | What to do |
|---|---|---|---|---|
| `invalid_host` | 403 | no | the `Host` header is not a loopback name (DNS-rebinding guard) | send requests to `127.0.0.1` or `localhost` only |
| `invalid_session_token` | 403 | no | `X-IDKMesh-UI-Token` is missing, wrong, or not ASCII | send the exact token the server was started with; this check precedes every other `/api/v1` check |
| `unsupported_api_version` | 404 | no | a path under `/api/` that is not `/api/v1/...`; `details.supported_versions` lists the supported versions | use `/api/v1/` |
| `not_acceptable` | 406 | no | `Accept` allows none of `application/json`, `application/vnd.idkmesh.control-tower.v1+json`, `application/*`, `*/*` (`text/event-stream` is also allowed on the event stream) | send `Accept: application/json` |
| `unexpected_query_parameters` | 400 | no | a query string on an endpoint that takes none | remove the query string |
| `method_not_allowed` | 405 | no | the route exists but not for this method; the `Allow` header lists what does | use a method from `Allow` |
| `preflight_not_supported` | 405 | no | cross-origin `OPTIONS` preflight; the API is same-origin only | call it from a non-browser client or the same origin |
| `not_found` | 404 | no | no such endpoint (this includes the not-yet-built `/decisions` sub-resource) | check the route against [`/api/v1/openapi.json`](API_QUICKSTART.md#discover-the-live-api) |

## Request body (`POST /api/v1/run-evidence/inspect`)

Only this route reads a request body; the 2 MiB cap and the other body limits
are in [service limits](API_LIMITS.md).

| Code | Status | Retry | When it is returned | What to do |
|---|---|---|---|---|
| `unsupported_transfer_encoding` | 400 | no | `Transfer-Encoding` (chunked) request bodies | send a fixed `Content-Length` body |
| `unsupported_media_type` | 415 | no | `Content-Type` is neither `application/json` nor the vendor JSON type | send `Content-Type: application/json` |
| `length_required` | 411 | no | no `Content-Length` | send a `Content-Length` header |
| `invalid_content_length` | 400 | no | `Content-Length` is not plain digits (`+2`, `-0` and similar are rejected) | send decimal digits only |
| `payload_too_large` | 413 | no | declared body above the cap; rejected before the body is read | send a smaller report |
| `request_timeout` | 408 | no | the body was not fully received within the request timeout | send the whole body promptly, or raise `--request-timeout` |
| `invalid_utf8` | 400 | no | the body is not valid UTF-8 | send UTF-8 JSON |
| `invalid_run_evidence` | 400 | no | the body is not a valid run-evidence report (malformed or duplicate-key JSON, wrong shape, too deeply nested) | fix the report; `message` names the first problem |

## Read model (runs, work units, projects, events, connections)

| Code | Status | Retry | When it is returned | What to do |
|---|---|---|---|---|
| `product_spine_store_not_configured` | 503 | no | the server was started without `--product-spine-store`; every store-backed read answers this | start the server with a store; retrying does not help, which is why `retryable` is `false` |
| `invalid_limit` | 400 | no | `limit` outside 1-200 (runs, work units, events, connections) | use a limit from 1 to 200 |
| `invalid_cursor` | 400 | no | `cursor` was not issued by this service for that listing | pass back `next_cursor` unmodified; never build cursors |
| `invalid_state` | 400 | no | `state` is not a canonical Product Spine lifecycle state | use one of the canonical lifecycle states in the Control Tower spec |
| `invalid_event_type` | 400 | no | `event_type` is not a known event type | use one of the known event types in the Control Tower spec |
| `invalid_filter` | 400 | no | a `project_id`, `run_id` or `work_unit_id` filter is blank | omit the filter or give it a value |
| `invalid_last_event_id` | 400 | no | `Last-Event-ID` on the event stream is not a non-negative integer, or is beyond the newest event (that form carries `details.latest_sequence`) | resume from a sequence you actually received |
| `run_not_found` | 404 | no | no stored run has this `run_id` | check the identity; run IDs may contain `/` and `:` |
| `work_unit_not_found` | 404 | no | no stored run references this work unit | check the identity |
| `project_not_found` | 404 | no | no stored run names this project | check the identity |
| `evidence_not_available` | 404 | no | the run exists but retains no evidence report | not an error in the run; there is nothing to fetch |
| `evidence_integrity_error` | 500 | no | the retained report no longer matches the run's `evidence_report_digest`; the report is never served | treat the store as damaged; do not retry |
| `store_error` | 500 | no | the local store is locked, unreadable or corrupt, or cannot be opened | inspect the store file; do not assume a retry will help |
| `persisted_state_corrupt` | 400 | no | a stored run row fails its own consistency checks (digest, projection or state disagree) | repair or recreate the store. This is a server-side fault answered with a `400` today, so branch on the code, not the status class |
| `not_product_spine_cli_run` | 400 | no | `GET /api/v1/runs/{run_id}` named a row in the shared runs table that is not a Product Spine run (for example a GitHub dispatch record) | use a Product Spine run ID |
| `connection_record_invalid` | 500 | no | `GET /api/v1/connections` met a stored connector row that fails validation | repair the connector store |

## Capacity (the only retryable codes)

| Code | Status | Retry | When it is returned | What to do |
|---|---|---|---|---|
| `overloaded` | 503 | yes | the concurrent-request cap is reached; no application work was done | wait `Retry-After` seconds (and add jitter), then retry |
| `too_many_streams` | 503 | yes | `GET /api/v1/events/stream` and every event-stream slot is open | wait `Retry-After`, or close an idle stream |
| `shutting_down` | 503 | yes | the server is draining and accepts no new requests (`/healthz` still answers) | wait `Retry-After`; the next instance may be a restart |

## Responses that are not the JSON envelope

The Python standard-library HTTP parser rejects some malformed requests before
IDKMesh code runs, so the body is not an `idkmesh-api-error` document:
`414` for a request line over the limit and `431` for too many or too large
header lines. The limits are in [service limits](API_LIMITS.md). The Python
client treats a response without the envelope as a `ProtocolError`.

## Python client: exception taxonomy

`idkmesh.api_client.ControlTowerClient` makes exactly one HTTP request per
call and never retries. Every failure is one of these classes (all subclass
`ControlTowerClientError`):

| Exception | Raised when | Carries |
|---|---|---|
| `ClientConfigurationError` | the base URL, token, timeout or an argument is unsafe or invalid, before any I/O | message |
| `TransportError` | the one HTTP exchange could not complete (refused, timed out, reset) | message |
| `ProtocolError` | the response violates the published contract (wrong media type, missing request ID, no envelope, wrong resource identity) | message |
| `IntegrityError` | a response or embedded digest does not verify (subclass of `ProtocolError`) | message |
| `ApiResponseError` | the server returned a schema-shaped error envelope | `status_code`, `code`, `message`, `retryable`, `details`, `request_id` |

`client.stream_events()` uses the same classes and adds no new one. An error the
server sends before the stream starts is an `ApiResponseError`; a stalled stream
or a drop without a `stream-ended` marker is a `TransportError`; a frame that
breaks the SSE contract is a `ProtocolError`; an event whose `payload_digest`
does not verify is an `IntegrityError`.

An `ApiResponseError` is the only class that corresponds to a row in this
catalog. Quote `request_id` when reporting a problem. See the
[quickstart](API_QUICKSTART.md#handle-errors) for a worked example.

## Adding or changing a code

A new code is an *additive compatible* change; removing or renaming one, or
changing its status or `retryable` value, is *breaking* and needs a decision
record ([compatibility and deprecation policy](../API_V1_BETA_MIGRATION_GUIDE.md#how-change-is-announced)).
Add the row here in the same change; the drift tests above fail otherwise.
