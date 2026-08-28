# Conversation Record — ACE Lineage Reconciliation

**Date:** 2026-08-28

## Project-owner direction

The project owner asked the assistant to continue work on the public `MSKazemi/idkmesh` repository.

## Repository state observed

The continuation found two overlapping pull requests:

- PR #44 implements Growth Seed #27 with a deterministic ACE population simulator and dedicated acceptance checks;
- PR #48 implements Growth Seed #25's lineage protocol but also contained a second `experiments/ace_population_sim.py` implementation and attempted to close #27.

The overlap would have forced reviewers to compare two implementations of the same file and created unnecessary merge/review complexity.

## Decision

Reconcile the work into two bounded contribution surfaces:

1. **PR #44 remains the simulator PR for #27.**
2. **PR #48 is narrowed to the parent -> seed -> descendant evidence protocol for #25.**

This follows the project's community-first and verification-first rules: smaller PRs are easier to understand, review, reproduce, and accept or reject independently.

## Lineage-protocol refinement

During reconciliation, the lineage metric definition was tightened to avoid survivorship bias.

A lineage edge can only exist once a descendant candidate exists. Therefore lineage edges cannot by themselves define the denominator of:

```text
R_community(W) = verified descendants / verified parents
```

Otherwise parents that produce zero descendants would be absent and the measured reproduction rate would be biased upward.

The revised protocol therefore requires the denominator to come from an independent eligible-parent/Growth-Seed inventory, such as the Bootstrap Cohort observer in PR #40 or a future unified IDKGraph.

It also documents right-censoring: newly created parents whose full observation window has not elapsed should not yet be counted as zero-descendant failures.

## Concrete lineage examples

The revised protocol uses actual current candidate relationships:

- issue #10 -> Growth Seed #25 -> PR #48;
- issue #10 -> Growth Seed #27 -> PR #44.

Both remain `candidate` evidence until their applicable verification/integration gates are satisfied.

## Verification boundary

The protocol keeps these distinctions explicit:

```text
activity != candidate fitness
merge != verified descendant
verification evidence != merge authority
```

Natural-language issue/PR content remains untrusted input. Structured `ACE_LINEAGE` metadata is validated evidence metadata, not executable instructions.

## Community impact

The reconciliation reduces duplicate code, lowers reviewer burden, keeps each Growth Seed claimable as one coherent unit, and makes future ACE metrics statistically less misleading.

No autonomous merge, policy-selection, or Growth Seed spawning authority is added by this continuation.
