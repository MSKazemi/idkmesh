# Continuation: Phase B2 v3 calibrated freeze — 2026-08-28

## User direction

Continue improving the public IDKMesh repository and keep substantive project work in GitHub.

## State refreshed first

The repository was moving concurrently, so this continuation re-read live state rather than relying on an earlier snapshot.

Confirmed current evidence:

- PR #177 is merged and its exact head `c4e4810c618a0ab840e22727724937a6dcb40513` has green Task 001 canonical v0.4 calibration, Phase 0, and IDKGraph checks.
- PR #175 is merged and current `tools/benchmark_cohort.py` validates public EvaluatorPlan v0.2, v0.3, and v0.4 contracts without changing the historical meanings of those versions.
- the obsolete attempted v2 successor PR #163 is closed/unmerged.
- current worker replacement PR #159 has fresh exact-head controlled Docker evidence; its remaining gate is genuinely separate human review in #138, so it was not merged or marked ready by this continuation.
- GitHub still reported `main` protection disabled, so no autonomy/integration ceiling was raised.

The conversation record from an earlier closed calibration branch was not present on `main`, so this file also preserves the durable continuation findings in the new public successor-definition branch.

## Why a new successor can now be defined

The original Phase B2 first-five cohort remains deliberately burned at definition digest:

`sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`

Its real Task 001 outcome exposed an exact-line versus semantic-fragment mismatch. The repository did not reinterpret the frozen evaluator after observing that result.

Subsequent calibration/versioning established:

```text
v0.2 / verifier 0.1.1 -> exact complete added-line equality
v0.3 / verifier 0.2.0 -> added-line substring presence
v0.4 / verifier 0.3.0 -> added + removed substring transition evidence
```

Presence-only v0.3 was itself shown Goodhartable by an inert lexical decoy. Canonical v0.4 then received a real frozen-source Task 001 calibration in #177:

- straightforward replacement: metadata verification passed / `accept_candidate`, and all unsafe path probes were behaviorally rejected;
- inert decoy: metadata verification failed / `reject_candidate`, while vulnerable path behavior remained;
- metadata-only verifier executed no candidate code;
- behavioral execution was kept as a separate evaluator-owned evidence channel;
- no automatic selection or merge authority was created.

That is sufficient to define a fresh small benchmark, not to claim v0.4 is a universal semantic verifier.

## New pre-outcome source freeze

The successor is bound to exact repository source revision:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

This revision predates the new benchmark directory. A worker receiving that source snapshot cannot obtain its evaluator plans from the source checkout.

## Five fresh tasks selected

The new cohort deliberately does not reuse the already-observed original Task 001.

1. **Bug fix** — `tools/benchmark_cohort.py`
   - current verified negative-evidence handling only performs strong checks when `evidence_type` already equals `verification_result`;
   - task requires replacing that conditional gate with an explicit fail-closed type requirement.

2. **Test/failure** — `tests/test_e015_phase_diagram.py`
   - strict-quorum regression hard-codes `need = 8`;
   - task requires deriving `floor(q*n)+1` instead of retaining the magic threshold.

3. **Bounded feature** — `sim/e015_analyze.py`
   - `effective_n_balanced` currently assumes equal costs for false accepts and false rejects;
   - task requires optional cost weights defaulting to 1.0 and normalized cost-weighted error while preserving current callers.

4. **Refactor** — `scripts/evolution_score.py`
   - weight migration initializes the whole map only when the map is absent;
   - task requires preserving existing values while defaulting any missing future dimension independently.

5. **Documentation contract** — `experiments/E015-verification-phase-diagram.md`
   - opening metric section still presents the one-sided metric before the later quorum caveat;
   - task requires an explicit one-sided versus quorum-comparable distinction near the metric definition.

All tasks have one writable path, public inputs, zero project spend, no secrets, and independent-verification requirements.

## Calibrated evaluator boundary

All five public evaluator plans use EvaluatorPlan v0.4 / deterministic patch verifier 0.3.0.

Each evaluator requires both:

- at least one specific removed substring from the frozen source;
- the intended added transition substring(s).

This is stronger than the burned v1 and Goodhartable v0.3 presence-only predicates. It is still a static transition proxy, not behavioral proof.

## New definition identity

Cohort:

`benchmark/phase-b2-first-five-v3`

Pre-outcome definition digest:

`sha256:fe4488053c794d696d3168664674a73f9d16b196a8ac8127ffd36734087000dd`

At this digest:

- five task families are present;
- every task evidence status is `pending`;
- every negative evidence status is `pending`;
- no ResultManifest, VerificationResult, candidate patch, selected candidate, or human decision is included.

## New freeze invariant

A dedicated read-only CI workflow validates the normal cohort schemas/digests and additionally checks every verifier-owned `required_removed_substrings` value against the **exact frozen source file** before candidate collection.

This is a direct lesson from the burned cohort: a transition evaluator should not be frozen unless its starting-state requirement is demonstrably present at the committed source revision.

If later calibration reveals another evaluator defect, burn this successor rather than retuning its frozen meaning after outcomes are observed.

## Authority

Nothing in this continuation can:

- write canonical repository state from CI;
- push;
- approve;
- merge;
- select a winning candidate automatically;
- bypass #159's genuinely independent human-review requirement;
- raise autonomy while `main` remains unprotected.
