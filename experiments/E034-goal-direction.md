# E034 — At a fixed distance, which direction breaks the archive?

**Direction matters as much as distance: on a single shell, where every future
goal is the same distance from the supplied set and the same size of change,
the archive's lead runs from `-4.894` to `+4.471` and is negative for 24.2% of
directions. The mechanism E033 proposed for that spread — the viability floor —
is falsified by its own preregistered test.**

E033 swept how far the future goal drifts and found the Quality-Diversity
archive's lead decays smoothly to nothing by `0.35`. It closed with a named next
step:

> Next: **E034** — hold the distance and sweep the direction, testing whether the
> archive's failures concentrate on goals that devalue a trait the viability
> floor forces every artifact to buy.

That hypothesis came from four goals. Two of E033's 42 matched goals put the
archive *behind* the hypothesis-free arms, and both weighted `security` at
almost nothing; across the four goals weighting `security` under `0.05` the mean
lead was `-1.362`, against `+2.741` for the other 38. But all four sat at `0.254`
or further from the box, so the observation was confounded with the distance
E033 was sweeping. E033 recorded it as a hypothesis, not a finding.

E034 holds the distance still and sweeps the direction.

## Design

Every goal measured here sits on one shell: `0.30 ± 0.015` from the nearest
member of `emergence_sim.PLAUSIBLE_GOALS`, **and** `0.391918 ± 0.015` from
`INITIAL_GOAL`. Both the distance to the box and the size of the change are
constant, so the only thing that varies is where on the shell the goal sits.
`0.30` is the E033 ring where per-goal outcomes were most dispersed — if
direction explains anything, it has the most to explain there.

Holding both distances is what makes the comparison mean anything. `PLAUSIBLE_GOALS`
contains `INITIAL_GOAL`, so moving a goal away from the box necessarily enlarges
the change; E033 needed a matched ladder for exactly this reason, and E034
inherits its `0.391918`.

Rejection-sampling `2,000,000` Dirichlet-style draws yields a shell of `38,643`
members. The arena's five traits fall into three structural classes, read off
the arena rather than asserted:

| class | traits | why |
|---|---|---|
| floored | `reliability`, `security` | `sim.viable` refuses any candidate under `0.25` on either, so every artifact has already spent budget on both |
| descriptor | `adaptability`, `efficiency` | `sim.niche` bins the archive on exactly these two |
| unconstrained | `simplicity` | none of the above — the control |

For each of the five traits, five cells at target weights `0.02, 0.10, 0.20,
0.30, 0.40`, `16` goals a cell chosen by farthest-point selection on the shell,
`100` seeds a goal: `400` goal-slots, `385` distinct goals. A goal is assigned
to a cell by the weight it places on that trait, so `15` goals legitimately
appear in two traits' ladders; the ladders are very nearly, but not exactly,
disjoint samples.

The statistic is E030's lead — `mean(arm) − mean(best arm holding no
hypothesis)` — which differences out "this goal is simply harder".

### The prediction, stated before the run

Quoted from the module docstring, written before any goal was measured:

> If E033's hypothesis is right and the mechanism is the viability floor, the
> archive's lead should **rise with the weight on the two floored traits** and be
> flat in `simplicity`. If instead the lead responds to any extreme direction,
> `simplicity` will move too, and the floor story is dead.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e034_goal_direction.py --jobs 8 --goals-per-cell 16 \
  --output experiments/results/E034-goal-direction.json
```

`--jobs` changes speed and not the answer: each goal is an independent seeded
measurement collected in input order. The workers must be processes, because
pointing the environment at a new future goal rewrites module globals in both
copies of the arena.

Measured shell occupancy, across all 400 slots: distance to the set spans
`0.285001`–`0.314991`, distance from `INITIAL_GOAL` spans `0.376919`–`0.406879`.
Both stay inside the tolerance, so no cell is quietly nearer the box than another.

## Result 1 — direction is worth as much as distance

All 385 goals are the same distance from the box and represent the same size of
change. Their archive leads:

| | value |
|---|---|
| worst direction | `-4.894` |
| best direction | `+4.471` |
| spread | `9.365` |
| directions with a negative lead | `93 / 385` (24.2%) |

For scale, E033's entire distance sweep — from a goal inside the box to one
`0.35` away, the point where the lead is fully spent — moved the ring mean by
`3.309`. Direction, at one distance, spans nearly three times that. A single
number for "the archive's lead at distance `d`" is an average over a spread
wider than the effect it is reporting.

