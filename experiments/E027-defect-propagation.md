# E027 — What changes when an accepted defect finally costs something?

## Research question

[E026](E026-imperfect-verifier-panel.md) armed E024's benchmark with a measured
imperfect, correlated verifier panel and found that **nothing moved**. Sweeping
the panel to 45% wrong in both directions changed the Quality-Diversity arm's
post-change utility AUC by 1.5% and left its catastrophe count at 0/100.

E026 also diagnosed why, and the diagnosis was measured rather than guessed. On
seed 7 under the stress panel, 157 non-viable candidates were accepted by the
panel and none survived in the final 64-niche archive. The reason is structural:
`utility()` and `robust_quality()` both consult `viable()` directly and return
`0.0` for a non-viable candidate, so a falsely accepted artifact scores zero,
never displaces an incumbent, and is discarded by the very predicate the
verifier was meant to enforce. E026's conclusion was that **E024 has no
defect-propagation channel**, that its falsification test therefore had very
little power, and that E024 must not be cited as evidence about verification
until an accepted defect carries a cost.

E027 supplies that cost and asks the question E026 could not:

> Once an accepted defect can persist and do harm, does the Quality-Diversity
> advantage over the majority-vote swarm survive an imperfect correlated panel,
> and do its catastrophic seeds stay at 0/100?

## The gap, stated precisely

Both E024 and E026 give every search arm a **free viability oracle**. The
verifier panel decides whether an artifact is accepted, and then the selection
rule immediately re-decides the same question for free, correctly, by calling
`viable()`. A verifier that can be overruled by a free oracle sitting behind it
is not load-bearing, which is exactly why moving the panel moved nothing.

Two clarifications to E026's account, both of which E027's audit measures:

- Defects **did** already reach the archive under E024/E026. `_qd_search`
  accepts unconditionally when a niche is empty, so on seed 7 under the stress
  panel 23 non-viable artifacts occupied a niche at some point, and up to 12
  were held simultaneously. They were simply worth `0.0`, so the first viable
  candidate in the niche evicted them and none was ever shipped. E026's "not one
  survived" is correct about the *final* archive; "never enters" would not be.
- A false *reject* really is cheap: one lost draw from a 2,500-draw budget with
  heavy redundancy. E027 does not change that side.

## The mechanism, and why this one

**Selection, retention and delivery rank by apparent quality; the trace scores
by ground truth.**

Apparent quality is what a system can actually observe once its panel has
accepted an artifact:

```text
apparent_utility(c, goal)        = utility(c, goal)        if viable(c)
                                 = cost * unchecked_utility(c, goal)        otherwise
apparent_robust_quality(c)       = robust_quality(c)       if viable(c)
                                 = cost * unchecked_robust_quality(c)       otherwise
```

Every arm's selection rule switches to the apparent score — the scalar arm's
elite ranking, the QD archive's niche comparison, the planner's incumbent test,
the swarm's per-agent vote — and every arm's per-generation trace value becomes
"pick the artifact that looks best, then score *that* artifact honestly" rather
than "take the true maximum". A falsely accepted defect can therefore evict a
real solution, occupy an archive niche, be drawn as a parent, and deliver `0.0`
in the generation it ships.

Composing several of the mechanisms the design space offers was considered and
rejected in favour of this one:

- **Contaminated archive niche** — included, and it is a direct consequence: a
  defect that wins its niche keeps a real solution out of it.
- **Parent contamination** — included, and also a consequence: the QD arm draws
  parents from the archive, so a defect in the archive breeds.
- **Integration debt taxing the whole population** — rejected. It would be a
  second modelling assumption on top of the first, and it is gated on the same
  event (a defect winning selection), so it could only scale an effect this
  channel already produces.
- **Latent defects surfacing generations later and retroactively degrading the
  trace** — rejected as a separate mechanism, because the cost knob already
  parameterises latency in a simpler way: `cost` *is* how far a defect stays
  latent past the acceptance gate.

The mechanism removes an assumption rather than adding one, which is what makes
its extreme setting the natural default.

## Why the knob is not a free parameter

`--defect-cost` is a single declared knob in `[0.0, 1.0]`, and both ends are
pinned by something other than convenience:

