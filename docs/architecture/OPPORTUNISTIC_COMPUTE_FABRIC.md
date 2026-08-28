# Opportunistic Compute Fabric for IDKMesh

**Status:** Working architecture proposal  
**Date:** 2026-08-28

## Executive idea

IDKMesh should not choose one cloud, one GPU marketplace, or one volunteer-computing system as its compute layer.

It should build a **provider-neutral Opportunistic Compute Fabric** around the existing bounded Work Unit abstraction.

The desired user experience is eventually close to:

```text
idkmesh run work-unit.yaml --provider auto --budget 0.50
```

The scheduler should then find the cheapest/safest suitable execution path in an ordered pool such as:

```text
local idle resource
    -> project CI resource when policy permits
    -> donated volunteer node
    -> zero-install browser worker
    -> institutional/campus idle capacity
    -> free/grant-backed compute
    -> interruptible/spot marketplace
    -> normal paid cloud fallback
```

The important design decision is that **Work Units describe work; provider adapters describe where it runs**.

This avoids coupling the project to any one vendor and directly supports the IDKMesh goal of scaling from one laptop to a large heterogeneous mesh.

---

## What compute can IDKMesh use?

### 1. The contributor's own laptop/workstation

**Best first resource.**

Use ordinary CPU/GPU/RAM through the local `idkmesh-node`, initially inside Docker/Podman and later stronger disposable sandboxes where needed.

Good for:

- local coding agents;
- tests and compilation;
- simulations;
- benchmark shards;
- local-model inference;
- independent verification;
- reproductions.

Advantages:

- zero project cloud bill;
- no external scheduler dependency;
- ideal for one-machine experiments;
- exposes the exact worker protocol needed later for the distributed system.

The project should make resource donation explicit and capped: CPU %, GPU use, memory, disk, network, time window, battery/AC-only policy, and pause/stop controls.

### 2. GitHub-hosted Actions runners

GitHub currently documents standard GitHub-hosted runners as free for public repositories, including Linux, Windows, macOS, x64, and Arm variants.

Use them for work directly related to production, testing, deployment, publication, and verification of IDKMesh software:

- CI test matrices;
- builds;
- linters;
- CodeQL/security checks;
- reproducibility checks;
- project benchmarks;
- packaging/releases;
- bounded project experiments that are legitimately part of developing/testing IDKMesh.

**Important limitation:** do not treat free GitHub Actions as a generic public supercomputer. GitHub's current terms prohibit GitHub-hosted runner activity unrelated to production, testing, deployment, or publication of the software project and prohibit disproportionate server load. The compute broker therefore needs a policy flag such as `eligible_for_project_ci: true` before considering the GitHub Actions adapter.

Sources:

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features

### 3. IDKMesh volunteer nodes

This should become the main community-native compute source.

A contributor installs `idkmesh-node`, chooses resource limits, and the node **pulls** approved bounded Work Units while idle. The node returns patches, reports, results, hashes, logs, and attestations rather than receiving repository merge authority.

Good for:

- asynchronous CPU jobs;
- local GPU inference;
- fuzzing;
- test shards;
- Monte Carlo/simulation tasks;
- compilation across diverse hardware/OS combinations;
- independent replications;
- coding/review agents with local models.

This architecture is already described in `AGENT_NETWORK_AND_VOLUNTEER_NODES.md`; the Compute Fabric turns it into one provider among many.

### 4. Browser + WebAssembly/WebGPU workers

A web page can become a **zero-install compute node**.

A visitor explicitly opts in, the page obtains a bounded Work Unit, runs code in WebAssembly and optionally general-purpose GPU computation through WebGPU, and uploads a result bundle.

Good for highly sandboxable, restartable work such as:

- hashing/search;
- deterministic verification;
- small simulations;
- benchmark shards;
- numerical kernels;
- model inference that fits browser constraints;
- replication tasks.

Advantages:

- almost no contributor installation friction;
- excellent community-growth surface;
- browser sandbox gives a useful baseline isolation layer.

