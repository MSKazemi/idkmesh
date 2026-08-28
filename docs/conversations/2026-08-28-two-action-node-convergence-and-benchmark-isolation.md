# Two-action repository continuation: node convergence + benchmark isolation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner request

Inspect the live public GitHub repository and perform the two highest-value bounded actions.

## Live findings

1. PR #91 remains the canonical `idkmesh-node` candidate at exact head `520ad2c9aa5825476de4957da4702d6823f4edb3`, with successful Node CI / Phase 0 CI and completed controlled-Docker evidence.
2. The branch is now heavily stale relative to `main`: 16 commits ahead and 54 commits behind at the inspected snapshot. GitHub reports it non-mergeable/draft.
3. The project requires genuinely separate human review of the exact worker evidence and forbids treating the same automation identity as independent approval.
4. Phase B2 benchmark definitions are frozen against immutable source revision `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`.
5. Current `main` now contains the solution to frozen benchmark Task 001 (`c04ae627...`, cohort path boundary). This creates potential answer leakage if a benchmark worker can inspect post-freeze history/current `main`.

## Action 1 — clean current-main node replacement

Instead of rebasing the stale #91 branch, reconstruct its exact 14-file worker delta on a fresh branch from current `main` using the original Git blob SHAs. This preserves implementation bytes while removing 54 commits of ancestry drift.

Important evidence rule:

- old #91/#37/#108 runtime evidence remains historical evidence about the identical worker bytes;
- it is **not** automatically transferred as exact-head acceptance to the replacement commit;
- the replacement must rerun exact-head Node/Phase 0 CI and controlled runtime evidence before human acceptance;
- human review remains external and cannot be manufactured by automation.

## Action 2 — protect Phase B2 from answer leakage

Task 001 is still valid as a frozen-source replay task, but it is no longer naturally held out from the evolving public repository because its solution now exists on later `main`.

Before using the cohort for diversity/quality claims, worker execution should therefore enforce a historical-knowledge boundary:

- checkout only the exact frozen source revision;
- do not expose later Git history/current `main` to the worker;
- do not give the worker network/tool access that can retrieve the public post-freeze solution unless that condition is explicitly classified as an open-book arm;
- record exposure status per task/arm;
- if isolation cannot be guaranteed, classify Task 001 as answer-exposed/control evidence rather than held-out evidence.

This does not alter the frozen cohort definition digest or rewrite outcomes. It preserves the negative possibility that an apparent benchmark win could be caused by information leakage rather than better reasoning.

## Principle reinforced

```text
convergence before expansion
+ exact evidence before acceptance
+ frozen source is not enough unless information exposure is also controlled
```
