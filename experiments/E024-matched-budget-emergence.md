# E024 — Matched-budget emergence after a goal change

## Research question

Does E011's synthetic Quality-Diversity advantage survive when every strategy
named by issue #22 receives exactly the same proposal and verification-attempt
budget?

The arms are random search, fixed-scalar evolution, a centralized planner with
one fixed objective, a majority-vote swarm, and constraint-guided
Quality-Diversity.

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
than every simpler baseline under an equal evaluation count.

For this fixed synthetic landscape, the hypothesis would be falsified if its
mean post-change utility AUC were no higher than a baseline, or if the apparent
advantage depended on retrying failed viability checks.

**This hypothesis is now partly falsified as stated.** The majority-vote swarm
matches Quality-Diversity on mean utility AUC and wins about half of paired
seeds. The advantage that survives is one of *reliability*, not of central
tendency — see Result and Interpretation.

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

The strategies otherwise preserve E011's intended differences, and the two
baselines added for issue #22 extend the same contrast:

- random search has no persistent memory;
- scalar evolution retains elites under the original fixed goal;
- the centralized planner retains exactly one plan, refines it by directed local
  search, and scores every candidate against the initial goal only — it is the
  non-evolutionary fixed-objective arm;
- the majority-vote swarm gives each agent one fixed goal hypothesis from the
  plausible set and advances a single consensus only on a strict majority
  preference, so belief diversity exists but is never retained as artifacts;
- Quality-Diversity retains a niche archive and scores candidates against the
  same predefined plausible-goal set used by E011.

Only Quality-Diversity retains alternatives. The planner and the swarm are both
single-artifact arms, which is why their `archive_size` is always 0.

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
| Centralized planner | 0.562637 | 14.065917 (13.983953–14.147882) | 10.934083 (10.852118–11.016047) | 0.562116 |
| Majority-vote swarm | 0.743056 | 18.576406 (17.782235–19.370576) | 6.423594 (5.629424–7.217765) | 0.742021 |
| Quality-Diversity | 0.882456 | 22.061411 (22.008369–22.114453) | 2.938589 (2.885547–2.991631) | 0.888550 |

Paired-seed win rate for Quality-Diversity on post-change utility AUC:

| Baseline | QD wins |
| --- | ---: |
| Centralized planner | 100/100 |
| Random | 100/100 |
| Fixed scalar | 100/100 |
| **Majority-vote swarm** | **51/100** |

The majority-vote result is the one that does not fit the original hypothesis,
and it is bimodal rather than merely noisy:

| Arm | mean | stdev | min | p10 | median | max | seeds with AUC < 16 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Majority-vote swarm | 18.576 | 4.052 | 13.202 | 13.935 | 20.626 | 22.500 | **44/100** |
| Quality-Diversity | 22.061 | 0.271 | 21.221 | 21.728 | 22.091 | 22.491 | **0/100** |

The swarm either tracks the post-change goal and finishes near the ceiling, or
locks onto a stale consensus and finishes far below every other arm. Its
standard deviation is roughly 15x the Quality-Diversity archive's.

## Interpretation

The E011 ordering survives removal of the evaluation-count confound on this
specific landscape **against three of the four baselines**. The result also
sharpens the negative finding for a fixed objective: spending the same number of
evaluations does not make an objective that remains wrong after the environment
changes adaptive. The centralized planner is the strongest form of that finding
— it is the worst arm in the benchmark precisely because it combines a fixed
objective with no retained alternatives.

The majority-vote swarm is the informative negative result. On the summary
statistic the original hypothesis proposed — mean post-change utility AUC — it
is indistinguishable from random search and wins about half of paired seeds
against Quality-Diversity. Reading only the mean would suggest that keeping a
diversity archive buys nothing over letting a swarm vote.

The distribution says something different. The swarm's outcome is close to
bimodal: it either follows the changed goal to near the ceiling or locks onto a
stale consensus, failing below AUC 16 in 44 of 100 seeds where the archive never
fails once. Majority voting collapses the swarm onto a single artifact, so its
belief spread stops functioning as retained diversity and becomes a one-time bet
settled early in the run.

