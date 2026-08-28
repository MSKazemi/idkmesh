# E020 — The Acceptance-Quorum Frontier Under the Measured Dependence Shape

## Research question

E015 swept the acceptance quorum at two levels (`q = 0.5, 0.7`) under a shared-shock
mixture and concluded that cost-asymmetric quorums help. E017 confirmed that on real
verifiers in a sharper form: with one-sided error, requiring unanimity beat majority
by 3.7x, while growing the panel to 25 bought nothing.

E018 and E019 then showed that swapping the shared-shock mixture for the
item-difficulty shape E017 measured overturns E015's headline ceiling. Both,
however, deliberately restricted themselves to `q = 0.5`, because comparing quorums
means modelling false accepts and false rejects separately, and that needs a corpus
base rate.

This experiment closes that gap:

> Does the change of dependence shape that overturned E015's ceiling also change
> **which aggregation rule you should use** — and do either of the two candidate
> models predict the high-quorum behaviour of a real panel?

The answer is no to the second half, and emphatically yes to the first.

## Data

Nothing new was collected. E020 reuses two existing artifacts, which is what makes
the base rate real rather than assumed:

- `experiments/results/E017-partial-oracle-votes.jsonl.gz` — 25 partial test
  oracles x 72 candidates = 1800 real verdicts;
- `benchmarks/e016-verification-corpus/tasks.jsonl` — the `viable` labels, giving a
  measured base rate of **0.6389** (46 of 72 candidates are defective).

Note that the corpus labels two mutants viable — `clamp_value::exclusive` and
`group_by_parity::neg_mod` are behaviourally equivalent to their references, so
accepting them is correct. Truth is taken from the `viable` field throughout;
deriving it from the task-name suffix instead inflates the irreducible count from
4 to 6.

```
verifiers                    : 25
tasks                        : 72  (26 viable, base rate 0.6389)
false rejects on viable code : 0
moment fit                   : mu=0.2044  icc=0.5800
irreducible tasks (all wrong): 4 -> lambda=0.0556
```

## Models compared

All three describe the same quantity — how many of `n` verifiers are wrong on a
given task — and the first two have identical parameter counts, so any difference
between them is shape, not freedom.

| model | mechanism | parameters |
|---|---|---|
| shared-shock | with probability `rho` all verifiers share one state, else independent | mean, `rho` |
| beta-binomial | each task draws difficulty `d ~ Beta(a,b)`; verifiers err independently at `d` | mean, ICC |
| one-inflated | a `lambda`-atom of irreducible tasks, plus a beta-binomial | mean, ICC, `lambda` |

The one-inflated model is introduced here because, as section 3 shows, **both
two-parameter models get the high-quorum limit wrong, in opposite directions**.

## Reproduce

```bash
python3 sim/e020_quorum_frontier.py
```

Fully deterministic — closed-form distributions plus a fixed artifact, no sampling.

## Results

### 1. The real quorum frontier, and what each model predicts

Panel error at each acceptance threshold, over all 72 candidates:

| `need` | real | shared-shock | beta-binomial | one-inflated |
|---:|---:|---:|---:|---:|
| 1 | 0.4167 | 0.5372 | 0.4941 | 0.5300 |
| 5 | 0.3611 | 0.3710 | 0.3148 | 0.3163 |
| 9 | 0.2500 | 0.1408 | 0.2401 | 0.2298 |
| 13 | 0.2083 | 0.1188 | 0.1857 | 0.1720 |
| 17 | 0.1250 | 0.1186 | 0.1385 | 0.1279 |
| 19 | 0.0972 | 0.1186 | 0.1155 | 0.1091 |
| 22 | 0.0556 | 0.1186 | 0.0790 | 0.0841 |
| 24 | 0.0556 | 0.1186 | 0.0500 | 0.0691 |
| 25 | 0.0556 | 0.1186 | 0.0313 | 0.0622 |

