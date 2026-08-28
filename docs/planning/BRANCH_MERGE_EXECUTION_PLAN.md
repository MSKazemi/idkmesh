# Branch-to-Main Merge Execution Plan

**Status:** proposed canonical execution plan  
**Date:** 2026-08-28  
**Scope:** comprehensive algorithm for converging the repository's branch population into one trustworthy canonical `main`

This document operationalizes `BRANCH_CONVERGENCE_POLICY.md`.

The repository has accumulated a large branch population through fast parallel experimentation. The goal is **not** to merge every branch. The goal is to make every branch reach one explicit terminal state:

```text
integrated into main
OR superseded/retired
OR preserved as evidence
OR actively blocked with a named gate
```

The plan therefore treats branch convergence as a controlled graph-reduction problem, not a bulk Git operation.

---

## 1. Current snapshot

At the start of this plan:

- canonical `main`: `523b10819abe1e88ce0207665098248ac0ed980b`;
- observed branch refs: **155** including `main`;
- public GitHub metadata still reports `main.protected = false`;
- current open PRs observed:
  - **#202** — review-ready ProjectManifest / DomainPack contract work;
  - **#195** — draft active-compute pulse, intentionally gated before activation;
  - **#159** — draft canonical node replacement, blocked on genuinely separate human review.

This is a point-in-time snapshot, not an invariant. IDKMesh changes quickly, so every irreversible action must re-read live repository state.

---

## 2. Objective

Define the non-default branch set at time `t` as `B_t`.

For every branch `b in B_t`, assign exactly one lifecycle decision:

```text
D(b) in {
  INTEGRATE_VIA_PR,
  PREPARE_CURRENT_MAIN_REPLACEMENT,
  PRESERVE_EVIDENCE,
  HOLD,
  RETIRE
}
```

The optimization target is not minimum branch count by itself.

A better repository objective is:

```text
ConvergenceQuality =
    canonical useful work
  + preserved falsification/evidence
  + explicit blocker visibility
  - duplicate responsibility
  - stale ancestry risk
  - reviewer/conflict debt
  - branch ambiguity
```

A branch disappears only after its useful or evidentiary information has a durable home.

---

## 3. Non-negotiable invariants

### 3.1 Branch existence is not merge authority

```text
branch exists != branch should merge
branch ahead != branch should merge
branch diverged != branch should merge
CI green != independent approval
worker/verifier success != integration decision
```

### 3.2 The PR is the integration transaction

Substantive canonical integration must flow through:

```text
branch
 -> pull request
 -> exact-head diff/evidence/review
 -> explicit integration decision
 -> main
```

No stale branch is directly merged merely to reduce branch count.

### 3.3 A merged source branch never gets merged again

Squash merging means the source ref may remain `ahead` or `diverged` even though its reviewed content is already canonical.

Therefore:

```text
current branch head == merged PR head
    -> RETIRE lane
    -> NEVER second merge
```

### 3.4 Exact-SHA evidence is binding

If evidence names branch head `H`:

```text
EvidenceValid = (current_head == H)
```

Rebase, force-update, merge-from-main, or any other head movement requires evidence to be deliberately rebound/re-executed as appropriate.

### 3.5 No hard gate is compensable

A priority score can order **eligible** work. It cannot override a missing safety/review/evidence gate.

### 3.6 Recompute after every merge

Any merge changes the canonical base and can change:

- conflicts;
- dependency satisfaction;
- stale-branch semantics;
- evidence freshness;
- whether another branch is now redundant.

Therefore merge planning is transactional rather than batched.

---

## 4. System model

The merge system uses three related graphs.

### 4.1 Branch lifecycle graph

Nodes: Git refs / branches.

Edges: PR history and replacement/supersession relationships.

Purpose: answer whether a branch is active, integrated, stale, evidentiary, or cleanup-ready.

### 4.2 Integration dependency DAG

Nodes: active/replacement PRs.

Directed edge:

```text
A -> B
```

means B must not integrate before A.

Dependencies may come from:

1. B's base branch is A's branch;
2. an explicit PR dependency declaration/reference;
3. B consumes a contract/schema/API introduced by A;
4. B's evidence was produced against A's exact artifact;
5. a maintainer explicitly records the ordering dependency.

No dependency edge should be inferred solely from similar prose or branch names.

### 4.3 Responsibility / semantic lineage graph

Nodes: branches/PRs that attempt the same project responsibility.

Examples:

- canonical worker lineage;
- evaluator lineage;
- ACE controller lineage;
- benchmark cohort lineage;
- IDKGraph warning lineage;
- interoperability bindings.

Purpose: prevent multiple obsolete implementations from all eventually reaching `main`.

Rule:

```text
one canonical implementation per responsibility
```

When a newer reviewed lineage supersedes an older one, the older branch moves to `RETIRE` or `PRESERVE_EVIDENCE`, not to the merge queue.

