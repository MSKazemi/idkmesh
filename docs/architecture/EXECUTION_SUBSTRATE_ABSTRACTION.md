# Execution Substrate Abstraction

**Status:** Working architecture proposal  
**Date:** 2026-09-17  
**Scope:** the execution boundary *after* compute admission and before result/verification contracts

## Decision in one sentence

IDKMesh should treat a WorkUnit attempt as a **logical execution** whose identity and provenance survive physical sandbox placement changes; Kubernetes Pods, sandbox objects, actor workers, VMs, containers, and local processes are replaceable execution-substrate details rather than canonical task identity.

This refines, rather than replaces, the provider-neutral scheduling in [Opportunistic Compute Fabric](OPPORTUNISTIC_COMPUTE_FABRIC.md) and [Resource to Compute Admission](RESOURCE_COMPUTE_ADMISSION.md).

```text
WorkUnit + attempt
      |
      v
compute/resource admission
      |
      v
logical execution identity
      |
      v
ExecutionSubstrate adapter
      |
      +---- local/container/process
      +---- Kubernetes Agent Sandbox
      +---- actor/worker multiplexing substrate
      +---- future HPC/batch/runtime backend
      |
      v
runtime placements / suspend-resume lineage
      |
      v
ResultManifest + runtime provenance
      |
      v
independent verification
```

The invariant is:

> **Logical execution identity must not be inferred from physical placement identity.**

A pod restart, worker reassignment, suspend/resume cycle, checkpoint restore, or migration must not silently create a new WorkUnit attempt. Conversely, reusing a physical worker must not make two logical attempts the same execution.

## Why this boundary became urgent

Two current open execution systems now expose materially different lifecycle models while solving adjacent agent-sandbox problems.

### Kubernetes Agent Sandbox

The Kubernetes SIG Agent Sandbox project reached the 1.0 line in September 2026. Its current APIs use `v1beta1`; the project provides `Sandbox`, `SandboxClaim`, `SandboxTemplate`, and `SandboxWarmPool` concepts for isolated, stateful singleton workloads and warm allocation. It explicitly targets AI-agent runtimes and untrusted generated code and supports stronger isolation runtimes such as gVisor or Kata Containers.

The important architectural property for IDKMesh is that the **sandbox is a stable agent-facing resource while Kubernetes still owns backing workload placement and lifecycle**. IDKMesh should therefore integrate it as an execution provider, not copy its CRDs into the WorkUnit contract.

References:

