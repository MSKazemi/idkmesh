---
description: "Local, read-only /api/v1 HTTP API exposing produced IDKMesh evidence to human-facing clients, without scheduling, verifying, writing to repos, or merging."
---
# Control Tower Local API v0.1

**Status:** experimental, local-only, read-only  
**HTTP version prefix:** `/api/v1`  
**Object schema version:** `0.1`  
**Issue:** #572  
**Product surface:** `idkmesh control-tower`

## Purpose

The Control Tower Local API is the first machine-readable product boundary for
the Human Control Tower. It exposes already-produced IDKMesh evidence for local
human-facing clients without becoming a scheduler, verifier, decision maker,
repository writer, or merge authority.

Its first canonical input contract is:

```text
idkmesh-run-evidence-report / schema_version 0.1
```

Its primary output contract is:

```text
idkmesh-control-tower-snapshot / schema_version 0.1
```

The corresponding JSON Schema is:

`schemas/control-tower-snapshot-v0.1.schema.json`

The API and browser UI consume the same Python service layer. Neither is a
second source of project truth.

## Versioning model

The HTTP prefix and object schema version are intentionally distinct:

```text
HTTP API compatibility line: /api/v1
response schema version:      0.1
```

Additive compatible response fields may remain under `/api/v1` with a new
explicit object schema version only when clients can safely ignore them.
Incompatible HTTP behavior requires a new URL version.

Unknown versions fail explicitly with:

`unsupported_api_version`

and return the supported version list.

## Trust boundary

The service binds only to:

`127.0.0.1`

This is a local process boundary, not a claim that localhost is a complete
sandbox against a compromised machine.

Every API request except `GET /healthz`, `GET /readyz`, and the HTML document itself requires:

```http
X-IDKMesh-UI-Token: <session-token>
```

The default token is a random per-process value embedded only in the locally
served browser page.

For intentional headless/local automation, callers may provide a stable token
through:

```text
IDKMESH_CONTROL_TOWER_TOKEN
```

The value must contain 32–4096 characters drawn only from ASCII letters,
digits, `-`, `.`, `_`, and `~`. Restricting the alphabet keeps the token safe
for both HTTP-header use and embedding into the locally generated HTML/JS. It
is never printed by the server. Environment injection exists so a local client
can know the token without weakening the browser default.

The server also:

- accepts only loopback `Host` values;
- compares session tokens with constant-time comparison;
- rejects cross-origin preflight;
- rejects transfer-encoded/chunked request bodies;
- caps request bodies at 2 MiB;
- emits no-store, frame, referrer, content-type, cross-origin, permissions and
  CSP protection headers.

### Enterprise service-runtime metadata

The Control Tower consumes the shared HTTP Service Runtime Baseline v0.1.

Every response carries bounded operational metadata:

```text
X-Request-ID
X-IDKMesh-Service
X-IDKMesh-Service-Version
X-IDKMesh-API-Version
X-IDKMesh-Read-Only
```

A safe caller-provided `X-Request-ID` is echoed for correlation. Invalid or
oversized values are replaced rather than reflected. Request IDs are not user
identity, authorization, or evidence.

Optional access logging is enabled with:

```text
IDKMESH_HTTP_ACCESS_LOG=1
```

Each log line is compact JSON containing request ID, method, path, response
status/size, duration, service, and event time. Query strings are stripped and
the logging API does not accept request bodies, authorization/session headers,
prompts, or secret material. Logging failure does not turn an otherwise valid
read-only response into an application failure.


## Authority invariant

The Control Tower is presentation and inspection only.

A Run Evidence Report is refused unless its authority object is exactly:

```json
{
  "canonical_state_write": false,
  "git_push": false,
  "merge": false,
  "automatic_candidate_selection": false
}
```

and its human decision remains exactly:

```json
{
  "status": "pending",
  "selected_attempt_id": null,
  "integration_authority": "external_human_or_governance"
}
```

v0.1 therefore cannot:

- execute workers;
- rerun or replace independent verification;
- record a human decision;
- select a candidate;
- mutate canonical project state;
- push Git;
- merge.

Those capabilities require separately reviewed contracts and authority.

## Media types

Requests to the inspection endpoint may use either:

```text
application/json
application/vnd.idkmesh.control-tower.v1+json
```

Clients may request either through `Accept`.

If the vendor type is explicitly requested, the server responds with that vendor
media type. Otherwise it returns ordinary `application/json`.

Unsupported response media types return HTTP 406 with
`not_acceptable`.

Unsupported request media types return HTTP 415 with
`unsupported_media_type`.

API responses include:

```http
Vary: Accept
X-IDKMesh-API-Version: v1
X-IDKMesh-Read-Only: true
X-IDKMesh-Content-Digest: sha256:<64-hex>
ETag: "<64-hex>"
```

The content digest is computed from the canonical JSON value using the same
sorted-key/minified UTF-8 SHA-256 rule used by repository provenance code.

The API still sends `Cache-Control: no-store`; ETag/content-digest headers are
integrity and deterministic-equality signals, not permission to cache sensitive
evidence.

## Determinism

The inspection endpoint is read-only and deterministic.

For the same valid input document and API implementation:

```text
same Run Evidence Report
 -> same Control Tower snapshot
 -> same response body bytes
 -> same snapshot_digest
 -> same X-IDKMesh-Content-Digest
 -> same ETag
```

No timestamp, random ID, host information, or mutable repository state is added
to the snapshot.

## Endpoint discovery

### `GET /healthz`

Unauthenticated process-liveness check:

```text
ok
```

