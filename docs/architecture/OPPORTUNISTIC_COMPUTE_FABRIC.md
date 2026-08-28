# Opportunistic Compute Fabric for IDKMesh

**Status:** Working architecture proposal  
**Date:** 2026-08-28  
**Active financial constraint:** **project compute spend = $0**

## Executive idea

IDKMesh should not become a cloud provider and should not depend on one compute vendor. It should expose a provider-neutral **Opportunistic Compute Fabric** around bounded Work Units.

The active design is now **zero-project-spend and fail-closed**.

```text
Work Unit
   -> hard repository policy
   -> capability/security matching
   -> zero-project-cost offers only
   -> deterministic selection
   -> execution by a separately trusted adapter
   -> evidence + independent verification
```

The repository-level policy is machine-readable in:

- `config/compute-policy.json`
- `schemas/compute-policy-v0.1.schema.json`
- `schemas/compute-offer-pool-v0.1.schema.json`

The governing decision is `docs/decisions/ADR-0006-zero-project-spend-compute.md`.

Current invariant:

> **No eligible zero-project-cost offer -> no execution selection. Never turn resource scarcity into an unapproved bill.**

A Work Unit may request a stricter budget but cannot relax the repository policy.

---

## Active routing order

The desired user experience is eventually close to:

```text
idkmesh run work-unit.json --provider auto
```

With the current `$0` policy, `auto` means something like:

```text
1. suitable local owned resource
2. legitimate public-project CI resource
3. explicit volunteer/donated node
4. zero-install browser worker where appropriate
5. donated institutional/campus/lab capacity
6. grant-backed capacity with no project invoice
7. genuine free-tier capacity within its terms/quota
8. queue / split / replan / wait / fail closed
```

There is deliberately **no paid fallback** in the active path.

If a 24 GB GPU is required and none is available for zero project spend, the correct result is `no_eligible_offer`, not a cloud invoice.

---

## What “free” means

The project must distinguish three different concepts:

### Zero project monetary spend

The IDKMesh project is not billed. This is the hard current requirement.

### Donated resources

A contributor or organization may voluntarily bear electricity, hardware wear, bandwidth, thermal load, machine time, or operational effort. Those costs are real and should be measured where practical.

Donation must be:

- explicit opt-in;
- visible before execution;
- resource-capped;
- easy to pause/stop;
- revocable;
- never required for community status.

### External subsidy / grant / free quota

A provider, sponsor, university, research program, or free tier may cover a limited amount. This capacity is opportunistic rather than guaranteed and must remain within the provider's current terms.

The scheduler should therefore optimize **verified useful work per scarce donated/free resource**, not pretend capacity has no cost.

---

## Active compute sources

### 1. Contributor laptop/workstation

This is the first and most important backend.

A local `idkmesh-node` can eventually expose explicitly capped CPU/GPU/RAM/disk/time capacity and local-model capability.

Good for:

- tests and compilation;
- deterministic experiments;
- benchmark shards;
- local-model inference;
- independent verification;
- reproductions;
- bounded coding/review agents inside a sandbox.

The first implementation should discover capabilities before executing anything. See issue #52.

### 2. GitHub-hosted Actions for legitimate repository work

Public-project CI can be useful for:

- schema validation;
- test matrices;
- builds;
- linters;
- CodeQL/security checks;
- reproducibility checks;
- project benchmarks;
- packaging/releases.

GitHub Actions must not be treated as a generic public supercomputer. A future provider adapter needs an explicit terms/policy eligibility gate before considering the `public_project_ci` cost class.

### 3. Volunteer `idkmesh-node` capacity

This is the main community-native scaling path.

A participant should eventually be able to:

```text
install node
choose limits
choose allowed capabilities
opt in
pause whenever desired
```

The node should **pull** bounded approved Work Units rather than expose an arbitrary remote shell.

Useful roles include:

- compute;
- verifier;
- researcher;
- coder;
- observer.

Architecture and security details are in `AGENT_NETWORK_AND_VOLUNTEER_NODES.md`; implementation tracking begins with issue #11.

### 4. Browser / WebAssembly / WebGPU workers

A zero-install browser worker can lower participation friction for narrowly bounded, checkpointable, sandbox-friendly jobs.

Potential tasks:

- deterministic verification;
- small simulations;
- numerical kernels;
- benchmark shards;
- lightweight local inference when supported.

Rules:

- explicit opt-in;
- visible CPU/GPU use;
- battery/thermal safeguards;
- no hidden computation;
- short/checkpointable jobs;
- treat browser availability as opportunistic.

### 5. BOINC-style volunteer pools

BOINC remains an important reference architecture for large numbers of weakly coupled volunteer jobs.

IDKMesh should learn from its:

- resource discovery;
- checkpointing;
- heterogeneous scheduling;
- redundancy;
- contribution accounting;
- donor UX.

Where eligible no-charge research capacity exists, IDKMesh can explore it as an adapter rather than immediately recreating a mature volunteer-compute stack.

### 6. University/lab/company donated clusters

