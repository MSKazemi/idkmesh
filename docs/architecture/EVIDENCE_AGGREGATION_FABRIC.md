# Evidence Aggregation Fabric

**Status:** normative extension to `ALGORITHM_COLLABORATION_FABRIC.md` v0.1  
**Date:** 2026-08-28  
**Authority:** evidence composition and decision-support only; no merge, approval, spending, compute activation, or autonomous-governance authority

## Purpose

The Algorithm Collaboration Fabric (ACF) reserves a distinct **aggregate evidence** stage between independent verification and governance. This document makes that stage executable and prevents a subtle composition failure:

> Different evidence algorithms answer different questions. Their outputs must not be multiplied, averaged, or renamed into one synthetic confidence score.

IDKMesh now has several mathematically distinct evidence channels:

- verifier discrimination / calibration;
- correlation-aware Bayesian evidence strength;
- a sharp count-contamination envelope for up to `f` arbitrary accepted reports;
- anytime-valid sequential evidence for repeated experiments;
- anytime-valid temporal drift alarms;
- deterministic governance hard guards.

The Evidence Aggregation Fabric (EAF) treats these as a **lattice of typed constraints**, not a scalar funnel.

---

## 1. Canonical evidence flow

```text
raw verifier / experiment evidence
        |
        v
+-----------------------------+
| provenance + admission      |
| exact scope/claim/revision  |
+-------------+---------------+
              |
              v
+-----------------------------+
| discrimination/calibration  |
| useful instrument?          |
+-------------+---------------+
              |
              v
       +------+-------------------------+
       |                                |
       v                                v
+----------------------+      +--------------------------+
| correlation channel  |      | contamination channel    |
| probabilistic model  |      | deterministic <= f model|
| effective evidence   |      | sharp honest-mean range |
+----------+-----------+      +------------+-------------+
           |                               |
           +---------------+---------------+
                           |
                           v
                 +---------+---------+
                 | typed evidence    |
                 | bundle            |
                 | NO scalar merge   |
                 +---------+---------+
                           |
                           v
                 +---------+---------+
                 | sequential        |
                 | repeated-effect   |
                 | evidence          |
                 +---------+---------+
                           |
                           v
                 +---------+---------+
                 | temporal drift    |
                 | regime-change     |
                 | guard             |
                 +---------+---------+
                           |
                           v
                 experiment_candidate
                           |
                           v
                 hard governance / integration
```

The diagram is conceptual rather than a claim that every channel must be computed in one process. In implementation, the composer receives already provenance-bound typed signals and checks that they refer to the same scope, claim, and source revision.

The constitutional/hard-guard layer remains globally dominant and may block at any point. The composer therefore records all blockers but returns `guarded` whenever the hard governance signal fails.

---

## 2. Why a lattice instead of one confidence number

These channels have incompatible semantics:

| Channel | Question answered | Typical output | What it does **not** mean |
| --- | --- | --- | --- |
| provenance | Are these artifacts/reports bound to the intended claim/revision? | valid/invalid | correctness |
| discrimination | Does the evaluator distinguish useful from inert/bad cases? | pass/fail + calibration evidence | independence |
| correlation | Under a declared dependence/reliability model, how much effective evidence is present? | posterior + effective votes | Byzantine robustness or proven independence |
| contamination | What honest-report mean is possible if at most `f` accepted reports are arbitrary? | sharp `[L_f,U_f]` + certificate | external truth or Sybil resistance |
| sequential | Under a bounded common-mean model, is repeated effect evidence strong enough under optional stopping? | anytime interval + candidate/observe | stationarity |
| drift | Is there evidence of a bounded temporal mean change under the scan model? | change/no-change alarm | proof of stationarity or causality |
| hard guard | Does the current governance/safety invariant permit stronger action? | pass/fail | statistical evidence |

A posterior probability and a count-contamination interval cannot be multiplied into a mathematically meaningful “combined confidence” without introducing a new joint model. Likewise, “no drift detected” is not an extra probability of correctness.

Therefore the machine-readable composer deliberately emits:

```json
{
  "composite_confidence": null,
  "scalarized_score": null,
  "double_counting_claim": false
}
```

