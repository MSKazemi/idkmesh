# Anytime Drift Guard

Status: experimental mathematical control-plane primitive. Read-only; no repository integration authority.

## Purpose

The Sequential Evidence Kernel protects IDKMesh against optional stopping while a bounded common-mean model remains credible. That leaves a separate failure mode: the data-generating regime itself may change.

Pooling evidence across a real regime shift can produce a precise answer to the wrong question. The Anytime Drift Guard therefore tests the **common-mean assumption** before a strong pooled effect is allowed to become an experiment candidate.

It is a blocking observer, not an actuator.

## 1. Fixed split test

For bounded observations `X_i in [a,b]`, consider a prefix ending at time `t` and split it at `k`:

```text
before = X_1 ... X_k
 after = X_(k+1) ... X_t
```

Let

```text
D_(t,k) = mean(after) - mean(before).
```

Under the null hypothesis that both windows have the same expectation, Hoeffding's inequality for the weighted difference of the two sample means gives

```text
P(|D_(t,k)| >= eps)
  <= 2 exp(
       -2 eps^2 /
       ((b-a)^2 (1/k + 1/(t-k)))
     ).
```

For pairwise error budget `delta_(t,k)`, the threshold is therefore

```text
tau_(t,k)
  = (b-a)
    sqrt(
      0.5 (1/k + 1/(t-k))
      log(2 / delta_(t,k))
    ).
```

A fixed pair alarms when

```text
|D_(t,k)| > tau_(t,k).
```

## 2. Global error spending over indefinite scanning

A repository can inspect the stream repeatedly and can try many historical split points. Treating every scan as a fresh `delta=0.05` test would recreate the optional-stopping problem.

For minimum window size `m`, scanning begins at `t=2m`. Define

```text
Z_m = sum_(s=2m..infinity) 1/s^2.
```

At time `t`, there are

```text
M_t = t - 2m + 1
```

admissible split points. The guard allocates

```text
delta_(t,k)
  = delta / (Z_m t^2 M_t).
```

For each fixed `t`, summing over all admissible `k` cancels `M_t`:

```text
sum_k delta_(t,k)
  = delta / (Z_m t^2).
```

Then

```text
sum_(t=2m..infinity) sum_k delta_(t,k)
  = delta.
```

Combining each fixed-pair Hoeffding bound with a union bound controls the probability of **any false change alarm over all future observation times and all admissible historical splits** by at most `delta`, under the stated bounded common-mean assumptions.

The implementation evaluates `Z_m` with the Basel identity

```text
sum_(t=1..infinity) 1/t^2 = pi^2 / 6.
```

## 3. What an alarm means

An alarm means:

```text
bounded change detected at the configured sensitivity;
review the regime boundary before pooling evidence.
```

It does **not** prove a physical phase transition, causal mechanism, malicious actor, or exact change-point location.

No alarm means only:

```text
no bounded change detected at this sensitivity.
```

It does **not** prove stationarity.

## 4. Multiple metrics

If `M` metrics are scanned simultaneously, the implementation first allocates

```text
delta_metric = delta / M
```

and each metric then spends its share over all times and splits. This preserves a total family-wise false-alarm budget across the named metric family rather than treating every repository signal as a separate 5% test.

## 5. Composition with sequential effect evidence

For paired candidate/baseline evaluation, define the effect stream

```text
E_t = candidate_t - baseline_t,  E_t in [-1,1].
```

The combined gate splits one total error budget into a drift portion and an effect-evidence portion, then applies the following strict ordering:

```text
hard governance failure
    > detected effect-stream regime change
    > sequential effect evidence.
```

Operationally:

```text
if hard_guard_ok == false:
    GUARDED
elif anytime_drift_alarm == true:
    OBSERVE_DRIFT
else:
    delegate to paired sequential evidence gate
```

A strong pooled effect cannot compensate for a detected regime change, and neither statistics nor drift analysis can compensate for a failed governance guard.

## 6. Evidence preservation

A detected change does **not** automatically delete, truncate, relabel, or reset historical evidence. The output policy is explicit:

```text
preserve_all_evidence_and_review_regime_boundary
```

Automatic history deletion would make the detector an evidence-selection actuator and could create a new Goodhart surface. Any later segmentation/reset policy requires separately reviewed semantics and provenance.

## 7. Assumptions and limitations

The guarantee relies on bounded observations and a common expectation under an independent/common-mean or appropriate bounded martingale model when the null is true. Unknown dependence, adversarially selected telemetry, incorrect bounds, missing-not-at-random observations, and logging-policy errors can invalidate calibration.

The all-splits implementation is deliberately `O(n^2)`. It is intended for low-rate repository/evaluation evidence streams, not high-frequency raw telemetry. If scale requires pruning, a later implementation should preserve an explicit global error budget rather than silently reducing statistical guarantees.

## 8. Authority boundary

The guard cannot:

- merge, approve, push, label, close, or rewrite repository state;
- delete or reset evidence;
- activate compute;
- change branch protection;
- infer causality from a detected mean shift;
- convert absence of an alarm into proof of stationarity.

Positive/negative outputs are decision support only.

## Executable surfaces

- `scripts/anytime_drift_guard.py` — global-error-spending change scan, multi-metric scan, and drift-guarded paired gate;
- `tests/test_anytime_drift_guard.py` — budget, detection, direction, multi-metric, non-compensation, and history-preservation invariants;
- `.github/workflows/anytime-drift-guard.yml` — pinned, contents-read, cross-interpreter deterministic CI.
