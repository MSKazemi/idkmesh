# Branch Steward Agent

**Status:** design for shadow-mode implementation  
**Date:** 2026-08-28  
**Scope:** branch lifecycle planning and PR integration decision support

IDKMesh already has a deterministic, read-only branch convergence auditor. The missing layer is not a bot that merges arbitrary branches. It is a **Branch Steward** that turns branch-state evidence into bounded, explainable next actions while preserving pull requests, verification, and independent review as the integration boundary.

## 1. Why an agent is useful

The repository can contain many simultaneous branch states:

- active PR heads;
- exact-SHA evidence branches;
- source branches whose PRs already merged;
- stale diverged branches with one useful idea;
- abandoned work with no unique commits;
- closed-unmerged negative/evidence branches;
- branches reused after their original PR merged.

Treating all of them as "things to merge" is unsafe. A smart steward should often recommend **do not merge**.

The existing `tools/branch_convergence_audit.py` remains the deterministic source of branch-state facts. The Branch Steward consumes those facts; it does not replace them.

## 2. Agent decomposition

Use four separated roles.

```text
Branch Observer
  deterministic, read-only
        |
        v
Branch Steward / Convergence Planner
  classify + prioritize + propose
        |
        +-------------------------+
        |                         |
        v                         v
Clean-Delta Builder          Retirement Queue
  optional branch/PR          exact-head cleanup proposal
  no merge authority          no implicit deletion authority
        |
        v
PR Integration Gate
  checks + review + policy + human decision
        |
        v
main
```

### Observer

Already implemented by the branch convergence auditor.

Authority: read only.

### Steward

Consumes the audit plus PR/check/evidence metadata and emits one of:

- `KEEP`
- `HOLD`
- `REVIEW_PR`
- `OPEN_PR`
- `EXTRACT_TO_CLEAN_MAIN`
- `RETIRE_AFTER_REVALIDATION`
- `PRESERVE_EVIDENCE`
- `UNKNOWN_ESCALATE`

Authority: advisory in the first phase.

### Clean-Delta Builder

For stale but useful work, creates a fresh branch from current `main` and transplants only the reviewed semantic delta.

Authority: may prepare a candidate branch/PR after a separately reviewed activation step; never approves or merges its own candidate.

### Integration Gate

Decides whether a PR may merge. This must remain logically separate from the actor that produced the change.

## 3. Deterministic branch decision algorithm

For every branch `b`, let:

- `H_b` = current branch head;
- `H_m` = current `main` head;
- `A_b` = commits ahead of `main`;
- `D_b` = commits behind `main`;
- `P_b` = same-repository PR history for the branch;
- `E_b` = whether durable evidence binds to `H_b` or the branch name;
- `S_b` = branch state emitted by the canonical auditor.

The Branch Steward first applies hard state rules:

```text
if S_b == canonical:
    KEEP

elif S_b in {active-draft-pr, active-review-pr}:
    REVIEW_PR

elif S_b == integrated-via-pr:
    RETIRE_AFTER_REVALIDATION

elif S_b in {orphan-no-unique-commits,
             closed-unmerged-no-unique-commits}:
    RETIRE_AFTER_REVALIDATION

elif S_b == orphan-clean-ahead:
    OPEN_PR

elif S_b in {orphan-diverged,
             post-merge-branch-moved,
             closed-unmerged-unique-work}:
    EXTRACT_TO_CLEAN_MAIN

elif S_b == closed-unmerged-evidence-branch:
    PRESERVE_EVIDENCE or EXTRACT_TO_CLEAN_MAIN

else:
    UNKNOWN_ESCALATE
```

No branch state maps to `DIRECT_MERGE`.

## 4. Smart prioritization is separate from merge eligibility

The steward may score **which branch to inspect next**, but a score must never override a failed safety gate.

A practical queue score is:

```text
Priority(b) =
    w_u * UniqueValue(b)
  + w_f * Freshness(b)
  + w_k * BlockerRelief(b)
  + w_c * CoordinationDebtReduced(b)
  - w_r * Risk(b)
  - w_s * Staleness(b)
  - w_d * DuplicationProbability(b)
  - w_e * EvidenceSensitivity(b)
```

Interpretation:

