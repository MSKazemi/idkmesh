# E038 — a symmetric gate is not a symmetric burden

[E037](E037-ladder-under-panels.md) measured something it could not explain.
Weakening the verifier panel from `perfect` to `stress` — 25 verifiers at `0.55`
accuracy, `0.9` correlation and a `0.4` blind spot — made the archive's lead go
*up*, from `+1.189` to `+1.659`, and cut its catastrophic seeds from `808` to
`138`. E037 ruled out the two obvious explanations and recorded the question as
open.

E038 answers it, and the answer is that one of E037's own findings is being read
wrongly.

## The claim, stated before the run

E037 established that the gate is **arm-blind**: the widest false-accept gap
between any two arms was `0.0123` on `measured` and `0.0196` on `stress`. That
is true, and it does not mean what it looks like it means.

**An arm-blind gate is not an arm-neutral gate.** The panel errs at the same
rate for everyone, but an error only hurts in the direction the arm is exposed
to, and the arms are not equally exposed. An arm whose proposals are almost
always viable can essentially only suffer false *rejects* — lost good work,
which a matched evaluation budget partly absorbs. An arm whose proposals are
mostly non-viable is mainly exposed to false *accepts*, which put unsound work
into its population.

Four clauses, each able to come out false:

1. the arms differ sharply in base viability — a spread of at least `0.2`;
2. the least viable arm is the one most exposed to false accepts;
3. the least viable arm takes the worst utility damage;
4. the archive is not the most damaged arm.

Clause 1 can kill the whole explanation on its own. If every arm proposes viable
work at about the same rate, differential exposure explains nothing and E037's
question stays open.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e038_symmetric_gate_asymmetric_burden.py \
  --sweep experiments/results/E034-goal-direction.json \
  --output experiments/results/E038-symmetric-gate-asymmetric-burden.json
