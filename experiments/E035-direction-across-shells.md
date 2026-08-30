# E035 — Does the direction result survive at a second distance?

E034 held the distance to the supplied goal set fixed at `0.30`, swept the
*direction* of the future goal, and reported three things. Every one of them was
measured on one shell, which E034 recorded as its first limitation and closed by
naming the test that would move it:

> Next: the mechanism is open. The test that would move it is a shell sweep — the
> same direction ladder at two or three distances — to establish whether the
> spread grows with distance and whether the trait ordering (`reliability` up,
> `simplicity` down) is stable or is itself a property of this one shell.

E035 runs that test. It repeats E034's ladder unchanged at `0.350` and `0.375`
and compares all three shells. The answer is mixed, and the mixed half falls on
E034's side of the ledger: the spread does **not** grow with distance, and the
trait ordering is **not** fully stable — the trait E034 leaned on hardest
reverses sign across the window. What does survive is the finding E034 treated
as secondary.

## Design

Nothing in the simulation changed. E034's `sweep()` already took a `--distance`,
so the two new shells are the same code, the same 2,000,000-draw goal pool, the
same seed, the same 100 seeds, 64 agents and 50 generations a cell, the same
`+/- 0.015` shell tolerance and `+/- 0.02` weight tolerance, and the same 16
goals in each of the 25 trait-by-weight cells. The change size is held at
E033's `0.391918` throughout, exactly as in E034.

That the shells really are siblings is not asserted, it is tested:
`ComparabilityTest.test_the_three_shells_differ_only_in_distance` reads all
nineteen design keys plus the four shell parameters out of all three artifacts
and fails on any drift. Without it, a trait "flipping sign" could be a changed
seed count rather than a result.

The comparison itself is three statistics, all in
`sim/e035_direction_across_shells.py`:

- **spread** — the range of the archive's lead over the best hypothesis-free arm
  across all the distinct goals on a shell;
- **ladder change** — the `w=0.40` cell minus the `w=0.02` cell for one trait,
  with Welch's t. Resolved means `|t| > 2.878`, the two-sided 0.01 critical value
  at the smallest degrees of freedom seen, which is 0.05 Bonferroni-corrected
  over E034's five preregistered ladders;
- **replication verdict** — `replicates` (same sign, resolved on every shell),
  `consistent` (same sign, not resolved everywhere), or `sign_flips`.

`sign_flips` outranks everything: a ladder that points one way on one shell and
the other way on another is telling us about that shell, not about the arena.

## Reproduction

```bash
# the two new shells (E034's own sweep, moved out to a new distance)
PYTHONPATH=. python3 sim/e034_goal_direction.py --distance 0.35  --goals-per-cell 16 --jobs 8 \
  --output experiments/results/E035-shell-0.350.json
PYTHONPATH=. python3 sim/e034_goal_direction.py --distance 0.375 --goals-per-cell 16 --jobs 8 \
  --output experiments/results/E035-shell-0.375.json

# the comparison
PYTHONPATH=. python3 sim/e035_direction_across_shells.py \
  --shell 0.30=experiments/results/E034-goal-direction.json \
  --shell 0.35=experiments/results/E035-shell-0.350.json \
  --shell 0.375=experiments/results/E035-shell-0.375.json \
  --output experiments/results/E035-direction-across-shells.json

# the feasibility window
PYTHONPATH=. python3 sim/e035_direction_across_shells.py --window \
  --output experiments/results/E035-feasibility-window.json
```

## Result 1 — the ladder cannot be run wherever we like

Before asking what the shells say, it is worth recording that there are very few
of them. E034's design holds *two* quantities at once — the distance to the
supplied set and the size of the change — and those constraints interact.
`PLAUSIBLE_GOALS` contains `INITIAL_GOAL`, so a goal near the supplied box is
also a small change from the initial goal, and a small change cannot put an
extreme weight on any single trait. Below `0.280` at least one trait-by-weight
cell is not thin but **empty**, and the ladder has no low rung to stand on.

| `d_set` | shell members | thinnest cell | that cell | feasible |
|---|---|---|---|---|
| `0.265` | 16313 | 0 | `adaptability` at `0.02` | **no** |
| `0.270` | 19247 | 0 | `adaptability` at `0.02` | **no** |
| `0.275` | 22653 | 8 | `adaptability` at `0.02` | **no** |
| `0.280` | 26324 | 75 | `adaptability` at `0.02` | yes |
| `0.285` | 30248 | 289 | `simplicity` at `0.40` | yes |
| `0.290` | 33631 | 582 | `simplicity` at `0.40` | yes |
| `0.295` | 36502 | 685 | `reliability` at `0.40` | yes |
| `0.300` | 38643 | 753 | `reliability` at `0.40` | yes |
| `0.310` | 41054 | 818 | `reliability` at `0.40` | yes |
| `0.320` | 40203 | 865 | `reliability` at `0.40` | yes |
| `0.370` | 23518 | 187 | `efficiency` at `0.40` | yes |
| `0.375` | 24650 | 134 | `efficiency` at `0.40` | yes |
| `0.380` | 25824 | 104 | `efficiency` at `0.40` | yes |
| `0.385` | 27060 | 57 | `reliability` at `0.02` | yes |
| `0.390` | 27923 | 8 | `reliability` at `0.02` | **no** |
| `0.395` | 24314 | 0 | `reliability` at `0.02` | **no** |
| `0.400` | 18498 | 0 | `reliability` at `0.02` | **no** |

