# E050 — Agent churn at a matched budget: five E024 arms, two churn models, five churn fractions

**Status:** complete. **Evidence level:** synthetic mechanism only. Every candidate, goal, verdict
and "agent" below is simulated; nothing here is a result about real agents, real people or real
contributor churn. **Generator:** `sim/e050_churn.py` ·
**Artifact:** [`results/E050-churn.json`](results/E050-churn.json) ·
**Builds on:** [E024](E024-matched-budget-emergence.md); **sits beside**
[E049](E049-derived-measurements.md), which listed churn as not measured.

## Research question

[Issue 22](https://github.com/MSKazemi/idkmesh/issues/22) names "agent churn" among the things the
emergence simulations should model and "resilience to churn" among the measurements. E024 says in
its limitations that the benchmark "does not model churn", and E049 repeats that agents never join or
leave. At a fixed proposal-plus-verification budget, what happens to each of the five arms'
post-change utility and catastrophic-seed count when a fraction `f` of the agents is replaced by
fresh agents every generation, and does any arm's lead over the archive change sign?

## Why this experiment exists

No churn is modelled anywhere in the simulation suite, so no statement about churn can currently be
made for any arm. The question is narrower than it sounds, because in E024 almost nothing lives in
an agent. The archive, the elite pool, the planner's incumbent and the swarm's consensus artifact are
shared; only the majority swarm gives each agent something private (one goal belief). The honest
experiment is therefore about **where each architecture keeps its state**, and this record says so
rather than presenting an unreachable arm as "robust".

## Method

**What churn is.** From generation 1, each generation `floor(f * agents + 0.5)` of the 50 agent slots
is drawn without replacement and refilled by fresh agents (5, 13, 25 and 50 slots at
`f = 0.1, 0.25, 0.5, 1.0`; `f = 1.0` is the limit where every agent is replaced every generation).
The budget is unchanged: `agents * generations = 2,500` proposals and verifications per arm.

**What "fresh" means, per arm.**

| arm | state that survives churn | what a fresh agent lacks |
| --- | --- | --- |
| random | none; agents are memoryless | nothing |
| scalar | shared elite pool | nothing private (it held none) |
| qd | shared MAP-Elites archive | nothing private (it held none) |
| planner | one shared incumbent | nothing private (it held none) |
| majority | shared consensus artifact | its own goal belief, re-drawn uniformly from the four plausible goals |

**Two churn models**, because the answer depends on which is meant:

- **memory.** A fresh agent loses its private memory and nothing else. Only the majority swarm has any,
  so `random`, `scalar`, `qd` and `planner` are unchanged by construction. This is a statement about
  state *placement* and is not a finding that those arms are robust to anything.
- **cold-start.** A fresh agent also has no access to the shared state for its first proposal, which is
  a blind random candidate instead of a mutation of the archive, elite, incumbent or consensus. The
  shared state itself still survives. For the four arms with no private state this is exactly a
  **blind-proposal dilution at rate `f`**, i.e. it cannot be told apart from raising an exploration
  rate; only the majority swarm's belief redraw is churn-specific.

Shared state surviving every departure is an assumption of the placement comparison, not a property
of real shared structures. The version in which state leaves with its authors is not measured.

**No E024 result changes.** E024's code is untouched. `sim/e050_churn.py` re-implements the five arm
loops line for line with churn hooks that do nothing at `f = 0`, because an arm cannot be extended
without editing E024's functions. Equality is checked, not assumed: at `f = 0` every arm row, trace
included, equals `matched_budget_emergence.run_seed`'s row, and the `aggregate` block rebuilt from
the `f = 0` cell matches the committed E024 artifact by digest:

```text
committed  64419a7dcc7f913688efefae1e994302fb043e596a7ed8c32cd0097f4190f78a
replayed   64419a7dcc7f913688efefae1e994302fb043e596a7ed8c32cd0097f4190f78a   matches: true
```

**Random streams.** Each arm keeps E024's proposal and verifier streams (the same per-arm seed offset,
as a new arm extending an existing one must). All churn randomness (which slots, which belief, which
blind candidate) comes from a third stream keyed to the same arm seed, so churn never consumes a
proposal draw; an arm's original proposals are still drawn and then replaced for fresh slots.

**Statistics.** Catastrophic seed = post-change utility AUC below E024's absolute cutoff
`0.64 * 25 = 16.0`, applied unchanged at every `f`. Exact Clopper-Pearson intervals; seeded percentile
bootstrap (2,000 resamples, own `random.Random` keyed by label) for mean AUC and paired mean
differences; all tests paired over the same 100 seeds, exact McNemar on catastrophic seeds and exact
sign test on AUC. The `f = 0` cell is shared by both models and is counted once.

