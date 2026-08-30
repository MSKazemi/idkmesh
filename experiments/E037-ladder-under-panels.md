# E037 — is the direction result about the goal geometry, or about a perfect verifier?

E030 through E035 answered five different questions and shared one setting none
of them varied: verification was perfect. Every candidate's true viability was
observed exactly, and observing it cost nothing. [E035](E035-direction-across-shells.md)
closed by naming that as the test that would move the mechanism:

> Next: every result here is on a perfect panel, and the arena's whole point is
> that verification is imperfect. The test that would move the mechanism now is
> E033's and E034's ladder on a panel with a non-zero blind-spot floor — if the
> directional structure is a property of the goal geometry it should survive,
> and if it is a property of costless perfect verification it should not.

E037 is that test.

## Design

E034's ladder, unchanged, run three times: on the perfect panel it was published
with, and on E027's `measured` and `stress` panels. Nothing else moves. The
shell is E034's own — `d_set = 0.30`, change size `0.391918`, tolerance `0.015`
— drawn from the same pool with the same seed, so the three runs measure the
**same 385 goals**.

No simulation code was written for this. `sim/e033_goal_distance.py` has always
taken a `panel` setting and `sim/e034_goal_direction.py` has always forwarded
it, so the two new arms are `--panel measured` and `--panel stress`. If a result
moves, the panel moved it.

`measured` is the panel that matters. It holds the same 25 verifiers at the same
`0.7956` accuracy as `independent`, and differs only in correlation — the
distinction [E036](E036-adversarial-contributors.md) showed is what a panel's
blind spot is actually made of.

One detail the record has to be exact about: `e027.PANELS` contains a `perfect`
entry, but the sweep never uses it. `e033._panel("perfect")` returns `None`,
which skips the verifier draw entirely and consumes a different rng stream. The
`perfect` column below therefore reports `verification_drawn` as `false` rather
than restating a config that was not applied.

| panel | `verification_drawn` | verifiers | accuracy | correlation | blind spot | mean lead | spread | goals with a negative lead |
|---|---|---|---|---|---|---|---|---|
| `perfect` | `false` | 0 | `1.0` | `0.0` | `0.0` | `+1.189` | `9.365` | 93 / 385 |
| `measured` | `true` | 25 | `0.7956` | `0.4513` | `0.0556` | `+1.328` | `9.168` | 84 / 385 |
| `stress` | `true` | 25 | `0.55` | `0.9` | `0.4` | `+1.659` | `9.038` | 69 / 385 |

Because the shell is held, the comparison is **paired**: each panel's result is
differenced against `perfect` goal by goal. That is checked, not assumed —
`comparability` refuses any pair of artifacts differing in anything but the
panel, and `goal_alignment` refuses to pair panels whose goal sets are not
identical. Both passed: 22 design keys identical, 385 goals shared, 385 goals
measured on each panel.

## The prediction, stated before the run

E035's sentence, turned into four clauses that could each come out false:

1. the descriptor contrast resolves on every panel;
2. no trait's ladder flips sign across the panels;
3. the floored pair stays asymmetric — `reliability` above `security`, and
   `security` never resolving;
4. the archive still leads on every panel.

The reasoning behind it: E034's ladder is a statement about which directions the
archive's diversity covers, and coverage is a property of the niche grid and the
budget, neither of which the panel touches. If the ladder was instead an
artifact of free, exact quality observation, weakening the panel should break
it.

## Reproduction

```bash
# the two new panels (E034's own sweep, with the panel changed)
PYTHONPATH=. python3 sim/e034_goal_direction.py --panel measured --goals-per-cell 16 --jobs 8 \
  --output experiments/results/E037-panel-measured.json
PYTHONPATH=. python3 sim/e034_goal_direction.py --panel stress   --goals-per-cell 16 --jobs 8 \
  --output experiments/results/E037-panel-stress.json

# the comparison
PYTHONPATH=. python3 sim/e037_ladder_under_panels.py \
  --panel perfect=experiments/results/E034-goal-direction.json \
  --panel measured=experiments/results/E037-panel-measured.json \
  --panel stress=experiments/results/E037-panel-stress.json \
  --output experiments/results/E037-ladder-under-panels.json

# the leakage probe
PYTHONPATH=. python3 sim/e037_ladder_under_panels.py --mode leakage \
  --panel perfect=experiments/results/E034-goal-direction.json \
  --panel measured=experiments/results/E037-panel-measured.json \
  --panel stress=experiments/results/E037-panel-stress.json \
  --output experiments/results/E037-panel-leakage.json
```

