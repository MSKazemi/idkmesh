# PHY-0A — Stationary-environment falsification for Physarum routing

**Status:** synthetic negative-control mechanism test, not empirical evidence  
**Date:** 2026-10-07  
**Implementation:** `sim/physarum_compute_routing_sim.py`  
**Parent research issue:** #630  
**Retained output:** `experiments/results/PHY-0A-stationary-sweep.json`

## Question

Does the Physarum-inspired policy still earn its added path diversity when the admitted
network does **not** change?

This is a falsification-oriented control for PHY-0. The graph, priors, route costs,
strategies, seeds, and task volume are unchanged. The only change is that every edge
keeps its pre-shift reliability for all 80 epochs.

The simulator still reports `pre_shift_success_rate` and
`post_shift_success_rate` for output compatibility. In this scenario epoch 40 is only
an observation-window boundary; **no reliability shift occurs there**.

## Command

```bash
python sim/physarum_compute_routing_sim.py \
  --scenario stationary \
  --seeds 40 \
  --epochs 80 \
  --tasks-per-epoch 20
```

## Result

| Metric | shortest | greedy | epsilon | Thompson | Physarum |
| --- | ---: | ---: | ---: | ---: | ---: |
| overall success | 0.9688 | 0.9688 | 0.9661 | **0.9699** | 0.9646 |
| first-half success | 0.9689 | 0.9689 | 0.9654 | **0.9703** | 0.9639 |
| second-half success | 0.9688 | 0.9688 | 0.9668 | **0.9696** | 0.9653 |
| mean route burden | **2.0000** | **2.0000** | 2.1635 | 2.0006 | 2.1214 |
| normalized path entropy | 0.0000 | 0.0000 | 0.2026 | 0.0123 | 0.1498 |
| max path share | 1.0000 | 1.0000 | 0.9074 | 0.9987 | 0.9279 |

## Interpretation

This control does **not** support a universal Physarum advantage.

- Thompson path sampling has the highest completion rate while adding essentially no
  route burden over the shortest path.
- Physarum preserves more path diversity than Thompson, but that diversity costs about
  **6.1% more mean route burden** than the static shortest path.
- Physarum's completion rate is about **0.53 percentage points lower** than Thompson in
  this stationary fixture.
- The first and second halves are stable, as expected when the environment does not
  change.

The result strengthens the research boundary rather than weakening it: Physarum's
extra state/exploration should be justified by churn, failure recovery, or another
measured resilience benefit. When the network is stationary, a simpler policy is on the
better success/burden frontier in this fixture.

## Consequence for #630

The required **no-shift / stationary environment** sweep is now reproducible. It is a
negative control, not an integration gate pass. The remaining stress tests must cover
gradual/transient failures, topology variation, correlated/node failures, burden
asymmetry, attribution errors, parameter sensitivity, and stronger failover/change-point
baselines before any dry-run product integration is earned.
