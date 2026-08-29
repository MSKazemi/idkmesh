# E014 parameter sensitivity — stable tradeoff frontier

**Source:** GitHub Actions run `33182525700`, job `98887077754`, Python 3.11.16  
**Sweep:** 24 parameter configurations × 12 seeds × 24 workers × 50 epochs.

The ACO sensitivity sweep produced **11 non-dominated configurations** across four objectives:

- maximize verified utility per cost;
- minimize duplicate rate;
- maximize task coverage;
- minimize maximum task-selection concentration.

This is a synthetic result only.

## Best-efficiency tested ACO configuration

```text
alpha       = 1.1
beta        = 2.5
rho         = 0.15
exploration = 0.03
```

Mean synthetic outcomes:

```text
verified utility / cost = 0.6071
duplicate rate          = 0.1833
task coverage           = 8 / 8
max selection share     = 0.2108
```

Relative to the original/default reference ACO configuration, this raises verified utility per cost by about **8.7%**, but duplicate rate rises by about **18.2%** and concentration by about **8.4%**.

That is exactly the tradeoff the experiment was intended to expose: stronger exploitation can buy efficiency by consuming some diversity/congestion margin.

## Comparison with capability-only routing

The best-efficiency tested ACO configuration still has about **30.1% lower** utility per cost than capability-only routing in the reference synthetic model.

However, relative to capability-only routing it also has approximately:

- **57.2% lower duplicate rate**;
- **45.0% lower maximum selection concentration**;
- **65.8% higher task coverage**.

So parameter tuning alone does not eliminate the central tradeoff.

## Biological/control interpretation

The useful analogy is becoming more precise:

- **capability matching** is strong local exploitation;
- **pheromone** is collective memory;
- **evaporation** prevents historical lock-in;
- **congestion/correlation penalties** act like density-dependent inhibition;
- **exploration** maintains ecological niches;
- **verification deposits** are reproductive reinforcement.

The synthetic evidence suggests IDKMesh should not ask one mechanism to maximize all objectives. A better design is likely a **capacity-governed hybrid controller** that uses capability matching by default and increases stigmergic diversity pressure only as duplication, concentration, or reviewer load approach unsafe levels.

## Candidate adaptive law

Let `lambda(t)` control the strength of diversity/congestion regulation:

```text
Score(a,j,t) = CapabilityValue(a,j)
               * tau_j(t)^alpha
               * Diversity(a,j,t)^lambda(t)
               * Congestion(j,t)^lambda(t)
```

and update `lambda` from observed overload:

```text
lambda(t+1) = clip(
    lambda(t)
    + k_d * (DuplicateRate(t) - D_target)
    + k_q * (ReviewLoad(t) - Q_target),
    lambda_min,
    lambda_max
)
```

Interpretation:

- when queues and duplication are low, `lambda` falls and capability exploitation dominates;
- when the system crowds one path or overwhelms reviewers, `lambda` rises and the colony spreads effort across alternatives;
- pheromone still decays, so old successes cannot permanently monopolize attention.

This combines **ACO + ecological density dependence + feedback control** rather than treating biological ACO as a fixed router.

## Decision

The sensitivity result supports continuing the research, but **not deploying ACO**.

Next experiment: implement the capacity-governed hybrid as a fifth strategy and ask whether it moves the Pareto frontier outward—approaching capability-only utility while retaining substantially lower duplication/concentration and broad coverage.
