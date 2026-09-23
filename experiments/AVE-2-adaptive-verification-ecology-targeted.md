# AVE-2 — Targeted AVE-Core Study

**Status:** synthetic targeted mechanism experiment, not empirical evidence  
**Date:** 2026-09-22  
**Implementation:** `sim/adaptive_verification_ecology_targeted.py`  
**Tests:** `tests/test_adaptive_verification_ecology_targeted.py`  
**Retained summary:** `experiments/results/AVE-2-targeted-summary.csv`  
**Parent experiment:** `experiments/AVE-1-adaptive-verification-ecology-ablation.md`  
**Tracking:** issue #621

## Question

After AVE-1 showed that probe-derived positive trust is not robust across all
synthetic environments, can a smaller **AVE-core** retain most of the useful
risk/capacity behavior without using known-bad probes to positively rank
verifiers?

## Policies

The targeted study compares four policies:

1. `plus-verifier-diversity`
   - the strongest general defect-escape arm from AVE-1;

2. `diversity-risk-no-probes`
   - verifier diversity + risk-adaptive verifier floor/quorum;
   - no probe memory;
   - no shadow-price backpressure;

3. `ave-core`
   - ecological anti-monoculture routing;
   - posterior task-family learning;
   - bounded entropy exploration;
   - verifier-family diversity;
   - risk-adaptive verifier floor/quorum;
   - verification shadow-price backpressure;
   - price-aware routing;
   - **no positive probe-derived verifier trust**;

4. `full-ave`
   - the original cumulative AVE including probe memory.

The same five AVE-1 environments and the same 20-seed, 24-worker, 50-epoch,
12-verifier setup are used.

## Targeted results

### One-sided medium

| Policy | Escaped defects | High-risk escapes | False-reject rate | Duplicate rate | Review cost | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| verifier diversity | **21.95** | 5.00 | 0.0450 | 0.1592 | 743.88 | 0.3327 |
| diversity + risk, no probes | 42.55 | 1.70 | 0.0348 | 0.1572 | 743.93 | 0.3514 |
| **AVE-core** | 38.95 | 0.85 | 0.0349 | 0.0762 | **635.60** | **0.3822** |
| full AVE | 37.70 | **0.70** | **0.0311** | **0.0725** | 638.86 | 0.3795 |

The result is a tradeoff. Verifier diversity alone minimizes ordinary escaped
defects, while AVE-core/full AVE sacrifice some ordinary escape performance to
reduce high-risk escapes, duplication, and review saturation.

### High-correlation

| Policy | Escaped defects | Escape rate | High-risk escapes | Review cost | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| verifier diversity | **48.00** | **0.0858** | 10.05 | 743.87 | 0.2995 |
| diversity + risk, no probes | 83.55 | 0.1314 | 3.50 | 743.93 | 0.3185 |
| **AVE-core** | 74.15 | **0.1271** | 2.80 | **636.16** | **0.3409** |
| full AVE | 74.85 | 0.1313 | **2.55** | 639.39 | 0.3333 |

AVE-core is slightly better than full AVE on ordinary escape rate, review cost,
and utility efficiency in this high-correlation environment, while full AVE is
slightly better on high-risk escapes.

### Scarce review

| Policy | Escaped defects | High-risk escapes | Duplicate rate | Review cost | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| verifier diversity | **12.50** | 2.65 | 0.1637 | 446.25 | 0.3250 |
| diversity + risk, no probes | 25.65 | 1.10 | 0.1636 | 446.31 | 0.3454 |
| AVE-core | 26.35 | 0.90 | 0.0249 | **415.37** | 0.4200 |
| **full AVE** | 24.00 | **0.65** | **0.0231** | 419.20 | **0.4245** |

Full AVE remains slightly stronger than AVE-core in this synthetic scarce-review
case. This is important negative evidence against over-simplifying the controller
from one environment.

### Misleading probes

| Policy | Escaped defects | Escape rate | High-risk escapes | Review cost | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| verifier diversity | **21.95** | **0.0373** | 5.00 | 743.88 | 0.3327 |
| diversity + risk, no probes | 42.55 | 0.0653 | 1.70 | 743.93 | 0.3514 |
| **AVE-core** | 38.95 | **0.0644** | **0.85** | 635.60 | **0.3822** |
| full AVE | 40.10 | 0.0670 | 1.30 | 637.11 | 0.3741 |

When probes are intentionally weakly aligned with live verification failure,
AVE-core is more robust than full AVE on escape rate, high-risk escapes, review
cost, and utility efficiency.

## Interpretation

The targeted experiment does **not** establish one universal best policy.

It supports a narrower architectural correction:

> Known-bad probes are useful evidence, but their success should not automatically
> create positive verifier trust until probe performance is shown to predict
> held-out real verification outcomes.

That allows probes to remain valuable for:

- gate-audit diagnostics;
- breach detection;
- negative/veto evidence;
- representativeness studies;
- verifier calibration research.

The result also reinforces a separation that is useful for the future product:

```text
general defect escape
  -> verifier-family diversity is a strong lever

high-risk defect escape
  -> risk-adaptive verifier floor/quorum is a strong lever

verification overload / duplicate generation
  -> shadow-price backpressure is a strong lever

positive verifier trust
  -> requires held-out outcome calibration, not probe success alone
```

## Current AVE-core candidate

The current research candidate for a future **dry-run-only** control-plane
comparison is:

```text
AVE-core =
  ecological anti-monoculture routing
  + posterior task-family learning
  + bounded entropy exploration
  + verifier-family diversity
  + risk-adaptive verifier floor/quorum
  + verification shadow-price backpressure
  + price-aware routing
```

This does not mean every listed component is independently proven beneficial.
In particular, the current entropy/temperature mechanism did not show a clear
safety gain in AVE-1. It remains in AVE-core as an exploration mechanism to test,
not as an accepted safety mechanism.

## Decision

1. Keep the full AVE proposal as a research superset.
2. Use AVE-core as the smaller candidate for future dry-run comparison.
3. Do not use known-bad probe success as positive production trust.
4. Keep verifier diversity, risk adaptation, and capacity backpressure as the
   highest-priority mechanisms for further testing.
5. Do not activate live routing until the remaining issue #621 environment
   sweeps and a held-out real WorkUnit cohort are complete.

## Evidence boundary

AVE-2 is still synthetic. It provides design-selection evidence inside the
simulator, not evidence that either AVE-core or full AVE improves real software
development.