- `UniqueValue`: how much still-useful unique work appears to exist;
- `Freshness`: proximity to current architecture/contracts;
- `BlockerRelief`: whether convergence unblocks a P0/P1 dependency;
- `CoordinationDebtReduced`: ambiguity removed for maintainers/contributors;
- `Risk`: security, workflow, governance, evaluator, protocol, or integration risk;
- `Staleness`: how far the branch is behind current `main`;
- `DuplicationProbability`: likelihood the idea already landed elsewhere;
- `EvidenceSensitivity`: penalty for exact-SHA/frozen evidence branches.

The first implementation should keep these components explicit and inspectable. An LLM may help estimate ambiguous semantic value or duplication, but those estimates are hypotheses, not merge authority.

## 5. The merge algorithm is conjunctive, not weighted

A candidate PR `p` may be considered mergeable only when all mandatory gates are satisfied:

```text
MergeEligible(p) =
    p.open
    AND NOT p.draft
    AND p.head == expected_head
    AND p.mergeable
    AND p.not_superseded
    AND bounded_diff_understood(p)
    AND required_checks_green(p)
    AND evidence_current_for_exact_head(p)
    AND required_review_satisfied(p)
    AND no_unresolved_blocking_threads(p)
    AND authority_invariants_satisfied(p)
```

For protected/high-risk surfaces, add stronger gates such as independent review, runtime evidence, schema compatibility, security review, or benchmark/evaluator sovereignty checks.

A high priority score cannot compensate for a false term in `MergeEligible`.

## 6. Clean extraction instead of stale branch merging

For a diverged branch:

```text
old branch B
 -> inspect unique commits/files
 -> identify still-useful semantic delta U
 -> create fresh branch C from current main
 -> apply only U
 -> run current CI/evidence
 -> open normal PR from C
 -> review/integrate C
 -> retire B after provenance is durable
```

This is safer than merging `B` because old ancestry can reintroduce superseded schemas, security assumptions, workflows, or governance rules.

## 7. Evidence-aware rules

If durable evidence names exact head `H`:

```text
EvidenceValid = (current_branch_head == H)
```

Therefore the steward must not casually rebase, force-update, or reuse an evidence branch. If useful work must change, create a new head and rerun the relevant evidence.

Negative results remain evidence and should not disappear merely because a branch is not mergeable.

## 8. Retirement algorithm

A branch may enter the retirement queue only if all are true:

```text
RetireEligible(b) =
    no_open_pr_uses(b)
    AND no_unique_useful_work_remains(b)
    AND required_evidence_is_durable(b)
    AND no_workflow_depends_on_branch_name(b)
    AND exact_head_revalidated_immediately_before_action(b)
```

`cleanup_eligible=true` from the auditor is a candidate signal, not deletion authority.

## 9. Recommended execution phases

### Phase A — shadow mode now

- run after the canonical branch audit;
- emit ranked branch actions and explanations;
- update no branches;
- merge nothing;
- delete nothing;
- compare recommendations with maintainer decisions.

### Phase B — bounded proposal mode

After shadow-mode calibration:

- open or update one canonical branch-convergence ledger;
- optionally prepare a clean replacement branch/PR for one explicitly selected stale branch;
- no automatic approval or merge.

### Phase C — guarded integration assistance

Only after `main` protection and repository governance gates are actually configured:

- verify exact PR head and required checks;
- verify required independent review;
- recommend merge or hold;
- keep the final protected integration action separate from the proposing/building agent.

## 10. Current repository constraint

At the time of this design, public repository metadata still reports `main` protection disabled. Therefore IDKMesh should **not** activate an autonomous merge agent now.

The useful next capability is a Branch Steward in shadow/advisory mode, built on the existing read-only auditor and issue #127 branch-lifecycle ledger.

## 11. Success metrics

Do not optimize branch count alone.

Measure:

- ambiguous branches resolved per reviewer minute;
- stale useful deltas recovered without stale ancestry;
- duplicate/redundant merge attempts prevented;
- branches retired without losing evidence;
- PRs reaching a clear merge/hold decision;
- false-positive `extract` or `retire` recommendations;
- reviewer corrections to the steward;
- average lifetime of ordinary short-lived branches;
- fraction of active branches with one obvious canonical PR/state.

North-star branch objective:

```text
useful canonical progress
--------------------------------------------
branch ambiguity + reviewer effort + risk
```

## 12. Safety invariant

> A branch agent may observe, classify, prioritize, and prepare a candidate, but it must not become the sole proposer, verifier, approver, and merger of the same protected change.

Related: `docs/planning/BRANCH_CONVERGENCE_POLICY.md`, `tools/branch_convergence_audit.py`, issue #127, and issue #35.