Existing infrastructure should be integrated, not replaced.

Potential adapters include:

- HTCondor;
- Slurm;
- Kubernetes Jobs;
- Ray;
- organization-managed isolated runners.

A university or sponsor can donate capacity without transferring repository authority to workers.

### 7. Grants and genuine free tiers

Grant-backed or free-tier CPU/GPU/model capacity can be useful, but it has to satisfy all of these conditions:

- project invoice remains `$0`;
- current service terms permit the workload;
- quota is available;
- no hidden conversion to paid billing;
- credentials are scoped;
- expiration/quota exhaustion produces `unavailable`, not paid fallback.

This class should have lower availability confidence than owned/donated capacity unless evidence shows otherwise.

---

## Provider-neutral offers

Providers should describe capacity rather than exposing provider-specific scheduling logic to IDKMesh Core.

Current experimental offer shape is defined in `schemas/compute-offer-pool-v0.1.schema.json`.

Conceptually:

```text
offer:
  provider
  cost_class
  project_cost_usd
  available
  trust
  capabilities
  cpu / memory / disk / gpu
  expected_wait
  observed success probability
  independence_group
```

Examples are in `examples/compute-offers/free-pool.example.json`.

The example deliberately includes an attractive paid GPU offer. Under current repository policy it must be rejected. This is a negative safety fixture, not an active provider recommendation.

---

## Financial authority is outside the Work Unit

The Work Unit v0.2 budget now includes:

```text
project_spend_usd_max
paid_fallback_allowed
```

But those fields cannot grant financial authority.

Effective budget is conceptually:

```text
effective_project_spend_limit =
    min(repository_policy.project_spend_usd_max,
        work_unit.budget.project_spend_usd_max)
```

Therefore, with repository policy equal to `$0`:

```text
Work Unit asks for $0      -> effective limit $0
Work Unit asks for $5      -> effective limit $0
Work Unit asks for $1000   -> effective limit $0
```

Likewise, `paid_fallback_allowed=true` in a Work Unit cannot override `paid_providers_enabled=false` at repository level.

This is an authority boundary, not a scheduler preference.

---

## Selection-only prototype

`experiments/free_compute_router.py` currently performs **selection only**. It does not launch provider workloads.

It validates:

- Work Unit schema;
- repository compute policy;
- compute offer pool;
- availability;
- allowed cost class;
- project monetary cost;
- capability match;
- CPU/RAM/disk/GPU requirements;
- accelerator requirements;
- minimum trust.

Among eligible offers, the prototype chooses deterministically using predicted success and wait time.

CI runs a negative scenario:

```text
synthetic Work Unit:
  requires CUDA GPU
  asks to allow $100
  sets paid_fallback_allowed = true

available offers:
  free grant GPU = unavailable
  paid GPU = available and excellent

repository policy:
  max spend = $0
  paid providers = disabled

expected result:
  no_eligible_offer
```

This proves that a task cannot buy its way around project policy.

---

## Scheduling mathematics under a hard `$0` constraint

Cost should be handled in two stages.

### Stage 1 — hard feasibility filter

An offer `p` is feasible only if:

```text
available(p) = true
capabilities(p) satisfy WorkUnit
resources(p) satisfy WorkUnit
trust(p) satisfies WorkUnit
cost_class(p) allowed by repository policy
project_cost_usd(p) <= effective_project_spend_limit
provider-specific terms/policy eligibility = true
```

With current policy:

```text
project_cost_usd(p) = 0
```

is mandatory.

### Stage 2 — utility ranking among free-to-project offers

Only after the hard filter, estimate:

```text
score(p) =
    + w_q * P(verified_success | task, provider, hardware)
    + w_v * verification_value
    + w_i * independence_value
    + w_l * locality_value
    - w_t * expected_wait_and_runtime
    - w_r * security/trust risk
    - w_d * donor_resource_burden
    - w_e * estimated energy/resource use
```

This prevents a high-quality paid offer from winning because monetary permission is never expressed as a soft negative weight.

Later, a contextual bandit can learn which **eligible zero-project-cost** configurations perform best for each task class.

---

## Scarcity strategy: compute less intelligently

A `$0` budget makes decomposition and scheduling quality more important.

When capacity is scarce, IDKMesh should try these transformations before giving up:

```text
large task
  -> split into smaller Work Units
  -> remove unnecessary replicas
  -> reserve replicas for high-risk claims
  -> lower model/hardware requirements where valid
  -> schedule during donor idle windows
  -> reuse cached artifacts
  -> deduplicate equivalent work
  -> checkpoint and resume
  -> send deterministic verification to CPU nodes
  -> send only accelerator-essential work to donated GPUs
```

The optimization target becomes:

> **Maximum verified useful work per unit of human attention and donated/free compute.**

---

## Compute is also verification capacity

New capacity should not all go to generation.

Reserve part of heterogeneous capacity for independent checking:

- one worker generates; another verifies;
- deterministic claims run on unrelated nodes;
- important results replicate across independence groups;
- high-risk candidate work gets stronger trusted verification;
- cheap CPU verifiers screen candidates before scarce GPU/model resources are used again.

