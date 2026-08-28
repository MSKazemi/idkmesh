# Conversation Record — Branch Convergence and Merge Discipline

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

The project owner asked to continue the repository convergence work with explicit attention to the large number of branches and their safe integration into `main`:

> “Okay, perfect. Go ahead and also consider that there is many branches. We need to take care about the merging of these branches in a main branch. If we have already an algorithm for the merge or something like that, you can consider it.”

This turn follows the standing rule that substantive IDKMesh project work and decisions are preserved publicly in the repository.

## Repository state observed

After the preceding PR-convergence cycle, the pull-request queue had become much smaller, but the repository still exposed **77 branches including `main`** at the first branch inventory in this turn.

That branch count mixed very different states:

- source branches of PRs already merged into `main`;
- branches of closed/superseded PRs;
- evidence/acceptance branches that retain useful negative or positive runtime history;
- clean replacement branches that superseded stale stacks;
- a small number of active/current integration branches;
- branches with no obvious current PR relationship.

Therefore “merge all branches” is not a valid maintenance operation.

## Existing algorithm/policy found

The repository already had strong merge-related principles in:

- `PROJECT_RULES.md`;
- `docs/planning/REPOSITORY_IMPROVEMENT_LOOP.md`;
- `docs/planning/PR_TRIAGE_2026-08-28.md`.

Those establish:

- convergence before expansion;
- integration over proliferation;
- exact artifact/evidence before PR prose;
- dependency-order integration;
- no stale-stack merges;
- clean current-`main` replacements rather than ancestry gymnastics;
- preservation of negative evidence;
- no automation self-authorization;
- no autonomous actor proposing, approving, and merging the same protected change.

What was missing was an explicit **branch lifecycle state machine** that could distinguish “already integrated” from “still needs integration” without treating every branch as merge backlog.

## Important live convergence during this turn

The repository continued changing concurrently while the branch audit was being designed.

In particular:

- PR #112, the ACE Phase-B activation gate, merged into `main`;
- PR #113, the real canonical-node bundle -> current hardened EvaluatorPlan verifier proof, merged into `main`;
- PR #91 remained open/draft because its exact worker runtime evidence still requires the explicitly separate human/reviewer inspection before canonical integration.

This reinforces the need for branch state to be derived from current PR/evidence state rather than static branch names.

## Main safety finding

A merged PR source branch must **not** be merged again merely because its Git ancestry still appears ahead/diverged.

IDKMesh frequently uses squash-style convergence: reviewed content becomes a new mainline commit, while the old source commit graph remains different. Therefore:

```text
PR merged + source branch unchanged
    -> source branch is cleanup candidate
    -> NOT a second merge candidate
```

The audit also protects the converse case:

```text
PR merged + source branch later moved
    -> NOT automatically cleanup eligible
    -> inspect commits added after the merged PR
```

This avoids losing new branch work or accidentally merging it without review.

## Branch convergence algorithm implemented

A new maintenance branch was created from current `main`:

`maintenance/branch-convergence-audit-v0`

It adds `tools/branch_convergence_audit.py`, a standard-library read-only GitHub state auditor.

For every branch it combines:

1. current branch head SHA;
2. all same-repository PRs referencing the branch;
3. open/draft/closed/merged PR state;
4. current `main...branch` ancestry comparison;
5. evidence-sensitive branch naming/context.

It classifies branches into states including:

- `canonical`;
- `active-draft-pr`;
- `active-review-pr`;
- `open-pr-head-mismatch`;
- `ambiguous-open-prs`;
- `integrated-via-pr`;
- `post-merge-branch-moved`;
- `closed-unmerged-no-unique-commits`;
- `closed-unmerged-evidence-branch`;
- `closed-unmerged-unique-work`;
- `orphan-no-unique-commits`;
- `orphan-clean-ahead`;
- `orphan-diverged`;
- `unknown`.

The most important invariant is deliberately simple:

```text
direct_merge_allowed = false
```

for every state.

A branch identifies a line of work; a normal reviewed PR remains the integration boundary.

