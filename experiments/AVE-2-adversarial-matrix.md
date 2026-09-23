# AVE-2 — Adversarial and non-stationary verification matrix

**Status:** executable synthetic falsification matrix  
**Date:** 2026-09-22  
**Tracker:** #621  
**Implementation:** `sim/adaptive_verification_ecology_ablation.py` and `sim/adaptive_verification_ecology_targeted.py`

## Purpose

The first AVE experiments suggested that verifier-family diversity contributes a
large share of the synthetic safety gain and that probe-derived positive trust
may be fragile.

AVE-2 exposes the controller to harder environments already supported by the
ablation harness.

## Added environments

- `dominant-worker-family`
  - one worker family receives a real quality advantage;
  - tests whether anti-monoculture pressure preserves weak alternatives at too
    high a cost.

- `workload-shift`
  - demand moves from documentation/onboarding-heavy work toward
    security/integration work mid-run;
  - tests adaptation rather than stationary task fit.

- `worker-family-outage`
  - one worker family disappears mid-run.

- `verifier-family-outage`
  - one verifier family disappears mid-run.

- `selective-adversarial-verifier`
  - one verifier family behaves very well on probes and correct candidates but
    accepts most live defects;
  - directly tests whether probe success can be gamed.

These extend the existing one-sided, two-sided, high-correlation, scarce-review,
and misleading-probe environments.

## Primary hypothesis under test

A smaller policy should be preferred when it preserves most of the safety gain:

```text
AVE-core =
  ecological anti-monoculture
  + posterior task-family learning
  + bounded exploration
  + verifier-family diversity
  + risk-adaptive verification
  + verification backpressure
  + price-aware routing
```

Known-bad probes remain diagnostic rather than positive trust in `AVE-core`.

## Critical comparisons

### Dominant worker family

If the dominant family is materially better, diversity pressure should not
blindly equalize usage.

Measure the price of preserving alternatives.

### Workload shift

Posterior routing and exploration should adapt without requiring manual
retuning of one static provider order.

### Worker/verifier family outage

The system should preserve useful work rather than treating previously learned
routes as permanently available.

### Selective adversarial verifier

This is the strongest current falsification case for probe-derived verifier
promotion.

A policy that trusts probe performance too strongly should be expected to fail
here.

## Metrics

Keep the matched resource ceilings and report:

- verified utility per total cost;
- escaped defects;
- risk-weighted escaped defects;
- high-risk escaped defects;
- false rejects;
- duplicate work;
- task coverage;
- worker-family concentration;
- verifier-family concentration;
- review and compute budget utilization;
- review shadow price;
- probe breach rate.

## Decision rule

Do not promote `AVE-core` because it is conceptually elegant.

Dry-run integration is justified only if it demonstrates a useful Pareto
trade-off across multiple environments and does not hide failures in the
selective-adversary case.

In particular:

- diversity is justified by independent evidence, not family count;
- probe success alone must not create positive trust;
- risk-adaptive verification must reduce risk-weighted escape, not merely raw
  task throughput;
- backpressure must improve behavior when review capacity is scarce;
- all mandatory WorkUnit/EvaluatorPlan validators remain hard constraints.
