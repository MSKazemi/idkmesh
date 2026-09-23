# IDKMesh API v1 Professionalization Plan

**Date:** 2026-09-23  
**Status:** execution blueprint  
**Program issue:** #713  
**Purpose:** define the complete plan, ownership, dependencies, release evidence, and non-negotiable boundaries required before expanding IDKMesh APIs.

## 1. Outcome

IDKMesh should have one coherent API platform that can support:

- the local Human Control Tower;
- CLI clients;
- connector/control-plane automation;
- the Product Spine;
- future multi-user deployments;
- GitHub-native and external adapters;
- official Python and web clients.

“API complete” does not mean “some endpoints exist.” It means the declared
v1 surface is versioned, schema-bound, authenticated/authorized for its
deployment profile, deterministic where promised, idempotent where mutating,
observable, bounded under load, documented, client-consumable, and release
qualified.

## 2. Non-negotiable project invariants

```text
routing != dispatch authority
dispatch != acceptance
worker success != verification
verification recommendation != human decision
human decision != integration execution
identity distinction != verification independence
model capability != repository authority
API convenience != authority expansion
```

The API may expose, record, and transport authority decisions. A transport
adapter must never invent authority.

## 3. Current assets and owners

Do not duplicate these existing owners:

| Area | Existing owner |
| --- | --- |
| API production-readiness umbrella | #713 |
| Control Tower UI/read API | #572 + PR #658 |
| HTTP runtime baseline | #677 |
| Connector CLI/HTTP control surface | #580 |
| Connector/control-plane program | #570 |
| End-to-end Product Spine | #682 |
| Local persistence/idempotency | #616 |
| GitHub-native durable run/evidence ledger | #597 |
| GitHub multi-user role/authority profile | #598 |
| GitHub governance/secret-access baseline | #607 |
| Enterprise identity/RBAC/ABAC | #670 |
| Enterprise readiness/security | #667 |
| Human Decision Record schema | `schemas/human-decision-record-v0.1.schema.json` |
| Connector Control API design | `docs/specifications/CONNECTOR_CONTROL_API_V0_1.md` |

New API issues created by this plan own integration gaps, not duplicate
implementations.

## 4. API architecture target

The target API has five layers:

```text
clients
  |
  +-- CLI
  +-- Control Tower web client
  +-- Python SDK
  +-- TypeScript SDK
  +-- GitHub / connector adapters
  |
transport adapters
  |
  +-- local loopback HTTP
  +-- future production HTTP adapter
  |
application services
  |
  +-- Project / WorkUnit query
  +-- routing / connector control
  +-- run lifecycle
  +-- evidence inspection
  +-- human decision recording
  +-- event query/stream
  |
domain contracts
  |
  +-- WorkUnit
  +-- RoutingDecision
  +-- CandidateReference
  +-- ResultManifest
  +-- VerificationResult
  +-- Run Evidence Report
  +-- Human Decision Record
  |
durable evidence / metadata / event stores
```

Transport, persistence, and UI are replaceable adapters around the same domain
and application-service semantics.

## 5. Deployment profiles

### Profile L — local developer/control-tower

- bind to loopback only;
- dependency-light base install;
- local session token;
- read-only by default;
- no assumption of multiple users;
- no claim that the local token is enterprise authentication.

### Profile N — network/multi-user

Must not expose the development stdlib HTTP server directly.

Expected shape:

```text
client
 -> TLS/proxy boundary
 -> trusted identity adapter
 -> authorization policy
 -> production transport
 -> application services
 -> durable metadata/evidence/event stores
```

Profile N requires #670 identity/policy integration plus #743 API security
profile before mutating endpoints are enabled.

## 6. Canonical HTTP namespace

Planning decision:

```text
/api/v1/...
```

is the product HTTP namespace.

Object schema versions remain independent, for example:

```text
HTTP compatibility line: /api/v1
object schema:            0.1 or idkmesh.io/v1alpha1
```

The older Connector Control API document currently uses `/v1`; #736/#738 own
reconciling that design before connector HTTP implementation becomes canonical.

## 7. Resource model

The intended v1 resource families are:

### Discovery / runtime

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/status`
- `GET /api/v1/openapi.json`

### Projects and work

- `GET /api/v1/projects/{project_id}`
- `GET /api/v1/work-units`
- `GET /api/v1/work-units/{id}`
- bounded WorkUnit preview through the connector/Product Spine service

### Runs and evidence

- `GET /api/v1/runs`
- `GET /api/v1/runs/{id}`
- `GET /api/v1/runs/{id}/attempts`
- `GET /api/v1/runs/{id}/evidence`
- read-only evidence inspection
- verifier-panel Gate Audit remains a specialized diagnostic, not the run API

### Human decisions

- `GET /api/v1/runs/{id}/decisions`
- `POST /api/v1/human-decisions`

Recording a decision does not execute integration.

### Events

- `GET /api/v1/events`
- scoped historical queries
- resumable SSE stream

### Connector/control plane

Canonical ownership remains #580/#570:

- connections;
- probes;
- route resolution;
- WorkUnit preview;
- run creation/cancel;
- connector dispatch.

These endpoints must share the same conventions and application/domain services.

## 8. Cross-cutting contract checklist

Every public endpoint must define:

- method and path;
- deployment profiles where available;
- required principal/scope;
- request schema;
- response schema;
- error codes;
- canonical resource identity;
- source revision/digest semantics;
- pagination/order semantics where list-like;
- idempotency semantics where mutating;
- concurrency/conflict semantics;
- authority ceiling;
- size/rate/time limits;
- audit event emitted;
- observability behavior;
- backward-compatibility classification.

## 9. Issue program

### Foundation / P0

- #735 — converge and qualify current local API v0.1
- #736 — API conventions, versioning, errors, deprecation
- #737 — complete public schema catalog + compatibility CI
- #738 — unify Control Tower and Connector Control API architecture
- existing #677 — HTTP runtime baseline

### Product read/decision / P0

- #739 — resource-oriented read API
- #740 — immutable Human Decision API
- existing #616 — persistence/idempotency
- existing #670 — identity/policy
- existing #682 — Product Spine integration

### Eventing / operations / P1

- #741 — canonical events + resumable SSE
- #742 — reliability/limits/backpressure/shutdown
- #743 — network/multi-user API security profile
- #744 — observability/metrics/tracing/SLO
- #750 — durable storage profiles, migrations, retention, recovery

### Qualification / developer experience

- #745 — contract/fuzz/load/security qualification
- #746 — Python/TypeScript clients + professional API docs
- #747 — v1 beta release qualification

## 10. Requirements traceability

The cross-program ownership/proof matrix is:

`docs/planning/API_V1_REQUIREMENTS_TRACEABILITY_MATRIX_2026-09-23.md`

It maps each professional API requirement to existing subsystem owners, API
integration issues, and release evidence. If a new requirement has no owner and
no proof, implementation pauses until the plan is updated.

## 11. Dependency sequence

```text
#735 current API convergence
    |
    v
#736 conventions -----------+
    |                       |
    +--> #737 schemas ------+
    |                       |
    +--> #738 architecture -+
                            |
              +-------------+--------------+
              |             |              |
              v             v              v
            #739          #741           #742
          read model      events       reliability
              |             |              |
              +------+------+<--------------+
                     |
                     v
                  #745 qualification
                     |
                     v
                  #746 SDK/docs
                     |
                     v
                  #747 v1 beta
```

Mutation path:

```text
#736 + #737 + #738
       +
#616 persistence/idempotency
       +
#670 identity/policy
       |
       v
#740 Human Decision API
       |
       v
#745 qualification
```

Network path:

```text
#677 runtime + #670 identity/policy + #738 architecture
                         |
                         v
                       #743
                         |
                  +------+------+
                  v             v
                #742          #744
              reliability   observability

#616 local metadata + #597 GitHub ledger + #738 architecture
                         |
                         v
                       #750
                    storage profiles
```

## 12. Implementation rules

Before implementing a new endpoint:

1. its owning issue exists;
2. domain owner is named;
3. request/response schemas exist or are part of the same bounded change;
4. authority ceiling is explicit;
5. authentication/authorization requirement is explicit;
6. idempotency/conflict semantics are defined if mutating;
7. audit event is defined if state changes;
8. test evidence is specified;
9. docs/OpenAPI impact is specified;
10. no duplicate canonical object is introduced.

## 13. Security planning baseline

The API threat model is documented in:

`docs/security/API_THREAT_MODEL_V0_1.md`

It separates local, GitHub-first, and network/multi-user trust boundaries and
maps authority confusion, auth bypass, replay, CSRF/CORS, proxy ambiguity,
webhook forgery, SSRF, storage tamper, and overload threats to their owning
issues.

## 14. Release quality gates

### Contract gate

- OpenAPI valid;
- all schema references resolve;
- all examples validate;
- runtime representative responses validate;
- compatibility diff has no undeclared breaking changes.

### Functional gate

- exact-head tests pass on supported Python versions;
- deterministic endpoints remain deterministic;
- mutations satisfy idempotency/concurrency rules;
- replay/provenance checks pass.

### Security gate

- authority negative tests;
- auth/scope negative tests for network profile;
- token/header/parser fuzz;
- CORS/CSRF checks for browser mutations;
- secret scanning;
- CodeQL/security workflow green.

### Reliability gate

- concurrency;
- slow client;
- body/header boundaries;
- overload behavior;
- restart/drain;
- load/soak/memory evidence appropriate to release tier.

### Operability gate

- health/readiness;
- metrics/log/tracing behavior;
- service SLOs;
- no sensitive payloads in telemetry.

### Developer-experience gate

- quickstart works from clean install;
- official client example works;
- error catalog and limits documented;
- migration/deprecation status visible.

## 15. Definition of done for API v1 beta

The first professional API beta is complete only when the exact beta scope has:

- versioned endpoint inventory;
- schema for every public object;
- one coherent namespace/convention set;
- principal/authority model for each deployment profile;
- durable mutation/idempotency semantics;
- read model and event model;
- observable/reliable runtime;
- contract/security/load qualification;
- official client/documentation;
- tagged source revision with reproducible qualification evidence.

The beta may intentionally exclude some future domains, but it must not leave
the semantics of included domains implicit.

## 16. What we deliberately do not do yet

- no autonomous merge API;
- no worker/verifier self-approval;
- no public-network exposure using only a localhost session token;
- no WebSocket until SSE proves insufficient;
- no opaque global project-health score;
- no hidden majority selection;
- no duplicate evidence/run/decision models for different UIs/providers.

## 17. Community impact

This plan reduces “architecture by chat” and makes API work independently
claimable. Contributors can pick one issue with bounded acceptance evidence
without needing to understand every connector, research algorithm, or enterprise
deployment concern.

The issue graph should be maintained as implementation evidence changes.
