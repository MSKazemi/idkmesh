# E039 — the blind spot has no address, and giving it one baits the optimiser

**Module:** [`sim/e039_content_addressed_blind_spot.py`](../sim/e039_content_addressed_blind_spot.py)
**Artifact:** [`experiments/results/E039-content-addressed-blind-spot.json`](results/E039-content-addressed-blind-spot.json)
**Tests:** [`tests/test_e039_content_addressed_blind_spot.py`](../tests/test_e039_content_addressed_blind_spot.py)
**Refs:** [#22](https://github.com/MSKazemi/idkmesh/issues/22), [#30](https://github.com/MSKazemi/idkmesh/issues/30), [#86](https://github.com/MSKazemi/idkmesh/issues/86)

[E036](E036-adversarial-contributors.md) closed by naming its own next step:

> the adversary here is goal-blind, independent of the other adversaries, and
> cannot see what was accepted. The test that would move this is a
> *coordinated* adversary that adapts to feedback — if independence of the
> verifiers is the defence, an attacker who learns the panel's shared blind
> spot should be able to remove it.

E039 tried to run that test and found it could not be run as posed. Fixing the
reason produced a result that reverses the intuition behind the request.

## The claim, stated before the run

Five clauses, preregistered in `PREDICTION` and scored in `outcome`:

| clause | predicted | observed |
|---|---|---|
| `the_panel_reads_the_artifact_through_one_bit` | true | **true** |
| `coordination_is_worthless_against_a_memoryless_panel` | true | **true** |
| `content_addressing_alone_is_not_the_attack` | true | true *(but see Result 3)* |
| `coordination_pays_against_a_content_addressed_panel` | true | **false** |
| `the_archive_is_the_most_exposed_arm` | true | **false** |

**3 of 5.** Two clauses are falsified and both are kept as written. The
falsifications are the useful part of this record.

## Result 1 — the panel reads the artifact through one bit. This is a proof.

`sim.emergence_sim.verify_candidate` touches the candidate exactly once:

```python
truth = viable(c)
```

Everything after that — the per-verifier accuracy draw, the shared correctness
shock, the blind-spot draw — is a coin flipped against the panel's rng and
never against the artifact. So two candidates that differ in every trait but
agree on that one bit are *indistinguishable* to the panel. `content_blindness`
runs 4000 decisions on the same rng stream for two such pairs and gets
**bit-identical decision sequences**, and differing sequences across the
viability bit. A test re-derives the single-use claim from the function's
source, so a future edit that reads the artifact somewhere else fails loudly
rather than silently invalidating this record.

The consequence for E036's request: **there is no blind spot to learn.** It is
a memoryless coin, not a region of artifact space, and no amount of feedback
localises a coin. A "coordinated adversary" measured against this panel would
return a null, and the null would be a fact about the simulator.

This scopes more than E036. E016, E020, E025–E028, E036, E037 and E038 all
measure panels whose errors are independent of artifact content. None of those
records says so.

## Result 2 — coordination against the memoryless panel does nothing, as it must

The archive's catastrophic seeds move `28 → 25` of 100 (`z = -0.48`,
unresolved). That is the control working: with nothing to learn, the coordinated
adversary is the goal-blind one. The two are built to be *identical* before any
evidence arrives — an unseen niche scores exactly 0.5 under a Beta(1,1)
posterior, so every niche ties and the tie-break is E036's apparent-quality
rule. A test asserts the two classes produce the same candidate from the same
seed on an empty memory.

## Result 3 — content-addressing alone is the attack, and it lands on the arms that optimise

The clause passed **on the archive**, which is the arm it was scored on, and is
emphatically false one column over. This is the largest effect in the
experiment and the preregistration would have hidden it, so it is reported from
a post-hoc block that says so.

Moving the blind spot from a coin to two niches — same panel size, same
correlation, same marginal accuracy, **no coordination at all** — at a 10%
hostile fraction:

| arm | catastrophic seeds | post-change utility AUC | region share | z |
|---|---|---|---|---|
| `scalar` | 93 → **100** | 13.505 → **0.137** | 0.5722 | **+2.69 ✓** |
| `planner` | 100 → 100 | 7.651 → **0.000** | 0.6310 | — *(saturated)* |
| `majority` | 85 → 84 | 5.474 → 3.421 | 0.2735 | −0.20 |
| `random` | 100 → **96** | 11.771 → 12.927 | 0.0537 | **−2.02 ✓** |
| `qd` | 28 → **20** | 17.678 → **19.042** | 0.0376 | −1.32 |

`scalar` and `planner` do not merely degrade; their post-change utility goes to
essentially zero. And they are *in* the blind spot — 57% and 63% of their
verification traffic, against a region calibrated to carry 5.5%.

**The construction landed where it was aimed, and there is a control that says
so.** `random` does not optimise, so its realised region share should sit at
the calibrated mass. It does: **0.0537 against 0.05546**. Nothing forces that
agreement — the calibration is measured on initial draws and a run evolves away
from them — so it is reported as a check rather than assumed.

## Result 4 — the archive is the *least* exposed arm, not the most

