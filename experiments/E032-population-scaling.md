# E032 — At a fixed budget, when is another agent worth adding?

[Issue 13](https://github.com/MSKazemi/idkmesh/issues/13) states its success
criterion as a question:

> **For a fixed budget and task class, when is another agent worth adding, and why?**

and its first falsifiable hypothesis as:

> Increasing `N` with low diversity produces diminishing or negative returns
> after a measurable threshold.

E032 answers the first for this simulator, and returns a **split verdict** on the
second: diminishing returns are measured and quantified for three of the five
arms, and the *negative* returns the hypothesis predicts are found — but not in
the arm the hypothesis points at, and not along the axis the obvious sweep uses.

## The confound that makes the obvious sweep wrong

[E024](E024-matched-budget-emergence.md)'s budget contract is

```
evaluation_budget = agents * generations
```

so sweeping `agents` at a fixed `generations` also multiplies the budget. From
`N=16` to `N=256` that is **16x more evaluations**, and "more agents helped"
becomes indistinguishable from "more compute helped" — which is precisely the
confound the issue's own success criterion excludes with the words *fixed
budget*. So the sweep is run both ways:

| mode | what is held | what it measures |
|---|---|---|
| `--mode unmatched` | `generations` | returns to **budget and population jointly** |
| `--mode matched` | `agents * generations` | returns to **population size alone** |
| `--mode capacity` | everything but `bins` | whether the archive result is about the grid |

Every cell of every mode holds the post-change horizon at exactly **25
generations**, so `post_change_utility_auc` is on one scale throughout and the
catastrophe threshold stays the published absolute `0.64 x 25 = 16.0` that E024,
[E027](E027-defect-propagation.md), [E028](E028-latent-defect-dimension.md),
[E030](E030-supplied-goal-membership.md) and
[E031](E031-learned-goal-filter.md) all use. In the matched mode the fixed
budget therefore trades population size against *pre-change* generations:
`N=16` gets 775 generations to converge before the goal moves, `N=256` gets 25.

## Statistical design, fixed before the sweep ran

**Paired comparisons.** A seed indexes a partially shared environment across
cells — the measured per-seed correlation between the `N=64` and `N=128` AUC is
`+0.441` for `majority` and `+0.192` for `random` — so consecutive cells are
compared as paired differences. On `majority`, the widest-spread arm, pairing
shrinks the standard error `1.34x`.

**A catastrophic-seed test as well as a mean test.** `majority` is bimodal: a
seed either locks onto the dead objective or does not. Its per-seed standard
deviation is roughly **40x** `qd`'s, which makes the mean a low-power statistic.
The catastrophic-seed count is the statistic E024 leads with for exactly that
reason, and **McNemar's exact paired test** is applied to it.

**`indistinguishable` is not `zero`.** A step is called a `gain` or a `loss`
only when its 95% paired interval excludes zero. `classify_returns` reports
`unresolved` when no step resolves, rather than collapsing that into
`saturated`. A design that cannot resolve a step has not measured that the step
is absent.

> **This experiment exists partly to correct an earlier claim of my own.** A
> 20-cell preliminary grid at 40 seeds appeared to show `majority` declining
> with `N` (`-0.440`, `-0.415`). At 40 seeds that arm's two-sigma band is
> `+/-1.6`, so the decline was inside noise. The claim is withdrawn, and at 100
> seeds it does not reappear.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e032_population_scaling.py --mode matched --seeds 100 \
  --output experiments/results/E032-matched-budget.json

PYTHONPATH=. python3 sim/e032_population_scaling.py --mode unmatched --seeds 100 \
  --output experiments/results/E032-unmatched-budget.json

PYTHONPATH=. python3 sim/e032_population_scaling.py --mode capacity --seeds 100 \
  --output experiments/results/E032-archive-capacity.json
```

100 seeds, perfect verifier panel, defect channel disarmed, `bins=8` except in
the capacity mode. The driver walks `mbe.run_seed` directly rather than calling
`mbe.sweep`, because `sweep` withholds `catastrophic_seeds` on a perfect panel
to keep its frozen artifact schema and never exposes per-seed values at all —
both of which this analysis needs. A test asserts the driver reproduces
`mbe.sweep` arm-for-arm on the same seeds, so keeping the per-seed values cannot
change what a seed does.

Recomputed sweeps should be compared **by value, not byte-for-byte** — the
simulators go through `exp` and `**`, whose last-place rounding differs across
CPUs and C libraries.

## Result 1 — returns to budget: three arms gain, two never do

`--mode unmatched`, 100 seeds, `generations=50`, budget growing `800 -> 12800`.

| N | budget | random | scalar | qd | planner | majority |
|---|---|---|---|---|---|---|
| 16 | 800 | 16.91 (1) | 15.65 (71) | 21.34 (0) | 14.25 (97) | 18.60 (37) |
| 32 | 1600 | 17.94 (0) | 16.03 (41) | 21.78 (0) | 14.18 (100) | 18.36 (44) |
| 64 | 3200 | 18.72 (0) | 16.34 (16) | 22.18 (0) | 14.07 (100) | 18.89 (38) |
| 128 | 6400 | 19.36 (0) | 16.55 (5) | 22.31 (0) | 14.10 (100) | 18.48 (45) |
| 256 | 12800 | 19.92 (0) | 16.56 (0) | 22.37 (0) | 14.05 (100) | 18.60 (45) |

_mean post-change utility AUC, with catastrophic seeds of 100 in parentheses._

Marginal value of each doubling, as a paired difference:

| arm | 16->32 | 32->64 | 64->128 | 128->256 | shape |
|---|---|---|---|---|---|
| random | `+1.024` | `+0.787` | `+0.633` | `+0.566` | **sublinear** (all resolved) |
| qd | `+0.439` | `+0.407` | `+0.123` | `+0.064` | **sublinear** (all resolved) |
| scalar | `+0.382` | `+0.313` | `+0.212` | `+0.007` | **saturated** at `N=128` |
| planner | `-0.064` | `-0.113` | `+0.028` | `-0.044` | **unresolved** — no step resolves |
| majority | `-0.240` | `+0.525` | `-0.407` | `+0.120` | **unresolved** — no step resolves |

**Diminishing returns are confirmed and quantified for `random`, `qd` and
`scalar`.** `qd`'s marginal value falls `6.9x` across the range and `scalar`
stops resolving entirely past `N=128`. Neither `planner` nor `majority` shows a
resolvable return to budget anywhere.

The catastrophe channel tells a sharper story than the means for `scalar`:
`71 -> 41 -> 16 -> 5 -> 0` catastrophic seeds, with McNemar `p = 0.0000`,
`0.0002` and `0.0127` on the first three steps. A scalar hill-climber that fails
71% of the time at `N=16` **never fails at all** at `N=256`. Nothing comparable
happens to `planner`, pinned at `100/100` at every population, or to `majority`,
whose count wanders `37, 44, 38, 45, 45` with every McNemar `p > 0.16`.

## Result 2 — at a fixed budget, the archive's gain disappears entirely

`--mode matched`, 100 seeds, `agents * generations = 12800` in every cell. More
agents buys fewer pre-change generations and nothing else.

| N | budget | pre-change G | random | scalar | qd | planner | majority |
|---|---|---|---|---|---|---|---|
| 16 | 12800 | 775 | 16.94 (2) | 15.42 (100) | 22.38 (0) | 14.06 (100) | 18.41 (39) |
| 32 | 12800 | 375 | 17.95 (0) | 15.71 (98) | 22.38 (0) | 14.07 (100) | 18.23 (44) |
| 64 | 12800 | 175 | 18.73 (0) | 15.98 (58) | 22.38 (0) | 14.05 (100) | 18.84 (38) |
| 128 | 12800 | 75 | 19.37 (0) | 16.29 (4) | 22.35 (0) | 14.06 (100) | 18.42 (45) |
| 256 | 12800 | 25 | 19.92 (0) | 16.56 (0) | 22.37 (0) | 14.05 (100) | 18.60 (45) |

| arm | 16->32 | 32->64 | 64->128 | 128->256 | shape |
|---|---|---|---|---|---|
| random | `+1.011` | `+0.774` | `+0.642` | `+0.553` | **sublinear** (all resolved) |
| scalar | `+0.285` | `+0.271` | `+0.309` | `+0.271` | **near-linear** (all resolved) |
| qd | `+0.000` | `+0.000` | `-0.029` | `+0.016` | **unresolved** — nothing moves |
| planner | `+0.000` | `-0.019` | `+0.010` | `-0.003` | **unresolved** — nothing moves |
| majority | `-0.177` | `+0.610` | `-0.420` | `+0.181` | **unresolved** |

**The archive's returns to population were entirely a return to budget.** In the
unmatched sweep `qd` gained on all four doublings; here it moves by `0.029` AUC
in total across a **16x** change in population, with 95% intervals of about
`+/-0.025` on every step. Its catastrophic count is `0/100` in all five cells.
Quality-Diversity, at a fixed budget, does not care how many agents you have.

`random` and `scalar` behave in the opposite way: their gains survive matching
almost unchanged (`random` `+1.024 -> +0.566` unmatched against
`+1.011 -> +0.553` matched). Those are genuine returns to population size.

And `scalar` is the arm that gains **most**, near-linearly — its four steps
differ by less than the intervals they sit inside, which is the condition the
classifier requires before it will call a trend at all — with no threshold
anywhere in a 16x range — while its catastrophic count falls `100 -> 98 -> 58 ->
4 -> 0`, with McNemar `p = 0.0000` on the two middle steps. At a fixed budget,
moving spend from generations into agents takes the scalar hill-climber from
failing **every** seed to failing **none**.

> **Internal control.** The two sweeps share exactly one cell — `N=256`,
> `G=50`, budget `12800` — and its per-seed values are identical in both
> artifacts, which is asserted as a test rather than eyeballed.

### The negative return exists — on the other axis

Hypothesis 1 predicts that spending more produces *negative* returns once
diversity is low. That is exactly what happens, but the variable that produces
it is **generations, not agents**. Holding `N=16` and spending **16x more
compute entirely on pre-change generations** (`800 -> 12800` evaluations,
`25 -> 775` generations before the goal moves):

| arm | delta | 95% paired CI | verdict | catastrophic | McNemar p |
|---|---|---|---|---|---|
| qd | `+1.044` | `[+0.936, +1.152]` | **gain** | `0 -> 0` | `1.0000` |
| random | `+0.030` | `[-0.080, +0.141]` | indistinguishable | `1 -> 2` | `1.0000` |
| planner | `-0.183` | `[-0.359, -0.006]` | **loss** | `97 -> 100` | `0.2500` |
| majority | `-0.195` | `[-0.316, -0.075]` | **loss** | `37 -> 39` | `0.5000` |
| scalar | `-0.223` | `[-0.343, -0.103]` | **loss** | `71 -> 100` | `0.0000` |

**Three of the five arms are made resolvably worse by sixteen times the
compute.** `scalar` goes from failing 71 seeds to failing all 100. Only the arm
that keeps an archive converts the extra generations into value.

## Result 3 — archive capacity has an optimum, and it is the published one

`--mode capacity` sweeps only `bins` at `N=64`, `G=50`. The archive holds
`bins ** 2` niches, a number that does not depend on `N` at all, so if the
Quality-Diversity result moved with capacity it would be a result about the
grid rather than about diversity.

| bins | capacity | archive filled | fill | qd mean | qd catastrophic |
|---|---|---|---|---|---|
| 4 | 16 | 16.0 | 1.00 | 21.878 | 0 |
| 8 | 64 | 64.0 | 1.00 | 22.183 | 0 |
| 16 | 256 | 255.7 | 1.00 | 22.039 | 0 |
| 32 | 1024 | 886.4 | 0.87 | 21.716 | 0 |

| step | delta | 95% paired CI | verdict |
|---|---|---|---|
| 4 -> 8 | `+0.306` | `[+0.208, +0.403]` | **gain** |
| 8 -> 16 | `-0.144` | `[-0.211, -0.078]` | **loss** |
| 16 -> 32 | `-0.323` | `[-0.405, -0.242]` | **loss** |

**More archive capacity actively hurts past `bins=8`.** This is the only place
in E032 where a resolved *negative* return appears, and it is on the archive
axis rather than the population axis. Fill is `0.87` at `bins=32`, so it is not
saturation: the same budget spread across 1024 niches leaves each one less
selected than the same budget across 64.

Two things this rules out. The published `bins=8` was not tuned to flatter the
archive — it is the measured optimum, and the two neighbouring values were
available to anyone who looked. And the archive's robustness does not come from
the grid at all: `qd` holds **0/100 catastrophic at every capacity**, including
the two where its mean is resolvably worse.

An internal control makes this readable: every non-archive arm is
**bit-identical** across the whole capacity sweep (`random` 18.724, `scalar`
16.342, `planner` 14.070, `majority` 18.886, with identical catastrophic counts
at every `bins`). `bins` is drawn from the same per-seed streams every arm uses,
so a change that leaked into shared randomness would have moved them. It is
pinned as a test.

## Result 4 — the consensus swarm is the one arm more agents does not stabilise

Per-seed standard deviation of post-change utility AUC, unmatched sweep:

| arm | N=16 | N=32 | N=64 | N=128 | N=256 | ratio |
|---|---|---|---|---|---|---|
| random | 0.384 | 0.295 | 0.232 | 0.172 | 0.150 | **2.6x smaller** |
| scalar | 0.621 | 0.478 | 0.379 | 0.286 | 0.154 | **4.0x smaller** |
| qd | 0.526 | 0.364 | 0.187 | 0.120 | 0.107 | **4.9x smaller** |
| planner | 0.881 | 0.653 | 0.383 | 0.261 | 0.191 | **4.6x smaller** |
| majority | 3.538 | 3.903 | 3.939 | 4.069 | 4.120 | **1.2x *larger*** |

Every arm but one converts population size into predictability, by a factor of
2.6 to 4.9 over a 16x range. The consensus swarm converts none of it: its spread
is 22x to 38x the others' at `N=256` and does not shrink.

This is the most directly useful answer E032 has for the issue's *"and why"*.
The consensus swarm's outcome is not a noisy average that more samples tighten —
it is a near-binary event, whether the swarm locks onto the dead objective,
which [E031](E031-learned-goal-filter.md) traced to the mechanism. Adding agents
does not make that event rarer and does not make it more predictable. For that
arm, **which seed you got matters more than how many agents you have**, at every
population size measured.

## Interpretation

**The answer to issue 13's success criterion, for this simulator.**

> For a fixed budget and task class, when is another agent worth adding, and why?

| arm | is another agent worth adding? | why |
|---|---|---|
| `scalar` | **Yes, all the way to `N=256`** — near-linear, and it is the difference between failing every seed and failing none | it retains nothing between generations, so population breadth is its *only* source of exploration |
| `random` | **Yes, but sublinearly** — `+1.011` falling to `+0.553` | same reason, but it never concentrated in the first place, so it has less to gain |
| `qd` | **No.** Zero measurable benefit across a 16x range | the archive already retains diversity *across time* in `bins ** 2` niches, so parallel agents are redundant — its capacity is its effective population |
| `planner` | **No**, and it fails `100/100` at every population | a centralized planner is a single-artifact baseline by construction; `N` buys it nothing to be diverse with |
| `majority` | **Cannot say at 100 seeds** | its outcome is near-binary, not a noisy mean, and its spread does not shrink with `N` at all |

**Hypothesis 1 is falsified in the direction it was stated.** It predicts that
increasing `N` *with low diversity* produces diminishing or negative returns
past a threshold. No arm shows a negative return to `N` at a fixed budget, and
the ordering runs the other way: the arm with the **least** retained diversity
(`scalar`) gains the most and shows no threshold at all, while the arm with the
**most** (`qd`) gains exactly nothing.

**But the failure mode the hypothesis is reaching for is real** — it is just
indexed by the wrong variable. Convergence to a dead objective is produced by
spending budget on *generations*, not by spending it on agents. Sixteen times
the compute, all of it time, makes three of five arms resolvably worse and takes
`scalar` from 71 to 100 catastrophic seeds. The right form of the hypothesis for
this landscape is: **a fixed budget spent on time rather than population
produces negative returns once the population is small enough to converge.**

**Two mechanisms, one substitution.** Diversity can be held across the
population (many agents at once) or across time (an archive that remembers). The
three results compose into a single statement: `qd` is insensitive to `N`
(Result 2) and sensitive to `bins` with an optimum at 8 (Result 3), because its
archive is a memory that substitutes for population. `scalar` has no such memory,
so it is sensitive to `N` and to nothing else. This is a concrete, measured
answer to the "why" half of the issue's question, and it predicts something
testable: an arm's returns to population size should be inversely related to how
much diversity it retains between generations.

**What this says about reporting.** The unmatched and matched sweeps disagree
about `qd` — sublinear gains on all four steps in one, nothing at all in the
other — from the same simulator, the same seeds, and the same 100 runs per cell.
The only difference is whether the budget was allowed to move. Any claim of the
form "more agents improved performance" that does not state which of the two it
measured is not interpretable, and this experiment exists partly because I made
that mistake first.

## Limitations

- Everything here is synthetic. No real model, task, reviewer, or machine is
  involved, and "agents" is a **population size in an evolutionary search, not a
  count of language-model workers**. Nothing in E032 estimates a scaling law for
  real coding agents; issues 70 and 96 are where that evidence would come from,
  and both are still waiting on a real held-out corpus.
- One evaluation unit is a simulator proposal plus a panel decision. It is not
  measured compute, energy, wall-clock, or human attention — four of the primary
  metrics issue 13 asks for, none of which this experiment supplies.
- The verifier panel is **perfect** in every cell, so E032 measures returns to
  population with verification held out of the way. E026 and E027 measure what an
  imperfect, correlated panel does, but only at one population size; the
  interaction between panel quality and `N` is unmeasured.
- Quality-Diversity is handed the four predefined plausible goals, so its
  diversity is supplied rather than discovered. E030 and E031 show that this
  matters enormously: against a goal outside the supplied set, the same spread
  that rescues the swarm makes it worse. E032 runs entirely inside the supplied
  set, so `qd`'s numbers here inherit that caveat in full.
- **The matched mode trades population against time, not population in
  isolation.** Holding `agents * generations` constant means more agents also
  buys fewer pre-change generations. That trade is the question the issue asks,
  but nothing here separates the two factors, and the largest population is
  evaluated after the shortest convergence by construction.
- A step reported as `indistinguishable` is a limit of this design at 100 seeds,
  **not** evidence that the true effect is zero. This matters most for
  `majority`, whose per-seed spread is large enough that resolving an effect the
  size of its own point estimates would need between **190 and 3926 seeds**
  depending on the step — computed from this run's paired interval widths, not
  assumed. Its four point estimates also alternate in sign, so they are as
  consistent with no effect as with any particular one.
- Only five arms and one landscape are measured. Issue 13's hypotheses 2 and 3 —
  heterogeneous teams at equal budget, and coordination topology changing the
  scaling exponent — are untouched here.

## Decision

**This closes no issue.** It supplies one falsifiable hypothesis' worth of
evidence for issue 13 and leaves the rest of that issue, including its entire
minimum-experiment table and every real-task metric, outstanding. The
`tools/issue_evidence_gate.py` registry deliberately does not list issue 13 as
blocked, because it is advanceable by work like this rather than waiting on an
external dependency.

What should be carried forward:

- `bins=8` is the measured archive optimum, not a convention. Do not raise it to
  "give the archive more room"; that is a resolved loss.
- Do not quote an unmatched population sweep as evidence about population size.
  Report the matched arm, or say plainly that the budget moved too.
- For any arm whose outcome is near-binary, report catastrophic seeds with a
  paired test and not only the mean. The mean of a bimodal arm at feasible seed
  counts is a low-power statistic, and reading a trend off it is how the
  preliminary version of this experiment produced a claim that did not survive.
