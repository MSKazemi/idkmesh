# Local task claims v0.1

**Status:** executable local coordinator foundation, C10-D/E (issue 914).
**Owners:** [C10](https://github.com/MSKazemi/idkmesh/issues/598) and
[C9](https://github.com/MSKazemi/idkmesh/issues/597).

[`idkmesh/task_claims.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/task_claims.py) composes the existing
SQLite `LocalMetadataStore`, `TenantScope` and enterprise authorization kernel.
It implements the first correctness slice of the
[coordination algorithm plan](../planning/HUMAN_AGENT_COORDINATION_ALGORITHMS_2026-10-04.md).
All local coordinators must use the same database on SQLite-supported local
storage. Separate copies, unsupported network filesystems and independent
Actions runner disks do not share claims. This is not the GitHub durable ledger,
an authenticated public mutation API, or a production distributed scheduler.

## Identity and limits

The ownership key is `ScopedResourceRef(scope, "task", stable_task_id)`. The
trusted caller resolves equivalent issues to that same logical identity. There
is no semantic duplicate detector: two unrelated IDs are two tasks. Provider,
actor, transport event, attempt, source revision and WorkUnit digest never
change the ownership key.

`TaskClaimPolicy` is frozen once under existing **dispatch** authority. Exact
configuration replay is harmless; changed configuration fails with
`task_policy_conflict`. A worker cannot configure tasks, increase concurrency,
reset a lifetime budget or downgrade stored risk. Changing this policy needs a
future reviewed revision/migration operation; creating another logical ID is
not a valid retry strategy.

| Limit | Pilot default | Allowed local range |
| --- | ---: | --- |
| Concurrent implementation slots | 1 | 1–3; more than one needs a reason |
| Total admitted attempts for the task | 3 | 1–32, at least the slot count |
| Acknowledgement window | 300 seconds | 1 second–7 days |
| Liveness lease | 300 seconds | 1 second–7 days |
| Progress window | 1,800 seconds | 1 second–7 days |
| Hard ownership deadline | 86,400 seconds | 1 second–7 days |

These are bounds for this local pilot, not optimal allocation claims. Human
tasks need explicit agreed availability/check-in windows. All shorter deadlines
are clamped to the hard deadline. Policy records risk and data class; operations
use those stored values, never caller-supplied lower classifications.

## Transaction and replay

`LocalMetadataStore.transaction()` acquires `BEGIN IMMEDIATE` before reading
time, policy, authority and slot occupancy. Every mutation commits or rolls
back as one transaction. SQLite serializes separate connections/processes on
one database. Migration v3 adds task policies, slots, claims and a clock
watermark; existing connections, runs, idempotency and append-only events remain.
Code supporting only store v2 refuses the upgraded store through the existing
newer-version check; back up before upgrading if rollback is needed.

`claim(task, actor, request_id=..., binding=...)` returns `(claim, created)`.
The request identity is scoped to the logical task. Its retained digest binds
the task, normalized owner identity, exact `ClaimBinding` and task policy.
`ClaimBinding` includes WorkUnit, source revision and input snapshot digests.
Changed content under one request ID fails `request_conflict`. Fresh IDs still
share the task's concurrency and lifetime limits. Replays return the retained
claim with `created=False`, including expired/released claims; they never
renew ownership, consume another attempt, or authorize external creation.

Successful fresh admission increments only the chosen slot's epoch. A second
competition slot does not invalidate the first. Renew, release and submission
compare request identity, owner principal/issuer/type, slot epoch and effective
deadlines inside the transaction. Even another authorized worker cannot use the
owner's grant. A serialized claim snapshot is not a bearer capability.

## Four deadlines and fenced submission

`update_owner(..., operation=...)` supports:

- `acknowledge`: records consent once; it does not extend other deadlines;
- `renew`: extends liveness only, capped by the original hard deadline;
- `progress`: extends the progress window only, also capped by that deadline;
- `release`: withdraws ownership and preserves any execution reservation.

Renewal/progress require acknowledgement. At any deadline boundary, ownership
is expired and cannot be renewed or used to submit. A heartbeat does not extend
progress. A reported progress update is a worker observation, not independently
verified progress or correctness. Even repeated updates cannot extend the hard
deadline. There is no background thread: reconciliation occurs when the trusted
coordinator invokes an operation or `snapshot()`.

`record_submission(..., artifact_digest=...)` records a current owner's
candidate digest with **execute** authorization. Changed digest under the same
grant fails `submission_conflict`. Expired, released or superseded grants fail
`stale_claim`. This fences only this metadata boundary; existing local-loop,
Product Spine and provider writers are not automatically wired into it. The
method does not validate artifact bytes, run a verifier, accept a candidate,
write a Git branch or integrate. Later integration must bind ResultManifest and
independent evidence to the grant and recheck authority at its own boundary.

## Ownership and execution occupancy

`reserve_dispatch()` requires a current acknowledged owner, fresh dispatcher
**dispatch** authorization and owner **execute** authorization. It atomically
retains an operation ID and `unknown` occupancy before any external call.
Its `(claim, created)` result is an intent record only. A later executor must
also enforce dependency readiness, SCM binding, routing/capability, sandbox,
provider/CI/donor capacity and zero-project-spend policy before using it.
No provider call or secret resolution exists in this library.

After a crash/timeout following a possible provider create, a repeated reserve
returns `created=False` (also after the grant expired, for the recorded owner and
epoch only). It cannot authorize a blind second create. The trusted
adapter must reconcile, use proven provider idempotency where available, or
abstain. This local transaction cannot supply exactly-once external effects.

`reconcile_execution()` may record `running` or `terminal` against the exact
historical request and epoch, even after ownership expires. It requires fresh
dispatch authority and a secret-free evidence reference from a trusted adapter.
`terminal` means conclusively stopped/completed/not-created, **not** a timeout or
an unconfirmed cancellation request. This module trusts the coordinator's
evidence classification; it does not independently contact a provider.
Terminal evidence is immutable and cannot be resurrected by a late running
event. Reconciling an old execution does not grant it new submission authority.

A slot is unavailable while **any** claim on that slot has either active
ownership or unknown/running execution. Consequently release/expiry does not
free a potentially running process. At cap one, replacement waits for terminal
confirmation. Explicit competition can use a different configured slot; it
never makes the old execution vanish. These are task slot limits, not shared
global provider/energy/CI budgets or physical process termination.

## Clock and authority boundary

Client methods do not accept timestamps. The default coordinator clock uses
wall-clock epoch seconds plus a monotonic elapsed-time floor for running
deadlines. Observed backwards wall-clock movement fails closed. A persisted
transactional watermark catches rollback across restarts/coordinators; expired
states cannot be revived. Forward jumps may conservatively expire ownership.
This assumes a trusted system clock and durable database. It cannot detect
every bad clock after power loss or make cloned databases authoritative.
The optional injected clock is only for deterministic coordinator conformance
tests, never an untrusted worker input.

Known operational risks (v0.1, accepted and documented):

- **Clock lockout.** The watermark is one row shared by every task. If the
  system clock was ever ahead and is then corrected, every operation fails with
  `clock_rollback` until real time passes the watermark. There is no reset
  method; recovery is a deliberate manual edit of the `task_claim_clock` row by
  the database owner.
- **Attempt-budget exhaustion.** Every claim, including released and expired
  ones, counts against `max_attempts` for the task's lifetime and nothing
  resets it. Workers in scope are trusted not to burn it; a buggy retry loop
  can retire a task.
- **Release is not idempotent.** A repeated `release` raises `stale_claim`;
  clients that retry on timeout must treat that as success after a read.
- **Free-text fields.** `request_id`, `competition_reason` and
  `evidence_reference` are length- and control-character-checked only; keeping
  them secret-free is the adapter's responsibility, and readers with `read`
  see them.

Every operation freshly evaluates the existing authorization kernel after
acquiring the write lock. Revoked, expired, wrong-scope or unauthorized actors
fail closed. High-risk configuration, dispatch and submission retain the
kernel's distinct-approver requirement. The authentication producer, freshness
and actual approval reference must be supplied by a trusted coordinator; task
text/JSON is not identity. Model tier never grants authority. No HTTP or CLI
mutation endpoint is added; do not expose this adapter directly to workers.

History is bounded by the lifetime attempt limit; it is not an append-only
privileged audit stream. C9's durable events, real provider reconciliation,
GitHub ledger admission, two genuine human actors and end-to-end integration
remain separate evidence gates. No live-user, independent-review, Internet
scale or learned-model-routing result is claimed.

## Reproduce local conformance

From a repository checkout with the documented test environment:

```bash
python -m pytest -q tests/test_task_claims.py
```

The tests use synthetic normalized human/service identities and real local
SQLite transactions. They exercise 100 distinct concurrent claims, separate
coordinator processes, replay/rebase conflicts, cross-tenant isolation, role
and revocation checks, four deadlines, per-slot epochs, lifetime budgets,
unknown execution after restart, absorbing terminal evidence, rollback and
v2-to-v3 preservation. Runtime snapshots conform to
[`task-claim-v0.1.schema.json`](https://github.com/MSKazemi/idkmesh/blob/main/schemas/task-claim-v0.1.schema.json).
