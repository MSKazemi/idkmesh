# E030 — Does the archive's advantage depend on being handed the future goal?

## Research question

[E024](E024-matched-budget-emergence.md) records its own sharpest limitation:

> the plausible goals are supplied by the experimenter rather than learned, and
> the majority-vote swarm's per-agent belief is drawn from that same supplied
> set, so its bimodality is a property of this landscape rather than a measured
> property of real swarms

and, one paragraph earlier:

> It is given an informative set of four plausible goals, **including the later
> goal**, while the scalar baseline is deliberately fixed to the initial goal.

That is not a caveat about presentation. `sim.PLAUSIBLE_GOALS` literally
contains `sim.CHANGED_GOAL`, the goal the environment switches to at generation
25. The quality-diversity arm averages its `robust_quality` over that set and
the majority-vote swarm draws each agent's belief from it, so both arms are
handed the future. `random`, `scalar` and `planner` are not. Every result from
E024 through [E028](E028-latent-defect-dimension.md) inherits that asymmetry.

E030 asks the obvious question: **how much of the archive's lead is retained
diversity, and how much is the answer being in the box?**

Answer, in one line: **almost none of it is the answer being in the box — for
the archive.** Removing the supplied answer costs the quality-diversity arm
at most 4.4% of its lead and nothing at all in catastrophic seeds. It costs the
majority-vote swarm its entire lead, in every panel. The confound E024 named as
a threat to the archive result turns out to be load-bearing for the *other*
hypothesis-holding arm.

## The manipulation is exactly one bit

The tempting design — delete `CHANGED_GOAL` from `PLAUSIBLE_GOALS` — is
confounded. It changes the set from four hypotheses to three, so the archive
would also be averaging over less, holding fewer niches' worth of belief, and
facing a differently-shaped robustness objective. Any effect would be
unattributable between "lost the answer" and "lost a quarter of the set".

E030 leaves the goal set **byte-identical** and moves where the environment
actually goes:

| | held | unheld |
|---|---|---|
| post-change goal | `(0.15, 0.35, 0.10, 0.10, 0.30)` | `(0.24, 0.43, 0.06, 0.13, 0.14)` |
| in `PLAUSIBLE_GOALS` | **yes** | **no** |
| `PLAUSIBLE_GOALS` itself | unchanged | unchanged |
| `INITIAL_GOAL` | unchanged | unchanged |
| every arm's code path | unchanged | unchanged |

The arms publish exactly the hypotheses they always published. The only thing
that differs between the two columns is whether one of them happens to be right.

`sim/matched_budget_emergence.py` loads `emergence_sim.py` a second time by file
path, under a different module name, so two live module objects own
`CHANGED_GOAL`. Patching one and not the other would score the arms against one
goal while switching the environment to another, and would produce a number
nobody could reproduce. `future_goal()` patches both, and
`tests/test_e030_supplied_goal_membership.py` pins that the second object is
genuinely distinct before asserting anything about the swap.

## What is held fixed — the parity control

A substitute goal that is merely *different* proves nothing: if it is closer, or
easier, or a smaller shock, the whole matrix moves for reasons that have nothing
to do with membership. The substitute is selected against measured criteria, and
those measurements travel inside the results artifact rather than living only
here.

Measured on one fixed pool of 79,388 viable candidates (the survivors of
200,000 samples, seed `20260830`), so both goals judge the same artifacts:

| property | held | unheld | gap (unheld vs held) |
|---|---|---|---|
| distance from `INITIAL_GOAL` | `0.374166` | `0.391918` | +4.7% |
| distance to nearest *other* supplied hypothesis | `0.200000` | `0.206398` | +3.2% |
| attainable ceiling | `0.883853` | `0.890478` | +0.7% |
| mean utility over viable candidates | `0.538014` | `0.522355` | −2.9% |
| **transfer regret from the initial optimum** | `0.382482` | `0.376827` | −1.5% |

The last row is the one that decides the outcome, and it is the one that failed
first. My initial candidate substitute `(0.14, 0.20, 0.12, 0.11, 0.43)` matched
Euclidean distance exactly but had transfer regret `0.254` against the held
goal's `0.354` — 28% cheaper for an arm committed to the old objective to move
to. That handed `scalar` `+2.91` and `planner` `+2.48` AUC and would have been
readable as the archive losing ground. It was discarded and the criterion added
before re-selecting.

**One parity is not achieved, and it is recorded rather than argued away.** Both
goals promote adaptability to first rank, but the substitute promotes
reliability where the published goal promotes security. Matching trait
*reordering* as well as distance, isolation, ceiling and regret leaves no
admissible goal on this simplex.

