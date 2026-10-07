# 2026-10-07 — Marginal evidence cross-cohort synthesis

## Request

Continue work on a new useful IDKMesh issue without duplicating active pull
requests or weakening authority boundaries.

## Selection

Current main was refreshed before work. Issue #921 was already covered by PR
#923. Issue #740 remains blocked for a real mutating API because the required
live identity/policy integration in #670 is not complete. Issue #693 had no
open PR and its own progress record explicitly named broader cohort synthesis
as the next research gate after merged PR #775.

The selected bounded slice therefore extends #693 with a diagnostic-only
cross-cohort synthesis layer over existing held-out benchmark reports.

## Implementation decision

The synthesis consumes a frozen manifest naming at least two benchmark reports.
It reuses the existing five strategy identities and the frozen selector-rule
version. It never re-runs selection and never receives raw verdict matrices.

The implementation fails closed when reports differ in evidence class or rule
version, when strategy rows are malformed or reordered, or when an exact
report, design split, holdout split, or benchmark identity would be counted
twice.

The output preserves per-cohort outcomes and descriptive aggregate counts and
means but intentionally has no winner, ranking, significance claim, routing
recommendation, EvaluatorPlan, acceptance verdict, or integration authority.

## Verification before publication

An isolated standard-library harness exercised the new module using the exact
benchmark constants expected from the repository:

    python -m unittest -q tests/test_marginal_evidence_synthesis.py

Result: 15 tests passed.

Both new JSON Schemas were parsed with the standard library, checked with
Draft202012Validator.check_schema, and validated against generated config and
report objects. The new module and test file also passed Python bytecode
compilation.

The full repository gate remains authoritative after publication because the
isolated environment cannot clone GitHub or execute the complete IDKMesh tree.

## Research boundary

This slice closes a tooling gap, not the scientific question. A broader
preregistered observed cohort is still needed before any claim that the
marginal selector beats simpler baselines or before AVE / Connector Control
Plane dry-run promotion.