## Result 2 — four of the five ladders resolve, and they do not agree

Archive lead against the weight the future goal puts on each trait. `change` is
the `w=0.40` cell minus the `w=0.02` cell, Welch's *t* on the two cells' 16 goals:

| trait | class | `w=0.02` | `w=0.40` | change | *t* | *p* | shape |
|---|---|---|---|---|---|---|---|
| `reliability` | floored | `-0.113` | `+2.939` | `+3.052` | `+5.80` | `<0.001` | **rises** |
| `security` | floored | `+0.279` | `+1.691` | `+1.412` | `+1.94` | `0.065` | unresolved |
| `adaptability` | descriptor | `-0.105` | `+2.335` | `+2.441` | `+3.80` | `0.0008` | **rises** |
| `efficiency` | descriptor | `+3.042` | `+0.596` | `-2.445` | `-3.55` | `0.0023` | **falls** |
| `simplicity` | unconstrained | `+2.257` | `-0.371` | `-2.628` | `-3.64` | `0.0015` | **falls** |

Five preregistered tests, so Bonferroni sets the bar at `0.05/5 = 0.010`. All
four resolved ladders clear it. The `shape` column is the module's own
classifier, which requires the endpoint confidence intervals to be disjoint —
a stricter test than the *p*-value, and it agrees.

## Result 3 — the preregistered prediction is falsified

The prediction had two halves and lost both.

**`simplicity` is not flat.** It is the control trait: not floored, not a
descriptor, structurally unremarkable. Its ladder is monotone, its endpoints
separate, and it carries the archive from `+2.257` to `-0.371` — the lead does
not merely shrink, it inverts. Against `reliability` the contrast is `+5.681`
(se `0.893`, *p* `<0.001`). By the docstring's own stated terms, "`simplicity`
will move too, and the floor story is dead".

**The floored pair is not a unit.** `viable` treats `reliability` and `security`
identically — both floored at `0.25`, both in the `0.08·√(reliability·security)`
interaction. If the floor were the mechanism they should behave alike. Instead
`reliability` is the strongest effect in the experiment (`+3.052`, *t* `5.80`)
and `security` is the only ladder that does not resolve (`+1.412`, *t* `1.94`).
Honest caveat: the difference *between* them, `+1.641` (se `0.898`), is itself
unresolved at *p* `0.078`. The claim that survives is the weaker one — the floor
hypothesis predicted two matching effects and got one clear effect and one null,
which is not support.

**The descriptor category is a cancellation, not a group.** `adaptability` and
`efficiency` are the two axes `niche` bins the archive on. They move in
*opposite* directions, `+2.441` against `-2.445`, a contrast of `+4.886`
(se `0.942`, *p* `<0.001`). Averaged into their category the ladder reads
`+1.468 → +1.466`, a change of `-0.002`, classified `unresolved`:

| category | `w=0.02` | `w=0.40` | shape |
|---|---|---|---|
| floored | `+0.083` | `+2.315` | rises |
| descriptor | `+1.468` | `+1.466` | unresolved |
| unconstrained | `+2.257` | `-0.371` | falls |

Read alone, that table looks like partial support for the prediction. It is an
artifact of averaging two resolved, opposite-signed effects to zero. **The
structural classes E034 was designed around are not the right grouping**, and
the category view is reported here only to show that it is misleading.

## Result 4 — when the archive loses, the archive is what moves

E033's central result was that the archive's lead vanished without the archive
deteriorating: `qd` held at `~22` while the hypothesis-free arms climbed to meet
it. On this shell that is no longer the story. Change across each ladder:

| trait | `qd` mean | best hypothesis-free arm |
|---|---|---|
| `reliability` | `+5.130` | `+2.078` |
| `simplicity` | `-4.801` | `-2.172` |
| `efficiency` | `-3.418` | `-0.972` |
| `adaptability` | `-1.434` | `-3.875` |

Where the lead falls, `qd` falls roughly twice as far as the baseline — an
absolute loss of archive performance, not a baseline catching up. `adaptability`
is the one ladder that behaves the way E033 described, and it runs the other
way: everyone gets worse and the archive merely gets worse more slowly.

## Result 5 — catastrophic failure is confined to the extremes

Mean catastrophic seeds out of 100 for `qd`:

