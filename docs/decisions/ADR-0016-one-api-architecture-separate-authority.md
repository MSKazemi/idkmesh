# ADR-0016 — One API Architecture, Separate Authority Boundaries

**Status:** Accepted for API planning and implementation  
**Date:** 2026-09-23

## Context

IDKMesh now has several product-facing API directions:

- the local Human Control Tower;
- Connector Control API design;
- the Product Spine;
- CLI surfaces;
- GitHub-native orchestration;
- future enterprise/multi-user deployment.

Without an explicit decision, these surfaces could evolve separate resource
models, error contracts, authentication assumptions, or authority semantics.

The highest-risk failure would be semantic rather than syntactic: a convenient
transport endpoint could accidentally turn a worker result, verifier
recommendation, or human decision into execution/merge authority.

## Decision

Adopt one API architecture with:

1. one set of canonical domain contracts;
2. one provider-neutral application-service layer;
3. multiple transport/client adapters;
4. one product HTTP namespace, `/api/v1`;
5. independently versioned domain/object schemas;
6. separate local and network deployment/security profiles;
7. explicit identity/policy/idempotency for mutations;
8. append-only audit/event evidence for state changes;
9. human decision recording separated from integration execution.

The local Control Tower API remains a development/read profile. Its session
token is not enterprise identity.

Connector Control API, Product Spine, Control Tower, CLI, and future SDKs must
converge on shared application/domain semantics rather than create competing
canonical objects.

## Authority invariant

```text
API transport != authority
worker claim != evidence
verification != human decision
human decision != integration execution
integration execution != implicit merge permission
```

A transport or UI may expose an authorized action but may not manufacture the
authorization needed to perform it.

## Consequences

### Positive

- clients can move between CLI/HTTP/UI without semantic drift;
- provider adapters stay replaceable;
- schemas/OpenAPI can be contract-tested centrally;
- multi-user security can replace the transport/auth adapter without rewriting
  the domain model;
- human/governance responsibility remains visible.

### Costs

- existing Connector Control API path conventions must be reconciled;
- mutations require more explicit identity/idempotency/audit work;
- release work must include compatibility/schema checks;
- some short-term duplicate implementation may need convergence rather than
  further extension.

## Alternatives considered

### Separate API per product surface

Rejected. It would make Control Tower, connector control, and Product Spine
semantics drift and force clients to translate between competing models.

### Make the HTTP API the canonical domain model

Rejected. Transport details should not define WorkUnit/evidence/decision
semantics and would couple GitHub/CLI/local modes to one server implementation.

### Let a human decision endpoint perform integration directly

Rejected. Recording accountable intent and executing protected repository
changes have different authority and failure modes.

### Use one permanent local-token security model everywhere

Rejected. A loopback session token is useful for local tooling but is not a
multi-user identity, RBAC, tenancy, or revocation model.

## Implementation ownership

- #713 is the program umbrella.
- #735-#747 define missing API work.
- #677 retains HTTP-runtime ownership.
- #670 retains enterprise identity/policy ownership.
- #580/#570 retain connector-control ownership.
- #682 retains Product Spine integration ownership.
- #572 retains Control Tower UX ownership.

## Revisit conditions

Revisit this ADR if evidence shows:

- a domain cannot be represented behind shared application services without
  harmful coupling;
- the `/api/v1` namespace cannot safely accommodate the declared v1 resources;
- event sourcing/persistence requirements require a materially different
  authority model;
- a second deployment profile demonstrates unavoidable incompatible semantics.

Any revision must preserve the explicit separation between evidence, human
decision, and integration authority unless governance deliberately changes that
project invariant.