It reveals no evidence/project state. It is exempt from the concurrent-request
cap and keeps answering `200` while the server drains, so liveness stays cheap
under saturation (see [Service limits](#service-limits)).

Supported methods:

```text
GET, HEAD
```

### `GET /readyz`

Unauthenticated service-readiness check. It returns only service/API runtime
metadata and no project, WorkUnit, run, evidence, secret, prompt, or identity
state.

Representative shape:

```json
{
  "status": "ready",
  "service": "idkmesh-control-tower",
  "service_version": "...",
  "mode": "local-read-only",
  "api_version": "v1"
}
```

Liveness and readiness are intentionally separate: a future service may be alive
while a required runtime dependency is not ready. Today the one concrete
difference is service pressure: `GET /readyz` is counted against the
concurrent-request cap and answers `503 overloaded` at the cap or
`503 shutting_down` while draining, each with `Retry-After`, so an orchestrator
stops routing to an instance that cannot take work.

Frozen by `schemas/idkmesh-readiness-v0.1.schema.json`. Built by the shared
`idkmesh/service_runtime.py:readiness_document()`, so any future IDKMesh HTTP
service reuses this same contract rather than defining its own.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/status`

Authenticated discovery document.

The response includes:

- API version;
- object schema version;
- service/mode;
- accepted media types;
- source contracts;
- schema URLs;
- enabled read capabilities;
- explicitly disabled actuation capabilities;
- the service limits in force (`operations.limits`, see
  [Service limits](#service-limits));
- endpoint list.

Representative shape:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-status",
  "ok": true,
  "service": "idkmesh-control-tower",
  "mode": "local-read-only",
  "media_types": [
    "application/json",
    "application/vnd.idkmesh.control-tower.v1+json"
  ],
  "capabilities": {
    "run_evidence_inspection": true,
    "semantic_timeline": true,
    "provenance_chain": true,
    "human_decision_recording": false,
    "worker_execution": false,
    "canonical_state_write": false,
    "git_push": false,
    "merge": false,
    "automatic_candidate_selection": false
  }
}
```

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/openapi.json`

Authenticated OpenAPI 3.1 discovery document.

It describes:

- the local-session-token security scheme;
- liveness and readiness endpoints;
- status endpoint;
- OpenAPI endpoint;
- run-evidence inspection endpoint;
- run list/read/attempts and WorkUnit list/read endpoints;
- supported request media types;
- core response/error status codes;
- published schema references.

This endpoint is generated from the same installed Python API constants as the
server behavior so client discovery is not maintained as a detached static
copy.

Supported methods:

```text
GET, HEAD
```

### `POST /api/v1/run-evidence/inspect`

Authenticated, read-only inspection endpoint.

Body:

one complete `idkmesh-run-evidence-report` v0.1 JSON document.

No query parameters are accepted in v1.

The service rejects:

- malformed JSON;
- duplicate JSON keys;
- non-finite JSON constants such as `NaN` or `Infinity`;
- unsupported report kinds/versions;
- malformed digests;
- duplicate attempt IDs;
- invalid attempt states;
- malformed required checks;
- recommendation/evidence-state mismatch;
- report summary drift;
- authority drift;
- non-pending human decision state;
- invalid UTF-8;
- unsupported request media type;
- transfer-encoded/chunked bodies;
- bodies over 2 MiB.

Successful response envelope:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-inspection-response",
  "ok": true,
  "snapshot_digest": "sha256:...",
  "snapshot": {
    "kind": "idkmesh-control-tower-snapshot",
    "schema_version": "0.1"
  }
}
```

Supported method:

```text
POST
```

Wrong methods return HTTP 405 with an `Allow` header. `HEAD` on a POST-only
resource also returns no body.

### `GET /api/v1/connections`

Authenticated, read-only connector-control listing (API-3, issue #738). This
is the first implemented HTTP slice from the Connector Control API contract
and deliberately lives in the existing Control Tower service rather than
creating a second HTTP server.

The endpoint reads the same `LocalMetadataStore` connection table used by
`idkmesh connections stored`. Only the canonical secret-free import summary is
projected. It never returns a secret reference or `settings`. A legacy/free-
form row with missing, mismatched, or extra fields fails closed with
`500 connection_record_invalid` rather than being serialized as an API resource.

Query parameters are `limit` (1-200, default 50) and an opaque `cursor`.
Ordering is by persisted connection id with keyset pagination. Unknown or
duplicate parameters fail with `400 unexpected_query_parameters`; a cursor
not issued by this connection-list service fails with `400 invalid_cursor`.

The server must be started with `--product-spine-store PATH`, the shared local
metadata database; otherwise the endpoint returns
`503 product_spine_store_not_configured`.

Each item conforms to `schemas/idkmesh-connection-resource-v0.1.schema.json`,
wrapped by the shared `idkmesh-list-v0.1` envelope.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/runs`

Authenticated, read-only Product Spine run listing (issue #739). Serves the
same `idkmesh/product_spine_run_store.py:ProductSpineRunStore.list()`
application service `idkmesh run list` already uses, deterministically
ordered by `run_id` with keyset (not offset) pagination -- API Conventions
v0.1 sections 10-11.

This is one of two Control Tower endpoints that accept query parameters
(the other is `GET /api/v1/work-units`):

- `limit` (optional integer, 1-200, default 50);
- `cursor` (optional opaque string from a previous response's
  `page.next_cursor`; never constructed or parsed by the caller);
- `state` (optional, an exact canonical Product Spine lifecycle state --
  `proposed`, `previewed`, `admission_blocked`, `admitted`, `dispatched`,
  `attempt_failed`, `candidate_observed`, `normalized`,
  `verification_requested`, `verification_error`, `evidence_ready`,
  `awaiting_human_decision`, `decided`, or `cancelled`);
- `project_id` (optional, an exact match; not a search/prefix).

Any other query parameter, or any of these repeated, is rejected with
`400 unexpected_query_parameters` (API Conventions v0.1 section 11: an
unknown filter fails explicitly rather than being silently ignored). An
out-of-range `limit` is rejected with `400 invalid_limit`; an unrecognized
`state` value is rejected with `400 invalid_state` rather than silently
matching zero rows. Like `GET /api/v1/runs/{run_id}`, this endpoint returns
`503 product_spine_store_not_configured` when this server instance was not
started with `--product-spine-store`.

`state` and `project_id` combine with AND, not OR: passing both narrows to
runs matching both.

The list contains **Product Spine runs only**, selected by an explicit set of
stored row kinds (`product-spine-cli-run`, created by `idkmesh run create`,
and `product-spine-idempotency-result`, the completed rows of the idempotent
offline Product Spine). The shared `runs` table also holds admission-only,
execution-error and GitHub dispatch/status rows; those are not Product Spine
runs and are excluded deterministically, including from keyset pagination
([ADR-0024](../decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)).
Before this rule a single non-Product-Spine row in the store made the whole
page fail; that defect is fixed. A row of a listed kind that does not restore
still fails loudly rather than being skipped.

Representative shape:

```json
{
  "kind": "idkmesh-list",
  "schema_version": "0.1",
  "items": [
    {
      "schema_version": "0.1",
      "kind": "idkmesh-product-spine-run",
      "run_id": "...",
      "state": "proposed"
    }
  ],
  "page": {
    "next_cursor": null,
    "limit": 50
  }
}
```

Frozen by the cross-cutting `schemas/idkmesh-list-v0.1.schema.json` (API
Conventions v0.1 section 10) wrapping
`schemas/idkmesh-product-spine-run-v0.1.schema.json` items -- no new envelope
schema was needed for this endpoint.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/runs/{run_id}`

Authenticated, read-only Product Spine run projection (issue #739, the first
slice of the API-4 read model). Serves the same
`idkmesh/product_spine_run_store.py:ProductSpineRunStore.status()`
application service `idkmesh run status` already uses -- the CLI and this
endpoint read through one service, never two.

This server instance only exposes it when started with
`--product-spine-store PATH` (or `create_server(...,
product_spine_store_path=...)` programmatically); otherwise every request
returns `503` with code `product_spine_store_not_configured`.

`run_id` may itself contain `/` (Product Spine run_ids share WorkUnit's
identifier grammar). [ADR-0019](../decisions/ADR-0019-run-subresource-suffix-reservation.md)
reserves `attempts`, `evidence`, and `decisions` as the only recognized
trailing path segments: a path ending in `/attempts`, `/evidence`, or
`/decisions` (with at least one character before it) always resolves as
that sub-resource of the remaining prefix, regardless of whether that
derived `run_id` exists; every other path is read as one literal `run_id`.
The accepted cost: a `run_id` that itself ends in one of those three
literal suffixes can no longer be read through this plain single-run `GET`
-- see `GET /api/v1/runs/{run_id}/attempts` below.

Representative shape:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-run-response",
  "ok": true,
  "run": {
    "schema_version": "0.1",
    "kind": "idkmesh-product-spine-run",
    "run_id": "...",
    "state": "proposed"
  },
  "idempotency_key": "...",
  "create_request_digest": "sha256:...",
  "created": false,
  "replayed": false,
  "provider_execution_terminated": false,
  "candidate_accepted": false,
  "merge_authority": false
}
```

`created` and `replayed` are always `false` here: they describe a create
call's outcome, carried over unchanged from the shared
`PersistedProductSpineRun` projection rather than given a second response
shape for reads.

Unknown `run_id` returns `404` with code `run_not_found`.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/runs/{run_id}/attempts`

Authenticated, read-only listing of one run's worker/verifier attempts
(issue #739's `attempts` read surface). `attempts` is a reserved trailing
path segment; see [ADR-0019](../decisions/ADR-0019-run-subresource-suffix-reservation.md)
and the note on the plain single-run `GET` above. Serves the same
`ProductSpineRunStore.status()` application service as the plain read, then
projects `run.attempts`.

This server instance only exposes it when started with
`--product-spine-store PATH`; otherwise every request returns `503` with
code `product_spine_store_not_configured`.

Representative shape:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-run-attempts-response",
  "ok": true,
  "run_id": "run/example-1",
  "attempts": [
    {
      "attempt_id": "attempt-1",
      "order": 1,
      "connector_id": "connector.example",
      "state": "created",
      "provider_reference": null,
      "candidate_reference_digest": null,
      "result_manifest_digest": null,
      "verification_semantic_digest": null,
      "error_code": null
    }
  ]
}
```

Unknown `run_id` returns `404` with code `run_not_found`, including when the
derived `run_id` (path minus the `/attempts` suffix) does not exist.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/runs/{run_id}/evidence`

Authenticated, read-only retrieval of the Run Evidence Report retained in one
run's row (issue #739's `evidence` read surface;
[ADR-0024](../decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)).
`evidence` is a reserved trailing path segment
([ADR-0019](../decisions/ADR-0019-run-subresource-suffix-reservation.md)).
The idempotent offline Product Spine retains the full report in the run row
next to the projection whose `evidence_report_digest` it must equal; this
endpoint serves that report, so a client can reconstruct a run and its
evidence without repository files and without supplying the evidence document.

The report is returned as retained, never synthesised. Before it is served the
service verifies that the run projection is a valid Product Spine run and that
`canonical_digest(report)` equals `evidence_report_digest`. On a mismatch the
report is **not** served: the response is `500 evidence_integrity_error`
(fail closed).

This server instance only exposes it when started with
`--product-spine-store PATH`; otherwise every request returns `503` with code
`product_spine_store_not_configured`. The endpoint accepts no query parameters.

Representative shape (the report is abbreviated):

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-run-evidence-response",
  "ok": true,
  "run_id": "run/example-1",
  "evidence_report_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "evidence_report": {
    "kind": "idkmesh-run-evidence-report",
    "schema_version": "0.1"
  }
}
```

Errors are distinct so a client can tell them apart:

| Condition | Status | Code |
|---|---|---|
| no stored run has this `run_id` | `404` | `run_not_found` |
| the run exists but retains no evidence (a run created by `idkmesh run create`, or one that has not reached `evidence_ready`) | `404` | `evidence_not_available` |
| the retained report does not match the run's `evidence_report_digest`, or the projection is not a valid Product Spine run | `500` | `evidence_integrity_error` |

`GET /api/v1/runs/{run_id}/decisions` is still not built and answers the generic
`404 not_found`. It needs a retained decision store and an authenticated,
accountable human or governance principal (issue #740 and the enterprise
identity work, issue #670); a local session token is not an accountable person,
so this is a governance gate and not an implementation detail.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/work-units`

