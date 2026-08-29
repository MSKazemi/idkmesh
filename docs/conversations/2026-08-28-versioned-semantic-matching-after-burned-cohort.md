# Continuation: burned cohort -> versioned semantic matching — 2026-08-28

## User direction

Continue improving `https://github.com/MSKazemi/idkmesh` while keeping substantive project work in the public repository.

## Convergence first

The turn began by refreshing the live repository rather than assuming the previous snapshot was still current.

A small bounded PR, #150, was merged after exact-head checks passed. Its executable change removed raw issue/PR body snapshots from retained evolution artifacts while keeping derived portfolio evidence. This reduced durable untrusted-text exposure.

## Benchmark state discovery

The Phase B2 first-five benchmark cohort was already present and frozen on `main`. The coordinator already had an execution-neutral worker-adapter boundary. PR #91's node was also correctly distinguished from a coding-agent producer: the node safely executes an explicit execution binding; it does not infer a coding command from a goal-level WorkUnit.

A zero-secret open-weight producer prototype was therefore explored on branch `experiment/open-model-benchmark-task001` / draft PR #161. The prototype was designed to expose only the frozen task objective and frozen allowed-file text to a network-disabled model container, then treat model output as untrusted text and route any bounded patch to the existing independent verifier.

Before that experiment could be interpreted, concurrent repository work produced a more important result.

## Successful benchmark failure

The original frozen Phase B2 cohort was burned intentionally in commit `2d96e9426f24a6e50829420607ebb612aa5821aa`.

Task 001's real solution revealed that its frozen EvaluatorPlan used a semantic fragment in `required_added_text`, while deterministic patch verifier v0.1.1 has exact complete-added-line semantics. A correct longer Python line therefore failed the frozen exact-line predicate.

The repository correctly preserved the pre-outcome commitment instead of changing evaluator meaning after observing the solution.

Draft PR #161 was immediately closed without claiming benchmark evidence. Its producer prototype remains public provenance for a future successor cohort, but it must not be revived against the burned evaluator.

## Issue #157 selected as the next blocker

Issue #157 requires an explicitly versioned semantic contract before a successor cohort is frozen.

No competing implementation or open PR for `required_added_substrings` was found.

The selected design is additive:

```text
historical path (unchanged)
EvaluatorPlan v0.2
 -> deterministic-patch-verifier v0.1.1
 -> required_added_text = exact complete added-line membership

new path
EvaluatorPlan v0.3
 -> deterministic-patch-verifier v0.2.0
 -> required_added_substrings = verbatim substring inside validated added line
```

The existing strict unified-diff parser remains the semantic evidence boundary, so text outside count-balanced `@@` hunks cannot satisfy either contract.

## Implementation direction

The #157 branch is:

`verification/evaluator-plan-v03-substring-semantics`

It adds rather than edits the historical contract:

- `schemas/evaluator-plan-v0.3.schema.json`;
- `experiments/patch_verifier_v020.py`;
- `experiments/evaluator_plan_v03.py`;
- a v0.3 fixture and regression tests;
- a dedicated read-only CI workflow;
- `docs/specifications/EVALUATOR_PLAN_V0_3_SEMANTIC_MATCHING.md`.

The semantic adapter reuses v0.1.1 for strict patch parsing, path authority, artifact/log integrity, worker status, and WorkUnit/ResultManifest binding. It does not execute candidate code.

## Critical regression

The same known-good patch adds:

`<!-- patch-evaluator expected -->`

The regression asks for fragment:

`patch-evaluator expected`

Expected result:

- v0.2 / v0.1.1 exact-line contract: **reject**;
- v0.3 / v0.2.0 substring contract: **support**.

This makes the semantic difference executable and reviewable.

## Governance / next gate

This is a verification-semantics change, so green CI is necessary but not self-approval. The resulting PR must remain open for independent review and must not be self-merged.

Only after the versioned contract is green and reviewed should a successor Phase B2 cohort be frozen. The original first-five cohort remains burned evidence, and its already-solved task 001 cannot be presented as untouched held-out evidence in the successor.
