# Conversation Record — ACE Lineage and Population Simulation

**Date:** 2026-08-28

## Project-owner direction

The project owner approved the GitHub-constrained ACE direction and asked the assistant to continue intelligently with the public repository as the durable project record.

## Repository state observed

The continuation found that IDKMesh already had:

- `COMMUNITY_GROWTH_ENGINE.md` and the ACE Growth Ledger (#23);
- an active metadata-only ACE workflow;
- Growth Seed #25 asking for parent -> seed -> verified descendant evidence links;
- Growth Seed #27 asking for a small deterministic ACE population simulator;
- open PR #40 adding a conservative Bootstrap Cohort observer that separates interest, claims, candidate PRs, merges, and explicitly verified descendants.

Rather than duplicating PR #40, this continuation treats it as the observation layer and fills the two missing scientific prerequisites for later policy evolution.

## Changes prepared

A review branch `ace-lineage-simulation-v0` adds:

1. `docs/community/ACE_LINEAGE_PROTOCOL.md`
   - a minimal JSON-in-Markdown lineage edge;
   - deterministic parent/seed/descendant references;
   - explicit `candidate`, `merged`, `verified`, and `rejected` states;
   - the invariant that merge/activity is not automatically verification;
   - a definition of how the records can support `R_community(W)`.

2. `schemas/ace-lineage-v0.1.schema.json`
   - JSON Schema validation for the lineage record;
   - required verification evidence when `status = verified`;
   - issue/PR/commit reference validation.

3. `experiments/ace_population_sim.py`
   - standard-library-only simulation;
   - fixed-seed deterministic results;
   - under-reproduction, healthy capacity-governed reproduction, and overload scenarios;
   - carrying-capacity equation, credit decay, branching reproduction, review burden, and verification degradation under overload;
   - text or JSON output.

## Illustrative default simulation result

With 24 requested generations and fixed random seed `3`, the current parameters produce approximately:

```text
scenario             seeds   verified   R_community   peak review load   verified value / burden
under-reproduction      1        0          0.000            1.0                 0.000
healthy-reproduction  115       64          1.049           11.0                 0.542
overload               19        4          0.800           16.5                 0.200
```

These numbers are **not empirical claims about GitHub communities**. They demonstrate that the equations can represent the desired qualitative regimes and, importantly, that maximizing raw spawning can produce worse verified value per burden than capacity-governed growth.

## Design conclusion

The safe ACE progression remains:

```text
GitHub events
 -> quiet observation
 -> explicit lineage evidence
 -> measured descendant fitness
 -> simulation / policy experiments
 -> generational strategy update
 -> very small bounded public action budget
 -> observe again
```

ACE should not gain autonomous policy-selection/spawning authority until lineage measurement is reliable enough that the system is optimizing verified descendants rather than activity proxies.

## Verification discipline

This work is prepared as a branch/PR rather than merged directly. That follows the IDKMesh invariant that an AI/tool should not unilaterally propose, verify, and merge its own material into the canonical branch.

## Standing repository rule

This conversation is archived under `docs/conversations/` in accordance with `PROJECT_RULES.md`. Public-safe project findings and implementation artifacts should continue to be preserved in `MSKazemi/idkmesh`.
