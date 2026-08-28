# E015 — Verification Phase Diagram and Effective Independent Panel Size

## Research question

E012 established qualitatively that **reviewer count is not independent evidence count**:
as verifier error correlation rises, majority-vote error rises while panel disagreement
falls. E012 measured this at a single operating point (5 verifiers, 75% accuracy,
quorum 0.5).

This experiment asks the quantitative version:

> Given a panel of `n` verifiers with per-verifier accuracy `p`, error correlation `rho`,
> and acceptance quorum `q`, **how many statistically independent verifiers is that panel
> actually worth?**

## The metric — effective independent panel size

For independent verifiers, the probability that the panel's majority is wrong is a
binomial tail. With `need = floor(q*n) + 1` votes required to accept:

```
E_indep(n, p, q) = sum_{k=0}^{need-1} C(n,k) * p^k * (1-p)^(n-k)
```

`E_indep` is strictly decreasing in `n`. We therefore define the **effective independent
panel size** `n_eff` of a measured correlated panel as the panel size that an *independent*
panel would need in order to produce the same measured false-accept rate:

```
n_eff(n, p, rho, q) = E_indep^{-1}( measured_false_accept_rate )
```

interpolated linearly between bracketing odd panel sizes.

`n_eff / n` is the **evidence efficiency** of the panel: the fraction of nominal reviewers
that survives as genuine independent evidence.

### Validation of the metric

The metric is anchored against E012's already-published numbers, not fitted to them:

| check | analytic | measured (E012) |
|---|---|---|
| independent 5-panel, `p=0.75`, `q=0.5` | `0.103516` | `0.103521` |
| fully correlated 5-panel (`rho=1`) | `0.25` (single verifier) | `0.251978` |

The simulator's verification model reproduces the binomial prediction at `rho = 0` to five
decimal places, and collapses to exactly one verifier at `rho = 1`. `n_eff` therefore
recovers `5.00` and `1.00` at the two endpoints by construction of the underlying model,
which is what makes the intermediate values meaningful.

## Design

Full factorial sweep, all cells completed:

```text
verifiers   n   = 3, 5, 7, 9, 11, 15, 21               (7 levels)
accuracy    p   = 0.60, 0.70, 0.75, 0.80, 0.90         (5 levels)
correlation rho = 0.0 .. 1.0 step 0.125                (9 levels)
quorum      q   = 0.5, 0.7                             (2 levels)
seeds           = 100 per cell
agents = 100, generations = 60, goal change at 30, bins = 8
strategies      = random, scalar, qd  (all three, pooled for panel metrics)
```

`7 x 5 x 9 x 2 = 630` cells; `630 x 100 = 63,000` simulator runs, each executing all
three search strategies, so `189,000` strategy-runs in total.

Verification error is a property of the panel rather than of the search strategy, so the
three strategies are pooled when computing panel metrics; per-strategy figures with CI95
intervals are retained in the raw records.

## Reproduce

```bash
E015_VERIFIERS=3,5,7,9,11,15,21 \
E015_ACCURACY=0.6,0.7,0.75,0.8,0.9 \
E015_CORRELATION=0.0,0.125,0.25,0.375,0.5,0.625,0.75,0.875,1.0 \
E015_QUORUM=0.5,0.7 \
python3 sim/e015_worker.py --seeds 100 --shard 0 --shards 1 --procs $(nproc) \
    --out e015-focus0.jsonl
python3 sim/e015_analyze.py e015-focus*.jsonl
```

Machine-readable results:

- `experiments/results/E015-verification-phase-diagram-raw.jsonl.gz` — per-cell, per-strategy
  aggregates with CI95 intervals (630 cells);
- `experiments/results/E015-verification-phase-diagram.jsonl` — derived `n_eff` per cell.


## Results

### 1. The metric recovers nominal panel size when errors are independent

`n_eff` at `p = 0.75`, `q = 0.5`:

| panel `n` | `rho=0` | `rho=0.25` | `rho=0.5` | `rho=0.75` | `rho=1` |
|---:|---:|---:|---:|---:|---:|
| 3 | 2.98 | 2.50 | 1.98 | 1.45 | 1.00 |
| 5 | 4.96 | 3.57 | 2.57 | 1.76 | 1.00 |
| 7 | 6.92 | 4.59 | 2.88 | 1.90 | 1.00 |
| 9 | 9.03 | 5.19 | 3.24 | 2.01 | 1.00 |
| 11 | 11.10 | 5.89 | 3.57 | 2.14 | 1.00 |
| 15 | 15.04 | 6.73 | 3.92 | 2.23 | 1.00 |
| 21 | 20.99 | 7.26 | 3.98 | 2.25 | 1.00 |

The `rho=0` column reproduces the nominal panel size across a 7x range (2.98 -> 20.99),
and the `rho=1` column collapses to exactly one verifier at every panel size. Neither
column was fitted; both fall out of the measurement.

