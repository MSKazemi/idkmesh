# IDKMesh Planning

This directory translates the long-range vision into current execution choices.

## Planning artifacts

- [`CURRENT_PRIORITIES.md`](CURRENT_PRIORITIES.md) — current narrative priority assessment and sequencing rationale.
- [`EXECUTION_TARGET_GRAPH.md`](EXECUTION_TARGET_GRAPH.md) — dependency-oriented goal -> target -> task -> evidence view for the current product critical path and parallel capacity-gated tracks.
- [`REPOSITORY_IMPROVEMENT_LOOP.md`](REPOSITORY_IMPROVEMENT_LOOP.md) — operating contract for evidence-bearing iterations, convergence before expansion, and review-capacity-aware task selection.
- [`PR_TRIAGE_2026-08-28.md`](PR_TRIAGE_2026-08-28.md) — evidence-oriented PR triage principles and canonical integration queue discipline.
- [`BRANCH_CONVERGENCE_POLICY.md`](BRANCH_CONVERGENCE_POLICY.md) — branch lifecycle, cleanup, exact-SHA evidence, stale-work extraction, and safe merge-boundary rules.
- [`BRANCH_MERGE_EXECUTION_PLAN.md`](BRANCH_MERGE_EXECUTION_PLAN.md) — transactional branch-to-main algorithm: classification lanes, dependency DAG, conjunctive merge gates, exact-head integration, recomputation after every merge, and retirement waves.

## Relationship to other project artifacts

- [`../foundations/GOALS.md`](../foundations/GOALS.md) defines the durable goal hierarchy and North Star.
- [`../../ROADMAP.md`](../../ROADMAP.md) defines the staged scale/research progression.
- GitHub Issues define claimable work and acceptance criteria.
- IDKGraph schemas/modeling define the intended machine-readable semantic layer.
- Planning documents are snapshots and should change when evidence changes priorities.

## Rule

Do not interpret a planning document as permission to bypass safety, verification, review, or governance gates.

A target is complete when its observable acceptance evidence exists, not merely when a document describing it has been merged.