Issue #22 asks whether a population can **reliably** evolve toward a coherent
system. Under that reading the archive's advantage is not that it scores higher
on average — against this baseline it does not, seed for seed — but that it
removes the failure mode. That is a claim about variance and worst case, and it
should be stated that way rather than as a win on means.

The result does **not** show that Quality-Diversity is generally superior. It is
given an informative set of four plausible goals, including the later goal,
while the scalar baseline is deliberately fixed to the initial goal. This is a
test of retaining alternatives under known goal ambiguity, not a learned Goal
Graph.

The strategies accept different numbers of viable candidates despite equal
attempt counts. That is an outcome of where each search policy proposes, not an
extra compute allowance.

> **Follow-up (E026).** This record was produced with a **perfect** verifier
> panel: `false_accept_rate`, `false_reject_rate` and `panel_disagreement_rate`
> are structurally `0.0` in all 100 seeds.
> [`E026-imperfect-verifier-panel.md`](E026-imperfect-verifier-panel.md) reruns
> the same benchmark with the panel E017 and E020 measured — 25 correlated
> partial oracles with an irreducible blind spot. Every conclusion above
> survives unchanged, but E026 shows why that is weak evidence: a falsely
> accepted candidate is non-viable, scores `0.0`, and is discarded by the same
> predicate the verifier was meant to enforce, so this landscape has no
> defect-propagation channel and the test has little power. Do not cite E024 as
> evidence about verification quality.
>
> **Follow-up (E027).** That gap is now closed.
> [`E027-defect-propagation.md`](E027-defect-propagation.md) adds an opt-in
> channel in which an accepted defect can evict a real solution, occupy an
> archive niche, be drawn as a parent, and deliver nothing when it ships. It has
> teeth — random search goes from 0/100 to 94/100 catastrophic seeds under a
> stress panel — and the Quality-Diversity reliability claim above still holds,
> at 0/100 catastrophes in every one of the twenty panel-by-cost cells. E027
> also shows why that survival is narrower than it reads: in this landscape
> apparent quality alone separates viable from non-viable candidates at AUROC
> ~0.94 among accepted candidates, so elitist selection is a second, free
> verifier. The conclusion above may now be cited as surviving a defect channel,
> but **not** as evidence that retained diversity is what defeats verifier
> error.

## Limitations and remaining issue scope

- candidates, objectives, changes, and verifier outcomes are synthetic;
- proposal count is only a compute proxy; wall time, energy, and human attention
  are not measured;
- the plausible goals are supplied by the experimenter rather than learned, and
  the majority-vote swarm's per-agent belief is drawn from that same supplied
  set, so its bimodality is a property of this landscape rather than a measured
  property of real swarms;
- novelty and information gain are not separately measured;
- churn, specialization, malicious workers, and stigmergic traces remain
  outside this benchmark; post-integration defects are outside *this record*
  but are modelled behind an opt-in flag in
  [E027](E027-defect-propagation.md);
- no real software/configuration tasks or hidden tests are used.

Issue #22 therefore remains open. All five baselines it names are now
implemented and reported, which closes the baseline-coverage gap this record
previously listed as an explicit limitation. The issue's remaining scope is
unaffected by this pass: the population is 50-200 agents rather than
100-10,000, the Goal Graph is still supplied rather than learned, and novelty,
information gain, human attention, churn, and adversarial contributors remain
unmeasured.

## Decision

Retain the constraint-guided Quality-Diversity hypothesis as a synthetic
candidate mechanism after budget matching, but **restate it as a reliability
claim rather than a mean-performance claim**. Against a majority-vote swarm the
mean advantage does not hold; the elimination of catastrophic runs does.

Do not promote it to production architecture or claim real-world emergence.

Report paired win rate, spread, and worst case together for this benchmark. A
future arm that reports only a mean could hide exactly the bimodality that makes
majority voting unsuitable, which is the practical lesson of this pass.

The strongest next step is unchanged: replace the predefined plausible-goal
oracle with evidence-driven Goal Graph updates, or move the comparison to
bounded real tasks with measured costs.
