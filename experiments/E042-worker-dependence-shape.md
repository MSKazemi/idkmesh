# E042 — E040's hedge points the wrong way, and its proportionality is a property of the shape

**Module:** [`randomness_lab/r1_dependence_shape.py`](../randomness_lab/r1_dependence_shape.py)
**Artifacts:** [machine-readable](../results/experiments/r1/worker-dependence-shape-seeds42-51.json.gz) · [generated table](../results/experiments/r1/worker-dependence-shape-seeds42-51.md)
**Tests:** [`tests/test_r1_dependence_shape.py`](../tests/test_r1_dependence_shape.py)
**Refs:** [#13](https://github.com/MSKazemi/idkmesh/issues/13), [#30](https://github.com/MSKazemi/idkmesh/issues/30)

[E040](E040-diversity-correlation-threshold.md) fitted the equal-budget
diversity advantage against retained independence `1 - rho`, found it
proportional in 17 of 18 curves, and then hedged its own result:

> The linearity in Result 1 is therefore itself an artifact of the assumed
> shape; a correctly shaped model would put more mass on the joint failures that
> erase the diversity advantage, so these slopes are the optimistic end.

[E041](E041-verifier-strictness-shock.md) showed the reshape E040 asked for has
no target on the *verifier* axis, because `randomness_lab` has no verifier
panel. **The worker axis does have one.**
`CorrelatedBernoulliEnvironment` is a genuine panel over the workers of a task,
and it is exactly the flat shared shock
[E017](E017-item-difficulty-and-quorum.md) falsified. So E040's request is
executable one axis over, and this experiment executes it.

Both halves of the hedge turn out to be wrong, in different ways. The slopes
rise rather than fall, and the proportionality E040 reported is substantially a
property of the shape it assumed.

## The comparison is shape and nothing else

The two environments take the same two parameters and are constructed to agree
at both endpoints, so any difference between them is attributable to shape:

- **`shared_shock`** — with probability `rho` the whole panel shares one
  correctness state, otherwise every worker is independent. The historical
  behaviour, and the default.
- **`item_difficulty`** — each task draws a difficulty `d ~ Beta(a, b)` with
  `a = mu(1-rho)/rho` and `b = (1-mu)(1-rho)/rho`, and workers then fail
  independently at `d`. This gives marginal error `E[d] = mu` and pairwise error
  correlation `1/(a+b+1) = rho`. It is the sampling counterpart of
  [E018](E018-dependence-model-shape.md)'s closed-form `item_difficulty_error`.

Measured over 40,000 tasks at `N = 5`, `p = 0.68`:

| rho | shared-shock marginal | item-difficulty marginal | shared-shock corr | item-difficulty corr | shared-shock P(all fail) | item-difficulty P(all fail) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.3203 | 0.3200 | 0.0059 | -0.0072 | 0.0032 | 0.0032 |
| 0.25 | 0.3229 | 0.3179 | 0.2507 | 0.2487 | 0.0856 | 0.0425 |
| 0.40 | 0.3225 | 0.3196 | 0.4042 | 0.4034 | 0.1326 | 0.0837 |
| 0.55 | 0.3220 | 0.3185 | 0.5479 | 0.5483 | 0.1795 | 0.1343 |
| 0.70 | 0.3239 | 0.3220 | 0.7046 | 0.7031 | 0.2297 | 0.1941 |
| 0.85 | 0.3231 | 0.3179 | 0.8543 | 0.8503 | 0.2769 | 0.2533 |
| 1.00 | 0.3219 | 0.3207 | 1.0000 | 1.0000 | 0.3219 | 0.3207 |

The marginals agree, the measured correlation tracks the configured `rho` under
both, and the two coincide at `0` and `1`. The only column that separates them
is the joint tail — and **the shared shock puts about twice as much mass on
total failure at `rho = 0.25`**. That single column drives everything below.

The direction is worth pausing on, because it is the opposite of what E040
assumed. It is not a surprise in context: [E020](E020-quorum-frontier-under-measured-shape.md)
already found the beta-binomial *lower* than the shared shock in the tail at
`n = 25` — `0.0313` against `0.1186`. E040's hedge is inconsistent with a result
this repository already had.

## The runner reproduces E040 exactly

This module computes the deltas directly from `run_r1_condition`, while E040
went through `r1_scaling`. The flat topology in that module calls
`run_r1_condition` unchanged, so the two must agree — and they do, to
`0.0000` across all nine of E040's published cells.

The strongest form of that check is not the slopes but E040's *exception*: it
reports 17 of 18 curves at `R^2 >= 0.99`, the one failure being
`diverse_verifiers / medium / N=2` at `0.9852`. This run recovers that cell at
`0.9852`, and its shared-shock proportional count is `17 of 18`. The two runners
agree down to which curve fails and by how much. This is the cross-runner check
E040's own decision item 4 asked to be put in the test suite rather than in
prose.

## Result 1 — the slopes rise

| family | difficulty | N | shared-shock | R2 | item-difficulty | R2 | change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| structural_diversity | easy | 2 | 0.1018 | 0.9977 | 0.1091 | 0.9973 | +7.2% |
| structural_diversity | easy | 5 | 0.1739 | 0.9989 | 0.2097 | 0.9766 | +20.6% |
| structural_diversity | easy | 10 | 0.1847 | 0.9976 | 0.2307 | 0.9456 | +24.9% |
| structural_diversity | medium | 2 | 0.1997 | 0.9929 | 0.1806 | 0.9930 | -9.6% |
| structural_diversity | medium | 5 | 0.3118 | 0.9980 | 0.3364 | 0.9942 | +7.9% |
| structural_diversity | medium | 10 | 0.3517 | 0.9989 | 0.3787 | 0.9770 | +7.7% |
| structural_diversity | hard | 2 | 0.1931 | 0.9981 | 0.2021 | 0.9789 | +4.7% |
| structural_diversity | hard | 5 | 0.4266 | 0.9987 | 0.4603 | 0.9986 | +7.9% |
| structural_diversity | hard | 10 | 0.5504 | 0.9989 | 0.5709 | 0.9909 | +3.7% |
| diverse_random_verifiers | easy | 2 | 0.1098 | 0.9907 | 0.1159 | 0.9856 | +5.6% |
| diverse_random_verifiers | easy | 5 | 0.1905 | 0.9951 | 0.2145 | 0.9761 | +12.6% |
| diverse_random_verifiers | easy | 10 | 0.1853 | 0.9944 | 0.2316 | 0.9438 | +25.0% |
| diverse_random_verifiers | medium | 2 | 0.1816 | 0.9852 | 0.1806 | 0.9896 | -0.6% |
| diverse_random_verifiers | medium | 5 | 0.3262 | 0.9985 | 0.3510 | 0.9903 | +7.6% |
| diverse_random_verifiers | medium | 10 | 0.3509 | 0.9984 | 0.3807 | 0.9762 | +8.5% |
| diverse_random_verifiers | hard | 2 | 0.1865 | 0.9914 | 0.2070 | 0.9883 | +11.0% |
| diverse_random_verifiers | hard | 5 | 0.4277 | 0.9988 | 0.4657 | 0.9959 | +8.9% |
| diverse_random_verifiers | hard | 10 | 0.5483 | 0.9982 | 0.5682 | 0.9935 | +3.6% |

The slope rose in **16 of 18** curves, with a mean change of `+8.7%` and a range
of `-9.6%` to `+25.0%`. E040 predicted the corrected shape would shrink them.

The mechanism is entirely in the tail column above. At `rho = 1` the two shapes
coincide, so `identical_replication` — the reference arm — is unchanged by
construction. In between, the beta-binomial loses fewer tasks *completely*, so
the diverse arm converts more of its retained independence into verified
successes, and its advantage over replication grows.

The effect is largest where the base success probability is highest: the three
largest increases are all `easy` cells at `N = 5` and `N = 10`. That fits the
mechanism — when workers are individually good, "the whole panel failed" is the
dominant way a task is lost, so a shape that reallocates mass out of that state
buys the most.

## Result 2 — proportionality is substantially a property of the shape

Counting curves at E040's own `R^2 >= 0.99` threshold: `17 of 18` under the
shared shock, and `8 of 18` under the item-difficulty shape.

E040's Result 1 is titled "the advantage is proportional to retained
independence". Under a shape matched on both of its parameters, that holds for
fewer than half the curves. The advantage still *falls* monotonically with
correlation under both shapes — nothing here restores a threshold — but the
specific claim that it falls *proportionally* does not survive the reshape.

The curves that stop being proportional are the same ones with the largest slope
increases, and they bend the same way: the deltas fall off more slowly than
linearly at low correlation, then drop. So Result 1 and Result 2 are one
phenomenon seen twice, not two findings.

## What this does not establish

- **It does not establish that the diversity advantage is larger than E040
  reported.** Neither shape is right.
  [E020](E020-quorum-frontier-under-measured-shape.md) measured a real panel and
  found a blind-spot floor `lambda` that the shared shock overshoots and the
  beta-binomial does not have at all — at `n = 25` the beta-binomial predicted
  `0.0313` against a measured `0.0556`, promising an improvement that never
  arrives. What is established is narrower: **E040's hedge is unsupported in the
  direction it was stated**, and the true direction is unknown, because both
  candidate shapes miss the feature the one measured panel actually had.
- **No model was called.** Worker quality and both correlations are invented
  parameters. This is a statement about the simulator.
- **The equivalence check is at one cell.** `N = 5`, `p = 0.68`. The shapes are
  matched by construction at every `mu`, but only verified by sampling there.
- **The intervals are not reported per curve.** E040's grid at 10 seeds is
  descriptive; the slope changes here are point estimates over the same seeds,
  and the two smallest changes — `-0.6%` and `+3.6%` — should not be read as
  directional on their own. The 16-of-18 count is the claim, not any single cell.
- **Only equal-quality workers are covered.** `ItemDifficultyEnvironment` refuses
  heterogeneous workers rather than inventing a rule for splitting one
  difficulty draw among them, which excludes exactly one R1 arm,
  `bandit_selected`. That arm is not in E040's grid either.
- **The help/hurt sweep is untouched.** E040 established that worker *quality*,
  not correlation, is what flips the sign of the diversity advantage. Nothing
  here charges the diverse arm for being diverse, so this grid still cannot
  produce a sign.

## Decision

1. **E040's hedge should be read as withdrawn, not weakened.** The sentence
   "these slopes are the optimistic end" points the wrong way in 16 of 18 curves
   and contradicts E020's existing numbers. It should not be quoted.
2. **E040's Result 1 should be cited with its shape named.** "Proportional to
   retained independence, under a flat shared shock" is defensible; the
   unqualified form is not, at `8 of 18`.
3. **The shape is now a first-class knob**, `worker_dependence_shape`, defaulting
   to `shared_shock` so every committed artifact still reproduces. Any future R1
   claim that depends on the joint-failure tail should be run under both and
   report both.
4. **The open question is the floor, not the shape.** E020's `lambda` is the
   feature neither shape has, and it is the one the single measured panel
   actually showed. A one-inflated variant — Beta plus an atom at "all wrong" —
   is the next thing to try, and unlike a panel for the verifier axis it needs no
   design change, only a third entry in the registry.
