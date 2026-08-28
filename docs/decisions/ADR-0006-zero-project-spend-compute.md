# ADR-0006 — Zero-Project-Spend Compute

**Status:** Accepted  
**Date:** 2026-08-28

## Context

IDKMesh is designed around heterogeneous compute: local machines, volunteer nodes, public CI, browsers, institutional clusters, grants/free tiers, and potentially commercial or decentralized providers.

The project owner has now made an operational constraint explicit: **the project cannot pay for computing resources**.

Without a hard policy, a convenience feature such as `provider=auto` could become dangerous: resource scarcity might cause a scheduler to select a paid cloud/GPU offer automatically. A per-Work-Unit budget alone is insufficient because a task, agent, or contributor could accidentally or intentionally raise that budget.

## Decision

IDKMesh adopts a repository-level compute policy with:

```text
project_spend_usd_max = 0
paid_providers_enabled = false
```

The canonical machine-readable policy is:

`config/compute-policy.json`

The policy is a **hard ceiling**. Work Units may restrict it further but cannot relax it.

The initial selector is:

`experiments/free_compute_router.py`

Its invariant is:

> No eligible zero-project-cost offer means no selection. The system must never silently convert missing capacity into project spending.

## Eligible capacity classes

The active policy may consider:

- locally owned compute already available to a participant;
- explicitly donated volunteer capacity;
- public-project CI when the workload is legitimately within the CI/service terms;
- grant-backed capacity that creates no project invoice;
- genuine free-tier capacity within its published terms and quotas.

These are **zero cost to the project**, not necessarily zero economic or environmental cost. Donors may bear electricity, hardware wear, bandwidth, thermal load, or opportunity cost. Donation therefore remains voluntary and resource-capped.

## Disabled capacity

Commercial compute markets, rented GPUs, spot/preemptible cloud instances, paid model APIs, and other billable providers are disabled in the active execution path.

Their adapters may still be documented or prototyped for interoperability research, but repository policy must reject them while this ADR is active.

## Failure behavior

When suitable zero-project-cost capacity is unavailable, the scheduler should use one or more of these responses:

1. queue the Work Unit;
2. split or reduce the task;
3. lower resource requirements when scientifically/technically valid;
4. wait for volunteer capacity;
5. request a replication or resource donation through normal community mechanisms;
6. use another eligible free backend;
7. stop and report `no_eligible_offer`.

It must not select a paid provider as an implicit fallback.

## Implementation consequences

The Work Unit v0.2 `budget` object now requires:

- `project_spend_usd_max`;
- `paid_fallback_allowed`.

The repository policy remains authoritative even if a Work Unit sets a higher amount or `paid_fallback_allowed=true`.

Provider-neutral capacity is represented through `schemas/compute-offer-pool-v0.1.schema.json`.

CI runs a negative test where a GPU Work Unit attempts to relax its own budget but the only matching available GPU is a paid offer. The correct result is no selection.

## Alternatives considered

### Allow tiny automatic spend

Rejected. Even a small amount creates billing credentials, cost-control, abuse, governance, and ownership questions that the project does not need at this stage.

### Keep cost only as scheduler preference

Rejected. A penalty term in an optimization function is not a spending control; enough predicted quality/latency could outweigh it.

### Put the limit only in each Work Unit

Rejected. Work Units are inputs to the scheduler and cannot be allowed to grant themselves financial authority.

### Remove all paid-provider concepts from architecture

Not required. Provider-neutral interoperability can still study paid systems, but they remain disabled by the hard repository policy.

## Community impact

This decision lowers the barrier to maintaining IDKMesh because contributors do not need billing accounts, credit cards, or cloud budgets to reproduce the core path. It also creates first-class contribution roles for compute donors and free-infrastructure adapters.

The project must avoid framing donated compute as truly free. Contributors who cannot or do not want to donate hardware remain equally valid community participants.

## Implementation references

- `docs/architecture/RESOURCE_COMPUTE_ADMISSION.md`

## Revisit conditions

This ADR may be revisited only through an explicit project governance/maintainer decision if sustainable funding or sponsorship later exists. Any change must update both human-readable project rules and the machine-readable policy before paid execution can become eligible.
