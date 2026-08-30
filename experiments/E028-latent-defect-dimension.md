# E028 — Does the archive still survive when the defect is invisible?

## Research question

[E027](E027-defect-propagation.md) armed E024's defect-propagation channel and
found that the constraint-guided archive held at `0/100` catastrophic seeds in
all twenty panel-by-cost cells while unconstrained random search went `0/100` to
`94/100`. The same audit that produced that result also produced the caveat
that bounds it: on this landscape, apparent robust quality *alone* separates
viable from non-viable accepted candidates at AUROC `0.937`. Elitist selection
is therefore already acting as a second, free verifier, and E027 could not say
how much of the archive's survival was retained diversity and how much was the
landscape quietly leaking ground truth into the quality signal.

E027 named the experiment that would settle it, and this is that experiment:

> Build a landscape whose apparent-quality signal is uninformative about
> viability, and ask whether the Quality-Diversity arm still holds at `0/100`.

Answer, in one line: **no.** The archive stops being safe. What survives is the
*ordering* — the archive is still the best of the five arms — not the absolute
claim that it never fails catastrophically.

## The confound, stated precisely

`sim.viable` requires `reliability >= 0.25` and `security >= 0.25`.
`sim.unchecked_utility` gives both traits positive weight under every plausible
goal and adds `0.08 * sqrt(reliability * security)` on top. A candidate that
looks good therefore *is* more likely to be viable, before any verifier votes.

Two facts follow, and only the second is a problem:

- The verifier panel is not the only thing standing between an accepted defect
  and the delivered artifact. Selection is a second filter.
- Because that second filter is free and perfectly reliable in the direction it
  acts, E027's arms were partly protected by an oracle no real system has.

E027 measured this rather than assuming it, and reported it as the dominant
confound on its own conclusion. E028 removes it.

## The construction, and why this one

Ground-truth viability moves off the five budgeted traits and into a sixth
`integrity` trait that:

- **no plausible goal weights**, so it cannot enter `utility` at all;
- **no behaviour descriptor reads**, so it cannot enter `niche`;
- **the trait budget does not constrain**, so it cannot be inferred from what a
  candidate spent elsewhere.

Independence is therefore structural rather than tuned. Nothing is fitted to
produce an effect: the alternative constructions all require choosing a
coefficient that trades the positive coupling of the original landscape against
the negative coupling the shared budget would introduce, and any such choice is
a free parameter aimed at a target. A dimension the goals cannot see has no
coefficient to choose.

This is also the case the synthetic landscape was always standing in for. A
latent defect in real software — a race, an injection, an unhandled boundary —
is not visible in how good the artifact looks. The original landscape's
alternative, that quality and correctness are 0.94-AUROC substitutes for one
another, is the optimistic end of the range, not the neutral one.

`tests/test_e028_latent_defect_dimension.py` pins the invisibility directly:
two candidates differing only in `integrity` must produce identical utility
under every plausible goal, identical robust quality, and an identical niche;
and spending the whole budget must not move `integrity`.

## What is held fixed — the parity control

Changing difficulty at the same time as informativeness would confound the
comparison, so two properties of the original landscape are held and *measured*
rather than asserted. `--mode parity` reports both landscapes in one process,
at the same sample size and the same seeds:

| Measured over 200,000 fresh draws | Original | Latent | Held? |
|---|---|---|---|
| Base viability rate | 0.396940 | 0.401290 | yes, by construction |
| `P(child viable \| parent viable)` | 0.834937 | 0.879900 | no — see below |
| **AUROC of apparent quality as a viability classifier** | **0.784979** | **0.500642** | **the intended change** |

`integrity ~ U(0, 1)` and the floor is `0.6`, so the base rate is exactly
`1 - 0.6` by construction rather than by fitting.

Heritability is deliberately *not* matched at the default. The default
`integrity` mutation sigma is the trait sigma, `0.12`, which adds no constant
the original model did not already have — and it leaves viability **stickier**
in the latent landscape than in the original, `0.880` against `0.835`. Stickier
viability helps every arm retain viable material, so the residual bias runs
against a collapse finding rather than toward it.

The sensitivity arm closes even that gap. At `--integrity-sigma 0.171` the
latent landscape's heritability is `0.830447` against the original's `0.834937`,
matched to within 0.005 — and the AUROC is unchanged at `0.500642`.

## Reproduction

```bash
PYTHONPATH=. python sim/e028_latent_defect_dimension.py --mode parity \
  --samples 200000 --seed 20260830 --pretty
PYTHONPATH=. python sim/e028_latent_defect_dimension.py --mode matrix --seeds 100 --pretty
PYTHONPATH=. python sim/e028_latent_defect_dimension.py --mode matrix --seeds 100 \
  --panels stress --integrity-sigma 0.171 --pretty
PYTHONPATH=. python sim/e028_latent_defect_dimension.py --mode diagnostic \
  --seed 7 --panel stress --pretty
```

