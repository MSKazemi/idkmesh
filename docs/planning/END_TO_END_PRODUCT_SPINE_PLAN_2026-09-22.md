# End-to-End Product Spine Execution Plan

**Date:** 2026-09-22  
**Status:** proposed P0 integration milestone  
**Parent program:** #570  
**Release gates:** #16, #374  
**Primary component dependencies:** #574, #578, #579, #580, #597, #598, #572, #596, #599

## 1. Why this plan exists

IDKMesh already has strong protocol and evidence foundations:

- canonical WorkUnit contracts;
- ResultManifest;
- EvaluatorPlan / evaluator sovereignty;
- VerificationResult;
- Run Evidence Report;
- Human Decision Record;
- deterministic routing primitives;
- worker/runtime experiments;
- GitHub-first product architecture.

The remaining product risk is **integration fragmentation**.

Today the repository can explain each subsystem independently, but a newcomer still cannot rely on one stable product path that performs:

```text
GitHub issue / bounded request
 -> canonical WorkUnit
 -> capability + authority routing
 -> admitted connector
 -> bounded attempt
 -> provider-specific candidate
 -> provider-neutral ResultManifest
 -> independent VerificationResult
 -> Run Evidence Report
 -> explicit Human Decision Record
 -> protected integration outside worker authority
```

The goal of this plan is to make that path the primary product spine.

## 2. Product principle

The product spine is an **application-service orchestration layer**, not a new evidence protocol.

It must reuse existing canonical artifacts rather than invent competing formats.

### Canonical artifacts remain

- WorkUnit;
- ResultManifest;
- EvaluatorPlan;
- VerificationResult;
- Run Evidence Report;
- Human Decision Record;
- existing identity/provenance bindings.

### The product spine adds only

- lifecycle orchestration;
- idempotent run/attempt identity;
- connector admission;
- durable state references/events;
- normalized service methods;
- read projections for CLI, GitHub, HTTP, and Control Tower.

It does **not** gain:

- correctness authority;
- verification authority;
- human-decision authority;
- merge authority.

## 3. The most important current gap

The repository currently has many useful implementation candidates, but most product-control modules are not yet on `main`.

The immediate gap is therefore twofold:

1. **Convergence:** integrate the C1 connector stack into a stable mainline contract.
2. **Vertical integration:** bind C1 + dispatch + candidate normalization + verification + human decision into one product-service flow.

Adding more providers before this spine exists would increase fragmentation.

## 4. Target user experience

### Local / CLI profile

```text
idkmesh work preview --issue 123
idkmesh route explain ...
idkmesh run create --issue 123
idkmesh run status RUN_ID
idkmesh evidence show RUN_ID
idkmesh decision record RUN_ID --accept|--reject|--escalate
```

The exact command names may evolve, but the semantic path must remain one service.

### GitHub-first profile

```text
structured issue
 -> preview workflow
 -> explicit authorized dispatch
 -> durable run ledger
 -> worker connector
 -> candidate PR/artifact
 -> normalization
 -> verification
 -> GitHub evidence summary / Control Tower
 -> explicit human decision
 -> normal protected PR integration
```

No always-on IDKMesh server is required for the bootstrap profile.

## 5. Product spine state machine

The first implementation should expose a simple deterministic projection:

```text
PROPOSED
  |
  v
PREVIEWED
  |
  v
ADMISSION_BLOCKED --------> stop / human/config action
  |
  v
ADMITTED
  |
  v
DISPATCHED
  |
  +---- provider/runtime failure ---> ATTEMPT_FAILED
  |
  v
CANDIDATE_OBSERVED
  |
  v
NORMALIZED
  |
  v
VERIFICATION_REQUESTED
  |
  +---- verifier/control failure --> VERIFICATION_ERROR
  |
  v
EVIDENCE_READY
  |
  v
AWAITING_HUMAN_DECISION
  |
  +---- ACCEPT
  +---- REJECT
  +---- ESCALATE
  |
  v
DECIDED
```

Protected merge/integration remains **outside** the service state machine.

A human acceptance decision is not itself a Git push or merge.

## 6. Canonical service boundary

The application service should eventually expose operations equivalent to:

### preview

Input:

- project/repository;
- exact issue/request revision;
- actor context.

Output:

- WorkUnit preview/reference;
- WorkUnit digest;
- RoutingDecision;
- blockers;
- no side effects.

### admit

Input:

- exact WorkUnit digest;
- exact routing policy revision;
- actor context;
- idempotency key.

Output:

- run ID;
- admitted connector set;
- durable admission event.

Hard gates happen before secret materialization.

### dispatch

Input:

- run ID;
- explicit admitted connector;
- attempt identity;
- exact source revision.

Output:

- provider/runtime run reference;
- append-only dispatch event.

### observe

Input:

- run/attempt reference.

Output:

- normalized provider status;
- candidate reference when available.

### normalize

Input:

- candidate reference;
- WorkUnit/source binding.

Output:

- canonical ResultManifest or fail-closed binding error.

### verify

Input:

- ResultManifest;
- evaluator-owned plan/policy.

