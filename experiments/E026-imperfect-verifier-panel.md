# E026 — Does the E024 emergence result survive verifiers that are wrong together?

## Research question

E024 compared five search strategies under a matched proposal and
verification-attempt budget and concluded that the Quality-Diversity archive's
surviving advantage is **reliability** — it never fails catastrophically, where
the majority-vote swarm fails in 44 of 100 seeds.

That conclusion was reached with a **perfect** verification panel. In the
committed 100-seed reference, `false_accept_rate`, `false_reject_rate` and
`panel_disagreement_rate` are exactly `0.0` for all five arms in all 100 seeds:
the fields exist in the schema but are structurally always zero.

Issue #22 requires "independent verifiers with controllable error correlation".
E026 supplies them and asks the falsification question directly: **does the
Quality-Diversity result survive a panel whose members are wrong together?**

## Why the panel has this shape and not a convenient one

The panel is not invented. Every parameter is measured in this repository, on
25 partial test oracles run over 72 candidates whose ground truth is decided by
executing hidden tests.

| Parameter | Value | Source |
| --- | ---: | --- |
| Verifiers | 25 | [E017](E017-item-difficulty-and-quorum.md) |
| Marginal per-verifier accuracy | 0.7956 | E017 §1 |
| Marginal pairwise error correlation | +0.5873 | E017 §2 |
| Dependence shape | beta-binomial over per-item difficulty | E017 §5 |
| Blind-spot floor `lambda` | 0.0556 (4 of 72) | [E020](E020-quorum-frontier-under-measured-shape.md) §3 |
| Reducible-unit correlation `icc` | 0.4513 | E020 moment fit |
| Quorum | 0.5 (majority) | E024's existing default |

Three constraints from prior results decide the shape:

**`rho` is not a sufficient statistic.** E017 fed its own measured `rho` back
into the shared-shock mixture that E012/E013/E015 assume and found it
under-predicts real panel error by 1.71x, because real panels fail *partially* —
11 of ~15 observed failures had a majority wrong while a minority was right, an
outcome shared-shock assigns essentially zero probability. The panel therefore
uses the item-difficulty (beta-binomial) shape, which reproduces the partial
failures at the same parameter count. Shared-shock remains available behind
`--verifier-dependence shared-shock` and is reported below as a control.

**Panel error has an irreducible floor.** E020 measured `lambda = 4/72` defects
that *every one* of the 25 verifiers missed. Shared-shock puts that floor 2.13x
too high; the plain beta-binomial has no floor at all and lands 1.77x too low,
promising an improvement that never arrives. The panel therefore carries an
explicit blind-spot atom: with probability `lambda` every verifier is wrong
together, whatever the panel size and whatever the quorum. That is E020's
one-inflated model.

**The correlation is decomposed, not double-counted.** E017's headline
`rho = +0.5873` is the *marginal* correlation of the whole panel — blind-spot
units are included in it, and they contribute perfectly correlated errors. Once
the blind spot is represented explicitly as its own atom, the correlation left
in the reducible units is E020's `icc = 0.4513`. Feeding 0.5873 as the base
correlation *and* arming the atom would count the same shared failures twice, so
the default is the decomposed pair `(0.4513, 0.0556)` whose implied marginal
correlation is E017's measurement. `--verifier-correlation` overrides it.

`accuracy` stays the *marginal* per-verifier accuracy over all units, so
`reducible_accuracy(0.7956, 0.0556) = 0.8424`, i.e. a reducible error of
`0.1576` — exactly the reducible-only mean E020 fits directly from the votes.
A regression test pins that identity.

## Matched budget under a 25-verifier panel

The budget contract is unchanged: one candidate proposal plus **one panel
decision**, 2,500 per strategy per seed, no acceptance retries, no unverified
bootstrap anchor. `run_seed` still fails closed if any arm's attempt count
diverges.

A panel of 25 costs 25 verifier votes per decision, identically for every arm,
so `budget_contract.verifier_votes_per_strategy` is `2,500 * 25 = 62,500` for
all five. Enlarging the panel cannot buy one arm more evidence than another.

## Reproduction

The perfect-panel default is unchanged, and the committed E024 reference still
reproduces from the same command it always did (byte-for-byte on the platform
that generated it; the simulation goes through `exp` and `**`, whose last-place
rounding is not identical across CPUs and C libraries, so treat reproduction as
exact in value rather than bit-identical everywhere):

```bash
python sim/matched_budget_emergence.py \
  --seeds 100 --seed-start 0 --agents 50 --generations 50 \
  --change-at 25 --bins 8 --pretty
```

The imperfect panel is opt-in:

```bash
python sim/matched_budget_emergence.py \
  --seeds 100 --seed-start 0 --agents 50 --generations 50 \
  --change-at 25 --bins 8 --imperfect-panel --pretty
```

Machine-readable result:
`experiments/results/E024-imperfect-panel-100-seed-summary.json`

The archive-contamination audit behind Result 3 is
`sim/e026_archive_contamination.py`.
(the artifact keeps the `E024-` prefix because it is the E024 benchmark run with
a different panel, and its `experiment_id` field is `E024`).