## Result 1 — the ladder survives, 4 of 4 clauses

The prediction is **supported**: 4 of 4 clauses met.

| trait | class | `perfect` | `measured` | `stress` | verdict |
|---|---|---|---|---|---|
| `reliability` | floored | `+3.052` (t `+5.80`, resolved) | `+2.941` (t `+5.55`, resolved) | `+2.606` (t `+4.66`, resolved) | `replicates` |
| `security` | floored | `+1.412` (t `+1.94`, not resolved) | `+1.175` (t `+1.61`, not resolved) | `+0.786` (t `+1.08`, not resolved) | `consistent` |
| `adaptability` | descriptor | `+2.441` (t `+3.80`, resolved) | `+2.666` (t `+4.33`, resolved) | `+3.204` (t `+5.72`, resolved) | `replicates` |
| `efficiency` | descriptor | `-2.445` (t `-3.55`, resolved) | `-2.395` (t `-3.54`, resolved) | `-2.263` (t `-3.39`, resolved) | `replicates` |
| `simplicity` | unconstrained | `-2.628` (t `-3.64`, resolved) | `-2.391` (t `-3.29`, resolved) | `-1.914` (t `-2.58`, not resolved) | `consistent` |

Every sign is the same on all three panels, and the three traits that resolve on
the perfect panel with room to spare still resolve on `stress`, where 45% of the
gate's decisions are wrong. The structure E034 found is a property of the goal
geometry. It is not an artifact of costless exact verification.

Two ladders soften rather than break. `security` never resolves anywhere, which
is E035's finding restated — the two identically-floored traits do not move
together, and that is what falsifies the viability-floor hypothesis on its
surviving leg. `simplicity` falls from `-2.628` (t `-3.64`) to `-1.914`
(t `-2.58`), crossing below the resolution bar on `stress` while keeping its
sign, so it is recorded as `consistent` rather than `replicates`.

The two structural contrasts behave exactly as E035 reported them, and if
anything more strongly:

| contrast | `perfect` | `measured` | `stress` |
|---|---|---|---|
| `adaptability` - `efficiency` | `+4.886` (t `+5.19`, resolved) | `+5.060` (t `+5.53`, resolved) | `+5.467` (t `+6.27`, resolved) |
| `reliability` - `security` | `+1.641` (t `+1.83`, not resolved) | `+1.766` (t `+1.96`, not resolved) | `+1.821` (t `+1.99`, not resolved) |

The descriptor contrast is the one E034 used to show the arena's trait
categories are an invalid grouping — the two `niche` descriptors move in
opposite directions and cancel. It resolves on all three panels and *grows* as
the panel weakens. The floored contrast never resolves on any panel, as at every
shell in E035.

## Result 2 — the archive's lead goes up as the panel gets worse

This was not predicted, and it is the direction nobody would guess.

| paired against `perfect` | `measured` | `stress` |
|---|---|---|
| archive's lead | `+0.140` (t `+15.81`) | `+0.470` (t `+17.88`) |
| archive's own score | `+0.033` (t `+7.82`) | `+0.122` (t `+6.97`) |
| consensus arm's lead | `+0.116` (t `+20.01`) | `+0.386` (t `+22.35`) |
| goals where the lead falls | 108 / 385 | 95 / 385 |
| goals whose reference arm moves | 6 / 385 (`random->scalar`) | 34 / 385 (`random->scalar`) |
| archive's catastrophic seeds | `808` -> `593` | `808` -> `138` |