Limitations:

- WebGPU is not yet universally available across all major browser/device combinations;
- browser tabs are ephemeral;
- thermal/battery use must be opt-in and visible;
- jobs must checkpoint or be naturally short;
- HTTPS is required for WebGPU.

Sources:

- https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API
- https://developer.mozilla.org/en-US/docs/Web/API/GPU

### 5. BOINC / BOINC Central

BOINC is the mature reference architecture for volunteer high-throughput computing. It automatically downloads jobs, selects work appropriate to a machine, executes it, uploads outputs, and tracks contribution credit.

BOINC Central now states that it can supply CPUs and GPUs from thousands of volunteered home computers, including applications packaged with Docker, and that eligible researchers can apply for no-charge computing.

IDKMesh can use BOINC in two ways:

1. **Learn from it** for resource discovery, credits, redundancy, heterogeneity, checkpointing, and volunteer UX.
2. For scientific IDKMesh experiments that fit BOINC Central's eligibility/policy, explore submitting containerized experiment batches rather than building a full volunteer pool immediately.

Good for:

- huge numbers of independent deterministic jobs;
- simulation sweeps;
- parameter searches;
- replication;
- CPU/GPU experiments where individual tasks are weakly coupled.

Less suitable for interactive coding agents or tightly coupled distributed training.

Sources:

- https://boinc.berkeley.edu/central/
- https://boinc.berkeley.edu/central/about.php
- https://boinc.berkeley.edu/central/scientist.php

### 6. Campus/lab/company idle machines with HTCondor

HTCondor is a strong adapter target for institutions that already have many desktops, lab machines, servers, or clusters.

Its model is close to IDKMesh Work Units: independent asynchronous jobs are submitted to an access point, matched to suitable execution points, sandboxed with input/output files, and can be rescheduled if a machine disappears.

Good for:

- universities;
- research labs;
- companies willing to donate internal idle capacity;
- large benchmark/experiment sweeps;
- opportunistic execution across machines that are not dedicated to IDKMesh.

Sources:

- https://htcondor.readthedocs.io/en/main/users-manual/quick-start-guide.html
- https://htcondor.readthedocs.io/en/main/overview/htcondors-power.html

### 7. Existing clusters through Ray / Kubernetes / Slurm

Many contributors or partner organizations will already own clusters. IDKMesh should not ask them to replace their scheduler.

Instead provide adapters:

- `ray` for Python/AI tasks and elastic clusters;
- `kubernetes-job` for containerized batch work;
- `slurm` for HPC centers;
- `htcondor` for high-throughput opportunistic pools.

Ray is particularly useful as an internal execution backend because it abstracts CPU/GPU/memory resources and can scale applications from a laptop to a cluster.

Source:

- https://docs.ray.io/en/latest/ray-core/scheduling/resources.html

### 8. Hugging Face ZeroGPU

Hugging Face currently provides shared ZeroGPU infrastructure for Spaces. Its documentation states that free personal accounts in good standing can host a limited number of ZeroGPU Spaces, with dynamically allocated shared GPUs.

This can be useful for:

- public IDKMesh demos;
- small GPU-backed research tools;
- interactive inference experiments;
- showcasing a contributor-facing verifier/agent demo.

It is **not** the general batch compute fabric: it currently has framework/interface constraints and quotas. Treat it as a specialized adapter/demo surface.

Source:

- https://huggingface.co/docs/hub/spaces-zerogpu

### 9. Cloudflare Workers / Workers AI as a lightweight control plane

Cloudflare Workers is better suited to the **broker/gateway/control plane** than heavy computation.

Current free limits include a large daily request allowance but very small per-request CPU budgets, which makes it attractive for:

- signed Work Unit distribution;
- capability registration;
- lightweight scheduling/routing;
- result metadata ingestion;
- webhooks;
- browser-worker coordination.