```

40 seeds on each of E037's five probe goals, on each of the three panels — 200
runs per panel, per arm. The counters are **pooled**, not averaged: the arms
have different denominators, so a per-seed rate averaged over seeds is not the
rate of the pooled run.

## Result 1 — the prediction is supported, 4 of 4

Base viability is read off the `perfect` panel, where the gate makes no errors
at all, so the accept rate *is* the arm's true rate of proposing viable work
rather than an estimate of it.

| arm | base viability | share of its errors that are false *accepts* on `measured` | on `stress` |
|---|---|---|---|
| `random` | `0.3981` | `0.6049` | `0.6004` |
| `qd` | `0.8900` | `0.1196` | `0.1617` |
| `scalar` | `0.9747` | `0.0286` | `0.0294` |
| `planner` | `0.9785` | `0.0215` | `0.0256` |
| `majority` | `0.9864` | `0.0138` | `0.0150` |

The spread is `0.588297`, far past the `0.2` bar the record committed to in
advance. `random` proposes viable work **two times in five**; every other arm
manages nine or more times in ten. So when the panel starts making mistakes,
three fifths of `random`'s errors are junk being let in, and between one and
three per cent of everyone else's are.

## Result 2 — the damage lands almost entirely on one arm

| arm | `perfect` | `measured` | change | `stress` | change |
|---|---|---|---|---|---|
| `random` | `18.7944` | `18.5584` | `-0.2360` | `17.9654` | `-0.8291` |
| `scalar` | `18.3273` | `18.2963` | `-0.0311` | `18.2330` | `-0.0943` |
| `planner` | `16.6188` | `16.6137` | `-0.0051` | `16.5985` | `-0.0203` |
| `majority` | `17.1946` | `17.1834` | `-0.0112` | `17.1802` | `-0.0145` |
| `qd` | `20.6746` | `20.7770` | `+0.1024` | `20.8408` | `+0.1662` |

On `stress`, `random` loses `-0.8291` of post-change utility AUC. The next worst
arm loses `-0.0943` — nine times less — and `planner` and `majority` lose
almost nothing at all. `qd` is the only arm that *gains*, `+0.1662`.

This is the whole of E037's Result 2. `random` is the reference arm that sets
`lead_over_hypothesis_free` for most goals on this shell, so an arm-blind gate
that happens to hit `random` nine times harder than anyone else raises every
other arm's *lead* without any of them getting better. E037 measured that 74% of
the archive's lead growth came from the baseline falling rather than the archive
rising; E038 says why the baseline falls.

## Result 3 — the throughput story is the opposite of the damage story

It is worth writing down that the arm that loses the most is the arm whose
throughput goes *up*.

| arm | `perfect` | `measured` | `stress` |
|---|---|---|---|
| `random` | `0.3981` | `0.4340` | `0.4881` |
| `qd` | `0.8900` | `0.7472` | `0.5354` |
| `scalar` | `0.9747` | `0.8105` | `0.5474` |
| `planner` | `0.9785` | `0.8111` | `0.5488` |
| `majority` | `0.9864` | `0.8202` | `0.5492` |

Every viable-proposing arm sees its accept rate collapse — `qd` from `0.8900` to
`0.5354`, `majority` from `0.9864` to `0.5492` — because a noisy gate rejects
work that should have passed. `random` goes the other way, `0.3981` to `0.4881`,
because a noisy gate accepts work that should have been refused. Reading accept
rate as a health metric would rank `random` as the panel's least affected arm.
It is the most damaged one.

## What this does not explain

`qd` gains. Exposure does not account for that: `qd` sits at `0.8900` base
viability, second-lowest of the five and clearly below `scalar`, `planner` and
`majority`, so on the exposure story it should be the second most damaged arm
rather than the only one that improves. It is `+0.1024` and `+0.1662` instead.

So E038 explains the denominator of E037's Result 2 and not the numerator. That
is the larger part — 74% of it — but the record should not be read as a complete
account of why the archive does better behind a bad gate.

## Limitations

- **This is an association across five arms, not an intervention.** Nothing here
  holds an arm's strategy fixed while moving its base viability. The five arms
  differ in many ways at once, and base viability is the one that happens to
  rank-order the damage. A within-arm manipulation would be the real test.
- **n = 5 arms.** Clauses 2 and 3 are rank comparisons over five points, and one
  of the five (`random`) is doing all the work in both.
- **The archive's own gain is unexplained**, per the section above.
- **Five goals, one shell.** The probe goals are E037's, all on the `d_set 0.30`
  shell at weight `0.40`. Nothing here says the ordering holds elsewhere in the
  goal space — and E035 is a standing warning that a result measured on one
  shell can invert on another.
- **Three panels, and `perfect` is a different kind of condition.** It skips the
  verifier draw entirely rather than drawing a perfect one, so the `perfect`
  column is a no-gate baseline, not a zero-error gate.
- **No deception.** The panel votes on `sim.viable`, a hard constraint. E036's
  channel, where something optimises against the panel, is a different question
  with the opposite answer.

## Decision

Stop describing a verifier panel by its error rate alone. The same panel is a
different instrument for each arm behind it, and the difference is not subtle:
at identical accuracy, identical correlation and an error gap between arms under
`0.02`, one arm lost nine times more utility than the next worst. **What decides
the cost of a review error is the reviewed party's base rate of proposing sound
work.**

For the arena's records this means one concrete correction: `lead_over_hypothesis_free`
is not a stable yardstick across panels, because its reference arm is the arm
most exposed to false accepts. Any cross-panel lead comparison must carry the
decomposition E037 introduced, and a lead quoted without its panel is now known
to be misleading rather than merely incomplete.

Next: the within-arm test this record cannot do. Hold one arm's strategy fixed
and move only its base viability — for instance by varying how much of its
proposal budget goes to unconstrained exploration — and see whether the damage
tracks viability inside a single arm the way it does across the five.
