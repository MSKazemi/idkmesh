# CI Shadow Outcome Evaluator v0.1

**Status:** evidence collection only; no test-selection or merge authority

## Purpose

The evaluator closes the first feedback loop around the CI Shadow Planner. After the unfiltered `PR Gate` completes, it joins the plan and planning receipt to GitHub check runs for the same immutable head SHA:

```text
exact-SHA plan + planning receipt + check runs + reviewed mappings
  -> normalized observation
  -> mapped failures, misses, attribution gaps, and modeled savings
  -> non-authoritative evaluation artifact
```

`config/ci-observation-policy-v0.1.json` qualifies mappings by workflow and check name. This prevents common job names such as `test` or `validate` from being silently conflated across workflows. Unknown failures remain explicit attribution gaps.

## Measurement semantics

A mapped failure is covered when at least one logical check associated with the observed workflow check was selected by the plan. Recall is calculated only over mapped failures. Unmapped failures are reported separately and block any future promotion claim.

The required baseline is the protected `PR Gate` matrix (`gate (3.11)` and `gate (3.13)`). Other observed jobs may still be pending when the snapshot is taken; their count is recorded. Estimated seconds come from planner priors and are labeled **modeled**, not measured GitHub Actions usage.

## Trust and authority boundary

The `workflow_run` job checks out the exact trusted default-branch revision associated with the event. It downloads the candidate plan artifact and GitHub API results only as data, validates their schemas plus exact-SHA and digest bindings, and has read-only `actions`, `checks`, and `contents` permissions. The evaluator always emits:

```text
promotion.eligible = false
execute = false
skip_required_checks = false
approve = false
merge = false
repository_write = false
```

Every existing workflow continues to run. These artifacts cannot satisfy branch protection or authorize integration.

## Next evidence gate

Retain 50–100 representative complete observations, including failures. Before proposing selective execution, add a reviewed cohort aggregator, measured runtime/cancellation data, stable failure attribution, delayed post-merge regression signals, and a randomized audit lane. Require no missed high-impact failure; any policy change remains a separate reviewed PR.