The preregistered reasoning was: an arm that spreads across niches must walk
into a niche-addressed blind spot, so the archive should be the most exposed.
Backwards. Region share under attack:

```
planner   0.6785      scalar    0.6460      majority  0.3055
random    0.0833      qd        0.0531        <- the archive
```

**Post-hoc reading.** A blind-spot niche is the one place in the arena where a
non-viable artifact with high apparent quality is *certain* to be accepted, so
it is the most attractive real estate there is to an arm that ranks on apparent
quality. The elitist arms converge into it and stay. The archive cannot: it
keeps one elite per niche, so however good the region looks it can hold at most
`region_size / niche_count` of the archive's slots — `2/64 = 0.031`, against a
measured 0.0376–0.0531. Niche partitioning caps the blind spot's reach on the
portfolio.

So the blind spot is not a hole the attacker walks through. It is **bait, and
the defender's own selection pressure walks into it.**

This is the same shape [E038](E038-symmetric-gate.md) found and a different
axis: one gate, applied identically, costing arms wildly different amounts
because they do not submit the same distribution of work. E038's axis was base
viability. This one is where in the space an arm chooses to look.

## Result 5 — coordination helps the *defender*, where it moves anything

Every coordination contrast on the archive is negative — fewer catastrophes
with a coordinated adversary than a goal-blind one:

| panel | goal-blind → coordinated | z | resolved |
|---|---|---|---|
| memoryless | 28 → 25 | −0.48 | no |
| content-addressed | 20 → **12** | −1.54 | no |
| content-addressed, diffuse region | 26 → **17** | −1.55 | no |

None resolves at 100 seeds, so this is a direction and not a measurement. The
reading that fits: a coordinated adversary concentrates its submissions into the
region, which means it *stops* attacking the other 62 niches. Against a
portfolio defender, concentrating an attack is containment. Against an elitist
arm there is nothing left to contain — `scalar` and `planner` are already at
100/100.

The diffuse region (9 niches carrying 0.0493 instead of 2 carrying 0.0555) does
not change the picture, which is worth knowing: the effect is not an artifact
of the region being small enough to memorise.

## Reproduction

```bash
PYTHONPATH=. python sim/e039_content_addressed_blind_spot.py --blindness-only
PYTHONPATH=. python sim/e039_content_addressed_blind_spot.py \
    --seeds 100 --pretty --jobs 10 \
    --output experiments/results/E039-content-addressed-blind-spot.json
```

Ten cells: two panel shapes × two adversaries × two hostile fractions, plus the
diffuse-region pair at the headline fraction. 100 seeds and five arms per cell,
E036's strategic effort of 8, E033's arena defaults. Cells run in processes
because each one rebinds `Candidate`, `viable` *and* `verify_candidate` on
shared module objects and keeps the adversary's memory in a module global.

Every exposure record is matched back to the arm that produced it and the match
is **checked** — a run's own attempt count must equal the arm's reported
`verification_attempts`, or the cell raises. The adversary's memory resets at
the start of every run, so no seed and no arm inherits another's learning.

## What this does not establish

- **The region is a construction, not a measurement.** E020 measured the blind
  spot's *rate* on 25 real oracles. Nothing measures its *shape*. A real shared
  blind spot need be neither niche-aligned nor this concentrated, and the whole
  of Results 3–5 depends on it being addressable in the coordinates the arms
  and the archive actually use.
- **Two clauses passed as nulls.** An unresolved difference at 100 seeds is not
  evidence of no difference; the observed differences and their `z` are in the
  artifact so the width can be judged.
- **The niche grid the blind spot is addressed by is the grid the archive
  partitions on.** That is the strongest possible alignment between the
  defence's structure and the attack's. Result 4 should be read as an existence
  result — niche partitioning *can* cap a blind spot's reach — not as a rate
  that would survive a differently-shaped region.
- **The adversary's feedback is exact and immediate.** It sees the decision on
  every one of its own submissions. A real attacker sees a delayed, partial
  signal.
- **The catastrophe metric saturates.** `planner` is at 100/100 before and
  after, so its collapse is only visible in utility AUC. Where an arm is
  pinned, read the AUC column.

## Decision

Stop describing the blind spot as a rate. `lambda = 0.0556` is a *marginal*
quantity, and two panels with the same lambda produced `scalar` at AUC 13.5 and
at AUC 0.137. What matters is whether the missed set has an address the
optimiser can find — and the results above say the address matters far more
than the rate.

Do not model an attacker as the thing that finds the blind spot. In every cell
here the arms found it faster and used it harder than the adversary did, and
the adversary's coordination made things *better* for the portfolio defender.
The failure mode to design against is a defender's own selection pressure
concentrating on a region the verifier cannot see, with or without anyone
attacking.

Keep the archive as the recommended arm, and add a reason it did not have
before: its niche partition is a structural bound on how much of its portfolio
any bounded blind region can own. That bound is a property of the partition,
not of the search, so it should hold for any diversity-preserving arm.

Next: the bound is the testable part. `region_size / niche_count` predicts the
archive's exposure and predicts nothing about the elitist arms. Sweeping region
size against bin count would confirm or break it, and it is one sweep away.
