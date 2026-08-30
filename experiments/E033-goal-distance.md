# E033 — How far can the goal drift before the archive stops helping?

**The archive's rescue decays smoothly, and at a matched change size it is
entirely gone by the time the future goal sits `0.35` from the supplied set —
about one and a half times the set's own spread. The published measurement of
that rescue was taken at `0.21`, and was a favourable draw from its own ring.**

E030 removed E024's supplied-oracle confound by switching the environment to a
goal the arms do not hold, and found the Quality-Diversity archive keeps
`3.308` of its `3.460` lead over the best arm that holds no hypothesis — 95.6%
— while the majority-vote swarm loses all of its `0.163` and goes to `-0.695`.

E030 also records the limitation that makes that number hard to use:

> The substitute goal is one point, not a distribution over unheld goals.

One point cannot separate two stories with opposite engineering consequences.
If the lead decays smoothly with distance, retained diversity buys a graceful
margin that can be budgeted. If it holds to a radius and then breaks, diversity
buys a guarantee that holds until it doesn't, and the number worth publishing is
the radius rather than the retention percentage.

E033 sweeps the distance, six goals to a ring.

## The axis, and why a naive sweep of it is uninterpretable

The axis is the Euclidean distance from the environment's post-change goal to
the **nearest** member of `emergence_sim.PLAUSIBLE_GOALS`. It is `0.0` when the
future goal is in the box — E024's original setting and E030's `held` condition
— and grows as the world moves somewhere nobody proposed. The supplied set's own
mean pairwise spread is `0.237`, and E030's substitute sits at `0.206`, so the
published finding lives just inside one set-spread of the box, which is exactly
where a cliff would be invisible.

`PLAUSIBLE_GOALS` contains `INITIAL_GOAL`. The distance to the set can therefore
never exceed the distance from the starting goal, so **pushing the future goal
away from the box also makes the change itself bigger**, and a bigger change is
harder for every arm — including the three that never read the box. A sweep that
does not control for this measures the two together.

Two independent controls separate them.

**The lead statistic.** Every number below is
`mean(arm) - mean(best arm that holds no hypothesis)`, computed by E030's rule
over E030's arm partition — `random`, `scalar`, `planner` hold no hypothesis;
`qd` and `majority` read the supplied set. A goal that is merely harder moves
the reference too and cancels. The reference arm is named in every row, because
if it changes between rings the lead is comparing two different baselines.

**The matched ladder.** `MATCHED_RINGS` sweeps the distance to the set while
holding the distance from `INITIAL_GOAL` fixed at `0.391918` — which is E030's
own substitute's change size, so E030's measured point lies *on* the ladder
rather than beside it. Across all seven rings the mean change size stays within
`0.388`–`0.397`. Along that ladder the world moves the same distance in every
ring; only its direction relative to the box changes.

The matched ladder stops at `0.35` because `0.40` from the box while `0.39` from
the start is geometrically impossible. `FREE_RINGS` drops the constraint and
runs to `0.60`, and is reported here as the counter-example rather than the
result.

## Design

Goals are drawn uniformly from the 4-simplex (normalised exponentials, one fixed
pool of 600,000 at seed `20260830`), filtered to within `0.01` of the ring — and,
on the matched ladder, of the change size — and six are chosen per ring by
farthest-point selection so they spread around the ring instead of clustering in
one direction. An infeasible ring raises rather than returning a thin sample.

Every cell is 100 seeds (`seed_start` 1) at `agents=64`, `generations=50`,
`change_at=25`, `bins=8`, on the perfect verification panel — E030's settings
unchanged. That is 42 goal points on the matched ladder and 60 on the free one,
each a full five-arm run, plus E030's two published goals rerun as anchors.

A ring statistic is the mean over its six goals, with a 95% t-interval on the
spread **across goals**. Six is a small sample of a four-dimensional ring, so a
ring difference that does not resolve here is not evidence of no difference; the
classifier reports `unresolved` for that case and reserves `flat` for a ladder
whose interval was narrow enough to have seen a decline the size of the lead
itself.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e033_goal_distance.py --ladder matched --jobs 8 \
  --output experiments/results/E033-matched-change-size.json

PYTHONPATH=. python3 sim/e033_goal_distance.py --ladder free --jobs 8 \
  --output experiments/results/E033-free-ring.json

PYTHONPATH=. python3 sim/e033_goal_distance.py --ladder matched --discriminability \
  --output experiments/results/E033-discriminability-matched.json

PYTHONPATH=. python3 sim/e033_goal_distance.py --ladder free --discriminability \
  --output experiments/results/E033-discriminability-free.json
