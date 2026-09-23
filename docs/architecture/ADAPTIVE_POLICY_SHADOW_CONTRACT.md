# Adaptive Policy Shadow Contract v0.1

**Status:** proposed executable contract for N2 -> N3 research transition  
**Date:** 2026-09-22

## Purpose

IDKMesh now has several experimental adaptive mechanisms, including:

- Adaptive Verification Ecology (AVE);
- Physarum-inspired compute-path routing;
- existing stigmergic/homeostatic task routing;
- future community-policy controllers.

Those mechanisms should not each invent a different path from "research result" to
"real repository recommendation."

The Adaptive Policy Shadow Contract provides one common envelope:

```text
exact real revision + real observed state
 -> hard gates
 -> eligible choices
 -> experimental policy
 -> advisory recommendation
 -> explanation + baseline + uncertainty + expected cost
 -> no execution / no merge / no spend authority
```

The contract is:

- `schemas/adaptive-policy-plan-v0.1.schema.json`
- `tools/adaptive_policy_shadow.py`

## What the contract does not do

It does not implement a routing algorithm.

It does not decide whether AVE, Physarum, ACO, a bandit, or a deterministic
baseline is better.

It only forces every policy to expose the same safety-relevant information.

## Required binding

Every plan is bound to:

- repository;
- exact source revision SHA;
- canonical digest of the policy input state;
- references to the WorkUnit/snapshot/offer graph/evidence used.

This reduces accidental hindsight leakage and stale-policy recommendations.

## Hard-gate rule

Hard gates are evaluated before adaptive selection.

Examples:

### AVE

- exact WorkUnit/source binding;
- evaluator sovereignty;
- required validator coverage;
- worker/verifier separation;
- project review budget.

### Physarum

- resource evidence;
- local authorization;
- concrete compute admission;
- WorkUnit capability/trust requirements;
- repository zero-project-spend policy.

If **any hard gate fails**, the contract requires:

```text
selected_choice_id = null
```

The adaptive policy is not allowed to "optimize around" the failure.

## Baseline requirement

The plan can record a named baseline choice beside the adaptive recommendation.

This is important for N3 dry-run evidence:

```text
adaptive recommendation
vs
existing deterministic / simple baseline
```

A later evaluator can then ask:

- did the recommendation differ?
- did the difference improve the eventual outcome?
- what resource premium did it predict?
- was the policy uncertain?
- did a human override it?

## Authority is structurally false

The schema fixes all of these values:

```text
advisory_only = true
dispatch = false
execute = false
approve = false
merge = false
repository_write = false
relax_hard_gates = false
modify_required_verification = false
authorize_project_spend = false
```

The recommendation can be recorded, compared, and studied. It cannot act.

## Expected-cost accounting

The recommendation records:

- project spend (fixed to zero);
- compute units;
- review units;
- human-attention units.

The non-monetary fields may be null when unmeasured.

A policy should not claim an efficiency improvement when the cost dimension was
not measured.

## N3 use for AVE

A future AVE dry-run can consume a real WorkUnit and current verifier state and
emit, for example:

```text
baseline:
  one deterministic eligible verifier portfolio

AVE-core:
  two-family verifier portfolio
  risk-adaptive fan-out
  estimated review premium
  uncertainty
```

It does not modify the EvaluatorPlan or dispatch a verifier.

After the real work finishes, retained outcomes can evaluate whether the shadow
recommendation would have helped.

## N3 use for Physarum

A future compute-path dry-run can consume the graph produced **after existing
compute admission**.

It can emit:

```text
baseline:
  current deterministic eligible path

Physarum:
  alternate admitted path
  expected burden premium
  reliability/conductance explanation
  uncertainty
```

It does not execute a job or create an eligible offer.

## Promotion evidence

The contract enables a common N3 cohort:

1. produce shadow plan against exact real revision/state;
2. retain the plan before the outcome is known;
3. run the existing real process unchanged;
4. record the eventual verified outcome;
5. compare policy vs baseline retrospectively;
6. measure resource/human-attention trade-offs;
7. keep negative cases.

This is the intended bridge from synthetic research to real observational
evidence without granting autonomy.


## Retrospective outcome record

Shadow plans are joined to later real outcomes through:

- `schemas/adaptive-policy-outcome-v0.1.schema.json`
- `tools/adaptive_policy_outcome.py`

The join is immutable with respect to the original plan. It records:

- exact plan digest;
- exact revision/input binding copied from the frozen plan;
- the choice the real process actually used;
- the observed real-process outcome;
- measured cost where available;
- whether the shadow recommendation matched the actual choice;
- whether the named baseline matched the actual choice.

The contract deliberately fixes:

```text
shadow_counterfactual_observed = false
causal_claim_allowed = false
```

for N3 shadow outcomes.

That matters when:

```text
baseline route A actually ran and succeeded
shadow policy recommended route B
```

The evidence supports:

```text
shadow disagreed with baseline
route A's real outcome is observed
```

It does **not** support:

```text
route B would have succeeded
route B would have been faster
the shadow policy would have improved the outcome
```

Those claims require either additional independently observable evidence or a
later bounded live experiment designed to identify the counterfactual.

This anti-counterfactual rule prevents dry-run evidence from being overstated.


## Cohort evaluator

A set of frozen plans and later outcome records can be summarized with:

- `schemas/adaptive-policy-cohort-summary-v0.1.schema.json`
- `tools/adaptive_policy_cohort.py`

The cohort evaluator verifies every outcome's exact plan digest before joining.

It reports:

- plan/outcome counts and missing outcomes;
- shadow-vs-baseline disagreement rate;
- how often the real process happened to match the shadow choice or baseline;
- descriptive observed success/escape rates;
- verified-utility mean when measured;
- measurement coverage for utility, defects, project spend, compute, review,
  and human attention.

It deliberately does **not** calculate a policy treatment effect:

```text
descriptive_only = true
shadow_counterfactual_observed = false
causal_effect_estimate = null
promotion_decision_automatic = false
```

This distinction matters because N3 shadow mode usually leaves the real process
unchanged. When shadow and baseline disagree, only the actually executed choice
has an observed outcome.

The first value of an N3 cohort is therefore to learn:

- whether the adaptive policy makes materially different recommendations;
- where it abstains;
- whether its inputs/costs are measurable;
- which disagreements deserve a future controlled N4 test;
- whether its assumptions fail on real repository state.

A low disagreement rate is itself useful evidence: it may show that the new
policy adds complexity without changing decisions enough to justify promotion.


## Temporal anti-hindsight binding

Exact revision/input binding is necessary but not sufficient for N3 evidence.
The contract also records explicit observation time.

Every shadow plan requires:

```text
binding.captured_at
```

Every later outcome requires:

```text
observed_process.observed_at
```

Both timestamps are normalized to UTC. The outcome joiner rejects:

```text
observed_at < captured_at
```

This catches an important class of accidental hindsight errors.

A timestamp field by itself is not cryptographic proof that a plan existed
before an outcome. Real N3 collection should therefore persist the frozen plan
to an append-only or reviewable repository/evidence location before execution
finishes. Git history, CI artifacts, or another independently timestamped
evidence store can provide that external ordering evidence.

The machine rule and the persistence rule work together:

```text
explicit temporal binding
+ immutable plan digest
+ external persistence before outcome
-> auditable anti-hindsight evidence
```
