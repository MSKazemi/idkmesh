# ADR-0023 — Canonical Append-Only Event Source, Event Query API and Resumable SSE

**Status:** Accepted
**Date:** 2026-10-02

## Context

Issue #741 (API-6) asks to replace the Control Tower's derived "background
timeline" approximations with a canonical append-only event source, a
paginated historical query, scoped queries, and a resumable Server-Sent Events
stream. Acceptance: no fabricated timestamps; duplicate delivery is safe;
reconnect resumes without silently skipping durable events; bodies are
schema-validated and provenance-bound; SSE is read-only; WebSocket is deferred.

State of the repository (measured):

- `build_timeline` in `idkmesh/control_tower_api.py` derives a timeline from an
  evidence report the caller posts; no durable event record exists.
- `LocalMetadataStore` (SQLite, `user_version` 1) holds runs, an idempotency
  table, connections, probes and routes. `admit_run` and `update_run` already
  commit a run and its idempotency row in one SQLite transaction
  (`BEGIN IMMEDIATE`), so an event row can join that transaction.
- Several writers share the `runs` table with different metadata shapes:
  Product Spine CLI (`run create/cancel`), the offline idempotent spine, GitHub
  explicit dispatch and GitHub status update.
- ADR-0019 reserves only `attempts`, `evidence`, `decisions` as run
  sub-resource suffixes; ADR-0022 bounds the development server but says SSE
  needs its own client limit and timeout policy.

## Decision

1. **One canonical stream per store.** Events live in a new append-only
   `events` table of the same SQLite store. `sequence` (SQLite `AUTOINCREMENT`)
   is the stream's monotonic position. Because SQLite serialises writers, commit
   order equals sequence order, so a reader that has seen sequence N has seen
   every committed event up to N: there are no gaps to skip silently.
2. **Atomic emission.** An event is inserted in the same transaction as the
   state change that it records (`admit_run` / `update_run` take an optional
   `event`). Either both commit or neither does. An idempotent replay emits
   nothing, which is what makes duplicate emission impossible.
3. **No fabricated timestamps.** `occurred_at` is supplied by the producer (the
   validated timestamp the caller already passed for the state change). The
   store never reads a clock to invent one.
4. **Envelope** (`schemas/idkmesh-event-v0.1.schema.json`), all fields required
   and nullable only where stated:
   `schema_version` (`"0.1"`), `kind` (`"idkmesh-event"`), `event_id`
   (`evt-` + 12-digit zero-padded sequence; unique within the stream),
   `sequence` (integer >= 1), `occurred_at` (UTC `...Z`), `event_type`,
   `principal` (`{type, id}`), `authority_class`, `project_id`,
   `work_unit_id`, `run_id`, `attempt_id` (nullable), `source_revision`
   (nullable), `evidence_reference` (nullable `{kind, digest}`), `payload`
   (object), `payload_digest` (`sha256:` of the canonical payload JSON).
5. **Event types in v0.1:** `run.created` (payload `{state, request_digest}`)
   and `run.cancelled` (payload `{previous_state, state}`). Authority classes:
   `local_control`, `worker_observation`, `verifier_recommendation`,
   `human_decision`; v0.1 emits only `local_control` (a local control action),
   the others are reserved so a recommendation is never mistaken for a
   decision. `principal` is `{type: "unauthenticated_local", id: "local-cli"}`
   because the CLI has no authentication; the field exists so an enterprise
   profile can fill a real principal without a schema change.
6. **Emitter coverage is stated, not implied.** Only Product Spine
   `ProductSpineRunStore.create` and `.cancel` emit events. Offline-spine,
   GitHub dispatch and GitHub status writers emit none yet; `GET /events` is
   canonical for the events that exist, not a claim of completeness over every
   run-table writer. Extending coverage is a follow-up per writer.
7. **Query API.** `GET /api/v1/events` returns the existing
   `idkmesh-list-v0.1` envelope, ordered by `sequence` ascending, keyset
   paginated with an opaque listing-scoped cursor, bounded `limit`
   (1-200), and four exact-match filters: `project_id`, `run_id`,
   `work_unit_id`, `event_type`. An unknown parameter or an unknown
   `event_type` fails explicitly with 400. Scoped run and work-unit queries are
   these filters; no new path suffix is reserved, so ADR-0019 is unchanged.
8. **Resumable SSE.** `GET /api/v1/events/stream` is read-only `GET`.
   - Each message is `id: <sequence>`, `event: <event_type>`,
     `data: <compact JSON envelope>`.
   - `Last-Event-ID: N` resumes with every event of sequence > N, then follows
     live. Without it the stream starts at the live tail; history comes from
     `GET /events`. A non-integer or negative id, or one beyond the newest event of
     this stream (a client cannot have seen an uncommitted event; accepting it
     would silently skip events), is 400 `invalid_last_event_id`.
   - Same four filters as the query API. Delivery is at-least-once; clients
     dedupe on `event_id`.
   - Bounded: at most `max_sse_clients` streams (default 8, own limiter; beyond
     it 503 `too_many_streams` + `Retry-After`); a heartbeat comment every 15 s;
     a maximum stream lifetime of 300 s after which the server ends the stream
     and the client reconnects with `Last-Event-ID`; the poll interval is 0.5 s.
     Streams end promptly on drain.
   - SSE requests do not occupy general request-cap slots.
9. **Retention.** v0.1 keeps every event; nothing prunes the table. If a pruner
   is ever added, a cursor or `Last-Event-ID` below the retained floor must
   answer 410 `cursor_expired`, never a silent gap. Declared here, not built.
