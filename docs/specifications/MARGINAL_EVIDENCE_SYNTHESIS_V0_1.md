# Marginal Evidence Cross-Cohort Synthesis v0.1

Status: experimental diagnostic contract  
Issue: #693  
Authority: diagnostic only

## Purpose

The command **idkmesh gate-marginal-synthesis** combines multiple already-produced
marginal-evidence-benchmark-report-v0.1 documents into one descriptive
cross-cohort report.

It answers a deliberately narrower question than routing:

> Across a frozen set of held-out benchmark cohorts, how often was each
> preregistered selector resolved, and what descriptive held-out deltas were
> observed when it was evaluated?

It does **not** choose a winning strategy, learn a threshold, modify a
RoutingDecision, create an EvaluatorPlan, accept a candidate, or grant Git
push/merge authority.

## Inputs

The command consumes one manifest defined by
schemas/marginal-evidence-synthesis-config-v0.1.schema.json.

Required fields:

- synthesis_id — stable identifier for this synthesis;
- evidence_class — every included benchmark report must match it exactly;
- selection_rule_version — v0.1 requires
  marginal-selection-interval-dominance-v0.1;
- benchmark_reports — at least two distinct paths, relative to the manifest.

Paths are resolved inside the manifest directory. Absolute paths, duplicate
paths, and path traversal outside that directory fail closed.

## Cohort compatibility

Every referenced document must be a
marginal-evidence-benchmark-report-v0.1 with:

- authority: diagnostic_only;
- the manifest's exact evidence_class;
- the frozen v0.1 selector-rule version in both analysis and selection_plan;
- all five benchmark strategies in canonical order;
- a positive held-out non-probe row count.

The synthesis also rejects duplicate benchmark IDs, whole-report digests,
design split digests, and holdout split digests. This prevents exact evidence
from being silently counted twice.

A benchmark report does not expose every candidate row ID, so this layer cannot
prove that two different report digests contain zero cross-report row overlap.
That limitation is emitted in every report. A stronger future observed-corpus
protocol should retain a cohort/row-set commitment if independent-cohort proof
becomes a promotion requirement.

## Aggregation semantics

The report preserves the five strategy IDs from the held-out benchmark:

1. marginal_effective_votes
2. random_eligible
3. highest_standalone_accuracy
4. different_family_first
5. minimum_mean_pairwise_error_correlation

For each strategy it reports:

- cohort count;
- design-selection resolved/unresolved count;
- held-out evaluated/not-evaluated count;
- per-cohort selected verifier and held-out status;
- panel-error delta measured/unresolved counts;
- panel-error improved/unchanged/worsened counts;
- macro mean panel-error delta;
- held-out-row-weighted mean panel-error delta;
- effective-vote delta measured/unresolved counts;
- positive/unchanged/negative effective-vote counts;
- macro mean effective-vote delta.

Positive panel_error_delta retains the underlying gate-marginal meaning: the
added verifier reduced measured panel error on that cohort. Negative means it
worsened the declared gate.

## What is intentionally absent

The report schema intentionally has no winner, best_strategy, ranking,
statistical-significance claim, multiple-comparison-adjusted inference, routing
recommendation, or production promotion decision.

A mean across heterogeneous cohorts is descriptive evidence, not proof of an
intrinsic verifier property or a causal treatment effect.

## Provenance

The output binds:

- normalized synthesis manifest digest;
- each exact benchmark report digest;
- each exact design and holdout split digest already retained by the benchmark;
- one canonical synthesis-input digest over the manifest plus included report
  digests;
- tool version.

Cohorts are emitted in benchmark_id order so manifest path ordering does not
change the synthesis result.

## CLI

Basic use:

    idkmesh gate-marginal-synthesis synthesis.json --pretty

Optional output:

    idkmesh gate-marginal-synthesis synthesis.json \
      --out results/marginal-synthesis.json --pretty

The CLI refuses to write over the manifest or any referenced benchmark report.

## Relationship to the held-out benchmark

gate-marginal-benchmark freezes candidate selection on design rows and then
evaluates the frozen choice on one disjoint holdout split.

gate-marginal-synthesis starts **after** those reports exist. It does not see
design or holdout verdict matrices and cannot alter selection. That separation
keeps holdout evaluation from becoming a threshold-tuning input.

## Relationship to AVE

Issue #621 / PR #622 studies Adaptive Verification Ecology and broader adaptive
control. This synthesis remains one level earlier: descriptive evidence about
which selector behaviors survived multiple held-out cohorts.

No AVE or Connector Control Plane integration should be promoted merely because
this command exists. Observed, preregistered cohorts and an explicit later
promotion decision are still required.

## Current evidence boundary

Synthetic cohorts can validate determinism, fail-closed behavior, aggregation,
and provenance. They cannot establish real-world reviewer-selection advantage.

Observed cohorts must remain labeled observed; synthetic and observed reports
cannot be silently mixed in one synthesis because the manifest requires one
exact evidence class.
