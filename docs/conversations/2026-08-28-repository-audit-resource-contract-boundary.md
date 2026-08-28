# Repository audit — bugs, convergence, and resource contract boundary

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

The project owner asked to continue development, inspect the repository for bugs/inconsistencies, choose the most useful next step, execute it, and keep the work public in the repository.

## Audit work completed in this pass

### Stale defect cleanup

Issue #82 still described a `local_verifier.py` self-test default-path bug. Current `main` already used isolated `candidate-root` directories, so #82 was documented and closed as completed rather than left as a misleading open defect.

### Product tracker normalization

Issues #4 and #16 contained historical worker SHA/checklist state. Corrective comments recorded the active exact worker candidate and were then corrected again as concurrent merges #117 and #116 moved the repository baseline forward.

This matters in a self-evolving repository: tracker state must follow actual current evidence rather than preserve an obsolete roadmap as if it were pending work.

### Replayable evidence retention

The repository had a real evidence-retention inconsistency:

- the single real-node -> independent-verifier path had a tested artifact-retention improvement on a diverged branch;
- the newly merged real two-attempt path emitted evidence to the job summary but did not retain the exact evaluator-owned bytes for later replay.

The older diverged PRs #115 and #119 were retired as superseded. PR #122 unified both paths using pinned `actions/upload-artifact` v4.6.2, 30-day retention, `if-no-files-found: error`, read-only repository permissions, and no selection/approval/merge authority.

The unified branch was explicitly synchronized with the merged #116 EvaluatorPlan-v0.2 orchestrator state and re-tested. Both real E2E paths succeeded and produced retained artifacts before #122 was squash-merged.

PR #122 merged as:

`2c312e124743dc677333fbf3b08477a619d615ad`

The exact compatibility runs before merge were:

- single real-node -> verifier: run `33187645308`, success, artifact `9692375594`, digest `sha256:42af1a108a2bb73d1c36fa7ad4319e01442e968e45338818dacbec3c1575c967`;
- real two-attempt evidence: run `33187645373`, success, artifact `9692376706`, digest `sha256:e68d6d4f9a8cdc2b2200d43f44ba5f9aa2c263c5dddff31838a8e69597994233`.

## Resource-contract ambiguity discovered after #125

PR #125 introduced the useful Free Resource Mesh v0:

- `schemas/resource-offer-registry-v0.1.schema.json`;
- `scripts/free_resource_planner.py`;
- free-resource policy tests and a read-only planning workflow.

The repository already had a separate zero-cost runtime layer:

- `schemas/compute-offer-pool-v0.1.schema.json`;
- `config/compute-policy.json`;
- `experiments/free_compute_router.py`;
- `experiments/local_compute_offer.py`.

These contracts are complementary rather than duplicates:

- the resource registry is discovery/control-plane evidence about possible resources;
- the compute-offer pool is concrete runtime/data-plane capacity.

The original planner JSON did not make that distinction machine-readable. A future integration could therefore treat a planner `selected` entry as an executable compute offer and accidentally evolve a second execution router.

## Concurrent convergence changed the implementation

While this fix was being tested, `main` independently gained:

`docs/architecture/FREE_RESOURCE_MESH_COMPUTE_BRIDGE.md`

That document explicitly establishes the canonical separation and states that a registry entry is not automatically a compute offer.

This was semantic overlap with an architecture note initially drafted on this branch. Rather than merge two normative documents that say essentially the same thing, the duplicate branch document was deleted.

This is a useful self-evolution rule:

```text
independent work discovers same boundary
 -> prefer the already-canonical artifact
 -> remove duplicate architecture
 -> retain only missing executable enforcement
```

## Missing executable enforcement kept by PR #128

The remaining useful delta is machine-readable and regression-tested.

`scripts/free_resource_planner.py` emits:

```text
runtime_materialization.required_before_execution = true
runtime_materialization.planner_output_is_executable_compute_offer = false
runtime_materialization.boundary_doc = docs/architecture/FREE_RESOURCE_MESH_COMPUTE_BRIDGE.md
runtime_materialization.discovery_contract = schemas/resource-offer-registry-v0.1.schema.json
runtime_materialization.runtime_contract = schemas/compute-offer-pool-v0.1.schema.json
runtime_materialization.runtime_router = experiments/free_compute_router.py
runtime_materialization.repository_compute_policy = config/compute-policy.json
```

`tests/test_free_resource_planner.py` locks all of those values.

The intended pipeline remains:

```text
resource catalog / freshness / policy evidence
 -> discovery planner
 -> provider-specific live materializer
 -> canonical Compute Offer Pool
 -> repository compute policy
 -> canonical free compute router
 -> bounded worker
 -> independent verification
 -> explicit integration decision
```

The key safety statement is:

```text
discovery eligibility != execution eligibility
```

A provider must supply live capacity/availability evidence and any required operator consent/caps before it can materialize into the existing runtime offer contract.

## Exact-head verification

Before the concurrent bridge landed, the initial machine-readable boundary passed the `Free Resource Mesh Plan` workflow at exact head `011160fc8327b06ae8519f817afa7ce996242fdc`, including:

- Python compilation;
- policy unit tests;
- current registry validation;
- sample public-task planning;
- JSON-plan validation.

After converging on the canonical bridge document and synchronizing current `main`, the same policy workflow should be treated as the required final merge evidence for the reduced patch.

## Remaining external governance gap

Public GitHub branch metadata continued during this audit to report `main` as unprotected with required status enforcement off.

Repository workflows can detect and document that state, but they cannot substitute for an actual GitHub ruleset/branch-protection configuration. The canonical worker PR #91 also retains its deliberate genuinely separate human/reviewer inspection gate; this audit did not manufacture independence by self-approving that worker.

## Next product experiment after resource-contract convergence

The real same-worker two-attempt path and EvaluatorPlan-v0.2 orchestration are already integrated. The most informative next product experiment is not another orchestration layer. It is one deliberately simple heterogeneous second real adapter/worker plus a small frozen real-task set, measuring:

- success by adapter;
- verifier disagreement;
- correlated failures;
- reproducibility;
- human review burden;
- verified useful work per donated/free resource unit.

That will test whether diversity actually improves IDKMesh rather than merely increasing agent count.
