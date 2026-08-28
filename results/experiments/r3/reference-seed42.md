# R3 Evolutionary Orchestration Evidence Report

**Status:** Synthetic mechanism experiment. Human review required; no autonomous promotion.

Split digest: `sha256:261e1edd128ee0492fd5b740a1576a0eeb1c5ef4cfb6ccbdf90989fac3f610f5`
Pre-heldout champion: `g-7d18f6c8917d`

## Held-out comparison

| Metric | Fixed baseline | Pre-heldout champion |
| --- | ---: | ---: |
| Verified success | 0.2917 | 0.6417 |
| Security failure | 0.0583 | 0.0208 |
| Regression | 0.0792 | 0.0542 |
| Compute/task | 5.6048 | 8.1963 |
| Latency/task | 8.3435 | 10.6808 |
| Human attention/task | 0.2525 | 0.0833 |

## Generalization / safeguards

- Final train-Pareto genomes evaluated on heldout: 47.
- Overfit flags: 12.
- Champion train→heldout success gap: 0.0733.
- Heldout success delta vs baseline: 0.3500.
- Heldout security delta vs baseline: -0.0375.
- Evidence supports consideration: True.
- Decision: **consider_for_separate human-reviewed experiment**.

Heldout families were not used for mutation, Pareto selection, survivor selection, or champion selection. This heldout split is considered burned after this report.

A favorable result can only motivate a separate human-reviewed experiment on independent real tasks; it cannot promote a policy into production.
