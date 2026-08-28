# Sequential Evidence Kernel

Status: experimental mathematical control-plane primitive. It is read-only and has no repository integration authority.

## Why this exists

IDKMesh already has Bayesian historical evidence, correlation-aware verification, Pareto/NSGA portfolio ranking, multiplicative weights, UCB exploration, entropy/diversity, graph unlock value, and Lyapunov-style homeostasis.

A different failure mode appears when the system looks at the same evolving experiment repeatedly. A fixed-horizon interval used after every observation is vulnerable to optional stopping: eventually, noise alone can cross a nominal threshold.

The sequential evidence kernel makes the observation rule explicit and testable.

## 1. Anytime-valid bounded confidence sequence

For observations `X_t` sharing a common mean `mu` and bounded in `[a,b]`, allocate the total error probability `delta` over time as

```text
delta_t = delta / (t (t + 1))
```

because

```text
sum_{t=1..infinity} 1 / (t (t + 1)) = 1.
```

At each time `t`, use the two-sided Hoeffding radius

```text
r_t = (b-a) * sqrt( log(2/delta_t) / (2t) ).
```

A fixed-time Hoeffding bound fails with probability at most `delta_t`; the union bound therefore gives simultaneous coverage over all positive integer observation times with total failure probability at most `delta` under the stated bounded common-mean assumptions.

That means a caller may inspect the sequence and stop at a data-dependent time without silently converting a 5% rule into repeated 5% tests.

This is intentionally a simple, auditable construction. It is not claimed to be the tightest possible confidence sequence.

## 2. Paired experiment effects

When a candidate and baseline are evaluated on the same task, seed, or benchmark unit, define

```text
D_t = candidate_t - baseline_t,   D_t in [-1,1].
```

The confidence sequence is applied to `D_t`, not to two independent point estimates. Pairing removes shared nuisance variation and produces a direct uncertainty interval for the improvement.

A candidate may be nominated only when all of the following are true:

```text
hard_guard_ok
AND n >= minimum_samples
AND lower_confidence_bound > minimum_effect.
```

The output is `experiment_candidate`, never `merge`, `approve`, or `activate`.

## 3. Off-policy evidence

For logged reward `R_i`, behavior probability `b_i`, and proposed target probability `pi_i`, the inverse-propensity contribution is

```text
Y_i = (pi_i / b_i) * R_i.
```

The implementation also reports Kish effective sample size

```text
ESS = (sum w_i)^2 / sum(w_i^2).
```

This exposes poor overlap and weight concentration even when the raw event count is large.

### Clipping rule

Large importance weights are commonly clipped for variance control, but clipping changes the estimand and generally introduces bias. IDKMesh therefore uses a fail-closed rule:

```text
if any importance ratio is clipped:
    target-policy confidence claim = false
    experiment nomination = disabled
```

The clipped sequence remains useful telemetry, but it cannot be presented as an anytime-valid interval for the target policy.

## 4. Non-compensation invariant

Statistical confidence and governance safety are conjunctive, not substitutable.

```text
strong evidence + failed hard guard = GUARDED
```

This is the same authority separation used elsewhere in the repository. In particular, `main` being unprotected is not a statistical variable and cannot be compensated for by more samples, a higher posterior, or a larger estimated effect.

## 5. Assumptions and non-goals

The Hoeffding construction assumes bounded observations with a common expectation under an independent/common-mean or corresponding martingale model. Unknown dependence, distribution drift, adversarial adaptation, and misspecified logging propensities require separate modeling; the module does not manufacture independence.

This layer does not:

- grant GitHub write, approval, or merge permission;
- change branch protection;
- activate autonomous compute;
- infer causal effects from arbitrary observational metadata;
- treat clipped IPS as unbiased target-policy evidence;
- replace independent verification or human integration review.

## 6. Future extensions

Only after enough real evidence exists should tighter methods be compared, for example mixture/e-process confidence sequences, empirical-Bernstein martingale bounds, doubly robust off-policy estimators, and distributionally robust policy comparison. Those should be benchmarked against this transparent baseline rather than replacing it by assertion.

## Executable surfaces

- `scripts/sequential_evidence.py` — deterministic mathematical primitives and demo;
- `tests/test_sequential_evidence.py` — optional-stopping/error-budget, non-compensation, overlap, clipping, and ESS invariants;
- `.github/workflows/sequential-evidence-kernel.yml` — path-scoped, contents-read CI on Python 3.11 and 3.13.