Authenticated, read-only WorkUnit listing (issue #739, the `work-units` read
surface). A **derived read model** ([ADR-0021](../decisions/ADR-0021-derived-work-unit-and-project-read-models.md)):
no WorkUnit store exists, so each item is computed on demand from the
WorkUnit reference (`id`, `version`, `digest`, `source_revision`) that every
retained Product Spine run already stores. Serves the same
`idkmesh/product_spine_run_store.py:ProductSpineRunStore.list_work_units()`
application service `idkmesh work-unit list` uses.

Items are one per distinct WorkUnit `id`, ordered by `id` ascending, with
keyset (not offset) pagination -- API Conventions v0.1 sections 10-11.

Query parameters (every other endpoint except `GET /api/v1/runs` still
rejects any query string):

- `limit` (optional integer, 1-200, default 50);
- `cursor` (optional opaque string from a previous response's
  `page.next_cursor`; a cursor issued by `GET /api/v1/runs` is rejected);
- `project_id` (optional, an exact match). When given, only that project's
  runs are considered, so every `run_count` counts only those runs.

Any other query parameter, or any of these repeated, is rejected with
`400 unexpected_query_parameters`. An out-of-range or non-integer `limit` is
`400 invalid_limit`; a cursor this service did not issue is
`400 invalid_cursor`. Without `--product-spine-store` the endpoint returns
`503 product_spine_store_not_configured`.

What an item does and does not say:

- `revisions` lists the distinct `{version, digest, source_revision}`
  references seen for the id, each with its own `run_count`, ordered
  ascending by `(version, digest, source_revision)`;
- no revision is marked latest, current, or preferred, and no health, status,
  or score is rolled up -- selecting one is a human/governance decision, not
  a read-model one;
- no WorkUnit body is returned because none is stored; `digest` is the
  binding a caller uses to fetch or verify a body elsewhere;
- a WorkUnit that has never had a run is not listed.

Representative shape:

```json
{
  "kind": "idkmesh-list",
  "schema_version": "0.1",
  "items": [
    {
      "id": "work/a",
      "run_count": 3,
      "revisions": [
        {
          "version": 1,
          "digest": "sha256:...",
          "source_revision": "0123456789abcdef0123456789abcdef01234567",
          "run_count": 2
        },
        {
          "version": 2,
          "digest": "sha256:...",
          "source_revision": "0123456789abcdef0123456789abcdef01234567",
          "run_count": 1
        }
      ]
    }
  ],
  "page": {
    "next_cursor": null,
    "limit": 50
  }
}
```

Frozen by `schemas/idkmesh-list-v0.1.schema.json` wrapping
`schemas/idkmesh-work-unit-resource-v0.1.schema.json` items.

Counts are consistent per request only: a run created between two page reads
can change them, the same caveat `GET /api/v1/runs` carries.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/work-units/{work_unit_id}`

Authenticated, read-only read of one derived WorkUnit resource, through the
same service as `idkmesh work-unit status`.

WorkUnit ids share the run-id grammar and may contain `/`, so the **entire
path remainder is one literal id** (`/api/v1/work-units/work/nested/b` reads
the id `work/nested/b`). v0.1 reserves no work-unit sub-resource suffix;
adding one needs a new ADR extending ADR-0019's path-only resolution rule.
Query parameters are rejected with `400 unexpected_query_parameters`.

Representative shape:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-work-unit-response",
  "ok": true,
  "work_unit": {
    "id": "work/a",
    "run_count": 1,
    "revisions": [
      {
        "version": 1,
        "digest": "sha256:...",
        "source_revision": "0123456789abcdef0123456789abcdef01234567",
        "run_count": 1
      }
    ]
  }
}
```

An id no stored run references returns `404` with code
`work_unit_not_found`. That states only that the retained runs do not mention
it, not that the WorkUnit does not exist elsewhere. Without
`--product-spine-store` the endpoint returns
`503 product_spine_store_not_configured`.

Frozen by `schemas/idkmesh-control-tower-work-unit-response-v0.1.schema.json`,
which references `schemas/idkmesh-work-unit-resource-v0.1.schema.json`.

Both work-unit endpoints answer `405` with `Allow: GET, HEAD` to any write
method.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/projects/{project_id}`

Authenticated, read-only project summary (issue #739, the `projects` read
surface), through the same service as `idkmesh project status`. A **derived
read model** ([ADR-0021](../decisions/ADR-0021-derived-work-unit-and-project-read-models.md)):
no project record exists, so this is counts over the stored Product Spine runs
that name the project, and nothing else.

`project_id` is not constrained beyond being non-empty and may contain `/`, so
the **entire path remainder is one literal id**
(`/api/v1/projects/org/team/project` reads `org/team/project`). Matching is
exact. v0.1 reserves no project sub-resource suffix and defines no project
list. Query parameters are rejected with `400 unexpected_query_parameters`.

Representative shape (all 14 canonical states are always present; only two are
shown):

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-control-tower-project-response",
  "ok": true,
  "project": {
    "project_id": "project.alpha",
    "run_count": 3,
    "runs_by_state": {
      "proposed": 2,
      "cancelled": 1
    },
    "work_unit_count": 2
  }
}
```

`runs_by_state` is zero-filled over every canonical run state, so the shape is
identical for every project, and its values sum to `run_count`.
`work_unit_count` is the number of distinct WorkUnit ids those runs reference;
list them with `GET /api/v1/work-units?project_id=`. The summary carries no
health, status, or score rollup and selects nothing.

A project no stored run names returns `404` with code `project_not_found`.
That states only that the retained runs do not mention it, not that the
project does not exist elsewhere. Without `--product-spine-store` the endpoint
returns `503 product_spine_store_not_configured`. Any write method answers
`405` with `Allow: GET, HEAD`.

Frozen by `schemas/idkmesh-control-tower-project-response-v0.1.schema.json`,
which references `schemas/idkmesh-project-resource-v0.1.schema.json`.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/events`

Authenticated, read-only history of the **canonical event source**
([ADR-0023](../decisions/ADR-0023-canonical-append-only-event-source.md),
issue #741), through the same service as `idkmesh events list`. Events live in
an append-only `events` table of the Product Spine store and are written in the
same SQLite transaction as the run change they record, so a committed state
change and its event either both exist or neither does.

Coverage is stated, not implied: in v0.1 only Product Spine `run create` and
`run cancel` emit events (`run.created`, `run.cancelled`). The offline
idempotent spine and the GitHub dispatch/status writers emit none yet, so this
endpoint is canonical for the events that exist and makes no claim of
completeness over every writer to the shared `runs` table. Nothing prunes the
table.

Response: the `idkmesh-list-v0.1` envelope, items ordered by `sequence`
ascending, each item an `idkmesh-event` envelope. Query parameters (anything
else, or a duplicate, is `400 unexpected_query_parameters`):

| Parameter | Meaning |
| --- | --- |
| `limit` | page size, 1-200 (default 50); otherwise `400 invalid_limit` |
| `cursor` | opaque token from the previous page's `page.next_cursor`; a token this listing did not issue, including a forged one that does not carry a bounded ASCII-decimal sequence (at most 18 digits), is `400 invalid_cursor` |
| `project_id`, `run_id`, `work_unit_id` | exact match; a blank value is `400 invalid_filter` rather than silently matching nothing |
| `event_type` | exact match, one of `run.created`, `run.cancelled`; any other value is `400 invalid_event_type` rather than silently matching nothing |

Scoped run and work-unit queries are these filters. No new run sub-resource
suffix is reserved, so [ADR-0019](../decisions/ADR-0019-run-subresource-suffix-reservation.md)
is unchanged.

Representative event:

```json
{
  "schema_version": "0.1",
  "kind": "idkmesh-event",
  "event_id": "evt-000000000002",
  "sequence": 2,
  "occurred_at": "2026-10-02T09:15:00Z",
  "event_type": "run.cancelled",
  "principal": {"type": "unauthenticated_local", "id": "local-cli"},
  "authority_class": "local_control",
  "project_id": "project.alpha",
  "work_unit_id": "work/a",
  "run_id": "run/alpha-1",
  "attempt_id": null,
  "source_revision": "0123456789abcdef0123456789abcdef01234567",
  "evidence_reference": null,
  "payload": {"previous_state": "proposed", "state": "cancelled"},
  "payload_digest": "sha256:<64 hex of the canonical payload JSON>"
}
```

Field rules:

- `sequence` is the stream's monotonic position (SQLite `AUTOINCREMENT`).
  Because SQLite serialises writers, commit order equals sequence order: a
  reader that has seen sequence N has seen every committed event up to N.
- `event_id` is `evt-` plus the 12-digit zero-padded sequence and is unique
  within the stream (the store file).
- `occurred_at` is supplied by the producer, the validated timestamp the caller
  passed for the state change. The store never reads a clock to invent one.
- `principal` is `unauthenticated_local` / `local-cli` because the CLI has no
  authentication; the field exists so an enterprise profile can supply a real
  principal without a schema change.
- `authority_class` is one of `local_control`, `worker_observation`,
  `verifier_recommendation`, `human_decision`. v0.1 emits only `local_control`;
  the others are reserved so a recommendation is never mistaken for a decision.
- `attempt_id`, `source_revision` and `evidence_reference` are nullable.
  `payload_digest` is the `sha256:` digest of the canonical payload.

An idempotent replay of `run create` emits nothing, so a duplicate emission
cannot occur at the source. The `events` table is append-only by construction:
SQLite triggers abort any `UPDATE` or `DELETE` of an event row, and `event_id`
is derived from `sequence` on read rather than stored, so it cannot drift from
it.

Without `--product-spine-store` the endpoint returns
`503 product_spine_store_not_configured`. Any write method answers `405` with
`Allow: GET, HEAD`. Frozen by `schemas/idkmesh-event-v0.1.schema.json`; the
list envelope is `schemas/idkmesh-list-v0.1.schema.json`.

Supported methods:

```text
GET, HEAD
```

### `GET /api/v1/events/stream`

Authenticated, read-only Server-Sent Events stream of the same events. It is a
`GET` only; WebSocket is deferred because nothing needs a bidirectional
channel.

Each message:

```text
id: 2
event: run.cancelled
data: {"schema_version":"0.1","kind":"idkmesh-event", ... }