**One residual gap is not captured by the pool argmax.** The pool's best
candidate is not the artifact an arm actually converges to. Scoring the elite an
`INITIAL_GOAL`-committed evolutionary run arrives at (60 seeds, 24 generations,
64 agents) gives `0.566294` under the held goal and `0.527268` under the
substitute — a **`-0.039025`** residual, about 6.9%. Over a 25-generation
post-change horizon that is roughly `1.0` of AUC, which is the right order for
the drops seen in `scalar` and `planner` below. It is a cost paid only by arms
locked to the old objective. It is *not* paid by the arm the lead statistic is
measured against, which commits to nothing.

## The statistic, and why it is not the mean

Raw means are **not** comparable across the two conditions. The environment's
goal itself changed, so every arm moves, and part of that movement is only the
new goal being marginally easier or harder to reach. `random` gains `+0.34`
under the substitute for exactly that reason, having no hypothesis to lose.

What is comparable is **how far ahead of the hypothesis-free arms** a
hypothesis-holding arm gets:

- **hypothesis-free**: `random`, `scalar`, `planner` — never read `PLAUSIBLE_GOALS`
- **hypothesis-holding**: `qd`, `majority` — read it, and are therefore the arms
  the supplied answer could be helping

`lead = mean(arm) - max(mean(random), mean(scalar), mean(planner))`.

The reference arm is **named** in every cell, not just valued. A lead computed
against `scalar` in one condition and `random` in the other would be comparing
two different things. In this matrix the reference is `random` in all eight
cells, in both conditions — verified, and pinned by a test.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e030_supplied_goal_membership.py --mode parity \
  --draws 200000 --output experiments/results/E030-goal-parity.json

PYTHONPATH=. python3 sim/e030_supplied_goal_membership.py --mode matrix \
  --seeds 100 --output experiments/results/E030-supplied-goal-membership.json
