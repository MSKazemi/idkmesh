# Conversation Record — ACE Lineage-to-Controller Interface

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner instructed the assistant to continue improving the public repository under the standing IDKMesh rule that each repository activity should contribute to verified system capability, useful evidence, risk reduction, or community leverage rather than merely increasing raw activity.

## Context

The ACE stack had been converging into distinct layers:

- PR #40 — Bootstrap Cohort observation / exposure evidence;
- PR #48 — tested causal lineage contract;
- PR #44 — offline population/capacity simulation;
- PR #51 — consolidated safety and protected-main fail-closed gate;
- PR #68 — Activity Metabolism / Phase-A generational controller.

The remaining semantic duplication was inside PR #68 itself: one `descendants` object mixed causal lineage status with policy-value/cost measurements.

## Problem

A causal lineage receipt can prove:

```text
parent -> seed -> descendant -> verification
```

but it cannot legitimately invent:

- maintainer minutes;
- added review latency;
- unproductive public writes;
- a universal utility/value score.

Conversely, a row claiming a large value or low cost must not become causal proof merely because it exists in the controller input.

Therefore:

```text
causality != utility measurement
```

and:

```text
denominator inventory != descendant evidence
```

## Controller refactor

PR #68 now separates three evidence layers.

### `parents`

Independent denominator inventory. Only entries with:

```text
verified = true
matured = true
```

enter the `R_community` denominator.

### `lineage_receipts`

Prevalidated receipts compatible with PR #48's ACE lineage protocol.

They determine the causal reproduction numerator.

The controller checks local invariants including unique identity, known parent reference, valid status, exact agreement between `status=verified` and `verified=true`, and finite non-negative reviewer minutes.

### `strategy_outcomes`

Measured policy-learning data linked to a known lineage identity:

- strategy;
- measured value;
- maintainer minutes;
- added review latency;
- unproductive public writes.

Reviewer minutes stay on the lineage receipt and cannot be duplicated in the outcome.

## New invariant

> **Causal reproduction comes only from verified lineage receipts; positive strategy value comes only from measured outcomes linked to a verified receipt.**

This creates useful asymmetric cases:

- verified lineage + no outcome -> counts reproduction, creates no positive strategy fitness;
- huge outcome value + unverified lineage -> creates no causal reproduction and no positive benefit;
- unverified activity may still create measured latency/noise cost.

## Executable changes

Updated:

- `scripts/ace_generation_controller.py`;
- `examples/community/ace-generation-shadow.example.json`;
- `tests/test_ace_generation_controller.py`.

Added:

- `docs/community/ACE_GENERATION_EVIDENCE_INTERFACE.md`.

The controller now rejects the old `descendants` input so the experimental PR cannot silently keep two canonical evidence formats.

The result declares:

```text
evidence_format = ace-lineage-receipts+strategy-outcomes-v1
```

## Verification

The evidence-interface refactor passed all relevant validation surfaces:

- `ACE Generation Shadow` — success;
- `Phase 0 schema check` — success, including cross-object provenance integrity, the executable independent verifier, two-attempt orchestration kernel, verification backpressure, zero-cost routing, local capability discovery, and the safe built-in smoke fixture;
- `randomness-lab` — success on Python 3.11, 3.12, and 3.13, including the R1/R2/R3 experiment command surfaces.

Tests cover:

- normalized positive strategy weights;
- unverified lineage cannot create positive fitness even with high outcome value;
- verified lineage still counts toward reproduction when no strategy outcome exists;
- outcome must reference an existing lineage identity;
- verified boolean must agree with lineage status;
- reviewer minutes cannot be duplicated across evidence layers;
- legacy `descendants` input is rejected;
- overload forces `CONSOLIDATE`, zero public action, and consolidation policy bias;
- activation and actuation gates remain separate;
- public write budget cannot exceed one;
- duplicate lineage identities are rejected;
- fixed input is deterministic.

## Repository integration performed

The PR #68 description was updated to make the three-layer evidence interface canonical and to record the successful cross-suite validation.

Issue #57 was updated with the Phase-A implementation status and the rule that Phase-B remains disabled until the cohort, lineage, safety/protection, and real descendant-evidence gates are satisfied.

Issue #10 was updated with the converged ACE stack:

```text
#40 cohort/exposure observer
#48 causal lineage contract
#44 offline capacity simulator
#51 consolidated safety/protection gate
#68 shadow policy-learning controller
```

This makes the dependency graph discoverable from the main community-engine tracker rather than only from implementation branches.

## Safety / community impact

This refactor reduces the number of ways an agent, contributor, or future workflow could game community-policy learning by writing favorable numbers into a single object. It also makes the system easier to explain to contributors: causal evidence and performance/cost evidence have different provenance and different authority.

No GitHub write capability, auto-merge, secret access, or Phase-B actuator is added.

At the time of the related safety convergence, public branch metadata still reported `main` as unprotected. Repository-level fail-closed guards are useful but do not replace the administrator enabling the actual GitHub ruleset/branch protection.

## Next step

The next true step is evidence collection and protected integration, not more controller theory:

1. independently review and integrate the consolidated #51 ACE safety/protection change;
2. configure and verify actual GitHub protection/rulesets for `main`;
3. independently review the #48 causal lineage contract and #40 cohort/exposure observer;
4. keep #44 as an offline falsification model;
5. feed real matured-parent and verified-lineage evidence into #68 in shadow mode;
6. compare its recommendation against simple non-adaptive baselines;
7. only after several evidenced generations consider a separately reviewed Phase-B actuator.
