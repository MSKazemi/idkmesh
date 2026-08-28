# Repository audit and evidence-retention convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner request

Continue development, inspect the repository for bugs/inconsistencies, choose a useful next step, and execute it while keeping the work public in the repository.

## Findings and actions

### 1. Stale verifier bug tracker

Issue #82 still described stale default candidate-root paths, but current `main` already uses:

```text
examples/verifier/good/candidate-root
examples/verifier/bad/candidate-root
```

The issue was therefore stale rather than an active code defect. It was documented and closed as completed.

### 2. Stale product-tracker state

Issues #4 and #16 still contained historical worker SHA/checklist text from before the current runtime acceptance evidence. Corrective comments now record the active exact worker boundary:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Historical evidence remains visible as provenance rather than being rewritten.

### 3. Evidence-retention branch drift

PR #115 correctly proposed retaining the real-node -> independent-verifier evaluator bundle as a GitHub Actions artifact. Its branch diverged while `main` advanced.

A current-main rebuild (#119) proved the same change at exact head and produced a replayable artifact, after which #115 was closed as superseded.

### 4. Concurrent product milestone changed the next step

While this audit was running, PR #117 merged to `main` as commit:

`35f427359b3bf38419c6028ac9d24a08e68269d4`

It advanced the product beyond the earlier audit snapshot by demonstrating:

```text
one canonical WorkUnit
 -> two isolated real node attempts
 -> independent verification for each completed candidate
 -> non-selecting Evidence Report
 -> saved-run replay
 -> explicit human decision still pending
```

It also demonstrated real worker-failure isolation: one failed attempt did not erase or invalidate the verified peer.

This means “build the first real two-attempt proof” is no longer the next task; it is now evidence already integrated on `main`.

## New inconsistency exposed by #117

The repository then had asymmetric evidence retention:

- single real node -> verifier E2E: a tested artifact-retention fix existed in #119 but was not yet on `main`;
- new real two-attempt E2E: evidence was rendered into the job summary but not retained as downloadable replay bytes.

The useful next step is therefore to make evidence retention consistent across both real E2E boundaries.

## Unified fix

Branch:

`fix/replayable-e2e-evidence-unified`

Based directly on post-#117 `main`.

Both workflows now use the same pinned action:

`actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` (`v4.6.2`)

### Single-attempt evidence

After successful real-node -> verifier execution, retain:

`evaluator/results/verification/real-node-520ad2c/`

### Two-attempt evidence

After successful two-attempt orchestration/report execution, retain:

`evaluator/results/orchestration/real-two-attempt-evidence/`

Both:

- fail if the expected evidence directory is absent;
- retain the bundle for 30 days;
- keep `contents: read` repository permissions;
- keep checkout credentials disabled;
- pass no repository secrets to candidate code;
- keep the exact worker SHA boundary;
- add no candidate-selection, approval, push, or merge authority.

Artifacts are replay/review evidence only.

## Governance finding remains unresolved

Public branch metadata still reports `main` as unprotected with required status enforcement off.

Repository workflows and documentation can fail closed around that fact, but they cannot substitute for enabling an actual GitHub ruleset/branch-protection policy. This remains an external/admin P0.

Likewise, PR #91 still intentionally requires a genuinely separate human/reviewer inspection of its exact accepted runtime head. The same automation that develops or tests the worker must not manufacture independence by approving it itself.

## Next product step after this fix

Because #117 already proves the same-worker two-attempt path, the next product experiment should be a deliberately simple heterogeneous second real adapter/worker path, followed by a small frozen set of real repository tasks. The purpose is to measure diversity and verifier correlation, not to add sophistication for its own sake.

## Self-improvement rule reinforced by this audit

```text
observe current repository state
 -> distinguish stale tracker text from active defects
 -> notice concurrent evidence that changes priorities
 -> repair one bounded inconsistency
 -> verify exact-head evidence
 -> preserve authority boundaries
 -> archive the result publicly
```

This is a more useful interpretation of repository self-evolution than continuously adding new architecture documents or autonomous write authority.
