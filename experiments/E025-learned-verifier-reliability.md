# E025 — Learned verifier reliability and dependence

**Status:** synthetic experiment complete; learned weighting helps in stable
regimes and fails materially under plausible shift. It is not production-ready
reputation.

## Research question

Can historical verified outcomes improve held-out aggregation after the model
is frozen, without hiding the new false-confidence risks introduced by learned
reliability and dependence?

The experiment removes E013's oracle assumption from learned methods. A
declared-group rule remains only as an oracle-like reference. All methods
consume exactly the same held-out votes at the same nominal review cost.

## Design

The synthetic panel keeps E013's `[7,1,1,1,1]` geometry. The seven-member group
has accuracy `0.72`; singleton accuracies are `0.62`, `0.74`, `0.84`, and
`0.90`. A labelled calibration stream estimates per-verifier `Beta(1,1)`
reliability posteriors, pairwise error correlations, dependence groups using
connected components above `rho=0.20`, and group-majority error.

The model is then frozen. The held-out evaluator passes only the vote vector to
the aggregator; truth is used afterward for scoring. Calibration and held-out
streams have separate deterministic seed formulas, so changing history length
cannot change held-out votes.

Seven methods are compared:

1. naive majority;
2. declared-group balancing (oracle reference only);
3. empirically inferred dependence groups;
4. learned `rho` in `N/(1+(N-1)rho)` (the unsafe E015 baseline);
5. calibration-observed effective evidence, without assuming dependence shape;
6. Bayesian/log-odds reliability weighting;
7. combined reliability and learned-correlation discounting.

Scores are evaluated by Brier score, false-accept, false-reject, total error,
and high-confidence error (`p <= 0.10` or `p >= 0.90`). Every aggregate has a
95% normal interval across deterministic seeds; posterior interval width makes
finite calibration uncertainty visible.

## Regimes and stopping rule

The committed run uses 20 seeds, 1,000 held-out claims per seed, and calibration
histories of 40, 200, and 1,000 claims. It tests stable shared-shock dependence,
stable item difficulty, reliability reversal, dependence disappearing, and
dependence emerging. The experiment succeeds only if it preserves at least one
stable improvement and one shift regime where learning hurts.

## Results

At 200 calibration claims, held-out total error is:

| regime | naive | oracle groups | inferred groups | `N_eff` heuristic | empirical evidence | reliability | combined |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stable shared shock | .2118 | .0766 | .0766 | .0766 | .1390 | .2015 | **.0653** |
| stable item difficulty | .2312 | .0788 | .0866 | .0797 | .0823 | .1829 | **.0597** |
| reliability shift | **.1071** | .1992 | .2049 | .1960 | .1947 | .1057 | .2182 |
| dependence dissipates | .0399 | .0502 | .0526 | .0532 | .0548 | **.0314** | .0568 |
| dependence emerges | .2519 | **.0808** | .2519 | .2519 | .2519 | .2286 | .2285 |

The stable item-difficulty combined result is `.0597` (95% CI
`.0563-.0630`) against naive `.2312` (`.2264-.2360`). The reliability-shift
result reverses that: combined `.2182` (`.2058-.2307`) against naive `.1071`
(`.1035-.1107`). Learned weighting clears the positive criterion but is not a
safe default.

### Finite-history sensitivity

| history | shared combined | item-difficulty combined | posterior CI width (shared/item) | exact group recovery (shared/item) |
| ---: | ---: | ---: | ---: | ---: |
| 40 | .1044 | .0881 | .259/.259 | .10/.15 |
| 200 | .0653 | .0597 | .118/.119 | 1.00/.90 |
| 1,000 | .0651 | .0594 | .053/.053 | 1.00/1.00 |

More history improves group recovery and shrinks uncertainty, but it cannot
protect against distribution shift. More confidently learning stale reliability
preserves the negative result.

### False confidence is distinct from decision error

When dependence emerges only after calibration, combined weighting has slightly
lower classification error than naive (`.2285` versus `.2519`) but a worse Brier
score (`.1801` versus `.1425`) and far more high-confidence errors (`.1198`
versus `.0063`). A headline error-rate improvement would conceal the exact
failure named by the issue.

## E015/E017/E018 constraints

- `N_eff` remains only a baseline. Learned-rho, true-calibration-rho, and
  calibration-observed effective counts separate estimation error from
  estimator bias.
- Calibration-observed effective size matches observed group *error* to
  `independent_error`: the binomial sum covers `k < majority` correct votes and
  its target is `1 - group_accuracy`. E015's continuous interpolation between
  bracketing odd panel sizes is reused rather than snapping to an odd integer.
  Regression tests pin the known `n=1` (`.25`) and `n=3` (`.15625`) errors at
  member accuracy `.75`, plus an interpolated value strictly between them.
- Directional correlation errors show when independence is overestimated.
- Both shared-shock and item-difficulty shapes are evaluated; pairwise `rho` is
  never treated as sufficient to determine panel error.
- E015's shared-shock ceiling is not applied to item difficulty because E018
  showed its regime is model-specific.
- The experiment does not model E020's irreducible shared-blind-spot floor.

## Reproduce

```bash
python sim/e025_learned_verifiers.py \
  --histories 40,200,1000 --heldout-trials 1000 --seeds 20 --pretty \
  > experiments/results/E025-learned-verifier-results.json
python -m pytest -q tests/test_e025_learned_verifiers.py
```

Machine-readable evidence:
[`results/E025-learned-verifier-results.json`](results/E025-learned-verifier-results.json),
validated by
[`../schemas/e025-learned-verifier-result.schema.json`](../schemas/e025-learned-verifier-result.schema.json).

## Limitations and next step

This is a synthetic binary panel with balanced prevalence, one clustering rule,
and no adversary. Intervals are descriptive, not anytime-valid. Correlation
shape, task mix, competence, and blind spots can shift. Nothing here licenses a
durable person/model reputation score. The next step is bounded software tasks
with delayed ground truth from independent hidden tests, with parameters scoped
by domain and time and a fail-closed response to unsupported shift.