Heterogeneity is therefore useful as a source of **independence**, not only throughput.

---

## Security boundary

### Protect compute donors

- pull approved bounded Work Units; no arbitrary remote shell;
- disposable sandbox/VM/container per job;
- no host home directory or personal credentials mounted by default;
- network default-off or allowlisted;
- strict CPU/RAM/GPU/disk/time limits;
- resource preview and emergency stop;
- automatic cleanup;
- no hidden mining or unrelated workloads;
- auditable task/project provenance.

### Protect IDKMesh

- volunteer workers are untrusted by default;
- workers never receive merge authority;
- immutable/content-addressed inputs where possible;
- no long-lived project secrets inside untrusted jobs;
- signed/hashed result manifests;
- independent verification;
- redundant execution for important claims;
- evidence-based task-specific reputation;
- trusted reruns for critical checks.

Ordinary contributor machines should not be exposed as unrestricted persistent self-hosted runners for arbitrary public-repository code.

---

## Paid providers: inactive interoperability surface only

Commercial cloud, GPU marketplaces, spot/preemptible instances, paid hosted models, Akash/Golem payment paths, and similar systems are **not active execution sources under the current project rule**.

They may remain in research notes or provider schemas because:

- provider neutrality should not depend on today's funding state;
- future sponsored deployments may have different repository-local policies;
- interoperability experiments can use mock offers without spending money.

But the active `config/compute-policy.json` excludes `paid`, and the core path must not require billing credentials.

If sustainable funding exists in the future, enabling paid capacity requires an explicit governance/maintainer decision that revises `PROJECT_RULES.md`, ADR-0006, and the machine-readable policy first.

---

## Implementation sequence under `$0`

### Phase 0 — selection contract

**Implemented:**

- repository compute policy schema/config;
- Work Unit project-spend fields;
- provider-neutral offer schema;
- mixed free/paid negative fixture;
- selection-only zero-cost router;
- CI fail-closed invariant.

### Phase 1 — local capability discovery

**Next:** issue #52.

Discover safe local CPU/RAM/disk/basic GPU/capability metadata, apply user caps, emit a zero-project-cost offer, and feed it into the selector. No remote execution yet.

### Phase 2 — local sandbox executor

Build the smallest offline `idkmesh-node` path from issue #11:

```text
local Work Unit
 -> policy + selection
 -> disposable local sandbox
 -> bounded execution
 -> normalized ResultManifest
 -> independent verification
```

### Phase 3 — volunteer-node pull protocol

Only after local safety works, allow an explicitly opted-in node to request eligible signed/approved public Work Units.

### Phase 4 — free/donated backend adapters

Add adapters only when real contributors/partners exist, prioritizing:

- legitimate public-project CI;
- donated organization machines;
- browser worker for a narrow deterministic task;
- HTCondor/Slurm/Kubernetes/Ray when an institution offers capacity;
- no-charge research/grant pools.

### Phase 5 — learned free-capacity router

Collect:

```text
(task features,
 provider/cost class,
 hardware/capabilities,
 wait/runtime,
 donor resource use,
 verified success,
 failure reason,
 independence group)
```

Then learn routing rules that maximize verified useful output under the hard `$0` monetary ceiling.

---

## First experiment

Run the same small deterministic/repository-verification Work Units across every zero-project-cost backend that is actually available:

```text
local machine
public-project CI when legitimately eligible
2-5 volunteer machines when volunteers exist
institutional/grant/free-tier capacity only when genuinely available
```

Measure:

- verified success rate;
- queue delay;
- runtime;
- retries/failures;
- contributor setup friction;
- donor CPU/RAM/GPU/time use;
- environment-induced disagreement;
- verification value from independent nodes;
- human attention minutes;
- project monetary spend, which must remain `$0`.

---

## Community growth mechanism

Compute contribution can be one contribution path among many:

```text
install / inspect node
 -> choose limits
 -> donate first bounded Work Unit
 -> receive public verified contribution record
 -> build task-specific reliability history
 -> verify other work
 -> maintain a provider adapter or become a compute steward
```

Possible understandable resource profiles:

```text
Eco:       low CPU, AC power only
Standard:  capped CPU while idle
Verifier:  independent validation jobs only
Local-AI:  explicitly allow local-model inference
Research:  explicitly scheduled experiments
```

Compute donation must never outrank code, review, documentation, research, design, moderation, or other useful contribution forms.

---

## Architectural decision

IDKMesh should be a **zero-spend compute liquidity router** under the current project constraints, not a new cloud provider and not a billing broker.

Its distinctive value is:

- bounded Work Units;
- resource/capability matching;
- hard policy enforcement;
- verification and independence;
- provenance;
- safe volunteer participation;
- efficient use of scarce donated/free capacity;
- community-scale collective intelligence.

Commodity execution infrastructure should be integrated when it is actually available at zero project cost and permitted by policy, rather than reinvented.
