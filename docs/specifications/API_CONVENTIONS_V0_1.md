# IDKMesh API Conventions v0.1

**Status:** proposed baseline; issue #736 owns review/freeze  
**Date:** 2026-09-23  
**Program:** #713

This specification defines cross-cutting conventions for IDKMesh HTTP product
APIs. Domain specifications remain authoritative for domain semantics.

## 1. Namespace and versions

Product endpoints use:

`/api/v1/...`

Operational probes use:

- `/healthz`
- `/readyz`

URL compatibility version and object schema version are separate.

Every IDKMesh API object should expose an explicit version field appropriate to
its contract, for example:

```json
{
  "kind": "idkmesh-control-tower-snapshot",
  "schema_version": "0.1"
}
```

A URL v1 breaking semantic change requires explicit migration/version review.

## 2. JSON

Default media type:

`application/json`

A domain may additionally define a versioned vendor media type.

Requirements:

- UTF-8;
- reject duplicate object keys at strict trust boundaries;
- reject non-finite values;
- deterministic canonical JSON when a digest is defined;
- document body-size limits;
- do not accept unknown top-level fields for authority/security-sensitive
  objects unless an extension mechanism is explicitly defined.

## 3. Resource identity

Resource IDs must be:

- stable across presentation clients;
- unique within their declared scope;
- bounded in length;
- safe for logs/URLs or encoded before path use.

Content identity uses canonical digests where required:

`sha256:<64-lowercase-hex>`

A filename, branch name, UI row number, or mutable provider URL is not a
substitute for immutable content identity.

## 4. Response envelope

Domain resources may be returned directly when a schema explicitly defines
that shape.

Operation/result envelopes should carry:

- API/schema version;
- object kind;
- result/resource;
- immutable digest where meaningful.

Do not add request-specific timestamps/random values to otherwise deterministic
evidence projections.

## 5. Standard error envelope

All JSON API errors should follow one stable structure:

```json
{
  "api_version": "v1",
  "schema_version": "0.1",
  "kind": "idkmesh-api-error",
  "ok": false,
  "error": {
    "code": "stable_machine_code",
    "message": "human-readable explanation",
    "retryable": false,
    "details": {}
  }
}
```

Rules:

- `code` is compatibility-sensitive;
- `message` is explanatory, not a parsing contract;
- `details` contains bounded structured recovery information;
- no secrets, tokens, prompts, or private raw payloads in errors;
- a provider/worker domain failure is not automatically an HTTP 5xx.

## 6. HTTP status mapping

Baseline meanings:

- 200 — successful read/operation result;
- 201 — immutable resource created;
- 202 — authorized asynchronous operation accepted;
- 204 — successful response intentionally has no body;
- 400 — malformed/contract-invalid request;
- 401 — no valid authenticated principal where authentication is required;
- 403 — authenticated but not permitted, or local session boundary rejected;
- 404 — resource not available to caller under the endpoint's disclosure policy;
- 405 — known resource, wrong method; include `Allow`;
- 406 — response media type unacceptable;
- 409 — idempotency/concurrency/state conflict;
- 411 — content length required when transport requires it;
- 413 — payload too large;
- 415 — request media type unsupported;
- 422 — syntactically valid request whose domain transition is invalid, only
  where the owning domain specification adopts this distinction;
- 429 — bounded rate/concurrency limit; include `Retry-After` when meaningful;
- 500 — internal service failure;
- 503 — dependency/capacity unavailable; include `Retry-After` when meaningful.

Issue #736 freezes any final mapping changes.

## 7. Request correlation

Accept safe caller `X-Request-ID`; replace invalid/unbounded values.

Every response exposes the effective request ID.

Request IDs:

- are operational correlation only;
- are not identity;
- are not authorization;
- do not enter deterministic evidence-body digests.

## 8. Service metadata

Services should expose stable bounded headers such as:

- `X-IDKMesh-Service`;
- `X-IDKMesh-Service-Version`;
- `X-IDKMesh-API-Version`;
- `X-IDKMesh-Read-Only` where applicable.

Evidence projections may expose:

- `X-IDKMesh-Content-Digest`;
- `ETag`.

No-store policy may coexist with ETag when ETag is an integrity/equality signal
rather than cache permission.

## 9. Authentication and authorization

### Local profile

A loopback session token may protect a local browser/API service.

It is not a human/service principal.

### Network profile

A request that can access project state or mutate durable state must carry a
trusted authenticated principal and pass policy authorization.

