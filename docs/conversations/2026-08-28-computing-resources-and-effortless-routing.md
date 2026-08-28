# Conversation Record — Computing Resources and Effortless Routing

**Date:** 2026-08-28

## Project-owner question

What computing resources can IDKMesh use, and how can it use those resources effortlessly?

Repository: https://github.com/MSKazemi/idkmesh

## Answer summary

IDKMesh should avoid binding itself to one compute provider. The recommended direction is a **provider-neutral Opportunistic Compute Fabric** driven by the existing bounded Work Unit abstraction.

The core user experience should eventually be as simple as:

```text
idkmesh run work-unit.yaml --provider auto --budget 0.50
```

The system should automatically choose among local compute, GitHub-native CI when policy permits, volunteer nodes, browser/WebGPU workers, institutional pools, grant/free capacity, interruptible GPU marketplaces, and traditional cloud fallback.

## Main compute sources identified

1. Local laptops/workstations through `idkmesh-node`.
2. GitHub-hosted Actions runners for legitimate project build/test/deployment/publication-related work.
3. Volunteer IDKMesh nodes contributing bounded CPU/GPU/RAM.
4. Browser WebAssembly/WebGPU workers for zero-install opt-in compute.
5. BOINC/BOINC Central for large weakly coupled scientific workloads and as a design reference.
6. HTCondor pools in universities, labs, and companies.
7. Existing Ray/Kubernetes/Slurm clusters through adapters.
8. Hugging Face ZeroGPU for selected public demos and small GPU tasks.
9. Cloudflare Workers as a low-cost control plane and optional lightweight AI routing layer.
10. Distributed GPU services such as SaladCloud.
11. GPU marketplaces such as Vast.ai for cheap burst/interruptible capacity.
12. Decentralized compute markets such as Akash and Golem as optional later adapters.
13. Traditional cloud spot/preemptible capacity as a reliable final fallback.
14. Community/sponsor-donated servers as project-managed trusted nodes.

## Key architectural proposal

Introduce a `ComputeProvider` abstraction roughly shaped as:

```text
discover(requirements, policy) -> offers
launch(work_unit, offer) -> execution_id
status(execution_id) -> state
checkpoint(execution_id) -> checkpoint_ref
cancel(execution_id)
collect(execution_id) -> result_bundle
```

Provider adapters can then be added without changing the Work Unit model.

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

## Effortless scheduling principle

Use a free-first opportunistic policy:

```text
local idle resource
 -> eligible project CI
 -> volunteer node
 -> browser/BOINC/institutional capacity
 -> grant/free shared capacity
 -> cheap interruptible market capacity
 -> normal paid cloud fallback
```

The scheduler should optimize verified success, independence, locality, cost, latency, security risk, and potentially energy/carbon rather than raw price alone.

## Important policy finding

GitHub-hosted Actions runners are very useful for IDKMesh, but they should not be treated as a generic free supercomputer. Current GitHub terms restrict hosted-runner use to activity connected to production, testing, deployment, or publication of the software project and prohibit disproportionate load.

The broker should therefore explicitly encode whether a Work Unit is eligible for GitHub CI execution.

## Important correction

GitHub Models should not be part of the compute roadmap: GitHub documentation currently states that GitHub Models was retired on 2026-07-30.

## Security principle

Workers and workloads are mutually untrusted.

Volunteer and market nodes should:

- pull bounded signed/approved Work Units rather than accept arbitrary remote shell access;
- execute in disposable isolation;
- have default-off/restricted network access;
- receive strict CPU/RAM/GPU/disk/time limits;
- never expose contributor home directories or credentials;
- return candidate artifacts and evidence rather than merge directly.

The project should independently verify important results and reserve some compute specifically for verification as generation capacity grows.

## First recommended implementation

1. Build the `ComputeProvider` interface around the current local sandbox.
2. Standardize the provider-neutral result bundle and provenance manifest.
3. Add a GitHub Actions adapter for eligible development/testing Work Units.
4. Build pull-based volunteer-node task pickup.
5. Add one narrow browser WebGPU/WASM worker experiment.
6. Add one institutional scheduler adapter when a partner exists.
7. Add one cost-capped paid GPU adapter.
8. Collect execution history and learn provider selection with a contextual bandit or related adaptive scheduler.

## Durable artifact

A full architecture proposal has been added at:

- `docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md`

## Community impact

Compute becomes a first-class contribution path. A contributor should eventually be able to install a node, select a safe resource profile, contribute verified Work Units, build a public reliability/capability history, and progress into verification or compute-steward roles without needing repository write permission.
