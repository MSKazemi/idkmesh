# E024 — Matched-budget emergence after a goal change

## Research question

Does E011's synthetic Quality-Diversity advantage survive when random search,
fixed-scalar evolution, and Quality-Diversity receive exactly the same proposal
and verification-attempt budget?

## Why this experiment exists

The original E011 sweep was deterministic and included 100 seeds, but it was
not cost matched:

- random search evaluated a fixed fresh batch per generation;
- fixed-scalar evolution retried proposals until it collected an accepted
  batch, so it could spend many more verification attempts;
- Quality-Diversity received a separate archive-initialization budget.

That confound was explicitly recorded in E011. E024 removes it without changing
the historical E011 implementation or artifacts.

## Hypothesis and falsification condition

Working hypothesis: Quality-Diversity will retain higher post-change utility AUC
than both simpler baselines under an equal evaluation count.

For this fixed synthetic landscape, the hypothesis would be falsified if its
mean post-change utility AUC were no higher than either baseline, or if the
apparent advantage depended on retrying failed viability checks.

This is a mechanism-level test. Passing it does not establish that the same
ordering holds for real software, people, or AI-agent populations.

## Matched budget contract

Each strategy receives, per seed:

```text
50 proposals/generation * 50 generations = 2,500 proposals
2,500 proposals * one verifier-panel decision = 2,500 verification attempts
```

Initialization consumes the first generation's budget. No strategy retries
until a proposal is accepted. There is no unverified bootstrap anchor.

The three strategies otherwise preserve E011's intended differences:

- random search has no persistent memory;
- scalar evolution retains elites under the original fixed goal;
- Quality-Diversity retains a niche archive and scores candidates against the
  same predefined plausible-goal set used by E011.

Internal bookkeeping cost is not measured, so this is an evaluation-count
match, not a claim of equal wall time, energy, or human attention.

## Reproduction

```bash
python sim/matched_budget_emergence.py \
  --seeds 100 \
  --seed-start 0 \
  --agents 50 \
  --generations 50 \
  --change-at 25 \
  --bins 8 \
  --pretty
```

Machine-readable result:

`experiments/results/E024-matched-budget-emergence-100-seed-summary.json`

## Measurements

E024 adds two fixed-horizon adaptation measures over the 25 post-change
generations:

```text
utility AUC = sum(post-change best utility)
regret AUC  = sum(1 - post-change best utility)
```

The value `1` is the simulator's declared utility upper bound, so regret is a
transparent synthetic bound-relative quantity rather than regret against a
hidden real-world optimum.

## Result

Every strategy used exactly 2,500 proposal/verification units in every seed.

| Strategy | Post-change mean | Utility AUC mean (95% CI) | Regret AUC mean (95% CI) | Final best mean |
| --- | ---: | ---: | ---: | ---: |
| Random | 0.738707 | 18.467677 (18.418585–18.516768) | 6.532323 (6.483232–6.581415) | 0.747510 |
| Fixed scalar | 0.649188 | 16.229700 (16.156538–16.302861) | 8.770300 (8.697139–8.843462) | 0.646462 |
| Quality-Diversity | 0.882456 | 22.061411 (22.008369–22.114453) | 2.938589 (2.885547–2.991631) | 0.888550 |

Quality-Diversity had higher post-change utility AUC than each baseline in
100/100 paired seed indices.

## Interpretation

The E011 ordering survives removal of the evaluation-count confound on this
specific landscape. The result also sharpens the negative finding for a fixed
objective: spending the same number of evaluations does not make an objective
that remains wrong after the environment changes adaptive.

The result does **not** show that Quality-Diversity is generally superior. It is
given an informative set of four plausible goals, including the later goal,
while the scalar baseline is deliberately fixed to the initial goal. This is a
test of retaining alternatives under known goal ambiguity, not a learned Goal
Graph.

The strategies accept different numbers of viable candidates despite equal
attempt counts. That is an outcome of where each search policy proposes, not an
extra compute allowance.

## Limitations and remaining issue scope

- candidates, objectives, changes, and verifier outcomes are synthetic;
- proposal count is only a compute proxy; wall time, energy, and human attention
  are not measured;
- the plausible goals are supplied by the experimenter rather than learned;
- no explicit majority-goal swarm or separate non-evolutionary central planner
  is implemented;
- novelty and information gain are not separately measured;
- churn, specialization, malicious workers, stigmergic traces, post-integration
  defects, and catastrophic failures remain outside this benchmark;
- no real software/configuration tasks or hidden tests are used.

Issue #22 therefore remains open. E024 completes one previously named
falsification step; it does not satisfy the issue's full simulation scope.

## Decision

Retain the constraint-guided Quality-Diversity hypothesis as a synthetic
candidate mechanism after budget matching. Do not promote it to production
architecture or claim real-world emergence. The strongest next step is to
replace the predefined plausible-goal oracle with evidence-driven Goal Graph
updates, or move the comparison to bounded real tasks with measured costs.