Endpoint specifications declare required scopes/actions.

Authority must never be inferred from:

- model output;
- issue text;
- user-supplied role strings;
- UI controls;
- GitHub labels alone.

## 10. List endpoints

List endpoints require:

- deterministic default order;
- bounded page size;
- opaque cursor;
- stable next-cursor semantics;
- documented filters;
- no unbounded full-table response.

Proposed response shape:

```json
{
  "kind": "idkmesh-list",
  "schema_version": "0.1",
  "items": [],
  "page": {
    "next_cursor": null,
    "limit": 50
  }
}
```

Offset pagination should be avoided for mutable event/run streams unless a
domain demonstrates safe semantics.

## 11. Filtering

Filters must be explicitly enumerated and bounded.

Do not expose arbitrary expression languages in v1.

Unknown filters fail explicitly rather than being silently ignored.

## 12. Mutations and idempotency

Every externally retried mutation defines whether it is idempotent.

For creation/dispatch/decision-recording APIs, prefer requiring:

`Idempotency-Key`

Semantics:

```text
same key + same canonical request digest
 -> return/refer to the original logical result

same key + different canonical request digest
 -> 409 conflict
```

Persist the idempotency record before invoking an external side effect when
required by the operation.

## 13. Concurrency

Mutable resources define an optimistic-concurrency strategy before release.

Preferred forms:

- immutable append-only record;
- expected revision/version;
- ETag + `If-Match`.

A retry must not silently overwrite a newer human or policy decision.

## 14. Human decisions

A Human Decision Record:

- binds to exact evidence digest;
- identifies the decider/principal;
- requires rationale;
- is immutable;
- may be idempotently created;
- carries no push/merge authority.

Integration execution is a separate operation and policy boundary.

## 15. Events

Canonical events are immutable and append-only.

Events should include:

- event ID;
- stream sequence;
- actual occurrence timestamp;
- principal;
- scoped object IDs;
- event type;
- payload/evidence digest;
- source revision;
- authority class.

Historical query uses cursor pagination.

Live read delivery begins with resumable SSE.

## 16. Health and readiness

`/healthz` answers whether the process is alive.

`/readyz` answers whether the service is ready for its declared profile.

Neither endpoint exposes project/evidence/secrets.

Readiness may report bounded dependency state in the network profile.

## 17. Limits and overload

Every deployment profile documents:

- maximum body size;
- maximum header size;
- request timeout;
- concurrency bound;
- queue bound;
- stream-client bound;
- rate-limit strategy;
- overload response.

Use 429/503 explicitly; do not allow uncontrolled memory growth.

## 18. Logging, metrics, tracing

Logs/telemetry must not contain:

- raw auth/session tokens;
- raw secrets/secret references where sensitive;
- request/response bodies by default;
- prompts;
- private evidence payloads;
- query-string secrets.

Network profile should support W3C `traceparent`.

Telemetry identifiers are not authority/evidence.

## 19. OpenAPI and JSON Schema

OpenAPI is a discovery/transport contract, not the sole source of domain truth.

Requirements:

- public objects have canonical JSON Schemas;
- OpenAPI references those schemas;
- examples validate in CI;
- representative runtime responses validate in CI;
- unresolved refs fail CI;
- backwards-compatibility diffing gates stable versions.

## 20. Deprecation

Stable API deprecation must be explicit.

Final policy is owned by #736, but should include:

- deprecation announcement;
- affected version/path/object;
- replacement;
- earliest removal date/version;
- migration guide;
- optional standard deprecation/sunset headers where applicable.

Nothing is removed merely because a newer UI stopped using it.

## 21. Security-sensitive browser mutations

If/when network browser mutations exist, define:

- credential delivery;
- CORS;
- CSRF protection;
- Origin/Referer policy;
- SameSite/cookie behavior if cookies are used;
- anti-replay/idempotency;
- user confirmation for high-risk operations where policy requires it.

Local token behavior must not be copied blindly into network mode.

## 22. Compatibility classes

Every API change should be labeled internally as one of:

- documentation-only;
- additive compatible;
- behavior clarification;
- deprecated;
- breaking.

Breaking changes require the process defined by #736 and release/migration
evidence.

## 23. Authority statement

These conventions standardize transport behavior.

They do not grant:

- dispatch authority;
- verification authority;
- acceptance authority;
- repository-write authority;
- merge authority.

Authority remains owned by domain policy and explicit actor/governance
decisions.