```

- `id:` is the event `sequence`; `event:` is the `event_type`; `data:` is the
  compact JSON envelope shown above.
- **Resume.** `Last-Event-ID: N` resumes with every event whose sequence is
  greater than N, then follows live events. A value that is not a non-negative
  integer (ASCII digits, at most 18), or that is **beyond the newest event of
  this stream**, is `400 invalid_last_event_id`. The second case carries
  `error.details.latest_sequence`: a client cannot have seen an event this
  stream has not committed, and accepting such an id would silently skip every
  event between the stream head and it (for example an id remembered from a
  different store).
- **Browsers.** The API requires the `X-IDKMesh-UI-Token` header, which the
  browser `EventSource` API cannot send. A browser client must use `fetch` with
  a streaming reader and send `Last-Event-ID` itself; `curl -N` and any client
  that can set headers work as is.
- **No header.** The stream starts at the live tail. History is read with
  `GET /api/v1/events`, so a first connection never silently depends on
  history it was not asked for.
- **Filters.** `project_id`, `run_id`, `work_unit_id` and `event_type`, with the
  same meaning and errors as the history endpoint (a blank filter is
  `400 invalid_filter`, an unknown `event_type` is `400 invalid_event_type`, and
  both are answered before any stream byte is sent). `cursor` and `limit` are not
  accepted on the stream.
- **Delivery is at-least-once.** A client dedupes on `event_id`.
- **Framing.** The response is `text/event-stream; charset=utf-8` with no
  `Content-Length`, `Connection: close` and `X-Accel-Buffering: no`, and may be
  requested with `Accept: text/event-stream`. The first bytes are `retry: 3000`
  (a 3 s client reconnect hint). When the server ends a stream it first writes
  one comment line, `: stream-ended reason=max-duration`,
  `reason=shutdown` (drain) or `reason=store-error`, then closes; a client
  treats all three as "reconnect with `Last-Event-ID`". `reason=store-error`
  means the store failed while the stream was polling (a locked, unreadable or
  corrupt database: the store reports a SQL error as a `LocalStoreError`), and
  the stream says so instead of dropping the connection.
- **Bounds** (published in `operations.limits`, see Service limits): at most
  `max_sse_clients` concurrent streams (default 8, counted by their own
  limiter; beyond it `503 too_many_streams` with `Retry-After`); a heartbeat
  comment line (`: keepalive`) every 15 s; a maximum stream lifetime of 300 s
  after which the server ends the stream and the client reconnects with
  `Last-Event-ID`; a poll interval of 0.5 s. A stream ends promptly when the
  server drains.
- A stream does not occupy a slot of the general concurrent-request cap. The
  request timeout still guards a stalled request; once the stream is open the
  connection may stay idle for the heartbeat interval plus a small margin.
- Only `GET` is supported. `HEAD` answers `405` with `Allow: GET` (an open
  stream has no meaningful headers-only form), as does every write method.
  Only a `GET` is admitted through the stream limiter; every other method goes
  through the general request cap, so a wrong-method request is answered `405`
  even when `max_sse_clients` streams are already open, never with a misleading
  `503 too_many_streams`. Cross-origin `OPTIONS` on the stream path is still
  rejected (`405 preflight_not_supported`); its `Allow` header advertises `GET`.

Example:

```bash
curl -N \
  -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: text/event-stream" \
  -H "Last-Event-ID: 41" \
  "http://127.0.0.1:8770/api/v1/events/stream?run_id=run/alpha-1"
```

Retention: v0.1 keeps every event. If a pruner is ever added, a cursor or
`Last-Event-ID` below the retained floor must answer `410 cursor_expired`,
never a silent gap. This is a declared contract, not a built feature.

Supported methods:

```text
GET
```

## Snapshot semantics

The snapshot is a deterministic projection, not a decision object.

### Source binding

The snapshot retains:

- exact evidence-report canonical digest;
- source run digest;
- source configuration digest;
- verifier-policy digest;
- Run Evidence Report kind/version/run ID.

`source.evidence_report_digest` is the canonical digest of the exact complete
Run Evidence Report document presented to the API.

That field is intended to support the later human-decision slice, whose decision
record must bind to immutable evidence rather than a filename.

### Summary

The API independently recomputes from `attempts[]`:

- attempt count;
- supported count;
- rejected count;
- inconclusive count;
- control-error count;
- verification disagreement;
- control-failure presence.

The report's own summary is not trusted merely because it is present.
Any mismatch fails closed.

### Human attention

The current projection can surface:

- worker/verifier identity overlap;
- verifier recommendation disagreement;
- worker/result/verifier control-path failure;
- rejected attempt evidence;
- pending human integration decision.

Attention items explain why a human should inspect something. They are not
scores, rankings, or automatic selections.

### Attempt layers

Every attempt keeps separate UI/API layers:

```text
worker claim
  -> independent verifier evidence/recommendation
  -> human authority remains pending
```

The API deliberately avoids collapsing those meanings into one pass/fail field.

### Provenance chain

The snapshot exposes deterministic provenance for:

```text
WorkUnit digest
 -> worker identity
 -> ResultManifest ID/digest
 -> verifier identity
 -> VerificationResult semantic digest
 -> required check outcomes
 -> pending human/governance authority
