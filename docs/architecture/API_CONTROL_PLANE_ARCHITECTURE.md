# IDKMesh API Control-Plane Architecture

**Status:** planning baseline  
**Date:** 2026-09-23  
**Program:** #713  
**Companion plan:** `API_V1_PROFESSIONALIZATION_PLAN_2026-09-23.md`  
**Cross-cutting conventions:** every endpoint under `/api/v1` follows the frozen
[API Conventions v0.1](../specifications/API_CONVENTIONS_V0_1.md) (error
envelope, status mapping, pagination, idempotency, concurrency, deprecation —
[ADR-0018](../decisions/ADR-0018-freeze-api-conventions-v0-1.md)). This
document defines how surfaces compose; the conventions specification defines
how each one talks HTTP.

## Purpose

This document defines how IDKMesh API surfaces fit together so the Control
Tower, connector control plane, Product Spine, CLI, and future multi-user
service do not evolve into separate systems with different semantics.

## Architectural rule

```text
one domain model
+ one application-service layer
+ multiple transport/client adapters
```

HTTP, CLI, GitHub Actions, browser UI, and provider connectors are adapters.
They may transform transport details but may not redefine WorkUnits, runs,
evidence, human decisions, or authority.

## Logical layers

### 1. Domain contracts

Canonical domain objects remain independently versioned:

- ProjectManifest / DomainPack;
- WorkUnit;
- RoutingDecision;
- CandidateReference;
- ResultManifest;
- EvaluatorPlan;
- VerificationResult;
- Run Evidence Report;
- Human Decision Record;
- ActorContext / AuthorizationDecision;
- compute/resource admission objects;
- future canonical Event Envelope.

No HTTP endpoint may create a competing replacement object merely for UI
convenience.

### 2. Application services

Application services own use-case semantics:

- project/work query;
- connector configuration/probe;
- WorkUnit preview;
- route resolution;
- run lifecycle;
- candidate normalization;
- verification/evidence inspection;
- human decision recording;
- event query/stream;
- integration handoff.

They are provider-neutral and transport-neutral.

### 3. Policy / authority boundary

Before a state-changing application service executes, it receives explicit:

- principal/ActorContext;
- project/tenant scope;
- AuthorizationDecision or equivalent policy evidence;
- source revision;
- idempotency metadata;
- risk/authority class.

A service may return `requires_approval`; it must not invent missing approval.

### 4. Persistence

Persistence adapters retain:

- immutable evidence;
- run/attempt metadata;
- idempotency records;
- human decisions;
- append-only events;
- connector configuration with secret references only.

Persistence stores decisions/evidence; it does not grant authority.

### 5. Transport adapters

Profiles:

#### Local HTTP

- loopback only;
- development/control-tower profile;
- session token;
- dependency-light;
- default read-only surface.

#### Network HTTP

- production transport;
- TLS/proxy assumptions explicit;
- trusted principal propagation;
- policy enforcement;
- rate/overload controls;
- durable services/stores;
- never direct public exposure of the development stdlib server.

#### CLI

Calls the same application services. CLI flags are not a parallel policy model.

#### GitHub-native adapters

GitHub events/actions are untrusted inputs until normalized and authorized.
Labels/comments are projections or triggers, not canonical authority.

## Namespace

Product HTTP resources converge on:

`/api/v1`

Runtime probes remain outside the product namespace:

- `/healthz`
- `/readyz`

Object schema versions remain independent from URL compatibility versions.

## Dependency diagram

The architectural rule above, grounded in the modules that exist on `main`
today (not a target-state sketch):

