# E011 — Emergence from vague goals

## Question

Can many exploratory agents move toward a coherent and adaptable system when the initial objective is incomplete, provided the system has hard constraints, diversity preservation, evidence-driven selection, and shared memory?

## Status

**Prototype experiment.** The current implementation is intentionally synthetic. It is designed to test mechanisms before applying them to real software engineering.

## Hypothesis

A constraint-guided Quality-Diversity system should be more resilient to a later goal/environment change than:

1. pure random search with no structured memory; and
2. evolutionary search that prematurely commits to one scalar interpretation of the original goal.

The experiment does **not** claim that randomness plus evolution automatically creates correct complex software.

## Core principle under test

`variation + constraints + selection + shared memory + diversity + verification -> adaptive capability`

Randomness is used to generate candidates, not to accept them.

## Model

Each candidate architecture has five competing traits:

- reliability;
- adaptability;
- efficiency;
- simplicity;
- security.

A finite resource budget creates trade-offs. Reliability and security are hard viability constraints.

The environment begins with one preference vector and changes halfway through the run. This is a toy representation of discovering that the original goal was incomplete or that requirements changed.

## Strategies

### A — Random

Generate fresh random candidates each generation. Viability constraints still apply, but there is no persistent structured search.

### B — Fixed scalar evolution

Select and mutate candidates according to a single fixed objective derived from the initial goal. The objective does not change after the environment changes.

This intentionally models premature project convergence.

### C — Constraint-guided Quality-Diversity

Maintain a MAP-Elites-like archive across behavioral niches based on adaptability and efficiency. Within each niche, prefer candidates that perform robustly across several plausible goal interpretations.

This models an IDKMesh design where competing approaches survive while uncertainty remains high.

## Reference command

```bash
python sim/emergence_sim.py \
  --strategy all \
  --seed 7 \
  --agents 200 \
  --generations 120 \
  --change-at 60 \
  --pretty
```

## Initial reference observation

For seed 7, the fixed scalar strategy achieved the strongest value just before the goal change (`0.821916`) but had substantially lower mean value afterward (`0.657890`).

The QD archive was slightly weaker before the change (`0.806625`) but had the strongest post-change mean (`0.897018`) and occupied 64 niches.

Fresh random exploration had post-change mean `0.784783` but used unstructured repeated sampling.

These numbers are recorded in `experiments/results/E011-reference-seed7.json`.

They are **not statistically significant evidence**. One seed and one synthetic landscape are only a smoke test.

## Falsification path

The hypothesis should be weakened or rejected if, across well-designed benchmark families and matched compute budgets:

- QD does not outperform simpler baselines after hidden-goal changes;
- preserving niches costs more than the adaptability it provides;
- the advantage disappears when plausible goals are misspecified;
- a simpler Bayesian, bandit, or multi-objective method performs as well or better;
- verification and coordination overhead remove the gain;
- the method optimizes proxy traits while real software quality degrades.

## Next experiment upgrades

1. Run at least 100 seeds and report confidence intervals.
2. Add regret and post-change area-under-curve metrics.
3. Match evaluations/compute budgets more carefully across strategies.
4. Add verifier agents with controllable accuracy and correlated failure.
5. Add a mutable Goal Graph rather than fixed predefined plausible goals.
6. Add stigmergic traces: failures/evidence should influence later search.
7. Add multi-armed-bandit resource allocation across niches.
8. Add churn, latency, worker specialization, and malicious workers.
9. Replace synthetic traits with small real software tasks/configurations.
10. Measure `Verified Useful Work / (Human Attention + Compute Cost)`.

**Follow-up:** E022 completes items 2 and 3 for the original three-strategy
synthetic comparison. It gives every strategy exactly 2,500 proposal and
verification attempts per seed, adds post-change utility/regret AUC, and retains
the QD ordering across 100 seeds. This removes one known confound but does not
resolve the supplied plausible-goal advantage or establish real-world evidence.
See [`E022-matched-budget-emergence.md`](E022-matched-budget-emergence.md).

## Relationship to IDKMesh architecture

If the hypothesis survives progressively stronger experiments, the corresponding architecture would be:

- **Constitution:** hard safety, provenance, verification, and resource invariants.
- **Goal Graph:** explicitly uncertain and revisable intent.
- **Variation engine:** humans and agents generate competing proposals.
- **Viability gates:** reject unsafe or invalid candidates before promotion.
- **Diversity archive:** preserve multiple strong niches while uncertainty is high.
- **Evidence system:** experiments and independent verification update confidence.
- **Resource allocator:** shift compute/attention toward promising or informative branches without starving alternatives.
- **Memory:** retain failures, evidence, artifacts, and lineage so the mesh does not repeatedly rediscover the same mistakes.

This is the concrete meaning of a **Constitutional Evolutionary Mesh**: specify the laws under which the system may adapt, rather than pretending to specify its final form in advance.
