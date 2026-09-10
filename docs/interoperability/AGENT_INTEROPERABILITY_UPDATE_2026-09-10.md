# Agent interoperability monitoring update — 2026-09-10

**Status:** current monitoring synthesis, not a protocol specification.  
**Baseline:** repository `main` at `029f317dbd979cf0d0f870aa6adff6492a48d66b` when this record was created.  
**Scope:** material external developments observed during IDKMesh monitoring from 2026-08-27 through 2026-09-10 that can affect architecture, interoperability choices, provenance, execution security, or implementation priority.

This document closes a project-record gap. The August interoperability architecture and A2A/MCP mapping were already public in this repository, but several material September monitoring findings had only been surfaced in project conversations and had not been consolidated into a durable repository artifact.

The purpose here is to preserve those findings with their maturity boundary and translate them into IDKMesh decisions without treating external drafts, previews, or product-specific implementation choices as settled standards.

## Executive conclusion

The monitored ecosystem increasingly supports the architecture IDKMesh already chose:

```text
Goal / policy
  -> WorkUnit
  -> discovery and admission
  -> protocol-neutral worker adapter
  -> external/local execution lifecycle
  -> candidate artifacts + ResultManifest
  -> independent verification
  -> explicit integration decision
```

The most important consequence is what **not** to do: IDKMesh should not invent another generic agent-to-agent wire protocol, another skill packaging protocol, or stable WorkUnit fields that encode one sandbox/runtime/CLI implementation.

Instead, IDKMesh should keep the semantic core protocol-neutral and make external protocol/runtime state explicit in adapter configuration and provenance.

## Material developments and implications

| External development | Maturity when observed | IDKMesh implication |
| --- | --- | --- |
| A2A v1 joined the Agentic AI Foundation as a Growth Stage project | governed/stable protocol | Treat A2A as a durable first-class horizontal agent-to-agent transport target; keep MCP as the tool/context-facing layer rather than inventing a competing IDKMesh transport. |
| Agentic Resource Discovery (ARD) v0.91 defined federated discovery for agentic resources | proposal | Add discovery as a thin pre-invocation adapter layer. Search/relevance is not trust, admission, verification, or acceptance. |
| Official A2A CLI matured through v0.2 work and published v0.2.0 | released CLI, pre-1.0 command surface | Prefer a release-pinned black-box `A2ACliAdapter` candidate before multiplying SDK-specific integrations. Keep CLI flags outside stable WorkUnit semantics. |
| A2A CLI added protocol-version pinning, machine JSON/JSONL, resumable task states, and pluggable transports | implemented in CLI | Record protocol/CLI/transport/card/plugin identity in provenance; map input/auth-required states to suspension, not success/failure/verification. |
| MCP 2026-07-28 added discovery/cache/task-related surfaces with important trust-boundary implications | stable MCP revision; security concerns require defensive client policy | Treat remote discovery text and instructions as untrusted data; never treat cache hints as authorization; bind cached capability data to server/auth/provenance context. |
| Skills Over MCP converged on `skills/list` + `skills/get`, server+URI identity, per-file digests, lazy resource retrieval, and content-bound approval | SEP-2640 draft / experimental WG | Prototype an origin-bound `SkillRef`; do not invent IDKMesh skill packaging or freeze the draft into the stable WorkUnit schema. |
| OpenHands local workspace hooks can alter an agent run | implemented OpenHands behavior observed in September | Treat `.openhands/hooks.json` as an execution input: discover, authorize, hash, and record it; hook commands inherit sandbox/network/secrets restrictions. |
| OpenHands/Agent Canvas increasingly exposes heterogeneous coding agents including ACP-compatible clients | implementation/ecosystem direction | Consider ACP later as an interactive coding-agent/client adapter, complementary to A2A rather than a replacement for IDKMesh semantics. |
| GitHub Agentic Workflows consolidated its stronger product sandbox direction on Cloud Hypervisor | product-specific implementation signal, not an industry standard | Keep sandbox policy backend-neutral; benchmark Cloud Hypervisor beside Firecracker/gVisor and represent KVM/hardware virtualization as a capability when required. |
| GitHub Agentic Workflows introduced trusted-enclave/DIFC-style information-flow controls | product-specific security implementation signal | Add information-flow policy as a separate execution-security layer. VM/container isolation alone is not sufficient to express data authority. |