---

## 5. Branch classification -> permitted operation

The existing `branch_convergence_audit.py` remains the source classifier.

The merge planner maps its states into five action lanes.

| Audit state | Merge-plan lane | Allowed next operation |
| --- | --- | --- |
| `active-review-pr` | PR integration review | evaluate hard PR gate |
| `active-draft-pr` | hold | satisfy explicit blocker |
| `open-pr-head-mismatch` | hold | refresh exact-head metadata/evidence |
| `ambiguous-open-prs` | hold | choose/split canonical PR |
| `integrated-via-pr` | retirement | never merge again |
| `post-merge-branch-moved` | extract or retire | inspect only post-merge delta |
| `closed-unmerged-no-unique-commits` | retirement | retire after reference check |
| `closed-unmerged-evidence-branch` | evidence preservation | preserve evidence, then retire/extract |
| `closed-unmerged-unique-work` | extract or retire | transplant useful delta to current main |
| `orphan-no-unique-commits` | retirement | retire after dependency/reference check |
| `orphan-clean-ahead` | extract or retire | normal PR or clean replacement |
| `orphan-diverged` | extract or retire | clean current-main replacement |
| `unknown` | hold | manual classification |

For every row:

```text
direct_branch_merge_allowed = false
```

---

## 6. Comprehensive convergence algorithm

### Step 0 — snapshot and freeze the decision input

Read:

- current `main` SHA;
- all branches and exact heads;
- all same-repository PR states/heads/bases;
- branch protection/ruleset status;
- exact CI/evidence/review state for open PRs;
- latest branch-convergence audit.

Record a snapshot identifier:

```text
S = SHA256(main_sha || sorted(branch_head_shas) || open_pr_heads)
```

The exact formula may be implemented later; the conceptual requirement is that merge decisions are bound to one live snapshot.

### Step 1 — classify every branch

Run the existing branch convergence auditor.

Every non-main branch must receive one known state. Unknown/inconsistent states fail closed.

### Step 2 — remove branches that are not integration candidates

Immediately exclude from the merge queue:

- exact merged-PR source heads;
- branches with no unique commits;
- superseded implementations;
- closed evidence-only harnesses;
- frozen negative/calibration experiments;
- drafts with unresolved blockers;
- branches whose PR head does not match the live ref.

These move to `RETIRE`, `PRESERVE_EVIDENCE`, or `HOLD`.

### Step 3 — resolve semantic duplication

For every responsibility with more than one surviving branch:

1. identify the newest accepted/canonical contract;
2. compare each branch's unique semantic delta to current `main`;
3. mark already represented semantics as superseded;
4. preserve unique useful ideas separately;
5. select at most one current integration lineage.

Never solve duplication by merging competing implementations together unless the PR explicitly reconciles them and reviewers understand that combined design.

### Step 4 — convert stale unique work into current-main deltas

For `closed-unmerged-unique-work`, `orphan-diverged`, and relevant `post-merge-branch-moved` branches:

```text
old branch
 -> inspect exact unique commits/files/hunks
 -> compare with current canonical contracts
 -> discard obsolete parts
 -> preserve still-useful semantics
 -> new clean branch from current main
 -> bounded PR
 -> fresh CI/evidence
```

This is semantic transplantation, not ancestry preservation.

Use cherry-pick only when the commit is demonstrably self-contained and compatible with current contracts. Otherwise reconstruct the minimal delta.

### Step 5 — build the active integration DAG

Let `P` be all open, non-draft, non-superseded PRs plus replacement PRs created in Step 4.

Construct dependency DAG `G=(P,E)`.

A PR with nonzero indegree cannot be first in the merge queue.

If cycles exist:

```text
cycle -> HOLD
```

Then either:

- combine genuinely inseparable changes into one bounded PR; or
- break the contract/API dependency so the cycle becomes acyclic.

### Step 6 — evaluate the hard merge gate

For candidate PR `p`:

```text
MergeEligible(p) =
    p.open
    AND NOT p.draft
    AND p.head_is_exactly_expected
    AND p.not_superseded
    AND p.diff_is_bounded_and_understood
    AND p.dependencies_are_integrated_or_explicitly_independent
    AND p.required_checks_are_green_for_exact_head
    AND p.evidence_is_current_for_exact_head
    AND p.required_independent_review_is_satisfied
    AND p.authority_invariants_are_satisfied
    AND p.base_was_revalidated_after_previous_merge
```

If any term is false or unknown:

```text
MergeEligible(p) = false
```

Unknown is not optimistic success.

### Step 7 — classify integration risk

Risk class influences review/evidence requirements, not whether safety can be bypassed.

Suggested classes:

#### R0 — documentation / static research record

Examples:

- prose-only docs;
- conversation/evidence records;
- static landing pages with no executable script.

