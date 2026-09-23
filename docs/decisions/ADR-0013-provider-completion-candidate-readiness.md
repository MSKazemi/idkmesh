# ADR-0013 — Separate Provider Completion from Candidate Readiness

- **Status:** Proposed
- **Date:** 2026-09-23
- **Related:** #575, PRs #702 and #703, Connector Control API v0.1

## Context

IDKMesh treats external coding systems as replaceable workers. A provider can report that
its task or session is complete, and it can expose outputs such as a pull-request URL.
Neither fact proves that IDKMesh has a usable, correctly bound candidate.

Collapsing provider completion directly into `candidate_ready` creates an authority and
provenance ambiguity:

- the provider is allowed to declare its own work complete;
- candidate identity belongs to the IDKMesh control/evidence boundary;
- a URL alone does not bind repository, pull-request number, exact head revision, or
  candidate artifact digest;
- a provider may complete successfully without producing a candidate of the expected type;
- provider APIs may change their output schema independently of IDKMesh.

The repository already holds the stronger invariant:

```text
worker success != acceptance
verification recommendation != merge authority
```

The run state machine should preserve the same separation between worker completion and
candidate discovery.

## Decision

IDKMesh will model **provider/worker completion** and **candidate readiness** as separate
states and separate evidence transitions.

### 1. Add a `worker_completed` run state

`worker_completed` means only:

> the selected worker/provider reports that its execution attempt has finished.

It does not mean a candidate exists, is correctly identified, is acceptable, or is verified.

A Jules Session in provider state `COMPLETED` therefore maps to
`worker_completed`, not `candidate_ready`.

### 2. Candidate readiness requires a concrete normalized candidate reference

A run may advance to `candidate_ready` only after IDKMesh has a provider-neutral
`CandidateReference` whose identity is independently resolved enough for the candidate
type.

For a GitHub pull request, the minimum reference is:

- repository identity;
- pull-request number;
- exact head commit SHA.

A provider-returned pull-request URL is a **discovery hint**, not the final candidate
identity. The SCM boundary must resolve and confirm the immutable head revision.

For an artifact bundle, candidate readiness requires a stable locator plus content digest.

### 3. Provider outputs remain observations

Provider output records may be counted or retained as bounded structural metadata for
discovery, but they do not advance authority by themselves.

The transition is:

```text
provider reports COMPLETED
        |
        v
worker_completed
        |
        v
candidate discovery/normalization
        |
        +-- no acceptable candidate --> remain worker_completed / fail by explicit policy
        |
        +-- concrete candidate bound --> candidate_ready
        |
        v
ResultManifest -> independent verification -> human/governance decision
```

### 4. Unknown provider states cannot advance the run

An unknown or newly introduced provider state must remain non-authoritative until the
adapter explicitly maps it. It may be surfaced with a warning, but it must not imply
`worker_completed`, `candidate_ready`, verification, or integration.

### 5. Completion events remain append-only observations

`agent.completed` is an observation event. It must not rewrite or synthesize
`candidate.discovered`, `result.normalized`, `verification.completed`, or a human
decision event.

## Consequences

### Positive

- preserves a clean provider-neutral trust boundary;
- prevents a provider from implicitly defining candidate identity;
- makes candidate provenance explicit and replayable;
- supports workers that finish without creating a PR;
- allows the same lifecycle for PR candidates and non-PR artifact bundles;
- makes later verifier and human-authority stages easier to audit.

### Cost

- candidate discovery requires an additional normalization/SCM lookup step;
- a provider that says "completed" may remain in `worker_completed` until its output is
  resolved;
- adapters need explicit logic for candidate types rather than treating provider output as
  canonical.

These costs are intentional. IDKMesh optimizes for verified useful work, not the shortest
possible state machine.

## Alternatives considered

### Map provider `COMPLETED` directly to `candidate_ready`

Rejected. It treats a provider claim as canonical candidate evidence and makes a later
candidate-normalization stage semantically redundant.

### Treat every provider completion as `failed` unless a PR already exists

Rejected. Workers may validly complete with non-PR artifacts, no-change outcomes, or
outputs that require a separate discovery pass.

### Let each connector define its own completion semantics

Rejected. That would make run-state meaning provider-specific and weaken the shared control
plane.

## Implementation requirements

1. Connector Control API v0.1 includes `worker_completed`.
2. Jules `COMPLETED` maps to `worker_completed`.
3. C2-F candidate discovery may advance to `candidate_ready` only after a concrete
   candidate reference is normalized.
4. Tests must prove that provider completion with a PR-shaped output still does not itself
   become `candidate_ready`.
5. No connector completion path may emit `verified`, `awaiting_human_decision`, or
   `integrated`.

## References

- `docs/specifications/CONNECTOR_CONTROL_API_V0_1.md`
- `docs/decisions/ADR-0004-verified-swarm-runner-first-product.md`
- `docs/decisions/ADR-0008-independent-evidence-verification.md`
- `docs/decisions/ADR-0010-external-action-handoff.md`
- `docs/planning/AGENT_MODEL_INTEGRATION_SELF_HOSTING_PLAN_2026-09-22.md`
