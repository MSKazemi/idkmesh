# AVE-1 — Matched-Ceiling Component Ablation

**Status:** synthetic mechanism experiment, not empirical evidence  
**Date:** 2026-09-22  
**Implementation:** `sim/adaptive_verification_ecology_ablation.py`  
**Tests:** `tests/test_adaptive_verification_ecology_ablation.py`  
**Retained summary:** `experiments/results/AVE-1-ablation-summary.csv`  
**Parent design:** `docs/algorithms/ADAPTIVE_VERIFICATION_ECOLOGY.md`  
**Tracking:** issue #621

## Question

Which AVE components create useful safety/coordination effects, and which merely add
cost or complexity?

The AVE-0 reference sweep showed that the combined controller could reduce
synthetic defect escape while spending more review than a cheap capability-only
baseline. AVE-1 therefore decomposes the controller instead of tuning the full
system until it wins one environment.

## Experimental design

This is a **cumulative ablation ladder**:

1. `capability-only`
2. `plus-ecology`
3. `plus-posterior`
4. `plus-temperature`
5. `plus-verifier-diversity`
6. `plus-probe-memory`
7. `plus-risk-adaptive`
8. `plus-shadow-backpressure`
9. `full-ave` (adds price-aware routing)

All arms run under common review and compute **ceilings**. This is not exact
equal-spend matching: policies can consume less than the ceiling because of
backpressure, routing, or budget blocking. Results must therefore be interpreted
as a constrained-resource comparison, not as a claim that each policy spent
identical resources.

Reference run:

```bash
python sim/adaptive_verification_ecology_ablation.py \
  --seed-start 1 \
  --seeds 20 \
  --workers 24 \
  --epochs 50 \
  --verifiers 12
```

The same deterministic implementation was run over five synthetic environments:

- `one-sided-medium` — partial-test-like error shape motivated by E017;
- `two-sided-medium` — meaningful false accepts and false rejects;
- `high-correlation` — stronger worker/verifier family shocks;
- `scarce-review` — verification capacity reduced to 60% of the reference;
- `misleading-probes` — known-bad probes weakly aligned with live verification
  failure.

The 20-seed runs were executed separately by environment to fit the execution
window; policy definitions, seeds, budgets, and equations were unchanged.

## Selected one-sided result

| Policy | Escaped defects | High-risk escapes | False-reject rate | Duplicate rate | Review cost | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| capability-only | 62.55 | 24.35 | 0.0224 | 0.3833 | 530.67 | **0.6194** |
| plus-ecology | 69.55 | 18.35 | **0.0219** | 0.1735 | 513.51 | 0.5449 |
| plus-posterior | 61.50 | 13.05 | 0.0243 | 0.1336 | 485.01 | 0.5837 |
| plus-temperature | 71.70 | 15.10 | 0.0215 | 0.1599 | **481.99** | 0.5397 |
| plus-verifier-diversity | **21.95** | 5.00 | 0.0450 | 0.1592 | 743.88 | 0.3327 |
| plus-probe-memory | 43.25 | 8.20 | 0.0349 | 0.1587 | 743.84 | 0.3354 |
| plus-risk-adaptive | 42.80 | 1.15 | 0.0354 | 0.1565 | 743.93 | 0.3531 |
| plus-shadow-backpressure | 36.00 | 0.85 | 0.0359 | 0.0794 | 643.03 | 0.3573 |
| full-ave | 37.70 | **0.70** | 0.0311 | **0.0725** | 638.86 | 0.3795 |

These are means over 20 synthetic seeds. Lower is desirable for escaped defects,
high-risk escapes, false rejects, duplicates, and review cost; higher is
desirable for verified utility per cost. No row is a universal winner.

## What the cumulative ladder says

### 1. Ecology is useful for spread, not sufficient for safety

Adding ecological niche/congestion pressure expands verified task coverage from
5.75/8 to 8/8 and cuts duplication from 0.383 to 0.174 in the reference
environment, but escaped defects rise from 62.55 to 69.55.

