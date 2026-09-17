# ACE zero-denominator reproduction semantics stewardship record

**Date:** 2026-09-17  
**Repository:** `MSKazemi/idkmesh`  
**Issue:** #57  
**Base revision:** `ee2d76110ff8176e5e8c154e972c447fe1d3639d`

## Project-owner requirement

The project owner requested a bounded repository-stewardship pass: choose exactly one valuable open issue not already owned by an active pull request; inspect the relevant code, tests, architecture, and documentation; implement production-quality integrated work; preserve scientific validity; add tests and documentation; validate the exact change; and merge only when the repository's required checks and review-safety conditions are satisfied.

## Selected work

Issue #57 (`ACE v1: build an evidence-gated generational policy controller`) was selected after checking the current open issue and pull-request queues. No active pull request was implementing this specific correction.

The existing Phase-A controller computed `R_community = 0.0` when there were zero eligible matured, verified parents. That conflated two different evidence states:

- `0 / P = 0.0` for `P > 0`: an observed zero reproduction ratio;
- no eligible denominator (`P = 0`): the empirical ratio is undefined.

Treating the second case as an observed zero could make missing denominator evidence look like measured failure.

## Implementation decision

The controller now preserves the undefined state explicitly:

- `reproduction_number()` returns no numeric ratio when the eligible-parent denominator is zero;
- serialized result contract version 2 emits `R_community: null` and `R_community_status: undefined_no_eligible_parents` in that case;
- positive denominators continue to emit a numeric ratio with `R_community_status: observed_ratio`;
- the no-parent state remains `DORMANT` with no recommendation/public action, while independent overload conditions can still force `CONSOLIDATE`;
- existing strategy-fitness, lineage validation, capacity homeostasis, and actuation gates are unchanged.

## Tests and documentation

Regression coverage distinguishes an actual observed `0.0` from the undefined zero-denominator state and checks the result-version boundary. The ACE generation evidence-interface documentation now defines the denominator semantics explicitly and warns that older `D / max(1, P)` design shorthand is not the empirical measurement contract.

## Scientific interpretation

This is a semantics/correctness improvement, not evidence that ACE community reproduction is positive or negative. `R_community` is still conditional on the project's declared parent eligibility, maturation window, lineage-validation, and verification rules. A nullable value prevents absence of eligible observations from being promoted into a quantitative empirical claim.

## Validation boundary

The automation environment did not provide a usable local execution container during this run, so no local full-suite result is claimed. Repository CI on the exact pull-request head is the integration evidence and must be green before merge.

## AI/tool provenance

This bounded change was prepared by the owner-controlled IDKMesh stewardship automation using ChatGPT and the connected GitHub integration. It is not independent human review and grants no integration authority by itself.
