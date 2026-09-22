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

Every API request except `GET /healthz` and the HTML document itself requires:

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

The value must contain at least 32 non-whitespace characters. It is never
printed by the server. Environment injection exists so a local client can know
the token without weakening the browser default.

The server also:

- accepts only loopback `Host` values;
- compares session tokens with constant-time comparison;
- rejects cross-origin preflight;
- rejects transfer-encoded/chunked request bodies;
- caps request bodies at 2 MiB;
- emits no-store, frame, referrer, content-type, cross-origin, permissions and
  CSP protection headers.

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
- status endpoint;
- OpenAPI endpoint;
- run-evidence inspection endpoint;
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

## Error envelope

All API JSON errors use:

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
- `not_found`.

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

Issue #572 defines later read-first slices:

1. immutable human-decision recording;
2. real event-source timeline;
3. verification-debt/capacity;
4. participant/resource/authority matrix;
5. IDKGraph repository health;
6. goal/uncertainty views;
7. collaboration/scientific-evidence views.

Write/actuation endpoints are explicitly outside v0.1.