**Multiple comparisons: 152 p-values**, so the Bonferroni level is `0.00033`. Family 1 is the archive
against each of four baselines, two tests, in nine cells (`f = 0` once plus four `f` for each model)
= 72. Family 2 is each arm's own change from `f = 0`, two tests, in eight cells = 80. All p-values
below are uncorrected; a `*` marks those below `0.00033`. Tests on arms the memory model cannot change
are counted anyway (guaranteed ties), which makes the level conservative.

**Registration.** None. The grid, both models and the `f = 1.0` limit were chosen before any aggregate
was computed; seed 0's five AUCs were viewed once, at six settings, while smoke-testing the
implementation.

## Reproduction

```bash
PYTHONPATH=. python sim/e050_churn.py \
  --check-e024 experiments/results/E024-matched-budget-emergence-100-seed-summary.json \
  --pretty --workers 4 --output experiments/results/E050-churn.json
```

100 seeds, 50 agents, 50 generations, change at 25, 8 bins, the E024 perfect panel; nine cells of 100
seeds and five arms each (estimated at roughly seven CPU-minutes, not timed end to end). `results/` is
gitignored, so the artifact is committed with `git add -f`, as its neighbours are.

## Result 1 — memory churn: only the majority swarm can move, and churn helps its reliability

Post-change utility AUC, mean (95% bootstrap CI), and catastrophic seeds out of 100. The horizon is 25
generations, so the maximum is 25.

| `f` | random | scalar | planner | majority | qd |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 (E024) | 18.47, 0 | 16.23, 25 | 14.07, 100 | 18.58 (17.83-19.36), **44** | 22.06 (22.01-22.11), 0 |
| 0.1 | same | same | same | 18.60 (18.12-19.06), 20 | same |
| 0.25 | same | same | same | 18.32 (17.99-18.66), 7 | same |
| 0.5 | same | same | same | 17.91 (17.65-18.19), 6 | same |
| 1.0 | same | same | same | 17.73 (17.56-17.91), **0** | same |

"Same" is exact: the whole row, trace included, is identical to `f = 0` for those four arms at every
`f` (checked by digest in the artifact), which is the by-construction result stated above and carries no
information about robustness.

The majority swarm's own change from `f = 0` (paired over seeds): catastrophic seeds 44 to 20, 7, 6 and 0
(McNemar against `f = 0`, churned-only / `f = 0`-only: `10/34` p = 0.00039, `4/41` p = 9.3e-09 `*`,
`4/42` p = 5.1e-09 `*`, `0/44` p = 1.1e-13 `*`). Its mean AUC does **not** rise: the paired mean change
is `+0.02` at `f = 0.1` and `-0.84` (-1.68 to -0.007) at `f = 1.0`, and no sign test on AUC reaches
significance (smallest p = 0.27). Churn removes the swarm's catastrophic seeds and its lucky high seeds
together: seeds with AUC of at least 21 fall from 49 to 21, 2 and 0 at `f = 0, 0.1, 0.5, 1.0` (counted from the
per-seed record), which leaves it in the middle (median 17.54 at `f = 1.0`, range 16.35 to 20.49).

Against the archive (paired; the archive minus the swarm, catastrophic counts as swarm-only / archive-only):

| `f` | mean AUC lead (95% CI) | AUC: archive higher / lower | catastrophic seeds, swarm-only / archive-only | McNemar p |
| --- | ---: | ---: | ---: | ---: |
| 0 | +3.49 (+2.72 to +4.32) | 51 / 49, p = 0.92 | 44 / 0 | 1.1e-13 `*` |
| 0.1 | +3.46 (+2.98 to +3.93) | 91 / 9, p = 3.3e-18 `*` | 20 / 0 | 1.9e-06 `*` |
| 0.25 | +3.75 (+3.39 to +4.07) | 97 / 3, p = 2.6e-25 `*` | 7 / 0 | 0.016 |
| 0.5 | +4.16 (+3.89 to +4.42) | 100 / 0, p = 1.6e-30 `*` | 6 / 0 | 0.031 |
| 1.0 | +4.33 (+4.15 to +4.51) | 100 / 0, p = 1.6e-30 `*` | 0 / 0 | 1.0 |

