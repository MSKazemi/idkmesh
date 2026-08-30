# E036 — Does the archive survive contributors who optimise to pass the gate?

**No adversary in this experiment ever made the constraint-guided archive worse
than another arm — it is never strictly beaten in any of the 48 cells. But the
preregistered reason for expecting it to fail was wrong, and the reason it
actually fails is not the archive at all. Two panels with *identical* accuracy
differ only in verifier correlation, and one is completely immune while the
other's archive goes to `58` catastrophic seeds in 100. Correlation is the
attack surface, not accuracy, and not the archive.**

E026, E027 and E028 all model verification going wrong by accident: a panel is
noisy, a panel is correlated, a defect slips through, the defect is invisible. In
all three the archive held.

Issue 22 lists something none of them model, and `matched_budget_emergence`
says so in its own limitations:

> The benchmark does not model churn, malicious workers, task dependencies,
> stigmergic traces, or post-integration defects.

A malicious worker is not a noisy channel. It is an optimising opponent, and the
quantity it optimises is the one the archive selects on.

## Design

The landscape is E028's unchanged: viability lives in a sixth `integrity`
dimension that no goal weights, no behaviour descriptor reads, and the trait
budget does not constrain, so apparent quality carries no information about
whether an artifact is sound.

A fraction of the contributor pool is hostile. A hostile contributor:

- draws `k` candidates instead of one and submits the one with the highest
  **apparent** quality — `unchecked_robust_quality`, exactly what the elitist and
  archive arms rank on;
- sets `integrity` to `0.0`, so the artifact is certainly defective.

`k = 1` is a **faulty** contributor: it ships junk but does not try, and its
apparent quality is statistically indistinguishable from an honest draw. `k = 8`
is a **strategic** one, and it looks *better* than an honest contributor
(`0.595` mean apparent quality against `0.467`). Separating the two is the whole
point — "how many are hostile" and "how hard each one tries" are different
questions and, as it turns out, they do not have the same answer.

Zero integrity is chosen rather than "somewhere below the floor" for two
reasons. A healthy lineage produces exactly-zero integrity with probability
`0.0`, so the signature is auditable; and `0.0` is five mutation sigmas below
the `0.6` floor, so **every** one-generation child of a poisoned parent is still
non-viable and about half land back on exactly zero because the trait clamps.
A captured niche stays captured. Both properties are measured in the tests
rather than assumed.

Nothing in the search arms changes. The adversary is installed as a `Candidate`
subclass the same way E028 installs its landscape, so an arm cannot special-case
it. The evaluation budget contract is untouched: every arm still sees exactly
`agents` proposals per generation and spends `agents * generations` verification
attempts. The adversary's `k` draws are its own cost — the realistic asymmetry,
since an attacker crafting a submission does not consume the maintainer's CI
budget while crafting it.

The four panels are E027's, reused by name so the cells line up with E027's and
E028's matrices:

| panel | verifiers | accuracy | correlation | blind spot | measured false-accept rate |
|---|---|---|---|---|---|
| `perfect` | 1 | `1.0` | `0.0` | `0.0` | `0.0000` |
| `independent` | 25 | `0.7956` | `0.0` | `0.0` | `0.0005` |
| `measured` | 25 | `0.7956` | `0.4513` | `0.0556` | `0.1717` |
| `stress` | 25 | `0.55` | `0.9` | `0.4` | `0.4495` |

`independent` and `measured` have **the same accuracy**. They differ in
correlation and a small blind spot. Hold on to that; it is the result.

### The prediction, stated before the run

Recorded in the module and in the artifact before the sweep ran:

> The archive's catastrophe advantage over the majority-vote swarm shrinks as
> adversary effort rises, and at the highest fraction and effort the archive
> loses its 0/100 catastrophic-seed record.

with the reasoning that *diversity preservation is the mechanism under attack
rather than the defence: the archive keeps one elite per niche and an optimising
adversary can offer the best-looking occupant of every niche.*

## Reproduction

