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


## E017 — measured correlation, item difficulty, and quorum (positive result)

E016 failed to measure `rho` because its LLM verifiers did not discriminate.
E017 uses verifiers that do: **partial test oracles**, each sampling inputs from
one named region of a problem's input domain (`e017_oracles.py`), accepting a
candidate only if it matches the reference implementation there.

```bash
python sim/e017_verify.py --seeds 5 --out e017-votes.jsonl
python sim/e017_analyze.py experiments/results/E017-partial-oracle-votes.jsonl.gz
```

25 verifiers over the 72-candidate corpus, deterministic, ~5 seconds. All 25
pass the discrimination screen, so the correlation is interpretable:

- measured `rho` = **0.587** (0.892 within a region, 0.526 across) — verifiers
  sharing no declared attribute still share **53%** of their errors;
- under majority vote, **25 verifiers are worth 1.00 independent one**, and the
  `N_eff` heuristic overstates that by 1.66x (E015's direction, on real data);
- the flat shared-shock model, fed the measured `rho`, underestimates panel
  error by **1.71x**, and a nested variant matching the block structure barely
  helps. The cause is shape: **11 of ~15 real panel failures are partial**
  (majority wrong, minority right), an outcome shared-shock assigns essentially
  zero probability. A **beta-binomial** item-difficulty model with the same two
  parameters reproduces it (11.2) and is 3.7x closer on panel error;
- errors here are strictly one-sided (368 false accepts, **0** false rejects),
  so majority vote is the wrong rule: unanimity-to-accept cuts error 3.7x
  (0.2083 -> 0.0556) while growing the panel to 25 bought nothing.

`rho` remains a useful summary of a panel, but it is **not a sufficient
statistic for its error**.

See [`../experiments/E017-item-difficulty-and-quorum.md`](../experiments/E017-item-difficulty-and-quorum.md).


## E018 — does E015 survive the corrected dependence model?

E017 showed the shared-shock shape is wrong. `e018_dependence_models.py`
recomputes E015's grid under both models in closed form. They take the same two
parameters and agree exactly at correlation 0 and 1, so any difference is shape.

```bash
python sim/e018_dependence_models.py
```

- item-difficulty predicts **more** error in 438/441 cells (median 1.27x, max
  2.71x), with three high-accuracy/low-correlation exceptions;
- **E015's `N_eff` warning generalises.** The heuristic overstates independence
  in 4% of cells under shared-shock but **100%** under item-difficulty, so the
  hedge "for accurate verifiers" can be dropped: never size a panel with
  `N/(1+(N-1)rho)`;
- **E015's accuracy-dependent ceiling is a shared-shock artifact.** At `p=0.90,
  rho=0.125` shared-shock pins at 4.59 forever while item-difficulty crosses it
  near `n=21` and keeps rising to 5.40 by `n=151`. Saturation is real but lives
  in the *high-correlation* regime instead — and bites harder there (about 1.6,
  not 4.1). The two models saturate in opposite regimes.

`emergence_sim.py` gained `--verifier-dependence {shared-shock,item-difficulty}`,
defaulting to `shared-shock` so every earlier experiment reproduces unchanged.

See [`../experiments/E018-dependence-model-shape.md`](../experiments/E018-dependence-model-shape.md).


## E019 — is E013's aggregation rule safe under the measured model?

E013 found that group-balanced majority beats naive majority from correlation
`0.25` upward. E019 re-runs that under the dependence model E017 measured.

```bash
python -m pytest -q tests/test_e019_group_independence.py
```

- **The crossover survives the shape change.** Under item-difficulty the
  crossover is still at `rho = 0.25`, so unlike E015's ceiling (see E018),
  E013's conclusion does not depend on the shared-shock shape.
- **The crossover disappears when the declared groups are not independent.**
  E017 measured verifiers sharing no declared attribute still sharing 53% of
  their errors. Modelling that — one task difficulty for the whole panel —
  group balancing **never wins at any correlation**, and both rules converge to
  a single verifier's error at `rho = 1`.

So group balancing is not a safe default: it beats naive majority only when the
declared groups carry genuinely independent evidence, which is a property to be
**measured**, not assumed.

See [`../experiments/E019-group-independence-under-item-difficulty.md`](../experiments/E019-group-independence-under-item-difficulty.md).


## E025 — learn reliability and dependence from history

`e025_learned_verifiers.py` removes E013's oracle grouping from learned methods.
It calibrates on labelled history, freezes the model, then evaluates every
method on the same held-out votes under two dependence shapes and three shifts.

```bash
python sim/e025_learned_verifiers.py --histories 40,200,1000 --seeds 20 --heldout-trials 1000 --pretty
```

At 200 history claims under item difficulty, combined weighting cuts error from
`.2312` to `.0597`; after reliability reversal it raises error from `.1071` to
`.2182`. When dependence appears only after calibration, error improves slightly
while Brier score and high-confidence errors worsen. Learned weights are
fallible evidence, not reputation or a confidence guarantee.

See [`../experiments/E025-learned-verifier-reliability.md`](../experiments/E025-learned-verifier-reliability.md).


## Multi-seed emergence sweeps

```bash
python sim/run_emergence_sweep.py --seeds 100 --pretty
```

Verifier parameters can be supplied to the sweep with the same CLI flags.

## E024 — matched evaluation budgets

`matched_budget_emergence.py` runs all five strategies named by issue #22 with an
exact common proposal and verification-attempt budget: random search,
fixed-scalar evolution, a centralized planner with one fixed objective, a
majority-vote swarm, and Quality-Diversity. Initialization consumes the same
budget and acceptance retries are disabled. The benchmark adds fixed-horizon
post-change utility and regret AUC.

```bash
python sim/matched_budget_emergence.py --seeds 100 --pretty
```

The synthetic 100-seed result preserves E011's QD ordering against random,
scalar, and the planner (100/100 paired seeds each), but **not** against the
majority-vote swarm, which wins 49/100 on mean utility AUC while failing
catastrophically in 44/100 seeds. QD's surviving advantage there is reliability,
not central tendency. The benchmark still gives QD the predefined plausible-goal
set and does not measure real compute, energy, or human attention. See
[`../experiments/E024-matched-budget-emergence.md`](../experiments/E024-matched-budget-emergence.md).

### E026 — the same benchmark with an imperfect, correlated panel

The panel is perfect by default, which is how the committed reference above was
produced. `--imperfect-panel` swaps in the panel E017 and E020 measured: 25
partial test oracles, marginal accuracy 0.7956, item-difficulty dependence at
`icc` 0.4513, and an irreducible blind-spot floor `lambda` 0.0556 (implied
marginal pairwise `rho` 0.5873). The individual flags — `--verifiers`,
`--verifier-accuracy`, `--verifier-correlation`, `--verifier-blind-spot`,
`--verifier-dependence`, `--verification-quorum` — then override any part of it,
and are rejected without `--imperfect-panel` so the default cannot drift.

```bash
python sim/matched_budget_emergence.py --seeds 100 --imperfect-panel --pretty
```

An imperfect run adds `configuration.panel_provenance`, a `catastrophic_seeds`
block, and panel-specific limitations; a perfect run emits exactly the schema the
reference artifact was published with. Every conclusion survives the imperfect
panel, but E026 records why that is weak evidence: a falsely accepted candidate
is non-viable, scores 0, and is discarded by the same predicate the verifier was
meant to enforce. See
[`../experiments/E026-imperfect-verifier-panel.md`](../experiments/E026-imperfect-verifier-panel.md).

### E027 — giving an accepted defect a cost

E026's null was a finding about the benchmark, not about Quality-Diversity, so
E027 removes the free viability oracle that caused it. `--defect-channel` makes
every arm rank, retain and ship artifacts by *apparent* quality — what a system
can observe once its panel has accepted something — while the trace still scores
the delivered artifact by ground truth. A falsely accepted artifact can then
evict an incumbent, occupy an archive niche, be drawn as a parent, and deliver
`0.0` when it is the artifact that ships.

`--defect-cost` is the single declared knob, in `[0.0, 1.0]`: `0.0` reproduces
the E024/E026 behaviour exactly and `1.0` (the default) adds no assumption at
all. It is rejected without `--defect-channel`, so the committed reference
sweeps cannot drift.

```bash
python sim/matched_budget_emergence.py --seeds 100 --imperfect-panel --defect-channel --pretty
python sim/e027_defect_propagation.py --mode matrix --seeds 100 --pretty
python sim/e027_defect_propagation.py --mode audit --seed 7 --panel stress --pretty
python sim/e027_defect_propagation.py --mode matrix --seeds 100 \
  --panels stress --costs 0.80,0.85,0.90,0.95 --pretty
```

The channel has teeth — random search goes from 0/100 to 94/100 catastrophic
seeds under the stress panel — and the Quality-Diversity archive still never
fails catastrophically. E027 records why that survival is narrower than it
looks: apparent quality alone separates viable from non-viable candidates well
enough that elitist selection acts as a second, free verifier. See
[`../experiments/E027-defect-propagation.md`](../experiments/E027-defect-propagation.md).

## Tests

With `pytest` installed:

```bash
python -m pytest -q \
  tests/test_emergence_sim.py \
  tests/test_emergence_sweep.py \
  tests/test_verifier_correlation_sweep.py \
  tests/test_verification_aggregation_sim.py \
  tests/test_e025_learned_verifiers.py \
  tests/test_e015_phase_diagram.py \
  tests/test_e015_quorum_frontier.py \
  tests/test_e016_analyze.py \
  tests/test_e017_item_difficulty.py \
  tests/test_e018_dependence_models.py \
  tests/test_e019_group_independence.py \
  tests/test_e020_quorum_frontier.py \
  tests/test_matched_budget_emergence.py \
  tests/test_e026_archive_contamination.py \
  tests/test_e027_defect_propagation.py
```

This is the same list `.github/workflows/emergence-sim.yml` runs; keep the two in step.

The tests cover deterministic replay, budget invariants, niche preservation, perfect verification compatibility, correlated-error mechanics, sweep configuration, the E013 regime where independence-aware aggregation can help or hurt, E025's calibration separation and preserved shift failures, the E015 effective-panel-size metrics, the E016 discrimination screen, the E017 item-difficulty model, the E018 model comparison, the E019 group-independence result, the E020 quorum frontier, E024's exact matched-evaluation contract, E026's archive-contamination audit, and E027's defect-propagation channel — its matched budget, its cost-zero identity with the channel off, and the demonstration that an accepted defect now persists and does harm.

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

## E020 — the quorum frontier under the measured shape (model-selection result)

`sim/e020_quorum_frontier.py` reuses E017's 1800 real verdicts and the E016 corpus
base rate to ask which acceptance quorum a panel should use, under each candidate
dependence model.

```bash
python3 sim/e020_quorum_frontier.py
```

Deterministic: closed-form distributions over a fixed artifact, no sampling.

- Fitted to the real panel, the **shared-shock model says no quorum beats majority
  (1.00x)**; the measured gain is **3.75x**.
- The optimal quorum spans **12-14 of 25** under shared-shock but **1-25** under
  item-difficulty, across the same sweep of correlation, base rate and cost ratio.
  Shape moves the optimum by up to 12 verifiers; `rho` moves it by 1.
- Neither two-parameter model predicts the unanimity floor: shared-shock is 2.13x
  too high, the beta-binomial 1.77x too low. The real floor `lambda = 0.0556` is the
  4 defects every verifier misses — a panel blind spot, not a correlated shock.

See [`experiments/E020-quorum-frontier-under-measured-shape.md`](../experiments/E020-quorum-frontier-under-measured-shape.md).