Rows between `0.320` and `0.375` are omitted; every one is feasible, and the
thinnest cell peaks at 865 goals at `0.320` before falling away again.

The feasible window is **`0.280` to `0.385`**, width `0.105`, bounded at both
ends by a genuinely empty cell — `adaptability` at `w=0.02` below, `reliability`
at `w=0.02` above. Two consequences follow. First, "hold the distance and sweep
the direction" can never be run near the supplied set at all, so E034's design
has nothing to say about goals that are small revisions of the one we were
given. Second, E034's `0.30` sits near the lower edge, not in the middle
(`0.3325`), and it is the shell where the low rung is thinnest of those sampled.

## Result 2 — the spread does not grow with distance

E034 conjectured that the direction spread would widen with distance, on the
strength of E033's per-ring spreads. It does not.

| shell | goals | shell members | lead min | lead max | spread | mean | s.d. | negative |
|---|---|---|---|---|---|---|---|---|
| `0.300` | 385 | 38643 | `-4.894` | `+4.471` | `9.365` | `+1.189` | `1.940` | 93 (24.2%) |
| `0.350` | 381 | 27335 | `-4.978` | `+4.430` | `9.408` | `+0.998` | `2.029` | 102 (26.8%) |
| `0.375` | 370 | 24650 | `-5.041` | `+4.368` | `9.409` | `+1.232` | `1.689` | 75 (20.3%) |

`9.365`, `9.408`, `9.409`. The spread is flat to within half a percent across a
window that is a quarter as wide again as the gap between the nearest and
farthest shell sampled. The conjecture is not supported.

This *strengthens* E034's headline rather than weakening it. Direction was worth
`9.365` against the `3.309` that E033's entire distance sweep moved; E035 shows
that ratio is not a property of the shell E034 happened to pick. At every
distance in the window the archive's lead spans more than 2.8x what distance
itself is worth, the mean lead stays positive, and between a fifth and a quarter
of directions are still ones where the archive loses outright.

## Result 3 — one ladder in five replicates

| trait | class | `0.300` | `0.350` | `0.375` | verdict |
|---|---|---|---|---|---|
| `reliability` | floored | `+3.052` (t `+5.80`, resolved) | `+2.748` (t `+5.04`, resolved) | `+1.031` (t `+2.73`) | `consistent` |
| `security` | floored | `+1.412` (t `+1.94`) | `+1.145` (t `+1.46`) | `+0.716` (t `+1.13`) | `consistent` |
| `adaptability` | descriptor | `+2.441` (t `+3.80`, resolved) | `+2.332` (t `+3.49`, resolved) | `+1.657` (t `+2.75`) | `consistent` |
| `efficiency` | descriptor | `-2.445` (t `-3.55`, resolved) | `-3.173` (t `-4.72`, resolved) | `-2.619` (t `-5.76`, resolved) | `replicates` |
| `simplicity` | unconstrained | `-2.628` (t `-3.64`, resolved) | `-1.260` (t `-1.61`) | `+0.723` (t `+1.52`) | `sign_flips` |

Only `efficiency` `replicates`: it falls on all three shells and resolves on all
three, and it is the strongest single result E034 produced that is still
standing without qualification. Three ladders are `consistent` — the same sign
everywhere, but resolving on two shells, two shells, and none.

Every ladder's magnitude decays toward the outer shell. `reliability` runs
`+3.052`, `+2.748`, `+1.031`; `adaptability` `+2.441`, `+2.332`, `+1.657`. At
`0.375` only `efficiency` clears the corrected bar at all. This is consistent
with the outer shell simply being noisier ground — it has the fewest members and
the thinnest cells — and is a reason to read `0.375` as the weakest of the three,
not as evidence that the effects vanish.

## Result 4 — `simplicity` reverses, which qualifies E034's falsification

`simplicity` runs `-2.628`, `-1.260`, `+0.723`. It is the one ladder classified
`sign_flips`.

This matters because of the load E034 put on it. `simplicity` was E034's
*preregistered control*: it is the one trait the viability floor does not
constrain, so the floor hypothesis predicted it would be flat, and E034
falsified that hypothesis on two counts — the control moved, and the two
identically-floored traits behaved differently. The first of those two counts
does not survive the window. At `0.375` `simplicity` is entirely consistent with
flat, and it is consistent with flat *in the opposite direction* from `0.300`.