```

The projection also retains:

- source run digest;
- source configuration digest;
- verifier policy digest;
- orchestrator version.

Identity distinction and independence remain different concepts.

When worker/verifier identities differ:

```text
identity_distinct_from_worker = true
```

but the API explicitly does **not** infer statistical, organizational,
model-family, or execution independence from different names alone.

When the same identity appears as worker and verifier, the Control Tower raises
a human-attention condition instead of calling the result independent.

### Semantic timeline

Run Evidence Report v0.1 is not a complete wall-clock event stream.

The API therefore derives deterministic sequence events only:

- observation;
- worker claim;
- independent evidence;
- verifier recommendation;
- control error;
- attention condition;
- authority boundary.

It does not fabricate timestamps.

## Published JSON Schema

The response snapshot is frozen by:

`schemas/control-tower-snapshot-v0.1.schema.json`

The schema constrains:

- API/schema/kind identifiers;
- source/provenance digests;
- WorkUnit identity;
- summary shape;
- human-attention records;
- claim/evidence attempt layers;
- provenance chains;
- semantic timeline events;
- warnings;
- pending human decision;
- zero-actuation authority;
- interpretation rules.

Focused tests validate the generated sample snapshot against this exact schema.

The status document (`GET /api/v1/status`) and the inspection success envelope
(`POST /api/v1/run-evidence/inspect`) are frozen the same way:

- `schemas/idkmesh-control-tower-status-v0.1.schema.json`
- `schemas/idkmesh-control-tower-inspection-response-v0.1.schema.json`

Focused tests validate `status_document()`'s and `success_document()`'s real
return values against these schemas, not only a hand-written example.

The run-read response (`GET /api/v1/runs/{run_id}`) is frozen by two
schemas, since the wrapper envelope and the nested run projection are
separately reusable contracts (the run projection is also what `idkmesh run
create/status/cancel --json` prints):

- `schemas/idkmesh-control-tower-run-response-v0.1.schema.json`
- `schemas/idkmesh-product-spine-run-v0.1.schema.json`

`tests/test_control_tower.py` validates both against a real run created
through the same `ProductSpineRunStore` the CLI uses, and separately asserts
the HTTP response is byte-for-byte identical to what the CLI's `run status
--json` would print for the same run.

The run-attempts response (`GET /api/v1/runs/{run_id}/attempts`) is frozen
by:

- `schemas/idkmesh-control-tower-run-attempts-response-v0.1.schema.json`

The run-evidence response (`GET /api/v1/runs/{run_id}/evidence`) is frozen by:

- `schemas/idkmesh-control-tower-run-evidence-response-v0.1.schema.json`

It references the existing `schemas/run-evidence-report-v0.1.schema.json` for
the retained report.

The derived WorkUnit resource and its single-read response
(`GET /api/v1/work-units`, `GET /api/v1/work-units/{work_unit_id}`) are frozen
by:

- `schemas/idkmesh-work-unit-resource-v0.1.schema.json`
- `schemas/idkmesh-control-tower-work-unit-response-v0.1.schema.json`

The list endpoint reuses `schemas/idkmesh-list-v0.1.schema.json`.

The derived project summary and its single-read response
(`GET /api/v1/projects/{project_id}`) are frozen by:

- `schemas/idkmesh-project-resource-v0.1.schema.json`
- `schemas/idkmesh-control-tower-project-response-v0.1.schema.json`

The canonical event envelope returned by `GET /api/v1/events` (as list items)
and carried in the `data:` field of `GET /api/v1/events/stream` is frozen by:

- `schemas/idkmesh-event-v0.1.schema.json`

## Error envelope

All API JSON errors use the shape frozen by
[`schemas/idkmesh-api-error-v0.1.schema.json`](../../schemas/idkmesh-api-error-v0.1.schema.json)
(cross-cutting for every IDKMesh product API, not specific to Control Tower —
see [API Conventions v0.1](API_CONVENTIONS_V0_1.md) section 5):

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-api-error",
  "ok": false,
  "error": {
    "code": "invalid_run_evidence",
    "message": "human-readable explanation",
    "retryable": false
  }
}
```

Optional structured `error.details` may be included when a machine-readable
recovery hint exists, such as supported API versions.

`error.retryable` is `false` for every code below except the three `503`
capacity responses `overloaded`, `too_many_streams` and `shutting_down`, which
carry `retryable: true`, a `Retry-After` header and
`error.details.retry_after_seconds`.

Stable v0.1 codes include:

- `invalid_host`;
- `invalid_session_token`;
- `not_acceptable`;
- `unsupported_media_type`;
- `length_required`;
- `invalid_content_length`;
- `unsupported_transfer_encoding`;
- `payload_too_large`;
- `invalid_utf8`;
- `invalid_run_evidence`;
- `unexpected_query_parameters`;
- `unsupported_api_version`;
- `method_not_allowed`;
- `preflight_not_supported`;
- `not_found`;
- `run_not_found` (`GET /api/v1/runs/{run_id}` and
  `GET /api/v1/runs/{run_id}/evidence`, unknown `run_id`);
- `evidence_not_available` (`GET /api/v1/runs/{run_id}/evidence`, 404, the run
  exists but retains no evidence report);
- `evidence_integrity_error` (`GET /api/v1/runs/{run_id}/evidence`, 500, the
  retained report does not match the run's `evidence_report_digest`; the report
  is never served);
- `work_unit_not_found` (`GET /api/v1/work-units/{work_unit_id}`, no
  stored run references the id);
- `project_not_found` (`GET /api/v1/projects/{project_id}`, no stored run
  names the project);
- `product_spine_store_not_configured` (`GET /api/v1/runs/{run_id}`,
  `GET /api/v1/runs/{run_id}/evidence`, `GET /api/v1/runs`, `GET /api/v1/work-units`,
  `GET /api/v1/work-units/{work_unit_id}`,
  `GET /api/v1/projects/{project_id}`, `GET /api/v1/events` and
  `GET /api/v1/events/stream`, no `--product-spine-store` given to this server
  instance);
- `invalid_limit` (`GET /api/v1/runs`, `GET /api/v1/work-units` and
  `GET /api/v1/events`, `limit` outside 1-200);
- `invalid_cursor` (`GET /api/v1/runs`, `GET /api/v1/work-units` and
  `GET /api/v1/events`, `cursor` this service did not itself issue for that
  listing);
- `invalid_state` (`GET /api/v1/runs`, `state` not one of the canonical
  Product Spine lifecycle states);
- `overloaded` (503, the concurrent-request cap is reached; carries
  `Retry-After`; `retryable: true`);