## Integration decision algorithm

The durable policy document `docs/planning/BRANCH_CONVERGENCE_POLICY.md` defines a conceptual conjunctive PR merge gate:

```text
MergeEligible(p) =
    p.open
    AND NOT p.draft
    AND p.head_is_expected
    AND p.not_superseded
    AND p.diff_is_bounded_and_understood
    AND p.required_checks_green
    AND p.evidence_current_for_exact_head
    AND p.required_independent_review_satisfied
    AND p.authority_invariants_satisfied
```

No activity score, branch age, branch count, or automation confidence may compensate for a failed hard gate.

For short-lived feature/convergence work, the policy recommends squash merge by default unless preserving the original commit graph is itself meaningful evidence.

## Exact-SHA evidence rule

PR #91 makes the need for frozen-branch discipline concrete.

When runtime/verification evidence names exact commit `H`:

```text
EvidenceValidForBranchHead = (current_head == H)
```

A rebase/force update performed only to reduce branch divergence would invalidate or require rerunning the exact-head evidence.

Therefore the branch audit preserves active exact-SHA/evidence-gated branches rather than automatically synchronizing them with `main`.

## Stale/superseded branch rule

Closed-unmerged branches with unique old work are not automatically merge candidates.

The safe pattern is:

```text
stale branch
 -> inspect exact unique delta
 -> identify still-useful semantics
 -> create clean branch from current main
 -> transplant only reviewed useful delta
 -> run fresh evidence/CI
 -> normal PR review
 -> preserve old PR/history
 -> cleanup old branch
```

This prevents reintroduction of obsolete schemas, duplicate protocols, weaker security checks, or older controller assumptions.

## Branch cleanup boundary

The auditor can mark a branch `cleanup_eligible`, but cleanup is deliberately separate from correctness and integration.

Before deleting a branch, durable PR/evidence/conversation provenance must be confirmed and no active workflow/document may still depend on the branch name.

The implemented workflow has **no branch deletion permission or action**.

## Read-only continuous audit

`.github/workflows/branch-convergence-audit.yml` runs:

- deterministic state-machine unit tests;
- a live read-only branch/PR/compare audit;
- Markdown summary publication to the Actions job summary;
- JSON/Markdown evidence artifact upload.

It uses:

```text
permissions:
  contents: read
  pull-requests: read
```

and pinned GitHub Action dependencies.

It has no push, merge, approve, branch-delete, issue/label, secrets, or settings authority.

The scheduled audit is intended to surface coordination debt without turning maintenance into an autonomous integration engine.

## Current external safety blocker

At the time of this turn, public GitHub branch metadata still reported:

```text
main.protected = false
required status-check enforcement = off
```

Therefore stronger autonomous merge/deletion behavior would be premature. Issue #35 remains the external repository-administration protection gate.

The offline ACE Phase-B gate that merged in #112 independently preserves the same principle: healthy capacity does not create authority, and unprotected integration remains a blocker.

## Expected branch-ecology outcome

The goal is not to minimize branch count as a vanity metric.

A healthy state is:

```text
one canonical main
+ few active review/evidence branches
+ merged branches clearly cleanup-eligible
+ stale unique work clearly extraction/replacement-only
+ preserved negative evidence
+ no ambiguity about which branch is authoritative
```

This makes repository state easier for humans and agents to navigate while preserving open-source history.

## Deliberate non-actions

This turn does not:

- bulk merge old branches;
- merge or move PR #91;
- delete branches automatically;
- create autonomous merge authority;
- infer correctness from branch age/activity;
- discard failed experiments or closed PR provenance;
- treat a squash-diverged source branch as unmerged simply because ancestry differs.

## Community Impact

Branch ambiguity is contributor friction. A newcomer should be able to distinguish an active proposal from a merged historical branch, a superseded experiment, or a frozen evidence target without private maintainer context.

The branch convergence policy and read-only audit make that distinction explicit and machine-readable while preserving normal public PR review as the path into canonical `main`.