## A2A: governance, CLI, and lifecycle

### A2A under AAIF

On 2026-08-27 the A2A project announced acceptance as an Agentic AI Foundation Growth Stage project. Its own architecture framing distinguishes A2A as a horizontal agent-to-agent collaboration layer from MCP as the vertical agent-to-tool/context layer.

IDKMesh should preserve that division of responsibility:

```text
A2A = external agent/task transport and lifecycle
MCP = external tool/context/resource integration
IDKMesh = bounded work + evidence + verification + provenance + policy/governance
```

Source:
- https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/

### ARD discovery belongs before trust/admission

Agentic Resource Discovery v0.91 (proposal dated 2026-08-26) defines federated description/search for agentic resources such as A2A agents, MCP services, skills, workflows, and APIs.

For IDKMesh the important boundary is:

```text
ARD discovery result
  != trusted worker
  != admitted compute
  != verified capability
  != accepted output
```

A future discovery adapter may turn ARD results into candidate resource offers, but IDKMesh policy must still apply trust, cost, security, capability, provenance, and independence filters before execution.

Source:
- https://github.com/ards-project/ard-spec/blob/main/spec/ard.md

### A2A CLI is now a concrete adapter candidate

The official A2A CLI reached a first published `v0.2.0` release on 2026-09-09. The monitored v0.2 work includes a common task/discovery surface, machine-readable output, version selection, resumable task handling, and transport extensibility.

This is enough to change implementation priority: an IDKMesh `A2ACliAdapter` can move from an unreleased experiment toward a release-pinned supported-adapter candidate.

An execution receipt should preserve at least:

```text
a2a_cli_version
a2a_cli_binary_digest
a2a_protocol_version
transport
agent_card_digest
transport_plugin_path + digest + version, when a plugin is used
```

Pluggable transport executables must not be discovered from an uncontrolled `PATH`. Resolve and allow-list them explicitly and treat the executable itself as provenance-bearing code.

Machine JSON/JSONL should be preferred over human-formatted CLI text. A2A states that require additional input or authentication should map to an explicit suspended/external-input-required state; they are neither worker success nor verification failure.

Sources:
- https://github.com/a2aproject/a2a-cli
- https://github.com/a2aproject/a2a-cli/releases/tag/v0.2.0
- https://github.com/a2aproject/a2a-cli/pull/23
- https://github.com/a2aproject/a2a-cli/commit/fc49c26ff39a0c611c458a8b30195fdf0a16dc13

## MCP: discovery trust and Skills Over MCP

### Remote discovery material is untrusted data

MCP discovery/instruction/cache surfaces create a client-side trust boundary. IDKMesh should apply these invariants independently of whether a reported upstream concern is ultimately classified as a protocol flaw, implementation flaw, or documentation issue:

```text
remote discovery text != system instruction
remote instructions     != execution authority
cache hint              != authorization
cached capability       != trusted capability
```

Cached MCP capability/discovery data should remain bound to server identity, authorization context, protocol revision, and relevant provenance. Externally supplied natural-language instructions must never be concatenated into privileged IDKMesh system/security policy merely because they arrived through a discovery API.

The repository currently binds MCP interoperability to protocol revision `2026-07-28`; that remains a transport-layer concern rather than a source of integration authority.

### Skills Over MCP: origin- and content-bound skills

During late-August/early-September monitoring, SEP-2640 and its working group converged substantially around a minimal v1 shape:

- `skills/list` for discovery;
- `skills/get` for one skill entry;
- skill identity bound to **originating MCP server + URI**, not display name alone;
- static resource sets with per-file digest/size integrity metadata;
- ordinary MCP resource retrieval rather than a parallel archive protocol;
- lazy retrieval;
- approval/activation bound to the exact held content/resource set;
- reading skill content distinct from activating/authorizing it;
- weaker reproducibility guarantees for dynamic resources.