Minimum: bounded diff, current links/facts, green applicable checks, normal integration decision.

#### R1 — ordinary non-privileged code/tests

Examples:

- deterministic utilities;
- pure schemas/validators without execution authority;
- research simulation code.

Require code/test review and current exact-head CI.

#### R2 — execution / contracts / verification

Examples:

- worker runtime;
- evaluator/verifier;
- orchestration;
- WorkUnit/Result/Evidence contracts;
- external adapters.

Require stronger exact-head evidence and independent review according to the affected contract.

#### R3 — privileged automation / governance / security

Examples:

- `pull_request_target`;
- write-capable Actions;
- self-evolution/ACE actuation;
- branch protection/integration controls;
- code that can create/modify PRs/issues/branches or authorization state.

Require explicit threat review, least privilege, fail-closed behavior, pinned dependencies where relevant, and independent integration control.

### Step 8 — order eligible PRs

Only after Step 6 yields `true` may priority be considered.

Use lexicographic priority rather than a compensating weighted sum:

```text
Priority(p) = lexicographic(
    critical_path_class,
    dependency_unlock_count,
    conflict/staleness_reduction,
    cleanup_gain,
    negative_review_cost
)
```

Recommended criticality order:

```text
P0 security / integration safety blockers
P1 canonical product critical path
P2 branch/contract convergence and dependency unlocks
P3 community/growth infrastructure
P4 research/docs leaves
```

Within the same class prefer the PR that:

1. unlocks more downstream work;
2. reduces more duplicate/stale responsibility;
3. has a smaller bounded review surface;
4. is less likely to become stale if delayed.

Do not prioritize merely because a branch is old.

### Step 9 — exact-head merge transaction

Immediately before merge:

1. re-fetch PR state;
2. re-fetch exact head SHA;
3. verify it equals the reviewed/evidenced SHA;
4. verify the PR is still non-draft;
5. verify dependencies are now canonical;
6. verify no unresolved required review thread remains;
7. verify latest required checks/evidence are still valid;
8. verify no new mainline change invalidated assumptions;
9. execute the merge with `expected_head_sha`;
10. prefer squash merge for ordinary short-lived branches unless commit-graph preservation is itself meaningful evidence.

If the expected head changed, abort.

### Step 10 — commit the new canonical state and invalidate the old plan

After merge `p` creates new `main=M'`:

```text
old plan = invalid
```

Rerun from Step 0.

Never continue merging from a queue computed against the old `main` without revalidation.

### Step 11 — retire source branches

After integration, a source branch becomes cleanup eligible only when:

- its PR/evidence/provenance is durable;
- the current branch head still matches the merged PR head, or post-merge extra commits were separately classified;
- no active workflow/document requires the ref name;
- no exact-SHA evidence requires the branch ref itself;
- no useful unique work remains.

Physical deletion is a repository-administration operation separate from merge correctness.

### Step 12 — prevent recurrence

Repository owner should enable:

```text
Settings -> General -> Pull Requests -> Automatically delete head branches
```

after confirming this matches desired evidence retention practice.

More importantly, protect `main` under issue #35 before increasing autonomous integration authority.

---

## 7. Transactional planner pseudocode

```text
repeat:
    S <- live repository snapshot
    A <- branch_convergence_audit(S)
    P <- build_branch_merge_plan(A)

    classify every branch into:
        integration-review
        extract-or-retire
        evidence-preservation
        hold
        retirement

    for every stale unique branch:
        if useful semantics remain:
            create clean current-main replacement PR
        else:
            mark retire

    G <- dependency DAG of active integration PRs

    Ready <- {
        p in G
        where indegree(p) == 0
        and MergeEligible(p) == true
    }

    if Ready is empty:
        publish blockers/preparation/retirement plan
        stop

    p <- lexicographically highest-priority member of Ready

    external reviewer/maintainer makes integration decision

    if accepted:
        merge p using expected_head_sha
        preserve merge/evidence record
        continue  # MUST resnapshot; old queue is invalid
    else:
        record hold/rejection/supersession evidence
        continue or stop based on new state
```

The planner itself never supplies the `external reviewer/maintainer makes integration decision` step.

---

## 8. Execution waves for the current repository

The exact wave membership is recomputed continuously, but the present structure is:

### Wave 0 — integration safety

- Keep #35 branch protection as the external P0 boundary.
- Do not authorize autonomous branch merging while `main` remains publicly unprotected.
- Enable automatic deletion of merged head branches as an owner/admin hygiene measure when appropriate.

### Wave 1 — current open PRs

#### #202 — ProjectManifest / DomainPack

State observed: open, non-draft.

Action:

```text
PR integration-review candidate
```

It should be evaluated against exact-head CI, diff scope, dependency compatibility, and normal review requirements. This document does not pre-authorize its merge.

#### #195 — Active Compute Pulse

