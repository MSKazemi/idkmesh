# Continuation: anytime-valid drift guard

Date: 2026-08-28

User request: continue strengthening `MSKazemi/idkmesh` mathematically and implement the result using GitHub-native capabilities.

## Precondition work completed in this continuation

The prior Sequential Evidence Kernel was first completed and merged in #206. A real post-merge observation then exposed an evidence-quality ambiguity: GitHub artifact archive digests differed across Python jobs even though both mathematical jobs passed. Follow-up #208 hardened the proof by running Python 3.11 and 3.13 in one read-only job, byte-comparing the actual JSON outputs, and recording an explicit content SHA-256.

For exact PR #208 head `64c08f9f8b4aa5fa473627445e6b46564abb0544`, the retained mathematical payloads were byte-identical with content SHA-256:

```text
4ae8b760903f57ee4ae987efebae3de264d2925a40ca66438ee4e77e5a9bd7bd
```

PR #208 merged as:

```text
5004ce6f989f13e44b64e7f70b2bfdcb167781e2
```

At the start of the next mathematical pass, a direct branch read confirmed that exact commit as canonical `main`. GitHub still reported `main` as unprotected with required status-check enforcement off.

## Next assumption audited

The sequential confidence layer makes its model boundary explicit: optional-stopping validity does not solve distribution drift. If a candidate effect or repository signal changes regime, pooling all observations under one common mean can make confidence increasingly precise while becoming less relevant to the current state.

Repository code and PR search found no existing change-point / CUSUM / Page-Hinkley / anytime drift implementation. This made temporal non-stationarity a clean missing layer rather than duplicate work.

## Mathematical decision

Implement an all-splits bounded change detector with explicit global error spending.

For each observation time `t` and admissible historical split `k`, compare the before/after means with a two-sample Hoeffding threshold. Instead of assigning the full false-alarm probability to every pair, distribute one total `delta` across all future times and splits using a normalized reciprocal-square schedule.

For minimum window `m`:

```text
Z_m = sum_(s=2m..infinity) 1/s^2
M_t = t - 2m + 1
delta_(t,k) = delta / (Z_m * t^2 * M_t)
```

The sum over every future pair is `delta`, so a union bound controls indefinite repeated scanning under the stated bounded common-mean assumptions.

## Control-plane composition

The drift detector is composed with paired sequential experiment evidence using strict priority:

```text
hard governance guard
  > detected regime change
  > statistical effect nomination
```

A drift alarm returns `observe_drift`, preserves all evidence, and blocks experiment nomination pending regime review. It does not automatically reset history because automatic deletion/reset would itself be an evidence-selection actuator.

## Multi-metric discipline

When several metrics are scanned, total `delta` is divided across metrics before each metric spends its share over time/splits. This prevents the repository from creating an unbounded multiple-testing surface by adding more health signals.

## Current-main convergence

While the drift branch was being assembled, `main` advanced and added `docs/research/METRIC_UNCERTAINTY_V0_1.md` plus `scripts/metric_uncertainty.py`. That work is complementary: it explicitly limits its Beta-Binomial helper to suitable yes/no observations and says dynamical/queueing metrics require different models. The drift guard therefore remains a separate temporal observation model rather than modifying or overloading the Beta-Binomial contract.

## GitHub authority boundary

The implementation is isolated in a new dependency-free math module, tests, architecture documentation, and one path-scoped workflow. The workflow is designed with:

```text
permissions:
  contents: read
```

It uses immutable Action SHAs, runs Python 3.11 and 3.13 in one job, compares actual JSON demo bytes across interpreters, records an explicit SHA-256, and publishes evidence only.

It does not modify the live Evolution Loop, repository settings, branch protection, issue/PR metadata, or merge authority.

## CI falsification and correction

The first exact-merge-ref run for PR #212 produced a useful failure. Both Python 3.11 and Python 3.13 passed all 26 drift + sequential-evidence tests, but the cross-interpreter byte comparison failed before artifact publication.

The cause was not a theorem/test disagreement. Python 3.12 changed floating-point behavior in the built-in `sum()` implementation. The first drift implementation computed the reciprocal-square prefix in `Z_m` with:

```text
sum(1 / t^2 for t in range(...))
```

so Python 3.11 and 3.13 could produce slightly different floating normalizers and serialized thresholds even though every semantic invariant passed.

The correction is algorithmic rather than cosmetic: `reciprocal_square_tail()` now uses an explicit left-to-right IEEE-754 accumulator. The scan also computes that normalizer once and reuses it, improving both reproducibility and runtime. CI continues to require byte-for-byte equality; the disagreement was not rounded away or ignored.

This is an example of the repository's evidence discipline changing implementation details in response to observed execution rather than weakening acceptance criteria after a failure.

## Scientific boundary

A detected bounded mean change is not a claim of causality or a literal physical phase transition. No detected change is not proof of stationarity. Unknown dependence or adversarial observation selection can invalidate the calibration and must be modeled separately.