Machine-readable results:

- `experiments/results/E028-landscape-parity.json`
- `experiments/results/E028-landscape-parity-heritability-matched.json`
- `experiments/results/E028-latent-defect-matrix.json` (4 panels x 5 costs, 100 seeds per cell, **both landscapes**)
- `experiments/results/E028-latent-defect-heritability-matched.json` (stress panel, sensitivity arm)
- `experiments/results/E028-auroc-pooling-diagnostic-{stress,measured,independent,truth-blind}.json`
- `experiments/results/E028-audit-seed7-{stress-cost0.0,stress-cost1.0,measured-cost1.0}.json`

The simulators go through `exp` and `**`, whose last-place rounding is not
identical across CPUs and C libraries, so reproduction is exact **in value**
rather than bit-identical everywhere; the tests compare parsed values with
`math.isclose(rel_tol=1e-9)` and pin only committed files' own digests.

No network, no model API, no cost.

## Result 1 — the collapse is real, and it is confined to one cell

The paired matrix runs E027's own matrix once per landscape. Catastrophic seeds
out of 100, `original → latent`:

| Panel | Cost | Random | Fixed scalar | **Quality-Diversity** | Planner | Majority |
|---|---:|---:|---:|---:|---:|---:|
| Perfect | 0.0–1.0 | 0 → 0 | 25 → 46 | **0 → 0** | 100 → 100 | 44 → 43 |
| Independent | 0.0–1.0 | 0 → 0 | 27 → 48 | **0 → 0** | 100 → 100 | 44 → 43 |
| Measured | 0.0–0.75 | 0 → 0 | 36 → 42–44 | **0 → 0** | 99 → 100 | 44 → 43 |
| Measured | **1.0** | 12 → 94 | 37 → 60 | **0 → 3** | 99 → 100 | 44 → 52 |
| Stress | 0.0–0.5 | 0 → 0 | 37–38 → 40–44 | **0 → 0** | 100 → 100 | 43 → 42 |
| Stress | 0.75 | 0 → 30 | 33 → 43 | **0 → 0** | 100 → 100 | 43 → 42 |
| **Stress** | **1.0** | 94 → 100 | 51 → 91 | **0 → 62** | 100 → 100 | 43 → 72 |

The honest reading is narrower than "the archive stops being safe", and more
useful:

- **In 18 of the 20 cells the Quality-Diversity arm is still `0/100`.** Removing
  the free verifier changes nothing there at all.
- **Under E017/E020's *measured* panel at the assumption-free cost, it goes to
  `3/100`.** Post-change utility AUC moves `21.911 → 21.233`. That is a real
  degradation and it is small.
- **Under the *stress* panel at the assumption-free cost, it goes to `62/100`**
  and AUC falls `21.685 → 10.344`. That is the collapse.

So the free-verifier confound is load-bearing in exactly one place: where the
panel is deliberately pessimistic *and* the cost knob is at its extreme. The
stress panel is not a measured object — it is `accuracy 0.55, correlation 0.9,
blind spot 0.4`, chosen in E026 to be worse than anything observed. Everywhere
E027 could point to a measured panel, its conclusion survives the removal of
the confound.

**The scalar arm is uninformative in this comparison and should not be read.**
Its `25 → 46` shift appears even in the perfect-panel rows, where no defect can
exist, so it cannot be a defect effect. The cause is threshold proximity: E024's
catastrophe cutoff is an absolute AUC of `16.0` and the scalar arm's mean sits
at `16.10–16.23` on both landscapes. A shift of `0.12` AUC moves a large
fraction of seeds across a line they were already straddling. The cost-`0.0`
rows are the control that makes this visible, which is why they are run.

For every other arm the cost-`0.0` baselines are close enough to compare: QD
`22.061 → 21.880`, random `18.468 → 17.626`, planner `14.066 → 14.121`,
majority `18.576 → 18.678`. The landscapes are of comparable difficulty, so the
cost-`1.0` differences are attributable to the channel rather than to a change
in what is achievable.

## Result 2 — the mechanism, measured directly

The archive's protection was never a mystery once it could be measured. At the
stress panel and cost `1.0`, the fraction of *retained* artifacts that are
non-viable:

| Arm | Original | Latent |
|---|---:|---:|
| Random | 0.5678 | 0.5633 |
| Fixed scalar | 0.0066 | 0.4031 |
| **Quality-Diversity** | **0.0002** | **0.4500** |
| Planner | 0.0000 | 0.5100 |
| Majority | 0.0000 | 0.5300 |

