# Human–agent coordination: first implementation

**Date:** 2026-10-04

## Project owner's request

> can you work on those

This follows the [coordination questions and algorithm proposal](2026-10-04-human-agent-coordination-algorithms.md): avoid duplicate implementation across humans/agents, permit useful bounded competition, recover stalled workers, honor dependencies and choose appropriate model capability under resource limits.

## Assistant's implementation and findings

Current main was refreshed at `98f18868e8f7982274e6f077ca6a8d044b0bf9fb`.
The relevant C9/C10 issues/comments, authorization/store code, open PRs and
branches were inspected. The queue had no active PR or implementation branch.
Existing request idempotency and Jules controls do not provide common logical
task ownership across participants. Bounded issue 914 records this first slice.

The implementation adds a local coordinator backed by the existing SQLite store:

1. A trusted dispatcher freezes task scope, concurrency/lifetime limits, risk,
   data class and four deadlines. Workers cannot enlarge those limits.
2. Atomic admission counts humans and all agent/provider identities against the
   same task. Rebase/new request IDs do not bypass the cap. Exact replay returns
   the retained grant without renewal or a second attempt.
3. Acknowledgement, liveness, progress and hard deadlines are distinct. Current
   owner checks and monotonically increasing per-slot epochs fence stale
   updates/submissions. Heartbeats cannot extend the hard deadline.
4. Dispatch intent is retained as unknown occupancy. Release/expiry withdraws
   ownership while leaving potentially running execution charged to its slot.
   Freshly authorized terminal reconciliation permits a replacement.
5. Trusted normalized identities reuse the existing authorization kernel,
   including tenant scope, role/revocation checks and high-risk distinct approval.
   Candidate metadata is not verification, acceptance or integration authority.

## Decisions and remaining work

This is local conformance infrastructure, not a live distributed platform.
The GitHub durable ledger, authenticated identity producer, real provider
reconciliation, shared global resource reservations and two real human actors
remain evidence gates. Existing runtime/provider paths do not automatically
enforce these new claims. Dependency-ready admission and effort/model routing
are subsequent bounded slices under the existing plan/owners; no new learned
router or candidate winner selection is activated.

Defaults of one concurrent implementation and three lifetime attempts are
declared pilot choices. Explicit competition permits two, exceptionally three,
slots with a reason. Human check-in windows require agreement. No universal
optimum, model-quality calibration or live energy measurement is claimed.

## Artifacts and verification

- [Coordinator](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/task_claims.py), existing store migration and
  [regression tests](https://github.com/MSKazemi/idkmesh/blob/main/tests/test_task_claims.py).
- [Local Task Claims v0.1](../specifications/LOCAL_TASK_CLAIMS_V0_1.md) and its
  [schema](https://github.com/MSKazemi/idkmesh/blob/main/schemas/task-claim-v0.1.schema.json).
- Architecture, changelog, schema/specification/conversation indexes and sitemap
  updated in the same bounded change.

The tests exercise real SQLite connections/processes with synthetic identities,
including 100 distinct concurrent human/agent requests. They are not a
two-human acceptance pilot. Actual final checks/results are recorded on the
implementation pull request; no check is inferred from this narrative.

## Community impact and provenance

Visible task ownership and bounded retries reduce duplicated effort. Identity
does not require a permanent reputation score or compute donation. The local
adapter has a documented boundary for the next contributor and reviewer.

Prepared with ChatGPT/Codex, connected GitHub reads/publication and local Python
tests. This is owner-controlled agent work. No independent human review or real
provider execution has occurred.
