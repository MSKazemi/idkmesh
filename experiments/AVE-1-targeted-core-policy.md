# AVE-1 — Targeted core-policy study

**Status:** synthetic experiment design  
**Date:** 2026-09-22  
**Tracker:** #621  
**Implementation:** `sim/adaptive_verification_ecology_targeted.py`

## Why this follow-up exists

AVE-0 and the first cumulative ablation surfaced a useful design warning:

- verifier-family diversity appears to contribute a large share of the synthetic safety gain;
- adding probe-driven verifier memory does not reliably improve that result;
- unrepresentative probes can distort verifier ranking;
- backpressure and price-aware routing appear most valuable when review capacity is scarce.

Therefore the next experiment tests a **smaller core policy** rather than assuming every biologically inspired mechanism belongs in production.

## Candidate core policy

```text
AVE-core =
  ecological anti-monoculture task routing
  + posterior task-family learning
  + bounded entropy exploration
  + verifier-family diversity
  + risk-adaptive verifier floor / aggregation
  + verification shadow-price backpressure
  + price-aware routing
```

Known-bad probes remain diagnostic only in this candidate.

## Compared policies

1. `plus-verifier-diversity`
   - diversity-aware routing;
   - two verifier families;
   - no probe memory;
   - no risk-adaptive floor;
   - no review price.

2. `diversity-risk-no-probes`
   - adds risk-adaptive verifier count and aggregation;
   - still no probes/backpressure.

3. `ave-core`
   - adds review congestion price, dispatch backpressure, and price-aware routing;
   - no probe-derived verifier promotion.

4. `full-ave`
   - original full synthesis including probe memory;
   - retained as the comparator, not assumed better.

## Environments

The current targeted runner uses the same synthetic environments as the ablation harness:

- one-sided partial-test-like verifier error;
- two-sided verifier error;
- high worker/verifier correlation;
- scarce review capacity;
- misleading/easy probes.

## Primary questions

1. Does verifier-family diversity remain the dominant safety mechanism?
2. Does risk adaptation reduce **high-risk** escapes even when total escaped-defect rate moves differently?
3. Does shadow-price backpressure improve utility per cost when review is scarce?
4. Does removing probe-derived positive trust improve robustness under misleading probes?
5. Is the smaller `ave-core` easier to justify than the original full AVE?

## Decision rule

Prefer the smallest policy that preserves the useful Pareto movement.

Do not retain a mechanism because it is biologically or economically interesting.

In particular:

- probe success must not become positive production trust without representativeness evidence;
- risk-adaptive verification should be judged on risk-weighted escapes, not only raw defect count;
- backpressure should be judged under constrained review capacity, not only abundant capacity;
- diversity should be judged on correlated-failure reduction rather than family count.

## Next real-data boundary

Even a positive AVE-1 synthetic result is insufficient for production routing.

The next evidence gate remains a bounded real corpus with:

- at least two materially different worker families;
- at least two verifier families;
- independently retained negative outcomes;
- measured verifier correlation;
- real review/human-attention cost;
- no automatic merge authority.

The target product integration after that gate is **dry-run routing explanation** in the Connector Control Plane, not autonomous dispatch.