State observed: draft.

Action:

```text
HOLD
```

Its own activation/security review must complete before it enters integration review. Merge must not be used to bypass the explicit opt-in/protected-main boundary.

#### #159 — canonical node replacement

State observed: draft.

Action:

```text
HOLD
```

Its exact-head runtime evidence exists, but a genuinely separate human/reviewer witness is still an explicit required gate. Branch hygiene cannot substitute for that witness.

### Wave 2 — stale unique/extraction backlog

Use the planner/auditor output to inspect `extract-or-retire` branches by semantic responsibility.

Priority within this wave:

1. unique work that blocks current product contracts;
2. unique work that reduces duplicate responsibility;
3. unique work with high probability of becoming incompatible if delayed;
4. low-risk documentation/research residue.

Every rescued item becomes a new current-main PR. The old branch itself is not merged.

### Wave 3 — evidence branches

Preserve durable receipts, negative evidence, run IDs, exact SHAs, and conversation records. Then retire refs whose names are no longer required.

### Wave 4 — cleanup-safe refs

Delete exact revalidated:

- merged-PR source heads;
- no-unique-commit branches;
- explicitly superseded branches after provenance is durable.

Then rerun the audit and measure reduced ambiguity.

---

## 9. Metrics

### 9.1 Branch ambiguity

```text
BranchAmbiguity =
    unresolved_unique_stale
  + unknown
  + ambiguous_open_prs
  + post_merge_moved_unclassified
```

Target: trend toward zero.

### 9.2 Canonical integration yield

```text
IntegrationYield =
  verified durable changes integrated
  -----------------------------------
  reviewer effort + conflict debt + rework
```

High merge count alone is not success.

### 9.3 Cleanup ratio

```text
CleanupRatio = retired_cleanup_safe_refs / cleanup_safe_refs_identified
```

This measures hygiene, not project value.

### 9.4 Evidence retention quality

```text
EvidenceRetention =
  retired evidence refs with durable evidence elsewhere
  ----------------------------------------------------
  retired evidence refs
```

Target: 1.0.

### 9.5 Stale unique load

One simple diagnostic is:

```text
StaleUniqueLoad = sum(risk_weight(b) * max(1, behind_by(b)))
```

for stale branches with unique work.

This is prioritization evidence only; it cannot override merge gates.

---

## 10. Failure modes this algorithm prevents

### Bulk branch merge

Failure: obsolete schemas/runtime/security assumptions re-enter `main`.

Prevention: stale refs must be semantically extracted onto current `main`.

### Double integration after squash merge

Failure: already-reviewed work is merged again because ancestry still appears divergent.

Prevention: merged PR head identity outranks ancestry for cleanup classification.

### Evidence laundering across head movement

Failure: old runtime/verification evidence is cited for changed code.

Prevention: exact-head evidence binding.

### Self-authorized automation

Failure: the system that proposes a change also interprets its own green run as approval and merges itself.

Prevention: planner always emits `merge_authorized=false`; independent integration decision remains external.

### Review-queue Goodharting

Failure: merge/close count is optimized instead of useful canonical state.

Prevention: hard gates plus IntegrationYield/ambiguity metrics.

### Branch-count Goodharting

Failure: evidence and useful work are deleted simply to make the branch number smaller.

Prevention: preserve/extract before retire.

### Stale batch queue

Failure: five PRs are approved against one `main`; the first merge invalidates assumptions for the next four.

Prevention: recompute after every merge.

---

## 11. Machine-readable implementation

`tools/branch_merge_planner.py` consumes the JSON produced by `tools/branch_convergence_audit.py` and emits:

- integration-review queue;
- stale-work preparation/extraction queue;
- evidence-preservation queue;
- explicit holds;
- retirement candidates.

It deliberately cannot emit final merge authorization.

The existing Branch Convergence Audit workflow runs both tools so there is one canonical read-only maintenance surface rather than parallel branch-management workflows.

---

## 12. Definition of done

This branch-convergence program is successful when:

- every branch has an explicit lifecycle decision;
- `main` is the only canonical code state;
- active integration branches are few and bounded;
- no already-merged branch is merged twice;
- stale unique work is either cleanly rescued or explicitly retired;
- negative/evidence branches retain durable provenance before retirement;
- draft/frozen branches remain untouched until their actual gate is satisfied;
- the merge plan is recomputed after each integration;
- repository owner enables safer branch lifecycle settings and protects `main` before stronger autonomous integration behavior;
- branch count becomes a side effect of clarity, not the objective itself.

## Community impact

A comprehensive branch-to-main algorithm makes the repository legible to human contributors and future agents. A newcomer should be able to answer, from public evidence, whether a branch is canonical, actively reviewable, blocked, evidentiary, superseded, awaiting extraction, or safe to retire. That lowers coordination cost without weakening the verification-first boundary.