Output:

- canonical VerificationResult.

### evidence

Input:

- run ID and all retained attempt/verification references.

Output:

- non-selecting Run Evidence Report.

### record human decision

Input:

- exact immutable evidence-report digest;
- authenticated human actor;
- accept/reject/escalate;
- rationale.

Output:

- Human Decision Record.

This operation never performs a merge.

## 7. Durable identity requirements

Every run must retain:

- project ID;
- WorkUnit ID/version/digest;
- exact repository/base SHA;
- issue/request revision;
- routing policy version;
- authority mode;
- selected/admitted connector;
- idempotency key;
- attempt IDs;
- provider/runtime IDs;
- candidate reference + exact head SHA/digest;
- ResultManifest reference/digest;
- EvaluatorPlan reference/digest;
- VerificationResult reference/digest;
- Run Evidence Report reference/digest;
- Human Decision Record reference/digest;
- initiating/authorizing human identity where applicable.

No provider secret value belongs in durable records.

## 8. Required invariants

### Authority

```text
issue author != dispatch authority
worker != verifier authority
verifier recommendation != human decision
human decision != merge execution
model tier != repository authority
```

### Idempotency

The same logical dispatch request must never create duplicate external work.

```text
same project
+ same WorkUnit digest
+ same source revision
+ same connector
+ same logical dispatch request
= same idempotency identity
```

Same key + different request digest must fail with conflict.

### Candidate binding

A candidate must not enter verification unless it binds to:

- exact WorkUnit;
- exact base/source revision;
- exact provider/worker attempt;
- exact candidate revision/artifact digest.

### Failure classification

Do not escalate model capability for:

- provider outage;
- authentication failure;
- missing secret;
- sandbox failure;
- CI backlog;
- task scope failure;
- human gate pending.

Those are not reasoning failures.

## 9. P0 dependency order

### Phase 0 — converge C1

Integrate and retarget the connector stack:

```text
#624 profile
 -> #625 registry
 -> #626 probes
 -> #629 validate/list CLI
 -> #656 probe/doctor/route explain
 -> #657 adversarial exit gate

parallel:
#627 secret boundary
#628 local metadata/idempotency
```

Exit:

- one stable connector/profile/probe/routing interface is on `main`;
- exact-head CI is green;
- adversarial tests are part of normal regression.

### Phase 1 — freeze Product Spine service contract

Create a small service-level implementation contract from the specification in
`docs/specifications/PRODUCT_SPINE_SERVICE_V0_1.md`.

No live provider needed.

Exit:

- service methods and lifecycle states agreed;
- no new competing canonical artifact introduced;
- idempotency and authority semantics explicit.

### Phase 2 — deterministic offline vertical slice

Implement the whole product spine with fake/offline adapters:

```text
fixture WorkUnit
 -> deterministic route
 -> fake admitted worker
 -> fake candidate reference
 -> candidate normalization
 -> existing verifier fixture
 -> Run Evidence Report
 -> human decision pending
```

This is the first end-to-end acceptance proof.

It should test orchestration semantics without network/provider uncertainty.

Exit:

- one command/test exercises the full lifecycle;
- all canonical digests/references are retained;
- no merge occurs;
- replay is deterministic.

### Phase 3 — real local bounded worker

Compose C4 local runner behind the same service.

Exit:

- real local candidate reaches ResultManifest + verification + evidence;
- provider-specific code remains behind connector/adapter boundary;
- failed attempt does not corrupt peer state.

### Phase 4 — one hosted worker

Connect one hosted path, preferably the first connector that is operationally ready.

Candidates include:

