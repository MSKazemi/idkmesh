# ADR-0022 — Bounded Service Limits for the Control Tower Development Server

**Status:** Accepted
**Date:** 2026-10-02

## Context

Issue #742 (API-7) asks for predictable behavior under slow, concurrent,
malformed or overloaded clients: request timeout, header and body limits, a
concurrency cap, bounded queues, `Retry-After` on overload, graceful drain,
and a documented connection policy. Its multi-user note says a public or
network deployment must use a reviewed production transport adapter rather
than expose the stdlib development server.

Measured state of `idkmesh/control_tower_ui.py` before this decision:

- `ControlTowerServer` is a stdlib `ThreadingHTTPServer` with
  `daemon_threads = True`: one thread per connection and no cap.
- There is no socket timeout, so a client that sends half a request line holds
  a thread indefinitely.
- Only one global body cap exists (`MAX_BODY_BYTES`, 2 MiB), enforced on the
  single endpoint that reads a body.
- `serve_control_tower` calls `server_close()` on exit but never waits for an
  in-flight request, because daemon threads are not joined.
- The stdlib parser already bounds the request line (414 above 65536 bytes) and
  the header block (431 above 99 header fields or for a header line over 65536
  bytes; the stdlib allows 100 lines but counts the terminating blank line).
  Nothing documented or tested this.
- The service has no per-client identity: it authenticates one loopback
  session token. At the time of this decision there was no SSE stream. ADR-0023
  later added the event stream with its own bounded client limiter, heartbeat,
  maximum lifetime, and drain behavior; those limits now compose with this ADR.

## Decision

Apply the following limits to the Control Tower development server, publish
them, and prove each one with a test.

1. **Request timeout.** Every connection gets a socket timeout (default 10 s,
   configurable). A client that stalls while sending the request line, headers
   or body is dropped. A stalled body read answers `408 request_timeout` where
   the socket still allows a response.
2. **Concurrency cap.** At most N requests (default 16, configurable) are
   handled at once. The cap is enforced by a thread-safe limiter shared across
   handlers. Beyond the cap a request is answered `503 overloaded` with a
   `Retry-After` header and the standard error envelope, without doing any
   application work. `GET /healthz` is exempt so liveness stays cheap.
3. **Bounded queue.** The listen backlog is set explicitly
   (`request_queue_size = 16`). The cap bounds concurrent request handling, not
   accepted connections; this is stated rather than implied.
4. **Graceful drain.** A drain flag makes new requests answer
   `503 shutting_down` (including `/readyz`, so an orchestrator stops routing)
   while `/healthz` still answers. `serve_control_tower` begins a drain on
   shutdown and waits up to 5 s for in-flight requests before closing. Every
   endpoint is read-only or a pure inspection, so no drain can leave a
   partially committed mutation.
5. **No `429` in v0.1.** `429 Retry-After` signals that one client exceeded its
   own rate. With a single local token there is no per-client identity to
   attribute a rate to, so emitting `429` would be fabricated precision.
   Server-wide saturation is `503`. `429` is reserved for the enterprise
   identity profile (ADR-0014/0016) and recorded as not implemented.
6. **Existing stdlib parser bounds are adopted as the documented contract**
   (request line 65536 bytes, header line 65536 bytes, 99 header fields, plus
   the 2 MiB body cap) and pinned by tests that fail if the stdlib behavior
   changes.
7. **Connection policy.** One request per connection (the stdlib HTTP/1.0
   default); no keep-alive.
8. **Discoverability.** The status document gains an optional
   `operations.limits` object reporting the limits actually in force.
   Adding an optional property is a non-breaking change under ADR-0020, so the
   frozen status schema is extended in place rather than versioned.
9. **Cancellation/disconnect behavior.** Every admitted request releases its
   limiter slot in a `finally` path even when the client disconnects before
   the response is written. The server does not retry interrupted application
   work. SSE disconnects terminate the stream on broken-pipe/reset/timeout and
   release the separate stream slot. Because this local profile is read-only
   plus pure inspection, an abandoned response cannot leave a partially
   committed mutation.
10. **Bounded SSE clients.** ADR-0023 adds a separate non-blocking limiter
    (default 8, configurable 1-64), heartbeat, maximum stream lifetime, and
    drain integration. SSE clients therefore cannot consume the general
    request pool or hold a worker thread indefinitely.

Tunables are exposed as `idkmesh control-tower --request-timeout SECONDS` and
`--max-concurrent-requests N`, validated to sane ranges.

## Consequences

### Positive

- A stalled or flooding local client can no longer pin the server or starve it
  silently; the failure is a deterministic `503` plus `Retry-After`.
- Shutdown no longer abandons an in-flight request.
- Limits are observable from the API and every claim has a test.

### Costs

- The cap bounds request handling, not connections: a connection flood still
  creates short-lived threads that answer `503`. The backlog bound and the
  loopback-only bind keep this acceptable for a development server.
- A POST rejected at the cap is answered without reading its body and the
  connection is closed, so a large body may see a connection reset instead of
  the `503`.
- Per-client `429` remains unimplemented until a trustworthy per-client
  identity exists. SSE capacity is now implemented under ADR-0023 with a
  separate limiter so long-lived streams do not consume general request slots.
- The same hardening is not applied to the other local stdlib servers
  (`gate-audit-ui`, steward UIs); they stay as before.

## Alternatives considered

### Adopt an ASGI/WSGI production server now

Rejected for this slice. It adds a dependency to a base install that #742
requires stay dependency-light, and the issue itself defers the network
profile to a reviewed transport adapter.

### Emit `429` for concurrency saturation

Rejected. It conflates server overload with a per-client quota and gives
clients wrong retry semantics.

### Block instead of rejecting beyond the cap

Rejected. An unbounded wait queue is an unbounded memory and latency
commitment, which is exactly what #742 asks to remove.

### Apply the limiter at the socket-accept layer

Rejected. Rejecting before parsing cannot exempt `/healthz` or return the
standard envelope with the request id and security headers.

## Implementation ownership

- Issue #742 owns the contract; this ADR bounds what v0.1 of the development
  server promises.
- `idkmesh/service_runtime.py` owns the reusable limiter and limit constants;
  `idkmesh/control_tower_ui.py` applies them;
  `docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md` documents them.

## Revisit conditions

Revisit this ADR if:

- the SSE/event-stream contract changes in a way that needs a different
  capacity, heartbeat, lifetime, or cancellation policy;
- a network or multi-user profile introduces per-principal identity (add
  `429` and per-principal quotas) or a production transport adapter (move the
  limits there);
- the other local servers need the same limits (promote the limiter to a
  shared base server).