Workers AI also currently provides a daily free inference allocation, useful for cheap classification/triage/routing experiments, but it should remain an optional model adapter rather than a core dependency.

Sources:

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/workers-ai/platform/pricing/

### 10. Distributed GPU clouds such as SaladCloud

SaladCloud runs containerized workloads on a distributed network of privately owned devices, primarily gaming PCs, and maintains requested replica counts across available nodes.

That is conceptually close to the future IDKMesh compute market, but it is already operated as a managed service. An adapter could let IDKMesh burst GPU/container jobs without building all capacity itself.

Good for:

- horizontally scalable GPU inference;
- resilient container workloads;
- bursty heterogeneous GPU jobs.

Source:

- https://docs.salad.com/

### 11. GPU marketplaces such as Vast.ai

Vast.ai exposes a real-time marketplace where hosts list GPUs, users search offers, and instances run Docker images. It supports API/CLI automation and cheaper interruptible capacity.

This is a strong paid fallback for checkpointable IDKMesh Work Units.

Good for:

- GPU-heavy experiments;
- local-model evaluation at scale;
- inference benchmarks;
- reproducible containerized jobs;
- temporary verification replicas.

The scheduler should prefer interruptible offers for tasks that support checkpoints/retries and reliability-filtered on-demand offers for important deadlines.

Sources:

- https://docs.vast.ai/guides/get-started
- https://docs.vast.ai/api-reference/introduction
- https://docs.vast.ai/guides/instances/pricing

### 12. Decentralized compute markets such as Akash and Golem

Akash provides a decentralized marketplace for containerized CPU/GPU resources; providers bid to host deployments. Golem allows requestors to consume resources shared by provider machines, with providers compensated using the network's token.

These systems are interesting later because they already solve parts of open compute discovery and economic coordination.

However, they introduce cryptocurrency/payment and operational complexity. IDKMesh's current project goals explicitly say not to introduce a token economy in the first implementation, so these should be **optional future provider adapters**, not protocol foundations.

Sources:

- https://akash.network/
- https://akash.network/docs/getting-started/what-is-akash/
- https://docs.golem.network/
- https://docs.golem.network/docs/golem/overview

### 13. Traditional cloud spot/preemptible capacity

AWS, Azure, GCP and other conventional clouds remain valuable as a final fallback because they offer predictable APIs, regions, storage, security controls, GPUs and large capacity.

Use spot/preemptible instances for restartable Work Units and on-demand instances only when latency/reliability matters enough to justify the cost.

The Compute Fabric should treat traditional clouds exactly like any other provider: discover offer -> evaluate policy/cost -> launch -> checkpoint -> collect result -> terminate.

### 14. Community-donated servers and organization runners

A company, university, maintainer, or sponsor may donate a permanently available server/GPU.

This should join the mesh as a **project-managed trusted node**, not as an unrestricted personal GitHub self-hosted runner exposed to arbitrary public PR code.

GitHub's security documentation warns that persistent self-hosted runners can be compromised by untrusted public-repository workflows. IDKMesh should therefore execute public Work Units in disposable isolation and keep long-lived host credentials outside worker sandboxes.

Source:

- https://docs.github.com/en/actions/reference/security/secure-use

---

## One interface for all of them

The central architecture should be a small `ComputeProvider` contract.

Conceptually:

```text
interface ComputeProvider:
    discover(requirements, policy) -> offers
    launch(work_unit, offer) -> execution_id
    status(execution_id) -> state
    checkpoint(execution_id) -> checkpoint_ref
    cancel(execution_id)
    collect(execution_id) -> result_bundle
```

Candidate adapters:

```text
local
container
volunteer-node
browser-webgpu
github-actions
boinc
htcondor
ray
kubernetes
slurm
huggingface-zerogpu
saladcloud
vast
akash
golem
aws-spot
azure-spot
gcp-spot
```

IDKMesh Core should not know provider-specific details beyond this interface.

---

## Portable Work Unit envelope

To make compute portable, every execution-capable Work Unit should include enough information to run without provider-specific logic.

