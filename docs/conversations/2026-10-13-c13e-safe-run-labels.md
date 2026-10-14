# 2026-10-13: C13-E run label projection

## Request and findings

The project owner requested a high-quality issue implementation, performance-conscious code, regression tests, and synchronized documentation. Issue #1080 had already been implemented, so this contribution targets the still-open C13-E slice of [#608](https://github.com/MSKazemi/idkmesh/issues/608). Existing routing projection managed the broad `idkmesh:` namespace, so separate lifecycle labels require scoped ownership.

## Decision and implementation

Introduce a deterministic, read-only lifecycle-label planner with a closed mapping of Product Spine states, dedicated work/verification/human display label namespaces, digest preconditions, limited input size, and minimal add/remove changes. The existing routing label helper must preserve labels belonging to this new projector. Preserve unrelated human labels. This is not a dispatch or approval surface.

## Evidence, limitations, follow-up

The focused synthetic standalone tests passed (11 cases, 45 subtests) against the inspected Product Spine state list. The repository's full CI remains necessary; the standalone harness did not reproduce the full repository environment. No provider call or untrusted execution was made. Follow-up: exact-head repository CI and review; later C13-G API sync with optimistic concurrency and destination authorization.

## Community and provenance

Improves contributor visibility without suggesting that GitHub labels authorize work. AI-assisted implementation (GPT-6); verification and review are separate obligations.
