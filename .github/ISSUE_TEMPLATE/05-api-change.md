---
name: API change
about: Propose a versioned IDKMesh API endpoint, contract, client, runtime, or compatibility change
title: "[API] "
---

## Goal

State the user/integrator outcome in one sentence.

## Program / owner

- Parent program: #713
- Canonical domain owner:
- Related API child issue:
- Existing subsystem owner(s):

Do not create a competing canonical WorkUnit, run, evidence, decision, identity,
or connector object.

## API surface

- Method/path:
- Deployment profile: local / network / both
- API URL version:
- Request object/schema:
- Response object/schema:
- OpenAPI impact:

## Authority ceiling

What may this API do?

What must it never do?

Explicitly state whether it can:

- dispatch work;
- verify;
- record a human decision;
- write canonical state;
- push Git;
- merge.

## Identity / authorization

- Authenticated principal required?
- Required scope/action:
- Project/tenant boundary:
- Separation-of-duties requirement:
- Local-session behavior (if applicable):

## Resource identity / provenance

- Stable resource ID:
- Source revision/digest:
- Evidence/provenance binding:
- Replay/reconstruction behavior:

## Mutation semantics

Delete this section for pure reads.

- Idempotency-Key required?
- Canonical request digest:
- Retry behavior:
- Conflict behavior:
- Concurrency/expected-version strategy:
- Immutable audit/event emitted:
- External side effect boundary:

## List/query semantics

Delete if not list-like.

- Deterministic order:
- Page-size bound:
- Cursor:
- Supported filters:
- Unknown-filter behavior:

## Limits / reliability

- Body-size limit:
- Header/request timeout considerations:
- Concurrency/rate implications:
- 429/503 behavior:
- Graceful shutdown implications:
- Streaming/client limits:

## Errors

List new stable machine error codes and HTTP status mapping.

## Security / privacy

- Secrets involved?
- Sensitive evidence involved?
- Browser CORS/CSRF/origin implications?
- Logging/metrics redaction requirements?
- Network exposure implications?

If this may be an undisclosed vulnerability, use `SECURITY.md` instead of a
public issue.

## Compatibility

Classify the change:

- [ ] documentation only
- [ ] additive compatible
- [ ] behavior clarification
- [ ] deprecation
- [ ] breaking

If breaking, state required version/migration plan.

## Acceptance evidence

Specify before implementation:

- [ ] request/response schemas;
- [ ] positive tests;
- [ ] negative/authority tests;
- [ ] OpenAPI update;
- [ ] runtime response/schema conformance;
- [ ] compatibility check;
- [ ] docs/example;
- [ ] relevant load/security/reliability evidence.

## Community impact

Explain whether this makes API use, contribution, review, or maintenance easier
or harder.
