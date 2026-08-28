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

---

# Cost-weighted quorum selection

## Why equal weighting is the wrong default

`n_eff_balanced` weights both error types equally. For IDKMesh they are not equal:
merging an unsafe patch costs more than asking a contributor to resubmit. The generalised
metric is

```
weighted_error = (w * false_accept + false_reject) / (1 + w)
```

where `w` is how many false rejects one false accept is worth. `w = 1` reproduces
`n_eff_balanced` exactly, so no previously published figure moves.

## Result — quorum and panel size are substitutes

For each panel configuration we solve for the **cost ratio at which quorum 0.7 overtakes
quorum 0.5**. Below the listed `w`, simple majority wins; above it, the strict quorum does.

At `p = 0.75`:

| panel `n` | `rho=0` | `rho=0.25` | `rho=0.5` | `rho=0.75` |
|---:|---:|---:|---:|---:|
| 3 | 3 | 3 | 3 | 3 |
| 5 | 3 | 3 | 3 | 3 |
| 7 | 3 | 3 | 3 | 3 |
| 9 | 7 | 7 | 7 | 7 |
| 11 | 8 | 7 | 8 | 7 |
| 15 | 17 | 17 | 18 | 15 |
| 21 | 39 | 33 | 24 | 19 |

Two readings, both operational:

**1. Large panels make strict quorums redundant.** A 3-to-7 member panel justifies a strict
quorum as soon as a false accept costs about **3x** a false reject — an easy bar to clear
for merge decisions. A 21-member panel needs the false accept to cost **39x**. Numbers and
strictness buy the same thing; buying both is waste.

**2. Correlation makes strictness worth buying sooner.** At `n = 21` the threshold falls
from **39** at `rho = 0` to **19** at `rho = 0.75`. Once reviewers are correlated, extra
reviewers stop suppressing false accepts (the ceiling from the phase diagram above), so the
quorum becomes the only remaining lever.

Combined with the saturation result, this gives a concrete policy shape: **estimate `rho`
first; if it is high, stop adding reviewers and raise the quorum instead.**

The threshold values cluster (3/3/3, then 7/7/7) because of the `floor(q*n) + 1` rounding
documented above; they should be read as bands, not exact crossings.

## Limitation

These crossings compare only the two quorum levels present in this sweep (`0.5` and `0.7`).
They locate the crossover between those two, not a global optimum over all quorums.

## Testing the `N_eff` heuristic

`MATHEMATICAL_FOUNDATIONS.md` section 9 records the standard equal-correlation heuristic

`N_eff ~= N / (1 + (N-1) rho)`

as an estimate of how much independent evidence a correlated panel supplies. E015 can test it
rather than assume it, because the shared-shock mixture makes the pairwise error correlation
*exactly* `rho`:

- marginal error rate is `1 - p` in both branches;
- `Cov(E_i, E_j) = rho (1-p) + (1-rho)(1-p)^2 - (1-p)^2 = rho p (1-p)`;
- `Var(E_i) = p (1-p)`, so `Corr(E_i, E_j) = rho`.

The heuristic is therefore fed precisely the parameter it asks for. Any disagreement is a
property of the heuristic, not a parameter mismatch.

### Result: exact at the endpoints, wrong in between, and not conservatively wrong

Comparing measured `n_eff_balanced` against the heuristic over the 280 simple-majority cells
with `N >= 3` and `rho > 0`:

| statistic | measured / heuristic |
| --- | ---: |
| minimum | 0.77 |
| median | 1.43 |
| maximum | 3.94 |
| cells where heuristic understates (`> 1.05x`) | 238 / 280 |
| cells where heuristic overstates (`< 0.95x`) | 4 / 280 |

At `p = 0.75`:

| N | rho | measured `n_eff` | heuristic | ratio |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 0.250 | 3.59 | 2.50 | 1.44 |
| 5 | 0.500 | 2.54 | 1.67 | 1.53 |
| 11 | 0.250 | 5.92 | 3.14 | 1.88 |
| 11 | 0.500 | 3.52 | 1.83 | 1.92 |
| 21 | 0.250 | 7.17 | 3.50 | 2.05 |
| 21 | 0.500 | 4.03 | 1.91 | 2.11 |

### The failure mode: a ceiling the heuristic does not have

The four overstating cells are not noise. They share a structure: high accuracy, low
correlation, large panel. Under the mixture, balanced panel error is

`E(N) = rho (1 - p) + (1 - rho) E_indep(N, p)`

so as `N -> infinity` it floors at `rho (1 - p)` — the shared branch cannot be outvoted, only
diluted. Effective size therefore floors too, at the `n` solving `E_indep(n, p) = rho (1 - p)`.
The heuristic has no accuracy term and rises to `1 / rho` instead.