Three things keep this from being a retraction:

1. **The measurement at `0.300` stands.** It was resolved, at `t = -3.64`,
   against a bar corrected for all five ladders. E034 reported what was there.
2. **The flip is measured across independent shells.** The `0.300` and `0.375`
   shells share no goals at all, so the reversal is not two readings of the same
   sample.
3. **The second count of the falsification survives everywhere.** `security`
   never resolves on any shell — `t` of `+1.94`, `+1.46`, `+1.13` — while
   `reliability` resolves on two of three and exceeds it at every distance. The
   floor hypothesis requires the two floored traits to move together. They do not,
   at any distance in the window.

So the floor hypothesis remains falsified, but on one leg rather than two, and
the surviving leg is the weaker one: the `reliability` − `security` contrast is
itself unresolved on all three shells (`+1.641`, `+1.602`, `+0.315`), so what is
established is that `security` does not move, not that the two provably differ.
E034 already recorded that contrast as unresolved and declined to claim it; that
restraint is what makes the result still usable.

## Result 5 — the category finding is what actually replicates

E034's third result was that the arena's structural trait categories are not a
valid grouping, because the two `niche`-descriptor traits move in opposite
directions and cancel to nothing when averaged. That is the finding that comes
through the window untouched.

`adaptability` rises and `efficiency` falls on all three shells, and the contrast
between them resolves on all three at `t` of `+5.19`, `+5.81`, `+5.67` — the
largest and most stable effect anywhere in E034 or E035. Averaging the two into a
"descriptor" number destroys a `+4.3` to `+5.5` separation at every distance
measured.

## What is left of the mechanism

Ranked by what the window supports:

- **Direction dominates distance.** Holds at every shell, by a factor of at least
  2.8. Unqualified.
- **The structural categories are not a valid grouping.** Holds at every shell,
  with the largest effect measured. Unqualified.
- **`efficiency` de-weighting helps the archive; `adaptability` de-weighting hurts
  it.** Resolved at every shell for `efficiency`, at two of three for
  `adaptability`, same sign throughout.
- **The viability floor does not explain directional failure.** Still falsified,
  but now on the `reliability`/`security` asymmetry alone, and that asymmetry is
  itself unresolved as a contrast.
- **`simplicity` de-weighting hurts the archive.** Shell-local to `0.300`. Do not
  carry this forward.
- **The spread widens with distance.** Not supported. Do not carry this forward.

No mechanism yet predicts which directions are the bad ones. E035 removes two
candidate explanations rather than supplying one.

## Interpretation

The useful shape of this result is that E034's *distributional* claims replicate
and its *per-trait* claims mostly do not. How wide the lead runs, how often it
goes negative, and the fact that a structural grouping cancels its own members
are all stable across the window. Which individual trait is the dangerous one to
de-weight is largely a property of where on the shell you stand.

That is a caution about how E033 and E034 should be quoted. "Report the lead as
a distribution, not a mean" — E034's decision — is exactly right, and E035
raises confidence in it. "De-weighting `simplicity` is what breaks the archive"
would have been the natural next sentence to write, and it would have been wrong.

## Limitations

- **Three shells, one window.** `0.280` to `0.385` is all the geometry allows
  under E034's design. A different change size would open a different window; the
  behaviour near the supplied set is unreachable by this method entirely.
- **The two outer shells are not fully independent.** Their `+/- 0.015` bands
  intersect by `0.005`, and they share 5 goals of 370 (1.4%). The `0.300` shell
  is disjoint from both, so the `sign_flips` verdict — which is read off the
  `0.300` and `0.375` endpoints — is unaffected. The `0.350`-to-`0.375` step is
  the one to read with care.
- **`0.375` is the weakest shell.** Fewest members, thinnest cells, and the only
  shell where four of five ladders fail to resolve. Some of the decay in Result 3
  is likely noise, not signal.
- **One panel.** The perfect verification panel throughout, as in E033 and E034.
  Nothing here has been tested against a noisy or correlated panel.
- **Absence of resolution is not absence of effect.** `security` never resolving
  at 16 goals a cell is consistent with a real but small effect. The claim is
  that it does not move *with* `reliability`, not that it is inert.

## Decision

Carry forward E034's decision unchanged — report the archive's lead at a distance
as a distribution — and add that the `9.365` spread is not shell-specific.

Withdraw two claims from circulation: that the spread grows with distance
(measured flat), and that de-weighting `simplicity` is what breaks the archive
(sign-flips across the window). Keep the falsification of the viability-floor
hypothesis, stated on its surviving leg: the two floored traits do not move
together at any distance.

Next: every result here is on a perfect panel, and the arena's whole point is
that verification is imperfect. The test that would move the mechanism now is
E033's and E034's ladder on a panel with a non-zero blind-spot floor — if the
directional structure is a property of the goal geometry it should survive, and
if it is a property of costless perfect verification it should not.
