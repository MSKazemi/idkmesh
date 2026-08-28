# Branch Convergence and Merge Discipline

**Status:** working maintainer policy  
**Date:** 2026-08-28  
**Scope:** lifecycle of non-`main` branches and their integration into canonical `main`

IDKMesh has accumulated many branches while the repository has been evolving quickly. A branch name is useful evidence of an attempted line of work, but **the existence of a branch is not a reason to merge it**.

The canonical integration unit is a reviewed pull request with current evidence, not an arbitrary Git ref.

This policy extends the repository's existing **convergence before expansion** and PR-triage rules to branch lifecycle management.

## 1. Core invariant

```text
branch != accepted change
commit != verified improvement
PR merged != source branch should be merged again
```

A branch may contain:

- already-integrated work;
- a currently active proposal;
- an exact-SHA evidence target;
- obsolete/superseded history;
- useful but stale unique work;
- abandoned or orphaned commits.

Those states require different actions. Bulk-merging old branches into `main` would combine incompatible histories and can resurrect code that the project deliberately superseded.

## 2. Integration boundary

Substantive integration should normally follow:

```text
branch
 -> pull request
 -> exact diff / changed-file review
 -> current-head checks and evidence
 -> required independent/human review
 -> integration decision
 -> main
 -> source-branch cleanup after provenance is durable
```

**Direct branch merge is not part of the branch-convergence algorithm.**

The read-only auditor in `tools/branch_convergence_audit.py` therefore sets:

```text
direct_merge_allowed = false
```

for every branch state.

## 3. Branch state machine

For every branch `b`, inspect:

- all same-repository PRs whose head is `b`;
- whether any PR is open, draft, merged, or closed-unmerged;
- `main...b` ancestry comparison (`ahead_by`, `behind_by`, compare status);
- whether the branch is an evidence/acceptance branch whose exact SHA appears in durable evidence.

Then classify it.

### `canonical`

`b == main`.

Action: keep. It is never treated as an integration source.

### `active-draft-pr`

Exactly one open PR exists and it is draft.

Action: preserve the branch. Satisfy the PR's explicit blockers before merge review.

If evidence is bound to an exact branch SHA, **moving the head invalidates or at least requires refreshing that evidence**.

Current example: canonical node PR #91 remains an exact-SHA evidence-gated draft until the required separate human/reviewer inspection is complete.

### `active-review-pr`

Exactly one open, non-draft PR exists.

Action: use the PR merge gate. Do not merge the branch ref directly.

### `ambiguous-open-prs`

More than one open PR references the same branch.

Action: fail closed. Select one canonical PR or split the work before integration.

### `integrated-via-pr`

At least one PR from the branch has already merged.

Action: **never merge that branch again**. It becomes cleanup-eligible once all needed provenance/evidence references are durable.

This rule deliberately takes precedence over raw commit ancestry. A squash merge creates a new commit on `main`, so the original source branch may still appear `ahead` or `diverged` even though its reviewed content has already been integrated.

### `closed-unmerged-no-unique-commits`

The branch has only closed-unmerged PR history and is not ahead of `main`.

Action: cleanup-eligible. The closed PR remains the public historical record.

### `closed-unmerged-evidence-branch`

A closed-unmerged acceptance/reference branch still has unique commits.

Action: inspect durable evidence references before cleanup. Preserve useful evidence or extract the still-relevant artifact onto a clean current-`main` branch. Do **not** bulk merge the old branch.

Negative runtime/experiment evidence is a project asset even when the branch is not integrated.

### `closed-unmerged-unique-work`

A closed-unmerged ordinary branch still has unique commits.

Action:

```text
review unique delta
 -> determine whether it is still useful
 -> transplant only useful current semantics onto current main
 -> open a clean PR
```

or delete/retire it as superseded.

Do not merge stale ancestry merely to preserve one useful idea.

### `orphan-no-unique-commits`

No PR exists and the branch has zero commits ahead of `main`.

Action: cleanup-eligible after confirming no external workflow or documentation depends on the branch name.

### `orphan-clean-ahead`

No PR exists and the branch is strictly ahead of `main` with no behind commits.

Action: inspect context/ownership and open a normal PR. The auditor still does not authorize direct merging.

### `orphan-diverged`

No PR exists and the branch has both unique commits and stale ancestry.

Action: create a clean branch from current `main` and transplant only the reviewed unique delta. This is the same convergence pattern already used successfully for stale IDKMesh PR stacks.