| Setting | Meaning | Status |
| --- | --- | --- |
| `0.0` | the search operator holds a free viability oracle and throws a falsely accepted artifact away for nothing | **exactly** the E024/E026 behaviour; a regression test asserts run-for-run equality with the channel off |
| `1.0` | no free oracle anywhere; the system trusts its verifier panel completely | the only setting that adds **no** assumption, which is why it is the default |

Every value strictly between the two hands the search operator ground-truth
viability information that no real system has. The knob is therefore a dial back
toward E024's optimistic assumption, not a dial tuned to manufacture an effect,
and the whole range is swept and reported below rather than one column being
quoted.

The channel is **off** by default. `--defect-cost` is rejected without
`--defect-channel`, exactly as the panel flags are rejected without
`--imperfect-panel`.

## Matched budget

Unchanged, and asserted. The channel only re-ranks what verification has already
produced; it consumes no random numbers of its own and creates no proposals. All
five arms still spend exactly 2,500 proposals and 2,500 panel decisions per
seed, `run_seed` still fails closed if any arm diverges, and a 25-verifier panel
still costs `2,500 * 25 = 62,500` verifier votes identically for every arm.
`tests/test_e027_defect_propagation.py` pins this at every cost in the sweep and
under all three panels.

## Reproduction

The committed E024 reference is untouched and still reproduces from the command
it always did, with the channel off and the panel perfect:

```bash
python sim/matched_budget_emergence.py \
  --seeds 100 --seed-start 0 --agents 50 --generations 50 \
  --change-at 25 --bins 8 --pretty
```

`sha256 c261193d2282a8822fc2a3ae1934a7ad1494803930af27b9601e02fedbe17b8a`,
byte-identical on the machine that produced it. The simulators go through `exp`
and `**`, whose last-place rounding is not identical across CPUs and C
libraries, so reproduction is exact **in value** rather than bit-identical
everywhere; the tests compare parsed values with `math.isclose(rel_tol=1e-9)`
and pin only the committed file's own digest.

The headline E027 sweep — measured panel, channel armed at the default cost:

```bash
python sim/matched_budget_emergence.py \
  --seeds 100 --seed-start 0 --agents 50 --generations 50 \
  --change-at 25 --bins 8 --imperfect-panel --defect-channel --pretty
```

The panel-by-cost sensitivity matrix, and the mechanism audit behind Results 3
and 4:

```bash
PYTHONPATH=. python sim/e027_defect_propagation.py --mode matrix --seeds 100 --pretty
PYTHONPATH=. python sim/e027_defect_propagation.py --mode audit --seed 7 --panel stress --pretty
```

Machine-readable results:

- `experiments/results/E027-defect-channel-100-seed-summary.json`
- `experiments/results/E027-defect-cost-sensitivity.json` (4 panels x 5 costs, 100 seeds each)
- `experiments/results/E027-defect-cost-threshold.json` (stress panel, fine grid near the top of the range)

```bash
PYTHONPATH=. python sim/e027_defect_propagation.py --mode matrix --seeds 100 \
  --panels stress --costs 0.80,0.85,0.90,0.95 --pretty
```

Wall time on one laptop core: **65 s** for the headline sweep, **31 min** for the
full matrix. No network, no model API, no cost.

## Result 1 — the channel has teeth, and random search is what it kills

This is the first thing that must be established, because without it a survival
anywhere else is indistinguishable from another null.

Stress panel (accuracy 0.55, `icc` 0.9, `lambda` 0.4), 100 seeds, cost `0.0`
versus cost `1.0`:

| Strategy | AUC at cost 0 | AUC at cost 1 | Δ | Catastrophes at cost 0 | Catastrophes at cost 1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Random** | **17.687** | **13.962** | **-3.725** | **0/100** | **94/100** |
| Fixed scalar | 16.118 | 15.956 | -0.162 | 37/100 | 51/100 |
| Centralized planner | 14.155 | 14.088 | -0.067 | 100/100 | 100/100 |
| Majority-vote swarm | 18.724 | 18.701 | -0.023 | 43/100 | 43/100 |
| Quality-Diversity | 21.715 | 21.685 | -0.030 | 0/100 | 0/100 |

