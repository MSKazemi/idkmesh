# Project Conversation — Execute Priorities: Protected Integration and Deterministic Verification

**Date:** 2026-08-28

## Project-owner direction

The project owner instructed the assistant to proceed with the high-priority repository work identified by the current priority audit.

## Priority execution in this turn

The work concentrated on two P0/P1 boundaries:

1. protect canonical integration before stronger autonomous write authority;
2. convert independent verification from a schema/reporting concept into executable evidence recomputation.

## Protected-integration work

A separate safety PR (#51) was opened to:

- document the exact bootstrap GitHub `main` protection contract;
- update governance with the invariant that one autonomous actor cannot propose, approve, and merge the same protected change;
- make the ACE reproductive actuator fail closed while GitHub reports `main` as unprotected;
- preserve the ACE ledger as observation-only evidence during that state.

The assistant deliberately did not self-merge that safety PR.

## Canonical-node integration observation

PR #34 was inspected repeatedly. Its branch was receiving concurrent updates while synchronization commits were being prepared. GitHub correctly rejected stale non-fast-forward ref updates.

The assistant did **not** force-push over the concurrent branch.

Later inspection found PR #34 head `9ac6c09d4db06dc7c846d319e76624fbf1eaaa0f` with both Node CI and Phase 0 schema CI passing, but the branch remained non-mergeable as `main` continued changing. Issue #37 was updated so Docker acceptance evidence is explicitly bound to the exact tested head SHA and cannot silently authorize later branch contents.

## Deterministic verifier gap

The repository already had:

- `VerificationResult v0.1` schema;
- Phase 0 cross-object validation;
- an independent-verifier identity requirement.

But those mechanisms could still validate **reported verification** without independently recomputing candidate evidence.

The next #5 slice was therefore defined as a deterministic candidate-bundle verifier.

## PR #61 implementation

PR #61 adds `verifier/deterministic.py` and a bounded fixture/test suite.

The verifier:

- validates canonical WorkUnit/ResultManifest contracts;
- requires verifier identity to differ from worker identity;
- recomputes the Work Unit canonical SHA-256;
- recomputes declared artifact/log SHA-256 values;
- rejects artifact locators escaping a trusted root;
- parses patch target paths;
- checks patch paths against `allowed_paths` and `forbidden_paths`;
- emits canonical `VerificationResult v0.1` decision support;
- treats unsupported required validator IDs as inconclusive rather than passed;
- never executes candidate code, model calls, network services, or paid compute.

## Negative evidence and corrections

The new CI did not pass immediately. The failures were retained and used to improve the branch.

### Failure 1 — validator-type mismatch

The WorkUnit fixture used validator type `policy` for `path-policy`, but WorkUnit v0.2 does not define `policy` as a validator type.

Correction:

- changed the WorkUnit validator type to `review`;
- preserved `policy` as the emitted VerificationResult check type, where that type is valid;
- recomputed and updated the Work Unit provenance digest.

### Failure 2 — good fixture artifact digest was wrong

After the contract fix, four fail-closed unit tests passed, while the known-good fixture was still rejected.

Diagnostics showed:

```text
declared:
sha256:3b2266db16579a288d6906b5418e9695b155936ea62a956b84d9d63c87db1526

independently computed by CI from checked-out bytes:
sha256:c5618872782508818f97df04e87e9fa6cec7c6d88e5f4bb905915bd36fd8eb19
```

The verifier was **not weakened** to accept the declaration. The fixture manifest was corrected to the independently observed digest.

This is a useful small demonstration of the project thesis: a worker/fixture claim is not evidence merely because it was intended to be correct.

## CI state at conversation record creation

Shared Phase 0 contract checks had repeatedly passed. The deterministic verifier workflow was re-running after the digest correction.

The branch should not be treated as ready until the dedicated verifier CI is green on its current head.

## Issue tracking updated

Issue #5 now distinguishes:

- completed deterministic evidence recomputation substrate;
- remaining sandboxed hidden-test/regression/static/security verifier plugins;
- benchmark task-set work.

Issue #37 now explicitly binds Docker acceptance evidence to an exact PR #34 head SHA.

## Next work after green verification CI

1. independent review/integration of #61;
2. controlled Docker acceptance #37 for the exact current #34 head;
3. independent review/integration of #51 and actual GitHub `main` ruleset configuration by a repository administrator;
4. after the worker and verifier paths are stable, build the small local multi-worker orchestrator (#4) and end-to-end Evidence Report (#16).

## Community impact

The new verifier creates a bounded contribution surface for independent validator plugins while preserving a simple rule:

> worker output is an untrusted candidate; evidence must be recomputed by an independently controlled verifier before integration.