- [Kubernetes SIG Agent Sandbox repository](https://github.com/kubernetes-sigs/agent-sandbox)
- [Agent Sandbox releases](https://github.com/kubernetes-sigs/agent-sandbox/releases) — v1.0.2 released 2026-09-11; v1.0.0 removed legacy `v1alpha1` APIs in favor of `v1beta1`.

### Agent Substrate

Google announced Agent Substrate availability on GKE on 2026-09-15, while the core project is open source. Its model separates an **Actor** (logical stateful workload) from a **Worker** (sandbox that currently hosts an active actor). Idle actors can be suspended, snapshotted, and later restored onto an available worker. That means physical placement is intentionally transient.

Google currently documents GKE Agent Substrate for evaluation/non-production use for all customers, with production support gated separately. Vendor-reported density and latency numbers are useful engineering signals, not IDKMesh evidence; IDKMesh should not repeat them as independently validated performance claims.

References:

- [Google Cloud announcement, 2026-09-15](https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
- [Google Cloud: About GKE Agent Substrate](https://docs.cloud.google.com/kubernetes-engine/ai-ml/about-agent-substrate)
- [Open-source Agent Substrate repository](https://github.com/agent-substrate/substrate)

These systems can coexist. One is naturally close to a stable sandbox object backed by Kubernetes resources; the other deliberately multiplexes many logical actors over fewer physical workers. IDKMesh should be able to use either without redefining its task/evidence semantics.

## Architectural role

The execution substrate sits below the canonical WorkUnit and above concrete runtime placement.

It is responsible for runtime mechanics such as:

- allocating an isolated execution environment;
- activating an admitted WorkUnit attempt;
- attaching bounded workspace/state;
- injecting runtime-scoped credentials without making them part of the WorkUnit payload;
- suspending/checkpointing when supported;
- resuming or rebinding onto another physical worker when supported;
- exposing runtime health and termination state;
- terminating and cleaning up execution resources;
- returning provenance needed to explain where and how the attempt ran.

It is **not** responsible for:

- deciding whether a WorkUnit is correct;
- granting merge/integration authority;
- changing repository spending policy;
- translating A2A/MCP/ACP semantics into IDKMesh truth;
- treating physical isolation as proof of verifier independence.

## Minimal provider-neutral lifecycle

A future implementation should support a small capability-driven lifecycle instead of assuming every backend implements hibernation or migration.

```text
admitted
   |
   v
allocated --> active --> completed --> terminated
                 |
                 +--> suspended --> active
                 |
                 +--> failed -----> terminated
```

Suggested provider-neutral operations:

```python
class ExecutionSubstrate(Protocol):
    def allocate(self, spec: ExecutionSpec) -> ExecutionHandle: ...
    def activate(self, handle: ExecutionHandle) -> RuntimeEndpoint: ...
    def suspend(self, handle: ExecutionHandle) -> SnapshotRef | None: ...
    def resume(
        self,
        handle: ExecutionHandle,
        snapshot: SnapshotRef | None = None,
    ) -> RuntimeEndpoint: ...
    def terminate(self, handle: ExecutionHandle) -> None: ...
```

This is an architecture sketch, not a committed Python API. Backends advertise capabilities such as `suspend_resume`, `checkpoint`, `network_policy`, `strong_kernel_isolation`, `persistent_workspace`, or `gpu` rather than forcing fake implementations of unsupported operations.

## Identity model

At minimum, execution evidence should be able to distinguish the following identities:

| Identity | Meaning | Stability |
| --- | --- | --- |
| `work_unit_id` | canonical bounded task | stable across attempts |
| `attempt` | canonical attempt number | stable for that attempt |
| `logical_execution_id` | runtime execution lineage for the attempt | stable across supported suspend/resume or placement changes |
| `substrate_provider` | adapter/backend class and version | stable for recorded execution evidence |
| `substrate_instance_id` | provider-side sandbox/actor/session identity | provider-defined |
| `placement_id` | current pod/worker/node/process/VM identity | explicitly transient |
| `snapshot_id` / `restored_from` | checkpoint lineage when used | immutable evidence reference |
| `isolation_class` | observed/requested runtime isolation | evidence, not trust by assertion |
| `policy_digest` | exact admission/security policy revision used | immutable evidence reference |

The canonical IDKMesh attempt must never be derived from `placement_id`.

For example, an Agent Substrate Actor may keep one `logical_execution_id` while running first on Worker A and later on Worker B. A Kubernetes Agent Sandbox may keep one provider sandbox identity while a backing runtime is restarted or restored. A local backend may have no migration at all but should still populate the same logical/provenance boundary.

## Provenance requirements

Runtime provenance should make relocation and resume history auditable without pretending that infrastructure metadata proves task correctness.

A ResultManifest-compatible execution record should eventually be able to bind:

```text
WorkUnit id/version/attempt
logical execution id
substrate provider + adapter version
provider-side sandbox/actor/session id
ordered placement lineage
isolation/runtime class
admission policy digest
workspace/snapshot lineage
runtime-scoped credential reference or scope metadata (never secret material)
start/stop/suspend/resume events
produced artifact digests
```

Snapshots themselves may be large or sensitive; canonical provenance should normally store immutable references/digests and lifecycle evidence rather than embedding snapshot contents.

### Independence warning

Two verifiers running in different pods are not automatically independent. They may still share a model, prompt lineage, provider, dependency, dataset, network service, or failure mode. Execution-substrate separation is one useful evidence channel, not a replacement for the existing worker/verifier independence contract.

## Credentials and authority

Execution credentials should be **runtime-scoped and short-lived** wherever the backend permits it.

The WorkUnit describes required permissions; the admitted execution layer materializes the minimum concrete credentials for those permissions. A backend should not receive a broad repository/cloud credential simply because the WorkUnit needs one narrow operation.

The provenance record should contain credential *scope/issuer/reference metadata* sufficient for audit, never secret values.

This preserves three different identities:

```text
task identity != agent identity != runtime/sandbox identity
```

and avoids coupling protocol identity (for example, an A2A agent or MCP client) to infrastructure identity.

## Mapping current/future backends

### Local process/container

Use as the simplest reference provider. It may support only allocate/activate/terminate. The lack of hibernation is a capability fact, not an error in the abstraction.

### Kubernetes Agent Sandbox

Map the stable provider resource to `substrate_instance_id`; record backing pod/node data as placement evidence. `SandboxClaim`/warm-pool allocation belongs inside the provider adapter. Do not put Kubernetes CRD fields in WorkUnit core semantics.

The adapter target should be the current `v1beta1` API line, not removed `v1alpha1` resources.

### Agent Substrate

Map Actor identity to the provider instance/logical runtime lineage and Worker identity to transient placement. Suspend/resume can preserve the logical execution while appending snapshot and placement events.

IDKMesh should not make GKE a required dependency: the core substrate project is open source and the provider abstraction remains Kubernetes/cloud neutral.

### HPC / batch scheduler

An HPC provider can map a logical execution onto one or more scheduler job allocations. Preemption/requeue/checkpoint-restart should append placement/allocation lineage rather than mutate the WorkUnit identity. MPI/rank topology or accelerator allocation belongs in execution evidence when material to reproducibility.

## Relationship to agent protocols

A2A, MCP, and ACP solve different boundaries from the execution substrate.

```text
IDKMesh semantic contract
  WorkUnit / ResultManifest / VerificationResult
            |
            v
agent/tool interoperability
  A2A / MCP / ACP / framework adapters
            |
            v
execution substrate
  local / sandbox / actor-worker / HPC
            |
            v
physical placement
  process / container / pod / VM / node / worker
```

A remote A2A worker can execute inside a Kubernetes Agent Sandbox. An MCP server can run as a substrate actor. An ACP coding harness can be hosted in either. These are composable axes; none should be encoded as if it were the other.

## Implementation priorities

The next implementation should be deliberately small:

1. define an internal `ExecutionHandle`/provenance shape with separate logical and physical identity;
2. implement the existing local execution path behind that boundary without changing WorkUnit semantics;
3. add lifecycle conformance tests proving that placement changes cannot change the logical attempt identity;
4. prototype one Kubernetes Agent Sandbox `v1beta1` provider behind the same interface;
5. add suspend/resume only as a capability after a backend can demonstrate it;
6. evaluate Agent Substrate as a second, structurally different backend to test whether the abstraction really decouples actor identity from worker placement;
7. treat provider performance claims as hypotheses until IDKMesh-controlled benchmarks produce observed evidence.

The key conformance case is not “can it start a pod?” It is:

> **Can two radically different runtime models execute the same canonical WorkUnit attempt while producing unambiguous, comparable lifecycle and provenance evidence?**

## Non-goals

This proposal does not:

- select Google Cloud, GKE, Agent Substrate, or Agent Sandbox as mandatory infrastructure;
- claim that IDKMesh currently supports suspend/resume, migration, or million-agent scale;
- change the WorkUnit, ResultManifest, or VerificationResult schemas;
- authorize paid cloud use or relax the zero-project-spend policy;
- claim that sandbox isolation alone makes an agent trustworthy;
- require snapshots or hibernation from simple/local/HPC providers;
- create a new general-purpose orchestration protocol.

## Evidence boundary

The external projects cited above establish that multiple execution models now exist and expose concrete APIs/lifecycles worth interoperating with. They do **not** establish that their vendor-reported throughput, density, latency, isolation, or production readiness transfers to IDKMesh workloads.

IDKMesh should record four states separately:

1. architecture mapping exists;
2. adapter implementation exists;
3. conformance/lifecycle tests pass;
4. observed workload evidence exists.

Only the fourth can support IDKMesh-specific performance or reliability conclusions.
