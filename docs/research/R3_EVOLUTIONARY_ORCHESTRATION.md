# R3 — Evolutionary Orchestration With Verification and Diversity

**Issue:** #32  
**Status:** Synthetic mechanism experiment

## Research question

Can evolutionary search discover useful IDKMesh orchestration policies **without** collapsing into one benchmark-specialized monoculture, optimizing activity instead of value, or promoting its own output into production?

R3 treats evolution as a proposal generator. Verification, held-out evaluation, and human review remain outside the evolutionary loop.

## Core loop

```text
initial population
      |
      v
changing training-task distribution
      |
      v
multi-objective evaluation
      |
      v
Pareto fronts + novelty-aware survivor selection
      |
      +----> diversity archive
      |
      v
crossover + mutation + random immigrants
      |
      v
next generation
      |
      ...
      |
      v
fixed train-reference evaluation
      |
      v
pre-heldout champion selected
      |
      v
held-out families evaluated once
      |
      v
human-readable evidence report
      |
      v
NO autonomous production promotion
```

## Genome

The first compact synthetic orchestration genome contains:

```text
worker_count
structural diversity_mix
decomposition_depth
replication_factor
verifier_depth
exploration_temperature
timeout_budget
escalation_threshold
```

This is deliberately small enough to inspect and mutate. It is not intended to freeze the eventual Verified Swarm Runner policy schema.

Bounds are explicit so mutation cannot create unbounded worker counts or nonsensical policy values.

## Synthetic task families

### Training families

The initial training split contains five named families representing different pressures:

- routine fixes;
- cross-file refactors;
- API changes;
- test generation;
- security-sensitive work.

Each family has synthetic controls for:

- difficulty;
- ideal decomposition depth;
- value of diversity;
- verification need;
- error-correlation pressure;
- security pressure;
- latency pressure.

### Held-out families

The initial held-out split contains three different families:

- ambiguous cross-module work;
- performance-constrained work;
- adversarial regression work.

Train and held-out family names are validated as disjoint. The complete split is hashed and recorded in the result.

These are **mechanism-test environments**, not claims that real coding tasks follow these distributions.

## Held-out discipline

The most important R3 rule is:

> **Held-out families cannot participate in evolutionary selection.**

During every generation:

- mutation sees no held-out result;
- crossover sees no held-out result;
- Pareto selection sees no held-out result;
- survivor selection sees no held-out result;
- the novelty archive sees no held-out result.

After the final generation, all surviving/archive candidates are first re-evaluated on one fixed uniform **training reference distribution**.

A single `preheldout_champion` is selected from the train Pareto front **before** any held-out evaluation occurs.

Only then are final train-Pareto candidates evaluated on held-out families.

The output records:

```text
heldout_used_for_evolutionary_selection = false
heldout_burned_after_final_evaluation = true
champion_selected_before_heldout = true
```

Once the held-out output is inspected, that split should not be called untouched in future tuning runs. A new independent split is required for a new confirmatory claim.

## Changing training distribution

A fixed public benchmark is easy to overfit.

R3 therefore changes the relative weighting of training families every generation while keeping the distribution identical for every genome evaluated within that generation.

This tests adaptation under non-stationary emphasis without giving one candidate an easier workload than another.

The final train-reference evaluation returns to a fixed uniform distribution so final candidates are comparable on one common training surface.

## Candidate generation model

The synthetic evaluator models interactions rather than one monotonic "more agents = better" rule.

Examples:

- worker count can improve search but introduces coordination penalty;
- diversity can reduce error correlation and help diversity-valuing families;
- replication provides less independent value when error correlation is high;
- decomposition helps when depth matches the task family, but excessive depth adds overhead;
- stronger verification reduces false acceptance but costs latency/attention;
- higher escalation can reduce autonomous risk only by consuming more attention;
- timeout fit differs by task difficulty.

Trials are sampled reproducibly from a seed derived from:

```text
experiment seed
+ context
+ generation
+ genome id
+ task-family name
```

A run with the same configuration is exactly reproducible.

## Fitness is not one scalar

R3 deliberately does **not** optimize raw output count, activity, commits, or one public benchmark score.

The initial Pareto objectives are:

### Maximize

- verified success rate;
- worst-family verified success rate.

### Minimize

- security failure rate;
- regression rate;
- error correlation;
- compute per task;
- latency per task;
- human attention per task;
- orchestration complexity.

A genome dominates another only if it is no worse on **every** objective and strictly better on at least one.

This makes trade-offs visible rather than hiding them inside one unexplained fitness coefficient.

## Complexity penalty