Random search goes from never failing catastrophically to failing in 94 of 100
seeds. It ships a defect in 20.8% of generations. That is the channel working:
verifier error now reaches the outcome metric, hard.

**This contradicts a reading of the published E024 record.** E024 reports random
search as the second-best arm on mean utility AUC with `0/100` catastrophic
seeds, and E026 left that untouched. It is an artifact of the free oracle.
Random search retains nothing, so every generation it must ship whichever
accepted artifact looks best, and under a bad panel that is often a defect. Its
apparent robustness in E024 came from being handed the true maximum for free.
The same effect, smaller, moves fixed-scalar evolution from 37 to 51
catastrophic seeds.

## Result 2 — the Quality-Diversity result survives, and the ordering does not move

> **Bounded by E028, and the bound is narrow.**
> [`E028-latent-defect-dimension.md`](E028-latent-defect-dimension.md) built the
> landscape this record's Decision section asked for — one in which apparent
> quality carries no information about viability — and re-ran the full 20-cell
> matrix on it against a live re-run of this one. The result is **not** that the
> `0/100` below was an artifact. The Quality-Diversity arm stays at `0/100` in
> **18 of the 20 cells**; it moves to `3/100` under the measured panel below at
> cost `1.0`; and it reaches `62/100` only under E026's *stress* panel at cost
> `1.0` (`53/100` in the heritability-matched sensitivity arm). The stress panel
> is a deliberately pessimistic construct, not a measured one. So the survival
> claim holds wherever the panel is a measured object and breaks at the
> pessimistic extreme — quote it with that exception rather than
> unconditionally.

Headline sweep: E017/E020 measured panel, channel armed at cost `1.0`, 100
seeds, against E026's same-panel run (which is this record's cost-`0.0` column).

| Strategy | E026 AUC (cost 0) | E027 AUC (cost 1), 95% CI | Δ | Catastrophes |
| --- | ---: | ---: | ---: | ---: |
| Random | 18.252631 | 17.148883 (16.979454–17.318311) | -1.103748 | 0/100 → **12/100** |
| Fixed scalar | 16.196394 | 16.174804 (16.078416–16.271192) | -0.021590 | 36/100 → 37/100 |
| Centralized planner | 14.133411 | 14.132179 (14.028935–14.235422) | -0.001232 | 99/100 → 99/100 |
| Majority-vote swarm | 18.622517 | 18.621898 (17.844867–19.398929) | -0.000619 | 44/100 → 44/100 |
| **Quality-Diversity** | **21.902828** | **21.910788 (21.850744–21.970833)** | **+0.007960** | **0/100 → 0/100** |

The QD arm's change is `+0.008` on a mean of `21.9` with a CI half-width of
`0.06`: unchanged within noise, and the sign is not interpretable. Paired-seed
wins for Quality-Diversity are identical to both earlier records — 100/100
against random, scalar and the planner, and **51/100** against the majority-vote
swarm — and QD's standard deviation stays `0.31` against the swarm's `3.96`.

So the answers to the three questions asked of this experiment are:

- **Does the QD advantage survive an imperfect correlated panel once defects
  carry a cost?** Yes, in all twenty panel-by-cost cells, and it *widens*
  against random search rather than narrowing.
- **Do QD's catastrophic seeds stay at 0/100?** Yes, in every one of the twenty
  cells.
- **Does the answer vary with the knob, and does zero reproduce E026?** Zero
  reproduces E026 exactly, by construction and by test. The variation is real
  but concentrated in the top quarter of the range — see Result 3.

## Result 3 — the response is real but strongly convex in the knob

Post-change utility AUC (top line) and catastrophic seeds out of 100 (bottom
line), 100 seeds per cell.

