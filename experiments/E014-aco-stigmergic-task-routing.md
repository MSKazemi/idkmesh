# E014 — ACO stigmergic task routing

**Status:** Proposed / executable synthetic baseline

## Question

Can evidence-backed stigmergic routing improve useful task allocation in a heterogeneous contributor/agent pool compared with simpler routing rules, without causing excessive herding, duplication, or review concentration?

## Biological mechanism under test

The experiment adapts ant-colony pheromone dynamics to IDKMesh task routing:

```text
tau_j(t+1) = clip((1-rho) * tau_j(t) + Deposit_j(t) - Penalty_j(t), tau_min, tau_max)
```

and worker-specific task selection:

```text
P(a -> j | t) proportional to tau_j(t)^alpha * eta_(a,j)(t)^beta
```

where the local heuristic includes worker-task capability, task value, information gain, accessibility, congestion, correlation/diversity, review cost, and risk.

## Baselines

Compare four policies:

1. **random** — uniform feasible choice;
2. **greedy** — always choose the highest intrinsic task value;
3. **capability** — choose the strongest worker-task capability/value match;
4. **ACO** — evidence-backed pheromone + local fit + explicit exploration + congestion/correlation penalties.

## Synthetic environment

The v0 simulator contains eight recurring work-path archetypes:

- schema;
- validator;
- security;
- docs;
- benchmark;
- integration;
- onboarding;
- reproduction.

Workers have heterogeneous skills and repeated `family-*` groups that approximate correlated agents/toolchains. This is deliberately synthetic. It is useful for testing algorithm mechanics, not for making claims about real open-source contributor behavior.

## Primary metric

```text
verified_utility_per_cost = verified utility / (review cost + compute cost)
```

The simulator also reports:

- verified artifact count;
- duplicate-attempt rate;
- task coverage;
- maximum task-selection share (herding/concentration proxy);
- neglected high-value tasks;
- per-task selections and verified outcomes;
- final pheromone state.

## Fair comparison rule

For a repeated-seed sweep, every strategy receives the same seed for a given replicate, so each starts with the same generated worker population. Routing decisions then cause the stochastic paths to diverge.

Do not select one favorable seed as evidence. Use repeated seeds and report the distribution/summary.

## Executable commands

Single run:

```bash
python sim/aco_stigmergy_sim.py --strategy all --seed 7 --workers 24 --epochs 50
```

Repeated-seed comparison:

```bash
python sim/run_aco_sweep.py --seed-start 1 --seeds 20 --workers 24 --epochs 50
```

Tests:

```bash
python -m pytest -q tests/test_aco_stigmergy_sim.py
```

## Predeclared success direction

ACO is interesting only if repeated runs show a useful Pareto tradeoff. In particular, prefer evidence that it can improve or preserve:

```text
verified_utility_per_cost
```

while avoiding material degradation in:

- duplicate rate;
- selection concentration;
- task coverage;
- neglected high-value tasks.

There is intentionally no requirement that ACO win every metric or every seed.

## Falsification / rejection conditions

Do not advance ACO toward production routing if repeated simulation and later repository replay show that it:

- consistently underperforms capability-only matching on verified utility per cost;
- creates stronger task concentration/herding without compensating utility;
- starves minority/novel tasks despite the exploration floor;
- increases correlated duplicate work;
- becomes highly sensitive to small parameter changes;
- can be gamed by unverified popularity/activity signals;
- requires unavailable or unreliable metadata to function.

A negative result is a valid outcome.

## Next evidence levels

### Level 0 — mechanics

Unit tests verify probability normalization, pheromone bounds/evaporation, and congestion/correlation penalties.

### Level 1 — repeated synthetic simulation

Run many seeds and parameter sweeps. Compare distributions, not a single lucky run.

### Level 2 — historical repository replay

Reconstruct task/evidence events from IDKMesh or another consenting public repository and compare what each policy would have recommended. Do not claim causal improvement from replay alone.

### Level 3 — advisory shadow mode

Generate task recommendations without changing assignments or permissions. Measure whether humans consider the recommendations useful.

### Level 4 — bounded live experiment

Only after prior levels are promising, route a deliberately small task pool with human override and independent verification.

## Safety invariant

Pheromone is a **routing signal, not truth, authority, or reputation**. ACO may recommend where effort goes; it must not grant permissions, approve work, bypass validators, or merge changes.

## Related

- `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md`
- `sim/aco_stigmergy_sim.py`
- `sim/run_aco_sweep.py`
- `tests/test_aco_stigmergy_sim.py`
- `MATHEMATICAL_FOUNDATIONS.md`
- `COMMUNITY_GROWTH_ENGINE.md`
