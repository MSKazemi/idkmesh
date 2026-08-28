# Phase B2 first-five benchmark v3

Status: **pre-outcome frozen successor definition**

This directory is the first Phase B2 five-task successor created after the original first-five cohort was deliberately burned.

## Freeze identity

- Cohort: `benchmark/phase-b2-first-five-v3`
- Frozen source revision: `a69aa0ae1ae4862e507511cbd9ad854237d0ad32`
- Definition digest: `sha256:fe4488053c794d696d3168664674a73f9d16b196a8ac8127ffd36734087000dd`
- Evaluator contract: public EvaluatorPlan v0.4 / deterministic patch verifier 0.3.0
- Initial outcomes: **none** — all five task evidence slots are `pending`

The source revision predates this directory, so a worker checkout of the frozen source cannot contain these WorkUnits or evaluator plans.

## Why v3 exists

The original first-five v1 definition was burned after real Task 001 evidence revealed that its frozen v0.2 evaluator had committed a semantic fragment under an exact-complete-line contract. The project preserved that failure instead of retuning the evaluator after seeing the solution.

The subsequent verification work established:

1. v0.2 / verifier 0.1.1 — exact complete added-line semantics;
2. v0.3 / verifier 0.2.0 — added-line substring semantics;
3. adversarial calibration showing presence-only substring semantics can be Goodharted by inert text;
4. v0.4 / verifier 0.3.0 — explicit added-and-removed substring transition semantics;
5. real frozen Task 001 calibration in PR #177, where the straightforward repair passed metadata verification and behavioral path checks while an inert decoy was rejected by v0.4 and remained behaviorally vulnerable;
6. PR #175 routing public v0.4 EvaluatorPlans through the canonical Benchmark Cohort v0.1 validator.

Original Task 001 is calibration evidence and is **not reused** here.

## Five fresh tasks

| Task | Family | Allowed path | Transition intent |
| --- | --- | --- | --- |
| 101 | bug fix | `tools/benchmark_cohort.py` | replace conditional negative-evidence verification with explicit fail-closed `verification_result` requirement |
| 102 | test/failure | `tests/test_e015_phase_diagram.py` | replace hard-coded `need = 8` with the analyzer's `floor(q*n)+1` rule |
| 103 | bounded feature | `sim/e015_analyze.py` | replace equal-error averaging with an optional normalized cost-weighted form |
| 104 | refactor | `scripts/evolution_score.py` | replace all-at-once weight defaulting with per-dimension forward-compatible defaults |
| 105 | documentation contract | `experiments/E015-verification-phase-diagram.md` | replace the singular one-sided metric introduction with an explicit one-sided vs quorum-comparable distinction |

Every task is bounded to one writable path, has zero project spend, requires independent verification, and has no merge/push/canonical-write authority.

## Pre-outcome guard

The dedicated freeze workflow checks, before any evidence collection:

- Benchmark Cohort schema and cross-object digest/binding validity;
- exact definition digest;
- five required families and five pending evidence slots;
- every WorkUnit/plan source binding equals the frozen source SHA;
- every plan is EvaluatorPlan v0.4 / verifier 0.3.0;
- each task has exactly one allowed/write path;
- the frozen source target exists;
- **every verifier-owned required-removed substring actually exists in that frozen target file**.

That last check is deliberately stronger than the burned v1 process. It does not prove the evaluator is behaviorally complete, but it prevents freezing a transition requirement whose starting state is absent.

## Outcome rule

Once this definition is accepted, do not modify WorkUnits, evaluator plans, taxonomy, source revisions, or the definition digest in response to candidate outcomes. Outcome evidence belongs in the existing `evidence` fields and does not participate in the pre-outcome definition digest.

If calibration reveals another evaluator defect, burn this cohort rather than silently reinterpret it.
