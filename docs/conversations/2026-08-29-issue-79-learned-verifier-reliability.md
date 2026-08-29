# Conversation record — issue #79 learned verifier reliability

**Date:** 2026-08-29
**Repository issue:** #79

## Owner request

The project owner asked coding agents to work professionally in parallel on ten
unclaimed issues, solve them, push the work, and integrate only after repository
review and merge safeguards are satisfied.

## Bounded interpretation

Issue #79 was unassigned and had no open PR or matching remote branch. It was
claimed publicly before implementation. This work implements E025; the issue's
initial experiment label collided with the canonical ACO experiment. This work
does not self-merge; evidence needs independent review at the exact PR head SHA.

Required work includes deterministic calibration/held-out separation, learned
reliability and dependence baselines, matched review cost, classification and
calibration metrics, correlation-estimation error, effective evidence, history
sensitivity, distribution shift, harmful regimes, uncertainty-bearing JSON,
documentation, and CI coverage.

## Decisions

- Preserve E013's `[7,1,1,1,1]` geometry with heterogeneous group accuracy.
- Freeze a model learned only from calibration. Prediction accepts
  `(votes, frozen_model)` and has no truth input.
- Keep declared groups only as an oracle reference. Learned groups use only
  calibration error correlations.
- Retain E015's `N_eff` formula as an explicitly unsafe baseline and add a
  calibration-observed alternative.
- Evaluate shared-shock and item-difficulty shapes so E017/E018 constrain E025.
- Report directional correlation error and high-confidence mistakes.
- Preserve reliability and dependence shifts where learned weighting loses.

## Exact-diff review correction

A later review questioned whether the effective-size helper compared a
majority-correct probability with group error. Direct evaluation showed the
summation is over `k < majority` correct votes, so it already computes majority
*error*: for `n=1, p=.75` it is `.25`, and for `n=3` it is `.15625`. Inverting
the comparison would have introduced the reported bug. The existing
`independent_error` error-to-error comparison was retained, its meaning was
documented, and the two known cases were added as regression tests.

A separate exact-diff review then found that `empirical_neff` selected only the
nearest odd integer, whereas E015 defines effective size by continuous linear
interpolation between bracketing odd sizes. E025 now reuses E015's canonical
`effective_n`, fails closed to one when a short-history reference accuracy is
not above chance, and tests an interpolated value between `n=1` and `n=3`. The
committed artifact is now validated against the strengthened schema and
reproduced in full by the focused test suite.

## Findings

In the 20-seed reference run, combined learning improves on naive majority in
all six stable cells and hurts in six shift cells. At 200 history claims under
stable item difficulty, error falls from `.2312` to `.0597`; under reliability
reversal it rises from `.1071` to `.2182`.

When dependence emerges after calibration, combined learning slightly improves
decision error but worsens Brier score and produces roughly nineteen times as
many high-confidence errors. Better classification alone does not establish
safer confidence.

## Community impact and open questions

The CLI, schema, committed artifact, tests, and experiment document make the
result reproducible with local/public CI and no project spend. The claim is
explicitly synthetic and negative regimes remain discoverable. Follow-up work
must determine how to gate learned weights under domain shift, represent shared
blind spots beyond pairwise correlation, and test the method on bounded software
tasks with independent delayed ground truth.