The simulation matches that closed form (`p = 0.90`, `rho = 0.125`, 100 seeds):

| N | measured balanced error | predicted |
| ---: | ---: | ---: |
| 3 | 0.03716 | 0.03700 |
| 5 | 0.02015 | 0.01999 |
| 7 | 0.01501 | 0.01489 |
| 9 | 0.01333 | 0.01328 |
| 11 | 0.01249 | 0.01276 |
| 15 | 0.01251 | 0.01253 |
| 21 | 0.01243 | 0.01250 |

and the measured `n_eff` saturates at 4.60 for `N = 11, 15, 21`, against an analytic ceiling of
4.59 and a heuristic asymptote of 8.00. An independent 9-verifier panel at `p = 0.90` has
balanced error `0.000891`; the real panel delivers `0.0125`, **14x worse**.

### Where the heuristic is unsafe

Ceiling by accuracy and correlation; `*` marks cells where the ceiling sits *below* the
heuristic asymptote `1/rho`, i.e. where the heuristic is optimistic:

| rho | `1/rho` | p=0.55 | p=0.65 | p=0.75 | p=0.85 | p=0.90 | p=0.95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.125 | 8.00 | >=199 | 30.48 | 11.61 | 6.08 `*` | 4.59 `*` | 3.33 `*` |
| 0.250 | 4.00 | >=199 | 19.00 | 7.74 | 4.36 | 3.31 `*` | 2.75 `*` |
| 0.500 | 2.00 | 56.28 | 8.77 | 4.19 | 2.68 | 2.39 | 2.17 |
| 0.750 | 1.33 | 16.99 | 3.83 | 2.33 | 1.84 | 1.69 | 1.58 |

