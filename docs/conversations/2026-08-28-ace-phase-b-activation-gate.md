# Conversation Record — ACE Phase-B Activation Gate

**Date:** 2026-08-28

## User direction

The user asked IDKMesh to continue evolving the GitHub-native, self-improving community system.

The standing project requirement remains that substantive project reasoning and implementation output should be preserved in this public repository.

## Context

Previous ACE work established:

- a GitHub-native Autocatalytic Community Evolution (ACE) model;
- a community reproduction number based on verified descendants rather than activity volume;
- carrying-capacity / review-load homeostasis;
- a conservative GitHub metadata loop;
- Bootstrap Cohort Growth Seeds;
- candidate observer, lineage, simulator, security, protection, and Phase-A controller implementations;
- a replicator-mutator controller operating in shadow mode;
- a hard public-action budget of at most one per generation;
- explicit zero-action behavior under overload.

During this continuation, PR #68 was reconciled and marked ready for review after its current head passed ACE Generation Shadow, Phase 0, and randomness-lab CI.

## New observation

The public ACE Growth Ledger (#23) was inspected again.

At approximately 2026-08-28 14:55 UTC it reported:

```text
Mode: CONSOLIDATE
Reproductive credit: ~15.419
Review-load proxy: ~35.55
Capacity multiplier: ~0.000
```

The repository had generated substantial internal activity, but its own experimental capacity signal said that verification/review pressure was saturated.

The Bootstrap Cohort still had no recorded independently verified descendant in the ACE evidence model. Candidate implementations existed for several seeds, but candidate work was deliberately not counted as verified reproduction.

This makes the correct near-term behavior **consolidation**, not further autonomous spawning.

## Decision

Implement an **external, fail-closed ACE Phase-B Activation Gate**.

The controller itself must not be able to declare its own activation prerequisites satisfied.

The v0 gate requires all of the following:

```text
observer accepted
AND lineage accepted
AND security accepted
AND controller accepted
AND protected integration enforced
AND real independently verified descendant evidence exists
AND review-capacity state is readable/fresh/single-writer/healthy
AND public write budget <= 1
AND forbidden high-impact capabilities remain disabled
```

This is a conjunction, not a weighted score. Security, protection, or evidence requirements cannot be offset by popularity or activity.

## Implementation

Branch: `ace-activation-gate-v0`

Added:

- `scripts/ace_activation_gate.py`
  - deterministic offline evaluator;
  - validates the gate snapshot;
  - fails closed on missing/malformed evidence;
  - returns `PASS` or `BLOCK` plus named blockers;
  - emits `activation_gate_passed` for future controller integration;
  - contains no GitHub API calls or mutation logic.
- `examples/community/ace-activation-gate-current.example.json`
  - point-in-time snapshot of current blocked conditions;
  - open/pending dependencies;
  - zero verified descendants;
  - ACE capacity approximately zero;
  - all forbidden capabilities disabled.
- `tests/test_ace_activation_gate.py`
  - current-state BLOCK;
  - all-evidence PASS;
  - pending dependency BLOCK;
  - unverified descendant BLOCK;
  - low/stale capacity BLOCK;
  - write-budget violation BLOCK;
  - forbidden-capability BLOCK;
  - malformed/missing component fail-closed;
  - determinism.
- `docs/community/ACE_ACTIVATION_GATE.md`
  - activation contract, formula, evidence sources, current snapshot interpretation, and non-goals.
- `.github/workflows/ace-activation-gate.yml`
  - read-only Python 3.11/3.13 validation;
  - explicitly asserts that the committed current-state fixture remains BLOCK.

## Core principle

The activation decision should be monotone with respect to safety prerequisites:

> adding evidence may remove a blocker, but raw activity can never bypass a missing blocker.

A BLOCK result is not a failure. It is a valid homeostatic output telling the repository to remain in shadow/consolidation mode.

## Next step

After independent review, a future read-only metadata adapter can build an activation snapshot from actual GitHub state and feed it into this gate.

Even then, a PASS result should only authorize consideration of the separately reviewed Phase-B adapter; it must not imply autonomous merge, governance mutation, secret access, untrusted code execution, or unrestricted issue/comment generation.

## Related

- #10 community engine
- #23 ACE Growth Ledger
- #25 / PR #48 lineage
- #26 / PR #62 security
- PR #40 cohort observer
- PR #51 protected integration
- #57 ACE v1 controller
- PR #68 ACE activity metabolism / Phase-A controller
