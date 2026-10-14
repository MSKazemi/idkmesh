# E049 — Recovery time, viable-niche coverage and cost per improvement for the five E024 arms

**Status:** complete. **Evidence level:** synthetic mechanism only. Every candidate, goal,
verdict and cost below is simulated; nothing here is a result about real agents or real people.
**Generator:** `sim/e049_derived_measurements.py` ·
**Artifact:** [`results/E049-derived-measurements.json`](results/E049-derived-measurements.json)
· **Builds on:** [E024](E024-matched-budget-emergence.md), read post hoc.

## Research question

[Issue 22](https://github.com/MSKazemi/idkmesh/issues/22) lists measurements that the emergence
simulations never aggregated across all five baselines. Three of them can be computed from what
E024 already runs:

1. **Recovery time from an incorrect initial objective.** How long after the goal changes does each
   arm deliver an artifact above an *absolute* utility bar?
2. **Diversity of viable architectures.** How many distinct viable niches does each arm's verified
   work reach, counted the same way for every arm?
3. **Compute per verified improvement.** How many proposals does each arm spend per accepted
   improvement?

## Why this experiment exists

Each of the three has a stand-in in the repository that does not answer the question:

- `recovery_generations` in `sim/emergence_sim.py` compares an arm with 95% of **its own** final
  value. An arm that sits on a low plateau "recovers" at generation 0, and
  `sim/matched_budget_emergence.py` records that the field is not aggregated.
- `archive_size` exists for the Quality-Diversity arm only and is `0` by construction for the other
  four, so it cannot compare arms.
- E024 shows every arm spent exactly `2,500` proposals, which is a budget match, not a cost per
  outcome.

## Method

**No committed result changes.** The module replays E024's `run_seed` with the same seeds, so each
arm keeps the proposal and verifier streams E024 derived for it
(`seed + offset * STRATEGY_SEED_STRIDE` and its mask twin). No arm is added and no randomness is
drawn from a simulator stream, which is the rule that a new arm must reuse the offset of the arm it
extends. The one instrument is a recording wrapper around `verify_candidate`: it forwards every
argument, returns the original answer, and is removed in a `finally`. Each arm makes exactly
`agents * generations` verifier calls in proposal order, which attributes every verdict to an arm
and a generation without reading any arm's private state.

The replay is checked, not assumed. The module rebuilds E024's `aggregate` block from the replayed
payloads using E024's own statistics and compares it with the committed artifact:

```text
committed  64419a7dcc7f913688efefae1e994302fb043e596a7ed8c32cd0097f4190f78a
replayed   64419a7dcc7f913688efefae1e994302fb043e596a7ed8c32cd0097f4190f78a   matches: true
```

**Recovery threshold.** `tau = 0.90 * optimum`, where `optimum` is the best utility any viable
candidate can reach under the changed goal. A deterministic grid (step `0.005`) over reliability and
security with the remaining budget filled greedily by goal weight gives `0.9`, so `tau = 0.81`.
It is absolute because it lives on the utility scale and is derived from the landscape, not from
any arm, so standing still cannot pass it. The `0.90` was fixed before any aggregate was computed
(seed 0's traces were viewed once while checking the replay) and a five-point grid
`{0.80, 0.85, 0.90, 0.95, 0.98}` is reported beside it.

Two readings of "recovered": **first passage** (first post-change generation with delivered utility
`>= tau`) and **sustained** (first generation from which delivered utility stays `>= tau` to the
end). **Censoring:** a seed that never gets there within the 25-generation horizon is right-censored.
It counts as *not reached* and contributes the horizon, a lower bound, to restricted means. It is
never scored `0` and never dropped.

**Viable-niche coverage.** `sim.niche` cells (adaptability x efficiency, `8 x 8 = 64`). A cell is
covered if it holds a panel-accepted, truly viable candidate proposed **after** the change; the
**good** variant also requires changed-goal utility `>= tau`. One function is applied to every arm's
accepted trace.

**Improvements.** An accepted candidate whose changed-goal utility beats the running best by more
than a materiality. The running best starts either at the best changed-goal utility among
everything the arm verified before the change (**carry**, primary) or at zero (**fresh**, which
credits an arm for re-finding what it already held). Materiality `0` is strict; `0.01` asks for a
material gain. One proposal is one verification attempt here, so cost is proposals per improvement,
pooled across seeds because a single seed can have zero improvements.

**Statistics.** Exact Clopper-Pearson intervals for rates; seeded percentile bootstrap (2,000
resamples, own `random.Random` keyed by label) for means and pooled ratios; paired comparisons
against the archive over the same 100 seeds by exact McNemar on "reached" and exact sign tests
elsewhere. 40 paired tests are reported, so the Bonferroni level is `0.00125`; p-values below are
uncorrected.

## Reproduction

```bash
PYTHONPATH=. python sim/e049_derived_measurements.py \
  --check-e024 experiments/results/E024-matched-budget-emergence-100-seed-summary.json \
  --pretty --output experiments/results/E049-derived-measurements.json
```

100 seeds, 50 agents, 50 generations, change at 25, 8 bins, the E024 perfect panel. About one
CPU-minute. `results/` is gitignored, so the artifact is committed with `git add -f`, as its
neighbours are.

## Result 1 — recovery time (`tau = 0.81`, 25-generation horizon, 100 seeds)

| arm | first passage: reached (95% CI) | median | restricted mean gens (95% CI) | sustained: reached (95% CI) | restricted mean gens (95% CI) |
| --- | ---: | ---: | ---: | ---: | ---: |
| random | 86/100 (0.776-0.921) | 7 | 9.40 (7.84-11.04) | **12/100** (0.064-0.200) | 24.88 (24.81-24.94) |
| scalar | 0/100 (0.000-0.036) | >=25 | 25.00 | 0/100 | 25.00 |
| planner | 0/100 (0.000-0.036) | >=25 | 25.00 | 0/100 | 25.00 |
| majority | 51/100 (0.408-0.611) | 0.5 | 12.26 (9.76-14.76) | 51/100 (0.408-0.611) | 12.26 (10.00-14.76) |
| qd | 100/100 (0.964-1.000) | 0 | 0.00 | 100/100 (0.964-1.000) | 0.00 |

Restricted means for censored arms are lower bounds. The majority-vote swarm is bimodal: 50 seeds
meet the bar in the change generation, 1 more at generation 1, and 49 never do.

Paired against the archive (`archive-only / other-only` seeds that reached the bar; exact McNemar):

| baseline | first passage | sustained |
| --- | ---: | ---: |
| planner | 100 / 0, p = 1.6e-30 | 100 / 0, p = 1.6e-30 |
| scalar | 100 / 0, p = 1.6e-30 | 100 / 0, p = 1.6e-30 |
| majority | 49 / 0, p = 3.6e-15 | 49 / 0, p = 3.6e-15 |
| random | 14 / 0, p = 0.00012 | 88 / 0, p = 6.5e-27 |

**Reading.** Random search looks close to the archive on first passage (86 against 100) and not
close at all once the bar must be *held* (12 against 100): it gets there on a lucky draw and falls
back, because it has no memory. First passage alone would have flattered it.

## Result 2 — viable-niche coverage after the change (mean over seeds, 95% bootstrap CI)

| arm | viable niches of 64 | good niches (`>= tau`) | viable, pooled over all seeds | good, pooled over all seeds |
| --- | ---: | ---: | ---: | ---: |
| random | 61.52 (61.24-61.79) | 1.63 (1.42-1.83) | 64 | 13 |
| scalar | 9.66 (9.45-9.87) | 0.00 | 16 | 0 |
| planner | 9.59 (9.43-9.76) | 0.00 | 17 | 0 |
| majority | 12.55 (11.69-13.61) | 5.54 (4.48-6.60) | 59 | 17 |
| qd | 64.00 (64.00-64.00) | 15.87 (15.60-16.15) | 64 | 21 |

Paired against the archive (`archive higher / other higher / ties`; sign test): good niches
`99/0/1` against majority, `100/0/0` against planner, scalar and random; viable niches `100/0/0`
against planner, scalar and majority and `93/0/7` against random, a mean gap of only **2.48 niches**
(2.21-2.77).

**Reading.** Raw viable-niche coverage barely separates the archive from random search: the archive
sits at its `8 x 8` capacity by construction and random search, which scatters proposals, reaches
61.5 of 64. The separation is in *good* niches, `15.87` against `1.63`. That ranking depends on the
bar, though: at `0.98` the archive's mean good-niche count is `1.91` and the swarm's is `1.46`
(descriptive, not tested). The pooled union of good niches is only 21 of 64 for the archive, which
is the observed ceiling of this landscape, not a target.

## Result 3 — cost per verified improvement (proposals after the change: 1,250 per seed)

Primary reading (carry, materiality 0):

| arm | improvements per seed (95% CI) | seeds with none | proposals per improvement (95% CI) | proposals per material improvement (>= 0.01) |
| --- | ---: | ---: | ---: | ---: |
| random | 0.75 (0.57-0.94) | 50/100 | 1667 (1330-2119) | 2907 (2232-4167) |
| scalar | 0.00 | 100/100 | undefined | undefined |
| planner | 0.00 | 100/100 | undefined | undefined |
| majority | 0.48 (0.30-0.71) | 70/100 | 2604 (1786-4167) | 15625 (6944-125000) |
| qd | 2.36 (2.05-2.69) | 9/100 | 530 (470-610) | 1623 (1374-1984) |

Under this reading the fixed-objective arms never beat the best artifact they held before the change,
and the archive has the lowest cost. **The ranking is not robust to the definition.** Starting the
running best at zero instead (fresh):

| definition | random | scalar | planner | majority | qd |
| --- | ---: | ---: | ---: | ---: | ---: |
| carry, materiality 0 | 0.75 | 0.00 | 0.00 | 0.48 | 2.36 |
| carry, materiality 0.01 | 0.43 | 0.00 | 0.00 | 0.08 | 0.77 |
| fresh, materiality 0 | 6.75 | 7.57 | 7.80 | 7.83 | 8.28 |
| fresh, materiality 0.01 | 5.75 | 5.03 | 5.00 | 3.72 | 5.53 |

(mean improvements per seed). Paired against the archive in the **fresh** reading, the archive's
count is higher than random's at materiality 0 (`60/32/8`, p = 0.0046, not significant at the
Bonferroni level) and **lower** at materiality 0.01 (`40/47/13`, p = 0.52, paired mean difference
`-0.22`, interval -0.69 to 0.26). Against planner, scalar and majority at materiality 0 the fresh
differences are not distinguishable from zero (p = 0.45, 0.19, 0.53).

## What undercuts the archive's advantage

- **Cost per improvement.** The archive's lead exists under carry-over accounting and disappears under
  fresh accounting: against random search it is a coin flip at materiality 0.01 (`40/47/13`), and
  proposals per material improvement are `226` for the archive against `217` for random there. This
  record does not choose between the two accountings, and it should not be quoted as showing the
  archive is cheaper per improvement.
- **Archive improvements are rare.** Under the primary reading the archive makes 2.36 improvements
  per seed and none in 9 seeds (39 seeds at materiality 0.01). It starts the change near the bar, so
  there is little left to improve; cost per improvement and recovery are not independent readings.
- **Raw viable coverage** separates the archive from random search by 2.5 niches of 64.
- **At `tau = 0.98` the archive no longer reaches the bar everywhere** (78/100 first passage,
  74/100 sustained), though it still beats every baseline.
- **Recovery time is zero for the archive because the later goal is one of the four it was handed.**
  That is E024's supplied-goal membership caveat, measured by
  [E030](E030-supplied-goal-membership.md) with a non-member goal. E049 does **not** repeat E030's
  non-member condition, so this record's recovery result is E024's advantage read on a new axis, not
  independent confirmation of it.

## What is not measured

- **Human attention.** Nothing models a person reading, deciding or waiting; proposal counts are not
  a proxy for it.
- **Novelty and information gain.** No novelty score or information measure is defined on candidates
  in this landscape, and none is invented here.
- **Churn.** Agents never join or leave in the E024 arms.
- **Energy and wall time.** A proposal is a unit, not a joule or a second.
- **Post-integration defects and adversarial contributors.** Outside the E024 perfect-panel arms
  ([E027](E027-defect-propagation.md) and [E036](E036-adversarial-contributors.md) model them).

## Caveats and what this does not show

- Coverage counts what each arm's search **produced** after the change, not what it **retains**. The
  arms retain different things (an archive, a population, one plan), so a retained count would be a
  different quantity per arm. Random search throws its coverage away each generation.
- The threshold fraction, the carry-over rule and the materiality are choices; the grids above exist
  so no verdict rests on one of them, and they belong to the same multiple-comparison family as the
  40 paired tests.
- Perfect verifier panel only: no false accept can inflate an arm's coverage or improvements. Imperfect
  panels are replayable through the same function but are not reported here.
- 100 seeds of one landscape, one change size and one direction (E033-E035 show the archive's lead
  depends on both).
- This is a post-hoc reading of an existing experiment. The five-arm comparison, the seeds and the
  budget are E024's; E049 chose the measurements after seeing E024's headline.

Issue 22 stays open. This record adds three of its listed measurements for the five arms and lists
what remains unmeasured.

## Decision

Report recovery time as an absolute-threshold, right-censored quantity, with both first passage and
sustained readings. First passage alone credits a memoryless arm for a lucky draw. Report diversity
as coverage computed by one function over every arm, and report good-niche coverage next to raw
viable coverage, because the raw count saturates. Do **not** report a cost-per-improvement ranking
without naming its accounting: this record shows it flips. Keep novelty, information gain, human
attention and churn on the open list instead of approximating them.

## Tests and provenance

- `tests/test_e049_derived_measurements.py` (fast, tiny configuration): replay payload identical to
  an unwrapped `run_seed` including under an imperfect panel; recorder removed after a run and after
  an error; censoring on a hand-built trace; one coverage function for all arms; carry and fresh
  improvements; exact test directions on hand-built seeds; determinism.
- `tests/test_e049_committed_artifact.py` (`sim`, nightly): the committed artifact's replay check, its
  configuration against E024's, and the first seeds re-derived exactly.
- Every number above is read from the committed artifact.
