# Human–agent coordination: executor admission gate

**Date:** 2026-10-04

## Project owner's request and context

> continue

This continues the [coordination questions/proposal](2026-10-04-human-agent-coordination-algorithms.md),
the [first ownership/recovery implementation](2026-10-04-coordination-implementation.md)
(Local Task Claims, PR 916) and the
[dependency/effort preflight](2026-10-04-dependency-effort-implementation.md)
(PR 918). The preflight record named its own gap: a real executor must
revalidate exact readiness/authority and acquire claims and resource
reservations atomically before external work, then recheck inputs at canonical
submission/integration, because a report alone leaves a check/use race.

## Assistant's implementation

Bounded issue 921 records this slice: a local executor admission gate
composing the preflight's readiness projection with Local Task Claims. The
gate derives the execution binding (WorkUnit digest, source revision, input
digest) from the frozen graph and the ready-state inputs inside the same
operation that acquires the claim, so a caller cannot bind a claim to an input
snapshot that was never ready. The logical task identity stays a scoped task
reference separate from that execution binding, matching the plan's rule that
task identity survives a rebase and duplicates resolve through an explicit
alias decision.

Blocked, already integrated, unknown, scope-mismatched and unconfigured tasks
are refused before any claim record exists. Before the external dispatch
intent is retained and again at canonical candidate submission, the exact
admission-time input snapshot is revalidated: changed upstream inputs fail
`inputs_changed` with nothing written, and a claim bound to another
WorkUnit/source revision fails `binding_mismatch`. Exact admission and
dispatch-intent replays return the retained records without renewal or a
second attempt; stale epochs, non-owners and unknown requests keep failing
through the existing fencing. Owner lifecycle and trusted execution
reconciliation stay on the claims layer; the gate adds no clock or occupancy
semantics.

Each phase emits a versioned report binding scope, graph digest, observation
digest, WorkUnit binding, input digest and the embedded claim snapshot, with
an all-false authority ceiling: the report is metadata, the durable claim is
the admission, and neither grants verification, acceptance or merge.

## Mathematical and reproducible checks

Admission is one local lock plus one SQLite claim transaction; readiness is
recomputed from the current snapshot in `O(V+E)` graph work plus hashing the
input pins, so no counter replay corruption is possible. Observations applied
through the gate are serialized with admissions in one process; direct
projection mutation remains fail-closed at both recheck points and a fresh
grant caught mid-mutation is withdrawn rather than left holding the slot.

The conformance suite (19 tests) covers ready/blocked/integrated refusals, the
derived binding, replay without renewal, upstream change before dispatch (no
intent written) and before submission (no digest written), unrelated branches
remaining current, binding mismatch, retained-intent replay, fencing
pass-through, one admitted grant among 20 concurrent human/agent identities,
and schema-conformant reports. The standalone stdlib demo reports
`task_not_ready` before the prerequisite integrates, then admission,
reservation and submission reports, then `inputs_changed` when the upstream
artifacts move. Actual local results: `tests/test_executor_admission.py`,
`tests/test_task_claims.py` and `tests/test_coordination_preflight.py` pass
under pytest in this session; final gate results belong to the pull request
opened from this change.

## Decisions, artifacts and remaining gates

- [Gate](../../idkmesh/executor_admission.py),
  [tests](../../tests/test_executor_admission.py),
  [demo](../../examples/coordination/admission_demo.py),
  [schema](../../schemas/executor-admission-v0.1.schema.json) and
  [specification](../specifications/EXECUTOR_ADMISSION_V0_1.md).
- This is local conformance composition, not a live distributed executor. The
  GitHub durable ledger, authenticated event/identity producers, real provider
  termination/recovery, global resource reservations, end-to-end wiring into
  the live runner/Jules/Product Spine paths, a genuine two-user pilot and
  held-out model-routing comparisons remain open evidence gates.
- Observation producers remain trusted adapters; the gate authenticates
  nothing and does not make external provider effects exactly-once.

## Community impact and provenance

One inspectable record now explains why work was admitted or refused and
exactly which inputs a candidate was bound to. Identity does not require a
permanent reputation score or donated compute.

Prepared with the coding agent using local code/tests and connected GitHub
state. No independent human review, live provider execution or real-user
acceptance evidence is represented.
