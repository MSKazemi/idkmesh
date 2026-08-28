# Conversation Record — Algorithmic CI Shadow Planner v0.1

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner asked whether the repository's CI/CD ecosystem and algorithmic CI could become substantially smarter, then requested continuation.

## Evidence reviewed

The review found 42 workflow files comprising roughly 4,644 lines. In the sampled latest 100 workflow runs, 17 were cancelled. Only eight workflows declared concurrency control, no workflow used dependency caching, five used `pull_request_target`, and 13 workflow files still referenced third-party Actions by movable major-version tags rather than immutable commits. Public metadata also continued to report `main` as unprotected.

The repository already had strong components: exact-head verification, conjunctive hard gates, typed evidence, non-scalar evidence aggregation, branch-plan invalidation, bounded authority, and deterministic mathematical tests. The missing layer was one common CI planner and durable outcome contract.

## Implemented decision

Implement `ci-planner-v0.1` in shadow mode:

1. classify exact changed paths by reviewed risk rules;
2. select impacted hard gates;
3. close their dependency graph;
4. rank only optional checks by explicit information-value/cost priors;
5. preserve deterministic exploration within the optional budget;
6. emit exact-revision `CIPlan` and planning-only `CIReceipt` artifacts;
7. continue running the existing full CI baseline.

The planner has no execution, test-skipping, repository-write, approval, or merge authority. It cannot spend project funds. Workflow and planner changes are R3 and promote the full regression suite to mandatory in the advisory plan.

## Open evidence requirement

No claim of smarter or cheaper CI is made yet. A 50–100 PR shadow cohort must compare planner recommendations with actual full-CI failures, duration, cancellations, and post-merge defects. Selective execution is a later proposal only if failure-detection recall remains strong and optional compute decreases without weakening hard gates.

## Community impact

The plan makes CI decisions explainable to contributors: every selected or omitted check has a reason, estimated cost, matched files, and authority boundary. A shared contract should eventually reduce duplicated workflow maintenance, but v0.1 deliberately adds one observational workflow while evidence is gathered.