```

100 seeds, 64 agents, 50 generations, change at 25, 8 niche bins, the four
[E027](E027-defect-propagation.md) verifier panels, defect channel disarmed.
Catastrophe threshold is E024's absolute cutoff, `0.64 x 25 = 16.0` AUC, so the
counts here are directly comparable to E024's, E027's and E028's.

Recomputed sweeps should be compared **by value, not byte-for-byte** — the
simulators go through `exp` and `**`, whose last-place rounding differs across
CPUs and C libraries.

## Result 1 — the archive keeps its lead

Lead over the best hypothesis-free arm, post-change utility AUC, 100 paired
seeds:

| panel | `qd` held | `qd` unheld | Δ | as % of lead |
|---|---|---|---|---|
| perfect | `+3.4598` | `+3.3083` | `-0.1516` | 4.4% |
| independent | `+3.4512` | `+3.3070` | `-0.1442` | 4.2% |
| measured | `+3.5619` | `+3.4438` | `-0.1181` | 3.3% |
| stress | `+3.7614` | `+3.7010` | `-0.0603` | 1.6% |

The archive's *raw* mean does not fall at all — it **rises**, by `+0.213` to
`+0.275` depending on panel — and on the same seed it does better without the
answer than with it in **93–97 of 100** cases. Its lead narrows only because
`random`, its reference, rises slightly more.

It stays at **`0/100` catastrophic seeds in every panel in both conditions**.

## Result 2 — the majority-vote swarm is where the answer was doing the work

Same statistic, same seeds, same runs:

| panel | `majority` held | `majority` unheld | Δ |
|---|---|---|---|
| perfect | `+0.1627` | `-0.6954` | `-0.8581` |
| independent | `+0.1627` | `-0.6953` | `-0.8580` |
| measured | `+0.3903` | `-0.4704` | `-0.8606` |
| stress | `+0.9813` | `+0.0622` | `-0.9191` |

Its lead goes **negative** under three of the four panels: without a correct
hypothesis in the box, a swarm that votes on hypotheses drawn from the box is
worse than a search that holds none. Its catastrophic seeds rise `38–39` to
`42–43`, and it wins only `51–52` of 100 paired seeds — a coin flip, against the
archive's 93–97.

The lead delta is `5.7x` to `15.2x` larger for `majority` than for `qd`, in
every panel.

This is the same phenomenon E024 flagged in its own limitation — "the
majority-vote swarm's per-agent belief is drawn from that same supplied set, so
its bimodality is a property of this landscape" — now measured rather than
suspected.

## Result 3 — the hypothesis-free arms, and one number that reads worse than it is

| arm | mean Δ (unheld − held) | catastrophic held → unheld |
|---|---|---|
| `random` | `+0.336` … `+0.364` | `0/100` → `0/100` |
| `scalar` | `-1.313` … `-1.429` | `15–24/100` → `100/100` |
| `planner` | `-0.874` … `-0.916` | `100/100` → `100/100` |
| `qd` | `+0.213` … `+0.275` | `0/100` → `0/100` |
| `majority` | `-0.494` … `-0.584` | `38–39/100` → `42–43/100` |

`scalar` going from `~16/100` catastrophic to `100/100` looks like a collapse
and is mostly a threshold artifact, which should be stated plainly rather than
quoted as a finding. On the `measured` panel its held distribution is mean
`16.370`, sd `0.424` — sitting just **above** the `16.0` cutoff and tightly
clustered on it. **82 of its 100 held seeds fall inside `[16.0, 17.384)`**, one
mean-shift's width of the line. A shift of `-1.384` therefore carries almost the
entire distribution across a boundary it was already resting on. The mean shift
is the real quantity; the count is that shift amplified by where the cutoff
happens to fall.

Two further spreads from the same run are worth recording, because they are the
shape behind the leads above:

- `majority` has sd `3.888` held and `4.499` unheld — an order of magnitude
  wider than every other arm (`qd` `0.226`/`0.229`, `random` `0.239`/`0.251`).
  Its mean is a poor summary of it in either condition. This is the bimodality
  E024 described.
- `qd`'s **worst** seed scores `21.396` held and `21.875` unheld. In both
  conditions the archive's worst run beats every other arm's *mean*.

That shift is itself the residual parity gap measured above, not an effect of
membership: `scalar` never reads `PLAUSIBLE_GOALS`, so there is no answer for it
to lose. It is committed to `INITIAL_GOAL`, and the substitute is `~6.9%` harder
to transfer to from an evolved `INITIAL_GOAL` artifact. `planner`, also
committed, drops by a similar amount. `random`, committed to nothing, gains.

This is why the lead is measured against the *best* hypothesis-free arm rather
than a fixed one, and why the reference arm is `random` in all eight cells: the
statistic routes around the residual mismatch instead of inheriting it.

## Interpretation

E024 named the supplied plausible-goal set as a threat to its headline result.
The threat is real, it is measurable, and it lands somewhere other than where
E024 pointed.

- **For the quality-diversity archive it is not load-bearing.** Take the answer
  out of the box and the archive's advantage moves by 1.6–4.4% of itself, its
  absolute performance goes *up*, it beats its own held-condition self on 93–97
  of 100 paired seeds, and its `0/100` catastrophic record is untouched in all
  eight cells. What the archive is buying is not "one of my four guesses was
  right"; it is having kept artifacts in enough distinct niches that *something*
  in the archive is near wherever the goal lands. A set of four wrong-but-spread
  hypotheses generates that coverage as well as a set containing the right one.

- **For the majority-vote swarm it is entirely load-bearing.** Its whole lead is
  the supplied answer. Remove it and three of four panels put it behind an arm
  that holds no hypothesis at all. Consensus over a hypothesis set is only worth
  what the set is worth; diversity over an artifact archive is worth something
  even when the set is worthless.

The practical reading, stated no more strongly than the evidence supports: on
this landscape, under an unheld future goal, **retaining diverse artifacts
degrades gracefully and retaining diverse beliefs does not**. That is a
distinction E024 could not draw, because in E024 both arms were reading a set
that contained the answer and both looked like the same kind of hedge.

It does *not* show the archive is robust to arbitrary goal change. One
substitute direction is one direction.

## Limitations

- **The substitute goal is one point, not a distribution.** It is matched on
  change size, isolation from the supplied set, attainable ceiling, mean
  attainable utility and transfer regret, but a single direction cannot rule out
  that this particular one is unusually kind to the archive. A sweep over many
  unheld goals is the direct strengthening and is not run here.
- **Trait reordering is not matched**, as recorded above. Both goals promote
  adaptability to first; the substitute promotes reliability where the published
  goal promotes security.
- **A residual `-0.039` transfer gap on evolved artifacts is not eliminated**,
  only measured, attributed to the objective-committed arms, and routed around
  by the choice of statistic. The reference arm is `random` in every cell, which
  is what makes that routing sound; if a future configuration made `scalar` the
  reference, the lead would inherit the gap and this record's Δ values would
  need re-deriving.
- **Only the environment moves.** No arm *updates* its hypotheses from evidence.
  This measures the value of being handed the answer, not the cost of having to
  learn it. A real Goal Graph particle filter is the natural successor — and
  E030 says where to point it: at the `majority` arm, not the archive.
- **The defect channel is disarmed.** E027 and E028 cover it. Arming both
  confounds at once would make any effect unattributable to either.
- **The landscape is synthetic**, as in every experiment from E011 onward. No
  real tasks, no hidden tests, no measured human attention.
- **Raw means are not comparable across conditions.** Every cross-condition
  claim here is about the lead, or about paired per-seed wins, or about
  catastrophic counts against a fixed absolute threshold.

## Decision

E024's supplied-oracle limitation is now **bounded rather than open**. Its text
should stand — the goals are still supplied and still contain the later goal —
but it can no longer be read as an unquantified threat to the archive result.
The quantity is at most 4.4% of the lead, and `0` catastrophic seeds either way.

The same limitation is **upgraded, not bounded, for the majority-vote arm**. Any
future record quoting `majority` as a hypothesis-hedging baseline must say that
its measured advantage on this landscape is contingent on the supplied set
containing the answer.

Issue #22 remains open. E030 closes none of it by itself; it removes one named
confound from one of the two arms that carried it.
