# Metric Uncertainty v0.1

IDKMesh should not treat every repository measurement as an exact truth value.

For a metric to influence self-evolution, it should eventually expose at least:

```text
estimate
observation model
sample size / evidence mass
uncertainty interval
assumptions
failure modes
```

## First supported model

The initial implementation supports bounded yes/no observations with a Beta-Binomial model.

For `s` observed successes among `n` trials and prior

```text
p ~ Beta(alpha_0, beta_0)
```

the posterior is

```text
p | data ~ Beta(alpha_0 + s, beta_0 + n - s)
```

with posterior mean

```text
E[p | data] = (alpha_0 + s) / (alpha_0 + beta_0 + n)
```

The current helper emits an explicitly approximate 95% interval using the posterior variance and a normal approximation. This is a bootstrap implementation, not a claim that this interval is optimal for all sample sizes.

## Intended first use

Independent-review coverage is naturally representable as a binomial observation:

```text
success = review-ready PR has >= 1 independent review
trial   = review-ready PR
```

The point ratio

```text
reviewed / ready
```

is useful but incomplete. A ratio of `1/1` and `100/100` should not carry the same uncertainty.

The uncertainty-aware representation makes that distinction explicit.

## Important boundary

Do **not** attach this model blindly to continuous, dependent, censored, or strategically generated metrics.

Examples requiring different models include:

- review latency: survival/time-to-event model;
- review concentration (HHI): sampling/bootstrap or explicit network model;
- contributor recurrence: cohort/survival model;
- verifier correlation: covariance/correlation uncertainty model;
- queue pressure: dynamical/queueing model;
- causal effects: preregistered causal design.

A generic `confidence = 0.9` field without an observation model is not sufficient evidence.

## Decision use

The current implementation is advisory. It does not change repository authority or merge gates.

A future policy may use a conservative bound rather than only a posterior mean, for example:

```text
ReviewReadiness = lower_95(review_coverage)
```

but only after calibration shows that doing so improves decisions relative to simpler baselines.

## Scientific falsification

Replace or revise the model if:

- its intervals are badly calibrated;
- observations are not approximately exchangeable/binomial;
- independence assumptions are materially violated;
- a simpler baseline predicts outcomes as well;
- decisions using the uncertainty estimate perform worse.

The purpose is not mathematical decoration. The purpose is to prevent small or biased samples from being mistaken for strong evidence.