This rejects any simple claim that "more ecological diversity" is automatically
safer.

### 2. Posterior task-family learning recovers some efficiency

Adding posterior/Thompson-style route learning lowers escaped defects from 69.55
to 61.50 and raises verified utility per cost from 0.545 to 0.584 in the
one-sided environment while preserving full task coverage.

The result is still synthetic and does not establish that the posterior model is
calibrated for real coding agents.

### 3. Entropy/temperature exploration is not yet justified as a safety mechanism

The current temperature layer does not consistently improve defect escape. In
the one-sided environment, escaped defects increase from 61.50 to 71.70 after
adding temperature sampling.

Temperature remains a useful exploration hypothesis, but its present form
should not be treated as an accepted production component.

### 4. Verifier-family diversity creates the largest general escape reduction

The largest step change in ordinary defect escape occurs when verifier-family
diversity is added:

- one-sided: 71.70 -> 21.95 escaped defects;
- two-sided: 71.70 -> 21.95;
- high-correlation: 132.70 -> 48.00;
- scarce-review: 65.50 -> 12.50.

This also increases review cost and, especially in the two-sided environment,
raises false rejection. The conclusion is therefore not "always use more
verifiers"; it is that **heterogeneous verifier allocation is the strongest
general safety lever in this synthetic family, but its cost and sidedness tradeoff
must be controlled**.

### 5. Probe-derived positive trust is not robust enough

Adding known-bad probe memory after verifier diversity worsens ordinary defect
escape in several environments. Examples:

- one-sided: 21.95 -> 43.25;
- high-correlation: 48.00 -> 91.55;
- misleading-probes: 21.95 -> 33.15.

The probe breach rate itself remains useful diagnostic evidence. What is not
supported is using probe success as automatic **positive routing trust** before
probe representativeness is demonstrated.

### 6. Risk-adaptive quorum targets the failure that matters most

The risk-adaptive step mainly changes **high-risk** escapes:

- one-sided: 8.20 -> 1.15;
- high-correlation: 15.75 -> 3.25;
- scarce-review: 4.80 -> 0.70.

It does not minimize total escaped defects, and in two-sided settings it can
increase rejection cost. This supports task/risk-dependent quorum rather than one
universal aggregation rule.

### 7. Shadow-price backpressure removes overload without pretending it is free

Adding review-capacity shadow pricing/backpressure eliminates or nearly
eliminates budget blocking, materially reduces duplicate attempts, and spends
less review than the saturated risk-adaptive arm.

It does so partly by dispatching fewer attempts. This is the intended economic
mechanism: when verification is scarce, AVE should reduce optional generation
rather than accumulate untrusted work.

## Cross-environment summary

The qualitative findings survive the five tested environments:

- **verifier diversity** is the strongest broad defect-escape reducer;
- **risk adaptation** is the strongest high-risk-escape reducer;
- **backpressure** is useful when verification capacity is a binding resource;
- **positive trust from probes is fragile** when probes are unrepresentative;
- **ecology and entropy are not safety guarantees** and must earn their place
  through outcome evidence.

However, the current sweep does **not** complete all of issue #621. It does not
yet provide:

- low/medium/high grids for verifier correlation;
- low/medium/high grids for worker correlation;
- dominant-provider/family-quality imbalance;
- workload distribution shift;
- provider/verifier outage;
- selective adversarial verifier behavior.

## Decision

Continue AVE research, but simplify the next candidate.

Do not promote the full cumulative stack directly into the Connector Control
Plane. Run the targeted AVE-core experiment without probe-derived positive trust,
then keep probes as diagnostic/negative evidence until representativeness is
measured.

## Evidence boundary

This experiment is a deterministic synthetic mechanism test. It does not show
that AVE improves real coding-agent outcomes, real reviewer panels, or production
software reliability. Production integration remains gated by issue #621 and a
future held-out real WorkUnit cohort.