```bash
# the matrix (48 cells, ~5 minutes at 16 jobs)
PYTHONPATH=. python3 sim/e036_adversarial_contributors.py \
  --seeds 100 --agents 64 --generations 50 --change-at 25 --jobs 16 \
  --output experiments/results/E036-adversarial-contributors.json

# the control: zero fraction must be E028 bit for bit
PYTHONPATH=. python3 sim/e036_adversarial_contributors.py --mode identity \
  --seeds 8 --agents 24 --generations 20 --change-at 10
```

Cells run in *processes*, never threads: a cell rebinds `Candidate` and `viable`
on two shared module objects, so two cells in one interpreter would silently read
each other's landscape.

## Result 1 — the control is an identity, not an approximation

At `fraction = 0.0` the hostile branch short-circuits before touching the rng, so
no randomness is consumed and the sweep is **bit-identical** to E028's on all
four panels. `--mode identity` proves it rather than asserting it, the way
E027's cost-0.0 column is pinned. The zero column of every table below is
therefore a live control, not a quoted number.

## Result 2 — the preregistered prediction is partially supported, and its reasoning is wrong

| panel | effort | `f=0.0` | `f=0.01` | `f=0.02` | `f=0.05` | `f=0.1` | `f=0.2` |
|---|---|---|---|---|---|---|---|
| `perfect` | `k=1` | `0` | `0` | `0` | `0` | `0` | `0` |
| `perfect` | `k=8` | `0` | `0` | `0` | `0` | `0` | `0` |
| `independent` | `k=1` | `0` | `0` | `0` | `0` | `0` | `0` |
| `independent` | `k=8` | `0` | `0` | `0` | `0` | `0` | `0` |
| `measured` | `k=1` | `7` | `4` | `4` | `8` | `8` | `17` |
| `measured` | `k=8` | `7` | `6` | `12` | `18` | `28` | `58` |
| `stress` | `k=1` | `50` | `62` | `69` | `66` | `78` | `90` |
| `stress` | `k=8` | `50` | `67` | `74` | `81` | `99` | `100` |

Graded on its two clauses:

- **"the advantage over majority shrinks with effort"** — supported, but barely.
  Summed over the hostile cells of the three non-`perfect` panels the archive's
  catastrophe advantage runs `513` at `k=1` against `478` at `k=8`, a 7% shrink,
  and almost all of it is a ceiling effect on `stress` where both arms reach
  100/100.
- **"the archive loses its 0/100 record"** — **not supported.** On the two panels
  where the archive had a clean record it never lost it: `0` in all twelve
  `perfect` cells and `0` in all twelve `independent` cells, at every fraction and
  both efforts. On `measured` and `stress` it did not have a clean record to lose,
  starting at `7` and `50` with no adversary present.

The reasoning was wrong in a way worth recording. The prediction was that
diversity preservation would be the vulnerability — that an optimising adversary
could take the archive niche by niche. The archive *is* captured that way: its
retained-defect rate on `measured` runs from `0.0281` with no adversary to
`0.3870` at 20% strategic hostiles, so nearly two artifacts in five that it holds
at the end are the attacker's. It is simply that every other arm is captured
worse.

## Result 3 — the archive is never strictly beaten, in any cell

| panel | `random` | `scalar` | `qd` | `planner` | `majority` |
|---|---|---|---|---|---|
| `perfect` | `0` | `35` | `0` | `100` | `37` |
| `independent` | `0` | `36` | `0` | `100` | `37` |
| `measured` | `100` | `100` | `58` | `100` | `95` |
| `stress` | `100` | `100` | `100` | `100` | `100` |

That table is the worst cell of each panel — 20% hostile, `k=8`. Across all 48
cells there is **no cell in which any arm has strictly fewer catastrophic seeds
than the archive**; it is tied for best in 26, always with `random` at zero on
the two immune panels. The archive's *relative* standing is completely robust to
this attack. What degrades is its absolute reliability, and on `measured` at
`k=8` its post-change utility AUC falls from `21.06` to `12.26`.

The memoryless arm is the interesting comparison. `random` retains nothing, so it
cannot be poisoned — and on the two immune panels it also sits at `0`. But on
`measured` it is at `100` before the adversary arrives at all, because a
strategy with no memory cannot recover from a goal change either. Immunity
bought by having nothing to protect is not a defence.

