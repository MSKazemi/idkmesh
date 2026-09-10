# randomness-lab

`randomness_lab` is a dependency-free experimental harness for testing stochastic coordination policies before IDKMesh embeds them in production orchestration.

It implements the first slices of issue #29 and supports the research direction in `docs/research/RANDOMNESS_ROADMAP.md`.

## Design rule

> Randomness controls exploration, not acceptance.

The simulator produces synthetic **verified outcomes**. A stochastic policy may choose which worker to try, but it cannot bypass the outcome/verification layer.

## Run

From the repository root:

```bash
python -m randomness_lab --policy thompson --rounds 1000 --seed 42
```

Run repeated trials and retain the raw distribution plus an uncertainty summary:

```bash
python -m randomness_lab \
  --policy thompson \
  --workers 0.55,0.65,0.80 \
  --error-correlation 0.25 \
  --rounds 1000 \
  --trials 30 \
  --seed 42 \
  --output results/thompson-30-trials.json
```

Trial seeds are deterministic: `seed`, `seed + 1`, ..., so an experiment can be reproduced exactly. For multiple trials the output includes every raw trial, mean/min/max verified-success rate, sample standard deviation, and a clearly labeled descriptive normal-approximation 95% interval across trial means.

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
- environment description;
- verified success count/rate;
- total and mean compute cost;
- total and mean latency;
- selection counts;
- empirical worker success rates;
- realized mean pairwise error correlation;
- randomness-source provenance.

Repeated experiments additionally retain all raw runs plus across-trial summary statistics. Raw metrics remain authoritative; uncertainty summaries are aids for comparison rather than replacements for the underlying distribution.

The current worker model is deliberately synthetic. `error_correlation` uses a transparent mixture: on some rounds all workers share one random draw; on the remaining rounds their draws are independent. This gives experiments an explicit positive-correlation knob without pretending to model every real agent failure mode.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests check seeded reproducibility, repeated-trial reproducibility and uncertainty output, policy interchangeability, environment interchangeability, the correlation control, Thompson-sampling adaptation, and the power-of-d helper.

## R1 verifier panels and dependence

R1 keeps two verifier-correlation concepts deliberately separate:

- `verifier_error_correlation` is the historical **within-task strictness shock** for one named verifier across candidates in the same task;
- `panel_dependence_correlation` is dependence **between distinct panel members judging one candidate**.

The panel-dependence axis is opt-in and defaults to zero. At zero, R1 stays on the historical verifier path so existing single-verifier and phase-(a) panel RNG calls remain unchanged. Positive panel dependence currently requires a real panel, zero within-task strictness correlation, and homogeneous verifier sensitivity/false-positive rate. These restrictions keep the two axes identifiable and make the correlation parameter comparable with E018's common-marginal analytic model instead of silently composing unlike mechanisms.

`randomness_lab/verifier_dependence.py` provides two synthetic dependence shapes:

- `shared_shock`: with probability rho, all panelists share one correctness draw; otherwise their correctness draws are independent;
- `item_difficulty`: a beta-binomial latent error probability parameterized so marginal accuracy is preserved and pairwise correctness/error correlation is rho.

Both shapes use exactly the same sampler at rho `0` (independent Bernoulli decisions) and rho `1` (one shared decision). Tests require exact sampled-vector and RNG-state equality at those endpoints, compare intermediate simulated panel error with the closed-form models in `sim/e018_dependence_models.py`, and check that realized pairwise correlation tracks the requested rho. E018 is an **analytic oracle only**; R1 does not reuse its implementation as a sampler.

This is infrastructure for issue #380, not a result for hypothesis 2. New panel arms, dependence sweeps, both attention-billing regimes, and the final interpretation belong to later experiment increments.

## R2 factor-isolation benchmark

The final issue #84 follow-up separates availability lag, load lag, regional
failure correlation, and offered load instead of changing them in one stress
preset. It also emits deterministic coordination-cost proxies and a separate
host-specific scheduler profile. Capability rarity is covered by the companion
`r2_capability_rarity` benchmark.

```bash
python -m randomness_lab.r2_factor_sweep --self-test
python -m randomness_lab.r2_factor_sweep --benchmark --output /tmp/r2-factors.json
python -m randomness_lab.r2_factor_sweep --profile --repetitions 5 --output /tmp/r2-profile.json
```

The retained five-seed evidence and interpretation are in
[`../results/experiments/r2/reference-factor-isolation-seeds41-45.md`](../results/experiments/r2/reference-factor-isolation-seeds41-45.md).

## Adding a policy

1. Implement the `Policy` protocol from `randomness_lab/policies.py`.
2. Give the policy a stable `name`.
3. Register it in `POLICIES` and `make_policy()`.
4. Add a deterministic seeded test.
5. Compare it with a simpler baseline. Bio-inspired or stochastic complexity is not accepted as evidence of superiority by itself.

## Adding an environment

Implement the `OutcomeEnvironment` protocol from `randomness_lab/model.py`. An environment needs:

- a stable `name`;
- `sample(workers, rng)`, returning exactly one boolean verified outcome for each worker name;
- `describe()`, returning machine-readable provenance/parameters.

Then inject the environment into `run_simulation(..., environment=...)`. Repeated experiments accept an `environment_factory` so each trial can receive a fresh environment instance.

An environment must model **candidate outcomes**, not weaken verification. It should also expose its assumptions clearly enough that a result can be reproduced and challenged.

## Next slices

This foundation is intentionally small. The next steps are:

1. explicit swarm/ensemble selection for issue #30;
2. load/queue environment for issue #31;
3. evolutionary policy genome for issue #32;
4. machine-readable experiment manifests and benchmark families;
5. richer uncertainty methods when experimental design warrants them;
6. CI artifacts for experiment results where useful.

Raw metrics should remain available even if later experiments add composite objectives.
