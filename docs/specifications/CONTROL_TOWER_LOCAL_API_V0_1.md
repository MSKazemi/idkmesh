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

It reveals no evidence/project state.

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
while a required runtime dependency is not ready.

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
- `run_not_found` (`GET /api/v1/runs/{run_id}`, unknown `run_id`);
- `work_unit_not_found` (`GET /api/v1/work-units/{work_unit_id}`, no
  stored run references the id);
- `project_not_found` (`GET /api/v1/projects/{project_id}`, no stored run
  names the project);
- `product_spine_store_not_configured` (`GET /api/v1/runs/{run_id}`,
  `GET /api/v1/runs`, `GET /api/v1/work-units`,
  `GET /api/v1/work-units/{work_unit_id}`, and
  `GET /api/v1/projects/{project_id}`, no `--product-spine-store` given
  to this server instance);
- `invalid_limit` (`GET /api/v1/runs` and `GET /api/v1/work-units`, `limit`
  outside 1-200);
- `invalid_cursor` (`GET /api/v1/runs` and `GET /api/v1/work-units`,
  `cursor` this service did not itself issue for that listing);
- `invalid_state` (`GET /api/v1/runs`, `state` not one of the canonical
  Product Spine lifecycle states).

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
`GET /api/v1/projects/{project_id}`) over an
existing Product Spine store (the same file `idkmesh run create/status/cancel`
already writes to):

```bash
idkmesh control-tower --no-browser --port 8770 \
  --product-spine-store path/to/product-spine.sqlite3
```

Read the same store's derived WorkUnits and project summaries from the CLI:

```bash
idkmesh work-unit list --store path/to/product-spine.sqlite3
idkmesh work-unit status work/a --store path/to/product-spine.sqlite3
idkmesh project status project.alpha --store path/to/product-spine.sqlite3
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

Issue #739's only unshipped read surfaces are `GET /api/v1/runs/{run_id}/evidence`
and `/decisions`, blocked on the immutable content store of issue #740.

Issue #572 defines later read-first slices:

1. immutable human-decision recording;
2. real event-source timeline;
3. verification-debt/capacity;
4. participant/resource/authority matrix;
5. IDKGraph repository health;
6. goal/uncertainty views;
7. collaboration/scientific-evidence views.

Write/actuation endpoints are explicitly outside v0.1.
