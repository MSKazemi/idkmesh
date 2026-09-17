# R1 low-diversity threshold robustness audit

**Issue:** #13  
**Evidence level:** synthetic mechanism sensitivity, not real coding-agent performance

## Purpose

[`R1_COLLECTIVE_SCALING.md`](../docs/research/R1_COLLECTIVE_SCALING.md) defines a
downstream low-diversity analysis over the synthetic `homogeneous` R1 arm. For each
adjacent swarm-size interval it summarizes the paired per-seed marginal
verified-success slope with a normal-approximation 95% interval and uses that
interval to describe positive, negative, or unresolved directions.

That construction is transparent, but the reference run has only ten deterministic
seed replications. A directional label that exists only because of one interval
approximation should not be treated as stronger evidence than it is. This audit
adds a second, independently constructed interval over the **same paired seed-level
estimand** and reports where the directional interpretation agrees or disagrees.
It does not modify the frozen R1 generator or replace the original analysis.

## Estimand

For adjacent configured sizes `N_a < N_b`, seed `s`, and verified-success rate
`V(N, s)`, the existing analyzer defines

```text
g(N_a -> N_b, s) = [V(N_b, s) - V(N_a, s)] / (N_b - N_a)
```

and, from the second interval onward,

```text
delta_g(t, s) = g(t, s) - g(t - 1, s)
```

The robustness audit keeps those definitions and the same fail-closed pairing rule:
all compared cells must contain the same ordered seed set. It reuses the existing
R1 extraction/validation path rather than introducing another interpretation of the
result payload.

## Secondary interval construction

For each vector of paired `g` or `delta_g` values, the audit performs 5,000
with-replacement bootstrap resamples of size `n` and records the 2.5th and 97.5th
percentiles of the resampled means.

The pseudorandom stream is deterministically seeded from the transition identity and
observed values. The same repository input therefore replays to the same audit. The
bootstrap is deliberately dependency-free and does not affect the simulation RNG or
the committed R1 reference artifacts.

The directional classifications use the same sign convention as the base analyzer:

- `positive` when the whole interval is above zero;
- `negative` when the whole interval is below zero;
- `uncertain` when the interval includes zero.

A **robust directional label** is emitted only when the original normal interval and
the bootstrap interval agree on `positive` or `negative`. Any disagreement, including
one method being directional while the other includes zero, is retained as
`uncertain`.

For issue #13's low-diversity hypothesis this yields two conservative markers:

- `supported_diminishing_return_robust`: the normal and bootstrap intervals for
  `delta_g` are both strictly negative;
- `supported_negative_return_robust`: the normal and bootstrap intervals for `g`
  are both strictly negative.

This is a sensitivity rule, not a new hypothesis test or an acceptance threshold for
IDKMesh policy.

## Why disagreement is useful

With a very small finite sample, a symmetric normal approximation can exclude zero
while a bootstrap interval still reaches zero. For example, paired marginal effects
`[0.0, 0.1, 0.1]` have a normal-approximation lower bound slightly above zero, while
the empirical bootstrap can resample the zero observation often enough for its
lower percentile to be exactly zero. The regression suite fixes this example so the
audit must preserve the disagreement rather than silently choosing the more
confident method.

The point is not that the bootstrap is automatically more correct. The point is that
method sensitivity is evidence about uncertainty and should stay visible.

## Reproduction

From the repository root:

```bash
python -m randomness_lab.r1_threshold_robustness \
  --tasks 200 \
  --trials 10 \
  --swarm-sizes 1,2,5,10 \
  --seed 42 \
  --output /tmp/r1-threshold-robustness.json \
  --report /tmp/r1-threshold-robustness.md
```

The CLI regenerates the seeded R1 mechanism input and runs the robustness audit
downstream. The focused regression coverage is in
[`tests/test_r1_threshold_robustness.py`](../tests/test_r1_threshold_robustness.py).

## Interpretation limits

This audit intentionally does **not** promote the synthetic result to a real scaling
law.

- The `homogeneous` arm is a simulator proxy for low diversity, not an empirical
  sample of contributors, model families, or production coding agents.
- The ten reference seeds are deterministic replications of one synthetic mechanism;
  they are not an independently sampled population of real software tasks.
- The percentile bootstrap has approximate finite-sample coverage and can itself be
  unstable at small `n`; 5,000 resamples reduce Monte Carlo noise but do not create
  information absent from the underlying seed sample.
- Neither interval family is multiplicity adjusted across difficulties, swarm-size
  transitions, or the several reported threshold questions.
- Agreement between two interval constructions is a robustness signal, not proof of
  external validity. Disagreement is a reason to weaken the directional wording,
  not evidence for the opposite direction.
- Real confirmation still requires the prospectively frozen, independently verified
  software-task evidence described by issues #13, #30, and #70.

The scientific value of this layer is therefore narrow: it makes one existing
synthetic conclusion more falsifiable by exposing whether its direction depends on
the interval approximation used to summarize the same paired seeds.