| trait | `0.02` | `0.10` | `0.20` | `0.30` | `0.40` |
|---|---|---|---|---|---|
| `reliability` | `6.25` | `5.69` | `0.00` | `0.00` | `0.00` |
| `security` | `6.00` | `4.44` | `0.00` | `0.00` | `0.00` |
| `adaptability` | `0.00` | `0.06` | `2.69` | `1.25` | `0.00` |
| `efficiency` | `0.00` | `0.00` | `3.62` | `6.69` | `1.56` |
| `simplicity` | `0.00` | `0.00` | `0.00` | `0.00` | `12.25` |

The archive's catastrophes sit at the ends of the ladders, not in the middle,
and the single worst cell in the experiment is the control trait at its highest
weight. Whatever drives catastrophic failure, an extreme weight on the
structurally unremarkable trait produces about twice the rate — `12.25` against
`6.25` and `6.00` — of an extreme *de-weighting* of either floored trait.

## Result 6 — E033's `security` observation does not survive the control

The direct test of the hypothesis E034 was built for. The `security` `w=0.02`
cell holds 16 goals averaging `0.0279` weight on `security`, all at a fixed
distance and change size:

| | E033, post-hoc, n=4 | E034, distance held, n=16 |
|---|---|---|
| `qd` lead | `-1.362` | `+0.279` |
| 95% interval | — | `[-1.095, +1.653]` |

E034's interval excludes E033's point estimate. Low weight on `security` does
not, on its own, put the archive behind — 7 of those 16 goals do have a negative
lead, but so do 24.2% of all directions. E033's observation was the distance
confound it warned it might be.

## What is left of the mechanism

The floor hypothesis is dead; nothing preregistered replaces it. Two post-hoc
observations are recorded as leads for a future experiment, not as findings:

- **Total weight on the floored pair correlates with the lead** (Pearson `+0.480`
  over 385 goals) — but it is not a sufficient statistic, because it *falls*
  along the `adaptability` ladder (`0.452 → 0.281`) while the lead *rises*. Any
  single-quantity account of direction has to explain that ladder, and this one
  does not.
- The worst directions share a shape — low `reliability`, low `security`, high
  `efficiency` and `simplicity`, e.g. `[0.086, 0.067, 0.444, 0.395, 0.008]` at
  `-4.894`. That is a goal whose optimum is a corner a hill-climber can walk
  straight to, which would make diversity pure overhead. E034 cannot test this:
  it is read off the losers after the fact.

## Interpretation

E033 measured the price of the archive's bet as a function of how far the world
moves. E034 says that function is a summary of a distribution wide enough to
contain both the best and the worst outcomes in the study. At `0.30` — inside
the range where E033's mean lead was comfortably positive — a quarter of
directions leave the archive behind arms that hold no hypothesis at all.

The engineering consequence is narrower than "diversity buys a margin". It buys
a margin *on average over directions you did not choose*, and the averaging is
doing more work than the distance. A design leaning on retained diversity to
survive goal drift cannot budget from the mean alone.

## Limitations

- **Direction is five weights, swept one at a time.** Weights sum to one, so
  raising one trait lowers the other four together. Each ladder is one trait
  against the rest, not a clean single-axis manipulation, and no cell isolates
  a two-trait direction.
- **The floored traits are confounded with the interaction term.** The
  `0.08·√(reliability·security)` bonus covers exactly the two floored traits, so
  a floored-trait effect could not have been attributed to the floor even if the
  prediction had held.
- **One shell.** Everything is `0.30` from the box at a change size of `0.392`.
  Whether the direction spread widens or narrows nearer the box is unmeasured;
  E033's per-ring spreads suggest it widens with distance.
- **One panel.** The perfect verification panel throughout, as in E033.
- **16 goals a cell.** A 4-goal pilot resolved nothing at all and was discarded
  unpublished; the scarce resource is goals, not seeds, since each per-goal lead
  is already a 100-seed mean. Cells remain wide enough that `security` is
  unresolved and the `reliability`–`security` contrast is unresolved.
- **The three structural classes are not a valid grouping** (Result 3), so the
  `categories` block in the artifact should not be quoted on its own.

## Decision

Report the archive's lead at a distance as a distribution, not a mean. The
supporting numbers are the `9.365` spread and the 24.2% negative share at
`0.30`, alongside E033's decay rate. Do not attribute directional failure to the
viability floor: that hypothesis was preregistered here and falsified.

Next: the mechanism is open. The test that would move it is a shell sweep — the
same direction ladder at two or three distances — to establish whether the
spread grows with distance and whether the trait ordering (`reliability` up,
`simplicity` down) is stable or is itself a property of this one shell.
