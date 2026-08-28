# Project Conversation — Persist real node verifier evidence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User instruction

> Continue.

## Current state

The canonical ACE convergence chain is now on `main`, including the fail-closed Phase-B activation gate. Phase B remains blocked because public GitHub metadata still reports `main` as unprotected and Bootstrap Cohort Observatory #109 still has zero external verified descendants.

On the product path, PR #113 merged the first successful real-node-to-independent-verifier E2E proof using exact accepted worker head `520ad2c9aa5825476de4957da4702d6823f4edb3` and the current hardened EvaluatorPlan/unified-diff verifier.

The exact PR #113 E2E workflow run passed, but inspection of its workflow artifacts returned an empty artifact list. The generated evaluator-owned bundle therefore existed only during the job plus selected job-summary/log output.

## Improvement

This change does not alter the worker, evaluator, plan, checks, or authority model. It adds one read-only evidence-retention step to `.github/workflows/real-node-verifier-e2e.yml` using a pinned `actions/upload-artifact` action.

On a successful E2E run, the workflow now persists:

`evaluator/results/verification/real-node-520ad2c/`

for 30 days. That directory contains the exact evaluator-owned inputs/results produced by the harness, including the generated WorkUnit copy, ResultManifest/candidate bundle, EvaluatorPlan, VerificationResult, and compact E2E evidence record.

## Why

A job summary is useful for inspection, but a downloadable bundle is a better reproducibility surface. Reviewers can retrieve the exact evidence directory instead of reconstructing it from logs, and future replay/integration work can bind to concrete bytes.

## Safety

- workflow remains `contents: read`;
- candidate remains checked out only by exact accepted SHA;
- no repository secrets are passed to candidate code;
- upload action is pinned to an immutable SHA;
- artifact retention creates no push/approve/merge authority;
- verifier recommendation remains decision support only;
- human integration remains external.

## Next product step

After this evidence-retention improvement, the remaining v0.1 product work is primarily:

1. separate human/reviewer inspection of PR #91 before it leaves draft;
2. wire the accepted real node behind the merged two-attempt orchestrator;
3. exercise the merged non-selecting Run Evidence Report over real attempts;
4. add one trivial heterogeneous second real adapter;
5. then run the real-task diversity/verification experiment.