### 2. Headline — correlation imposes a hard ceiling on obtainable evidence

The `rho=0.5` column stops growing. Going from 15 to 21 reviewers buys `+0.05` effective
verifiers. The ceiling is a property of the correlation level, not of the budget.

Maximum `n_eff` reachable at **any** panel size up to 21 (`q = 0.5`):

| `rho` | `p=0.6` | `p=0.7` | `p=0.75` | `p=0.8` | `p=0.9` |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 20.9 | 21.0 | 21.0 | 21.2 | 21.8 |
| 0.125 | 16.1 | 13.3 | 10.6 | 8.0 | 4.6 |
| 0.25 | 12.7 | 9.4 | 7.3 | 5.6 | 3.4 |
| 0.375 | 9.8 | 6.9 | 5.4 | 4.3 | 2.8 |
| 0.5 | 7.1 | 4.9 | 4.0 | 3.1 | 2.4 |
| 0.625 | 5.3 | 3.7 | 2.9 | 2.6 | 2.0 |
| 0.75 | 3.4 | 2.6 | 2.3 | 2.0 | 1.7 |
| 0.875 | 2.1 | 1.8 | 1.6 | 1.5 | 1.4 |
| 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

**Even 12.5% error correlation caps a 21-member panel at 10.6 effective verifiers.**

### 3. Marginal value of the last six reviewers (15 -> 21), `q = 0.5`

| `p` | `rho=0` | `rho=0.25` | `rho=0.5` | `rho=0.75` |
|---:|---:|---:|---:|---:|
| 0.60 | +5.83 | +3.11 | +1.31 | +0.52 |
| 0.70 | +5.85 | +1.28 | +0.37 | +0.09 |
| 0.75 | +5.94 | +0.53 | +0.05 | +0.03 |
| 0.80 | +6.31 | +0.20 | -0.01 | +0.02 |
| 0.90 | +6.71 | +0.08 | -0.06 | -0.01 |

Six additional reviewers deliver essentially their full nominal value when independent and
approximately nothing once `rho >= 0.5`. Values at or slightly below zero are within
sampling noise at 100 seeds; they are reported unrounded rather than clipped.

### 4. Counterintuitive — more accurate reviewers saturate sooner

Evidence efficiency `n_eff / n` at `n = 21`, `q = 0.5`:

| `p` | `rho=0` | `rho=0.25` | `rho=0.5` | `rho=0.75` | `rho=1` |
|---:|---:|---:|---:|---:|---:|
| 0.60 | 99.4% | 60.4% | 34.0% | 16.4% | 4.8% |
| 0.70 | 99.9% | 44.6% | 23.4% | 12.3% | 4.8% |
| 0.75 | 100.0% | 34.6% | 18.9% | 10.7% | 4.8% |
| 0.80 | 100.8% | 26.6% | 14.6% | 9.6% | 4.8% |
| 0.90 | 103.8% | 16.0% | 11.2% | 8.0% | 4.8% |

At `rho = 0.25`, a panel of 21 reviewers who are individually 90% accurate retains **16%**
of its nominal evidence, while a panel of 21 reviewers who are individually 60% accurate
retains **60%**.

The mechanism: an independent panel of highly accurate reviewers drives error down very
fast, so the error floor created by shared shocks corresponds to a much smaller
independent-equivalent panel. Correlation is more costly precisely where reviewers are
individually strong — which is the regime IDKMesh is heading into, since agents drawn from
the same model family are both accurate and correlated.

The `rho=0` values slightly above 100% (100.8%, 103.8%) are interpolation and
sampling artifacts at 100 seeds, not evidence of superadditivity.

## Limitations

1. **`n_eff` is only comparable within a fixed quorum.** *(Resolved -- see
   "Quorum-comparable metric" below.)* It is calibrated on the false-accept rate alone.
   Every `n_eff` figure quoted above is at `q = 0.5`, where the two error types are
   symmetric. Use `n_eff_balanced` to compare quorums.
2. Correlation is the shared-shock mixture inherited from E012. It is a controlled
   mechanism, not a model fitted to real reviewer behaviour, and real correlation is
   unlikely to be uniform across a panel.
3. Viability classification is synthetic; this is not a code-review benchmark.
4. 100 seeds per cell. Differences below roughly 0.1 effective verifiers are noise.
5. `n_eff` is capped at 201 by the search bound in `effective_n`.

## Consequences for IDKMesh

1. **Panel size must be justified against an estimated correlation, not chosen.** Beyond the
   ceiling, extra reviewers consume budget and return no evidence. This bears directly on
   the roadmap's primary metric, `Verified Useful Work / (Human Attention + Compute Cost)`:
   reviewers past saturation inflate the denominator and leave the numerator unchanged.
