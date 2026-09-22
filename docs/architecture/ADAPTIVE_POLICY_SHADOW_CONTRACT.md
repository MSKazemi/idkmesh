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
