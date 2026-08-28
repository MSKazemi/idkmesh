# E018 — Which E015 conclusions depend on the shape of the dependence model?

**Status: positive result, with one correction to E015 and one strengthening of it.**

## Why

E012, E013 and E015 all model verifier dependence the same way: with probability
`rho` every verifier shares one correctness state, otherwise they are
independent. E017 measured a real panel and found that shape wrong — it assigns
near-zero probability to a panel failing *partially*, which is how most real
panel failures look, and it underestimated real panel error by 1.71x.

That raises an obvious question about everything built on it. E018 answers it by
recomputing E015's grid under both models **in closed form**, so the comparison
carries no simulation noise.

The two models take the **same two parameters** (accuracy, correlation) and
agree exactly at `rho = 0` and `rho = 1`. Any difference between them is
therefore attributable to shape alone, not to extra freedom.

```bash
python sim/e018_dependence_models.py
```

## Validation first

Given only the accuracy and correlation E017 measured, and predicting forward:

| | real (E017) | item-difficulty | shared-shock |
|---|---|---|---|
| panel error | 0.2083 | **0.1864** | 0.1202 |
| effective size | 1.00 | **1.37** | 2.75 |

The item-difficulty closed form lands within `0.022` of the measured panel
error; shared-shock is off by `0.088`. Neither is exact — item-difficulty is
still somewhat optimistic — but it is roughly 4x closer, from the same two
inputs.

## 1. The shape changes the predicted error almost everywhere

Across the 441 comparable cells of E015's grid at quorum 0.5:

```
item-difficulty predicts MORE error than shared-shock in 438/441 cells (99%)
error ratio (item/shock): median 1.27x, max 2.71x
```

The direction matches E017's measurement. **Every panel-error number in
E012/E013/E015 is optimistic**, typically by about a quarter and by as much as
2.7x.

## 2. E015's `N_eff` warning generalises — from 4% of the grid to all of it

E015 concluded that the standard `N_eff = N / (1 + (N-1) rho)` heuristic is
optimistic **for accurate verifiers**. That hedge was necessary under
shared-shock, where the heuristic is optimistic in only a small corner:

```
under shared-shock    : heuristic OVERSTATES independence in   17/441 cells (  4%)
under item-difficulty : heuristic OVERSTATES independence in  441/441 cells (100%)
```

Under the shape that matches reality the heuristic overstates independence in
**every single cell**. E015 reached the right conclusion for a narrow reason;
the correct statement is unconditional:

> Never size a verifier panel with `N / (1 + (N-1) rho)`. It overstates your
> independent evidence everywhere, not just at high accuracy.

E017 measured exactly this on a real panel: heuristic 1.66 against a measured
effective size of 1.00.

## 3. The accuracy-dependent ceiling is a shared-shock artifact — and the regimes invert

This is the correction. E015's ceiling — effective size saturating as the panel
grows — does not survive where E015 found it. Extending well past E015's largest
panel (`p=0.90`, `rho=0.125`, quorum 0.5):

```
    n   shared-shock  item-difficulty
    5           3.82             2.82
   11           4.57             3.93
   21           4.59             4.56
   41           4.59             4.89
   81           4.59             5.16
  151           4.59             5.40
```

Shared-shock pins at `4.59` and never moves. Item-difficulty crosses it around
`n = 21` and keeps rising. **In the accurate, weakly-correlated regime there is
no hard ceiling; adding verifiers keeps paying, slowly.**

The saturation is real, but it lives somewhere else. At `p=0.75, rho=0.5`:

```
   n=[3, 5, 7, 9, 11, 15, 21]
   shared-shock   : [2.0, 2.6, 2.9, 3.3, 3.5, 3.9, 4.1]   <- still climbing
   item-difficulty: [1.3, 1.4, 1.5, 1.5, 1.5, 1.6, 1.6]   <- flat almost at once
```

So the two models saturate in **opposite regimes**. Under the measured shape,
strong correlation is what caps a panel — and it caps it far harder and far
sooner than E015 reported (an effective size of about 1.6, not 4.1).

Practical consequence: E015's guidance on when to stop adding verifiers is
inverted over part of the space. Under item-difficulty, **high correlation is
the thing that makes extra verifiers worthless, and low accuracy amplifies it**;
high accuracy is not itself a reason to stop.

## What this changes in the repository

- `sim/emergence_sim.py` gains `--verifier-dependence {shared-shock,item-difficulty}`.
  The default is `shared-shock`, so E011/E012/E013/E015 reproduce byte-for-byte;
  the new model is opt-in.
- E015's published conclusions are **not retracted**. Its `N_eff` warning is
  strengthened to an unconditional one. Its ceiling result is re-scoped: it is a
  property of the shared-shock model, not of correlated verification in general.

## Limitations

- **Quorum is restricted to 0.5.** Both error functions here mean "the panel is
  wrong when fewer than `need` verifiers are correct", which coincides with an
  accept-threshold rule only at a symmetric majority. Above 0.5 they diverge —
  E017 hit exactly this on real data — and separating false accepts from false
  rejects needs the base rate of viable work, a property of the corpus rather
  than the panel. E015's quorum-frontier results are therefore untouched here.
- **The item-difficulty model is validated against one measured panel**, E017's,
  whose diversity structure was constructed. It fits far better than
  shared-shock, which is a low bar; it is not established as correct.
- A Beta difficulty distribution is a modelling choice. It is the natural
  two-parameter conjugate form, not something E017 measured the shape of.
- Both models assume verifiers are exchangeable — identical accuracy and a
  single common correlation. Real panels are heterogeneous, which E017 showed
  does not by itself explain the shared-shock gap, but which neither model here
  represents.
