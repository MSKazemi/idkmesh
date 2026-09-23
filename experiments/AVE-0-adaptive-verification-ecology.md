# AVE-0 — Adaptive Verification Ecology reference sweep

**Status:** synthetic mechanism test, not empirical evidence  
**Date:** 2026-09-22  
**Implementation:** `sim/adaptive_verification_ecology_sim.py`  
**Design:** `docs/algorithms/ADAPTIVE_VERIFICATION_ECOLOGY.md`  
**Retained output:** `experiments/results/AVE-0-reference-sweep.json`

## Question

Can a controller that combines:

- ecological anti-monoculture pressure;
- immune-style known-bad verifier probes;
- risk-adaptive verifier allocation;
- economic shadow-price backpressure; and
- entropy/temperature exploration

reduce correlated verification failure and duplicated work without simply replacing them with unlimited review cost?

## Important model boundary

This first simulator is deliberately small and synthetic.

Its verifier-error shape is **partial-test-like**: correct candidates are rarely rejected, while defective candidates can be missed, including through correlated family shocks. This is motivated by E017's measured one-sided partial-test panel.

That choice is not a claim that real LLM judges, human reviewers, security tools, or arbitrary validators have the same error shape.

No production routing decision should use this result.

## Baselines

### `capability-static`

- greedy capability/value routing;
- one fixed verifier;
- no learning;
- no verifier-family diversity;
- no backpressure.

### `diversity-static`

- capability routing with ecological/congestion discounts;
- fixed two-family verifier set;
- no verifier memory;
- no adaptive review pricing.

### `ave`

- posterior/Thompson-style route sampling;
- ecological niche pressure;
- entropy temperature;
- known-bad probe memory;
- correlation-aware verifier-family selection;
- risk-adaptive verifier floor;
- shadow-price verification backpressure.

## Command

```bash
python sim/adaptive_verification_ecology_sim.py \
  --seeds 40 \
  --workers 24 \
  --epochs 50 \
  --verifiers 12
```

The simulator is deterministic for a fixed seed/configuration.

## Reference result

| Metric | capability-static | diversity-static | AVE |
| --- | ---: | ---: | ---: |
| escaped defects | 71.55 | 84.05 | **39.33** |
| escaped defect rate | 0.0754 | 0.0984 | **0.0619** |
| risk-weighted escaped defects | 24.50 | 29.58 | **7.69** |
| high-risk escaped defects | 22.10 | 21.73 | **1.30** |
| false-reject rate | **0.0214** | 0.0229 | 0.0357 |
| duplicate-attempt rate | 0.2510 | 0.1771 | **0.0772** |
| task coverage | 6 / 8 | 8 / 8 | **8 / 8** |
| verifier-family concentration | 1.000 | 0.500 | **0.271** |
| review cost | **442.36** | 975.03 | 634.29 |
| compute cost | 284.20 | 320.93 | **228.20** |
| verified utility / total cost | **0.7700** | 0.3626 | 0.3997 |

## What this synthetic result says

Against the static capability baseline, AVE in this model:

- reduces escaped defects by about **45%**;
- reduces high-risk escaped defects by about **94%**;
- reduces duplicate attempts by about **69%**;
- covers all eight task classes rather than six;
- spreads verification across families instead of concentrating all checks in one family;
- spends about **43% more review cost**;
- increases the false-reject rate by about **67%** relative;
- has about **48% lower verified utility per total cost**.

Against the static-diversity policy, AVE:

- reduces escaped defects by about **53%**;
- spends about **35% less review cost**;
- has about **10% higher verified utility per total cost**.

These are properties of this synthetic environment only.

## Interpretation

The first result is deliberately not a universal "AVE wins" claim.

The current controller appears to buy **risk reduction, broader coverage, and anti-duplication** by paying more verification cost than a cheap one-verifier capability policy.

That is exactly the trade-off the next experiment must attack.

The most useful next question is not:

> Can we tune AVE until it wins this one simulator?

It is:

> Which AVE component creates the risk reduction, and which component creates the review-cost penalty?

## Required ablation matrix

Run matched-budget arms that progressively add:

1. capability-only;
2. + ecological niche pressure;
3. + entropy/Thompson exploration;
4. + verifier-family diversification;
5. + known-bad probe memory;
6. + risk-adaptive quorum;
7. + shadow-price backpressure;
8. full AVE.

For every arm, report:

- escaped defects and risk-weighted escapes;
- false rejects;
- review/compute cost;
- coverage;
- duplication;
- verifier concentration;
- utility per cost.

## Required environment sweeps

Before any production recommendation, vary:

- symmetric vs one-sided verifier error;
- verifier correlation;
- worker correlation;
- review capacity;
- probe frequency and probe representativeness;
- high-risk task prevalence;
- family quality imbalance;
- workload shift;
- provider/verifier outage;
- adversarial verifier behavior.

## Falsification gate

AVE should not progress beyond dry-run research if a simpler arm can achieve comparable risk reduction at materially lower review/human-attention cost.

The project's standard remains a Pareto improvement or an explicitly justified risk/cost trade-off, not architectural novelty.