10. **Schema migration.** `SCHEMA_VERSION` becomes 2. A v1 store gains the
    `events` table in place; a v2 store opened by older code is refused by the
    existing "newer than supported" check. WebSocket is deferred.

## Implementation contract

Parallel implementers build against these exact names.

- `idkmesh/connector_store.py`: `SCHEMA_VERSION = 2`; `admit_run(..., event=None)`
  and `update_run(..., event=None)` where `event` is a mapping of the envelope
  fields excluding `sequence`, `event_id`, `schema_version`, `kind`,
  `payload_digest` (the store computes the last three plus the two ids);
  `LocalMetadataStore.list_events(*, limit, after_sequence=0, project_id=None,
  run_id=None, work_unit_id=None, event_type=None) -> (list[dict], bool)`;
  `latest_event_sequence() -> int`.
- `idkmesh/product_spine_run_store.py`: `EVENT_TYPES`, `EVENT_AUTHORITY_CLASSES`;
  `ProductSpineRunStore.list_events(*, limit=DEFAULT_LIST_LIMIT, cursor=None,
  project_id=None, run_id=None, work_unit_id=None, event_type=None) ->
  (list[dict], str | None)` raising `invalid_limit`, `invalid_cursor`,
  `invalid_event_type`; `events_after(sequence, *, limit=200, **filters) ->
  list[dict]`; `latest_event_sequence() -> int`.
- `idkmesh/control_tower_ui.py`: the two routes above; `create_server` /
  `serve_control_tower` gain `max_sse_clients` (default 8, valid 1-64);
  `ControlTowerServer.sse_limiter`; `drain()` drains both limiters.
- `idkmesh/service_runtime.py`: `limits_document` gains `max_sse_clients`,
  `sse_heartbeat_seconds`, `sse_max_stream_seconds`; the status schema gains
  those three as optional properties.
- `idkmesh/cli.py`: `idkmesh events list --store PATH [--limit N] [--cursor T]
  [--project-id ID] [--run-id ID] [--work-unit-id ID] [--event-type T] [--json]`
  and `control-tower --max-sse-clients N`.

## Consequences

### Positive

- The timeline can be rebuilt from durable, ordered, provenance-bound events;
  reconnects cannot skip a committed event.
- No new dependency; the events table reuses the store's transaction.
- Authority classes keep recommendations and decisions distinguishable before
  any such event exists.

### Costs

- Coverage starts narrow (two event types, one writer family).
- SSE is poll-based (0.5 s) with one thread per stream, which is acceptable
  only for the bounded local development profile; a production transport
  adapter would replace it.
- Opening a v2 store with older code fails closed.
- The table grows without bound until a pruner and the 410 contract exist.

## Alternatives considered

### Derive events from run rows on read

Rejected. State changes overwrite the run row, so history is lost and
timestamps would be inferred, which #741 forbids.

### Emit from the application layer after the commit

Rejected. A crash between the commit and the emit loses a durable event, which
is exactly the silent skip the issue forbids.

### A random UUID `event_id` with no sequence

Rejected. Resume needs a total order.

### WebSocket

Deferred per the issue; nothing needs a bidirectional channel.

### Reserve an `events` run sub-resource suffix

Rejected for v0.1. Filters give the same scoping without changing ADR-0019's
path-resolution rule.

## Implementation ownership

Issue #741 owns the contract. `connector_store.py` and
`product_spine_run_store.py` own durability and the service API;
`control_tower_ui.py` owns transport; the spec
`docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md` owns the endpoint text.

## Revisit conditions

Revisit if events must cover other run-table writers, a pruner is proposed,
an enterprise principal profile lands, or a production transport adapter
replaces the stdlib server.

## Update 2026-10-02 (static review)

A read-only static review of the implementation, before any test had run,
clarified how decisions 2, 4 and 8 are enforced. The decisions are unchanged.

- **Envelope enforcement (decision 4).** The store, not only the schema, rejects
  an event whose `event_type` is not `run.created` or `run.cancelled`, whose
  `authority_class` is not one of the four reserved classes, whose `occurred_at`
  is not a UTC timestamp ending in `Z`, whose `source_revision` is not null or
  40/64 hex characters, or whose `run_id` differs from the run it is committed
  with. The rejection is a `ValueError` raised before the transaction opens, so
  nothing is written and decision 2's atomicity holds. The enumerated `event_type` also keeps the SSE `event:` line
  free of control characters.
- **One event per transition (decision 2).** `update_run` takes
  `expected_state`; a racing second writer gets `LocalStoreConflict` and appends
  nothing. `cancel` then returns the already-cancelled run, or fails with
  `cancel_conflict` if the run moved to another state, so two concurrent cancels
  emit one `run.cancelled` with a true `previous_state`.
- **Inputs.** A blank `project_id`, `run_id` or `work_unit_id` is
  `invalid_filter`; cursors are bounded ASCII-decimal sequences (at most 18
  digits).
- **Faults and retry semantics.** A SQL error from the store is a
  `LocalStoreError`; an open stream ends with `: stream-ended reason=store-error`
  instead of dropping the connection. The 503 capacity responses carry
  `retryable: true`. Only a `GET` on the stream path uses the stream limiter, so
  other methods get `405 Allow: GET`.
- **Coverage (decision 6).** A run created before the store reached version 2
  has no `run.created` event, so cancelling it later yields a `run.cancelled`
  with no earlier event for that run.
