# Resource Discovery -> Runtime Materialization Boundary

**Status:** normative v0 boundary  
**Date:** 2026-08-28  
**Project cost ceiling:** USD 0

## Why this boundary exists

IDKMesh now has two resource-related contracts with intentionally different jobs:

1. `schemas/resource-offer-registry-v0.1.schema.json` describes **discovery/control-plane evidence** about possible free resources: freshness, task classes, external-processing/secret requirements, setup burden, security risk, and activation method.
2. `schemas/compute-offer-pool-v0.1.schema.json` describes **runtime/data-plane capacity** that can actually be considered for a Work Unit: current availability, trust, CPU/RAM/disk/GPU capacity, wait time, reliability, independence group, and project monetary cost.

They are not competing schemas and must not become competing routers.

The canonical runtime selector remains:

`experiments/free_compute_router.py`

under the repository authority ceiling in:

`config/compute-policy.json`

The Free Resource Mesh planner is advisory discovery only.

## Required flow

```text
Resource registry
  (catalog evidence)
       |
       v
Free Resource Planner
  (eligible candidates)
       |
       v
provider-specific materializer / live probe
  + operator consent / caps
  + current availability
  + current concrete resources
       |
       v
Compute Offer Pool v0.1
  (runtime capacity)
       |
       v
repository compute policy
       |
       v
free_compute_router.py
       |
       v
selected runtime offer OR no eligible offer
       |
       v
bounded worker execution
       |
       v
independent verification
       |
       v
human / governance decision
```

A planner result must never skip the materialization step.

## Materialization function

Let:

- `r` be one eligible discovery-registry entry;
- `p` be current provider/live-probe evidence;
- `c` be operator consent and resource caps;
- `P` be repository policy.

Define:

```text
M(r, p, c, P) -> o | null
```

where `o` is a valid `Compute Offer Pool v0.1` runtime offer.

`M` returns `null` unless all hard conditions are satisfied, including:

```text
registry evidence is fresh
AND provider is currently reachable/available where applicable
AND concrete runtime capacity is known
AND operator consent/caps permit the advertised capacity
AND project_cost_usd <= repository ceiling
AND no prohibited authority is introduced
AND the provider-specific adapter can truthfully populate the runtime contract
```

This is deliberately fail-closed.

Discovery eligibility is therefore necessary but **not sufficient** for execution eligibility:

```text
eligible_discovery(r) != executable(r)
```

Instead:

```text
executable(o) only after o = M(r, p, c, P)
```

## Hard invariants

### 1. Planner output is not a Compute Offer Pool

The `selected` entries emitted by `scripts/free_resource_planner.py` are candidate resource IDs and advisory scores. They must not be passed directly to a worker or treated as `compute-offer-pool-v0.1` objects.

### 2. Catalog capabilities do not imply concrete capacity

A registry entry may say a resource is conceptually capable of Docker, LLM inference, coding, verification, or GPU work. That does not establish current CPU count, RAM, disk, GPU availability, queue time, reliability, or operator willingness.

Those runtime facts must be measured, declared, or otherwise materialized at execution time.

### 3. Hardware discovery is not consent

For local/volunteer machines, detected hardware is not permission to consume it. Materialization must apply explicit operator caps. The existing `experiments/local_compute_offer.py` follows this rule by advertising conservative defaults and requiring explicit GPU/donated-mode choices.

### 4. Financial authority stays above both layers

Neither a discovery registry entry nor a runtime Work Unit may grant itself spending authority.

The repository-level compute policy remains authoritative. If no compliant zero-project-cost runtime offer exists, the system queues, splits, replans, waits, requests voluntary capacity, or fails closed.

### 5. Resource ranking is not correctness evidence

A high discovery score or runtime scheduling score says nothing about correctness of candidate output. Result acceptance remains downstream of independent verification and explicit integration/governance rules.

### 6. No third execution protocol

Provider integrations should implement materializers/adapters into the existing runtime contract rather than introduce a provider-specific Work Unit, result format, or execution-offer schema unless a demonstrated requirement cannot be represented canonically.

## Examples

### Local volunteer node

```text
registry: volunteer/local compute is an allowed resource class
 -> local capability probe
 -> operator caps: 2 CPU, 2048 MB, no GPU
 -> Compute Offer Pool entry with project_cost_usd=0
 -> free_compute_router.py
```

### GitHub-hosted public CI

```text
registry: public GitHub Actions is fresh/eligible for deterministic compute
 -> workflow/provider materializer confirms the executable lane and bounded task fit
 -> runtime offer / execution binding appropriate to the canonical Work Unit
 -> repository policy gate
 -> bounded execution
```

### Manual hosted agent

A manual/conditional hosted agent can be a valid discovery candidate without being a runtime compute offer at all. If the lane is human-delegated, the planner output remains advisory and the human contribution re-enters IDKMesh through normal candidate/evidence/verification paths.

This is why the discovery registry intentionally contains a broader resource universe than the runtime compute-offer pool.

## Machine-readable boundary

`scripts/free_resource_planner.py` emits a `runtime_materialization` object containing:

- `required_before_execution: true`;
- `planner_output_is_executable_compute_offer: false`;
- the discovery contract path;
- the runtime contract path;
- the canonical runtime router path;
- the repository compute-policy path.

`tests/test_free_resource_planner.py` locks this boundary so later refactors cannot accidentally erase it.

## Design consequence

IDKMesh should evolve resource support by adding:

```text
new evidence-backed registry entries
        +
small provider-specific materializers
        +
one canonical runtime offer contract
        +
one repository policy gate
        +
one verification path
```

rather than by adding one scheduler/protocol per provider.

This keeps zero-cost growth modular while preventing architectural duplication and authority drift.