Every one of those is resolved far past the bar. The archive's mean lead rises
monotonically — `+1.189` on `perfect`, `+1.328` on `measured`, `+1.659` on
`stress` — the goals where it is behind fall from 93 to 84 to 69 of 385, and its
catastrophic seeds fall from `808` to `593` to `138`. On `stress`, not one goal
of 385 got worse on that count.

## Result 3 — three quarters of that is the yardstick falling, not the archive rising

The lead is measured against the best hypothesis-free arm *for that goal*, so a
lead that grew could mean the archive improved or could mean its baseline
collapsed. Both are happening, and the split is not close:

| panel | change in the lead | change in the archive's own score | implied change in the baseline | share of the lead's growth from the baseline |
|---|---|---|---|---|
| `measured` | `+0.139718` | `+0.033038` | `-0.106680` | 76.4% |
| `stress` | `+0.470448` | `+0.121759` | `-0.348689` | 74.1% |

Roughly three quarters of the archive's growing lead is the hypothesis-free arms
getting worse. The archive's own score does rise, resolved on both panels
(t `+7.82` and `+6.97`), so it is not purely a yardstick effect — but a reader
who takes "the archive gains from a bad panel" as "the archive is helped by bad
verification" has the causality wrong three times out of four.

The yardstick literally moves, too: the reference arm switches from `random` to
`scalar` on 6 goals under `measured` and 34 under `stress`. The per-arm
catastrophe counts say why.

| arm | `perfect` | `measured` | `stress` |
|---|---|---|---|
| `random` | `0` | `0` | `125` |
| `scalar` | `5879` | `6249` | `6624` |
| `qd` | `808` | `593` | `138` |
| `planner` | `13938` | `13945` | `14082` |
| `majority` | `14025` | `13983` | `13939` |

`random` is catastrophe-free on both the perfect and the `measured` panel and
picks up `125` catastrophic seeds on `stress`. That is the baseline breaking.
Note also what is true on **every** panel including the perfect one:
`random` — not the archive — has the lowest catastrophe count. That is an E034
fact, not something E037 changed, and the ranking does not move across panels.
It is the reason the archive is recommended on its *lead*, which is a
utility measure, and not on this count.

## Result 4 — the obvious mechanism is ruled out, not assumed

The tempting explanation is that a leaky gate lets more candidates through and
the archive, alone among the arms, has somewhere to put them. The sweep cannot
say: `e030.per_seed_auc` keeps only the utility AUC and discards the per-arm
verification metrics. `--mode leakage` reruns 20 seeds on five of the measured
goals with those metrics kept.

| panel | false accepts | false rejects | asymmetry | widest gap between arms | archive size |
|---|---|---|---|---|---|
| `perfect` | `0.000000` | `0.000000` | `+0.000000` | `0.000000` | `64.0` |
| `measured` | `0.178223` | `0.171943` | `+0.006280` | `0.012343` | `64.0` |
| `stress` | `0.443982` | `0.447830` | `-0.003848` | `0.019580` | `64.0` |

Three things follow, and the first kills the tempting explanation:

* **The archive does not grow.** It is capacity-bound at `64` — the agent count
  — on every panel. Whatever the extra accepted candidates do, they do not make
  the archive bigger.
* **The gate is not leaky; it is noisy.** False accepts and false rejects run
  within `0.0063` of each other on `measured` and `0.0038` on `stress`. It is a
  symmetric error channel, not a one-way leak.
* **The panel does not favour an arm.** The widest false-accept gap between any
  two arms is `0.0123` and `0.0196`. It could not be otherwise — the panel
  cannot see which arm proposed — but if it were, every cross-arm comparison in
  E030 through E035 would be confounded, so it is measured rather than assumed.

E037 therefore reports *that* the archive's relative position improves under a
noisy gate and *that* the two obvious mechanisms are not it.