## Result 4 — effort dominates fraction

| panel | `f` | `k=1` | `k=8` | ratio |
|---|---|---|---|---|
| `measured` | `0.0` | `7` | `7` | `1.00`x |
| `measured` | `0.01` | `4` | `6` | `1.50`x |
| `measured` | `0.02` | `4` | `12` | `3.00`x |
| `measured` | `0.05` | `8` | `18` | `2.25`x |
| `measured` | `0.1` | `8` | `28` | `3.50`x |
| `measured` | `0.2` | `17` | `58` | `3.41`x |
| `stress` | `0.0` | `50` | `50` | `1.00`x |
| `stress` | `0.01` | `62` | `67` | `1.08`x |
| `stress` | `0.02` | `69` | `74` | `1.07`x |
| `stress` | `0.05` | `66` | `81` | `1.23`x |
| `stress` | `0.1` | `78` | `99` | `1.27`x |
| `stress` | `0.2` | `90` | `100` | `1.11`x |

On `measured`, going from 1% hostile to 20% hostile at `k=1` moves the archive
from `4` to `17`. Holding the fraction and raising effort from `k=1` to `k=8`
moves it from `17` to `58` — and the ratio is above 3x at three of the five
hostile fractions. **A few contributors who try are worse than many who do not.**

This is the practically useful half of the result. A defence calibrated to the
*number* of bad contributors is calibrated to the wrong variable.

## Result 5 — the adversary cannot beat the panel; it beats what is behind it

| panel | effort | `f=0.0` | `f=0.01` | `f=0.02` | `f=0.05` | `f=0.1` | `f=0.2` |
|---|---|---|---|---|---|---|---|
| `perfect` | `k=1` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| `perfect` | `k=8` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| `independent` | `k=1` | `0.0000` | `0.0002` | `0.0000` | `0.0000` | `0.0000` | `0.0002` |
| `independent` | `k=8` | `0.0000` | `0.0000` | `0.0003` | `0.0002` | `0.0000` | `0.0008` |
| `measured` | `k=1` | `0.0281` | `0.0289` | `0.0338` | `0.0494` | `0.0672` | `0.1252` |
| `measured` | `k=8` | `0.0281` | `0.0405` | `0.0545` | `0.0933` | `0.1845` | `0.3870` |
| `stress` | `k=1` | `0.4359` | `0.4639` | `0.5020` | `0.5891` | `0.7130` | `0.8502` |
| `stress` | `k=8` | `0.4359` | `0.5269` | `0.6352` | `0.7778` | `0.9106` | `0.9833` |

The panel's false-accept rate is *flat* in both knobs — `0.1717` on `measured`
and `0.4495` on `stress` regardless of fraction or effort. The adversary cannot
change how often it gets in. What it changes is what gets in: the archive's
retained-defect rate rises with both knobs, to `0.3870` on `measured` and
`0.9833` on `stress`.

So the mechanism is a division of labour the defender should care about. **The
panel sets the entry rate. The adversary sets the quality of what enters, and
therefore whether it survives selection.** Raising effort does not get more
artifacts past the verifier; it makes the ones that get past it win.

## Result 6 — correlation is the attack surface, not accuracy

This is the finding that was not predicted and is the reason to read this record.

`independent` and `measured` are the same 25 verifiers at the same accuracy,
`0.7956`. The differences are correlation `0.0` against `0.4513`, and a blind
spot of `0.0556`. Their measured false-accept rates are `0.0005` and `0.1717`,
a factor of 340, and their outcomes under a 20% strategic adversary are `0` and
`58` catastrophic seeds.

An imperfect panel is not the vulnerability. One verifier in five being wrong
costs nothing here, provided they are wrong independently. What the adversary
needs is for them to be wrong *together*, and the correlated panel supplies it.

## The starvation control

A hostile contributor does two things: it occupies a proposal slot an honest one
would have used (starvation), and on an imperfect panel it gets accepted
(poisoning). The `perfect` panel separates them, because it reads the patched
viability predicate, sees `integrity`, and admits no hostile artifact at all —
retained-defect rate exactly `0.0000` in all twelve cells.

