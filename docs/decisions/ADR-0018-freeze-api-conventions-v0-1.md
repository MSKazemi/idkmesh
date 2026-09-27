# ADR-0018 — Freeze API Conventions v0.1

**Status:** Accepted  
**Date:** 2026-09-27

## Context

ADR-0016 decided that IDKMesh product HTTP APIs share one architecture — one
domain model, one application-service layer, one `/api/v1` namespace — but
left the specific cross-cutting conventions (error shape, HTTP status
mapping, pagination, idempotency, concurrency, deprecation) as a "proposed
baseline" in `docs/specifications/API_CONVENTIONS_V0_1.md`, explicitly
deferred to issue #736.

Every API-* issue in the #713 program (#737-#747) depends on those
conventions being settled before it can define its own endpoints without
re-litigating error codes or pagination shape per issue. Two implementations
already exist against the proposed conventions — `idkmesh/control_tower_api.py`
already emits the section 5 error envelope (`kind: idkmesh-api-error`,
`schema_version`, `ok`) and the section 8 service headers — so freezing is
formalizing a contract already exercised by running code, not designing one
from a blank page.

The two remaining acceptance gaps from issue #736 were:

1. the specification's sections 5 and 10 example JSON blocks were prose, not
   machine-testable contracts (no schema, no CI validation);
2. no architecture document for Control Tower or the connector control plane
   linked to the conventions specification, so a reader following the
   architecture docs would not discover it.

## Decision

Freeze `docs/specifications/API_CONVENTIONS_V0_1.md` as the v0.1 cross-cutting
HTTP convention contract for every IDKMesh product API, with the following
closing this ADR's two acceptance gaps:

1. `schemas/idkmesh-api-error-v0.1.schema.json` and
   `schemas/idkmesh-list-v0.1.schema.json` are the canonical JSON Schemas for
   the section 5 error envelope and section 10 list envelope. Each envelope
   has one committed example under `examples/api/`, registered in
   `tests/test_example_contract_coverage.py`, so a future incompatible change
   to either envelope fails CI rather than silently drifting from this
   specification.
2. `docs/architecture/API_CONTROL_PLANE_ARCHITECTURE.md` and
   `docs/architecture/AGENT_MODEL_CONNECTOR_CONTROL_PLANE.md` — the Control
   Tower and connector-control-plane architecture documents named in issue
   #736's acceptance criteria — now link to the frozen specification.

"Frozen" means sections 5, 6, 12, 13, and 20 are the stable v0.1 contract:
changing any of them is a breaking change under the specification's own
section 22 compatibility-class rule, not a same-document edit. The remaining
sections (namespace, resource identity, correlation, headers, auth profile,
list/filter shape, events, limits, OpenAPI, browser-mutation security) were
already consistent with ADR-0016 and required no change to freeze.

## Consequences

### Positive

- API-2 through API-13 (#737-#747) can build against one settled error,
  status, pagination, and idempotency contract instead of each defining its
  own;
- the error and list envelopes are enforced by a schema and a committed
  example, not only by prose a future editor could drift from unnoticed;
- Control Tower and connector-control architecture readers now have a direct
  path to the conventions that govern their own endpoints.

### Costs

- a future genuinely necessary change to the frozen sections must go through
  the section 22 compatibility-class process (a new ADR/decision record and
  release/migration evidence) rather than a quick doc edit;
- `idkmesh/control_tower_api.py` and any future endpoint are now measured
  against this contract; a divergence found later is a bug against a frozen
  spec, not a design question still open.

## Alternatives considered

### Leave the specification "proposed" until every API-* issue ships

Rejected. Every dependent issue already needs a stable contract to design
against; deferring the freeze past issue #736 would just relocate the same
error/pagination/idempotency debate into #737-#747 one at a time, with a
higher chance of quiet drift between them.

### Validate the envelope examples with a hand-written assertion instead of a JSON Schema

Rejected. This repository's own section 19 requirement ("public objects have
canonical JSON Schemas... examples validate in CI") applies to the
specification's own envelopes as much as to any domain object; a bespoke
assertion would not compose with `tests/test_example_contract_coverage.py`'s
existing schema-validity and completeness guarantees.

### Fold the frozen conventions into ADR-0016 instead of a new ADR

Rejected. ADR-0016 is already `Accepted`; this repository treats an accepted
ADR as an immutable record of its own decision. The conventions freeze is a
distinct, later decision that extends ADR-0016 without re-opening it.

## Implementation ownership

- #713 is the program umbrella.
- #736 (this ADR's issue) is closed by this decision.
- #737-#747 build against these frozen conventions.
- #677 retains HTTP-runtime ownership; #682 retains Product Spine integration
  ownership. Neither introduces a competing envelope shape.

## Revisit conditions

Revisit this ADR if evidence shows:

- a shipped API-* endpoint needs an error/status/pagination/idempotency shape
  the frozen conventions cannot express without contradiction;
- the opaque-cursor list envelope proves unsafe or insufficient for a real
  mutable event/run stream;
- a second deployment profile (network/multi-user) demonstrates the frozen
  authentication or concurrency conventions cannot hold.

Any revision must go through the section 22 compatibility-class process this
ADR froze, and must preserve ADR-0016's authority invariant
(`API transport != authority`).
