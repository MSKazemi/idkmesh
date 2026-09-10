# ACE Convergent Recovery

**Status:** implemented safety/reliability contract  
**Scope:** `.github/workflows/ace-community-growth.yml`  
**Related:** issue #379

## Problem

ACE maintains a singleton public Growth Ledger and also performs bounded community-growth writes such as applying `growth-seed` and creating descendant Growth Seeds from explicitly opted-in merged pull requests.

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

Outstanding parents are ordered deterministically by merge time and pull-request number. Ordinary replacement bursts are repaired as a batch so the surviving run does not recover an older dropped event while silently omitting its own eligible event.

Automatic recovery is bounded by:

```text
MAX_AUTOMATIC_SPAWN_RECOVERY = 4
```

If more than four descendants are simultaneously missing, the workflow creates **none** of them and fails loudly with the observed backlog size. That is intentional: a large backlog can indicate stale `growth:spawn` labels or a wider controller problem, and ACE must not convert that anomaly into mass issue creation. A maintainer must inspect the labels/descendants and reduce or otherwise resolve the backlog before automatic recovery proceeds.

This gives the controller three useful properties at once: serialized ledger state, automatic convergence for ordinary pending-run replacement bursts, and fail-closed behavior for anomalously large public-write demand.

## Safety invariants

1. The concurrency group remains the single global `ace-community-growth` group.
2. `cancel-in-progress` remains `false`.
3. The workflow still never checks out or executes pull-request-controlled code.
4. Trusted-seed label recovery preserves the existing author-association trust check.
5. Descendant creation still requires both main protection and the explicit `ACE_AUTONOMOUS_ACTUATION_ENABLED=true` repository opt-in.
6. A `growth:spawn` label remains an explicit opt-in; the workflow does not infer parent eligibility from PR text.
7. Dedupe requires both the workflow-owned `growth-seed` label and the parent marker.
8. PR titles are never interpolated into generated issue content.
9. Automatic descendant recovery is capped at four issues per run; a larger backlog fails before creating any descendant issue.
10. No worker, PR author, or ACE output gains merge or repository-integration authority.

## Failure behavior

A replaced pending event is no longer a silent one-shot dependency. The next surviving serialized run recomputes missing work from current GitHub state.

For one to four missing opted-in descendants, that run repairs the complete observed backlog. For more than four, it reports an explicit failure and creates no descendant issues, preserving the repository's anti-spam boundary rather than partially draining a suspicious backlog and leaving the remainder implicit.

If actuation is disabled, descendant creation remains fail-closed. Trusted `ACE_SEED` classification may still be repaired because applying the workflow-owned classification label is separate from autonomous reproduction.

## Regression coverage

`tests/test_ace_convergent_recovery.py` pins the following properties:

- singleton writer concurrency cannot be silently parameterized per PR;
- trusted seed recovery reads repository state rather than `context.payload.issue`;
- descendant recovery reads merged, opted-in parents rather than the current PR payload;
- the existing actuation gate remains required;
- marker-plus-label dedupe remains in place;
- the four-descendant safety cap is checked before the creation loop;
- an oversized backlog is a loud fail-closed condition rather than partial recovery.

The older ACE safety/hardening tests remain responsible for immutable Action pinning, permission boundaries, trusted legacy-ledger adoption, state validation, and the no-checkout/no-PR-code-execution contract.

## Community impact

This change reduces the chance that a contributor-facing Growth Seed silently disappears because of workflow scheduling behavior, without increasing concurrency risk in the controller state or permitting an anomalous backlog to become a mass issue burst. It also makes the recovery model explicit for future maintainers: **serialize shared state, reconcile externally visible effects, and fail loudly when the requested actuation exceeds its safety envelope.**
