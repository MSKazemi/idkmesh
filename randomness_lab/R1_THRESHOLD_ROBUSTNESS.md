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
seed replications and emits several directional questions across difficulties and
swarm-size transitions. A directional label should therefore not become stronger
merely because one interval approximation or one member of a multiple-comparison
family happens to exclude zero.

This audit keeps the original mean-effect analysis intact and adds two conservative
checks:

1. a deterministic percentile bootstrap over the **same paired seed-level mean
   estimand**;
2. an exact sign test for directional consistency, with Holm-Bonferroni correction
   across every marginal and change-from-previous-marginal question emitted by the
   audit.

It does not modify the frozen R1 generator or replace the original analysis.

## Mean-effect estimand

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
bootstrap is dependency-free and does not affect the simulation RNG or the committed
R1 reference artifacts.

The directional classifications use the same sign convention as the base analyzer:

- `positive` when the whole interval is above zero;
- `negative` when the whole interval is below zero;
- `uncertain` when the interval includes zero.

The existing `robust_classification` remains intentionally backward-compatible: it
is directional only when the original normal interval and the bootstrap interval
agree on `positive` or `negative`. Any disagreement remains `uncertain`.

## Exact sign corroboration

The v2 audit additionally computes a classical two-sided exact binomial sign test for
each paired vector.

- zero-valued seed effects are omitted from the sign count;
- positive and negative non-zero effects are counted separately;
- under the null, positive/negative signs are treated as equally likely;
- the reported two-sided p-value is twice the smaller exact binomial tail, capped at
  `1.0`.

This is **not the same estimand as the mean interval**. The sign test asks whether the
non-zero seed-level effects show consistent direction (a median/sign-balance
question); it deliberately ignores effect magnitude. It is therefore used only as
corroboration, never as a replacement for the paired mean analysis.

Its exactness is conditional on the sign-test assumptions. In particular, the seed
signs must be independently/exchangeably distributed under the null for the usual
p-value interpretation to hold. Deterministic simulator seeds are not automatically
an empirical sample from a real task population.

## Multiplicity control

The audit defines one explicit family containing **all** sign tests emitted across:

- every configured difficulty;
- every adjacent swarm-size marginal `g`;
- every available change-from-previous-marginal `delta_g`.

Raw sign-test p-values are adjusted with the Holm-Bonferroni step-down procedure at
familywise `alpha = 0.05`. This controls family-wise error under valid individual
p-values without requiring independence among the tests themselves.

A `familywise_robust_classification` is directional only when all three conditions
hold:

1. normal and bootstrap intervals agree on a strict direction;
2. the exact sign test points in the same direction;
3. the Holm-adjusted sign-test p-value is at most `0.05`.

The corresponding threshold markers are:

- `supported_diminishing_return_familywise` for a familywise-negative `delta_g`;
- `supported_negative_return_familywise` for a familywise-negative `g`.

The previous interval-only robust fields remain in the payload. The machine-readable
audit version is bumped to `schema_version = 2` so downstream consumers can detect
the added multiplicity semantics.

## Why the stricter layer is useful

Two different uncertainty problems are now visible instead of being collapsed:

- **method sensitivity:** a normal approximation may exclude zero while the
  bootstrap reaches zero;
- **multiple questioning:** even a raw directional sign test can become
  insufficient once several thresholds are inspected together.

For example, six identical positive non-zero seed effects yield a raw two-sided sign
p-value of `0.03125`. If that test sits in a three-question family with another
comparably small p-value, Holm adjustment raises the adjusted value above `0.05`.
The interval direction is retained, but the stronger familywise label stays
`uncertain`. The regression suite fixes this case so future changes cannot silently
turn raw significance into familywise evidence.

Conversely, ten same-direction non-zero effects in a one-question family produce an
exact two-sided sign p-value of `0.001953125`, allowing the familywise layer to
corroborate an interval-robust direction when the other requirements also hold.

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
downstream. Focused regression coverage is in
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
- The exact sign test ignores magnitudes and tests directional/median consistency,
  not the mean effect summarized by the intervals. Zero effects are omitted.
- Holm-Bonferroni controls the declared family only if the underlying sign-test
  p-values are valid. It does not repair dependence or exchangeability violations in
  the simulator seeds, and it does not establish external validity.
- Agreement across all three layers is a robustness signal, not proof of a real
  population effect. Disagreement is a reason to weaken the wording, not evidence
  for the opposite direction.
- Real confirmation still requires the prospectively frozen, independently verified
  software-task evidence described by issues #13, #30, and #70.

The scientific value of this layer is narrow but concrete: it makes one existing
synthetic threshold analysis less vulnerable to both interval-method sensitivity and
unadjusted multiple questioning while preserving every underlying seed-level result.