```
RMSE over all 25 quorums: shared-shock=0.0766  beta-binomial=0.0251  one-inflated=0.0328
```

The beta-binomial wins on average across the whole curve, reproducing E018's
verdict. But averages hide the operating point: **from `need = 17` upward the
shared-shock column is frozen at 0.1186** while reality keeps falling to 0.0556.

### 2. Headline — the two models disagree about whether a high quorum can help at all

At unanimity the three numbers separate cleanly, and neither two-parameter model
lands on the truth:

```
real = 0.0556    shared-shock = 0.1186 (2.13x too high)    beta-binomial = 0.0313 (1.77x too low)
```

The disagreement is structural, not a fitting artifact:

- **shared-shock** puts `P(all n wrong) = rho*mu + (1-rho)*mu^n`, which tends to the
  **hard floor `rho*mu = 0.1186` at every panel size**. The model asserts that past
  a certain threshold, raising the quorum cannot help.
- **beta-binomial** puts `P(all n wrong) = E[d^n] = B(a+n, b)/B(a, b)`. Since
  `Gamma(a+n)/Gamma(a+b+n) ~ n^-b`, this **decays as `n^-beta` with
  `beta = (1-mu)(1-icc)/icc = 0.5762`** — slowly, but to zero. The model asserts
  there is no floor at all, and that enough verifiers will verify anything.
- **reality has a floor, but not the one shared-shock describes.** It sits at
  `lambda = 0.0556` — the 4 defects that *every one of the 25 verifiers* misses.
  It is a shared blind spot of the panel, not a correlated shock.

The two mechanisms are distinguishable and matter differently. A shared shock is a
property of the *correlation*; a blind spot is a property of *which verifiers you
chose*. You escape the first by decorrelating and the second only by adding a
verifier of a different kind.

The beta-binomial's optimism is quantifiable: it says 10 verifiers suffice to reach
an error of 0.0556, and then promises continued improvement past it. The real panel
reaches 0.0556 and stops there from `need = 22` onward.

### 3. The shape, not the correlation, decides the aggregation rule

Optimal `need` minimising `base * cost_FA * P(false accept) + (1-base) * cost_FR *
P(false reject)`, `n = 25`, sweeping correlation, base rate and cost ratio:

| `rho` | base | FA:FR | `q*` shared-shock | `q*` item-difficulty | shift |
|---:|---:|:--|---:|---:|---:|
| 0.25 | 0.639 | 1:1 | 13 | 15 | +2 |
| 0.25 | 0.639 | 10:1 | 14 | 22 | +8 |
| 0.25 | 0.100 | 1:1 | 12 | 6 | −6 |
| 0.25 | 0.100 | 10:1 | 13 | 13 | +0 |
| 0.58 | 0.639 | 1:1 | 13 | 20 | +7 |
| 0.58 | 0.639 | 10:1 | 14 | 25 | +11 |
| 0.58 | 0.100 | 1:1 | 12 | 1 | −11 |
| 0.58 | 0.100 | 10:1 | 13 | 15 | +2 |
| 0.80 | 0.639 | 1:1 | 13 | 25 | +12 |
| 0.80 | 0.639 | 10:1 | 14 | 25 | +11 |
| 0.80 | 0.100 | 1:1 | 12 | 1 | −11 |
| 0.80 | 0.100 | 10:1 | 13 | 17 | +4 |

**Under shared-shock the optimum never leaves the neighbourhood of majority — it
spans 12 to 14 across every cell. Under item-difficulty it spans 1 to 25, the entire
range.** Changing `rho` from 0.25 to 0.80 moves the shared-shock optimum by one
verifier; changing the *shape* at fixed `rho` moves it by up to twelve.

The mechanism is the shape of the mass. A beta-binomial with these parameters is
U-shaped: most tasks are easy for everyone or hard for everyone, and little
probability sits in the middle. A decision threshold placed anywhere in that empty
middle costs almost nothing to move, so the optimum runs to whichever extreme the
cost asymmetry favours. The shared-shock mixture keeps a tight binomial core around
`n*mu`, so moving the threshold off centre immediately cuts into dense mass and the
optimum stays pinned.

