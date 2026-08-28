# Project Conversation — Repository audit and next step

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User instruction

The project owner asked to continue, inspect the repository for bugs or inconsistencies, choose the most useful next step, and execute it.

## Audit snapshot

Current `main` at the start of this pass was:

`e86fec878697bdcea0b1d866d41c88d4124c17a0`

The repository has substantially converged around the Verified Swarm Runner and independent verification path. The newest convergence audit correctly identifies the main product sequence as:

1. protect `main` in external GitHub settings;
2. obtain a genuinely separate human/reviewer inspection of PR #91;
3. integrate PR #91 unchanged if that review accepts the exact frozen head;
4. connect the real node behind the merged two-attempt orchestrator;
5. render/replay the real multi-attempt run through the non-selecting Evidence Report layer;
6. only then expand benchmark inventory, fan-out, autonomy, or federation.

This pass deliberately did not bypass the human-review or branch-protection gates.

## Inconsistency 1 — stale verifier bug issue

Issue #82 claimed that `experiments/local_verifier.py self-test` still defaulted to the parent `examples/verifier/good` and `examples/verifier/bad` directories.

Current `main` already contains the required isolated defaults:

```text
examples/verifier/good/candidate-root
examples/verifier/bad/candidate-root
```

Therefore #82 was a stale tracker item rather than a current code bug. It was commented with the observed current-main state and closed as completed.

This is important repository hygiene: open issues should represent current defects/work rather than historical already-fixed conditions.

## Inconsistency 2 — evidence-retention PR diverged from current main

PR #115 adds a useful improvement to the real-node -> independent-verifier E2E workflow: retain the evaluator-owned evidence directory as a downloadable GitHub Actions artifact for 30 days.

Its exact head had already demonstrated a successful E2E run and artifact creation, but the branch had diverged from current `main` while other repository work landed.

Rather than force-merge a diverged branch or bypass the repository's intended review boundary, this pass rebuilt the same small workflow improvement on a fresh branch from current `main`:

`fix/replayable-e2e-evidence-current-main`

The workflow change:

- keeps repository permissions at `contents: read`;
- keeps the worker pinned to exact accepted SHA `520ad2c9aa5825476de4957da4702d6823f4edb3`;
- uses pinned `actions/upload-artifact` v4.6.2 by immutable SHA;
- uploads only `evaluator/results/verification/real-node-520ad2c/`;
- errors if expected evidence is absent;
- retains evidence for 30 days;
- grants no push, approve, merge, or candidate-selection authority.

The artifact remains evidence for review/replay, not an acceptance decision.

## Why this is the next safe executable step

The largest external governance blocker is still unprotected `main`, and the canonical real worker still intentionally requires separate human review before integration. Those cannot be honestly solved by the same automation that proposed the work.

Evidence retention, however, can be improved without crossing either gate. Persisting exact evaluator-owned bytes makes the required human review and later replay easier and more reproducible.

So the safe sequence for this turn is:

```text
close stale tracker defect
 -> rebuild evidence-retention change on current main
 -> let exact-head CI verify it
 -> preserve PR #91 human-review gate
 -> after #91 integration, implement real two-attempt node orchestration
```

## Additional tracker inconsistency found

Issues #4 and #16 still contain older frozen-worker text (`d638a2f...`) in parts of their bodies, while the current accepted PR #91 runtime head is:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Issue #5 is already updated to the current exact accepted head and successful real-node -> verifier E2E evidence.

The product trackers should be normalized so #4/#16 do not present historical acceptance state as the active state. A compact corrective comment is preferable to rewriting historical evidence unless the body is deliberately refreshed.

## Current principle

Repository self-improvement should increasingly mean:

```text
observe real current state
 -> identify concrete inconsistency
 -> remove stale state or repair one bounded defect
 -> verify the change
 -> preserve authority boundaries
 -> record the result publicly
```

not simply opening more architecture or research work.