Any downstream consumer that needs a new scalar objective must define and review a new observation/joint model rather than silently inventing one.

---

## 3. Typed signal contract

Each evidence channel uses the ACF-style envelope:

```json
{
  "signal_id": "...",
  "producer": "algorithm/version",
  "scope_id": "stable target / experiment / work unit",
  "claim_id": "the exact proposition being evaluated",
  "signal_type": "provenance|discrimination|correlation|contamination|sequential|drift|hard_guard",
  "observation_model": "named mathematical/deterministic model",
  "evidence_mass": "model-specific count/ESS/digest set",
  "uncertainty": "model-specific uncertainty or not-applicable",
  "assumptions": [],
  "failure_modes": [],
  "evidence_refs": [],
  "source_revision": "exact immutable revision",
  "authority_ceiling": "observe|recommend|propose",
  "payload": {}
}
```

### Alignment invariant

All channels in one composition must have exactly the same:

```text
scope_id
claim_id
source_revision
```

Evidence about a different candidate, a different claim, or an earlier commit cannot be combined merely because its numeric direction is favorable.

A mismatch is a validation error rather than a statistical penalty.

---

## 4. Channel ownership

### 4.1 Provenance

Owns identity/revision/evidence binding.

Typical payload:

```json
{"valid": true}
```

If provenance fails, the result is `observe_invalid_provenance` even when every numeric channel is favorable.

### 4.2 Discrimination

Owns whether the verifier/evaluator is informative enough to deserve downstream aggregation.

Typical payload:

```json
{"passed": true}
```

This encodes the lesson from the E016 verifier work: diversity/correlation of constant or non-discriminating instruments is not useful evidence.

### 4.3 Correlation-aware evidence strength

Owns probabilistic dependence/reliability discounting, currently represented by `bayesian_vote_posterior()` and its effective-vote mass.

Typical payload:

```json
{
  "posterior_probability": 0.92,
  "effective_votes": 3.4
}
```

The EAF can require a reviewed minimum effective-evidence mass. A very high posterior with too little effective evidence remains `observe_correlation_uncertainty`.

This prevents a favorable point probability from compensating for a nearly singular evidence panel.

### 4.4 Count-contamination envelope

Owns worst-case robustness to a declared maximum number `f` of arbitrary **accepted** reports.

Typical payload:

```json
{
  "certificate": "support_certified",
  "max_faults": 1,
  "honest_mean_lower": 0.72,
  "honest_mean_upper": 0.91
}
```

Certificates:

```text
support_certified
reject_certified
uncertain_under_fault_budget
```

An uncertain envelope blocks a positive nomination even when the naive mean or Bayesian channel is favorable.

The fault model is not Sybil resistance: identity/admission must make the statement “at most `f` accepted reports are arbitrary” credible.

### 4.5 Sequential evidence

Owns repeated-experiment effect evidence under optional stopping.

Typical payload:

```json
{
  "decision": "experiment_candidate",
  "lower_confidence": 0.14,
  "upper_confidence": 0.31
}
```

A sequential candidate remains a nomination only.

### 4.6 Drift

Owns temporal regime-change blocking.

Typical payload:

```json
{"detected_change": false}
```

If a change is detected, the EAF returns `observe_drift`. It does not delete history or infer causality.

### 4.7 Hard governance guard

Owns constitutional/current-state permission for stronger bounded action.

Typical payload:

```json
{"passed": true}
```

This is conjunctive and non-compensatory. No statistical evidence can offset a failed hard guard.

---

## 5. Decision lattice

The executable composer retains **all** blockers but selects one bounded operational recommendation using a deterministic priority:

```text
hard guard failure
  -> guarded

invalid provenance
  -> observe_invalid_provenance

non-discriminating verifier/evaluator
  -> observe_non_discriminating

insufficient correlation-adjusted effective evidence
  -> observe_correlation_uncertainty

robust contamination rejection
  -> insufficient_support

contamination envelope overlaps decision boundary
  -> observe_adversarial_uncertainty

temporal change detected
  -> observe_drift

sequential evidence not yet a candidate
  -> observe / insufficient_effect

all required channels adequate
  -> experiment_candidate
```

