# Product Spine Service v0.1

**Status:** proposed application-service contract  
**Date:** 2026-09-22  
**Scope:** provider-neutral orchestration across existing canonical IDKMesh artifacts

## 1. Purpose

This specification defines the application-service boundary that connects the
existing IDKMesh product components into one usable lifecycle.

It does not define a new correctness protocol.

The service coordinates existing canonical artifacts:

```text
WorkUnit
 -> RoutingDecision
 -> attempt/provider reference
 -> CandidateReference
 -> ResultManifest
 -> EvaluatorPlan
 -> VerificationResult
 -> Run Evidence Report
 -> Human Decision Record
```

The service may persist lifecycle events/references, but it must not create a
second competing source of truth for those canonical artifacts.

## 2. Service responsibilities

The Product Spine Service owns:

- preview orchestration;
- admission checks;
- deterministic/idempotent run identity;
- connector admission;
- dispatch coordination;
- attempt observation;
- candidate-reference handoff;
- result normalization handoff;
- verification handoff;
- evidence assembly handoff;
- human-decision recording handoff;
- read projections for CLI/API/GitHub/UI.

It does not own:

- provider-specific implementation details;
- evaluator policy;
- verification correctness;
- human acceptance authority;
- Git merge authority.

## 3. Lifecycle projection

Allowed states:

```text
proposed
previewed
admission_blocked
admitted
dispatched
attempt_failed
candidate_observed
normalized
verification_requested
verification_error
evidence_ready
awaiting_human_decision
decided
cancelled
```

This state is an operational projection. Canonical evidence artifacts remain the
source for their own semantics.

## 4. Core operations

### preview(request)

Must be side-effect free.

Input minimum:

- project/repository identity;
- exact source/request revision;
- actor context.

Output minimum:

- WorkUnit reference/digest;
- RoutingDecision;
- authority mode;
- blockers/warnings;
- eligible/ineligible connector explanation when available.

### admit(request, idempotency_key)

Must run before secret materialization or external work.

Checks:

- exact WorkUnit/source binding;
- actor authority;
- routing hard gates;
- project policy;
- connector health/capability;
- external-processing rule;
- spend rule;
- concurrency/capacity;
- durable duplicate detection.

Output:

- stable run ID;
- admission record/reference;
- eligible connector set.

### dispatch(run_id, connector_id)

Requires explicit admitted connector.

Output:

- attempt ID;
- provider/runtime run reference;
- append-only dispatch event.

The operation must be idempotent.

### observe(run_id, attempt_id)

Returns normalized attempt state and, when present, CandidateReference.

Observation never means candidate acceptance.

### normalize(candidate_reference)

Validates:

- exact WorkUnit binding;
- exact source SHA/digest;
- exact attempt identity;
- exact candidate SHA/artifact digest.

Output:

- canonical ResultManifest reference/digest.

### verify(result_manifest)

Verification remains evaluator-owned.

The service may invoke/request the verifier but may not fabricate or reinterpret
a VerificationResult.

### build_evidence(run_id)

Assembles the non-selecting Run Evidence Report from retained references.

The report must include failed/control-error attempts, not only favorable ones.

### record_decision(report_digest, actor, decision, rationale)

Allowed decisions:

- accept;
- reject;
- escalate.

Output:

- canonical Human Decision Record reference/digest.

The operation does not merge, push, or mutate protected application state.

## 5. Idempotency

Each mutating service operation must have a deterministic request digest.

At minimum, dispatch identity binds:

- project;
- WorkUnit digest;
- source revision;
- connector ID;
- logical dispatch request;
- policy revision.

Rules:

```text
same idempotency key + same request digest
 -> return existing outcome

same idempotency key + different request digest
 -> conflict / fail closed
```

## 6. Error classes

Normalize operational errors so routing/escalation does not confuse them with
reasoning failures.

Minimum classes:

- validation_error;
- configuration_error;
- authentication_error;
- authorization_error;
- policy_denied;
- human_gate_pending;
- duplicate_conflict;
- source_binding_error;
- connector_unavailable;
- capacity_unavailable;
- provider_unavailable;
- rate_limited;
- quota_exhausted;
- sandbox_failure;
- tool_failure;
- attempt_failed;
- candidate_missing;
- candidate_binding_error;
- normalization_error;
- verification_error;
- cancelled.

## 7. Authority invariants

The service must preserve:

```text
routing != dispatch authority
dispatch != candidate acceptance
candidate != verified result
verification recommendation != human decision
human decision != merge execution
```

No service method named or shaped as `merge` belongs in v0.1.

## 8. Secret boundary

Secret references may be inspected before admission.

Secret values may be materialized only:

- after project/actor/policy admission;
- for the exact admitted connector/action;
- for the shortest practical lifetime.

Secret values must never be stored in:

- run ledger;
- ResultManifest;
- VerificationResult;
- Run Evidence Report;
- Human Decision Record;
- UI snapshot;
- GitHub issue/comment status.

## 9. Provider neutrality

Provider-specific code implements connector/adapter interfaces.

The application service must not contain logic like:

```text
if provider == "jules": ...
elif provider == "openhands": ...
elif provider == "gemini": ...
```

Provider behavior should enter through normalized connector interfaces.

## 10. Persistence abstraction

Local development may use SQLite.

GitHub-only deployment may use the durable Git-native ledger from #597.