**Reading.** Two things move in opposite directions. The archive's mean lead over the swarm *grows*
with churn (`+3.49` to `+4.33`), and the paired AUC comparison goes from a coin flip (`51/49`) to
`100/0`, because churn takes away the swarm's high mode. The archive's *reliability* lead over the swarm
shrinks to nothing: E024's headline "0 of 100 catastrophic seeds against 44" becomes `0` against `6` at
`f = 0.5` (not significant after correction) and `0` against `0` at `f = 1.0`. A plausible mechanism, not
tested here, is that a swarm whose initial beliefs happen to point away from the changed goal stays
stuck in the fixed-belief arm, while re-drawing beliefs gives it another draw.

## Result 2 — cold-start churn: dilution that hurts the archive and helps the fixed-objective arms

Post-change utility AUC, mean (95% bootstrap CI), and catastrophic seeds out of 100.

| `f` | random | scalar | planner | majority | qd |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 18.47, 0 | 16.23, 25 | 14.07, 100 | 18.58, 44 | 22.06 (22.01-22.11), 0 |
| 0.1 | 18.47, 0 | 16.67 (16.60-16.74), 1 | 14.11, 100 | 18.28, 19 | 22.01 (21.95-22.06), 0 |
| 0.25 | 18.47, 0 | 17.19 (17.13-17.26), 0 | 14.17, 100 | 18.06, 9 | 21.95 (21.89-22.01), 0 |
| 0.5 | 18.47, 0 | 17.76 (17.71-17.81), 0 | 14.07, 99 | 17.52, 5 | 21.78 (21.71-21.85), 0 |
| 1.0 | 18.47, 0 | 18.65 (18.60-18.70), 0 | 14.41 (14.16-14.65), 87 | 17.04 (16.89-17.18), 9 | 20.79 (20.70-20.88), 0 |

(Random search is unchanged because a blind proposal is what it already makes.)

Each arm's own change from `f = 0`, paired over seeds:

| arm | mean AUC change at `f = 0.1 / 0.25 / 0.5 / 1.0` | seeds lower / higher at `f = 1.0`, p |
| --- | --- | --- |
| scalar | +0.44 `*`, +0.96 `*`, +1.53 `*`, **+2.42** (+2.32 to +2.51) `*` | 0 / 100, p = 1.6e-30 `*` |
| qd | -0.06, -0.11, -0.28 `*`, **-1.27** (-1.37 to -1.17) `*` | 99 / 1, p = 1.6e-28 `*` |
| planner | +0.05, +0.10, +0.01, +0.34 (+0.09 to +0.59) | 43 / 57, p = 0.19 |
| majority | -0.30, -0.52, -1.05, -1.54 (-2.35 to -0.76) | 55 / 45, p = 0.37 |

The scalar arm's 25 catastrophic seeds go to 1, 0, 0 and 0 (churned-only / `f = 0`-only `0/24`, p = 1.2e-07
`*`, then `0/25` p = 6e-08 `*`); the planner's 100 go to 100, 100, 99 and 87 (`0/13` at `f = 1.0`, p = 0.00024
`*`). The archive has **0** catastrophic seeds at every `f` in both models.

The archive's lead over each baseline in mean AUC (archive minus arm; the archive is higher in 100 of 100
seeds against random, scalar and planner at every `f` in this model):

| `f` | random | scalar | planner | majority |
| --- | ---: | ---: | ---: | ---: |
| 0 | +3.59 | +5.83 | +8.00 | +3.49 |
| 0.1 | +3.54 | +5.34 | +7.89 | +3.73 |
| 0.25 | +3.48 | +4.76 | +7.78 | +3.89 |
| 0.5 | +3.32 | +4.02 | +7.71 | +4.26 |
| 1.0 | +2.32 | +2.14 | +6.38 | +3.75 |

**Where the lead changes sign: nowhere.** For every arm, in both models, the archive's paired mean AUC
lead keeps its `f = 0` sign across the whole grid (`first_sign_change_fraction` is `null` in all eight
cells of the artifact). The nearest approach is the scalar arm under cold-start at `f = 1.0`, where the
lead has fallen from `+5.83` to `+2.14`. That statement is about the mean AUC lead on this grid; the
catastrophic-seed lead against the majority swarm does vanish under memory churn at `f = 1.0` (Result 1),
which is a tie, not a reversal.

## What undercuts the archive's advantage

- **The archive's reliability lead over the swarm does not survive churn.** E024's catastrophic-seed
  contrast (`0/100` against `44/100`) falls to `0` against `6` at `f = 0.5` and `0` against `0` at
  `f = 1.0` under the memory model, because the swarm's catastrophes disappear. Churn is *good* for the
  swarm's reliability in this model, so "the archive is safer than the swarm" is a statement about a
  swarm that never turns over its members.
