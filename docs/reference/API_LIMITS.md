---
title: "Control Tower API Service Limits"
description: "The request, concurrency, body, header, retry, drain and event-stream limits the local Control Tower enforces, which flags tune them, and how to read the values in force from the status endpoint."
---
# Control Tower API service limits

The Control Tower is a standard-library HTTP server bound to loopback. It
enforces the bounded limits below
([ADR-0022](../decisions/ADR-0022-control-tower-bounded-service-limits.md),
[ADR-0023](../decisions/ADR-0023-canonical-append-only-event-source.md)) so that a slow, malformed or flooding local
client gets a deterministic answer instead of pinning the process. It is a
development and single-user server: a public or network deployment needs a
reviewed production transport adapter, not this server.

You do not have to trust this page for the values in force. They are published
by the running server at `operations.limits` on `GET /api/v1/status`
(`ControlTowerClient.status()` returns them), and
`tests/test_api_reference_docs.py` fails if any number here differs from that
document, from the runtime constants in `idkmesh/service_runtime.py`, or from
the range the validators enforce. The behaviour of each limit is proven by
`tests/test_control_tower_limits.py` and `tests/test_control_tower_events.py`.

## Published limits

Defaults of a server started with no tuning flags, exactly as
`GET /api/v1/status` reports them under `operations.limits`.

| Key | Default | Meaning |
|---|---|---|
| `request_timeout_seconds` | `10.0` | socket timeout on every connection |
| `max_concurrent_requests` | `16` | requests handled at once; more are rejected, not queued |
| `retry_after_seconds` | `1` | value of `Retry-After` on a capacity `503` |
| `drain_timeout_seconds` | `5.0` | how long a graceful shutdown waits for in-flight requests |
| `max_request_line_bytes` | `65536` | longest request line; longer answers `414` |
| `max_header_line_bytes` | `65536` | longest header line; longer answers `431` |
| `max_header_count` | `99` | most header fields in one request (including `Host`); 100 answers `431` |
| `max_request_body_bytes` | `2097152` | request body cap (2 MiB); larger answers `413 payload_too_large` |
| `overload_status` | `503` | status used when the concurrency cap is reached |
| `connection_policy` | `"close_after_response"` | one request per connection; no keep-alive |
| `per_client_rate_limit` | `"not_implemented"` | there is no per-client quota and no `429` |
| `max_sse_clients` | `8` | open event streams at once |
| `sse_heartbeat_seconds` | `15.0` | idle event streams get a `: keepalive` comment this often |
| `sse_max_stream_seconds` | `300.0` | the server ends a stream after this long; resume with `Last-Event-ID` |

## Tunable limits

Three limits are set when the server starts (`idkmesh control-tower` or the
`create_server` keyword of the same name). A value outside the range is
refused at startup.

| Flag | Minimum | Maximum | Default |
|---|---|---|---|
| `--request-timeout` | `0.1` | `300.0` | `10.0` |
| `--max-concurrent-requests` | `1` | `1024` | `16` |
| `--max-sse-clients` | `1` | `64` | `8` |

The other limits are fixed. The request-line, header-line and header-count
bounds are the Python standard library parser's own, measured and pinned by
tests rather than re-implemented.

## What a client sees

| Situation | Answer | Retry? |
|---|---|---|
| concurrency cap reached | `503 overloaded`, `Retry-After`, no application work done, connection closed | yes, after `Retry-After` |
| no free event-stream slot | `503 too_many_streams`, `Retry-After` | yes, after `Retry-After` |
| server draining | `503 shutting_down`, `Retry-After` (`/readyz` too) | yes, after `Retry-After` |
| body not received in time | `408 request_timeout` | resend the whole body |
| slow request line or headers | the connection is dropped; there may be no response | resend |
| body over 2 MiB declared | `413 payload_too_large`, body unread | no |
| request line over 65536 bytes | `414` (stdlib answer, not the JSON envelope) | no |
| header line over 65536 bytes, or more than 99 fields | `431` (stdlib answer, not the JSON envelope) | no |
| any per-client overuse | not emitted: no `429` exists in this profile | n/a |

The codes are catalogued in the [error catalog](API_ERROR_CATALOG.md).

Semantics worth knowing:

- `GET /healthz` is exempt from the cap and from drain rejection, so liveness
  stays cheap. Every other request, `GET /readyz` included, is admitted or
  rejected.
- The cap bounds concurrent request *handling*, not accepted connections. A
  connection flood still creates short-lived threads that answer `503`.
- A `POST` rejected at the cap is answered without its body being read and the
  connection is closed, so a client sending a large body may see a connection
  reset instead of the `503`.
- There is no application wait queue: saturation is rejected immediately. The
  listen backlog is 16.
- Event streams are counted by their own limiter and never use a general
  request slot. A stream is read-only; a disconnect releases its slot.
- An interrupted request is never retried by the server, and every endpoint is
  read-only or a pure inspection, so a drain or disconnect cannot leave a
  partially committed change.
- The Python client's own `timeout` is mandatory, has no default, and is
  independent of the server's `request_timeout_seconds`. The client also
  rejects `limit` outside 1-200 before any I/O, matching the server.

## Not covered

Only the Control Tower server is hardened this way; `gate-audit-ui` and the
steward UIs keep their previous behaviour. There is no authentication tier, no
per-principal quota and no production transport adapter in this profile; those
belong to the network profile described in the
[API authority matrix](../specifications/API_AUTHORITY_MATRIX_V0_1.md), which
is a proposal rather than something enforced today.
