# R1 low-diversity marginal threshold

Issue: [#13](https://github.com/MSKazemi/idkmesh/issues/13)

Status: **synthetic mechanism analysis; issue #13 remains open**.

This document makes the first hypothesis in issue #13 machine-readable without
changing the frozen R1 collective-scaling generator or its reference artifact:

> increasing population size under low diversity can show diminishing or negative
> marginal returns after a measurable threshold.

The implementation is
[`randomness_lab/r1_low_diversity_threshold.py`](../../randomness_lab/r1_low_diversity_threshold.py).
It consumes the seeded output of
[`randomness_lab/r1_scaling.py`](../../randomness_lab/r1_scaling.py) rather than
modifying that generator. This preserves the existing frozen R1 reference hash and
separates a new interpretation from the evidence producer that generated the data.

## Operationalization

### Low-diversity proxy

The existing R1 `homogeneous` family is the proxy for low diversity. Its workers use
the same strategy family, so it is intentionally a strong synthetic replication
condition. It is **not** a measurement of contributor diversity, model-family
diversity, demographic diversity, or real coding-agent diversity.

Only the `flat` topology is used. If the analyzer receives a schema-v2 R1 result that
also contains role-specialized or task-DAG cells, those cells are ignored for this
question. That keeps the analysis aligned with the original population-size axis and
prevents topology changes from being mistaken for a diversity effect.

### Marginal return

For adjacent configured sizes `N_a < N_b`, seed `s`, and verified-success rate
`V(N, s)`, define

```text
g(N_a -> N_b, s) = [V(N_b, s) - V(N_a, s)] / (N_b - N_a)
```

This is the paired verified-success-rate gain per additional worker. Pairing is valid
only when every compared cell contains the same ordered seed set; the analyzer fails
closed if that condition is violated.

The configured intervals need not have equal width (the reference grid is 1, 2, 5,
10). Dividing by `N_b - N_a` makes each value an average discrete slope per added
worker over that interval. It does **not** identify a continuous point derivative or
a threshold between unobserved population sizes.

For every transition after the first, the change in marginal gain is

```text
delta_g(t, s) = g(t, s) - g(t - 1, s)
```

The analyzer summarizes `g` and `delta_g` across seeded replications with the sample
mean, sample standard deviation, min/max, and a descriptive normal-approximation 95%
interval.

## Threshold labels

The labels are deliberately conservative and descriptive:

- **supported diminishing return** — the 95% interval for `delta_g` is entirely
  below zero;
- **supported negative return** — the 95% interval for `g` is entirely below zero;
- **interval not strictly positive** — the interval for `g` overlaps or falls below
  zero. This is an uncertainty marker, not evidence that the underlying gain is zero.

The first swarm size at which each condition occurs is emitted per difficulty. A
missing threshold means only that the configured seeded synthetic run did not resolve
one at the tested sizes. It does not establish that no threshold exists.

These intervals are **not formal hypothesis tests**, have no multiplicity correction,
and should not be interpreted as confidence statements about a population of real
software tasks or agents. Their role is to make the simulator's threshold semantics
reproducible and auditable.

## Reproducible use

Run the default R1 configuration and print the report:

```bash
python -m randomness_lab.r1_low_diversity_threshold
```

Write machine-readable and Markdown outputs:

```bash
python -m randomness_lab.r1_low_diversity_threshold \
  --output /tmp/r1-low-diversity-threshold.json \
  --report /tmp/r1-low-diversity-threshold.md
```

A smaller diagnostic run can override the task count, trial count, seed, and swarm
sizes:

```bash
python -m randomness_lab.r1_low_diversity_threshold \
  --tasks 25 --trials 3 --seed 17 --swarm-sizes 1,2,5
```

`R1ScalingConfig` remains the source of validation for those overrides.

## Integration and evidence boundaries

This analysis deliberately reuses R1's `verified_success_rate`, raw deterministic
seed replications, population sizes, and homogeneous family. It does not create a
second simulator or a second success metric. The generator remains unchanged, so
[`tests/test_r1_scaling_reference.py`](../../tests/test_r1_scaling_reference.py)
continues to protect the frozen reference artifact byte-for-byte.

The analyzer adds a narrower view than the existing R1 marginal curves: R1 reports the
success-rate change between adjacent sizes, while this module normalizes that change
by the number of additional workers and then compares consecutive paired marginals.
That is the quantity needed to state a measurable diminishing-return threshold.

The broader evidence record still matters:

- [`R1_COLLECTIVE_SCALING.md`](R1_COLLECTIVE_SCALING.md) establishes the synthetic
  population-size mechanism and its current reference curves.
- [`E032 Population Scaling`](../../experiments/E032-population-scaling.md) found no
  negative-return population regime in its tested arms; fixed-budget and free-budget
  population changes behaved differently.
- [`E040 Diversity Correlation Threshold`](../../experiments/E040-diversity-correlation-threshold.md)
  isolates a different axis: retained worker independence as error correlation
  changes.

Those results should not be collapsed into one claim. Population size, resource
budget, strategy diversity, error correlation, and coordination topology are distinct
experimental factors.

## What would be needed to close issue #13

This analyzer does not close issue #13. A real scaling claim still requires the
prospectively frozen evidence boundary already described in the R1 program: held-out
software tasks, pinned agents/models and configurations, matched resource accounting,
independent verification, and measured compute/time/reviewer costs. The threshold
rule should be frozen before those outcomes are inspected so that a real result can
confirm, fail to resolve, or falsify the hypothesis without post-hoc threshold
selection.
