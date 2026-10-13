# Verifier-Panel External-Validity Preregistration — Amendment v1.2

**Date:** 2026-10-13  
**Status:** pre-outcome computational-method amendment; no X6/X7 confirmatory verifier outcome is used here  
**Amends:** [v1 preregistration](VERIFIER_PANEL_EXTERNAL_VALIDITY_PREREG_V1.md) and [v1.1 amendment](VERIFIER_PANEL_EXTERNAL_VALIDITY_AMENDMENT_V1_1.md)  
**Issue:** [#1080](https://github.com/MSKazemi/idkmesh/issues/1080)  
**Parent program:** [#971](https://github.com/MSKazemi/idkmesh/issues/971)

## 1. Reason for this amendment

The v1.1 amendment froze two separate requirements:

1. the final confirmatory decision uses 10,000 repository-cluster and 10,000
   task-cluster bootstrap resamples; and
2. sample-size planning uses 10,000 simulated confirmatory cohorts.

A literal implementation that performs both 10,000-replicate confirmatory
bootstraps inside every one of 10,000 power-simulation cohorts is a nested
bootstrap with roughly 100 million bootstrap replicates **per clustering level
and per candidate sample size**, before accounting for the work inside each
replicate. At the larger task counts it is not a credible zero-project-spend
planning path.

No scientific outcome motivated this amendment. The problem was identified
during implementation review of #1080 before any X6/X7 confirmatory verifier
matrix existed.

This amendment changes **only the sample-size power approximation**. It does not
change the final confirmatory estimator, decision threshold, effect of interest,
number of confirmatory bootstrap replicates, or the allowed interpretation of
X6/X7.

## 2. Final confirmatory inference is unchanged

The confirmatory H1 decision remains exactly the v1.1 rule:

- compute the class-macro held-out log-score difference between item difficulty
  and shared shock;
- produce a repository-cluster percentile interval with **10,000** resamples;
- produce a task-cluster percentile interval with **10,000** resamples;
- use seed **20261011**;
- call a positive replication only when the 95% lower bound is above zero under
  **both** cluster schemes;
- one interval above zero and the other overlapping zero is unresolved.

The power planner records this final rule but does not execute 20,000 nested
bootstrap replicates inside each simulated cohort.

## 3. Power-planning approximation

### 3.1 Unchanged design constants

The following v1.1 quantities remain frozen:

- smallest effect of interest: delta0 = log(1.10) ≈ 0.09531 nats/item;
- target power: **0.90**;
- simulated cohorts per candidate sample size: **10,000**;
- seed: **20261011**;
- candidate task-count ladder:
  **50, 75, 100, 150, 200, 300, 500**, followed by the full eligible universe
  when different;
- minimum confirmatory source repositories for a cross-repository claim: **8**.

Calibration effects are still centered separately within the official-pass and
official-fail strata before +delta0 is injected. The observed calibration
effect direction therefore cannot make the planned sample smaller.

### 3.2 Cluster-jackknife / cluster-t planning interval

For each simulated cohort, compute the class-macro point estimate as the equal
average of the official-pass and official-fail mean log-score differences.

For each clustering level — repository and task — delete each cluster in turn
and recompute the macro estimate. The standard delete-one-cluster jackknife
variance is used, and the planning lower bound is the full-cohort estimate minus
the two-sided 95% Student-t critical value times the jackknife standard error.

A simulated cohort counts as a power success only when both the repository-level
and task-level lower bounds are above zero.

The estimated power is the success fraction over the 10,000 simulated cohorts.

This is a **sample-size planning approximation**, not a replacement for the
confirmatory percentile bootstrap.

### 3.3 Small-cluster correction

Repository counts can be small, so the planner uses the two-sided 95% Student-t
critical value for the repository/task cluster degrees of freedom rather than
the Normal 1.96 threshold. Values through 30 degrees of freedom are fixed from
the standard t table; above 30 the deterministic implementation uses a
Cornish-Fisher expansion around the Normal 0.975 quantile.

This makes the planning interval more conservative than a Normal approximation
when the repository count is small.

## 4. Repository-count realism

The simulated cohort must not contain more independent repository clusters than
the actual eligible confirmatory universe.

For candidate task count N, the simulated repository count is the smaller of N
and the eligible repository count, subject to at least eight repositories.

Calibration repository profiles may be resampled with replacement to represent
an unseen repository drawn from the same calibration population, but each
simulated cohort contains no more than the eligible repository count.

The eligible repository count is frozen from the pre-confirmatory candidate
inventory; it is not inferred from verifier outcomes.

## 5. Decision rule for sample size

For each task count on the frozen ladder:

1. generate 10,000 hierarchical cohorts from the centered calibration
   repository/task structure;
2. inject only +delta0;
3. calculate both cluster-jackknife/cluster-t lower bounds;
4. estimate power as the fraction with both lower bounds above zero.

Choose the smallest task count reaching power at least 0.90.

If no ladder value reaches 0.90, evaluate the complete eligible task universe.

If the complete universe remains below 0.90, the frozen result is
**underpowered_full_universe**. The study may still run and publish
descriptively, but it does not claim that the positive confirmatory design was
adequately powered for delta0.

If the admissibility requirements fail — including fewer than eight eligible
repositories or absence of either execution-label stratum — the result is
**infeasible**.

Neither status can be repaired after confirmatory unblinding by changing
delta0, alpha, cluster level, or the task-count ladder.

## 6. Canonical versus development power plans

The machine-readable plan is canonical only when all of these match this
amendment:

- 10,000 simulated cohorts;
- seed 20261011;
- delta0 = log(1.10);
- target power 0.90;
- the cluster-jackknife/cluster-t planning rule in Section 3;
- final confirmatory bootstrap count recorded as 10,000 per clustering level.

Smaller simulation counts may be used for unit tests and implementation
development, but the output must carry canonical=false and cannot satisfy the
S3 freeze gate.

A freeze manifest must re-parse the bound power plan and reject canonical=false,
an invalid self digest, or drift in any frozen setting.

## 7. Why this does not weaken the experiment

The confirmatory hypothesis test is not made cheaper or less strict. The final
repository/task bootstrap decision remains exactly as preregistered.

This amendment only replaces a computationally explosive **power-analysis
approximation** with a standard cluster-jackknife/cluster-t approximation that:

- preserves both clustering levels;
- retains a small-cluster t correction;
- uses the full 10,000 outer power simulations;
- cannot use the observed calibration effect direction;
- cannot simulate more repository clusters than the eligible universe;
- fails closed to underpowered/infeasible instead of lowering the target.

The approximation and its limitation must be reported in Paper A's methods if
the power plan is used.

## 8. Evidence boundary

Nothing in this amendment is evidence that E017 replicates.

Still required:

- a calibration dataset produced under the frozen competence and stage rules;
- a **canonical** power plan;
- a content-addressed freeze manifest;
- #804 before untrusted-patch execution where required;
- retained X6 evidence;
- retained independent-family X7/X10 evidence;
- the unchanged final 10,000-replicate confirmatory bootstrap analysis.

## 9. Provenance

This amendment was created during implementation review of #1080 on 2026-10-13.
The reviewer noticed that a literal nested 10,000-by-10,000 resampling design was
not operationally credible under the project's zero-spend constraint.

The change was made before any X6/X7 confirmatory verifier outcome was generated
or inspected. It is AI-assisted research design under maintainer direction and
is not independent peer review.