**Answered by [E038](E038-symmetric-gate.md), and by reading the second of those
findings the other way round.** An arm-blind gate is not an arm-*neutral* gate:
the arms differ enormously in how often they propose viable work at all
(`random` `0.3981`, every other arm `0.8900` or above), so three fifths of
`random`'s verification errors are false accepts against one to three per cent
of everyone else's. On `stress`, `random` loses `-0.8291` of utility and the
next worst arm loses `-0.0943`. `random` is the reference arm, so the archive's
lead rises without the archive improving — which is exactly the 74% measured in
Result 3. What E038 does *not* explain is the remaining quarter: the archive's
own `+0.1662` gain.

## Result 5 — what this panel is, and is not, a model of

The panel in this arena votes on `sim.viable` — a hard constraint on
`reliability`, `security` and the budget. Weakening it therefore adds **noise to
a hard gate**. It does not add deception: there is no latent dimension here on
which a candidate can look good and be unsound.

That is exactly the channel [E036](E036-adversarial-contributors.md) added, on
E028's latent landscape, and the two records must be read together:

* **Noise is survivable.** Push the same panel to `0.55` accuracy and `0.9`
  correlation and the archive's catastrophic seeds *fall*, from `808` to `138`.
* **Deception is not.** Put a latent integrity dimension behind the same panel
  and give contributors a reason to optimise against it, and the same `measured`
  panel takes the archive from `0` to `58` catastrophic seeds in 100.

The same correlation number, `0.4513`, is harmless in the first setting and is
the whole attack surface in the second. A panel's correlation is not dangerous
on its own; it is dangerous when something is optimising against it.

## Limitations

- **One shell.** Everything here is at `d_set = 0.30`. E035 showed `simplicity`
  *sign-flips* across shells at a fixed panel; E037 shows it merely attenuates
  across panels at a fixed shell. Neither result generalises to the other axis,
  and the two have not been crossed.
- **The lead is a utility measure, and the mechanism behind Result 2 is only
  partly established.** Result 4 rules out the archive absorbing more and rules
  out differential treatment by the panel. [E038](E038-symmetric-gate.md) then
  explained the larger part — the baseline arm's collapse, 74% of the effect —
  by differential exposure to false accepts. The archive's own gain, the other
  quarter, is still unexplained.
- **Three panels, not a sweep.** `perfect`, `measured` and `stress` are three
  points, and `perfect` is not even the same *kind* of condition as the other
  two — it skips the verifier draw rather than drawing a perfect one. The
  monotone trend in Result 2 rests on three points, one of which is
  qualitatively different.
- **The leakage probe is small.** 20 seeds on 5 goals, against 100 seeds on 385
  goals for the ladder. It is enough to rule out an archive that grows by a
  third; it is not a precision measurement.
- **No deception channel.** By construction, per Result 5. Nothing here says
  anything about a panel facing an adversary; that is E036's question and E036's
  answer is the opposite one.
- **Absence of resolution is not absence of effect.** `security` failing to
  resolve on any panel at 16 goals a cell remains consistent with a real but
  small effect.

## Decision

Stop qualifying E030 through E035 with "on a perfect panel". The directional
structure — the descriptor cancellation, the floored pair's asymmetry, the sign
of every ladder — survives a panel that gets 45% of its decisions wrong. Those
records can be quoted without the caveat.

Keep the caveat on the *magnitudes*. The archive's lead is not panel-invariant:
it is roughly 40% larger on `stress` than on `perfect`, and about three quarters
of that difference is the hypothesis-free baseline degrading rather than the
archive improving. Quote a lead with the panel it was measured on.

Do not carry "a worse panel is better for the archive" out of this record. What
is measured is that the archive's *relative* position improves under symmetric
gate noise, that its absolute score improves much less, and that the mechanism
is unknown. Read alongside E036, the general claim is the opposite: a panel's
weakness is survivable when it is noise and catastrophic when something is
optimising against it.

Next: cross the two axes. E035 found the direction result is shell-dependent at
a fixed panel and E037 finds it panel-robust at a fixed shell; whether the
shell-dependence itself survives an imperfect panel is one sweep away, and it is
the one that would tell us whether the feasibility window is a geometric fact or
a perfect-panel one.
