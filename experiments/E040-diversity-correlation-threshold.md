# E040 — hypothesis 2 has no threshold to find, and its verification half is worth nothing

**Module:** [`randomness_lab/r1_correlation_threshold.py`](../randomness_lab/r1_correlation_threshold.py)
**Artifacts:** [machine-readable](../results/experiments/r1/diversity-correlation-threshold-seeds42-51.json.gz) · [generated table](../results/experiments/r1/diversity-correlation-threshold-seeds42-51.md)
**Tests:** [`tests/test_r1_correlation_threshold.py`](../tests/test_r1_correlation_threshold.py)
**Refs:** [#13](https://github.com/MSKazemi/idkmesh/issues/13), [#30](https://github.com/MSKazemi/idkmesh/issues/30)

Issue #13 states three falsifiable hypotheses. Hypothesis 1 was tested by
[E032](E032-population-scaling.md) and falsified in the direction it was stated.
Hypothesis 3 was tested by the coordination-topology arms in
[`docs/research/R1_COLLECTIVE_SCALING.md`](../docs/research/R1_COLLECTIVE_SCALING.md).
Hypothesis 2 is the one this experiment is about:

> Heterogeneous teams with independent verification outperform homogeneous
> teams at equal inference/compute budget on at least some software-engineering
> workloads.

**An earlier revision of this page said hypothesis 2 had no named test. That
was wrong, and the correction is the most useful thing on this page.** The
worker-correlation axis was already swept, under a different name: the
help/hurt regime sweep built for issue #30
([`randomness_lab/r1_sweep.py`](../randomness_lab/r1_sweep.py),
[`R1_HELP_HURT_SWEEP.md`](../docs/research/R1_HELP_HURT_SWEEP.md)) runs
`structural_diversity` against `identical_replication` across worker
correlations `0, 0.25, 0.5, 0.75, 1.0`, crossed with verifier correlation and a
structural-worker quality penalty, and classifies every cell `helps`, `hurts`,
or `uncertain`. It was never connected to issue #13's hypothesis 2, which is
how it went unnoticed, but the axis was not unswept. See
[what the help/hurt sweep already knew](#what-the-helphurt-sweep-already-knew)
below, which corroborates the result here and bounds it correctly.

What was genuinely missing is narrower: the R1 *scaling* runner measures the
same contrast — its `equal_attempt_budget_comparisons` section pairs the
structurally diverse arm against maximally correlated replication at an
identical attempt count — but only at one assumed correlation, `0.25`. The
scaling write-up says of the result:

> That result is partly constructed by the correlation assumptions; it must not
> be cited as evidence that heterogeneous coding agents outperform replicated
> models.

That hedge is correct and unquantified. Nothing anywhere fitted the shape of
the decay, and nothing separated the two halves of hypothesis 2's sentence.
This page does both.

## The claim, stated before the run

The sweep was written expecting a knee: some correlation above which the
advantage stops resolving, with `0.25` sitting comfortably below it and the one
correlation this repository has actually measured — `+0.5873`, from
[E017](E017-item-difficulty-and-quorum.md) — sitting near or above it. That
framing is what the runner's `thresholds` section was built to report.

It is the wrong shape. There is no knee.

## Result 1 — the advantage is proportional to retained independence

Fitting each difficulty-by-N curve's mean verified-success delta against
retained independence `1 - rho`, forced through the origin, gives an uncentered
R-squared of at least `0.99` in **17 of 18 curves**. The exception is
`diverse_verifiers / medium / N=2` at `0.9852`, the cell with the smallest
effect.

The fit is forced through the origin because the design pins that point:
`build_r1_conditions` fixes `identical_replication` at
`worker_error_correlation = 1.0` and hands `structural_error_correlation` to
the diverse arms, and both draw profiles with the same base success
probability. At `rho = 1.0` the two arms differ by a profile label and nothing
else. The runner asserts the observed delta there is exactly `0.0000` in all
nine `structural_diversity` cells as a harness self-check, not as a finding.

Slopes scale with the two things one would expect:

| | N=2 | N=5 | N=10 |
| --- | ---: | ---: | ---: |
| easy | 0.1018 | 0.1739 | 0.1847 |
| medium | 0.1997 | 0.3118 | 0.3517 |
| hard | 0.1931 | 0.4266 | 0.5504 |

Harder tasks and larger swarms buy more per unit of retained independence.
Nothing here is a threshold; it is a slope.

## Result 2 — correlation alone cannot flip the sign

If the advantage is `slope * (1 - rho)` with slope positive everywhere, then
for **any** assumed correlation short of `1.0` the diverse arm wins, and it
wins by an amount the assumption sets. The advantage stops resolving at
`rho = 0.85` in exactly two of eighteen cells — both `easy / N=2`, the smallest
effect in the grid — and otherwise survives to the last correlation before the
arms are identical by construction. No cell in this grid ever reports the
diverse arm *losing*.

So this grid cannot falsify hypothesis 2, and its output must not be quoted as
support for it: a mechanism that returns "hypothesis 2 holds" at every value it
can be given is reporting its assumption back. That is a statement about this
grid, not about the R1 lab as a whole — see the next section, which finds the
lever that does flip the sign, and it is not correlation.

This is a finding about the repository's own tooling, in the same class as
[E027's finding that E024 had no defect-propagation channel at all](E027-defect-propagation.md).
The correct use of the R1 scaling runner is to size an effect under a stated
assumption, never to decide whether the effect exists.

## What the help/hurt sweep already knew

The issue #30 sweep was rerun at its documented reference invocation to see how
much of the above it had already established. Ninety cells, `--tasks 200
--trials 10 --worker-correlations 0,0.25,0.5,0.75,1 --verifier-correlations
0,0.5,1 --quality-penalties 0,0.05,0.10 --swarm-sizes 2,5 --seed 42`:

| structural-worker quality penalty | helps | hurts | uncertain |
| ---: | ---: | ---: | ---: |
| 0.00 | 24 | **0** | 6 |
| 0.05 | 19 | 5 | 6 |
| 0.10 | 15 | 8 | 7 |

**All thirteen `hurts` cells carry a non-zero quality penalty, and eleven of
the thirteen sit at `rho_w = 1.0`.** Across the entire worker-correlation
ladder at penalty `0`, including `rho_w = 1.0`, the sweep never once reports
structural diversity hurting.

That is an independent corroboration of Result 1 and Result 2 from a runner
this experiment did not write, and it supplies the boundary Result 2 needs:
E040's grid gives its diverse workers no quality penalty, so it is exactly the
slice in which the sign cannot flip. The R1 lab *does* have a failure mode for
hypothesis 2. It is that diverse workers may be individually weaker, which the
help/hurt sweep charges explicitly and this grid does not charge at all.

Stated as one sentence: **correlation sets the size of the diversity advantage;
worker quality sets its sign.** Neither runner alone says that — the help/hurt
sweep classifies without fitting, and this grid fits without charging for
diversity.

## Result 3 — the verification half of the hypothesis is worth nothing here

Hypothesis 2 bundles two claims into one sentence: heterogeneous teams, *with
independent verification*. The two arms in this grid differ by exactly one
thing — `diverse_verifiers` randomizes verifier assignment over a pool of three
to five verifiers, `structural_diversity` keeps one fixed verifier — so
subtracting their fitted slopes isolates what the verification half buys.

| difficulty | N | worker diversity | + verifier diversity | increment | share |
| --- | ---: | ---: | ---: | ---: | ---: |
| easy | 2 | 0.1018 | 0.1098 | +0.0079 | +7.8% |
| easy | 5 | 0.1739 | 0.1905 | +0.0166 | +9.6% |
| easy | 10 | 0.1847 | 0.1853 | +0.0006 | +0.3% |
| medium | 2 | 0.1997 | 0.1816 | -0.0181 | -9.1% |
| medium | 5 | 0.3118 | 0.3262 | +0.0144 | +4.6% |
| medium | 10 | 0.3517 | 0.3509 | -0.0008 | -0.2% |
| hard | 2 | 0.1931 | 0.1865 | -0.0065 | -3.4% |
| hard | 5 | 0.4266 | 0.4277 | +0.0011 | +0.3% |
| hard | 10 | 0.5504 | 0.5483 | -0.0021 | -0.4% |

Five of nine increments are positive: a coin flip. The largest absolute
increment is `0.0181`, against worker-diversity slopes running to `0.5504`. The
sign does not hold within a difficulty or within a swarm size.

The whole measured effect is on the worker side. Quoting the `diverse_verifiers`
arm as evidence that independent verification pays would attribute to
verification an effect that survives removing it.

The mechanism is visible in the design rather than in a fitted parameter. Every
verifier in the pool is constructed with identical sensitivity and
false-positive rate, and `verifier_error_correlation` stays at its default
`0.60` throughout this sweep. Randomizing *which* identical verifier reads a
candidate cannot add independence that the pool does not have. Verifier
independence is a separate axis, and it is not the one this sweep moves.

## Result 4 — worker correlation swamps verifier assignment at the top of the range

At `rho = 1.0` the `diverse_verifiers` arm is not pinned to zero the way
`structural_diversity` is, because it still varies verifier assignment. Its
observed deltas there run from `-0.0145` to `+0.0235`, and all nine cells
classify `uncertain`.

Randomized verifier assignment does not rescue a fully correlated worker pool.
Whatever it is worth, it is not worth enough to be seen once the workers agree.

## Reproduction

From the repository root:

    python -m randomness_lab.r1_correlation_threshold \
      --tasks 200 \
      --trials 10 \
      --swarm-sizes 1,2,5,10 \
      --difficulties easy:0.82,medium:0.65,hard:0.45 \
      --seed 42 \
      --correlations 0,0.25,0.4,0.55,0.7,0.85,1.0 \
      --output results/experiments/r1/diversity-correlation-threshold-seeds42-51.json.gz \
      --report results/experiments/r1/diversity-correlation-threshold-seeds42-51.md

That is the default invocation, and it reproduces the committed payload. The
replay test compares by value at a relative tolerance of `1e-9` rather than by
digest, for the reason
[`docs/research/R1_COLLECTIVE_SCALING.md`](../docs/research/R1_COLLECTIVE_SCALING.md)
gives for its own artifacts: the simulation goes through `exp` and `**`, whose
last-place rounding is not identical across CPUs and C libraries, so byte
equality would assert something about the runner rather than about the code.

The whole sweep takes about eight seconds.

## What this does not establish

- **No model was called.** Worker quality, error correlation, defect rates, and
  verifier behavior are invented parameters. This is a statement about the
  simulator, not about coding agents.
- **The correlation swept is a shared-shock parameter, and E017 showed that
  shape is wrong.** At `rho = 0.5873`, E017 measured a joint-failure tail
  `1.71x` heavier than a flat shared shock predicts, and fitted a
  beta-binomial instead. The linearity in Result 1 is therefore itself an
  artifact of the assumed shape; a correctly shaped model would put more mass
  on the joint failures that erase the diversity advantage, so these slopes are
  the optimistic end.
- **`rho` is not a sufficient statistic.** Two panels at the same marginal
  correlation can have different joint-failure structure, which is E017's
  finding and the reason a single swept scalar cannot settle the question.
- **The intervals are descriptive.** Normal approximations over 10 seeds, with
  no multiplicity correction across the 126 reported cells. The `classification`
  field is a flag for where to look, not a hypothesis test.
- **Only the worker correlation moves.** `verifier_error_correlation` is held at
  `0.60`. The sweep says nothing about the verifier-independence axis, which
  Result 3 identifies as the one that would matter.
- **Diversity is free in this grid, and it is not free in reality.** Every arm
  draws profiles at the same base success probability, so the structurally
  diverse arm is never charged for being diverse. The help/hurt sweep's quality
  penalty is the honest version of that cost, and it is where every `hurts`
  cell lives.

## Decision

Hypothesis 2 stays open, and issue #13 stays open. What changes is what may be
said about it:

1. The R1 scaling runner's equal-budget advantage is not evidence for
   hypothesis 2 at any correlation, and should be cited as a sized effect under
   a stated assumption or not at all. Where a sign is wanted rather than a
   size, the help/hurt sweep is the runner that can produce one, because it
   charges for diversity.
2. Any future claim about "independent verification" must come from an arm that
   moves verifier independence. The `diverse_verifiers` arm does not; it moves
   verifier *assignment* over an identically parameterized pool.
3. The next test that would move this is a sweep of `verifier_error_correlation`
   against a beta-binomial joint-failure shape rather than a flat shared shock,
   using E017's fitted parameters as the reference point. The help/hurt sweep
   already crosses verifier correlation with a flat shape and finds it does not
   separate the `hurts` cells — eleven of thirteen are at `rho_w = 1.0`
   regardless of `rho_v` — so the shape, not the axis, is the open part.
4. A cross-runner check belongs in the test suite, not in prose. This revision
   adds one; the reason it is needed is that this page shipped a false claim
   about what the repository already contained, and prose is what allowed it.
