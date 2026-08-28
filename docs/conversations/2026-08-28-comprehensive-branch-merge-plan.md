# Conversation Record — Comprehensive Branch-to-Main Merge Plan

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

The project owner asked for a comprehensive plan and algorithm to merge the repository's many branches into `main`.

The standing project rule requires substantive project decisions and implementation work from this chat to remain public and inspectable in the repository.

## Live repository state

At the start of this continuation:

- `main` head was `523b10819abe1e88ce0207665098248ac0ed980b`;
- public GitHub branch metadata still reported `main.protected = false`;
- branch inventory contained 155 refs including `main`;
- open PRs observed were #202, draft #195, and draft #159.

The branch count continues to move quickly as experiments and PRs are created and integrated. Therefore this snapshot is evidence, not a permanent count.

## Existing foundation

The repository already had:

- `docs/planning/BRANCH_CONVERGENCE_POLICY.md`;
- `tools/branch_convergence_audit.py`;
- deterministic branch-state tests;
- a scheduled/read-only Branch Convergence Audit workflow;
- issue #127 as the branch-retirement/convergence tracker.

That foundation correctly answered:

> What lifecycle state is this branch in?

It did not yet provide a single comprehensive answer to:

> In what order should useful branch work converge to `main`, what exact operation is permitted next, and when must the merge queue be invalidated and recomputed?

## Decision

Do not create an autonomous branch merger.

Create an **execution planner** that converts branch lifecycle states into five action lanes:

1. PR integration review;
2. extract useful stale work / clean-current-main replacement;
3. evidence preservation;
4. explicit hold;
5. retirement.

The planner must always keep:

```text
direct_branch_merge_allowed = false
merge_authorized = false
```

Final integration remains a PR-level exact-head transaction after all hard gates and the required external review/integration decision.

## Core algorithm

For every planning cycle:

```text
live snapshot
 -> branch convergence audit
 -> semantic lineage reduction
 -> stale-work extraction decisions
 -> active PR dependency DAG
 -> conjunctive exact-head merge gate
 -> choose one eligible dependency-root PR
 -> external integration decision
 -> exact-head merge
 -> invalidate old plan
 -> resnapshot from new main
```

The critical rule is:

> After every merge into `main`, the old queue is stale until recomputed.

This avoids carrying CI/evidence/conflict assumptions across a changed canonical base.

## Conjunctive merge gate

The durable planning document defines:

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

Unknown is false. No priority score can compensate for a failed hard gate.

## Why stale branches are not merged wholesale

IDKMesh frequently evolves contracts and security boundaries faster than old branches are maintained. Bulk-merging a stale branch can reintroduce:

- older WorkUnit/EvaluatorPlan semantics;
- duplicate worker/evaluator/controller implementations;
- weaker workflow/security assumptions;
- stale planning/status documents;
- obsolete benchmark/calibration definitions.

The safe operation is semantic transplantation:

```text
stale unique branch
 -> inspect exact delta
 -> discard obsolete pieces
 -> rebuild useful semantics on current main
 -> fresh PR + fresh evidence
```

## Current queue interpretation

At this snapshot:

- #202 is an integration-review candidate because it is open and non-draft, but this plan does not pre-authorize its merge;
- #195 remains a hold because it is intentionally draft and crosses an active scheduled-compute activation boundary;
- #159 remains a hold because it explicitly requires a genuinely separate human/reviewer witness for exact-head worker evidence.

Branch cleanup is not permission to bypass either draft gate.

## Implementation

This continuation adds:

- `docs/planning/BRANCH_MERGE_EXECUTION_PLAN.md` — comprehensive algorithm, graph model, hard gates, transaction rules, current execution waves, metrics, failure modes;
- `tools/branch_merge_planner.py` — deterministic read-only lane planner over branch-audit JSON;
- `tests/test_branch_merge_planner.py` — fail-closed tests for active PRs, merged branches, stale unique work, evidence preservation, draft/head mismatch holds, and direct-merge rejection;
- extension of the existing Branch Convergence Audit workflow so one canonical job emits both audit and plan artifacts;
- planning index link to the execution plan.

No second autonomous workflow/controller is introduced.

## Authority boundary

The planner is decision support only. It does not:

- merge PRs;
- directly merge branches;
- approve reviews;
- delete branches;
- force-update refs;
- change branch protection/rulesets;
- set repository variables;
- create paid compute authority.

Issue #35 remains the external repository protection gate.

## Community impact

The intended result is a repository where every branch has an obvious public answer:

```text
integrate through this PR
or rebuild this useful delta
or preserve this evidence
or hold for this named blocker
or retire safely
```

That is more useful than merely reducing branch count, and it makes future human/agent collaboration less dependent on hidden maintainer context.
