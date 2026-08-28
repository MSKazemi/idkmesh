# E017 — Measured verifier correlation, and why the shared-shock model is the wrong shape

**Status: positive result.** The first measurement of real verifier error
correlation in this repository, and the first real-data test of the model
E012, E013 and E015 all depend on.

## What E016 left open

E016 tried to measure error correlation with LLM verifiers and failed: none of
the 20 discriminated above chance, so no correlation could be estimated. The
obstacle was verifier competence, not the question. The stated limitation of
E012/E013/E015 — `rho` is a knob, never measured — stayed open.

E017 closes it with verifiers that demonstrably work.

## The panel

A verifier here is a **partial test oracle**: it draws inputs from one named
*region* of a problem's input domain (`tiny`, `small`, `large`, `extreme`,
`duplicate`) and accepts a candidate only if it matches the reference
implementation on all of them. 5 regions x 5 seeds = **25 verifiers**, run over
the same 72-candidate corpus E016 used, whose ground truth is decided by
executing hidden tests.

This is a real verification panel in the sense that matters: every verifier is a
program, every error is a genuine missed defect, and the error vectors are
observed rather than assumed. Region membership is a *declared independence
label* of exactly the kind ADR-0008 hypothesises, which makes the label itself
testable.

It cost 5 seconds on one laptop. E016 spent 20 Azure VMs to produce nothing
measurable.

```bash
python sim/e017_verify.py --seeds 5 --out e017-votes.jsonl
python sim/e017_analyze.py experiments/results/E017-partial-oracle-votes.jsonl.gz
```

## 1. The panel passes the screen E016 failed

```
verifiers: 25   discriminating above chance: 25/25
mean accuracy p = 0.7956
```

Every verifier's Youden `J` is significantly positive after Bonferroni
correction. The correlation numbers below are therefore interpretable, which is
precisely what could not be said of E016's.

## 2. Real verifiers are heavily correlated, and the label only partly predicts it

```
same region (declared dependent)   n= 50  mean rho=+0.8924
diff region (declared independent) n=250  mean rho=+0.5263
ALL PAIRS                          n=300  mean rho=+0.5873
```

The declared label carries real signal — `+0.892` within a region against
`+0.526` across. **But verifiers that share no declared attribute still share
53% of their errors.** Treating a metadata group boundary as an independence
boundary would overstate the panel's independent evidence by a wide margin.
This sharpens E013's conclusion: independence must be *estimated from observed
error vectors*, because the declared structure captures only part of it.

## 3. Under majority vote, 25 verifiers are worth 1

```
real 25-verifier majority error : 0.2083
single verifier                 : 0.2044
measured effective size         : 1.00   (of 25 nominal)
N_eff heuristic N/(1+(N-1)rho)  : 1.66   -> overstates by 1.66x
```

The panel is no better than one of its members. This is the strongest available
support for the repository's central verification claim — *reviewer count is not
independent evidence count* — and it is now measured rather than simulated.

It also confirms E015's direction on real data: the `N_eff` heuristic is
optimistic (1.66 against a measured 1.00).

## 4. The shared-shock model has the wrong shape

Feeding the **measured** `rho` back into the model E012/E013/E015 use:

```
real 25-verifier majority error          : 0.2083
independent model (rho=0)                : 0.0005
FLAT shared-shock at mean rho=0.587      : 0.1216   (1.71x too low)
NESTED shared-shock (g=0.526, b=0.773)   : 0.1290   (1.62x too low)
```

A nested variant that matches **both** the within-region and cross-region
correlation barely improves on the flat one. Accuracy heterogeneity does not
explain the gap either — re-simulating with each verifier's own measured
accuracy gives `0.1228`, still `+0.086` short.

The reason is structural, and it is visible in the distribution of how many
verifiers err per task:

```
 k err  observed  beta-binom  shared-shock
     0        42        35.9          33.7
     1         2         5.6           0.6
    13         1         0.9           0.0
    24         0         1.3           0.0
    25         4         2.1           8.6
partial       11        11.2           0.0   <- panel failures short of unanimous
```