Example:

```yaml
id: wu-01J...
input_revision: 3b5c...
type: compute
image: ghcr.io/mskazemi/idkmesh-worker@sha256:...
command: ["python", "experiment.py", "--shard", "17"]
inputs:
  - sha256:...
requirements:
  cpu: 4
  memory_mb: 8192
  gpu:
    count: 0
  disk_mb: 20000
  architecture: [amd64, arm64]
resource_budget:
  wall_seconds: 1800
  network: restricted
  max_cost_usd: 0.10
checkpoint:
  enabled: true
  interval_seconds: 120
verification:
  replicas: 2
  independence: different_provider_if_possible
output:
  manifest: result.json
  max_bytes: 100000000
security:
  work_unit_signature: ...
  allowed_domains: []
```

The exact schema should evolve, but the architecture needs immutable inputs, explicit resource requirements, bounded permissions, a maximum cost, and a normalized output/result manifest.

---

## The effortless routing policy

The scheduler should implement **free-first opportunistic routing** rather than forcing the user to choose a provider.

Example policy:

```text
1. Is a suitable local node idle?                 -> use it
2. Is this legitimately eligible for project CI?  -> GitHub runner
3. Is a suitable volunteer node available?        -> use it
4. Is a browser/BOINC/institutional pool suitable? -> use it
5. Is grant/free shared capacity available?        -> use it
6. Is cheap interruptible market capacity enough?  -> rent it
7. Otherwise                                       -> paid reliable cloud
```

Users can override with policy:

```text
--provider local
--provider volunteer
--provider auto
--max-cost 0
--max-cost 2.00
--deadline 10m
--require-gpu 24GB
--region eu
--no-third-party-data
```

---

## Scheduling formula

For every feasible offer `p`, estimate a utility score rather than simply choosing the cheapest machine.

One first formulation:

```text
score(p) =
    + w_q * P(success | task, provider, hardware)
    + w_v * expected_verification_value
    + w_i * independence_value
    + w_l * locality_score
    - w_c * expected_cost
    - w_t * expected_latency
    - w_r * security_and_trust_risk
    - w_e * expected_energy_or_carbon_cost
```

subject to hard constraints:

```text
capability_match = true
cost <= WorkUnit.max_cost
security_policy_satisfied = true
deadline_feasible = true
```

The probability terms should be learned from actual execution history rather than permanently hand-coded.

A contextual multi-armed bandit is a natural later scheduler: explore new providers/hardware occasionally, exploit configurations with high verified-success-per-cost most of the time.

---

## Compute is also a verification resource

Extra compute should not only create more candidate outputs.

A key IDKMesh rule should be:

> When generation capacity grows, reserve a fraction of new capacity for independent verification.

Examples:

- one GPU generates candidate patches; another hardware/model stack reviews them;
- a deterministic job runs on two unrelated volunteer nodes;
- suspicious or high-value results are replicated on a trusted project-managed node;
- benchmark results are rerun on a different provider to detect environment-specific artifacts.

This turns heterogeneous compute into **independence**, not just throughput.

---

## Security architecture

The mesh must protect both the project and compute donors.

### Protect compute donors

- node pulls signed/approved Work Units; no arbitrary remote shell;
- disposable sandbox/VM/container for each job;
- host home directories and credentials are never mounted;
- network default-off or allowlisted;
- strict CPU/RAM/GPU/disk/time limits;
- visible resource use and emergency stop;
- no hidden cryptocurrency mining;
- task provenance and public project identity;
- automatic cleanup.

### Protect IDKMesh

- volunteer/market workers are untrusted;
- workers never receive merge authority;
- no long-lived repository secret inside an untrusted job;
- content-addressed immutable inputs;
- signed result manifests;
- deterministic validation where possible;
- redundant execution for important claims;
- reputation based on verified history;
- trusted infrastructure reruns critical verification.

---

## What *not* to use as a foundation

### GitHub Models

