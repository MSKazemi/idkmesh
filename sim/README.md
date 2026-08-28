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

Verification is perfect by default so the original E011 experiment remains reproducible. It can also use an imperfect verifier panel:

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

## E012 — correlation sweep

```bash
python sim/run_verifier_correlation_sweep.py --pretty
```

The reference E012 configuration uses five 75%-accurate verifiers across correlation levels `0, 0.25, 0.5, 0.75, 1` and 50 random seeds.

As correlation rises, majority-vote error rises while panel disagreement falls. At full correlation the panel reports zero internal disagreement, but false-accept/false-reject rates are about 25% — effectively behaving like one verifier.

See [`../experiments/E012-correlated-verification.md`](../experiments/E012-correlated-verification.md).

## E013 — independence-aware aggregation

`verification_aggregation_sim.py` compares two aggregation rules on the **same sampled verifier votes**:

1. naive majority over every individual vote;
2. group-balanced majority, where each declared independence group produces one vote.

```bash
python sim/verification_aggregation_sim.py --pretty
```

The reference panel contains 11 verifiers in groups `[7,1,1,1,1]`, each with marginal accuracy `0.75`. The experiment varies within-group error correlation.

The result is deliberately nuanced:

- at correlation `0`, naive majority is better because all 11 votes really are independent;
- from the first tested positive correlation (`0.25`) onward, group balancing is better for this panel geometry;
- at full correlation, naive majority error is about `24.55%`, while group-balanced error is about `10.27%`.

Therefore IDKMesh should **not** blindly discount reviewers by metadata group. It should ultimately estimate independent information from observed evidence and retain uncertainty about that estimate.

See [`../experiments/E013-independence-aware-aggregation.md`](../experiments/E013-independence-aware-aggregation.md).

## E015 — verification phase diagram

`e015_worker.py` sweeps panel size, verifier accuracy, error correlation, and quorum together,
so the interaction between them can be read off one grid instead of one axis at a time.
`e015_analyze.py` turns measured false-accept/false-reject rates into an **effective panel
size**: the number of independent verifiers that would produce the same error.

```bash
python sim/e015_worker.py --seeds 100 --shard 0 --shards 1 --procs 8 --out e015.jsonl
python sim/e015_analyze.py experiments/results/E015-verification-phase-diagram-raw.jsonl.gz
```

The published artifact holds 630 cells at 100 seeds. Headline results:

- 21 correlated verifiers can be worth about 3 independent ones;
- quorum choice is cost-asymmetric — a strict quorum trades false accepts for false rejects,
  and `best_quorum` selects between them under an explicit false-accept cost;
- the standard `N_eff ~= N / (1 + (N-1) rho)` heuristic is **optimistic** for accurate
  verifiers, because real effective size has an accuracy-dependent ceiling that the heuristic
  lacks.

See [`../experiments/E015-verification-phase-diagram.md`](../experiments/E015-verification-phase-diagram.md).

## E016 — live verifier correlation (negative result)

`e016_corpus.py` builds 72 candidate solutions whose ground truth is decided by
executing hidden tests, `e016_agent.py` runs one open-weight verifier against
them, and `e016_analyze.py` measures pairwise error correlation.

```bash
python sim/e016_corpus.py --out benchmarks/e016-verification-corpus/tasks.jsonl
python sim/e016_analyze.py experiments/results/E016-live-verifier-votes.jsonl.gz
```

The published run put 20 verifiers (4 models x 5 prompts) on 20 Azure VMs.
**It failed, and the failure is the result:** 0 of 20 agents discriminated above
chance (mean Youden `J = +0.049`), 6 emitted a single constant verdict for all
72 tasks, and the 20-agent majority vote (accuracy `0.514`) was beaten by a
constant "reject everything" rule (`0.639`).

Accuracy alone could not have caught this — on a 36%-viable corpus, answering
`NO` to everything scores `0.639` and looks like the panel's best verifier. So
`e016_analyze.py` now runs a Bonferroni-corrected discrimination screen
(`youden_j`) before the correlation section and prints a blocking warning when
no agent passes it. **The near-zero `rho` from that run measures the instrument,
not the panel, and must not be quoted as evidence of verifier independence.**

The E012/E013/E015 limitation — `rho` is never measured on real verifiers —
therefore remains open.

See [`../experiments/E016-live-verifier-correlation.md`](../experiments/E016-live-verifier-correlation.md).


## Multi-seed emergence sweeps

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
  tests/test_verifier_correlation_sweep.py \
  tests/test_verification_aggregation_sim.py \
  tests/test_e015_phase_diagram.py \
  tests/test_e015_quorum_frontier.py \
  tests/test_e016_analyze.py
```

This is the same list `.github/workflows/emergence-sim.yml` runs; keep the two in step.

The tests cover deterministic replay, budget invariants, niche preservation, perfect verification compatibility, correlated-error mechanics, sweep configuration, the E013 regime where independence-aware aggregation can help or hurt, the E015 effective-panel-size metrics, and the E016 discrimination screen.

## Interpretation

These simulators are **not** evidence that IDKMesh can automatically evolve a correct complex software system. They are deliberately small falsifiable models for exploring mechanisms.

The useful emergence hypothesis is:

`variation + hard constraints + selection + shared memory + diversity preservation + independent verification`

may be more resilient to vague/changing goals than either pure randomness or optimization against one prematurely fixed objective.

The verification experiments add two related hypotheses:

`nominal verifier count != effective independent evidence count`

and

`independence weighting is useful only when the independence model is informative`

The model should become progressively less toy-like by adding:

- learned correlation/reliability estimates instead of known group labels;
- Bayesian/log-odds and effective-sample-size aggregation;
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
