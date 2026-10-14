# X8 — A budget-split predictor, tested against synthetic ground truth because the real-data test is blocked

**Status:** the predictor is built and its synthetic validation is complete; **the real-data test of
H4 has not been run and cannot be run yet.** **Evidence level:** synthetic only. Every task, worker,
verifier read, cost and acceptance rule below is simulated; nothing here is a result about real coding
agents or real verifiers. **Generator:** `sim/x8_budget_split.py` (`idkmesh.sim.x8_budget_split.v1`) ·
**Artifact:** [`results/X8-budget-split.json`](results/X8-budget-split.json), digest `604f4e90b621…` ·
**Program item:** X8 ([issue 981](https://github.com/MSKazemi/idkmesh/issues/981)), hypothesis H4,
algorithm A6, in [the scientific program](../docs/research/SCIENTIFIC_PROGRAM.md). **Builds on:**
[E043](E043-panel-frontier.md) (a panel does not pay when billed per read),
[E017](E017-item-difficulty-and-quorum.md) / [E020](E020-quorum-frontier-under-measured-shape.md)
(verifier difficulty shape) and [E046](E046-agent-value-forecast.md) (worker difficulty shape).

## The question, and why only half of it can be answered

H4 says that with imperfect verifiers the best split of a fixed budget between worker attempts and
verifier reads is predictable from the two measured dependence shapes, and that it beats fixed
heuristics. Its falsifier: all-workers, 50/50 or all-verifiers matches the predicted split's verified
value on held-out tasks, within uncertainty.

The real test needs, for the **same tasks**, worker outcomes and verifier verdicts on the candidates
those workers produced, with correctness labels, plus measured per-attempt and per-read costs. The
repository has none of that: X6 ([issue 979](https://github.com/MSKazemi/idkmesh/issues/979)) is blocked,
X7 ([issue 980](https://github.com/MSKazemi/idkmesh/issues/980)) is open, and E016/E017/E043 are
partial-oracle, synthetic or program panels. The maintainer's status comment on issue 981 (2026-10-12)
says the same and asks that the allocator and its three baselines be preregistered before any real
held-out split is opened. This record does that part and **manufactures no evidence**: it builds the
predictor, freezes the comparison in code, and measures the predictor against a simulated world whose
true best split is known.

**What it can and cannot show.** It shows the predictor is implementable from pilot-sized data, how
large its error is, where it fails, and that the comparison harness can tell a good predictor from a
broken one. It cannot show that real worker and verifier shapes behave like the simulated ones, or
that real costs have these ratios.

## The pipeline being allocated

An allocation is `(n, m)`: `n` worker attempts per task, each read by `m` independent verifier reads,
costing `n * (1 + m * c_v)` where one attempt costs 1 and a read costs `c_v`. A candidate is accepted
if at least `need(m)` reads accept (strict majority or unanimity, fixed per scenario). The task ends
with the first accepted candidate; if none is accepted it is escalated. With `p` the chance one attempt
is correct and `d` the chance one read accepts a wrong candidate:

`pc = p * P(Bin(m, 1 - r) >= need)`, `pw = (1 - p) * P(Bin(m, d) >= need)`,
`V = pc/(pc+pw) * (1 - (1-pc-pw)^n)`, `E = pw/(pc+pw) * (1 - (1-pc-pw)^n)`, `U = (1-pc-pw)^n`.

`(V, E, U)` is verified-correct, escaped defect, escalated; with the cost it is the part of the
program's verified-useful-work vector this model can express. Latency, human attention, energy and
traffic are **not** simulated. A Monte Carlo realisation of the pipeline agrees with the closed form
(tested).

## The predictor (A6)

Input: a list of `TaskObservation` records, one per pilot task (attempts made, how many were correct,
reads per candidate, accept votes on wrong and on correct candidates). This is the contract a real
X3 + X6 matrix must meet. It fits

- a worker beta-binomial (mean, intra-class correlation) from per-task solve counts;
- a verifier false-accept beta-binomial on reads of wrong candidates, pooled so tasks are weighted by
  how many wrong candidates they produce, and a pooled false-reject rate on correct candidates;
- a cross-dependence correlation between a task's worker failure rate and its false-accept rate,
  corrected for the attenuation both noisy rates carry.

It then integrates the closed form over a Gaussian copula of the two fitted marginals on a 30 by 30
grid and picks the feasible allocation with the highest predicted `V` (ties to the cheaper one).
Blind-spot routing (A7) is **not** implemented: it needs task-level features that this pilot format
does not carry.

## The synthetic world (deliberately not the predictor's own model)

Per task `p ~ Beta(mean 0.35, icc 0.4)` with an 8% atom at `p = 0` (worker-blind), and `d ~ Beta` with
an icc of 0.1 or 0.5 and a 5% atom at `d = 1` (verifier-blind). The cross term shifts `d`'s mean in
proportion to the task's worker failure rate (coefficient 0 or 0.6), a different shape from the
predictor's copula; the predictor has no atoms. False-reject rate 0.1. The scenario grid is
32 cells: read cost 0.1 or 0.5 of an attempt, budget 6 or 12 attempts, cross term 0 or 0.6, verifier
icc 0.1 or 0.5, majority or unanimity. Each of 16 replicates draws a 200-task pilot (8 attempts and 4
reads per candidate), fits, and is scored on 400 fresh tasks.

## Preregistration (frozen in the module before any scenario was scored)

Primary endpoint: held-out expected verified value `V`, paired by replicate, predicted split against
each baseline. A scenario is `predicted_wins` only if the paired difference to **every** baseline
exceeds two standard errors, `baseline_wins` if any baseline exceeds the prediction by two, else `tie`.
The issue's falsifier is the complement of `predicted_wins`. Baselines: all workers (`m = 1`, as many
attempts as fit; zero reads would yield no *verified* work), 50/50, and all verifiers (`n = 1`, as many
reads as fit, capped at 15). Controls: an oracle that sees the held-out truth, a uniformly random
allocation, and a **broken predictor** that reads the fitted predictions upside down.

## Results

**Headline.** Of 32 scenarios the predicted split beat all three baselines in **16 of 32**, tied in 14
and lost to a baseline in 2. The falsifier therefore fires in 16 of 32 scenarios, and this synthetic
test does not support the unconditional form of H4.

| scenario block | predicted wins | ties | baseline wins | predicted regret | best-baseline regret |
|---|---:|---:|---:|---:|---:|
| reads cost 0.1 of an attempt (16) | 16 | 0 | 0 | 0.0007 | 0.0389 |
| reads cost 0.5 of an attempt (16) | 0 | 14 | 2 | 0.0003 | 0.00002 |

Regret is the oracle's held-out `V` minus the strategy's. Mean regret over all 32 scenarios: predicted
0.00049, all workers 0.0332, 50/50 0.0503, all verifiers 0.2872, random allocation 0.1425, broken
predictor 0.3178. The broken-predictor control is about 640 times worse than the predictor, so the harness
does distinguish a predictor that works from one that does not.

**Where the wins are.** All 16 wins are the cheap-read scenarios, where the best fixed heuristic loses
0.039 of verified value to the optimum on average (the predicted split gains 0.038 on average over the
best baseline, range 0.016 to 0.115). When reads cost half an attempt, the best of the three heuristics
is within 0.0014 of the optimum in every scenario (mean regret 0.00002), so the predictor can at best
tie it. The predicted split is on average 0.0003 worse than the best baseline there.

**Where the predictor loses.** In two cost-0.5, budget-6, cross-0.6, verifier-icc-0.1 scenarios (one
per acceptance rule) all-workers beat the predicted split by 0.0010 and 0.0008 in `V` (z of -3.1 and
-2.1 over 16 replicates). The predictor chose `(3, 2)` in all 16 replicates, and the
all-workers allocation `(4, 1)` scored slightly higher on the held-out tasks. The margin is far below any practical meaning but is decisive under the preregistered rule,
so it is reported as a loss.

**The cross-dependence term did not matter here.** The predictor with the fitted cross term had mean
regret 0.00049; with the term forced to zero, 0.00052. The paired difference was within two standard
errors in all 32 scenarios (largest |z| 1.43), including the 16 where the world's coupling was 0.6.
In this model the term is not needed; this does not show it is unneeded in real data, where X7 is the
test.

**Prediction error.** The predicted `V` surface has a mean absolute error of 0.0246 over allocations
and a bias of -0.0071 (it under-predicts slightly). The predicted pick's mean rank among the
feasible allocations is 1.30 (worst scenario 2.69). Chosen allocations varied across scenarios, from
`(3, 2)` to `(10, 2)` and `(8, 5)`.

**Small pilot.** With 40 pilot tasks instead of 200 (sensitivity run, same scenarios and verdict
rule) the verdict counts are the same, 16 wins, 14 ties and 2 baseline wins; mean regret rises
from 0.00049 to 0.00087 and the surface error from 0.0246 to 0.0434.

**The vector, not the scalar.** Maximising `V` does not minimise escaped defects. In the cheap-read
block the predicted split escapes 0.323 of tasks against 0.236 for 50/50, and all-workers escapes
0.477; escalations average 0.170 for the predicted split. An operator who weights escapes heavily would
want a different objective, and the allocator takes none.

## Caveats that bound the claim

- The predictor and the truth share the closed-form pipeline, so only the parameters and the dependence
  shape are estimated. The result mostly shows that estimation from a pilot is adequate for *this*
  pipeline; a real pipeline (adaptive stopping, candidate ranking, correlated reads across candidates)
  would break that identity.
- Costs, acceptance rule, the atoms and every difficulty parameter are invented. The ties at read cost
  0.5 depend on 50/50 being a grid point close to the optimum there, which is a property of two chosen
  cost ratios and budgets, not a law.
- Held-out truth is the exact expectation over candidate and read randomness for each held-out task's
  true latent `(p, d)`, not a realised sample.
- The 32 scenarios are not independent draws from a population of real task classes; the 16/32 count
  is a property of the grid.
- The reads of one candidate are conditionally independent given the task. Real verifiers may share
  content-dependent errors beyond task difficulty, which this world does not contain.

## What is not done, and what unblocks it

1. The real held-out test: a matrix of worker outcomes plus verifier verdicts on the same candidates
   (X3 + X6), with measured costs; `fit_model` already takes it as `TaskObservation` records.
2. The independent-family verifier term (X7).
3. Blind-spot routing (A7) and the operator-facing advisor (T2, [issue 982](https://github.com/MSKazemi/idkmesh/issues/982)).
4. A preregistration document for the real run in the style of the E046 preregistrations; the frozen
   comparison in `sim/x8_budget_split.py` is the draft.

## Reproduce

`PYTHONPATH=. python sim/x8_budget_split.py` rebuilds the artifact (about 10 minutes, standard library
only). `tests/test_x8_budget_split.py` checks the closed form against Monte Carlo, the fit against a
known generator, the held-out calibration, the broken-predictor control, the verdict rule, one
replicate of the committed artifact from scratch, and that this record states the artifact's numbers.