What remains there is starvation alone, and it does almost nothing: the archive
stays at `0` catastrophic seeds at every fraction, and its worst AUC loss across
the whole `perfect` block is `0.196` out of about `22`, under 1%. Starvation is
not a confound for anything above.

## Interpretation

The headline that survives is not about the archive. Every arm's exposure to an
optimising adversary is set by the panel it sits behind, and the panel property
that matters is independence rather than accuracy. That is consistent with what
this repo already measured about effective panel size, and it says the defence
against malicious contributors is bought in verifier *diversity*, not in
verifier *quality*.

The second thing worth carrying is that adversary effort, not adversary
population, is the dangerous variable — which inverts the intuition that a
community is safe while the hostile fraction is small.

The archive's own record is mixed but honest. It is never beaten, it degrades
gracefully where others collapse, and it is nonetheless captured: at 20%
strategic hostiles on the empirically calibrated panel, `0.3870` of what it
retains is the attacker's work.

## Limitations

- The adversary is goal-blind: it maximises unchecked_robust_quality, which is what the archive and the elitist arm rank on, but not the goal-weighted utility that decides delivery. A goal-aware adversary would be strictly stronger and is not measured here.
- The adversary's effort draws are free to the adversary. The system's evaluation budget is untouched and identical across cells, but a defender who could charge the attacker for its search would face a weaker opponent than this.
- Hostile contributors are independent. They do not coordinate, do not adapt to what was accepted, and do not persist across generations, so this is a lower bound on what an organised attacker does.
- Adversarial artifacts do not breed true: a mutation of an integrity-0.0 parent regains integrity at the mutation sigma, so the pool must be re-poisoned every generation rather than being progressively captured.
- The perfect-panel rows are a null control, not evidence: that panel reads the patched viability predicate, so it sees the latent trait and rejects every hostile artifact. They exist to show the attack runs through the false-accept channel rather than through a defect in the harness.
- One landscape. The panel axis reuses E027's four panels by name so the cells are comparable, but only the defect cost is held at 1.0 and E027's cost axis is not swept again.
- Catastrophe counts use E024's threshold of 0.64 of the post-change horizon, as in E027 and E028, so the counts are comparable across those records but the threshold is still a choice.
- The matrix reports means and counts over the seed set; it does not report a paired significance test across cells.
- Small movements in the `scalar` column on the immune panels (`26`-`40`) are
  seed noise at 100 seeds, not an effect; the archive and `planner` columns there
  are exactly constant, which is what makes the noise legible.

## Decision

Do not describe an imperfect verifier panel as the risk. Describe a *correlated*
one: at equal accuracy, independence moved the archive's worst cell from `58`
catastrophic seeds to `0`. Where a panel's verifiers share a failure mode,
assume an optimising contributor can use it.

Calibrate defences to contributor effort rather than contributor count. A 1%
hostile fraction that optimises is worth more than a 20% fraction that does not.

Keep the archive as the recommended arm. It was not beaten in any of the 48
cells, and it is the only arm that degrades rather than collapsing. But stop
quoting its catastrophe record without naming the panel: `0/100` is a fact about
`independent`, and `58/100` is a fact about `measured`.

Next: the adversary here is goal-blind, independent of the other adversaries,
and cannot see what was accepted. The test that would move this is a *coordinated*
adversary that adapts to feedback — if independence of the verifiers is the
defence, an attacker who learns the panel's shared blind spot should be able to
remove it.

**Answered by [E039](E039-content-addressed-blind-spot.md), and the answer
reverses this paragraph's premise.** The test cannot be run against the panel as
written: `verify_candidate` reads the artifact through exactly one bit
(`viable(c)`), so the blind spot is a memoryless coin rather than a region and
there is no address for an attacker to learn. Give it a content address at the
same marginal rate and the arms that rank on apparent quality walk into it
unaided — `scalar` falls from AUC 13.505 to 0.137 against a *goal-blind*
adversary, with 57% of its verification traffic inside a region calibrated to
carry 5.5%. Coordination then makes things *better* for the archive rather than
worse (20 → 12 catastrophic seeds, unresolved), because concentrating an attack
on a portfolio defender is containment. The blind spot is bait, not a hole.
