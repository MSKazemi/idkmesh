# Coordination Criticality and Finite-Difference Response

**Status:** synthetic mechanism experiment implemented as E020

**Issue:** [#49](https://github.com/MSKazemi/idkmesh/issues/49)

## Research question

Can a small controlled load perturbation reveal a fragile verification queue
before an absolute utilization or backlog threshold does?

Statistical physics motivates the question through susceptibility,

```text
chi_X = d E[X] / d h
```

and, for particular equilibrium systems, fluctuation-response relationships.
IDKMesh is not assumed to be an equilibrium system. E020 uses only the empirical
finite difference

```text
chi_(y,u) ~= (E[y | u + delta_u] - E[y | u]) / delta_u
```

as an engineering measurement. A steep queue response is not evidence of a
thermodynamic phase transition.

## Model

[`../../experiments/criticality_susceptibility.py`](../../experiments/criticality_susceptibility.py)
is a discrete two-stage queue:

```text
20 generator slots
 -> worker queue (capacity 12/tick)
 -> verifier queue (capacity 8/tick)
 -> verified outcome
```

Each operating point is evaluated with three variants:

1. control: constant base load;
2. probe: `+5%` load for 40 ticks, followed by recovery;
3. stress: the same `+5%` increase remains active through the horizon.

For a seed, all variants share the exact arrival, defect, and detection draws.
This common-random-number design makes the paired difference attributable to
the load schedule. It does not make the synthetic workload representative of a
real community or production verifier.

The experiment records queue mean, peak and variance; latency; verified
throughput; escaped synthetic failures; and recovery time. Responses are
reported with two-sided normal-approximation 95% intervals across seeds. Raw
trial records and per-tick queue histories remain in the compressed result.

## Ordinary baselines

E020 compares its predeclared superlinear-response alert against:

- offered load reaching 90% of verifier capacity;
- baseline mean backlog reaching one verifier window.

The future-stress label is the first load cell where at least half of matched
sustained-stress runs end with a verifier-capacity-sized backlog and positive
post-probe growth. This is a benchmark definition, not a universal overload
criterion.

## Result and use

The 40-seed result is documented in
[`../../experiments/E020-coordination-criticality.md`](../../experiments/E020-coordination-criticality.md).
Susceptibility warned earlier in this grid, but at the cost of false alarms; it
did not dominate the utilization baseline. The useful control-plane conclusion
is therefore conditional:

> A bounded probe may expose fragility, but it should remain one signal beside
> queueing baselines, with its alert cost calibrated on representative work.

The signal can inform issue #14 verification-scaling experiments. It cannot
grant acceptance, deployment, or merge authority.

## Follow-up boundary

The next experiment should add worker churn and heterogeneous cells only as a
new, separately reviewed cohort. E020 intentionally keeps the first result
small enough to reproduce and falsify.