Wall time on one laptop core, 100 seeds x 5 arms x 2,500 evaluations:
**25.6 s** perfect, **29.4 s** imperfect. No network, no model API, no cost.

## Result 1 — the error fields are now real

| Strategy | False accept | False reject | Panel disagreement | Accepts (of 2,500) |
| --- | ---: | ---: | ---: | ---: |
| Random | 0.1718 | 0.1700 | 0.4667 | 1086.65 |
| Fixed scalar | 0.1655 | 0.1722 | 0.4696 | 2022.11 |
| Centralized planner | 0.1620 | 0.1731 | 0.4669 | 2033.07 |
| Majority-vote swarm | 0.1644 | 0.1714 | 0.4678 | 2047.99 |
| Quality-Diversity | 0.1725 | 0.1717 | 0.4680 | 1862.19 |

About one panel decision in six is wrong, and the panel is internally split on
nearly half of them. Every arm sees the same panel, as the matched budget
requires.

## Result 2 — the Quality-Diversity ordering does not move

| Strategy | Perfect AUC | Imperfect AUC (95% CI) | Δ | Imperfect stdev | Imperfect min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Random | 18.467677 | 18.252631 (18.201198–18.304064) | -0.215046 | 0.262412 | 17.494747 |
| Fixed scalar | 16.229700 | 16.196394 (16.095046–16.297743) | -0.033306 | 0.517084 | 15.035862 |
| Centralized planner | 14.065917 | 14.133411 (14.030302–14.236521) | +0.067494 | 0.526067 | 12.720141 |
| Majority-vote swarm | 18.576406 | 18.622517 (17.845458–19.399577) | +0.046111 | 3.964589 | 13.159268 |
| Quality-Diversity | 22.061411 | 21.902828 (21.839912–21.965743) | -0.158583 | 0.320995 | 21.040210 |

Paired-seed wins for Quality-Diversity on post-change utility AUC are
**identical** to the perfect-panel run: 100/100 against random, scalar and the
planner, and 51/100 against the majority-vote swarm.

Catastrophic seeds (post-change utility AUC below 16 of a 25-generation
horizon — the same threshold the E024 record used):

| Strategy | Perfect | Imperfect |
| --- | ---: | ---: |
| Random | 0/100 | 0/100 |
| Fixed scalar | 25/100 | 36/100 |
| Centralized planner | 100/100 | 99/100 |
| Majority-vote swarm | 44/100 | 44/100 |
| **Quality-Diversity** | **0/100** | **0/100** |

E024's reliability claim therefore survives verbatim: the archive still never
fails catastrophically where the swarm fails in 44 of 100 seeds, and the
imperfect panel changes the QD arm's mean utility AUC by 0.7%.

## Result 3 — and that is mostly a finding about the benchmark, not about QD

The honest reading of Result 2 is not "Quality-Diversity is robust to correlated
verifier error". It is that **E024's landscape barely transmits verifier error
into its outcome metrics at all**, so the falsification test it supports is much
weaker than the headline suggests.

Sweeping the panel from perfect to deliberately absurd, 100 seeds each:

| Panel | FA | FR | Disagree | QD AUC | Swarm AUC | QD>swarm | QD catastrophes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Perfect | 0.0000 | 0.0000 | 0.0000 | 22.061 | 18.576 | 51/100 | 0/100 |
| 25 independent (`icc` 0, `lambda` 0) | 0.0004 | 0.0004 | 0.9969 | 22.059 | 18.576 | 51/100 | 0/100 |
| Shared-shock at `rho` 0.5873 (rejected shape) | 0.1204 | 0.1202 | 0.4107 | 22.006 | 18.665 | 51/100 | 0/100 |
| **E017/E020 measured** | **0.1725** | **0.1717** | **0.4680** | **21.903** | **18.623** | **51/100** | **0/100** |
| `icc` 0.9, `lambda` 0.0556 | 0.2046 | 0.2038 | 0.0924 | 21.954 | 18.644 | 51/100 | 0/100 |
| Stress: accuracy 0.55, `icc` 0.9, `lambda` 0.4 | 0.4511 | 0.4499 | 0.0334 | 21.715 | 18.724 | 52/100 | 0/100 |

At a panel that is wrong **45% of the time in both directions**, the QD arm's
utility AUC falls by 1.5% and its catastrophe count stays at zero. No setting of
the panel changes any conclusion E024 drew.

The mechanism is measured, not inferred, and the measurement has a reproduction
command. `sim/e026_archive_contamination.py` replays the Quality-Diversity arm
with the same strategy-seed derivation and the same two random streams the
benchmark uses, then counts what the panel waved through and what survived:

```bash
python sim/e026_archive_contamination.py --seed 7 --panel stress --pretty
```

On seed 7:

```text
perfect panel : 2228 accepts,   0 accepted-but-non-viable, 0 non-viable in the final 64-niche archive
measured panel: 1899 accepts,  49 accepted-but-non-viable, 0 non-viable in the final 64-niche archive
stress panel  : 1375 accepts, 157 accepted-but-non-viable, 0 non-viable in the final 64-niche archive
```

