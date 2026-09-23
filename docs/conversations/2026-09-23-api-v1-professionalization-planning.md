# Conversation record — API v1 professionalization planning

**Date:** 2026-09-23  
**Program:** #713  
**Planning branch:** `planning/api-v1-professionalization-blueprint`

## Project-owner requirement

The project owner asked to stop implementation temporarily and first ensure that
all planning, documentation, issue decomposition, dependencies, and acceptance
criteria required for a professional API are present in GitHub. The intent is to
improve each design area one by one before resuming implementation.

## Repository audit

Existing API-relevant owners were reviewed before creating new work:

- #713 — API production-readiness umbrella;
- #677 — reusable HTTP service-runtime baseline;
- #670 — enterprise identity federation / RBAC / ABAC;
- #580 — connector CLI and optional HTTP API;
- #570 — connector-control-plane program;
- #682 — end-to-end Product Spine;
- #616 — restart-safe metadata/idempotency store;
- #572 — Human Control Tower;
- #667 — enterprise readiness/security;
- `CONNECTOR_CONTROL_API_V0_1.md`;
- Human Decision Record schema.

The audit showed that the project needed an API-wide execution map and several
missing cross-cutting owners, but should not duplicate the existing subsystems.

## Planning artifacts added

### Master plan

`docs/planning/API_V1_PROFESSIONALIZATION_PLAN_2026-09-23.md`

Defines:

- definition of API completeness;
- target layers and deployment profiles;
- resource families;
- issue program;
- dependency sequence;
- endpoint readiness checklist;
- contract/security/reliability/operability/developer-experience gates;
- v1 beta definition of done.

### Architecture

`docs/architecture/API_CONTROL_PLANE_ARCHITECTURE.md`

Defines one domain/application-service model with multiple transports and keeps
human decision separate from integration execution.

### API conventions

`docs/specifications/API_CONVENTIONS_V0_1.md`

Introduces the proposed cross-cutting contract for:

- namespace/versioning;
- JSON;
- IDs/digests;
- errors/status codes;
- request/service metadata;
- auth profiles;
- pagination;
- idempotency/concurrency;
- events;
- health/readiness;
- limits;
- observability;
- OpenAPI/schema compatibility;
- deprecation;
- browser mutation security.

Issue #736 owns review and final freezing of this baseline.

### Architecture decision

`docs/decisions/ADR-0013-one-api-architecture-separate-authority.md`

Records the decision to use one API architecture, `/api/v1` as the intended
product namespace, shared domain/application services, separate local/network
security profiles, and explicit separation of evidence, human decision, and
integration authority.

### Dependency graph

`docs/planning/API_V1_ISSUE_DEPENDENCY_GRAPH_2026-09-23.md`

Defines execution waves, hard dependencies, parallel tracks, acceptance
artifacts, critical path, and the readiness checklist before coding.

## New claimable API issues

Created under #713:

- #735 — converge and qualify current Control Tower local API v0.1;
- #736 — conventions/versioning/errors/deprecation;
- #737 — public schema catalog + compatibility CI;
- #738 — unified Control Tower/Connector service architecture;
- #739 — resource-oriented read API;
- #740 — immutable Human Decision API;
- #741 — canonical event envelope/query/resumable SSE;
- #742 — reliability/limits/backpressure/graceful shutdown;
- #743 — network/multi-user API security profile;
- #744 — metrics/tracing/SLO contract;
- #745 — conformance/fuzz/load/security qualification;
- #746 — official Python/TypeScript clients + professional docs;
- #747 — v1 beta release qualification.

These issues explicitly reference existing owners where work is already
assigned rather than creating replacement implementations.

## Key planning decisions

1. No further endpoint expansion should happen before the current API branch is
   converged and the shared conventions/architecture are reviewed.
2. Product HTTP paths should converge on `/api/v1`; object schema versions stay
   independent.
3. Local loopback token authentication is a local profile, not a multi-user auth
   mechanism.
4. Human Decision API is the first intended mutation but remains non-actuating.
5. The read model and canonical event model precede a broad network control
   plane.
6. Mutations require identity, authorization, idempotency, concurrency rules,
   immutable audit evidence, and explicit authority ceilings.
7. Public API release quality includes compatibility, fuzz/load/security,
   observability, clients, docs, and reproducible tagged-source evidence.

## Implementation hold point

This turn intentionally focuses on planning/docs/issues. Feature implementation
should resume only by selecting a ready issue from the dependency graph and
refining its details first.

The first recommended implementation target after planning is #735: converge
and qualify the existing local API baseline.

## Community impact

This planning package converts a large API ambition into claimable,
evidence-bounded work. A contributor can work on one issue without needing
private chat context or inventing cross-cutting conventions independently.

## AI/tool provenance

Repository audit, issue decomposition, and documentation were produced with
ChatGPT using connected GitHub tools. No claim of independent human review is
made.