Complexity is itself a minimized Pareto objective derived from:

- worker count;
- decomposition depth;
- replication factor;
- verifier depth;
- diversity mix;
- exploration temperature.

This does not guarantee simple policies, but it prevents an arbitrarily elaborate orchestration from being considered strictly superior merely because it purchases small improvements with more moving parts.

## Diversity preservation

### Novelty-aware survivor tie-breaking

When a Pareto layer cannot fit entirely into the survivor budget, candidates with larger genotype distance from the rest of the population are preferred before train-performance tie-breaks.

### Diversity archive

Novel Pareto candidates can enter a bounded archive if their average distance from nearby archived genomes exceeds the configured threshold.

Archived genomes can later become parents.

### Exploration floor

At least a configurable fraction of every new population is filled with random immigrants.

This makes permanent lock-in harder even if mutation/crossover converge around one lineage.

## Crossover and mutation

Crossover chooses each genome field from one of two parents.

Mutation changes one bounded field at a time, for example:

- ±1 worker;
- ±1 decomposition/replication/verifier level;
- Gaussian perturbation of diversity, temperature, or escalation;
- ±1 timeout budget.

Mutation and crossover are stochastic but seed-reproducible.

## Fixed-policy baseline

R3 always evaluates a simple fixed baseline genome:

```text
workers = 3
diversity = 0.25
decomposition = 2
replication = 1
verifier depth = 2
temperature = 0.20
timeout = 5
escalation = 0.50
```

The baseline is evaluated on both the final train reference and held-out families.

Evolution therefore has something concrete to beat. "It evolved" is not evidence of improvement.

## Raw failure evidence

Every evaluation retains, per family:

- verified success;
- false acceptance;
- security failure;
- regression;
- escalation;
- error correlation;
- compute;
- latency;
- human attention.

Failures and regressions are not deleted when a genome performs well overall.

Each generation retains every candidate evaluation plus:

- family distribution;
- Pareto-front ids;
- survivor ids;
- archive ids.

## Overfitting check

For final train-Pareto candidates, R3 computes:

```text
train verified-success rate
-
heldout verified-success rate
```

A configurable positive gap threshold raises an `overfit_flag`.

It also records held-out success and security deltas against the fixed baseline.

This is a diagnostic, not proof of causal generalization.

## Promotion boundary

R3 cannot change production configuration.

The output always contains:

```text
autonomous_promotion = false
status = human_review_required
```

Even when synthetic held-out evidence looks favorable, the strongest possible recommendation is:

```text
consider for separate human-reviewed experiment
```

The policy must then be evaluated on an **independent real-task experiment** before production consideration.

A bad held-out result produces:

```text
do not promote from this evidence
```

## Human-readable evidence report

The CLI can emit both raw JSON and a concise Markdown evidence report:

```bash
python -m randomness_lab.r3 \
  --population 24 \
  --generations 12 \
  --trials 80 \
  --seed 42 \
  --output results/r3.json \
  --report results/r3.md
```

The report compares the pre-heldout champion with the fixed baseline on held-out metrics and includes:

- verified success;
- security failure;
- regression;
- compute;
- latency;
- human attention;
- train→heldout gap;
- overfit count;
- explicit human-review decision.

## Acceptance criteria mapping for #32

The first harness is designed to satisfy the mechanism-level acceptance criteria:

- simple fixed-policy baseline;
- no output-volume fitness;
- held-out task families not used in evolution;
- raw failures/regressions retained;
- machine-readable result;
- human-readable promotion evidence;
- no autonomous policy promotion.

## Limitations

This first R3 experiment does **not** prove that evolutionary orchestration improves real coding agents.

It does not yet model:

- actual model providers or prompts;
- real task graphs;
- real verifier correlation;
- real compute prices;
- benchmark contamination in model pretraining;
- adversarial agents gaming the fitness process;
- long-term policy co-evolution;
- policy compatibility/version migration;
- online safe exploration in production.

The synthetic model is useful only if it exposes mechanism failures and helps design the real experiment.

## Next evidence step

After the harness is validated:

1. commit a reproducible synthetic reference run;
2. identify any overfit/negative regimes rather than only the champion;
3. define an adapter from real Verified Swarm Runner experiment metrics into the same multi-objective representation;
4. freeze a new held-out real-task corpus;
5. evolve only on a separate training corpus;
6. select the champion before opening held-out results;
7. publish all failed candidates and promotion evidence;
8. never auto-promote the winning policy.

The desired result is not "evolution wins." The desired result is a reproducible map of **when evolutionary orchestration generalizes, when it overfits, and when a simple fixed policy is better**.