157 defective artifacts were waved through by the panel and **not one survived**.
The reason is structural: in this landscape `utility()` and `robust_quality()`
both return `0.0` for any non-viable candidate, so a falsely accepted artifact
scores zero, never displaces an archive incumbent, a scalar elite, a plan or a
consensus, and is silently discarded by the very predicate the verifier was
supposed to enforce. A false *reject* is merely one lost draw from a
2,500-draw budget with heavy redundancy.

**E024 has no defect-propagation channel.** Its own limitations list already
names "post-integration defects" as out of scope; E026 shows that this omission
is not a minor caveat but the thing that decides the experiment's answer.

> **Closed by E027.** [`E027-defect-propagation.md`](E027-defect-propagation.md)
> supplies the missing channel and re-runs this comparison through it. Two
> corrections to the reading above follow from it. First, the mechanism was
> slightly narrower than stated: defects *did* already drop into empty archive
> niches under E026, because an empty niche accepts unconditionally — they were
> simply worth `0.0`, so they never displaced anything and never shipped.
> Second, the channel is not what carries the whole story. Once the free
> viability oracle is removed, apparent quality alone still separates viable
> from non-viable candidates at AUROC ~0.94 among accepted candidates, so the
> archive's own quality comparison is a second verifier. E026's `0` in the
> "non-viable in the final archive" column is reproduced by E027's cost-`0.0`
> column exactly, which is how E027's knob is anchored.

One secondary result is worth recording. The shared-shock row above reports a
false-accept rate of 0.1204 where the measured shape gives 0.1725 — the rejected
model understates panel error by **1.43x** at the same nominal correlation,
reproducing E017's 1.71x finding inside a second, independent benchmark.

## Interpretation

- The Quality-Diversity reliability claim from E024 is **not falsified** by an
  imperfect, correlated panel with a measured blind-spot floor.
- That non-falsification is **weak evidence**, and it should not be quoted as
  "QD survives bad verifiers". The correct statement is: *on this landscape,
  outcome quality is almost independent of verification quality, so the test
  had little power to falsify anything.*
- The strongest next step is no longer a better search arm. It is a landscape
  where an accepted-but-defective artifact carries a cost — integration debt, a
  contaminated archive niche, or a downstream failure — so that verifier error
  can reach the outcome metric at all. Until then, E024's benchmark should not be
  cited as evidence about verification.
  **[E027](E027-defect-propagation.md) took that step**: an accepted defect now
  competes on its observable merits, can evict a real solution, and delivers
  nothing when it ships. The channel changes outcomes — random search collapses
  — and the Quality-Diversity reliability result survives it.
- The correlation and blind-spot machinery itself behaves as the prior results
  predict: 25 *independent* verifiers drive panel error to 0.0004 while the same
  25 at the measured correlation leave it at 0.17, and no panel size escapes the
  blind spot.

## Limitations

- Candidates, objectives, goal changes, and verifier outcomes are all synthetic;
  only the panel's *parameters* are measured.
- The panel parameters describe **E017's** 25 partial oracles. E017 states that
  its `rho` is not a universal constant, and E020 states that `lambda` rests on 4
  of 72 tasks (Clopper-Pearson 95%: 0.015–0.136). Neither transfers.
- E017's oracles had strictly one-sided error (368 false accepts, 0 false
  rejects). This simulator's panel errs in both directions, so the reported
  `false_reject_rate` is a model output, not a transferred measurement, and
  E017's "unanimity beats majority by 3.7x" quorum result does not carry over as
  stated.
- The quorum is left at majority. E017 and E020 both find that the aggregation
  rule matters more than panel size; sweeping it here would be a different
  experiment.
- Panel size scales verifier votes identically for every arm, so the comparison
  stays matched, but the extra cost is counted in votes only — not wall time,
  energy, or human attention.
- Result 3's insensitivity finding is a property of *this* landscape's viability
  predicate. It says nothing about whether real systems are similarly forgiving;
  the plain reading is the opposite.
- Everything E024 already lists remains true: 50 agents rather than 100–10,000,
  a supplied rather than learned Goal Graph, and no measurement of novelty,
  information gain, churn, or adversarial contributors.

## Decision

Record the imperfect-panel sweep as a committed artifact and keep the perfect
panel as the default, so the published E024 reference stays reproducible.

Do **not** upgrade E024's conclusion to "robust to correlated verifier error".
Record instead that the benchmark cannot currently answer that question, and
that closing the gap needs a cost for accepted defects rather than a better
verifier model.

Issue #22's requirement for "independent verifiers with controllable error
correlation" is now met mechanically. Its scientific intent is not: the arms are
insensitive to those verifiers.

**Superseded in part by [E027](E027-defect-propagation.md).** The last paragraph
no longer holds unconditionally: with the defect channel armed the arms are
*not* all insensitive — random search and fixed-scalar evolution are damaged
substantially. The Quality-Diversity arm remains insensitive, and E027 measures
why. Cite E026 for the panel model and for the diagnosis; cite E027 for what
happens once an accepted defect costs something.