- `shutting_down` (503, the server is draining; carries `Retry-After`;
  `retryable: true`);
- `request_timeout` (408, a request body was not received within the service
  request timeout);
- `invalid_event_type` (`GET /api/v1/events` and `GET /api/v1/events/stream`,
  `event_type` not one of the known event types);
- `invalid_filter` (`GET /api/v1/events` and `GET /api/v1/events/stream`, a
  `project_id`, `run_id` or `work_unit_id` filter that is blank);
- `invalid_last_event_id` (`GET /api/v1/events/stream`, `Last-Event-ID` is not
  a non-negative integer or is beyond the newest event of this stream;
  the latter carries `error.details.latest_sequence`);
- `too_many_streams` (503, `max_sse_clients` streams are already open; carries
  `Retry-After`; `retryable: true`);
- `store_error` (the Product Spine store failed: a locked, unreadable or
  corrupt database. A SQL error is raised by the store as a `LocalStoreError`
  and reported by the run-store service as `store_error`.
  Every store-backed read endpoint (`/runs`, `/runs/{run_id}`,
  `/runs/{run_id}/attempts`, `/runs/{run_id}/evidence`, `/work-units`,
  `/projects`, `/events` and the stream's pre-stream check) answers it `500`;
  so does `evidence_integrity_error`. Opening the store (which runs its
  migration) is guarded as well: a file that cannot be opened is answered with
  a `500 store_error` body, not a dropped connection).

## Service limits

The Control Tower is a stdlib development server bound to loopback. Its limits
([ADR-0022](../decisions/ADR-0022-control-tower-bounded-service-limits.md), issue #742) are published at `operations.limits` on
`GET /api/v1/status`, validated by `schemas/idkmesh-control-tower-status-v0.1.schema.json`,
and each is proven by `tests/test_control_tower_limits.py`.

| Limit | Default | Enforcement | Proven by |
| --- | --- | --- | --- |
| Request timeout | 10 s (`--request-timeout`, 0.1-300) | socket timeout on every connection; a stalled request line or headers drop the connection, a stalled body answers `408 request_timeout` | `SlowClientTests` |
| Concurrent requests | 16 (`--max-concurrent-requests`, 1-1024) | non-blocking `RequestLimiter`; beyond the cap `503 overloaded` + `Retry-After`, no application work, connection closed | `OverloadTests`, `RequestLimiterTests` |
| Concurrent evidence inspection | same general cap | independent `POST /api/v1/run-evidence/inspect` requests execute concurrently inside the cap and remain deterministic for the same evidence | `ConcurrentInspectionTests` |
| Queue | listen backlog 16 | `request_queue_size`; there is no application wait queue | `OverloadTests` |
| Retry hint | `Retry-After: 1` | on every 503 from the cap or a drain; the error body also carries `retryable: true` | `OverloadTests`, `DrainTests` |
| Graceful drain | 5 s | `ControlTowerServer.drain()`: new requests `503 shutting_down`, then waits for in-flight requests; `serve_control_tower` calls it on shutdown | `DrainTests` |
| Request line | 65536 bytes | stdlib parser, `414` above | `ParserBoundTests` |
| Header line | 65536 bytes | stdlib parser, `431` above | `ParserBoundTests` |
| Header fields | 99 | stdlib parser, `431` at 100 (the stdlib allows 100 lines but counts the blank line ending the header block) | `ParserBoundTests` |
| Request body | 2 MiB | `413 payload_too_large`; one global cap, only `POST /api/v1/run-evidence/inspect` reads a body; an oversized declared length is rejected before body read | `RequestBodyBoundTests` |
| Connections | one request each | stdlib HTTP/1.0 default; no keep-alive | `ConnectionPolicyTests` |
| Client cancellation/disconnect | n/a | an admitted request always releases its limiter slot in `finally`; interrupted work is not retried, and a later request can immediately reuse the capacity | `CancellationTests` |
| SSE clients | 8 (`--max-sse-clients`, 1-64) | a separate non-blocking `RequestLimiter` for `GET /api/v1/events/stream`; beyond it `503 too_many_streams` + `Retry-After` | `EventStreamLimitTests` (`tests/test_control_tower_events.py`) |
| SSE heartbeat | 15 s | `: keepalive` comment on an idle stream | `EventStreamLimitTests` (`tests/test_control_tower_events.py`) |
| SSE stream lifetime | 300 s | the server ends the stream; the client resumes with `Last-Event-ID` | `EventStreamLimitTests` (`tests/test_control_tower_events.py`) |
| Per-client rate limit | not implemented | `429` is reserved; see below | status `per_client_rate_limit` |

Semantics:

- `GET /healthz` is exempt from the cap and from drain rejection. Every other
  request, including `GET /readyz`, is admitted or rejected.
- A rejection answers with the standard error envelope (`retryable: true`),
  `X-Request-ID`, and the security headers, and does no application work, so its
  cost does not depend on the request. `HEAD` rejections carry headers and no
  body.
- A `POST` rejected at the cap is answered without reading its body and the
  connection is closed, so a client sending a large body may see a connection
  reset instead of the `503`.
- If a client disconnects after admission, the handler may finish the
  read-only/inspection work but never retries it; the general or SSE limiter
  slot is released even when writing the response fails. A disconnect therefore
  abandons only that response, not server capacity.
- Every endpoint is read-only or a pure inspection, so a drain cannot leave a
  partially committed mutation.
- The cap bounds concurrent request *handling*, not accepted connections: a
  connection flood still creates short-lived threads that answer `503`.
- `429` is not emitted. It signals that one client exceeded its own rate, and a
  single local token provides no per-client identity. Server-wide saturation is
  `503`. `429` is reserved for the enterprise identity profile.
- SSE streams are counted by their own limiter and do not occupy a general
  request slot; drain ends them promptly and `drain()` waits for both limiters.
  Only a `GET` on the stream path is counted by that limiter: `HEAD`, `POST`
  and the other write methods use the general cap and are answered `405
  Allow: GET`.
- Only the Control Tower server is hardened. `gate-audit-ui` and the steward UIs
  keep their previous behavior.
- A public or network deployment must use a reviewed production transport
  adapter; the stdlib server must not be exposed to the Internet.

Representative `operations.limits`:

```json
{
  "request_timeout_seconds": 10.0,
  "max_concurrent_requests": 16,
  "retry_after_seconds": 1,
  "drain_timeout_seconds": 5.0,
  "max_request_line_bytes": 65536,
  "max_header_line_bytes": 65536,
  "max_header_count": 99,
  "max_request_body_bytes": 2097152,
  "max_sse_clients": 8,
  "sse_heartbeat_seconds": 15,
  "sse_max_stream_seconds": 300,
  "overload_status": 503,
  "connection_policy": "close_after_response",
  "per_client_rate_limit": "not_implemented"
}
```

## HTTP method behavior

Known endpoints return HTTP 405 for unsupported methods and publish the allowed
method set in `Allow`.

Valid `/api/v1/*` routes are token-authenticated before normal route behavior,
so unauthenticated local callers cannot use method differences as a substitute
for API access.

Cross-origin `OPTIONS` preflight is deliberately rejected because v0.1 is a
same-origin local API.

`PUT`, `PATCH`, `DELETE`, `TRACE`, and `CONNECT` have no write or
tunneling meaning in v0.1 and are rejected.

## CLI and headless use

Browser mode:

```bash
idkmesh control-tower
```

Open a specific report:

```bash
idkmesh control-tower path/to/evidence-report.json
```

Headless server with a caller-known token:

```bash
export IDKMESH_CONTROL_TOWER_TOKEN='replace-with-at-least-32-random-characters'
idkmesh control-tower --no-browser --port 8770
```

Headless server that also serves the run, WorkUnit, and project read endpoints
(`GET /api/v1/runs`, `GET /api/v1/runs/{run_id}`,
`GET /api/v1/runs/{run_id}/attempts`, `GET /api/v1/work-units`,
`GET /api/v1/work-units/{work_unit_id}`,
`GET /api/v1/projects/{project_id}`, `GET /api/v1/events`,
`GET /api/v1/events/stream`) over an
existing Product Spine store (the same file `idkmesh run create/status/cancel`
already writes to):

```bash
idkmesh control-tower --no-browser --port 8770 \
  --product-spine-store path/to/product-spine.sqlite3
```

Tune the service limits (both are validated before the port is bound):

```bash
idkmesh control-tower --no-browser --port 8770 \
  --request-timeout 5 --max-concurrent-requests 8 --max-sse-clients 4
```

Read the same store's derived WorkUnits and project summaries from the CLI:

```bash
idkmesh work-unit list --store path/to/product-spine.sqlite3
idkmesh work-unit status work/a --store path/to/product-spine.sqlite3
idkmesh project status project.alpha --store path/to/product-spine.sqlite3
```

Read the canonical event history from the CLI (the same service as
`GET /api/v1/events`):

```bash
idkmesh events list --store path/to/product-spine.sqlite3
idkmesh events list --store path/to/product-spine.sqlite3 \
  --run-id run/alpha-1 --event-type run.cancelled --json
```

Example status request:

```bash
curl \
  -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/status
```

The environment token is an ephemeral local API session credential. It is not a
provider secret or repository credential and should not be committed.

### Python client

`idkmesh.api_client.ControlTowerClient` is the supported Python surface for the
read/inspection endpoints above. It covers `status`,
`run-evidence/inspect`, `runs`, `runs/{run_id}`, `runs/{run_id}/attempts`,
`runs/{run_id}/evidence`, `work-units`, `work-units/{work_unit_id}`,
`projects/{project_id}`, and `events`; human-decision recording is deliberately
absent until the authenticated mutation adapter (issue #740) exists. The
`/healthz` and `/readyz` probes, `openapi.json` discovery, and the
`events/stream` Server-Sent Events stream are not wrapped by the client and
remain plain HTTP.

```python
import os

from idkmesh.api_client import ControlTowerClient

client = ControlTowerClient(
    "http://127.0.0.1:8770",
    os.environ["IDKMESH_CONTROL_TOWER_TOKEN"],
    timeout=5.0,  # mandatory by construction
)
run = client.get_run("run/alpha-1")
print(run.request_id, run.value["run"]["state"])

page = client.list_runs(limit=50, project_id="project.alpha")
while page.value.next_cursor is not None:
    page = client.list_runs(
        limit=50,
        project_id="project.alpha",
        cursor=page.value.next_cursor,  # cursors stay opaque
    )
```

Client guarantees, each fail-closed:

- exactly one HTTP request per method call: no retries, redirects, or hidden
  idempotent replay;
- loopback-only `http` base URLs, so the local session token cannot leak to a
  remote host;
- the response content digest is recomputed and compared before the document
  is returned, and embedded evidence/snapshot digests are verified
  independently of the outer envelope (`IntegrityError` on mismatch);
- every resource read is bound to the requested identity: a response naming a
  different `run_id`/`work_unit`/`project` raises `ProtocolError`;
- request IDs and response metadata are exposed on every
  `ApiResult` for correlation and bug reports;
- failures use the stable taxonomy `ClientConfigurationError`, `TransportError`,
  `ProtocolError`/`IntegrityError`, and `ApiResponseError` (which carries the
  server's stable error `code`, `retryable` flag, and HTTP status);
- list methods validate `limit`, `cursor`, and filters before any transport
  I/O, and unknown query parameters fail explicitly on the server
  (API Conventions v0.1 section 11).

## Relationship to Gate Audit

`gate-audit-ui` and `control-tower` are complementary.

Gate Audit asks:

> How much independent evidence does this verifier panel actually provide?

Control Tower asks:

> What happened in this multi-attempt run, what evidence exists, where is there
> disagreement/failure, how is it bound by provenance, and what still needs a
> human decision?

Both local UIs share one browser-security helper while retaining separate domain
contracts.

## Interpretation rules

Every client must preserve:

```text
worker success != verified correctness
verifier recommendation != human integration decision
multiple recommendations != majority truth
replay equality != correctness
identity distinction != independence
```

## Next compatible extensions

Issue #739's only unshipped read surface is `GET /api/v1/runs/{run_id}/decisions`.
`/evidence` is shipped
([ADR-0024](../decisions/ADR-0024-retained-evidence-read-and-mixed-store-run-reads.md)):
the idempotent offline spine already retains the digest-verified report in the
run row. `/decisions` stays blocked on issue #740: no decision content is
retained anywhere, and recording one needs an authenticated, accountable human
or governance principal, which is a governance gate.

Issue #741's canonical event source, history query and resumable SSE stream
are shipped
([ADR-0023](../decisions/ADR-0023-canonical-append-only-event-source.md)). Not
yet built: events for the other writers of the shared `runs` table (offline
spine, GitHub dispatch and status), further event types (attempts, evidence,
verification, human decisions), an enterprise principal on `principal`, a
retention pruner with its `410 cursor_expired` contract, and a production
transport adapter that would replace the poll-based SSE loop.

Issue #572 defines later read-first slices:

1. immutable human-decision recording;
2. a Control Tower timeline built from the canonical event source (the event
   source itself exists; the UI still derives its timeline from the posted
   report);
3. verification-debt/capacity;
4. participant/resource/authority matrix;
5. IDKGraph repository health;
6. goal/uncertainty views;
7. collaboration/scientific-evidence views.

Write/actuation endpoints are explicitly outside v0.1.