The service contract must not depend on one storage backend.

Required persisted facts are stable IDs, state transitions, request digests,
artifact references/digests, actor identities, and provider/runtime references.

## 11. Read projections

The same service state should feed:

- CLI;
- optional HTTP API;
- GitHub status projection;
- Human Control Tower.

These surfaces may render differently but must not compute independent business
rules.

## 12. Deterministic reference implementation

Before any credentialed provider is accepted as proof of the service, implement
an offline fixture path:

```text
fixture WorkUnit
 -> deterministic RoutingDecision
 -> fake admitted connector
 -> fake attempt
 -> fake CandidateReference
 -> canonical ResultManifest fixture
 -> real deterministic verifier fixture
 -> Run Evidence Report
 -> Human Decision Record pending/recording path
```

Acceptance:

- no network;
- no secret;
- deterministic IDs/digests where appropriate;
- replay-equivalent output;
- all lifecycle transitions validated;
- failed attempt fixture included;
- no merge authority.

## 13. Compatibility

v0.1 must preserve the existing canonical WorkUnit, ResultManifest,
VerificationResult, Run Evidence Report, and Human Decision Record contracts.

If integration reveals a missing field, prefer adding a referenced operational
record before changing canonical evidence schemas.

Schema changes require explicit versioning and migration/compatibility review.

## 14. Observability

Every run projection should make visible:

- current lifecycle state;
- WorkUnit digest;
- authority mode;
- selected/admitted connector;
- attempt IDs;
- candidate state;
- verification state;
- evidence state;
- human decision state;
- blocking reason;
- last durable event.

No opaque aggregate score is required.

## 15. Definition of done

A conforming implementation can drive one deterministic vertical slice from
preview through human-decision recording while:

- remaining provider-neutral;
- remaining storage-neutral;
- preventing duplicate dispatch;
- preserving exact source/candidate/evidence binding;
- keeping secrets out of durable/public surfaces;
- keeping verification and human authority separate;
- performing no merge.


## Reference lifecycle core

The standard-library reference implementation begins in
`idkmesh.product_spine`.

PS-A implements only the pure operational lifecycle boundary:

- explicit run and attempt state vocabularies;
- fail-closed transition validation;
- immutable run and attempt projections;
- retained failed attempts and new identities for retries;
- exact WorkUnit digest and Git source revision fields;
- the same authority-mode vocabulary used by connector routing;
- automatic admission blocked for `human_required` work;
- explicit zero write/push/merge authority in serialized projections;
- strict round-trip parsing for replay/read projections.

This module performs no network, provider, filesystem, database, verification,
human-decision, GitHub mutation, or integration work.

Its projection is not a canonical correctness artifact and must not replace
WorkUnit, ResultManifest, VerificationResult, Run Evidence Report, or Human
Decision Record. Those remain independently authoritative for their own
semantics.


## Deterministic offline vertical slice

The PS-B reference composition lives in
`idkmesh.product_spine_offline`.

It composes the lifecycle core with existing canonical boundaries while keeping
all external work fake:

```text
WorkUnit + exact source revision
 -> connector RoutingDecision
 -> fake admitted attempt
 -> CandidateReference observation
 -> ResultManifest normalization
 -> VerificationHandoff
 -> injected independent verifier
 -> existing Run Evidence Report builder
 -> human decision pending
 -> injected Human Decision Record builder
```

The package module does not import repository experiments. Verification,
evidence, and human-decision functions are injected, so the installed package
does not silently acquire evaluator or human authority.

The retained offline scenarios prove:

- a supported bounded candidate reaches independent verification and evidence;
- a failed worker attempt remains visible while a peer succeeds;
- wrong WorkUnit/source candidate bindings fail before verification;
- `human_required` authority blocks automatic dispatch even with a T4 connector;
- replaying identical offline inputs yields the same semantic run/evidence state.

This slice does not yet make admission/dispatch restart-idempotent. Durable
same-key/same-request reuse and same-key/different-request conflict handling
remain the PS-C composition over the local metadata/idempotency store.


## Local restart-safe idempotency composition

PS-C adds `idkmesh.product_spine_idempotency`, a local/reference wrapper around
the deterministic offline service and the existing SQLite
`LocalMetadataStore`.

The wrapper applies these fail-closed rules before worker/verifier execution:

- one canonical idempotency digest covers project, exact WorkUnit/source,
  routing policy, connector capabilities/policy, and deterministic attempt
  request content;
- candidate filesystem roots are excluded from semantic identity, while
  CandidateReference and WorkUnit/source/attempt bindings remain included;
- the idempotency key is atomically reserved before orchestration;
- same key + same request reconstructs the stored Product Spine projection and
  evidence without invoking the worker/verifier path again;
- same key + different request returns an idempotency conflict;
- a retained but incomplete reservation is not automatically re-dispatched;
- persisted Product Spine/evidence digest drift fails closed on replay.

The Product Spine run keeps its own internally derived request/evidence digest.
The SQLite record keeps the broader idempotency-request digest, and replay
cross-checks both bindings rather than allowing callers to override either one.

The persisted record contains compact, secret-free semantic projections and
digests. It is a development/reference store, not the hosted multi-tenant
durable ledger.

This slice completes the deterministic offline idempotency acceptance behavior.
Hosted recovery, provider session reconciliation, and distributed locking remain
separate durable-ledger concerns.
