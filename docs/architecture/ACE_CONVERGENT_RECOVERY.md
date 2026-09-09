# ACE Convergent Recovery

**Status:** implemented safety/reliability contract  
**Scope:** `.github/workflows/ace-community-growth.yml`  
**Related:** issue #379

## Problem

ACE maintains a singleton public Growth Ledger and also performs bounded community-growth writes such as applying `growth-seed` and creating one descendant Growth Seed from an opted-in merged pull request.

The workflow intentionally uses one global GitHub Actions concurrency group with:

```yaml
cancel-in-progress: false
```

That serializes ledger writers and prevents a read-modify-write race on the singleton `ACE_STATE`. It does **not** guarantee that every queued run will execute: GitHub can replace an older pending run when another run enters the same concurrency group.

Issue #379 measured this pending-run cancellation mechanism on the live repository. The measured cancellations had not yet caused a lost Growth Seed, so this is a **latent reliability defect**, not evidence of historical data loss.

## Why per-PR concurrency is the wrong repair

Keying the workflow per pull request would make individual PR events less likely to be dropped, but it would also permit multiple workflow instances to update the Growth Ledger concurrently.

The ledger update is intentionally a single-writer read-modify-write sequence. It does not use optimistic concurrency, ETags, or a transactional store. Parallelizing that path could therefore replace one latent dropped-event risk with an actual lost-update race in controller state.

The global group is therefore part of the state-consistency contract and remains unchanged.

## Recovery rule

Correctness-critical ACE work must be **convergent**:

> A surviving run reconstructs outstanding work from current repository state instead of assuming that the event which first exposed that work was executed.

The workflow now performs two reconciliations.

### 1. Trusted `ACE_SEED` label reconciliation

Every surviving run scans repository issues and finds issue records that:

- are not pull requests;
- contain an `<!-- ACE_SEED ... -->` marker;
- were authored with repository-trusted association (`OWNER`, `MEMBER`, or `COLLABORATOR`);
- do not already carry `growth-seed`.

Those issues receive `growth-seed` idempotently. The marker remains **data, not authorization**: an untrusted author cannot create authority merely by copying marker text.

This means an `issues: opened` run may be dropped without permanently hiding a trusted seed from the label-based cohort observer.

### 2. `growth:spawn` descendant reconciliation

When the existing two-part actuation gate is enabled, each surviving run examines merged pull requests carrying `growth:spawn` and compares them with existing Growth Seed issues containing the canonical parent marker:

```text
spawned-from:pr-N
```

A parent is outstanding only when no issue exists that has both:

- the `growth-seed` label; and
- the matching parent marker.

The workflow selects the oldest outstanding eligible parent deterministically and creates **at most one** descendant issue in a run.

That preserves the deliberately bounded public-write rate while ensuring a dropped merged-PR event is recoverable by the next surviving serialized run.

## Safety invariants

1. The concurrency group remains the single global `ace-community-growth` group.
2. `cancel-in-progress` remains `false`.
3. The workflow still never checks out or executes pull-request-controlled code.
4. Trusted-seed label recovery preserves the existing author-association trust check.
5. Descendant creation still requires both main protection and the explicit `ACE_AUTONOMOUS_ACTUATION_ENABLED=true` repository opt-in.
6. A `growth:spawn` label remains an explicit opt-in; the workflow does not infer parent eligibility from PR text.
7. Dedupe requires both the workflow-owned `growth-seed` label and the parent marker.
8. PR titles are never interpolated into generated issue content.
9. A single run creates at most one missing descendant Growth Seed.
10. No worker, PR author, or ACE output gains merge or repository-integration authority.

## Failure behavior

If several eligible parent events are replaced while pending, the serialized reconciler drains at most one missing descendant per later run. This favors bounded public writes over burst recovery. Because the newest event that displaced a pending run itself remains queued to run, the mechanism has a natural recovery opportunity without introducing parallel ledger writers.

If actuation is disabled, descendant creation remains fail-closed. Trusted `ACE_SEED` classification may still be repaired because applying the workflow-owned classification label is separate from autonomous reproduction.

## Regression coverage

`tests/test_ace_convergent_recovery.py` pins the following properties:

- singleton writer concurrency cannot be silently parameterized per PR;
- trusted seed recovery reads repository state rather than `context.payload.issue`;
- descendant recovery reads merged, opted-in parents rather than the current PR payload;
- the existing actuation gate remains required;
- marker-plus-label dedupe remains in place;
- no loop can create multiple descendant issues in one run.

The older ACE safety/hardening tests remain responsible for immutable Action pinning, permission boundaries, trusted legacy-ledger adoption, state validation, and the no-checkout/no-PR-code-execution contract.

## Community impact

This change reduces the chance that a contributor-facing Growth Seed silently disappears because of workflow scheduling behavior, without increasing concurrency risk in the controller state. It also makes the recovery model explicit for future maintainers: **serialize shared state, reconcile externally visible effects.**
