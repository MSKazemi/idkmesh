# Conversation Record — Zero-Project-Spend Compute Router

**Date:** 2026-08-28

## Project-owner requirement

Repository: `https://github.com/MSKazemi/idkmesh`

The project owner asked to continue implementing the compute-resource direction directly in the repository and added a decisive constraint:

> **We cannot pay for the resources.**

This means the prior opportunistic-compute concept needed to change from “free-first with paid fallback” to **hard zero-project-spend with no paid fallback**.

## Assistant interpretation

The financial constraint should not be a soft scheduler preference. It is an **authority boundary**.

A task, model, agent, issue, Work Unit, scheduler score, or provider offer must not be able to create project spending merely because a paid resource is faster, more reliable, or the only available match.

Therefore the safe rule is:

```text
repository policy first
    -> Work Unit may tighten policy
    -> provider/capability matching
    -> zero-project-cost offers only
    -> selection
```

If no eligible free/donated/subsidized resource exists:

```text
queue / split / replan / wait / request voluntary capacity / fail closed
```

not:

```text
rent compute
```

## Durable decision

IDKMesh now has a repository-level policy:

```text
project_spend_usd_max = 0
paid_providers_enabled = false
```

Canonical artifacts:

- `PROJECT_RULES.md` — Rule 3, Zero project spend for compute;
- `docs/decisions/ADR-0006-zero-project-spend-compute.md` — architecture decision record;
- `config/compute-policy.json` — machine-readable active policy;
- `schemas/compute-policy-v0.1.schema.json` — policy schema.

A future Work Unit is allowed to be stricter but cannot relax this repository ceiling.

## Work Unit contract change

`schemas/work-unit-v0.2.schema.json` now requires two budget fields:

```text
project_spend_usd_max
paid_fallback_allowed
```

The valid Phase 0 smoke Work Unit now declares:

```text
project_spend_usd_max = 0
paid_fallback_allowed = false
```

The schema documentation was updated to clarify that financial authority remains outside the Work Unit.

## Provider-neutral capacity contract

The implementation added:

- `schemas/compute-offer-pool-v0.1.schema.json`;
- `examples/compute-offers/free-pool.example.json`.

A compute offer describes:

```text
provider
cost class
project monetary cost
availability
trust
capabilities
CPU/RAM/disk/GPU
expected wait
success probability
independence group
```

Supported conceptual cost classes are:

```text
local_owned
donated
public_project_ci
grant
free_tier
paid
```

`paid` remains representable for interoperability and negative testing but is disabled by active repository policy.

## Negative paid-offer fixture

The example offer pool deliberately contains a paid cloud/GPU offer that is more attractive in quality/latency terms than some free offers.

This is intentional. It proves that the monetary constraint is applied as a hard feasibility filter rather than a small negative term in an optimization score.

## Selection-only router

`experiments/free_compute_router.py` was added.

It performs **selection only** and does not launch provider workloads.

It validates:

- Work Unit;
- repository compute policy;
- compute offer pool;
- availability;
- allowed cost class;
- project cost ceiling;
- capabilities;
- CPU/RAM/disk/GPU requirements;
- accelerator requirements;
- minimum worker trust.

The effective monetary limit is conceptually:

```text
min(repository project spend ceiling,
    Work Unit project spend ceiling)
```

The self-test includes an important adversarial/negative scenario:

```text
Work Unit requires CUDA GPU
Work Unit sets its own budget to $100
Work Unit sets paid fallback = true
free grant GPU is unavailable
paid GPU is available
repository policy remains $0 and paid disabled
```

Expected result:

```text
no eligible offer
```

This proves a Work Unit cannot grant itself financial authority.

## CI integration

`.github/workflows/phase0-schema-check.yml` now:

1. validates Phase 0 contracts/fixtures;
2. runs the zero-cost router self-test;
3. shows an example free compute selection;
4. runs the deterministic local smoke fixture.

The workflow explicitly notes that the router performs selection only and must fail closed rather than choose project-paid compute.

## Compute architecture revision

`docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md` was revised to remove paid fallback from the **active** routing path.

Current automatic routing is:

```text
local owned
 -> legitimate public-project CI
 -> volunteered/donated
 -> browser where suitable
 -> donated institutional capacity
 -> grant-backed capacity
 -> genuine free-tier capacity
 -> queue/split/replan/wait/fail closed
```

Paid cloud, GPU marketplaces, paid hosted models, spot instances, and payment-based decentralized compute may remain documented as inactive interoperability surfaces, but current policy excludes them from execution.

## Important economic distinction

“Project spend = $0” is **not** the same as “compute has no cost.”

Volunteer and owned resources can consume:

- electricity;
- hardware life;
- bandwidth;
- thermal headroom;
- machine availability;
- contributor attention.

Therefore resource donation must remain:

- opt-in;
- visible;
- capped;
- easy to stop;
- non-required for community standing.

The scheduler should eventually optimize verified useful work per unit of **donated/free compute plus human attention**, not simply maximize raw activity.

## Existing issue integration

Issue #11, `Prototype a safe local idkmesh-node volunteer worker`, received a comment adding the zero-project-spend requirements:

- local/donated capacity reports project cost `$0`;
- no billing credentials required;
- donor limits explicit;
- Work Unit cannot grant financial authority;
- no eligible free capacity means fail closed;
- capacity/resource provenance remains visible.

## New implementation issue

Issue #52 was created:

**Connect the zero-cost router to real local capability discovery**

This is intentionally smaller than building a distributed node immediately.

The first target is:

```text
inspect local safe capabilities
 -> apply user resource caps
 -> emit provider-neutral local offer
 -> validate offer
 -> route Phase 0 Work Unit
```

No remote execution, network scheduler, billing credentials, or cloud account is required.

This makes issue #52 a low-risk bridge between the current selector and issue #11's future local `idkmesh-node` executor.

## Community impact

The zero-project-spend rule reduces onboarding requirements: core IDKMesh work should not require a credit card, cloud account, paid model account, or project budget.

It also creates compute contribution as one optional community role without making it a prerequisite for participation.

Potential contribution paths include:

- local capability discovery;
- resource-capping UX;
- CPU-only verification tasks;
- safe browser workers;
- institutional adapter work;
- volunteer-node security;
- scheduling/reliability research;
- measurement of donor resource burden;
- independent verification on heterogeneous hardware.

## Immediate next engineering step

Implement issue #52 first: local capability discovery and zero-cost offer emission.

After that is reliable, connect the same offer format to the offline local sandbox prototype in issue #11. Only then should the project add networked volunteer task pickup.
