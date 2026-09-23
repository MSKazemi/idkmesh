# Conversation record — Control Tower API hardening

**Date:** 2026-09-22  
**Pull request:** #658  
**Related:** issue #572

## Project-owner requirement

> work on the APIs and make it solide

## Repository state checked

PR #658 already contained the first read-only Human Control Tower, Run Evidence
Report inspection, provenance projection, semantic timeline, and local v1 API.

The API boundary was intentionally non-actuating, but several product-level
contracts were still implicit rather than frozen.

## Hardening completed in this turn

### Stable response contracts

The local API now has explicit object identifiers and schema versions for:

- Control Tower status;
- inspection success envelope;
- inspection snapshot;
- API error envelope.

The inspection response now carries a deterministic `snapshot_digest`, and the
snapshot carries the canonical digest of the exact Run Evidence Report it was
derived from.

That report digest uses the same sorted-key/minified UTF-8 SHA-256 canonical
JSON rule as the repository's provenance-integrity code.

### Machine-readable discovery

Added:

`GET /api/v1/openapi.json`

The endpoint returns an OpenAPI 3.1 description generated from the installed
Python API constants.

Published a frozen response schema:

`schemas/control-tower-snapshot-v0.1.schema.json`

The schema covers source binding, WorkUnit identity, summary, attention,
claim/evidence attempt layers, provenance chains, timeline, authority, pending
human decision, and interpretation rules.

Focused tests validate the generated snapshot against that schema.

### HTTP behavior

The server now provides explicit behavior for:

- `GET` / `HEAD`;
- correct HTTP 405 responses with `Allow`;
- `PUT`, `PATCH`, `DELETE`, `TRACE`, and `CONNECT` rejection;
- unsupported API versions;
- unexpected v1 query parameters;
- unsupported request media types;
- unsupported response media types;
- unsupported transfer encodings;
- oversized bodies;
- invalid content lengths.

No API route relies on the base Python HTTP server's generic 501 behavior for
these known cases.

### Content negotiation and deterministic response identity

Supported media types:

- `application/json`;
- `application/vnd.idkmesh.control-tower.v1+json`.

Responses include:

- `Vary: Accept`;
- `X-IDKMesh-API-Version: v1`;
- `X-IDKMesh-Read-Only: true`;
- `X-IDKMesh-Content-Digest: sha256:...`;
- deterministic `ETag`.

The same valid evidence input produces the same response bytes and digests.

### Local API authentication

Browser mode still uses a random per-process session token.

Headless clients may intentionally provide:

`IDKMESH_CONTROL_TOWER_TOKEN`

The configured value must contain 32–4096 characters using only ASCII letters,
digits, `-`, `.`, `_`, and `~`.

This restriction prevents unsafe HTML/script or HTTP-header characters from
entering the locally generated page.

Token comparison uses constant-time comparison.

Valid v1 API routes authenticate before normal route behavior.

Invalid token configuration is reported through the normal CLI user-error path
instead of producing a traceback.

### Provenance reconciliation

Concurrent work on the same PR added the deeper provenance-chain slice while
this API hardening was in progress.

The API hardening was reconciled against that current branch state rather than
overwriting it.

The formal snapshot JSON Schema now includes the provenance projection and
retains the key distinction:

```text
identity distinction != statistical/organizational independence
```

Worker/verifier identity overlap is surfaced as a human-attention condition;
different IDs are not treated as proof of independent verification.

## Authority boundary

No new actuation was added.

The v1 Control Tower API still cannot:

- execute workers;
- rerun verification;
- record a human decision;
- select a candidate;
- write canonical state;
- push Git;
- merge.

## Documentation / product surface

Updated:

- Control Tower Local API v0.1 specification;
- README headless-client example;
- changelog;
- package description.

The API specification now documents versioning, authentication, media types,
headers, deterministic digests, OpenAPI discovery, snapshot schema, error codes,
method behavior, source/provenance binding, and authority constraints.

## Verification

Focused tests were expanded for:

- snapshot JSON Schema conformance;
- exact evidence-report digest binding;
- deterministic success envelope;
- OpenAPI discovery;
- status/schema discovery;
- response version/read-only/digest headers;
- vendor media-type negotiation;
- `HEAD` behavior;
- 405 + `Allow`;
- unsupported versions and query parameters;
- repeated byte-identical inspection;
- configured headless token behavior;
- unsafe/short token rejection;
- clean CLI failure for invalid token configuration.

The exact PR head is submitted to the repository's normal Python 3.11/3.13 PR
gate, schema checks, CodeQL, and repository observability workflows before the
PR is considered ready.

## Community impact

A documented, deterministic, machine-readable local API makes the Control Tower
usable by small local tools and future GUI modules without requiring each
contributor to reverse-engineer internal Python functions.

The API remains deliberately read-only so easier integration does not quietly
expand agent authority.

## AI/tool provenance

Implementation and repository updates were produced with ChatGPT using connected
GitHub tools. No claim of independent human review is made.
