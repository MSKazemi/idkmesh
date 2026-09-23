# PHY-0 — Physarum-inspired adaptive compute routing

**Status:** synthetic mechanism test, not empirical evidence  
**Date:** 2026-09-22  
**Implementation:** `sim/physarum_compute_routing_sim.py`  
**Design:** `docs/algorithms/PHYSARUM_ADAPTIVE_COMPUTE_ROUTING.md`  
**Retained output:** `experiments/results/PHY-0-reference-sweep.json`

## Question

Can conductance-style adaptive routing preserve alternate compute paths and recover from a changing network faster than static or simple adaptive path selection?

This experiment is deliberately **after compute admission**. It does not model provider authorization, monetary policy, capability materialization, trust admission, or merge authority. Those remain hard upstream gates.

## Fixture

The synthetic admitted graph contains three primary coordinator -> worker corridors plus cross-links.

Before epoch 40:

- corridor A is shortest and highly reliable;
- corridor B is slightly longer;
- corridor C is longest and very reliable.

After epoch 40:

- A degrades sharply;
- B improves;
- C stays stable.

Every strategy receives the same graph and shift.

## Baselines

- `shortest-static`
- `reliability-greedy`
- `epsilon-greedy`
- `thompson-path`
- `physarum`

The Thompson baseline is important: Physarum should not receive credit merely for being adaptive.

## Command

```bash
python sim/physarum_compute_routing_sim.py \
  --seeds 40 \
  --epochs 80 \
  --tasks-per-epoch 20
```

## Reference result

| Metric | shortest | greedy | epsilon | Thompson | Physarum |
| --- | ---: | ---: | ---: | ---: | ---: |
| overall success | 0.788 | 0.788 | 0.798 | 0.811 | **0.934** |
| pre-shift success | **0.969** | **0.969** | 0.965 | **0.970** | 0.964 |
| post-shift success | 0.607 | 0.607 | 0.631 | 0.651 | **0.905** |
| mean route burden | **2.000** | **2.000** | 2.164 | 2.022 | 2.298 |
| normalized path entropy | 0.000 | 0.000 | 0.203 | 0.274 | **0.356** |
| max path share | 1.000 | 1.000 | 0.907 | 0.944 | **0.587** |

## Interpretation

In this synthetic shift fixture, the Physarum policy gives up some route efficiency:

- mean route burden is about **15% higher** than the static shortest path;
- pre-shift completion is slightly lower than the static/Thompson baselines.

In exchange it retains more alternate-path activity and adapts far better after the old shortest corridor degrades:

- post-shift success is about **0.905** versus **0.651** for Thompson path sampling;
- path selection is materially less concentrated.

This is a positive synthetic result for the mechanism, not evidence that it should be deployed.

## Why greedy gets stuck

The reliability-greedy policy begins with a favorable prior and repeatedly uses the initially short/high-performing corridor. Because it does not explore, it learns almost nothing about alternatives until its chosen route has already degraded.

That is an intended failure mode in this fixture, not a universal statement about greedy routing.

## What Physarum is buying

The mechanism maintains a non-zero conductance floor plus bounded stochastic exploration.

That creates a real cost:

```text
more alternate-path traffic
 -> higher average route burden
 -> more information about the network
 -> faster recovery when conditions change
```

The next experiments must determine whether that resilience premium remains worthwhile under other network shapes and failure regimes.

## Required next sweeps

Before any integration, vary:

- no environment shift;
- gradual rather than abrupt degradation;
- transient failures rather than persistent shift;
- sparse vs dense graphs;
- asymmetric donor/network burden;
- correlated regional failures;
- node rather than edge failures;
- stale or incorrect failure attribution;
- different `D_min`, evaporation and exploration settings.

Add stronger baselines where useful:

- contextual bandit with edge features;
- change-point-aware Thompson sampling;
- shortest path over confidence bounds;
- explicit multipath failover.

## Product boundary

A successful research result would justify only a dry-run planner after existing admission:

```text
hard admission
 -> eligible admitted graph
 -> adaptive route recommendation
 -> explain route + alternatives + learned state
```

It would not justify autonomous dispatch, paid fallback, relaxed trust, or integration authority.
