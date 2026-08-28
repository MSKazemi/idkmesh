# CI Shadow Planner v0.1

**Status:** implemented shadow experiment; no test-skipping or integration authority

## Purpose

IDKMesh has many specialized CI workflows but no common planner that explains which checks a change affects, which checks are non-negotiable, and which additional experiments provide the most information within a bounded compute budget.

The CI Shadow Planner supplies that missing decision-support layer without changing execution:

```text
exact base/head + changed paths + reviewed policy
 -> risk classification
 -> impacted check graph
 -> mandatory dependency closure
 -> optional value/cost ordering
 -> deterministic exploration
 -> CIPlan + planning-only CIReceipt
```

Every existing workflow continues to run. The planner only records what it would select.

## Hard boundary

The planner always emits:

```text
mode = shadow
full_suite_baseline_required = true
execute = false
skip_required_checks = false
approve = false
merge = false
repository_write = false
project_spend_usd_max = 0
```

Hard gates are selected before optimization. A risk threshold may promote an optional check to mandatory, and dependency closure may add prerequisites. No score can remove a mandatory check.

## Optional-check algorithm

For impacted non-mandatory check `j`, the current explicit prior is:

```text
score(j) = P(failure | impact class)
           * consequence impact
           * expected information gain
           / (estimated runtime + queue cost)
```

The values in `config/ci-policy-v0.1.json` are labeled priors, not learned facts. Selection operates on dependency-closed bundles under `optional_seconds`. A SHA-derived ordering can use any remaining budget for bounded exploration, making replay deterministic.

The planner does not collapse correctness into this score. The score orders only already-eligible optional checks.

## Contracts

- `schemas/ci-plan-v0.1.schema.json` binds the recommendation to an exact base SHA, head SHA, policy digest, changed-file set, risk classification, budget, and check decisions.
- `schemas/ci-receipt-v0.1.schema.json` proves only that planning occurred. Its check-execution list is empty; planner runtime/resource use remains explicitly unmeasured, and it makes no claim that externally borne CI cost is zero.
- `tools/ci_shadow_planner.py` is dependency-free and rejects unknown dependencies, dependency cycles, path escapes, malformed SHAs, non-Boolean controls, and any non-zero project-spend policy.

## Evidence required before selective CI

Shadow mode should run for at least 50–100 representative PRs. Compare plans with the full CI baseline and measure:

- failure-detection recall, especially failures outside the selected set;
- changed-path coverage and unknown-impact frequency;
- mandatory-gate stability;
- optional compute minutes and queue latency;
- cancellation and duplicate-execution rates;
- flaky-test posteriors;
- escaped regressions or post-merge repairs.

The first promotion gate should require no missed high-impact failure in the evaluation cohort and a useful reduction in optional compute. Even then, protection, security, schema, governance, and planner-self changes remain mandatory, and a randomized audit slice must continue estimating selection error.

## Known limitations

- path patterns are a bootstrap impact model, not yet a semantic dependency graph;
- runtime, failure probability, impact, and information gain are hand-reviewed priors;
- check outcomes are now joined by the [CI Shadow Outcome Evaluator](CI_SHADOW_OUTCOME_EVALUATOR.md), but a representative cohort and delayed post-merge outcomes do not yet exist;
- GitHub Actions artifacts expire and are not sufficient long-term learning memory;
- repository branch protection and the external merge decision remain separate unresolved gates.

The next version should aggregate a durable evaluation cohort and learn calibrated optional-check usefulness in shadow mode. It must not learn authority or weaken hard gates.
