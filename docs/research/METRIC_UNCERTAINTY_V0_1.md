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

The authoritative interval is `credible_interval_95`: the exact equal-tail 95%
credible interval of the Beta posterior, computed dependency-free by inverting
the regularized incomplete beta function (`beta-binomial-v3`). The earlier
normal-approximation interval is still emitted as `legacy_normal_interval` /
`approx_interval_95` for comparison; it is clipped to `[0, 1]`, is **not** a
bootstrap interval, and does not have exact small-sample coverage, so decisions
should read the credible interval.

### Prior-only results are not observations

A Beta posterior exists even when `n = 0`. With the default `Beta(1, 1)` prior,
that posterior has mean `0.5`, but this is a statement about the chosen prior,
not evidence that an empirical success rate of 50% was observed.

`beta-binomial-v2` therefore exposes both Bayesian and empirical semantics:

```json
{
  "model": "beta-binomial-v2",
  "successes": 0,
  "trials": 0,
  "observed_sample_size": 0,
  "empirical_rate": null,
  "evidence_status": "prior_only_no_observations",
  "posterior_mean": 0.5,
  "prior_pseudocount_mass": 2.0,
  "posterior_concentration": 2.0
}
```

When observations exist, `evidence_status` is `observed` and
`empirical_rate = successes / trials`. The posterior mean remains separately
reported because it incorporates the declared prior.

The historical `effective_sample_size` field is retained for compatibility, but
its value is the Beta posterior concentration (`alpha + beta`), which includes
prior pseudocount mass. It must not be presented as the number of empirical
observations. `observed_sample_size` is the empirical count.

This distinction is an evidence-boundary rule: prior assumptions may regularize
an estimate, but they must not manufacture observations.

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

The uncertainty-aware representation makes that distinction explicit. Likewise,
a zero-trial snapshot should remain visibly prior-only instead of being mistaken
for an observed 50% rate.

### Where it is wired

`review_metrics()` in `scripts/repository_evolution_score.py` and
`scripts/evolution_live_governor.py` attach a `review_coverage_evidence` and an
`approval_coverage_evidence` block (the `beta_binomial_summary` of ready PRs with
an independent review / approval) beside the existing point values. The point
values (`review_coverage`, `approval_coverage`) are unchanged policy inputs, and
with no ready PR they still default to `1.0` ("nothing is waiting"). That default
is a convention, not an observation: the evidence block then reports
`evidence_status: prior_only_no_observations`, `observed_sample_size: 0` and
`empirical_rate: null`, so `0` ready PRs and `100/100` reviewed ready PRs are
distinguishable. Drafts are excluded from the trials, and the two implementations
are pinned to agree by `tests/test_review_coverage_evidence.py`. No decision rule
reads the evidence blocks yet; they are advisory, as described under
[Decision use](#decision-use).

## Important boundary

Do **not** attach this model blindly to continuous, dependent, censored, or strategically generated metrics.

Examples requiring different or more explicit models include:

- review latency: survival/time-to-event model or a clearly labelled descriptive bootstrap;
- review concentration (HHI): descriptive share concentration plus a sampling/network model if population inference is attempted;
- contributor recurrence: a Beta-Binomial summary is acceptable for a bounded observed cohort proportion, but time-to-return or causal recurrence questions require cohort/survival or causal models;
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

but only after calibration shows that doing so improves decisions relative to simpler baselines. A bound from a prior-only summary is still prior-derived; consumers must inspect `evidence_status` and `observed_sample_size` before treating it as empirical support.

## Scientific falsification

Replace or revise the model if:

- its intervals are badly calibrated;
- observations are not approximately exchangeable/binomial;
- independence assumptions are materially violated;
- a simpler baseline predicts outcomes as well;
- decisions using the uncertainty estimate perform worse.

The purpose is not mathematical decoration. The purpose is to prevent small,
biased, or entirely absent samples from being mistaken for strong evidence.

See also: [Metric Contracts v0.1](METRIC_CONTRACTS_V0_1.md) for the per-metric assumptions, observables, uncertainty, prediction, baseline, failure modes and human/security constraints.