```text
+----------------------------------------------------------------+
| Domain contracts (schemas/*.schema.json)                       |
| WorkUnit, RoutingDecision, CandidateReference, ResultManifest,  |
| VerificationResult, Run Evidence Report, Human Decision Record  |
+----------------------------------------------------------------+
                              ^
                              | validated against, never redefined by
                              |
+----------------------------------------------------------------+
| Application services (idkmesh/*.py)                            |
|  control_tower_api.py     -- read-only evidence inspection      |
|  connector_store.py       -- connections/routing/run persistence|
|  connector_routing.py     -- RoutingDecision resolution         |
|  product_spine_run_store.py -- run create/status/cancel         |
|  local_loop.py            -- WorkUnit -> attempts -> evidence   |
|                               (delegates to experiments/*)      |
+----------------------------------------------------------------+
          ^                 ^                  ^              ^
          | thin dispatch   | thin dispatch    | thin dispatch |
          |                 |                  |               |
+---------+------+  +-------+--------+  +------+-------+  +----+----+
| Local HTTP     |  | CLI            |  | GitHub-native |  | Network |
| control-tower  |  | idkmesh {...}  |  | Actions/hooks |  | HTTP    |
| /api/v1, read  |  | connections,   |  | untrusted     |  | (not    |
| -only + GET    |  | run, local-loop|  | until checked |  | built)  |
| runs, GET runs/|  |                |  |               |  |         |
| {id}, GET runs/|  |                |  |               |  |         |
| {id}/attempts, |  |                |  |               |  |         |
| GET work-units,|  |                |  |               |  |         |
| GET work-units/|  |                |  |               |  |         |
| {id}, GET      |  |                |  |               |  |         |
| projects/{id}  |  |                |  |               |  |         |
| (#739)         |  |                |  |               |  |         |
+----------------+  +----------------+  +---------------+  +---------+
```

The Local HTTP box's run, WorkUnit, and project read endpoints are opt-in per
server instance (`idkmesh control-tower --product-spine-store PATH`); they
return 503 without it, rather than being conditionally present in this
diagram. The WorkUnit and project endpoints are read models derived from
stored runs
([ADR-0021](../decisions/ADR-0021-derived-work-unit-and-project-read-models.md)),
not a WorkUnit or project store; `idkmesh work-unit list|status` and
`idkmesh project status` read through the same service.

Every box in the bottom row is a transport/client adapter over the same
application services; none may redefine a domain contract to fit its own
transport. The Network HTTP adapter is explicitly not built yet -- see
"Architecture completion evidence" below.

## Resource ownership map