### `unknown`

Insufficient or inconsistent evidence.

Action: hold. Do not merge or delete until manually classified.

## 4. Merge eligibility algorithm

Branch classification determines *where work belongs*. Pull-request evidence determines *whether it may integrate*.

For a PR `p`, define the conceptual gate:

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

No weighted score can override a failed conjunctive gate.

For security/runtime/evidence-sensitive work, `evidence_current_for_exact_head` is especially important:

```text
head moved -> old exact-SHA evidence is not carried forward automatically
```

For the bootstrap project, a green workflow is evidence but is not independent approval by itself.

## 5. Merge method

Default for short-lived feature, fix, research, documentation, and convergence PRs:

```text
squash merge
```

Rationale:

- keeps canonical history compact while many experimental branches are created;
- makes one reviewed PR correspond to one mainline state transition;
- reduces stale-stack ancestry pressure;
- allows source branches to be deleted after integration without losing the reviewed PR discussion.

Use a merge commit or rebase only when preserving the original commit graph is itself useful evidence or materially improves maintainability. The merge method is an integration decision, not something the branch auditor chooses automatically.

Because squash merging intentionally breaks direct ancestry identity, branch cleanup must use **merged PR state**, not only `git merge-base` ancestry, to decide that a branch is integrated.

## 6. Evidence/frozen branch rule

Acceptance and evidence branches require special handling.

If an issue, PR, workflow, evidence bundle, or verification result names exact branch head `H`, then:

```text
EvidenceValidForBranchHead = (current_head == H)
```

Changing the branch may invalidate the evidence. Therefore:

- do not rebase or force-update a frozen evidence branch just to make it look current;
- if a correction is required, create a new exact head and rerun the relevant evidence gate;
- retain failed old runs as negative evidence;
- only clean the old branch after its important evidence/provenance is durable elsewhere.

## 7. Superseded branches

A superseded branch is not a backlog item to merge later.

The safe pattern is:

```text
stale branch with useful idea
 -> identify exact useful delta
 -> current-main replacement branch
 -> fresh CI/evidence
 -> review/merge replacement
 -> preserve old PR discussion
 -> cleanup old branch
```

This prevents accidental rollback of newer safety, schema, verification, or governance changes.

## 8. Cleanup eligibility is not deletion authority

The audit may report:

```text
cleanup_eligible = true
```

This means the branch no longer needs integration. It does **not** mean an autonomous tool has permission to delete it.

Before deletion confirm:

1. any PR discussion is durable;
2. required conversation/project-memory records are on `main`;
3. frozen evidence does not rely on the branch remaining addressable by name;
4. no active workflow or documentation requires the branch ref;
5. no open PR uses the branch;
6. no unique useful work remains unextracted.

The current audit workflow is intentionally read-only and has no branch deletion capability.

## 9. Current protection boundary

At the time this policy was introduced, public GitHub metadata still reported:

```text
main.protected = false
```

Therefore branch convergence must not become an autonomous merge/deletion system. Issue #35 remains the external repository-admin protection gate.

Even after protection is configured, the project invariant remains:

> No autonomous actor may propose, approve, and merge the same protected change by itself.

## 10. Read-only audit command

With a read-only GitHub token:

```bash
python tools/branch_convergence_audit.py \
  --repo MSKazemi/idkmesh \
  --output-json /tmp/idkmesh-branches.json \
  --output-md /tmp/idkmesh-branches.md
```

The report is a decision-support surface. It can identify cleanup candidates and branches requiring extraction/review, but it performs no mutation.

## 11. Healthy branch ecology

A healthy IDKMesh repository should tend toward:

- `main` as the one canonical integrated state;
- a small number of active, reviewable short-lived branches;
- explicit frozen evidence branches only while their evidence gate is active;
- merged branches cleaned after durable provenance;
- superseded branches retired rather than repeatedly rebased;
- unique stale ideas reintroduced as clean current-main deltas;
- branch count treated as coordination state, never as project success.

The objective is not “few branches” by itself. The objective is **low ambiguity about which work is canonical, active, evidenced, superseded, or safe to clean up**.

## Community Impact

A clear branch lifecycle lowers maintainer and contributor navigation cost. New contributors should not have to guess whether an old branch is unfinished, already merged, rejected, or still authoritative. Keeping integration behind normal PR review also makes it easier for future reviewers and maintainers to participate without inheriting private repository history.
