# Conversation record — ACE cohort observability continuation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Prompt / direction

The project owner asked to continue work on IDKMesh after activating the ACE (Autocatalytic Community Evolution) bootstrap cohort and scheduling a weekly cohort check.

The standing project rule remains that substantive project chats should be distilled into the public repository rather than remaining private conversational context.

## Repository state observed

At the start of this continuation:

- Bootstrap Cohort 1 consisted of Growth Seeds #24–#28.
- The seeds were still open and had no external comments/assignees visible yet.
- No pull request matching `ACE` was found.
- PR #33 had merged the WorkUnit contract work.
- PR #34 was open for the canonical local node backend.
- PR #36 was open for the proposal-first Repository Homeostasis Engine.

Because several other project tracks were active concurrently, this continuation intentionally avoided modifying those product or repository-structure branches.

## Decision

The next ACE step should be **observability, not more seed creation**.

The project needs to distinguish the following states:

```text
interest -> claim -> candidate PR -> merged candidate -> verified descendant
```

Raw activity is not community reproduction evidence.

## Implementation proposed in this branch

Branch: `ace-cohort-observer-v0`

### `.github/workflows/ace-cohort-observer.yml`

A metadata-only GitHub workflow that:

- observes Growth Seeds in Bootstrap Cohort 1;
- counts external comments separately from claims;
- recognizes `/claim`, external assignment, or a cross-referenced PR as a claim signal;
- observes PR cross-references through GitHub timeline metadata;
- treats merged PRs as candidates rather than automatic verified descendants;
- requires the explicit `ace:verified-descendant` label before a merged candidate contributes to ACE reproduction evidence;
- reads ACE Growth Ledger #23 only for the current review-capacity signal;
- maintains a single `[ACE] Bootstrap Cohort Observatory` issue;
- reports `HOLD_COHORT_1` or `EVALUATE_COHORT_2` but never creates Cohort 2 automatically;
- never checks out or executes pull-request-controlled code.

### `docs/community/ACE_COHORT_OBSERVER.md`

Documents the funnel, evidence rules, temporary seed reproduction ratio, capacity-aware expansion recommendation, anti-Goodhart rules, and security boundary.

### Pull-request template

Adds an optional lineage field such as:

```text
ACE-Seed: #24
```

This makes candidate lineage easier for contributors and reviewers to express without introducing a database.

## Metric distinction

Until issue #25 defines a general parent→descendant lineage format, the observer reports:

```text
SeedReproductionRatio = verified descendant PRs / Growth Seeds
```

This is explicitly **not** the full ACE community reproduction number:

```text
R_community(W) = verified descendant contributions / verified parent contributions
```

The distinction prevents the project from overstating evidence during the bootstrap experiment.

## Guardrail

Do not create Cohort 2 merely because the repository is active. Expansion should be evidence- and capacity-gated.