- **Cold-start churn costs the archive and benefits its competitors.** The archive loses `1.27` AUC at
  `f = 1.0` (99 of 100 seeds lower) while the scalar arm gains `2.42` and ends above random search
  (`18.65` against `18.47`); the archive's lead over the scalar arm falls by 63% (`+5.83` to `+2.14`).
  The archive is the only arm whose mean AUC change is below zero with a sign test that clears the
  corrected level (`f = 0.5` and `1.0`); the swarm's mean AUC also falls with `f` but its sign tests do not
  reach significance (p = 0.27 to 0.48).
- **The "robust to churn" reading is not available for any arm.** In the memory model four arms are
  unchanged by construction; in the cold-start model the effect on them is an exploration-rate effect
  (the fixed-objective arms were under-exploring after the goal change) and would appear without any
  agent leaving. Neither model tests whether an architecture survives *real* turnover.
- **The archive's remaining lead at `f = 1.0` comes from retention, not direction.** With every proposal
  blind the archive still beats random search by `+2.32` (65% of its `f = 0` lead, 2.22 to 2.42), and the
  scalar arm, which retains an elite pool but no niches, beats it by only `+0.18`. This is descriptive;
  it suggests the archive's value under dilution is what it keeps and how it organises it.
- **The archive's own AUC advantage over the majority swarm at `f = 0` is itself a coin flip**
  (`51/49`, p = 0.92); that is E024's published result and is repeated here, not new.

## What is not measured

- **State that leaves with its authors.** The shared archive, elite pool, incumbent and consensus always
  survive every departure. The version where retained work walks out with the people who held it is the
  harsher test for the archive and is not run.
- **Onboarding as anything but one blind proposal.** No learning curve, mentoring, partial memory or
  skill difference between newcomers and veterans.
- **Who churns.** Departures are uniform at random over slots, never correlated with a belief, a niche or
  a region, and never adversarial.
- **Churn as a process in time.** A fixed fraction per generation: no bursts, no trend, no change in the
  population size.
- **Malicious or faulty replacements.** Every fresh agent is honest ([E036](E036-adversarial-contributors.md)
  models adversarial contributors separately).
- **Human attention, energy and wall time**, and **real people**: nothing here models contributor
  retention or attrition in any real project.

## Caveats and what this does not show

- This is **not** a model of real human or agent churn. "Agents" are proposal slots; "fresh" means an
  empty private belief and, under cold-start, one blind candidate.
- The memory model's null for four arms is a property of where E024 puts state. It is reported, not
  celebrated.
- Cold-start churn and an exploration-rate increase are the same operation for four arms, so the
  gains of the scalar and planner arms must not be read as "churn helps".
- The mean-AUC and catastrophic-seed readings can disagree (Result 1), so neither is quoted alone.
- The `f = 1.0` cell is a limit, not a realistic setting. Read the grid below `0.5` first.
- Perfect verifier panel only; 100 seeds of one landscape, one change size and one direction
  (E033-E035 show the archive's lead depends on both).
- The mechanism offered for the swarm's catastrophe reduction is a hypothesis, not tested here.
- 152 p-values were computed; most headline contrasts clear the corrected level and the ones that do not
  are marked. The grid was fixed before aggregation but no outcome was preregistered.

Issue 22 stays open. This record adds the churn measurement for the five arms and lists what remains
unmeasured.

## Decision

Report churn as two readings, never one. Under memory loss only per-agent state matters, and E024's
arms keep almost none, so the result is about state placement. Under cold start it is a
blind-proposal dilution that the archive pays for and the fixed-objective arms profit from. State that
the archive's reliability advantage over the majority swarm is specific to a swarm that never turns over
its members, and do not cite either reading as the archive being robust to churn. Keep state that leaves
with its authors, correlated departures and arrival processes on the open list.

## Tests and provenance

- `tests/test_e050_churn.py` (fast, tiny configuration): `f = 0` rows equal E024's, including under an
  imperfect panel; the budget is matched at every `f` and model; E024's shared code is untouched; the
  churn schedule's size, determinism, bounds and zero-draw property; what "fresh" changes per arm and
  per model; McNemar and the paired difference on hand-built tables; the sign-change rule; and the
  p-value count.
- `tests/test_e050_committed_artifact.py` (`sim`, nightly): the committed artifact's E024 digest check,
  the memory-model digest identity, the first seeds re-derived in four cells, and the summaries
  recomputed from the per-seed record.
- Every number above is read from the committed artifact.