| Panel | Cost | Random | Fixed scalar | Planner | Swarm | Quality-Diversity | QD > swarm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Perfect | 0.00–1.00 | 18.468 · 0 | 16.230 · 25 | 14.066 · 100 | 18.576 · 44 | 22.061 · 0 | 51/100 |
| Independent (`icc` 0, `lambda` 0) | 0.00–1.00 | 18.468 · 0 | 16.219 · 27 | 14.071 · 100 | 18.576 · 44 | 22.059 · 0 | 51/100 |
| Measured | 0.00 | 18.253 · 0 | 16.196 · 36 | 14.133 · 99 | 18.623 · 44 | 21.903 · 0 | 51/100 |
| Measured | 0.25 | 18.253 · 0 | 16.200 · 36 | 14.133 · 99 | 18.623 · 44 | 21.909 · 0 | 51/100 |
| Measured | 0.50 | 18.253 · 0 | 16.200 · 36 | 14.133 · 99 | 18.623 · 44 | 21.909 · 0 | 51/100 |
| Measured | 0.75 | 18.253 · 0 | 16.200 · 36 | 14.133 · 99 | 18.623 · 44 | 21.908 · 0 | 51/100 |
| **Measured** | **1.00** | **17.149 · 12** | 16.175 · 37 | 14.132 · 99 | 18.622 · 44 | **21.911 · 0** | 51/100 |
| Stress | 0.00 | 17.687 · 0 | 16.118 · 37 | 14.155 · 100 | 18.724 · 43 | 21.715 · 0 | 52/100 |
| Stress | 0.25 | 17.687 · 0 | 16.130 · 38 | 14.155 · 100 | 18.724 · 43 | 21.717 · 0 | 52/100 |
| Stress | 0.50 | 17.687 · 0 | 16.123 · 38 | 14.155 · 100 | 18.724 · 43 | 21.717 · 0 | 52/100 |
| Stress | 0.75 | 17.673 · 0 | 16.130 · 33 | 14.155 · 100 | 18.724 · 43 | 21.717 · 0 | 52/100 |
| **Stress** | **1.00** | **13.962 · 94** | **15.956 · 51** | 14.088 · 100 | 18.701 · 43 | **21.685 · 0** | 51/100 |

Three things to read off it.

**The cost-`0.0` column is E026, to the digit.** Every measured-panel and
stress-panel value at cost `0.0` equals E026's Result 3 table exactly, including
QD `21.903`/`21.715`, swarm `18.623`/`18.724`, `51`/`52` paired wins and `0/100`
QD catastrophes. A test asserts this against the committed E026 artifact with
`math.isclose(rel_tol=1e-9)`. The knob's zero end is anchored to a published
result, not to a claim.

**The perfect-panel rows cannot move**, at any cost, and they do not. A panel
that never accepts a non-viable artifact never creates a defect to propagate.
This is the null control the matrix needs.

**Almost all of the response lives above `0.75`.** A finer grid on the stress
panel, `experiments/results/E027-defect-cost-threshold.json`, shows this is a
sharply rising curve rather than a step:

| Stress panel, cost | 0.75 | 0.80 | 0.85 | 0.90 | 0.95 | 1.00 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Random AUC | 17.673 | 17.611 | 17.397 | 16.809 | 15.630 | 13.962 |
| Random catastrophes | 0/100 | 0/100 | 0/100 | **13/100** | **57/100** | **94/100** |
| Random generations shipping a defect | 0.06% | 0.34% | 1.30% | 4.56% | 11.14% | 20.80% |
| Fixed-scalar catastrophes | 33/100 | 39/100 | 38/100 | 39/100 | 41/100 | 51/100 |
| **QD catastrophes** | **0/100** | **0/100** | **0/100** | **0/100** | **0/100** | **0/100** |

The convexity is a measured property of this landscape, explained in Result 4: a
non-viable candidate's apparent quality is structurally capped below what viable
candidates reach, so a defect discounted by even 15% loses almost every
comparison it enters. The knob is honest, but its lower half carries no
information, and the finding is therefore a statement about the top of the range
rather than about a uniform response.

## Result 4 — what protects the archive is not verification

The mechanism is auditable rather than inferred. `--mode audit` replays the QD
arm with the same strategy-seed derivation, the same two random streams and the
same budget the benchmark uses, and counts what happened. Seed 7:

| Panel | Cost | Accepted defects | Reached a niche | Evicted a viable incumbent | Peak held | In final archive | Generations shipping a defect |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Perfect | 0.0 / 1.0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Measured | 0.0 | 49 | 6 | 0 | 4 | 0 | 0 |
| Measured | 1.0 | 39 | 5 | 0 | 5 | 0 | 1 |
| Stress | 0.0 | 157 | 23 | 0 | 12 | 0 | 0 |
| Stress | 1.0 | 168 | 32 | **5** | **16** | 0 | **2** |

(Accept counts differ between costs because the channel changes what the archive
holds, hence which parents are drawn, hence which candidates are proposed. The
trajectory diverges; the budget does not.)

The channel demonstrably does what it was built to do — with the cost armed,
defects evict real solutions and get shipped, and neither happens with it
disarmed — and yet 64 niches are still enough that the arm's utility trace barely
notices.

The audit also measures the reason, and it is not the one a reader would guess:

```text
AUROC of apparent robust quality as a viability classifier,
over this seed's accepted candidates:   0.937387  (stress panel,   cost 1.0)
                                        0.956102  (measured panel, cost 1.0)
```

This figure carries the experiment's central caveat, so it is committed rather
than left to be re-derived. All six audit runs behind the table above are in
`experiments/results/E027-audit-seed7-<panel>-cost<cost>.json`, each recording
its own `selection_as_free_verifier` block with the accepted-viable and
accepted-defect counts the AUROC was computed over.

**In this landscape the archive's own quality comparison is already a verifier.**
Apparent quality — computed with no access to `viable()` at all — separates
viable from non-viable accepted candidates at AUROC ~0.94. A non-viable
candidate must leave reliability and security below `0.25` and cannot spend that
budget usefully enough elsewhere to catch a good incumbent, so elitist selection
filters what the panel let through, for free. That is why QD is immune, why the
response is so convex in the knob, and why random search — which has no incumbents to compare
against, only a fresh batch — is the arm that dies.

## Interpretation

- **The gap E026 identified is closed.** An accepted defect can now persist,
  evict a real solution, breed, and deliver nothing. The channel changes
  outcomes by up to 3.7 AUC and 94 catastrophic seeds, so this is no longer a
  test without power.
- **E024's Quality-Diversity reliability claim survives it**, in all twenty
  panel-by-cost cells, with catastrophic seeds at 0/100 throughout and the
  51/100 paired split against the majority-vote swarm unchanged. This is a
  genuine robustness result and it is stronger than E026's null, because the
  instrument is now demonstrably sharp.
- **It is not, however, evidence that retained diversity defeats verifier
  error.** Result 4 shows the archive is protected mainly by a property of the
  landscape: apparent quality is itself a ~0.94-AUROC viability classifier, so
  selection acts as a second, free verifier. In a landscape where defects look
  *as good as* or *better than* healthy artifacts — which is the interesting
  real case, and the reason a verifier exists at all — this result gives no
  cover. State the claim as "QD survived a defect channel on a landscape whose
  quality signal is itself informative about viability", not as "QD is robust to
  accepted defects".
- **The E024 record's treatment of random search does not survive.** Random
  search is reported there as a strong, never-catastrophic baseline. With the
  free oracle removed it fails in 94 of 100 seeds under a bad panel. An arm that
  retains nothing has to ship whatever currently looks best, and that is exactly
  what an imperfect verifier corrupts. This is the clearest positive result in
  E027: **retention is what converts a bad verifier from fatal into survivable**,
  and it is visible as an ordering (QD ≈ swarm ≈ planner ≫ scalar ≫ random in
  sensitivity to the channel), not merely as a level.
- The convexity of the response should keep expectations modest. The lower half
  of the sweep is flat because a discounted defect cannot win a comparison in
  this landscape, not because the mechanism is inert — the fine grid on the
  stress panel resolves 0, 0, 0, 13, 57 and 94 catastrophic random-search seeds
  at costs 0.80, 0.85, 0.90, 0.95 and 1.00.

## Limitations

- The defect channel is a **synthetic mechanism**, and unlike the verifier panel
  none of it is measured. No defect cost was observed anywhere; the knob is
  swept, not fitted.
