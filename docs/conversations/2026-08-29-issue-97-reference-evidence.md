# Issue #97 Selection and Reference-Evidence Completion

**Date:** 2026-08-29
**Scope:** Select one currently unclaimed issue, complete it through a bounded
pull request, and integrate only after current exact-head checks pass.

## Project-owner requirement

Select an issue that no other contributor is currently working on, solve it
professionally, open a pull request, and merge the verified result into `main`.

## Selection evidence

Issue #97 was selected after checking current GitHub and repository state:

- it had no assignee and no issue comments;
- neither open PR (#159 or #242 at selection time) overlapped R4;
- PR #100 had already merged the executable R4 harness;
- PR #101 was closed because it contained only a failing one-shot workflow and
  none of the result files claimed by its description;
- the old `experiment/r4-reference` and `biology-aco-stigmergy-v0` branches were
  stale historical refs, not active review surfaces.

The issue was publicly assigned before implementation to prevent duplicate
work. The replacement branch started from current
`main@5123f8c1f47c4ec5b1982863d0e90c8bf8b00232`; no stale branch was merged.

## Work completed

The documented default and lock-in scenarios were regenerated from the merged
harness with full per-step events. The change publishes:

- both raw machine-readable traces;
- a readable comparison with exact commands and SHA-256 provenance;
- fixed artifact-digest and cross-runtime replay tests, with byte-for-byte
  regeneration on the recorded Python 3.12 runtime family;
- status/documentation updates that preserve the synthetic-only boundary.

## Findings

- evaporation plus exploration outperformed permanent pheromone in both frozen
  scenarios;
- permanent pheromone never sampled the strong late expert in the lock-in trap;
- Thompson sampling slightly led realized success in the default trace and
  decisively beat every stigmergic policy in the lock-in trap;
- every stigmergic run recorded zero positive pheromone change from unverified
  activity.

The conventional-bandit win is retained as a negative result. The evidence does
not authorize production routing, contributor scoring, governance power, or
automatic acceptance.

## Community impact

The issue is no longer a misleading open implementation candidate, and future
contributors can reproduce or challenge the evidence without recovering a
failed workflow or stale branch. Follow-up parameter sweeps remain separable
research rather than an implicit requirement for closing this bounded issue.

## AI/tool provenance

Codex selected the bounded issue, generated the deterministic artifacts with the
repository CLI, prepared the analysis and tests, and ran the documented
verification. GitHub exact-head checks remain the integration gate.