**Eleven of the ~15 real panel failures are partial** — a majority of verifiers
wrong while a minority is still right. The shared-shock mixture assigns that
outcome essentially zero probability: conditional on the shock it produces
unanimity, and conditional on no shock it produces a tight binomial spike near
`k=5`. It compensates by over-predicting unanimous failure (8.6 against 4
observed) and still lands 1.7x too low overall.

## 5. A model of the right shape, at the same parameter count

Replace "with probability `rho` everyone shares one correctness state" with
"each task has a difficulty `d ~ Beta(alpha, beta)`, and each verifier errs
independently with probability `d`". That is a **beta-binomial**, and it has the
same two free parameters as the flat shared-shock model (a mean and a
correlation) — so this is a comparison of shape, not of freedom.

```
beta-binomial fit: mu=0.2044  implied pairwise rho=0.5713  (measured 0.5873)
panel error   real=0.2083   beta-binomial=0.1847   flat shared-shock=0.1216
partial failures  real=11   beta-binomial=11.2     flat shared-shock=0.0
```

The fitted correlation lands on the independently measured `rho`, the partial
failure count is reproduced almost exactly, and the panel error is **3.7x
closer** to reality.

**Recommendation:** parameterise verifier dependence by an item-difficulty
distribution, not by a single shared-shock probability. `rho` remains a useful
*summary* of a panel, but it is not a sufficient statistic for its error.

## 6. Quorum choice matters more than panel size

Every verifier error in this panel is a **missed defect**: across all 1800
decisions there were 368 false accepts and **zero** false rejects. A passing
partial test suite can fail to expose a bug; it never condemns correct code.

With one-sided error, majority vote is the wrong rule — any single rejection is
decisive evidence:

```
 need  rule                  error
    1  any accept           0.4167
   13  majority             0.2083
   19  need>=19             0.0972
   24  need>=24             0.0556
   25  unanimous accept     0.0556
```

**Fixing the aggregation rule cuts error 3.7x (0.2083 -> 0.0556); growing the
panel to 25 bought nothing.** The residual 4 are defects that every one of the
25 verifiers misses — an irreducible floor no quorum can reach.

This is E015's cost-asymmetric quorum result, confirmed on real verifiers, with
a sharper practical form: **measure whether your verifiers' errors are one-sided
before choosing how to aggregate them.**

> **Follow-up (E020).** Section 6's quorum result is extended to the full
> frontier, with the corpus base rate, in
> [`E020-quorum-frontier-under-measured-shape.md`](E020-quorum-frontier-under-measured-shape.md).
> Two things there qualify this experiment. The beta-binomial recommended here
> **under-predicts the unanimity floor by 1.77x** (0.0313 against the measured
> 0.0556): it has no floor at all, decaying as `n^-0.576`, whereas the real panel
> stops at the 4 defects every verifier misses. And the shared-shock model does
> not merely fit worse -- it reports that **no quorum beats majority** (1.00x
> against the measured 3.75x), so it gets the highest-leverage decision on this
> panel exactly backwards.

## Limitations

- **The verifiers' diversity structure is constructed, not naturally occurring.**
  Their errors are real, but I chose the regions. The measured `rho` describes
  this panel; it is not a universal constant for verification panels.
- **One-sided error is a property of test oracles**, not of verifiers in general.
  E012/E013/E015 model two-sided error, so section 6 transfers only to panels
  whose errors are also one-sided. Section 4's shape critique does not depend on
  sidedness.
- **The beta-binomial is fitted, not predicted.** Both its parameters come from
  these data. The claim is that it fits far better at equal parameter count, not
  that it was validated out of sample.
- **72 candidates from 24 problems.** Problems, not candidates, are the
  independent unit, so the effective sample size for `rho` is nearer 24 than 72.
  Confidence in the third decimal of `rho` is unwarranted.
- Python function-level correctness only; a single corpus.
- Sensitivity is 1.0 for every verifier by construction, so Youden `J` reduces to
  specificity here. The screen is still meaningful — it is what E016 failed —
  but it is not exercising both of its terms.