This is why E015 saw only a mild quorum effect: it swept `q` under the model that
structurally cannot produce a large one.

### 4. Decision test — how much does tuning the quorum actually buy?

Each model is fitted to this panel and then asked how much error a better quorum
could remove. Unlike section 3, this is checkable against the panel itself:

| source | at majority | best reachable | gain |
|---|---:|---:|---:|
| **MEASURED** | 0.2083 | 0.0556 | **3.75x** |
| shared-shock | 0.1188 | 0.1186 | 1.00x |
| beta-binomial | 0.1857 | 0.0313 | 5.92x |
| one-inflated | 0.1720 | 0.0622 | 2.77x |

**The shared-shock model — the one used throughout E012, E013 and E015 and still the
default in `emergence_sim.py` — reports that no quorum beats majority by more than a
rounding error (1.00x).** On the real panel, choosing the quorum well is the single
largest available reduction in error (3.75x), and it is free: it costs no extra
verifiers, only a different rule for combining the votes they already cast.

An engineer following the shared-shock model would have spent the budget on more
verifiers, which E017 showed buys nothing, and skipped the change that removes
three quarters of the error.

The one-inflated model is the only one of the three whose gain estimate is the right
order (2.77x against 3.75x), because it is the only one that represents a blind spot.

## What this changes

1. **E015's quorum conclusion is directionally right and badly undersized.**
   Cost-asymmetric quorums do help; under the measured shape they help far more than
   E015 could see, and the optimum can sit at either extreme rather than near
   majority.
2. **`rho` is not the parameter to elicit.** Section 3 shows correlation moves the
   optimal rule by ~1 verifier and shape moves it by up to 12. E017 already showed
   `rho` is not a sufficient statistic for panel *error*; it is not one for panel
   *design* either.
3. **Measure `lambda`, the irreducible fraction.** It is the floor on what any
   aggregation rule can achieve, it is cheap to measure once you have per-task votes,
   and neither standard model predicts it.
4. **Prefer the one-inflated model for quorum decisions**, and the plain
   beta-binomial for whole-curve fit. They disagree exactly where the decision is
   made.

## Limitations

1. **Section 3 is a model comparison, not a measurement.** Its two-sided cost model
   assumes the panel is equally fallible in both directions. This panel is not — it
   produced **zero** false rejects in 1800 verdicts, because a passing partial test
   suite can miss a bug but never condemns correct code. Sections 1, 2 and 4 are
   measured on real votes; section 3 is what each shape *implies* once both error
   types exist, and it is unvalidated. A two-sided corpus is required to test it.
2. **The one-inflated model has three parameters against two**, so its better
   unanimity fit is partly bought. The structural claim — that a floor exists and
   the two-parameter models cannot express it — does not depend on the fit quality;
   it is visible directly in the 4 all-wrong tasks.
3. **`lambda = 0.0556` is 4 tasks.** The floor's existence is solid, its value is
   not: the Clopper-Pearson 95% interval on 4/72 runs 0.015 to 0.136.
4. **One corpus, one panel, Python function-level correctness.** The verifiers'
   diversity structure was constructed, as E017 notes. `lambda` in particular is a
   property of this panel's blind spots and will not transfer.
5. The 72 candidates come from 24 problems, so the independent unit count is nearer
   24 than 72 — as in E017, confidence in third decimals is unwarranted.

## Implementation references

- `sim/e020_quorum_frontier.py` — distributions, quorum frontier, decision test
- `tests/test_e020_quorum_frontier.py` — 17 tests
- Inputs: `experiments/results/E017-partial-oracle-votes.jsonl.gz`,
  `benchmarks/e016-verification-corpus/tasks.jsonl`
