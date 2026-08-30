# R1 Help/Hurt Regime Sweep

**Issue:** #30  
**Depends on:** `randomness_lab.r1`

The first R1 harness compares six swarm configurations at one parameter setting. This sweep answers the more important question:

> **Under which assumptions does structural diversity help, hurt, or remain statistically ambiguous relative to identical replication?**

It deliberately searches for failure regimes instead of tuning only for a positive result.

## Sweep dimensions

The runner varies:

1. **swarm size**;
2. **worker base-error correlation** for the structurally diverse condition;
3. **verifier error correlation**;
4. **structural-worker quality penalty**.

The quality penalty is important. Diversity is not free in real systems: a more diverse set of models/tools/roles may include weaker workers, slower workers, or more expensive coordination. A method that only works when every diverse worker is as individually strong as the best replicated worker would be fragile.

For each cell, `identical_replication` keeps the base worker quality and maximally correlated base errors. `structural_diversity` receives the configured worker correlation and quality penalty.

## Paired seeded comparisons

For every cell and trial seed, both conditions run with the same seed index. The output retains the raw pair:

```text
seed
replication verified success + utility
structural verified success + utility
signed deltas
```

The sweep summarizes the trial-level deltas rather than subtracting two unrelated confidence intervals.

## Classification

For verified success and verified utility per unit cost separately:

```text
95% delta interval entirely > 0  -> helps
95% delta interval entirely < 0  -> hurts
otherwise                         -> uncertain
```

The interval is currently a descriptive normal approximation over seeded trial deltas. It is not presented as a substitute for stronger statistical design on real benchmark data.

## Run

```bash
python -m randomness_lab.r1_sweep \
  --tasks 200 \
  --trials 10 \
  --worker-correlations 0,0.25,0.5,0.75,1 \
  --verifier-correlations 0,0.5,1 \
  --quality-penalties 0,0.05,0.10 \
  --swarm-sizes 2,5 \
  --seed 42 \
  --output results/r1-help-hurt-map.json
```

The result is machine-readable and contains:

- all parameter cells;
- all raw seed-level trial pairs;
- paired success deltas;
- paired utility deltas;
- realized structural error correlation;
- help/hurt/uncertain classification counts;
- exact sweep configuration.

## What a harmful regime means

A `hurts` classification is not a problem to hide. It is one of the most valuable outputs of IDKMesh research.

For example, structural diversity can plausibly hurt when:

- diverse workers are materially weaker;
- their errors remain highly correlated anyway;
- verifier errors are correlated;
- added attempts consume more compute or reviewer attention than their extra success probability justifies.

The synthetic sweep can establish whether the orchestration logic detects such regimes. Only real-task experiments can estimate where the actual system lies in this parameter space.

## What it turned out to also answer

This sweep was written for issue #30. It also, without saying so, tested issue
#13's hypothesis 2 — heterogeneous teams beat homogeneous teams at an equal
budget — because that is exactly the `structural_diversity` versus
`identical_replication` contrast it classifies. That connection went unrecorded
long enough for
[E040](../../experiments/E040-diversity-correlation-threshold.md) to claim the
hypothesis had no test at all before finding this page.

Read together, the two runners say something neither says alone. E040 fits the
advantage against retained independence and finds it proportional to `1 - rho`
with no knee, in a grid where diverse workers cost nothing extra. This sweep
charges for diversity through the quality penalty, and every one of its
`hurts` cells carries a non-zero penalty while the penalty-free slice reports
none across the whole correlation ladder.

**Correlation sets the size of the diversity advantage; worker quality sets its
sign.** A sign is what this sweep can produce and E040's grid cannot, which is
the reason to keep both.

## What this still does not prove

The sweep does **not** estimate real model error correlation, real security risk, or real human-review cost. Its probabilities are controlled assumptions.

Therefore the next R1 step is a real-task replay interface:

```text
real candidate artifacts/results
        -> normalized R1 records
        -> measured pairwise failures
        -> same help/hurt analysis
```

That is the bridge from mathematical mechanism testing to evidence about actual coding swarms.
