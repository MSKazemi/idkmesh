# E019 — E013's aggregation rule under the dependence model E017 measured

**Status: E013's crossover is robust to the model's *shape*, and disappears
entirely when the declared groups are not actually independent.**

## Why

E013 asked when counting every reviewer equally becomes worse than aggregating
within declared independence groups and giving each group one vote. Its answer,
for an 11-verifier panel in groups `[7,1,1,1,1]` at accuracy `0.75`: naive
majority wins at correlation `0`, group balancing wins from `0.25` upward.

That result was computed under the shared-shock mixture. E017 measured a real
panel and found two things that bear on it:

1. the shared-shock **shape** is wrong — it assigns near-zero probability to a
   group failing partially;
2. verifiers sharing **no declared attribute** still shared `53%` of their
   errors, so "independent groups" is not a description of a real panel.

E019 tests both.

```bash
python -m pytest -q tests/test_e019_group_independence.py
```

## 1. The crossover survives the shape change

Error rates for the E013 reference panel, 200 000 trials per cell:

| `rho` | shared-shock naive / balanced | item-difficulty naive / balanced |
|---|---|---|
| 0.000 | **0.0340** / 0.0650 | **0.0345** / 0.0654 |
| 0.125 | **0.0606** / 0.0697 | **0.0741** / 0.0796 |
| 0.250 | 0.0883 / **0.0755** | 0.1099 / **0.0886** |
| 0.500 | 0.1410 / **0.0835** | 0.1718 / **0.0995** |
| 1.000 | 0.2501 / **0.1034** | 0.2511 / **0.1034** |

The crossover sits at `rho = 0.25` under **both** models. E013's conclusion does
not depend on the shared-shock shape — a useful robustness result, and the
opposite of what happened to E015's ceiling in E018.

(The shared-shock column reproduces E013's published figures: about `24.55%`
naive against `10.27%` balanced at full correlation.)

## 2. The crossover disappears when groups share task difficulty

E017's measurement says the declared groups in a real panel are not independent.
Modelling that — one task difficulty drawn per work unit, every group erring at
that rate — removes group balancing's advantage completely:

| `rho` | naive | balanced | winner | naive advantage |
|---|---|---|---|---|
| 0.000 | **0.0345** | 0.0659 | naive | −0.0314 |
| 0.125 | **0.1200** | 0.1366 | naive | −0.0166 |
| 0.250 | **0.1719** | 0.1809 | naive | −0.0090 |
| 0.500 | **0.2232** | 0.2255 | naive | −0.0023 |
| 0.750 | **0.2448** | 0.2449 | naive | −0.0001 |
| 1.000 | 0.2492 | 0.2492 | tie | 0.0000 |

**Group balancing never wins at any correlation.** The two rules converge to a
tie at `rho = 1`, where both report `0.2492 ~= 1 - accuracy` — the panel has
collapsed to a single verifier and no aggregation rule can recover anything.

The mechanism is straightforward. Group balancing pays a real cost: it discards
the extra votes inside the large group. That cost is worth paying only when the
small groups supply evidence the large group does not have. When every group
errs on the same hard work units, they supply nothing extra, and the discarded
votes are pure loss.

## What this means

E013 already warned that IDKMesh "should not blindly discount reviewers by
metadata group" and should "estimate independent information from observed
evidence". E019 gives that warning a quantitative form and a sharper edge:

> Group balancing is not a safe default. It beats naive majority only when the
> declared groups carry genuinely independent evidence. E017 measured a real
> panel whose declared groups did not, and in that regime balancing is never
> better and is worse by up to 3 percentage points.

The practical rule is a measurement, not a policy: **before weighting by
declared groups, check whether cross-group error correlation is actually lower
than within-group correlation, and by how much.** E017's panel had `0.526`
across against `0.892` within — a real gap, but nowhere near the independence
that balancing assumes.

## What changed in the code

`sim/verification_aggregation_sim.py` gains two options, both off by default so
E013 reproduces exactly:

- `dependence={"shared-shock","item-difficulty"}` — the within-group model;
- `cross_group=True` — draw one task difficulty for the whole panel instead of
  one per group.

## Limitations

- The reference panel is a single geometry (`[7,1,1,1,1]` at accuracy `0.75`).
  E013 chose it to make the effect visible; the crossover location is a property
  of that geometry, not a universal constant.
- `cross_group=True` is the extreme case — difficulty shared *completely* across
  groups. E017 measured partial sharing (`0.526` across against `0.892` within),
  which lies between the two columns reported here. This experiment brackets the
  real case rather than reproducing it.
- Both regimes still assume every verifier has the same marginal accuracy.
- Truth is sampled 50/50. A skewed base rate changes the error rates, though not
  the ordering of the two rules.