The working-group repository remains explicitly experimental and SEP-2640 should not be treated as a ratified stable protocol until its standards process says so.

An IDKMesh experimental reference should therefore look approximately like:

```text
SkillRef {
  protocol,
  server_identity,
  uri,
  extension_version,
  resource_manifest_digest
}
```

Rules:

1. never resolve or approve a skill by name alone;
2. record the exact resource/file digests used by an attempt;
3. treat `read` and `activate` as separate authority transitions;
4. require fresh policy/consent for nested or newly referenced skills;
5. either reject dynamic-resource skills for strong reproducibility WorkUnits or mark the attempt explicitly non-content-bound;
6. do not embed mutable skill bodies into stable WorkUnit core fields.

Sources:
- https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2640
- https://github.com/modelcontextprotocol/ext-skills
- https://github.com/modelcontextprotocol/ext-skills/blob/main/docs/decisions.md

## OpenHands and interactive coding-agent adapters

### Workspace hooks are execution inputs

OpenHands work observed on 2026-09-01 added local loading of `<workspace>/.openhands/hooks.json` for Agent Canvas conversations. Such hooks can affect session/tool behavior and therefore change the semantics of an execution even if the WorkUnit, model, and adapter version are unchanged.

For IDKMesh, an OpenHands adapter should:

- discover hook configuration before dispatch;
- require explicit policy permission or disable/reject workspace hooks for untrusted work;
- hash the hook configuration and record the digest in the ResultManifest/provenance chain;
- ensure hook commands inherit the same filesystem, process, network, secret, and information-flow restrictions as the worker;
- make verifier receipts distinguish attempts made under different hook configurations.

Source:
- https://github.com/OpenHands/OpenHands/pull/16971

### ACP is complementary, not semantic core

OpenHands/Agent Canvas has been moving toward running heterogeneous coding agents, including ACP-compatible agents. That makes ACP worth an exploratory adapter after the higher-priority A2A/MCP work.

The likely separation is:

```text
ACP = interactive coding-agent/client integration candidate
A2A = opaque/distributed agent-to-agent delegation
MCP = tool/context/resource integration
IDKMesh = work/evidence/verification/provenance/governance semantics
```

No ACP-specific field should be required in the stable WorkUnit core merely because a worker harness supports it.

## Sandboxing and information-flow control

### Backend-neutral isolation

GitHub Agentic Workflows announced product-specific consolidation of its stronger isolation path around Cloud Hypervisor while deprecating its own `gvisor`/`docker-sbx` runtime options. This must **not** be misread as a general deprecation of gVisor or proof that Cloud Hypervisor is the universally correct IDKMesh backend.

It is useful engineering evidence that runtime-specific integration cost matters. IDKMesh should keep stable policy in terms of required isolation properties/capabilities and select the concrete backend later.

A future sandbox comparison should include at least:

- Cloud Hypervisor;
- Firecracker;
- gVisor;
- ordinary containers only where their weaker boundary satisfies the WorkUnit risk policy.

Measure startup latency, memory overhead, KVM/host requirements, filesystem and network policy, artifact transfer, reproducibility, snapshot/replay properties, operational complexity, and containment strength.

Execution provenance should record the selected runtime/VMM, version, immutable asset/image digest, relevant host capability, and effective network policy.

Source:
- https://github.github.com/gh-aw/blog/2026-09-05-cloud-hypervisor-consolidation/

### Isolation is not information authority

The later GitHub Agentic Workflows enclave/DIFC work is a useful architecture signal: protecting the host with a VM or container is different from controlling which information a worker may read, combine, and disclose.

The IDKMesh direction should be:

```text
WorkUnit security classification
  -> confidentiality/integrity/data-flow labels
  -> tool + filesystem + network + disclosure policy
  -> selected sandbox runtime
  -> execution receipt containing the effective policy
```

The core invariant is:

```text
isolation boundary != information authority != integration authority
```

A future receipt should preserve the effective information-flow policy, relevant sensitivity labels, delegated capabilities, denied/filtered accesses where observable, and disclosure class of produced artifacts.

