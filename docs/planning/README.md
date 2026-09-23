# IDKMesh Planning

This directory translates the long-range vision into current execution choices.

## Planning artifacts

- [`API_V1_PROFESSIONALIZATION_PLAN_2026-09-23.md`](API_V1_PROFESSIONALIZATION_PLAN_2026-09-23.md) — canonical API program plan: completeness definition, deployment profiles, resource families, issue ownership, release gates, and v1 beta definition of done.
- [`API_V1_ISSUE_DEPENDENCY_GRAPH_2026-09-23.md`](API_V1_ISSUE_DEPENDENCY_GRAPH_2026-09-23.md) — dependency/parallelism map for issues #735–#747 plus existing runtime, identity, persistence, Product Spine, connector, and Control Tower owners.
- [`END_TO_END_PRODUCT_SPINE_PLAN_2026-09-22.md`](END_TO_END_PRODUCT_SPINE_PLAN_2026-09-22.md) — P0 integration plan for converging connector/routing, dispatch, candidate normalization, verification, human decision, GitHub durability, bootstrap, and release into one end-to-end product spine.
- [`MODEL_TIER_DISPATCHER_EXECUTION_PLAN_2026-09-22.md`](MODEL_TIER_DISPATCHER_EXECUTION_PLAN_2026-09-22.md) — capability-tier, authority, connector-admission, escalation, GitHub-only state, and #574 implementation plan.
- [`AGENT_MODEL_INTEGRATION_SELF_HOSTING_PLAN_2026-09-22.md`](AGENT_MODEL_INTEGRATION_SELF_HOSTING_PLAN_2026-09-22.md) — staged connector-control-plane roadmap: first use external agents/models to finish IDKMesh, then self-host repository development, then use the same product interfaces to build a second application.
- [`CURRENT_PRIORITIES.md`](CURRENT_PRIORITIES.md) — current narrative priority assessment and sequencing rationale.
- [`EXECUTION_TARGET_GRAPH.md`](EXECUTION_TARGET_GRAPH.md) — dependency-oriented goal -> target -> task -> evidence view for the current product critical path and parallel capacity-gated tracks.
- [`REPOSITORY_IMPROVEMENT_LOOP.md`](REPOSITORY_IMPROVEMENT_LOOP.md) — operating contract for evidence-bearing iterations, convergence before expansion, and review-capacity-aware task selection.
- [`PR_TRIAGE_2026-08-28.md`](PR_TRIAGE_2026-08-28.md) — evidence-oriented PR triage principles and canonical integration queue discipline.
- [`BRANCH_CONVERGENCE_POLICY.md`](BRANCH_CONVERGENCE_POLICY.md) — branch lifecycle, cleanup, exact-SHA evidence, stale-work extraction, and safe merge-boundary rules.
- [`BRANCH_MERGE_EXECUTION_PLAN.md`](BRANCH_MERGE_EXECUTION_PLAN.md) — transactional branch-to-main algorithm: classification lanes, dependency DAG, conjunctive merge gates, exact-head integration, recomputation after every merge, and retirement waves.
- [`CHATGPT_PROJECT_MIGRATION_PACK_2026-09-19.md`](CHATGPT_PROJECT_MIGRATION_PACK_2026-09-19.md) — complete ChatGPT-project migration pack: canonical v3 jobs, full prompts/schedules, historical 34-job archive, replacement map, and recovery procedure.
- [`CHATGPT_AUTOMATIONS_V3.yaml`](CHATGPT_AUTOMATIONS_V3.yaml) — machine-readable manifest for recreating the nine canonical ChatGPT scheduled agents in a fresh project.
- [`CHATGPT_FRESH_PROJECT_BOOTSTRAP_PROMPT.md`](CHATGPT_FRESH_PROJECT_BOOTSTRAP_PROMPT.md) — copy/paste bootstrap prompt for recreating the canonical automation set after connecting GitHub.

## Relationship to other project artifacts

- [`../foundations/GOALS.md`](../foundations/GOALS.md) defines the durable goal hierarchy and North Star.
- [`../../ROADMAP.md`](../../ROADMAP.md) defines the staged scale/research progression.
- GitHub Issues define claimable work and acceptance criteria.
- IDKGraph schemas/modeling define the intended machine-readable semantic layer.
- Planning documents are snapshots and should change when evidence changes priorities.

## Rule

Do not interpret a planning document as permission to bypass safety, verification, review, or governance gates.

A target is complete when its observable acceptance evidence exists, not merely when a document describing it has been merged.
