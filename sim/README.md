# IDKMesh Simulation Kernel

This directory contains small, reproducible models for testing IDKMesh coordination hypotheses before building a wide-area system.

## `emergence_sim.py`

The first simulator asks a narrow version of the project's deepest question:

> Can a system preserve useful complexity and adapt when the initial goal is incomplete or later changes?

It compares three intentionally simplified strategies under a shared resource budget and hard viability constraints:

1. **`random`** — each generation samples fresh random candidates. Randomness produces variation but no persistent structured search.
2. **`scalar`** — evolutionary search optimizes one fixed interpretation of the initial goal. This models premature convergence around a single objective.
3. **`qd`** — a constraint-guided Quality-Diversity archive preserves strong candidates across multiple behavioral niches while evaluating them against several plausible goals.

The candidate has five competing traits:

- reliability;
- adaptability;
- efficiency;
- simplicity;
- security.

A finite budget prevents all traits from simply becoming maximal. Reliability and security are hard viability constraints. Halfway through a default run, the hidden environment changes its preferences. The fixed scalar strategy continues optimizing the old interpretation, while the QD strategy can draw from an archive of alternatives.

## Run

```bash
python sim/emergence_sim.py --strategy all --seed 7 --agents 200 --generations 120 --change-at 60 --pretty
```

The program has no third-party runtime dependencies.

## Tests

With `pytest` installed:

```bash
python -m pytest -q tests/test_emergence_sim.py
```

The initial tests check deterministic replay, resource-budget invariants, niche preservation, and a fixed reference scenario in which QD should outperform the prematurely fixed scalar objective after the goal changes.

## Interpretation

This simulator is **not** evidence that IDKMesh can automatically evolve a correct complex software system. It is a deliberately small falsifiable model for exploring mechanisms.

The useful hypothesis is:

`variation + hard constraints + selection + shared memory + diversity preservation + verification`

may be more resilient to vague/changing goals than either pure randomness or optimization against one prematurely fixed objective.

The model should become progressively less toy-like by adding:

- explicit independent verifier agents and correlated verifier errors;
- Goal Graph updates from evidence;
- stochastic Work Units and task dependencies;
- agent specialization and contributor reputation;
- churn, latency, bandwidth, and heterogeneous compute;
- adversarial workers and collusion;
- stigmergic traces in shared state;
- bandit allocation of compute across niches;
- changing constraints and catastrophic-regression tests;
- human-attention cost;
- verified-useful-work metrics;
- replication across many random seeds with confidence intervals.

The repository should keep negative results as carefully as positive ones.