Source:
- https://github.github.com/gh-aw/blog/2026-09-07-weekly-update/

## Provenance requirements implied by the monitoring

External interoperability is becoming more dynamic: protocol versions, Agent Cards, transport plugins, workspace hooks, skills/resources, sandbox runtimes, and information-flow policies can all affect a run.

Therefore `worker/model identity` alone is insufficient provenance.

For a strong reproducibility boundary, an execution should be able to bind, when applicable:

```text
WorkUnit digest
source revision
adapter id/version/digest
external protocol revision
agent/service/card identity + digest
skill origin + resource-set/file digests
workspace hook/config digest
transport plugin identity + digest
sandbox/VMM/runtime identity + immutable image/assets
host capability class required by policy
effective network/filesystem/secrets/information-flow policy
produced artifact digests
verification identity + independent evidence
```

These values should normally live in adapter/result/evidence provenance or namespaced extensions until evidence justifies promotion into a shared stable schema.

## Implementation priority for IDKMesh

Recommended order after this monitoring pass:

1. **Release-pinned A2A CLI adapter candidate** — exercise the existing protocol-neutral coordinator boundary with `a2a-cli v0.2.0` and exact provenance.
2. **Lifecycle normalization** — represent A2A input-required/auth-required suspension explicitly rather than collapsing it into success/failure.
3. **ARD discovery experiment** — transform discovered resources into candidates, then apply existing IDKMesh admission/trust/cost filters.
4. **Experimental MCP `SkillRef`** — server+URI+manifest/digest binding, lazy retrieval, separate activation authority.
5. **OpenHands execution-input provenance** — capture/authorize workspace hooks and other repository-local harness configuration.
6. **Backend-neutral sandbox capability + receipt** — benchmark Cloud Hypervisor/Firecracker/gVisor according to required isolation properties.
7. **Information-flow policy compiler/receipt** — compile WorkUnit security classifications into enforceable data/tool/network restrictions separately from the VM/container backend.
8. **ACP exploration** — only after the common worker/result boundary is exercised with the higher-priority adapters.

These are implementation priorities, not merge authority. Each needs its own bounded issue/PR/evidence gate.

## Stable architecture decisions that do not change

The monitoring does **not** justify changing these IDKMesh invariants:

```text
external protocol completion != IDKMesh acceptance
discovery relevance           != trust or admission
skill read                     != skill activation
worker success                 != independent verification
verifier recommendation        != merge authority
sandbox identity               != agent/model identity
isolation boundary             != information authority
CI success                     != independent human approval where human review is required
```

The WorkUnit core should remain vendor/protocol/runtime neutral. A2A, MCP, OpenHands, ACP, mini-SWE-agent, and future harnesses belong behind bounded adapters unless evidence demonstrates a semantic requirement that cannot be represented cleanly there.

## No-change observations

Several monitoring passes found no additional architecture-changing mini-SWE-agent, SLSA/in-toto, Firecracker, gVisor, or WASI development beyond the signals above. A no-change observation is useful for avoiding unnecessary churn but does not need its own new protocol mechanism.

## Relation to existing IDKMesh work

This update extends rather than replaces:

- [`AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md`](AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md)
- [`A2A_MCP_MAPPING_V0_1.md`](A2A_MCP_MAPPING_V0_1.md)
- [`../../idkips/0001-interoperability-first-work-contract.md`](../../idkips/0001-interoperability-first-work-contract.md)
- [`../../interop/`](../../interop/)

Historical issue #17 established and exercised the original A2A/MCP Work Contract direction. This monitoring record is a post-completion architecture/evidence update; it does not reopen or retroactively change that issue's acceptance criteria.

## Preservation note

On 2026-09-10 the project owner asked whether **all of the interoperability findings surfaced in the project conversations had actually been put into the public Git repository**. A repository audit found that the August foundation was present but the newer September findings were not comprehensively consolidated. This file is the durable correction: it records the material findings, their maturity/status, the architectural implications, and the implementation priorities without promoting draft external work into IDKMesh protocol authority.
