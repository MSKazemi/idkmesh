# IDKMesh API Control-Plane Architecture

**Status:** planning baseline  
**Date:** 2026-09-23  
**Program:** #713  
**Companion plan:** `API_V1_PROFESSIONALIZATION_PLAN_2026-09-23.md`

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