The priority determines the **single recommendation**, not which facts are retained. For example, if a hard guard fails while drift and contamination uncertainty are also present, all three blocker records remain in the artifact.

This is important for repair planning: solving one blocker must not hide the others.

---

## 6. Non-compensation laws

The EAF encodes several laws that should remain true across future implementations.

### Law A: governance cannot be compensated

```text
hard_guard_failed + arbitrarily strong evidence
    -> guarded
```

### Law B: provenance cannot be compensated

```text
wrong revision/claim/scope + favorable statistics
    -> reject composition / observe_invalid_provenance
```

### Law C: poor discrimination cannot be repaired by apparent independence

```text
non-discriminating evaluator + low measured correlation
    -> observe_non_discriminating
```

### Law D: arbitrary-report uncertainty cannot be repaired by a favorable probabilistic model

```text
Bayesian posterior high
AND contamination envelope crosses threshold
    -> observe_adversarial_uncertainty
```

### Law E: a strong pooled effect cannot compensate for a detected regime change

```text
sequential experiment_candidate
AND drift detected
    -> observe_drift
```

### Law F: no channel creates integration authority

```text
all evidence channels clear
    -> experiment_candidate
    != merge / approve / activate
```

---

## 7. Relationship to the ACF role matrix

This extension adds two explicit evidence roles to the ACF and refines the existing aggregate-evidence stage:

| Algorithm family | Owns | May influence | Must not own |
| --- | --- | --- | --- |
| correlation-aware aggregation | probabilistic effective evidence under declared dependence/reliability model | verifier evidence strength | independence as fact, arbitrary-fault robustness, merge authority |
| adversarial/count-contamination envelope | sharp honest-report mean range for `<= f` arbitrary accepted reports | robust support/reject/uncertainty certificate | truth, Sybil resistance, Byzantine consensus, merge authority |
| Sequential Evidence Kernel | anytime-valid repeated-effect evidence | experiment nomination | stationarity, merge/activation |
| Anytime Drift Guard | temporal mean-change alarm | whether historical evidence may be pooled without regime review | stationarity proof, causality, history deletion, merge authority |
| Evidence Aggregation Fabric | scope-aligned blocker composition without scalar collapse | bounded evidence recommendation | new statistical model, truth, integration authority |

The original ACF remains the broader system architecture; this document is the normative evidence-stage specialization.

---

## 8. Relationship to human review sessions

The IDKGraph human review-session validator and this fabric solve different layers:

```text
review-session validator
    -> validates/describes one review artifact and its provenance disclosures

Evidence Aggregation Fabric
    -> composes several already accepted typed evidence signals for the same claim/revision
```

A structurally valid human review can still be correlated with another review, non-discriminating, or one of the `f` arbitrary accepted reports in a threat model. Conversely, the count-contamination certificate does not validate the provenance of a review artifact.

---

## 9. Relationship to identity and Sybil resistance

The contamination guarantee is only as meaningful as the upstream statement about accepted-report faults.

If one actor can cheaply create many accepted identities, then a report-count budget `f` may not represent an actor-count threat model.

Therefore this fabric keeps:

```text
sybil_resistance_claim = false
```

A future identity/admission layer may provide typed facts such as independent administrative domains, hardware roots, proof-of-personhood, economic cost, rate limits, or other diversity evidence. Such mechanisms require their own explicit threat models; they must not be retroactively inferred from the current report envelope.

---

## 10. Executable surface

- `scripts/evidence_aggregation_fabric.py` — typed signal validation, scope/claim/revision alignment, non-scalar blocker composition, deterministic recommendation;
- `tests/test_evidence_aggregation_fabric.py` — alignment, no-scalarization, non-compensation, missing-channel, blocker-retention, authority, and fail-closed invariants;
- `.github/workflows/evidence-aggregation-fabric.yml` — pinned contents-read CI that also runs the upstream correlation/sequential/drift/adversarial mathematical suites.

The implementation intentionally has no GitHub mutation functions. Its strongest output is `experiment_candidate`.