On the original landscape the archive holds **essentially no defects at all** —
`0.0002` — while random search's retained population is 57% defective under the
identical panel. That gap is not verification: both arms saw the same panel. It
is the quality comparison acting as a second filter.

Remove the leak and QD's retained-defect rate goes to `0.4500`, statistically
indistinguishable from every other arm. **The archive's defect-filtering
advantage was entirely the landscape's doing.** This is the cleanest available
confirmation of what E027 could only infer from an AUROC.

Under the measured panel the same quantity moves only `0.0000 → 0.0259`, because
there the panel itself rejects most defects before selection ever sees them.

## Result 3 — what survives is the tail, not the typical run

Paired-seed wins for Quality-Diversity, `original → latent`:

| Cell | vs random | vs scalar | vs planner | vs majority |
|---|---:|---:|---:|---:|
| 18 unaffected cells | 100 → 100 | 100 → 100 | 100 → 100 | 51–52 → 50–51 |
| Measured, cost 1.0 | 100 → 97 | 100 → 97 | 100 → 98 | 51 → 56 |
| **Stress, cost 1.0** | **100 → 52** | **100 → 47** | **100 → 57** | **51 → 44** |

This is the result that must not be over-claimed. Across all 20 cells the
Quality-Diversity arm still has the **highest mean post-change utility AUC in
20 of 20 cells, and never more catastrophic seeds than any other arm** on the
latent landscape (strictly fewest in 3 cells, tied at the floor in the rest).
But in the stress/cost-`1.0` cell its *per-seed* dominance is gone: it beats
fixed-scalar search in 47 of 100 seeds and random search in 52 — a coin flip.

Both facts are true at once because the advantage has moved into the tail. QD's
mean is higher and its disasters are rarer, while its median run is no better
than the baselines'. Stated plainly: **once defects are invisible and the panel
is bad, retention no longer makes a typical run better — it only makes a
disaster less likely, and even that protection is partial at `62/100`.**

## Result 4 — where E027's AUROC actually came from

E027's `0.937` is measured over every candidate one seed ever accepted, pooled
across all 50 generations. Two quantities drift upward together over a run:
archive quality rises as search proceeds, and the accepted pool's viable
fraction rises as proposals come to be drawn from an accepted — and therefore
panel-enriched — archive. Pooling two quantities that both trend with generation
manufactures an association between them even when none exists at any fixed
generation. That mechanism had to be ruled out before `0.937` could be treated
as a landscape property.

`--mode diagnostic` replays the same Quality-Diversity arm — same seed
derivation, same two random streams, same order of operations — and reports the
pooled figure alongside one computed *within* each generation and weighted by
that generation's pair count. Seed 7, cost 1.0:

| Panel | Landscape | Pooled AUROC | Stratified by generation | Accepted viable / defect |
|---|---|---|---|---|
| Stress | original | 0.937387 | 0.885067 | 1189 / 168 |
| Stress | latent | 0.568493 | 0.549137 | 691 / 578 |
| Measured | original | 0.956102 | 0.948000 | 1830 / 39 |
| Measured | latent | 0.671950 | 0.679045 | 1630 / 86 |
| Independent | original | 0.995959 | 1.000000 | 2227 / 1 |
| Independent | latent | undefined | undefined | 2028 / 0 |
| **Truth-blind (accuracy 0.50)** | **original** | **0.922739** | **0.877137** | 1001 / 284 |
| **Truth-blind (accuracy 0.50)** | **latent** | **0.493807** | **0.459885** | 301 / 961 |

Two things follow.

**E027's caveat was real, not an artifact of pooling.** Conditioning on
generation moves the original landscape's separation from `0.937` only to
`0.885`. The overwhelming majority of it survives, so E027 was right to treat it
as the dominant confound on its own result.

**The latent landscape's residual is the panel's doing, not the landscape's.**
On fresh draws the latent landscape measures `0.500642` — chance, by
construction. Over a seed's accepted candidates it reads `0.549`. The
`truth-blind` row isolates which of the two possible causes is responsible. That
panel is 25 independent verifiers each at exactly chance, so its acceptance
carries no information about ground truth at all. Against it the original
landscape's separation is essentially unchanged (`0.877`) because it is a
property of the landscape, while the latent landscape's collapses to `0.460` —
chance. The residual is therefore created *endogenously*, by a panel that is
better than chance combined with heritable viability: viable lineages are
accepted slightly more often, so they generate more offspring, so they occupy
more of the high-quality niches.

That is worth stating on its own, because it is the uncomfortable half of the
result. **A quality–viability association cannot be fully designed away.** Any
panel that is better than chance will re-create a weak one through selection,
whatever the landscape looks like. It can be reduced from `0.885` to `0.549`,
which is enough to change the outcome completely — but not to zero.

The `truth-blind` panel is a diagnostic control only. It is not a plausible
panel, it is not swept in the matrix, and the command line rejects it outside
`--mode diagnostic`.

