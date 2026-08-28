# IDKMesh Simulation Kernel

This directory contains small, reproducible models for testing IDKMesh coordination hypotheses before building a wide-area system.

## `emergence_sim.py`

The first simulator asks a narrow version of the project's deepest question:

> Can a system preserve useful complexity and adapt when the initial goal is incomplete or later changes?

It compares three intentionally simplified strategies under a shared resource budget and viability constraints:

1. **`random`** — each generation samples fresh random candidates. Randomness produces variation but no persistent structured search.
2. **`scalar`** — evolutionary search optimizes one fixed interpretation of the initial goal. This models premature convergence around a single objective.
3. **`qd`** — a constraint-guided Quality-Diversity archive preserves strong candidates across multiple behavioral niches while evaluating them against several plausible goals.

The candidate has five competing traits: reliability, adaptability, efficiency, simplicity, and security. A finite budget prevents all traits from simply becoming maximal.

Halfway through a default run, the hidden environment changes its preferences. The fixed scalar strategy continues optimizing the old interpretation, while the QD strategy can draw from an archive of alternatives.

## Verification model

Verification is perfect by default so the original E011 experiment remains reproducible. It can now be replaced by a panel of imperfect verifiers:

```bash
python sim/emergence_sim.py \
  --strategy all \
  --seed 7 \
  --agents 100 \
  --generations 60 \
  --change-at 30 \
  --verifiers 5 \
  --verifier-accuracy 0.75 \
  --verifier-correlation 0.5 \
  --verification-quorum 0.5 \
  --pretty
```

`--verifier-correlation` uses a shared-error mixture. At `0`, verifier correctness is independent; at `1`, all verifier correctness states are shared. The model records false accepts, false rejects, and within-panel disagreement.

This exposes a critical distinction for IDKMesh: **reviewer count is not independent evidence count**.

## Correlation sweep

Run E012 with:

```bash
python sim/run_verifier_correlation_sweep.py --pretty
```

The reference configuration uses five 75%-accurate verifiers across correlation levels `0, 0.25, 0.5, 0.75, 1` and 50 random seeds.

The synthetic result shows that as correlation rises, majority-vote error rises while panel disagreement falls. At full correlation the panel reports zero internal disagreement, but false-accept/false-reject rates are about 25% — effectively behaving like one verifier.

See [`../experiments/E012-correlated-verification.md`](../experiments/E012-correlated-verification.md).

## Multi-seed sweeps

```bash
python sim/run_emergence_sweep.py --seeds 100 --pretty
```

Verifier parameters can be supplied to the sweep with the same CLI flags.

## Tests

With `pytest` installed:

```bash
python -m pytest -q \
  tests/test_emergence_sim.py \
  tests/test_emergence_sweep.py \
  tests/test_verifier_correlation_sweep.py
```

The tests cover deterministic replay, budget invariants, niche preservation, perfect verification compatibility, correlated-error mechanics, and sweep configuration.

## Interpretation

These simulators are **not** evidence that IDKMesh can automatically evolve a correct complex software system. They are deliberately small falsifiable models for exploring mechanisms.

The useful hypothesis is:

`variation + hard constraints + selection + shared memory + diversity preservation + independent verification`

may be more resilient to vague/changing goals than either pure randomness or optimization against one prematurely fixed objective.

The verifier experiment adds a second hypothesis:

`nominal verifier count != effective independent evidence count`

The model should become progressively less toy-like by adding:

- correlation-aware aggregation rather than naive majority voting;
- Goal Graph updates from evidence;
- stochastic Work Units and task dependencies;
- agent/verifier specialization and contributor reputation;
- churn, latency, bandwidth, and heterogeneous compute;
- adversarial workers, malicious verifiers, and collusion;
- stigmergic traces in shared state;
- bandit allocation of compute across niches;
- changing constraints and catastrophic-regression tests;
- human-attention cost;
- verified-useful-work metrics;
- real bounded software tasks and hidden tests.

The repository should keep negative results as carefully as positive ones.