2. **Correlation must be measured, not assumed.** The gap between `rho=0` and `rho=0.125`
   is the difference between 21 and 10.6 effective reviewers. Estimating `rho` is worth more
   than adding reviewers.
3. **Panel disagreement cannot be used as a health signal.** E012 already showed
   disagreement falls as correlation rises; combined with these results, a quiet panel is
   consistent with either genuine independence or total correlation, which are the best and
   worst cases.
4. **Model-family diversity is a first-class scheduling constraint**, not a nice-to-have —
   result 4 shows the penalty is largest exactly where reviewers are individually strong.

## Compute provenance

Run on two ephemeral Azure `Standard_F64s_v2` virtual machines (Intel Xeon Platinum 8272CL
@ 2.60 GHz, 32 physical cores / 64 threads each; 128 threads total) in `eastus2` and
`uksouth`, on 2026-08-28. The 630-cell grid was split into two index-strided shards and
completed in 463 s and 460 s of wall clock respectively.

The machines were created in dedicated resource groups (`idkmesh-lab-*`) and deleted
immediately after the results were harvested. Local reproduction is entirely practical: the
same grid is roughly 15 core-hours and runs on one workstation overnight, or in about
25 minutes on 32 cores.

Per-core throughput differs between the cloud machines and a laptop by roughly 3.5x, so the
wall-clock figures above are not portable; the seed counts and cell counts are.

---

# Quorum-comparable metric (`n_eff_balanced`)

## The defect in `n_eff`

`n_eff` inverts the false-accept tail only. Raising the acceptance quorum suppresses false
accepts by trading them for false rejects, so a one-sided metric reads a strict quorum as
an enormous panel. Measured, at `p = 0.75`, `n = 11`, independent errors:

| `q` | false accept | false reject | `n_eff` (one-sided) |
|---:|---:|---:|---:|
| 0.5 | 0.0343 | 0.0343 | 11.06 |
| 0.7 | 0.0013 | 0.2866 | **199.00** |

An 11-member panel is not worth 199 reviewers. The false-accept rate fell 26x while the
false-reject rate rose 8x, and the one-sided metric saw only the first half.

## The fix

`n_eff_balanced` matches the panel's **balanced error** -- the mean of the two error
types -- against a fixed reference family: *independent simple-majority panels*. Because
the reference does not move with the measured panel's quorum, the values are comparable
across quorums. At `q = 0.5` the two metrics coincide exactly, so every result above is
preserved.

| `rho` | `n_eff` (one-sided, `q=0.7`) | `n_eff_balanced` (`q=0.7`) |
|---:|---:|---:|
| 0.0 | 199.00 | **3.47** |
| 0.25 | 166.87 | 2.72 |
| 0.5 | 86.57 | 2.13 |
| 0.75 | 46.38 | 1.56 |
| 1.0 | 1.00 | 1.00 |

## Result — a strict quorum destroys evidence

`n_eff_balanced` at `p = 0.75`:

| panel `n` | `rho` | `q = 0.5` | `q = 0.7` |
|---:|---:|---:|---:|
| 5 | 0.0 | 4.98 | 2.25 |
| 11 | 0.0 | 11.06 | 3.47 |
| 21 | 0.0 | 21.09 | 4.08 |
| 11 | 0.5 | 3.55 | 2.13 |
| 21 | 0.5 | 4.01 | 2.30 |

Raising the quorum from 0.5 to 0.7 costs a 21-member independent panel roughly **80% of
its evidence** (21.09 -> 4.08). A strict quorum is not free caution; it converts one error
type into a larger quantity of the other.

## Result — a fractional quorum does not mean what it says

`n_eff_balanced` at `q = 0.7` is **not monotone in panel size**: `n = 9` scores 2.06 while
`n = 11` scores 3.47. This is not noise. The acceptance threshold is
`need = floor(q*n) + 1`, so a nominal 70% quorum imposes:

| `n` | votes required | effective fraction |
|---:|---:|---:|
| 3 | 3 | 100.0% |
| 5 | 4 | 80.0% |
| 7 | 5 | 71.4% |
| 9 | 7 | 77.8% |
| 11 | 8 | 72.7% |
| 15 | 11 | 73.3% |
| 21 | 15 | 71.4% |

A "70% quorum" is unanimity at `n = 3` and 77.8% at `n = 9`. **Adding one reviewer can
make a panel materially worse** by pushing the rounded threshold up.

Operationally: specify quorums as *vote counts*, not fractions, or pin the panel size --
otherwise the review policy silently changes strictness as panels grow and shrink.

## Remaining limitations

- The balanced error weights false accepts and false rejects equally. Where the two carry
  different costs (accepting a bad patch is usually worse than rejecting a good one), a
  cost-weighted variant is the right generalisation; `effective_n_balanced` takes the two
  rates separately so the weighting is a one-line change.
- The reference family is fixed to simple-majority independent panels. This is a choice,
  not a derivation; it is stated so results remain interpretable.