```

`--jobs` changes speed and not the answer: each goal is an independent seeded
measurement collected in input order. The workers must be processes, because
pointing the environment at a new future goal rewrites module globals in both
copies of the arena.

### The anchors

Both sweeps rerun E030's two published goals and reproduce its committed
perfect-panel cell **exactly** — every arm mean, every lead, every catastrophic
count, and the identity of the reference arm:

| anchor | distance to set | `qd` lead | `majority` lead |
|---|---|---|---|
| `held` (`CHANGED_GOAL`, a member) | `0.000` | `+3.4598` | `+0.1627` |
| `unheld` (E030's substitute) | `0.206` | `+3.3083` | `-0.6954` |

If they had not reproduced, the ladder would be measuring something E030 was
not, and every comparison below would be void.

## Result 1 — the decay is smooth, and it goes to zero

Matched ladder, change size held at `0.39`:

| distance to set | `qd` lead | 95% CI | across the six goals | `majority` lead | `qd` mean | best hypothesis-free arm |
|---|---|---|---|---|---|---|
| `0.055` | `+3.480` | `[+3.070, +3.891]` | `+2.955 .. +3.946` | `+0.050` | `22.389` | `18.909` |
| `0.105` | `+3.383` | `[+2.663, +4.104]` | `+2.318 .. +4.414` | `-0.014` | `22.313` | `18.930` |
| `0.156` | `+3.324` | `[+2.206, +4.441]` | `+1.432 .. +4.652` | `-0.001` | `22.394` | `19.071` |
| `0.213` | `+2.709` | `[+1.447, +3.972]` | `+0.679 .. +4.348` | `-0.300` | `21.707` | `18.998` |
| `0.254` | `+2.370` | `[+1.221, +3.520]` | `+1.273 .. +4.371` | `-0.847` | `21.610` | `19.239` |
| `0.307` | `+1.014` | `[-1.716, +3.744]` | `-3.823 .. +3.709` | `-2.661` | `21.375` | `20.361` |
| `0.349` | `+0.171` | `[-2.598, +2.940]` | `-4.747 .. +3.274` | `-4.152` | `22.104` | `21.933` |

The ring means fall monotonically. The endpoints separate, and the largest
single step carries `0.410` of the total decline of `3.309` against a uniform
share of `0.167` — well under the `0.6` a step needs to be called a cliff. The
shape is **smooth**.

There is no safe radius to publish. There is a rate: the archive's whole
advantage is consumed over roughly one and a half set-spreads.

## Result 2 — the archive does not get worse; everyone else gets better

The obvious reading of Result 1 — that the archive degrades as its curation
objective goes stale — is wrong, and the `qd` mean column says so. Across the
whole ladder the archive delivers `22.389 → 22.104`, a change of `-0.285`. The
lead closes because the best hypothesis-free arm climbs `18.909 → 21.933`, a
rise of `+3.024`. `scalar`, which is committed to the *old* goal and reads
nothing, improves from `16.366` to `21.389`.

So the archive is not damaged by distance. It simply stops being better than
not bothering.

## Result 3 — distant goals are more discriminating, not less

The competing explanation for a closing lead is that far-from-the-box goals are
ones where artifact choice does not matter, so every arm converges and nothing
can lead. That is testable, and it is false in the measured direction. Scoring
every ladder goal against one shared pool of 79,388 viable candidates:

| distance to set | attainable ceiling | headroom over the pool mean | spread over the pool |
|---|---|---|---|
| `0.055` | `0.8919` | `0.3526` | `0.1100` |
| `0.156` | `0.9028` | `0.3624` | `0.1148` |
| `0.254` | `0.9017` | `0.3662` | `0.1188` |
| `0.307` | `0.9172` | `0.3960` | `0.1313` |
| `0.349` | `0.9583` | `0.4348` | `0.1453` |

Choosing well is worth **more** out there, not less: headroom rises 23% from the
near ring to the far one. The archive is the one arm that fails to collect any
of it.

For scale, the three published goals score `0.2686` (`INITIAL_GOAL`), `0.3458`
(`CHANGED_GOAL`) and `0.3681` (E030's substitute) on the same pool, so E030's
substitute was not an unusually easy or hard goal — only an unusually
*favourable* one, which is the next result.

## Result 4 — E030's published point was a favourable draw from its own ring

At `0.206`, the six goals E033 draws give `qd` leads of `+0.679`, `+2.410`,
`+2.611`, `+3.028`, `+3.181` and `+4.348` — mean `+2.709`. E030's substitute
scores `+3.308` and **ranks second of the seven**.

Retention of the in-the-box lead of `+3.460` is therefore `78.3%` at that
distance, not the `95.6%` the single point reports.

E030's number is correct for E030's goal. It is not the number to plan with, and
the gap between the two is the whole reason one point is not enough.

## Result 5 — smooth in the mean is not safe per goal

Two of the 42 matched goals put the archive *behind* the arms that hold no
hypothesis:

| distance to set | goal weights | `qd` lead | `qd` mean | catastrophic seeds | reference |
|---|---|---|---|---|---|
| `0.308` | `[0.033, 0.213, 0.357, 0.395, 0.002]` | `-3.823` | `15.180` | `100/100` | `scalar` |
| `0.348` | `[0.114, 0.001, 0.513, 0.363, 0.009]` | `-4.747` | `19.199` | `0/100` | `scalar` |

The first is a total failure: every one of its 100 seeds falls below E024's
absolute catastrophe threshold of `16.0`, in an experiment where the archive is
`0/100` in almost every other cell ever run.

This is why the spread column matters more than the mean as distance grows. The
six goals span `0.991` of lead at `0.055` and `8.021` at `0.349` — eight times
wider. A single measurement far from the box carries almost no information about
its neighbours.

**A post-hoc observation, offered as a hypothesis and not a finding.** Both
failing goals put nearly no weight on `security` (`0.002` and `0.009`) while the
arena's viability floor forces `security >= 0.25` and all four supplied goals
weight it `0.15`–`0.30`. Of the four matched goals weighting `security` below
`0.05`, the mean `qd` lead is `-1.362`; across the other 38 it is `+2.741`. With
n=4, and all four sitting at `0.254` or further, this is confounded with
distance and cannot be separated here. It is the reason E034 should sweep
*direction* rather than distance.

## Result 6 — the uncontrolled ladder sees none of this

The free ladder sweeps the same axis without holding the change size, which
grows `0.231 → 0.701` along it. Every arm's absolute score rises — `random`
goes `17.931 → 23.548` — because the reachable ceiling rises with it.

For the archive the free ladder returns **`unresolved`**: a total decline of
`0.917` inside an endpoint margin of `2.778`. Run this way, the experiment would
have reported that the archive's lead does not decay with distance at all.

The consensus swarm is the one arm the free ladder still resolves, declining
`-0.405 → -6.669` and classified `smooth`; it never holds a positive lead at any
distance on either ladder.

**Never quote a goal-distance sweep that let the change size move.** Report the
matched ladder, or say the change got bigger too.

## Interpretation

The archive is a bet that the future goal resembles something in the box. E030
showed the bet pays when the goal is nearby but unheld. E033 measures the price
of the resemblance and finds it linear rather than cliffed, fully spent by
`0.35`, and — this is the part that was not visible from one point — spent
without the archive itself deteriorating. `robust_quality` averages utility over
the four supplied goals, so as the world moves away from all four the archive's
curation converges on an uninformative filter. It keeps delivering `~22`, which
was excellent when the alternatives delivered `~19` and is unremarkable when
they deliver `~22`.

That reframes the engineering claim. Retained diversity is not insurance against
an arbitrary future. It is insurance against a future *within about one
set-spread of what you thought to write down*, and its value is measured against
what a hypothesis-free arm would have got anyway.

## Limitations

- **Six goals a ring.** The ring intervals are t-intervals on six observations
  of a four-dimensional ring. They are wide, and every step of the matched
  ladder is individually unresolved; the smooth verdict rests on the endpoints
  separating and no step dominating, not on step-by-step significance.
- **One panel.** Everything here is the perfect verification panel, so the
  anchors could reproduce E030's perfect cell exactly. E030's finding spans four
  panels; whether the decay rate changes under a noisy or correlated panel is
  unmeasured.
- **One arena.** `PLAUSIBLE_GOALS` is four goals in five dimensions with a
  viability floor on two traits. The set-spread unit that makes `0.35` sound
  small is a property of that particular box.
- **Distance is not direction.** A ring is a sphere, and Result 5 suggests the
  archive's failures are directional. This experiment averages over direction by
  design and therefore cannot see that structure.
- **The matched ladder cannot reach past `0.39`.** Distances beyond it exist
  only on the free ladder, where they are confounded.

## Decision

Record the rate, not a radius. Where a design leans on retained diversity to
survive goal drift, the supporting number is `78.3%` retention at `0.21` — nine
tenths of a set-spread — falling to `5%` at `0.35`, measured against the
hypothesis-free baseline at a matched change size, and not E030's `95.6%`, which
is one favourable goal.

Next: **E034** — hold the distance and sweep the direction, testing whether the
archive's failures concentrate on goals that devalue a trait the viability floor
forces every artifact to buy.