| Resource/use case | Canonical owner |
| --- | --- |
| projects | ProjectManifest/Product Spine |
| connections/probes | Connector Control Plane (#570/#580) |
| WorkUnit preview | Product Spine + connector service |
| routes | RoutingDecision / connector kernel |
| runs | Product Spine / run service |
| attempts/candidates | run service + CandidateReference |
| result manifests | ResultManifest contract |
| verification | verifier/evidence service |
| run evidence | Run Evidence Report |
| human decisions | Human Decision Record |
| resource/compute admission | zero-project-spend compute router (`experiments/free_compute_router.py`, `scripts/free_resource_planner.py`, ADR-0006) |
| events | canonical event service (#741) |
| integration execution | separate protected integration authority |

## Read versus mutation separation

Read surfaces may aggregate projections, but must expose the underlying
provenance/digests.

Mutation surfaces must add:

- authenticated principal;
- authorization;
- idempotency;
- concurrency/conflict semantics;
- immutable audit event;
- postcondition evidence.

## Human Decision boundary

The Human Decision API records:

```text
who decided
what decision
why
which exact evidence digest
when
```

It does not:

- merge;
- push;
- edit canonical code;
- dispatch a worker.

A later integration actor must independently consume the decision plus policy.

## Event architecture

Events are append-only facts about state transitions, not a replacement for the
domain records they reference.

The future event service must support:

- exact event ID;
- stream sequence;
- actual occurrence time;
- principal/actor;
- object IDs;
- source revision;
- payload/evidence digest;
- authority class;
- resumable cursor.

SSE is the first live-delivery transport because current needs are one-way
observation.

## Local-to-network evolution

The local API is not thrown away when network mode arrives.

Shared:

- domain contracts;
- application services;
- schemas;
- error semantics;
- audit/event semantics;
- authority rules.

Replaced/extended:

- transport server;
- authentication;
- tenancy;
- persistence;
- rate/overload controls;
- TLS/proxy boundary;
- metrics/tracing.

## Failure model

The API distinguishes:

- invalid input;
- unauthenticated;
- unauthorized;
- not found;
- conflict/idempotency mismatch;
- rate limited;
- dependency unavailable;
- internal control failure.

A worker/provider failure is a domain outcome and should not automatically be
reported as an HTTP server failure when the request itself was processed
correctly.

## Security model

### Local

The session token protects the local browser/API boundary. It is not a user
identity.

### Network

Principal identity comes from a trusted authentication adapter and is evaluated
through #670 policy semantics. Role/authority is never inferred from model
output, issue text, labels, or self-declared headers.

## Operational model

All HTTP services should converge on the reusable runtime baseline:

- request ID;
- service/version headers;
- liveness/readiness;
- bounded logs;
- deterministic bodies where promised.

Later network services add:

- metrics;
- tracing;
- SLOs;
- limits/backpressure;
- graceful drain.

## Implementation ownership

The API program does not absorb existing subsystems.

- #677 owns common HTTP runtime primitives.
- #670 owns enterprise identity/policy semantics.
- #616 owns local persistence/idempotency prototype.
- #597 owns the GitHub-native durable run/event/evidence ledger.
- #598 owns the GitHub-first multi-user role/authority profile.
- #607 owns GitHub governance and secret-access preflight.
- #580 owns connector CLI/HTTP productization.
- #682 owns Product Spine lifecycle integration.
- #572 owns Human Control Tower UX.
- #713 + #735-#747 own API-wide convergence and missing cross-cutting contracts.

## Anti-patterns

Reject designs that:

- implement policy separately in browser JavaScript;
- create provider-specific run objects as canonical state;
- let a verifier recommendation populate a Human Decision Record automatically;
- make HTTP 200 mean “accepted for integration”;
- infer independence from different worker/verifier names;
- use a UI health score as evidence;
- put raw secrets in API objects;
- expose localhost authentication as enterprise auth;
- silently retry non-idempotent mutations.

## Architecture completion evidence

This architecture is considered implemented only when:

1. Control Tower and connector endpoints share the conventions/application
   service boundary;
2. domain objects are schema-bound;
3. mutations enforce identity/policy/idempotency;
4. persistence and events are restart-safe;
5. a client can follow WorkUnit -> run -> evidence -> human decision without
   provider-specific knowledge;
6. integration remains separately authorized.

### Verified against current main -- 2026-09-27

Not yet fully implemented; measured state per criterion, so a later pass can
tell what actually changed rather than re-deriving all six from scratch:

1. **Partial.** `idkmesh/control_tower_api.py` emits the frozen conventions
   (`idkmesh-api-error`, service headers) over real local HTTP endpoints. No
   connector-control HTTP endpoint exists yet to compare against --
   `docs/specifications/CONNECTOR_CONTROL_API_V0_1.md` remains an
   unimplemented design contract (issue #580). Not measurable until a
   connector HTTP endpoint ships.
2. **Partial.** Domain contracts (WorkUnit, ResultManifest, VerificationResult,
   Run Evidence Report, Human Decision Record) and the cross-cutting
   envelopes (error, list, status, inspection, readiness -- issue #736/#737)
   are schema-bound. The event envelope and a human-decision API
   request/response wrapper are not (issue #737 remains open for both).
3. **True for the CLI mutation path.** `idkmesh run create --idempotency-key`
   persists to a SQLite `idempotency_key TEXT ... UNIQUE` constraint in
   `idkmesh/connector_store.py`, so a duplicate key with a different request
   digest fails closed rather than double-creating a run. No HTTP mutation
   endpoint exists yet to verify the same at the transport layer.
4. **Partial.** Product Spine run/connection state persists in a restart-safe
   local SQLite store (`idkmesh/connector_store.py`). The canonical event
   service (#741) referenced by the ownership map above does not exist yet,
   so "events are restart-safe" is not yet measurable.
5. **True for one bounded case, via the CLI.** `idkmesh local-loop <config>`
   (issue #883/ROADMAP S4 R1) runs WorkUnit -> two isolated attempts ->
   independent verification -> evidence report end to end without the
   caller naming a worker/provider. Recording a human decision and replay
   are still separate, deliberately manual commands, not part of this
   client path. Not yet exposed over HTTP.
6. **True.** No code path in `idkmesh/control_tower_api.py`,
   `idkmesh/local_loop.py`, or the Product Spine CLI grants merge/push
   authority; `idkmesh local-loop` explicitly prints next steps
   (`record_human_decision.py`, `replay_run.py`) rather than executing them.

Net: this architecture is grounded and consistently followed where it has
been implemented, but is not yet complete by its own six-criterion bar --
criteria 1 and 4 are blocked on work (a connector HTTP endpoint, the event
service) that does not exist yet, not on a design disagreement.
