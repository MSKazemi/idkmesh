# Verifier-Panel External-Validity Replication — Preregistration v1

**Date:** 2026-10-07  
**Status:** preregistered design only; no confirmatory outcome data collected  
**Parent plan:** [issue #936](https://github.com/MSKazemi/idkmesh/issues/936)  
**Motivating evidence:** [E017](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md), [E018](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E018-dependence-model-shape.md), [E020](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E020-quorum-frontier-under-measured-shape.md)  
**Current manuscript:** [paper/main.tex](https://github.com/MSKazemi/idkmesh/blob/main/paper/main.tex)  
**Project compute policy:** zero project spend; no paid provider fallback

## 1. Why this replication exists

E017 measured one constructed panel of 25 partial test oracles over 72 candidates.
That panel showed four important behaviors:

1. substantial verifier error dependence;
2. a majority-vote panel no better than its own members;
3. partial majority failures that a fitted shared-shock mechanism could not reproduce;
4. an observed all-verifier blind-spot floor that changed the high-quorum frontier.

Those findings are internally reproducible, but their external validity is weak because
the verifier family and diversity structure were deliberately constructed.

This replication asks a narrower scientific question:

> **Does the dependence-shape result survive on a verifier panel whose members use materially different verification mechanisms and whose confirmatory tasks were not used to select the panel?**

The purpose is **not** to force replication. A result in which shared shock fits better,
no blind spot appears, or the panel cannot pass the competence screen is scientifically
valid and must be retained.

## 2. Confirmatory claim under test

### Primary hypothesis H1

On the held-out confirmatory corpus, a per-item difficulty model will predict the
verifier error-count distribution better out of sample than a two-parameter
shared-shock model matched at comparable complexity.

Operationally, let:

- \(k_i\) = number of panel verifiers wrong on confirmatory item \(i\);
- \(M_S\) = shared-shock model;
- \(M_D\) = per-item difficulty / beta-binomial model.

The primary estimand is the task-grouped out-of-sample log-score difference:

\[
\Delta_{D-S}
=
\frac{1}{m}
\sum_{i=1}^{m}
\left[
\log p_{M_D}(k_i)
-
\log p_{M_S}(k_i)
\right].
\]

**Replication criterion:** the task-group bootstrap 95% interval for
\(\Delta_{D-S}\) is strictly above zero.

**Falsification criterion:** the interval is strictly below zero.

**Unresolved:** the interval overlaps zero.

No alternative threshold will be introduced after confirmatory outcomes are visible.

## 3. Secondary questions

These are preregistered secondary analyses, not co-primary hypotheses.

### RQ2 — Is pairwise correlation sufficient?

Does matching mean verifier accuracy and pairwise error correlation reproduce:

- majority-vote error;
- the frequency of partial majority failures;
- unanimous failures;
- the full quorum frontier?

### RQ3 — Does declared heterogeneity correspond to empirical independence?

Compare within-family and cross-family pairwise error correlation.
The family labels are descriptive metadata, not assumed independence groups.

### RQ4 — Does the panel exhibit a shared blind spot?

Measure the confirmatory rate at which **all eligible verifiers are wrong**.
A non-zero observed rate is reported with finite-sample uncertainty; it is not
automatically called a population-level irreducible floor.

### RQ5 — Does the effective-votes heuristic transfer?

Compare the measured effective independent panel size with
\(N / (1 + (N-1)\rho)\) on the confirmatory panel.

This is secondary because contemporary work already establishes that correlated
judge panels can contain fewer effective votes than their nominal size.

## 4. Materially different replication family

The replication must differ from E017 in **both verifier mechanism and task cohort**.

### 4.1 Candidate task family

Use a frozen set of repository-scale or package-scale Python tasks with executable
acceptance criteria. Each task must provide:

- a pinned source revision;
- one known-correct baseline state;
- one or more candidate variants containing real or deliberately seeded defects;
- a hidden executable acceptance harness that decides the confirmatory label;
- no dependency on the candidate verifiers for that label.

The confirmatory cohort must contain at least **24 task groups** and at least
**72 labeled candidates** unless the preregistration is amended **before** any
confirmatory verdicts are inspected.

The cohort is frozen by:

- task identifiers;
- source commit/release;
- candidate patch digests;
- hidden acceptance-harness digest.

### 4.2 Verifier mechanisms

The target panel is heterogeneous across at least **three** mechanism families.

Eligible examples include:

1. independently authored visible unit/regression checks;
2. metamorphic or property-based checks;
3. static-analysis / invariant / contract checks;
4. type or schema checks where semantically relevant;
5. deterministic fuzzing or generated test checks;
6. domain-specific validation tools.

A family may contribute multiple deterministic configurations or seeds, but
changing only a random seed does **not** count as a new mechanism family.

The confirmatory panel target is **at least 20 eligible verifiers**.

If fewer than 20 pass the frozen calibration rules, the replication is recorded
as **infeasible under preregistration v1**. The competence threshold must not be
weakened to rescue the study.

## 5. Independence of ground truth

The hidden acceptance harness is not a panel member.

To be eligible:

- verifier source/configuration must not import the hidden harness;
- hidden cases must not be copied into visible verifier fixtures;
- a verifier may not be generated from hidden expected outputs;
- panel verdicts cannot determine or modify the hidden label;
- candidate labels are computed before panel aggregation;
- panel aggregation has no effect on the acceptance harness.

A shared dependency on the public task specification is unavoidable and must be
reported as a residual threat to validity.

## 6. Two-stage design

The study deliberately separates **panel selection** from **confirmatory evaluation**.

### Stage A — calibration / feasibility

Use a calibration corpus disjoint by task group from the confirmatory corpus.

Calibration may answer only:

- does each verifier run deterministically?
- does it produce a verdict for the intended task class?
- does it discriminate above chance?
- what family/configuration metadata should be frozen?
- does the proposed hidden-label path execute independently?

Calibration outcomes must not be included in confirmatory effect estimates.

#### Competence screen

For each verifier on calibration data, compute:

- sensitivity;
- specificity;
- Youden's \(J\);
- raw accuracy;
- constant-verdict rate.

Eligibility requires:

1. deterministic execution under replay;
2. non-constant verdict behavior;
3. \(J > 0\);
4. a preregistered one-sided permutation test for \(J\) passing the
   familywise correction across candidate verifiers.

The correction method and random seed are frozen in the analysis code before
confirmatory execution.

### Stage B — confirmatory held-out run

After the panel is frozen:

- no verifier is added, removed, reweighted, or retuned based on confirmatory outcomes;
- no task is removed for being "too easy", "too hard", or embarrassing;
- crashes/timeouts are retained under the failure policy below;
- all registered candidates receive verdicts from all eligible verifiers unless
  a predeclared execution failure occurs.

## 7. Failure and missingness policy

A verifier execution may end as:

- accept;
- reject;
- tool_error;
- timeout;
- not_applicable only where declared before the confirmatory run.

Primary analysis requires a complete binary verdict matrix.

Therefore:

- tool_error and timeout are **not silently dropped**;
- if a verifier exceeds the preregistered maximum missing/error fraction, the
  entire verifier is excluded by the frozen rule, not item-by-item;
- any such exclusion is reported and the primary analysis is rerun only if at
  least 20 verifiers remain;
- otherwise the confirmatory result is **infeasible / incomplete**, not repaired
  by changing thresholds.

The exact maximum missing/error fraction must be set from calibration before
Stage B and committed with the frozen manifest.

## 8. Models compared

The confirmatory analysis compares four prespecified model families.

### M0 — independent binomial

A baseline with verifier error probability determined by panel mean error and
no dependence.

### M1 — shared shock

A two-parameter mixture matching mean error and a dependence parameter.

### M2 — per-item difficulty

A beta-binomial model with the same two-parameter complexity class used in the
current manuscript.

### M3 — one-inflated per-item difficulty

A three-parameter model adding explicit mass for all-verifier failure.

M3 is secondary because it has additional flexibility.

## 9. Fitting and out-of-sample evaluation

### Grouping unit

The **task group** is the independence/resampling unit.
Multiple candidates from the same task are never treated as independent task samples.

### Cross-validation

Use deterministic grouped cross-validation:

- five folds when at least 25 task groups are available;
- otherwise leave-one-task-group-out.

Every candidate from one task stays in the same fold.

For each fold:

1. fit model parameters on training task groups only;
2. score the held-out task groups;
3. retain per-item log predictive density and predicted failure-count probabilities.

No confirmatory task may influence the panel-selection stage.

### Primary uncertainty

Compute a task-group bootstrap with **10,000 deterministic bootstrap replicates**
using a seed committed before Stage B.

Report:

- mean \(\Delta_{D-S}\);
- 95% percentile interval;
- median per-task contribution;
- number of task groups favoring each model.

No p-value substitution is used to overturn the preregistered decision rule.

## 10. Secondary metrics

Report, with task-group uncertainty where applicable:

- member sensitivity, specificity, Youden's \(J\), and accuracy;
- panel majority error;
- best-member error;
- mean pairwise error correlation;
- within-family vs cross-family correlation;
- observed effective independent panel size;
- Kish/design-effect estimate;
- partial-majority failure rate;
- unanimous failure rate;
- full acceptance-quorum frontier;
- RMSE of each fitted model against the measured quorum frontier;
- error-count histogram \(P(K=k)\).

Any exploratory metric added after unblinding must be labeled exploratory.

## 11. Blind-spot interpretation rule

An observed all-verifier miss is evidence about this finite panel/corpus only.

The manuscript may say:

> "The confirmatory panel exhibited an observed unanimous-miss rate of X."

It may **not** say:

> "All verifier panels have an irreducible floor X."

If zero unanimous misses are observed, report the corresponding upper uncertainty
bound rather than claiming the blind spot is absent in the population.

## 12. Stopping rule

The confirmatory run stops when the complete frozen cohort has been evaluated.

There is:

- no sequential stopping for significance;
- no extension because H1 is unresolved;
- no deletion of unfavorable tasks;
- no added verifier after seeing the confirmatory matrix.

A rerun is allowed only for a documented infrastructure fault that invalidated
execution, and both the original failure record and rerun provenance must be retained.

## 13. Leakage and contamination checks

Before unblinding analysis:

- hash the hidden harness;
- hash verifier configs;
- hash candidate artifacts;
- confirm no hidden-test file is in verifier inputs;
- confirm no result file from Stage B was used during panel selection;
- confirm task-group separation between calibration and confirmatory cohorts.

If confirmatory leakage is discovered after outcomes are visible, the cohort is
marked compromised. It is not silently regenerated and re-described as the original study.

## 14. Zero-project-spend execution gate

This project currently permits **$0 project-funded compute spend**.

Eligible execution paths include:

- local maintainer hardware;
- volunteer hardware with explicit opt-in;
- public-project GitHub Actions within terms;
- genuine free-tier resources within published limits.

There is no paid-provider fallback.

If no eligible path can run the frozen experiment, Step 2 records
**execution infeasible under current compute policy** rather than changing the design.

## 15. Required artifacts

Before Stage B:

- replication-manifest.json;
- frozen task/candidate inventory;
- hidden-harness digest inventory;
- verifier inventory and family labels;
- calibration report;
- analysis script with fixed bootstrap seed;
- exact commit SHA.

After Stage B:

- raw verifier-by-item verdict matrix;
- per-verifier execution status;
- hidden labels;
- model-fit artifacts;
- cross-validation predictions;
- bootstrap summary;
- human-readable experiment report;
- exact reproduction commands.

Raw negative and failure outputs must be retained.

## 16. Manuscript update gate

The current verifier manuscript must **not** be updated with replication claims
when only the preregistration or calibration exists.

A manuscript change is allowed only after:

1. Stage B is complete;
2. raw confirmatory evidence is committed;
3. analysis is reproducible from those artifacts;
4. evidence class is recorded in paper/CLAIM_EVIDENCE_MAP.md;
5. negative/null outcomes are included.

## 17. Interpretation matrix

| Confirmatory outcome | Interpretation |
| --- | --- |
| M2 clearly beats M1 | E017 dependence-shape result replicates on this materially different panel |
| M1 clearly beats M2 | E017 shape result is falsified as a transferable expectation; dependence is panel-specific |
| interval overlaps zero | external validity remains unresolved |
| <20 competent verifiers after calibration | replication infeasible under v1 competence gate |
| confirmatory leakage | cohort compromised; no confirmatory claim |
| zero unanimous misses | no observed blind spot on this cohort; report upper uncertainty bound |
| non-zero unanimous misses | observed finite-panel blind-spot rate; do not universalize it |

Every row is an acceptable scientific outcome.

## 18. Non-goals

This replication does not attempt to prove:

- that all LLM judges follow item-difficulty dependence;
- that the beta-binomial is a universal verifier model;
- that more verifiers are always harmful or helpful;
- that a blind spot must exist;
- that one quorum is universally optimal;
- that declared mechanism diversity guarantees independence;
- that IDKMesh's production verification policy is validated.

## 19. Relationship to current literature

Current literature already provides strong evidence that model/judge errors can be
correlated and that aggregation can fail under latent confounding.

This replication is intentionally narrower:

> **Can the shape of verifier dependence, measured through the error-count
> distribution and quorum frontier, transfer beyond E017's constructed
> partial-oracle panel?**

That is the external-validity gap the current manuscript explicitly leaves open.

## 20. Provenance

This preregistration was produced from the ordered publication plan in #936 after
Step 1 passed the repository PR gate. It is AI-assisted research design under
maintainer direction. It contains no confirmatory outcome and is not independent
scientific review.
