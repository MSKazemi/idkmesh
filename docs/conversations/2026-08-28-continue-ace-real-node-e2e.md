# Project Conversation — Continue ACE and Verified Swarm Runner convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User instruction

> Continue.

## Repository observation

The canonical ACE convergence chain had completed on `main`:

- #106 cohort observer merged;
- #48 causal lineage protocol merged;
- #104 live review-capacity model merged;
- #68 shadow generational controller merged;
- #98 privileged-workflow safety boundary merged.

The external Phase-B activation gate remained correctly blocked because public GitHub metadata still reported `main` as unprotected and Bootstrap Cohort Observatory #109 still reported zero external verified descendants. PR #112 was verified green and moved from draft to ready for independent review; no self-merge was performed.

## Product-path continuation

The Verified Swarm Runner path had also advanced beyond the older issue #16 snapshot:

- #103 verifier output-authority fix merged;
- #107 canonical metadata-only unified-diff evaluator merged;
- #111 evaluator evidence-completeness hardening merged;
- #88 non-selecting run evidence/replay layer merged;
- PR #91 controlled Docker acceptance completed for exact worker head `520ad2c9aa5825476de4957da4702d6823f4edb3`, but PR #91 intentionally remains draft for separate human/reviewer inspection.

PR #108 contained the first evaluator-side real node -> verifier E2E probe. Its runtime acceptance job passed, but the later E2E job failed before independent verification because the PR merge ref contained an older compatibility wrapper. The failure was explicit:

```text
EvaluatorPlan v0.2 failed schema validation:
backend: 'required_log_types' is a required property;
verifier.adapter_version: '0.1.1' was expected
```

The latest reviewed PR #108 branch subsequently contained the compatibility fix. Rather than revive the closed acceptance PR or alter the accepted worker, this continuation converges the corrected evaluator-side harness onto current `main` as a separate integration proposal.

## New bounded proposal

The clean proposal copies the reviewed evaluator harness files from PR #108 and adds a current-main workflow that:

1. checks out evaluator-owned repository state separately;
2. checks out PR #91 only by exact immutable SHA `520ad2c9...`;
3. preloads the allowlisted Docker image;
4. generates a real worker ResultManifest/patch/log bundle;
5. constructs EvaluatorPlan only after candidate generation;
6. runs the merged hardened metadata-only evaluator;
7. emits canonical VerificationResult/e2e evidence;
8. persists the evaluator-owned result bundle as a GitHub Actions artifact for later replay/review.

The workflow is evidence-only: `contents: read`, no secrets, no approval/merge/write authority, and no candidate-controlled evaluator code.

## Decision rule preserved

```text
worker success != verification
verification evidence != integration authority
healthy ACE capacity != permission to actuate
```

The next useful milestone is one passing real node -> independent verifier replay, followed by wiring that exact worker/evaluator path behind the already-merged two-attempt orchestrator and run-evidence layer.