(`>=199` is the analyzer's `nmax = 201` search cap, not a converged value.)

The unsafe corner is **accurate verifiers with modest shared dependence** — precisely the
regime IDKMesh is trying to build. The heuristic is conservative where verifiers are weak,
which is where its conservatism costs the least.

### Consequence for IDKMesh

1. Do not size a verifier panel with `N / (1 + (N-1) rho)`. It is an intuition, not a budget.
2. Compute the ceiling `E_indep(n, p) = rho (1 - p)` first. If the ceiling is below the target
   confidence, **no panel size reaches it** and more reviewers are wasted spend; the only
   remaining moves are raising `p` or lowering `rho`.
3. This sharpens E012's warning. E012 showed correlation destroys panel benefit; E015 shows the
   standard correction for it is itself optimistic in the regime that matters.

### Limitations

- All of this is inside the shared-shock mixture. A different dependence structure with the
  same pairwise `rho` would give a different ceiling; the heuristic's failure is demonstrated
  against this model, not against real reviewer panels.
- The ratio table uses the QD strategy's rates at quorum `0.5`; other quorums are analyzed in
  the sections above.
- `n_eff` above ~199 is censored by the analyzer's search cap.

## Full grid: where the optimal quorum actually is

The first sweep varied quorum at two levels (`0.5`, `0.7`), so it could only report a
*crossover* between them. That was recorded as an open limitation. This section closes it with
a second, larger sweep.

```text
verifiers   = 1, 3, 5, 7, 9, 11, 15, 21
accuracy    = 0.55 .. 0.95 step 0.05
correlation = 0.0 .. 1.0 step 0.125
quorum      = 0.5, 0.6, 0.7, 0.8
seeds       = 150
cells       = 8 x 9 x 9 x 4 = 2592
```

Artifact: `experiments/results/E015-verification-phase-diagram-full-raw.jsonl.gz` (2592 cells,
no duplicates, every cell 150 seeds and all three strategies).

### Quorum is not the free parameter it looks like

Quorum acts only through the acceptance threshold

`need = floor(quorum * n) + 1`

so distinct nominal quorums are frequently the *same decision rule*:

| n | q=0.5 | q=0.6 | q=0.7 | q=0.8 | distinct rules |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 1 | 1 | 1 | 1 |
| 3 | 2 | 2 | 3 | 3 | 2 |
| 5 | 3 | 4 | 4 | 5 | 3 |
| 7 | 4 | 5 | 5 | 6 | 3 |
| 9 | 5 | 6 | 7 | 8 | 4 |
| 21 | 11 | 13 | 15 | 17 | 4 |

Only `n >= 9` resolves all four quorums into four different rules. Everything below is
therefore keyed on the realised threshold `need/n` and restricted to the **324 cells with four
distinct rules** (`n = 9, 11, 15, 21`). Reporting nominal quorum instead would claim resolution
the grid does not have.

### Result 1 — the optimum is usually interior

`interior` = the best rule is strictly between the loosest and strictest available, i.e. a
two-level sweep at the endpoints would have missed it.

| false-accept cost | mean optimal `need/n` | interior optimum |
| ---: | ---: | ---: |
| 1 | 0.540 | 1 / 324 (0.3%) |
| 2 | 0.568 | 71 / 324 (21.9%) |
| 5 | 0.620 | 145 / 324 (44.8%) |
| 10 | 0.656 | 178 / 324 (54.9%) |
| 25 | 0.686 | 186 / 324 (57.4%) |
| 50 | 0.709 | 169 / 324 (52.2%) |
| 100 | 0.729 | 147 / 324 (45.4%) |

Two things follow.

1. **At balanced cost, simple majority is right** — the optimum is the loosest rule in 99.7% of
   cells. E015's earlier finding survives.
2. **Once false accepts are more expensive than false rejects, the optimum moves off both
   endpoints in roughly half the cells.** A two-level sweep does not merely lose precision
   there; it reports the wrong rule. The crossover reported earlier was real, but it was a
   crossover, not an optimum, exactly as flagged.

Mean optimal threshold rises monotonically with false-accept cost (`0.540 -> 0.729`), which is
the expected direction and a sanity check on the measurement.

### Result 2 — stricter quorums are for *weak* verifiers, not strong ones

Optimal `need/n` at false-accept cost 10, `n = 21`:

| rho \ p | 0.55 | 0.60 | 0.65 | 0.70 | 0.75 | 0.80 | 0.85 | 0.90 | 0.95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.000 | 0.81 | 0.62 | 0.62 | 0.62 | 0.62 | 0.52 | 0.52 | 0.52 | 0.52 |
| 0.250 | 0.81 | 0.62 | 0.62 | 0.62 | 0.62 | 0.52 | 0.62 | 0.62 | 0.52 |
| 0.500 | 0.81 | 0.62 | 0.62 | 0.62 | 0.62 | 0.62 | 0.52 | 0.71 | 0.52 |
| 0.750 | 0.81 | 0.62 | 0.62 | 0.62 | 0.62 | 0.62 | 0.71 | 0.71 | 0.52 |
| 1.000 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 | 0.52 |

- The strongest dependence is on **accuracy**, not correlation. Barely-better-than-chance
  verifiers (`p = 0.55`) want a strict threshold (`0.81`); accurate verifiers want simple
  majority. The intuition that "unreliable reviewers mean we should demand consensus" is the
  one this table supports; "correlated reviewers mean we should demand consensus" is not.
- The `rho = 1.0` row is uniformly `0.52` because a fully correlated panel votes as one
  verifier: every threshold produces identical behaviour, and ties resolve to the loosest rule.
  This is a degenerate row, not evidence that simple majority is good at `rho = 1`.
- Correlation does shift the optimum at high accuracy (the `0.71` entries at `p = 0.85..0.90`),
  but weakly and non-monotonically at this seed count.

### Result 3 — the heuristic falsification replicates

Re-running the `N_eff` comparison of the previous section on the full grid (504 simple-majority
cells with `n >= 3`, `rho > 0`, versus 280 before):

| statistic | 630-cell grid | full 2592-cell grid |
| --- | ---: | ---: |
| min ratio | 0.77 | 0.56 |
| median ratio | 1.43 | 1.37 |
| max ratio | 3.94 | 4.32 |
| optimistic cells | 4 / 280 | 14 / 504 |

The conclusion is unchanged and the optimistic tail is worse, because the full grid reaches
`p = 0.95`, where the accuracy-dependent ceiling bites hardest.

### Limitations

- Only `n >= 9` supports a four-rule comparison, so Results 1 and 2 speak to larger panels;
  small panels genuinely cannot express four distinct quorums.
- The grid samples four quorum levels. An optimum "interior" to these four is not proven to be
  the global optimum over all thresholds `1..n` — it establishes that the endpoints are wrong,
  not that `0.6`/`0.7` are exactly right.
- Ties resolve to the loosest rule; at `rho = 1` this makes the whole row degenerate.
- False-accept cost is exogenous here. IDKMesh has no calibrated value for it, and Result 1
  shows the answer depends on it strongly.
- All cells use the QD strategy's rates, 150 seeds, and the shared-shock mixture.

### Compute provenance

Four `Standard_F32s_v2` VMs (Xeon 8272CL, 32 vCPU each, 128 vCPU total) across
`eastus2` and `uksouth`, index-strided into four shards of 648 cells, 150 seeds per cell,
~56 minutes wall clock. All four ran byte-identical `sim/e015_worker.py` and
`sim/emergence_sim.py` to the committed sources (md5 verified before harvest). The VMs were
destroyed after the data was verified locally.