GitHub Models should not appear in the compute roadmap. GitHub currently states it was fully retired on **2026-07-30**.

Source:

- https://docs.github.com/en/github-models

### Free notebook services as unattended workers

Interactive notebook services can be useful to contributors, but they should not be the foundation of autonomous background execution because sessions, quotas, acceptable-use policies, and hardware availability are interactive/variable.

### Tightly synchronized volunteer supercomputer assumptions

Home laptops across the Internet are excellent for high-throughput asynchronous work, but poor substitutes for low-latency tightly coupled HPC/GPU fabrics. IDKMesh should decompose work into independent or weakly coupled Work Units whenever possible.

---

## Recommended implementation sequence

### Phase 0 — local provider

Implement the compute-provider interface against the existing local worker/sandbox.

Deliver:

```text
idkmesh run work.yaml --provider local
```

### Phase 1 — provider-neutral result bundle

Standardize:

- immutable input reference;
- execution manifest;
- resource usage;
- stdout/stderr/log hashes;
- output hashes;
- environment/tool versions;
- verification status.

### Phase 2 — GitHub CI adapter

Use GitHub Actions only for eligible IDKMesh development/testing work. Prove provider dispatch and normalized results without a new server fleet.

### Phase 3 — volunteer node

Implement pull-based `idkmesh-node` registration and task pickup with explicit resource controls and disposable sandboxes.

### Phase 4 — browser worker

Create an opt-in WebAssembly/WebGPU worker for a narrow deterministic benchmark or verification task. Measure participation friction and failure rates.

### Phase 5 — one institutional backend

Add either HTCondor or Slurm/Kubernetes depending on first partner demand.

### Phase 6 — one cheap paid GPU adapter

Add Vast.ai or SaladCloud as a cost-capped burst backend. Require automatic teardown and checkpoint/retry support.

### Phase 7 — learned auto-router

Start collecting `(task features, provider, hardware, cost, latency, verified success)` and learn routing policies.

### Phase 8 — BOINC/decentralized adapters only when justified

Use BOINC, Akash, Golem, or other networks when a real experiment/community use case justifies their additional operational/economic complexity.

---

## First concrete experiment

Run the same 100 small deterministic or repository-verification Work Units through multiple backends:

```text
local Docker
GitHub Actions
2-5 volunteer nodes
one cheap interruptible GPU/CPU marketplace where relevant
```

Measure:

- successful Work Units / submitted Work Units;
- verified useful work / dollar;
- verified useful work / contributor attention minute;
- queue delay and runtime;
- failure/retry rate;
- environment-induced disagreement;
- energy/resource use where measurable;
- setup friction for a new compute donor;
- security incidents/policy violations.

The experiment should answer whether provider abstraction is actually buying portability rather than only adding complexity.

---

## Community growth mechanism

Compute donation can itself become a contribution path:

```text
install node
 -> contribute first verified Work Unit
 -> public contribution receipt
 -> capability/reliability history
 -> unlock more interesting task classes
 -> help verify other contributors
 -> become compute steward / adapter maintainer
```

Recognition should emphasize **verified useful work**, uptime/reliability, replications, bugs caught, and compute made available—not raw electricity consumed or number of jobs executed.

The node should expose simple modes such as:

```text
Eco:       CPU only, AC power, max 20%
Standard:  CPU 50%, optional GPU while idle
Research:  explicit scheduled experiments
Verifier:  only independent validation jobs
Local-AI:  allow local model inference
```

This makes resource contribution understandable to non-specialists.

---

## Architectural decision

The current recommendation is:

> **Build IDKMesh as a compute liquidity router, not as a new cloud provider.**

IDKMesh should make all safe available capacity—local, donated, institutional, free, grant-backed, market-priced, or cloud—look like offers behind one Work Unit protocol.

The project's distinctive value should remain coordination, verification, provenance, matching, community, and collective intelligence. Commodity infrastructure should be integrated rather than reinvented whenever practical.
