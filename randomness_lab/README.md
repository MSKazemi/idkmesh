# randomness-lab

`randomness_lab` is a dependency-free experimental harness for testing stochastic coordination policies before IDKMesh embeds them in production orchestration.

It implements the first slice of issue #29 and supports the research direction in `docs/research/RANDOMNESS_ROADMAP.md`.

## Design rule

> Randomness controls exploration, not acceptance.

The simulator produces synthetic **verified outcomes**. A stochastic policy may choose which worker to try, but it cannot bypass the outcome/verification layer.

## Run

From the repository root:

```bash
python -m randomness_lab --policy thompson --rounds 1000 --seed 42
```

Add a simple correlated-error environment:

```bash
python -m randomness_lab \
  --policy ucb \
  --workers 0.55,0.65,0.80 \
  --error-correlation 0.35 \
  --rounds 5000 \
  --seed 7 \
  --output results/ucb-seed-7.json
```

Available worker-selection policies:

- `greedy`;
- `epsilon-greedy`;
- `softmax`;
- `ucb`;
- `thompson`.

`power_of_d_least_loaded()` is also included as a small reusable primitive for issue #31.

## What the first simulator measures

Each run records:

- the exact configuration and seed;
- worker definitions;
- verified success count/rate;
- total and mean compute cost;
- total and mean latency;
- selection counts;
- empirical worker success rates;
- realized mean pairwise error correlation;
- randomness-source provenance.

The current worker model is deliberately synthetic. `error_correlation` uses a transparent mixture: on some rounds all workers share one random draw; on the remaining rounds their draws are independent. This gives experiments an explicit positive-correlation knob without pretending to model every real agent failure mode.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests check seeded reproducibility, policy interchangeability, the correlation control, Thompson-sampling adaptation, and the power-of-d helper.

## Adding a policy

1. Implement the `Policy` protocol from `randomness_lab/policies.py`.
2. Give the policy a stable `name`.
3. Register it in `POLICIES` and `make_policy()`.
4. Add a deterministic seeded test.
5. Compare it with a simpler baseline. Bio-inspired or stochastic complexity is not accepted as evidence of superiority by itself.

## Next slices

This foundation is intentionally small. The next steps are:

1. repeated-trial experiment runner with confidence intervals/distributions;
2. explicit swarm/ensemble selection for issue #30;
3. load/queue environment for issue #31;
4. evolutionary policy genome for issue #32;
5. machine-readable experiment manifests and benchmark families;
6. CI artifacts for experiment results where useful.

Raw metrics should remain available even if later experiments add composite objectives.