- A latent defect costs exactly the ground-truth utility of the artifact
  carrying it. Rework, blast radius, remediation effort, and defects that damage
  artifacts other than their own are not modelled.
- Defect propagation is instantaneous within a generation. There is no latency
  before a defect surfaces and no retroactive correction of an earlier trace
  point; `cost` stands in for latency in a much cruder way.
- **The knob's lower half is uninformative in this landscape.** Nothing moves
  below cost `0.75`, and the whole response is compressed into the top quarter
  of the range. The finer grid shows a curve rather than a step, but a reader
  should still treat the result as "at and near the assumption-free extreme",
  not "uniformly across the range".
- **The AUROC ~0.94 separation is the dominant confound.** It was measured, not
  assumed, and it means this benchmark cannot distinguish "diversity protects
  against accepted defects" from "this landscape's quality signal already
  detects defects". A landscape where defective and healthy artifacts are
  indistinguishable on observable traits is the experiment that would separate
  them, and it does not exist yet.
- The channel is deliberately **not neutral across arms**: a single-artifact arm
  ships a defect for a whole generation while an archive can route around a
  contaminated niche. That asymmetry is the mechanism under test, not a bias to
  correct — but it does mean the arms are not exchangeable under it.
- The channel changes what each arm retains, so the arms explore different
  regions than they did with it disarmed. Differences against E024 or E026 are
  the combined effect of contamination and of the altered search trajectory,
  which this benchmark does not separate.
- Everything E026 lists about the panel still holds: its parameters describe
  E017's 25 partial oracles, `lambda` rests on 4 of 72 tasks (Clopper-Pearson
  95%: 0.015–0.136), E017's oracles erred one-sidedly while this simulator's
  panel errs in both directions, and the quorum is left at majority.
- Everything E024 lists still holds: 50 agents rather than 100–10,000, a
  supplied rather than learned Goal Graph, and no measurement of novelty,
  information gain, churn, human attention, or adversarial contributors.

## Decision

Record the defect channel, the headline sweep, the panel-by-cost matrix and the
threshold grid as committed artifacts. Keep the channel **off** by default, so
the published E024 and E026 references stay reproducible from their own
documented commands — both were re-verified byte-identical after this change.

**E024 may now be cited as surviving a defect-propagation channel**, which E026
explicitly forbade. It may **not** be cited as evidence that retained diversity
defeats verifier error, because Result 4 shows a cheaper explanation that this
benchmark cannot rule out.

**Correct the record on random search.** E024's report of random search as a
never-catastrophic baseline depends on the free viability oracle. Any future
citation of that arm should carry E027's number instead: 94/100 catastrophic
seeds under a stress panel once accepted defects cost something.

The strongest next step is no longer a defect channel — it is a landscape whose
apparent-quality signal is *uninformative* about viability, so that verification
is the only thing standing between an accepted defect and the outcome. Until
that exists, E027's survival result is bounded by an AUROC of 0.94 and should be
quoted with it.

> **That step was taken.** [E028](E028-latent-defect-dimension.md) moved
> ground-truth viability into a dimension no goal weights, no descriptor reads
> and the trait budget does not constrain, holding the base viability rate and
> the heritability of viability at this landscape's measured values so only the
> informativeness changed — AUROC `0.784979` to `0.500642` over fresh draws.
> The survival result **mostly** carries over: `0/100` in 18 of 20 cells,
> `3/100` under the measured panel at cost `1.0`, and `62/100` only under the
> unmeasured stress panel at that cost. The comparative claim carries over on
> means and tails — Quality-Diversity holds the highest mean post-change AUC in
> `20/20` cells and never more catastrophes than any other arm — but **not** per
> seed: in the
> stress/cost-`1.0` cell its paired-seed win rate against the other arms falls
> to `44`–`57` of 100. E028 also measured the mechanism this record could only
> infer: the archive's retained-defect rate in that cell goes `0.0002` to
> `0.4500`, so the filtering advantage really was the landscape's doing. And it
> checked whether this record's `0.937` was itself an artifact of pooling across
> generations, and found it was not — conditioning on generation moves it only
> to `0.885`, so the caveat above was correctly stated.