- Jules (#575);
- OpenHands (#641).

Do not require both before proving one hosted path.

Exit:

- issue -> hosted worker -> candidate PR -> normalization -> verification -> evidence;
- exact provider/run/source/candidate provenance retained;
- no autonomous merge.

### Phase 5 — GitHub dispatch + durable state

Compose:

- #578 dispatch bridge;
- #597 durable ledger;
- #598 actor/role policy.

Exit:

- authorized explicit GitHub action creates exactly one run;
- duplicate event creates no duplicate provider work;
- killed coordinator can recover safely.

### Phase 6 — human decision productization

Use the existing Human Decision Record contract.

Implement:

- read-only evidence review in Control Tower;
- explicit accept/reject/escalate recording;
- immutable evidence digest binding;
- human identity binding;
- no integration side effect.

Exit:

- decision is inspectable/replayable;
- worker/verifier cannot self-record integration authority.

### Phase 7 — newcomer CLI + GitHub bootstrap

Compose #580 + #596 + #607 + #608 + #609.

Exit:

- newcomer does not edit Python;
- `idkmesh init --github` can bootstrap a fresh repo;
- preview/dispatch/status/evidence are understandable from GitHub.

### Phase 8 — release and second-project proof

Use #374 and #599 as final gates.

Exit:

- clean install;
- reproducible bounded example;
- >=10 pilot WorkUnits;
- >=2 human actors;
- restart/replay evidence;
- protected integration;
- reproducible tagged release.

## 10. Missing implementation slices that should be promoted

Do not create dozens of issues at once.

Promote the following only when dependencies are ready.

### PS-A — ProductSpineService types and lifecycle reducer

Depends on: converged C1.

Deliver:

- service result/error types;
- lifecycle states;
- pure transition validation;
- no external I/O.

### PS-B — deterministic offline vertical slice

Depends on: PS-A + candidate-normalization minimum contract.

Deliver:

- fake dispatcher;
- fake candidate;
- canonical normalization;
- existing verification;
- evidence report;
- decision pending;
- deterministic replay test.

### PS-C — run/admission idempotency integration

Depends on: #628 or converged equivalent.

Deliver:

- create/admit idempotency;
- same-key same-request reuse;
- same-key different-request conflict;
- restart-safe local test.

### PS-D — CandidateReference minimum contract

This should be implemented as the first C6 slice, not as a competing protocol.

Deliver:

- PR-backed reference;
- artifact-backed reference;
- exact source/candidate binding;
- no verification result embedded in candidate object.

### PS-E — Human Decision service

Depends on: existing Human Decision Record schema + evidence report.

Deliver:

- bind decision to report digest;
- actor identity;
- rationale;
- accept/reject/escalate;
- no merge action.

### PS-F — end-to-end CLI demo

Depends on: PS-A through PS-E.

Deliver:

- one deterministic command/path a newcomer can run locally;
- produces/prints artifact references;
- ends at human decision pending/recorded;
- no provider-specific payload knowledge.

## 11. Issues that already exist and should not be duplicated

Use these as component owners:

- #574 — C1 connector kernel;
- #575 — Jules;
- #576 — model provider;
- #577 — local worker;
- #578 — GitHub dispatch;
- #579 — candidate normalization;
- #580 — CLI/API;
- #596 — GitHub bootstrap;
- #597 — durable ledger;
- #598 — identity/roles/authority;
- #599 — second-project pilot;
- #607 — governance baseline;
- #608 — WorkUnit intake;
- #609 — GitHub evidence surfaces;
- #641 — OpenHands;
- #572 — Human Control Tower;
- #374 — reproducible release gate.

The product-spine milestone coordinates them; it does not replace them.

## 12. Review strategy

Prefer small PRs in this order:

1. pure types/state reducer;
2. fake integration fixture;
3. idempotency/persistence composition;
4. candidate normalization;
5. local worker composition;
6. hosted worker composition;
7. GitHub event bridge;
8. human decision recording;
9. CLI/UI surfaces;
10. bootstrap/release proof.

A PR mixing provider HTTP, state persistence, GitHub webhooks, UI, and verification is too large.

## 13. CI strategy

Because the repository already experiences Actions saturation:

- use focused unit tests for pure service/state logic;
- run provider live tests only in explicit/manual or bounded lanes;
- use concurrency cancellation where safe;
- do not spawn agent work when CI verification backlog is saturated;
- separate deterministic contract tests from credentialed live smokes;
- preserve exact-head evidence for security/authority changes.

## 14. Product metrics

Track outcomes, not agent activity.

Minimum cohort metrics:

- WorkUnits admitted;
- attempts started;
- duplicate dispatch prevented;
- candidates produced;
- normalization failures;
- verification supported/rejected/inconclusive/control-error counts;
- human decision latency;
- reviewer minutes;
- external/provider cost;
- Actions minutes;
- recovery events;
- escalation causes;
- worker/verifier identity overlap;
- integrated candidates;
- post-integration regression/rework.

Raw agent task count is not a success metric.

## 15. Documentation set

The productization track should retain these distinct documents:

1. **Architecture** — system boundaries and authority.
2. **Product Spine Service specification** — service operations/state semantics.
3. **Execution plan** — dependency/PR sequence (this document).
4. **Connector Control API** — connector/project-facing contracts.
5. **Bootstrap guide** — how another repo adopts IDKMesh.
6. **Security/governance guide** — GitHub permissions/secrets/protections.
7. **Operator guide** — route/doctor/run/evidence/decision commands.
8. **Release proof** — exact reproducible example and evidence.

Avoid placing all concepts into README.

## 16. Definition of done

The product spine is done when a newcomer can perform one bounded run and answer:

1. What exact task ran?
2. Who/what was allowed to dispatch it?
3. Why was this connector eligible?
4. What exact source revision was used?
5. What did the worker produce?
6. What candidate revision/artifact was normalized?
7. What independent verification occurred?
8. What evidence disagreed or failed?
9. What decision is required from a human?
10. What did the human decide?
11. Can the run be replayed/reconstructed?
12. Did any worker/verifier gain merge authority? — **No**.

## 17. Immediate recommendation

The shortest path is:

```text
converge C1
 -> freeze ProductSpineService v0.1
 -> build deterministic offline vertical slice
 -> add CandidateReference / normalization
 -> compose local worker
 -> compose one hosted worker
 -> GitHub idempotent dispatch + durable ledger
 -> human decision recording
 -> newcomer bootstrap
 -> second-project pilot
```

Do not add another provider or another planning layer before the deterministic vertical slice exists.
