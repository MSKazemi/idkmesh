# E014 reference sweep — mixed result

**Source:** GitHub Actions run `33182352840`, Python 3.11.16, commit `81e117ed861fce578d9b8993d8065b6450a845d5`  
**Configuration:** 40 seeds, 24 workers, 50 epochs per strategy.

This is a **synthetic result**, not evidence about real contributors.

## Mean results

| Strategy | Verified utility / cost | Duplicate rate | Task coverage | Max selection share | Neglected high-value tasks |
| --- | ---: | ---: | ---: | ---: | ---: |
| random | 0.3997 | 0.2266 | 8.000 | 0.1391 | 0.000 |
| greedy | 1.1322 | 0.8333 | 1.000 | 1.0000 | 1.000 |
| capability | 0.8690 | 0.4281 | 4.825 | 0.3833 | 0.000 |
| ACO | 0.5584 | 0.1551 | 8.000 | 0.1944 | 0.000 |

## What ACO improved

Compared with random routing, ACO produced about **39.7% more verified utility per cost** and about **31.6% less duplicate work**, while preserving full task coverage.

Compared with capability-only routing, ACO produced about **63.8% less duplicate work**, about **49.3% lower maximum selection concentration**, and about **65.8% more task coverage**.

Compared with greedy routing, ACO reduced duplicate work by about **81.4%**, reduced maximum concentration by about **80.6%**, and covered all eight task classes instead of one.

## What ACO did not improve

ACO's mean verified utility per cost was about **35.7% below capability-only routing** and about **50.7% below the greedy baseline** in this synthetic model.

The greedy baseline's high efficiency is not a general success: it sends every worker to one task, has a duplicate rate of 0.8333, covers only one task class, and neglects a high-value task. But the result demonstrates an important tradeoff: **diversity and congestion control are not free**.

## Interpretation

The current ACO configuration should not be described as the best router.

A more accurate interpretation is:

> In this synthetic ecology, ACO behaves like a diversity/congestion controller. It substantially reduces duplication and concentration and preserves broad task coverage, but pays for that resilience with lower immediate utility efficiency than a capability-focused router.

This is useful because IDKMesh is explicitly multi-objective. It also means the next experiment should not simply increase pheromone strength until ACO wins one scalar metric.

## Next hypothesis: capacity-governed hybrid

The next hypothesis is that the Pareto gap can be reduced by combining capability exploitation with stigmergic congestion control.

One candidate form is:

```text
Score(a,j) = CapabilityValue(a,j)
             * tau_j^alpha
             * Diversity_j^delta
             * Congestion_j^gamma
```

with an explicit exploration floor and an adaptive penalty coefficient that increases only when duplication/review load exceeds a target.

Conceptually:

```text
maximize verified utility per cost
subject to:
  duplicate_rate <= D_max
  max_selection_share <= S_max
  task_coverage >= C_min
```

This reframes ACO as a constrained multi-objective controller rather than a replacement for capability matching.

## Required next evidence

1. Parameter sensitivity over `alpha`, `beta`, `rho`, and exploration rate.
2. Pareto analysis rather than a single winner ranking.
3. Compare a capability + ACO hybrid against the current four baselines.
4. Historical repository replay before any live recommendation.
5. Preserve this mixed result even if later configurations improve.

## Decision

**Do not promote ACO to live routing.**

Continue at synthetic evidence Level 1 and test whether a hybrid can retain ACO's low duplication/full coverage while approaching capability-only utility efficiency.
