# Homeostatic Stigmergic Routing (HSR)

**Status:** Experimental synthesis derived from E014 evidence.

## Motivation

The first ACO reference sweep exposed a genuine tradeoff:

- capability-only routing had high immediate verified utility per cost but concentrated work and duplicated effort;
- ACO reduced duplication and concentration and preserved task coverage, but sacrificed immediate efficiency.

HSR combines three ideas instead of treating ACO as a fixed router:

1. **capability matching** for local exploitation;
2. **stigmergic memory** for evidence-backed collective learning;
3. **homeostatic/density-dependent feedback** that increases diversity pressure only when the system becomes crowded.

The biological inspiration is not only ants. Living systems often regulate growth and activity through negative feedback: when local density or resource pressure rises, inhibition increases; when pressure falls, normal growth resumes.

## Routing score

For worker/agent `a`, task `j`, and time `t`:

```text
Score(a,j,t) = CapabilityValue(a,j)
               * tau_j(t)^alpha
               * [Diversity(a,j,t) * Congestion(j,t)]^lambda(t)
```

where:

- `CapabilityValue` combines worker-task skill and intrinsic task value;
- `tau_j` is evidence-backed stigmergic memory;
- `Diversity` discounts correlated repeated attempts;
- `Congestion` discounts crowded work paths;
- `lambda(t)` is the adaptive regulation strength.

A probabilistic selector applies a `beta` exponent to the score and preserves an explicit random exploration floor.

## Homeostatic feedback law

Let:

- `D(t)` = observed duplicate-attempt rate;
- `D_target` = acceptable duplicate rate;
- `S(t)` = maximum task-selection concentration;
- `S_target` = acceptable concentration;
- `lambda(t)` = strength of ecological regulation.

Update:

```text
lambda(t+1) = clip(
    lambda(t)
    + k_d * (D(t) - D_target)
    + k_s * (S(t) - S_target)
    - r * (lambda(t) - lambda_min),
    lambda_min,
    lambda_max
)
```

Interpretation:

- when duplication/concentration exceed targets, `lambda` rises and strongly penalizes crowded/correlated routes;
- when the system is healthy, `lambda` relaxes toward `lambda_min`, allowing capability exploitation to dominate;
- the control is continuous rather than switching between two hard-coded modes.

A later repository implementation can add review load explicitly:

```text
+ k_q * (ReviewLoad(t) - Q_target)
```

so scarce verifier/reviewer capacity becomes part of the feedback loop.

## Stigmergic memory

HSR retains the ACO evidence update:

```text
tau_j(t+1) = clip(
    (1-rho) * tau_j(t)
    + VerifiedDeposit_j(t)
    - Penalty_j(t),
    tau_min,
    tau_max
)
```

Only evidence-backed useful outcomes should create strong deposits.

Popularity is not evidence.

## Why this synthesis may fit IDKMesh better than fixed ACO

Fixed ACO asks one routing law to balance exploitation and diversity at all times. HSR instead treats the system as adaptive:

```text
healthy capacity
    -> capability exploitation dominates

crowding / reviewer pressure / correlated duplication
    -> ecological regulation rises
    -> effort spreads toward alternative paths

pressure falls
    -> regulation relaxes
```

This resembles biological homeostasis and feedback control more closely than a fixed pheromone equation alone.

## Safety boundaries

HSR is still only a recommendation/routing mechanism.

It must not:

- grant repository permissions;
- decide that an artifact is correct;
- bypass independent verification;
- merge changes;
- infer contributor worth from pheromone;
- use raw popularity as a verified deposit;
- hide parameter changes.

## Current implementation

- `sim/homeostatic_stigmergy_sim.py`
- `tests/test_homeostatic_stigmergy_sim.py`

The first synthetic comparison tests HSR against capability-only routing and fixed ACO over repeated seeds.

## Falsification criterion

HSR is useful only if it moves the Pareto frontier outward relative to the simpler mechanisms—for example, approaching capability-only utility efficiency while retaining materially lower duplication/concentration and broad task coverage.

If it merely adds complexity without a reproducible Pareto improvement, reject it.

## Related evidence

- `experiments/E014-aco-stigmergic-task-routing.md`
- `experiments/results/E014-reference-sweep.md`
- `experiments/results/E014-parameter-pareto.md`
- `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md`