## Interpretation

- **E027's conclusion is more robust than its own caveat feared, and it fails
  exactly where the caveat said it might.** Removing the free verifier changes
  nothing in 18 of 20 cells, costs `3/100` under the panel measured on real
  verifiers, and costs `62/100` under a stress panel nobody has measured. The
  right correction to E027 is not "the survival result was wrong" — it is "the
  survival result holds wherever the panel is a measured object, and breaks at
  the pessimistic extreme."
- **The mechanism E027 inferred is now measured.** The archive's retained-defect
  rate under the stress panel goes from `0.0002` to `0.4500` once quality stops
  predicting viability. The archive was not filtering defects because it retains
  diversity; it was filtering them because the landscape let its quality
  comparison double as a verifier.
- **"Best arm" and "safe arm" are different claims, and only the first is
  general.** QD holds the highest mean AUC in all 20 cells on both landscapes,
  and never more catastrophic seeds than any other arm. It does *not* hold per-seed dominance in the worst
  cell, where it beats fixed-scalar search 47/100. An arm can be better on
  average, safer in the tail, and no better than a coin flip on the run you
  actually get.
- **A quality–viability association cannot be fully engineered away.** Result 4's
  truth-blind control shows the residual `0.549` on the latent landscape is
  created by the panel, not the landscape: any panel better than chance,
  combined with heritable viability, re-creates a weak association through
  selection. It can be reduced from `0.885` to `0.549` — enough to change the
  outcome completely — but not to zero.
- **What a practitioner should take from this** is that the protection retention
  buys against verifier error scales with how much their own quality signal
  already predicts correctness. No estimate of that quantity exists for any real
  software landscape, and producing one would be worth more than another
  synthetic sweep.

## Limitations

- Both landscapes are synthetic. Only the verifier-panel parameters are
  measured (E017/E020); the latent dimension is *constructed* to be
  uninformative, not observed to be.
- The latent landscape holds base viability rate and heritability near the
  original's measured values. No other moment of the original landscape is
  matched, and there is no claim that the two are otherwise comparable.
- The `0.5` AUROC is a property of fresh draws. The realised separation over a
  seed's accepted candidates is `0.549` under the stress panel and `0.679` under
  the measured panel, so the free-verifier effect is reduced, not eliminated.
- **The paired cells share a seed but not a proposal sequence.** A latent
  candidate consumes one extra random draw at creation and one more at each
  mutation. The first candidate's observable traits are therefore still
  identical — the latent draw comes after them — and every candidate from the
  second onward diverges, so from the same seed the two landscapes walk
  different points. The pairing is therefore by *configuration* —
  same panel, same cost, same seed range, same budget — and not by realised
  candidate stream. With 100 seeds per cell this affects the precision of a
  per-cell difference, not the direction of one this large; a genuinely
  seed-matched design would need the latent dimension drawn from its own
  generator, which would break the byte-level reproduction of E027's control
  column that this record relies on.
- The original column of the paired matrix is a live re-run of E027's matrix on
  the same synthetic model. It is a control against harness drift; it is **not**
  independent evidence for E027's conclusion.
- Catastrophe counts use E024's threshold of `0.64` of the post-change horizon,
  unchanged, so the two landscapes are scored identically. A different threshold
  would move the counts.
- Cells report means and counts over 100 seeds. No paired significance test
  across cells is computed.
- The defect cost remains a swept dial, not a measured quantity, exactly as in
  E027.

## Decision

- **E027's Result 2 is bounded, not retracted, and the bound is narrow.** Its
  `0/100` holds in 18 of 20 cells after the confound is removed, and degrades to
  `3/100` under the measured panel. It must be quoted with the stress-panel
  exception rather than as an unconditional claim.
- **Neither E024 nor E027 may be cited as evidence that retained diversity
  defeats verifier error.** E027 said this from the confound; E028 now says it
  from the measurement — under the stress panel the archive's retained-defect
  rate is `0.4500`, no better than any other arm.
- **The claim that is safe to carry forward** is that the constraint-guided
  archive has the highest mean post-change utility AUC and the fewest
  catastrophic seeds in every cell measured, on both landscapes. Per-seed
  dominance is *not* safe to carry forward into the stress/cost-`1.0` cell.
- **Correct the record on the scalar arm's catastrophe counts.** Its `25 → 46`
  shift is threshold proximity, not a landscape or defect effect, and the
  cost-`0.0` perfect-panel control proves it. Any future citation of a scalar
  catastrophe count from either landscape should carry that caveat, or report a
  threshold-free statistic instead.
- **Issue #22 stays open.** The plausible-goal oracle is still supplied rather
  than learned, the population sweep is still undone, and no arm has been run
  against a real task with hidden tests.
