# AVE-core Shadow Adapter

**Status:** stacked research adapter for N2/N3 dry-run evidence  
**Date:** 2026-09-22  
**Depends on:** Adaptive Policy Shadow Contract (PR #637 / issue #636)  
**Related research:** AVE (PR #622 / issue #621), E025 learned verifier reliability

## Purpose

The AVE-core shadow adapter is the first concrete consumer of the common
adaptive-policy shadow contract.

It answers only:

> Given one canonical WorkUnit, its already-owned EvaluatorPlan, and a
> point-in-time verifier observation pool, which verifier portfolio would
> AVE-core recommend **in shadow mode**?

It does not:

- modify the EvaluatorPlan;
- dispatch a verifier;
- execute candidate code;
- approve or merge;
- relax required validators;
- grant project spending authority;
- convert model/provider identity into trust.

## Inputs

### WorkUnit v0.2

The adapter reuses:

- exact WorkUnit id/version;
- provenance source revision;
- security risk class;
- required validators;
- independent-verification requirement;
- minimum independent verifier count;
- zero-project-spend budget lane.

### Existing EvaluatorPlan

The adapter treats the current EvaluatorPlan as the **named baseline**.

It verifies:

- exact canonical WorkUnit digest;
- WorkUnit id/version binding;
- source revision binding;
- required validator coverage;
- verifier-distinct-from-worker policy.

The baseline remains visible even when AVE would not choose the same verifier.

That is necessary for a fair N3 comparison.

### Verifier Observation Pool v0.1

Schema:

`schemas/verifier-observation-pool-v0.1.schema.json`

Each candidate includes:

- current availability;
- verifier family;
- supported validator IDs;
- expected review units and queue load;
- independence/correlation signals;
- domain-scoped reliability evidence;
- known-bad probe diagnostics.

The pool is point-in-time evidence, not a durable reputation ledger.

## E025 constraint: no global verifier reputation

E025 showed an important failure mode:

- learned reliability/dependence weighting can improve stable regimes;
- the same learned model can perform materially worse after reliability or
  dependence shifts;
- more calibration history can shrink uncertainty without protecting against a
  changed environment.

Therefore AVE-core gives positive reliability weight only when all are true:

```text
basis == live_outcomes
domain == current task domain
shift_warning == false
sample_count > 0
observed_at is not future-dated
age(observed_at, captured_at) <= reliability_max_age_days
```

Otherwise reliability is neutral:

```text
mean_reliability = 0.5
positive_live_samples = 0
```

This includes:

- synthetic evidence;
- unknown evidence;
- probe-only evidence;
- stale live outcomes;
- wrong-domain live outcomes;
- live outcomes under a shift warning.

## Probe rule

Known-bad probes have asymmetric meaning.

### Passing probes

Passing probes does **not** create positive verifier trust.

A verifier with:

```text
99 / 99 known-bad probes handled correctly
0 live outcomes in the current domain
```

does not outrank a verifier merely because of those probe passes.

### Breaching a known-bad probe

A known-bad breach is a strong diagnostic signal.

For AVE-core v0.1:

```text
known_bad_probe_breaches > 0
 -> verifier remains visible in the frozen observation state
 -> current EvaluatorPlan baseline can still be named
 -> verifier is excluded from AVE shadow portfolio selection
```

This is intentionally asymmetric and should be revisited only with real
representativeness evidence.

## Hard gates

AVE never compensates for a failed hard gate.

The adapter records:

- WorkUnit v0.2 support;
- exact WorkUnit digest binding;
- WorkUnit id/version binding;
- source revision binding;
- verifier-pool repository/WorkUnit binding;
- evaluator sovereignty;
- zero-project-spend lane;
- independent-verification policy;
- required-validator binding.

Any failure forces:

```text
selected_choice_id = null
```

The plan still records the baseline and failure reasons for audit.

## Risk-adaptive target

The shadow target is:

```text
target =
  max(
    WorkUnit.minimum_independent_verifiers,
    risk floor
  )

risk floor:
  low      -> 1
  medium   -> 2
  high     -> 3
  critical -> 3
```

AVE-core v0.1 requires the recommended target-sized portfolio to use distinct
declared verifier families.

This is **not** a claim that different family labels prove independence.

It is a research heuristic motivated by correlated-failure evidence. The shadow
plan explicitly states that family labels are not statistical proof.

If the requested family-diverse portfolio is unavailable, AVE abstains rather
than reducing the target.

## Validator coverage

Portfolio validator coverage is computed as the union across selected
verifiers.

A portfolio is viable only when it covers every validator that is required by:

- the WorkUnit; or
- the existing EvaluatorPlan.

AVE does not remove or downgrade required checks.

## Lexicographic selection

Among viable portfolios, v0.1 uses an explicit lexicographic order:

1. more distinct verifier families;
2. fewer shared-model/shared-runtime correlation signals;
3. more verifiers with fresh same-domain live-outcome evidence;
4. more live-outcome samples;
5. higher posterior mean reliability;
6. fewer review units;
7. lower queue load;
8. deterministic verifier IDs.

There is intentionally no opaque global “trust score.”

## Replay normalization

The verifier pool is canonicalized before shadow-plan hashing:

- verifier candidates sorted by ID;
- validator ID lists sorted/deduplicated;
- reliability source refs sorted/deduplicated;
- limitations sorted/deduplicated.

Equivalent pool orderings therefore produce the same shadow plan.

## N3 evidence workflow

A real N3 capture should occur **before** verification outcome:

```text
WorkUnit + EvaluatorPlan + current verifier pool
 -> AVE shadow adapter
 -> freeze adaptive-policy-plan
 -> real verification continues unchanged
 -> observed VerificationResult/outcome
 -> adaptive-policy outcome join
 -> cohort evaluator
```

The real EvaluatorPlan remains unchanged throughout the cohort.

## Historical fixtures are compatibility tests, not N3 evidence

Existing repository records such as:

`results/verification/node-e2e-replay-2026-08-30/`

are useful to test canonical WorkUnit/EvaluatorPlan compatibility.

They cannot become N3 evidence by replaying AVE today because their verification
outcomes are already known.

That would violate the anti-hindsight rule.

## Promotion gate

This adapter should remain shadow-only until a real pre-outcome cohort shows:

- a meaningful shadow-vs-baseline disagreement rate;
- intact hard gates;
- measurable review/human-attention cost;
- enough delayed outcome evidence to identify useful future controlled tests;
- no evidence that a simpler deterministic diversity rule provides the same
  recommendations at lower complexity.

N3 observational data remains descriptive and does not establish the causal
effect of an unexecuted AVE portfolio.
