# IDKIP-0001: Interoperability-first Work Contract

- **Status:** Experimental
- **Authors:** IDKMesh bootstrap project
- **Created:** 2026-08-28
- **Discussion:** GitHub issue to be linked
- **Implementation:** issues #3, #4, #6 plus follow-up interoperability tasks

## Summary

IDKMesh should define its core Work Contract as a **scheduling, verification, evidence, and provenance envelope** that can map onto existing agent/task protocols rather than defining a new generic remote-agent transport.

The first interoperability targets should be:

- Agent2Agent (A2A) Task / Agent Card / Artifact;
- Model Context Protocol (MCP) tool calls plus the Tasks extension where appropriate;
- direct local adapters for coding-agent harnesses such as mini-SWE-agent and OpenHands.

## Problem

IDKMesh needs a machine-readable unit of bounded work, but the agent ecosystem is converging around open interoperability protocols.

If IDKMesh defines a complete competing agent protocol too early, it risks:

- unnecessary implementation work;
- a smaller compatible ecosystem;
- duplicated discovery/task-lifecycle concepts;
- contributor confusion;
- long-term maintenance of commodity transport concerns rather than the project's distinctive research layer.

At the same time, A2A and MCP do not define all of the information IDKMesh needs for verification-first collective engineering.

Examples of IDKMesh-specific requirements include:

- risk/trust class;
- allowed files/resources/actions;
- dependency graph;
- expected evidence;
- verification policy;
- replication/diversity policy;
- resource/capability hints;
- provenance requirements;
- integration/acceptance policy.

## Motivation

As of 2026, A2A provides an open agent interoperability model with Agent Cards, skills, stateful Tasks, Messages, and Artifacts. MCP has become a major tool/context substrate and its Tasks extension provides durable asynchronous task handles for long-running operations.

IDKMesh can move faster and attract more external implementations by fitting into this ecosystem.

The project's innovation budget should be spent primarily on:

- collective task decomposition;
- verification;
- evidence;
- diversity/error correlation;
- scheduling;
- uncertain goal management;
- integration policy;
- community-scale coordination.

## Scope

This proposal defines the architectural relationship between the IDKMesh Work Contract and external task/agent protocols.

## Non-goals

This proposal does not:

- freeze the final JSON fields of WorkUnit v0;
- require every worker to implement A2A or MCP;
- require networked execution for the first release;
- replace GitHub collaboration;
- standardize model prompts or internal agent reasoning;
- define an economic settlement protocol.

## Proposal

### 1. Define the Work Contract as an IDKMesh semantic envelope

The Work Contract should contain the information needed by coordinator, scheduler, worker adapter, verifier, and integrator.

Conceptual groups:

```text
identity
  id, project, goal/task references, version

intent
  objective, scope, constraints, dependencies

capability/resource contract
  required capabilities, CPU/GPU/memory hints, timeout, environment

execution policy
  allowed paths/actions/network, sandbox/risk class

verification contract
  expected artifact types, verifier policy, hidden-check references,
  replication/diversity requirements, acceptance threshold

provenance contract
  input hashes, required environment/tool metadata, signatures/attestations

integration policy
  candidate-only / human-review / merge restrictions

interop metadata
  transport/adapter-specific references without coupling core semantics
```

### 2. ResultManifest becomes an Evidence Report

The result object should not merely say that a worker finished.

It should return:

- candidate artifact references/hashes;
- patch/branch/worktree reference where relevant;
- worker/adapter identity and version;
- environment/tool/model provenance;
- execution logs/metrics references;
- self-reported confidence where useful;
- tests run by the worker, clearly distinguished from independent verification;
- reproducibility information;
- signatures/attestations where enabled.

Independent verifier results should remain separable so a worker cannot certify itself.

### 3. A2A mapping

A2A should be treated as a candidate remote-agent interoperability transport.

Possible mapping:

```text
IDKMesh worker capability
    <-> A2A Agent Card + skills

IDKMesh Work Contract invocation
    -> A2A Message / Task request with structured Part metadata

long-running worker lifecycle
    <-> A2A Task state

candidate outputs
    <-> A2A Artifacts

IDKMesh-specific verification/scheduling data
    -> A2A extension / structured data Part
```

IDKMesh should explore a declared A2A extension for the Work Contract instead of modifying A2A core semantics.

### 4. MCP mapping

MCP remains especially useful for tools/resources available to an agent or coordinator.

Where a Work Contract is naturally implemented as a tool operation:

```text
IDKMesh operation
   -> MCP tools/call

long-running execution
   -> MCP Tasks extension

status/result
   <- durable task handle + final tool result
```

MCP should not be forced into every worker relationship. A2A and direct adapters may be more natural for autonomous remote agents.

### 5. Direct adapters remain first-class

The local v0.1 runner should not require a network protocol.

A simple interface should allow adapters such as:

- local subprocess/shell;
- mini-SWE-agent;
- OpenHands;
- human/GitHub task;
- A2A remote agent;
- MCP-backed task/tool.

This makes the core testable before distributed networking exists.

### 6. Core must remain vendor-neutral

The core Work Contract must not contain mandatory fields specific to one model provider, coding agent, Git forge, or cloud.

Provider-specific metadata belongs in namespaced adapter/provenance fields.

## Alternatives considered

### Alternative A — Invent a complete IDKMesh agent protocol now

Rejected as the default direction because it duplicates rapidly standardizing ecosystem primitives and increases community burden.

It remains possible to define a custom wire protocol later if experiments reveal requirements A2A/MCP cannot satisfy.

### Alternative B — Use A2A Task directly as the WorkUnit

Not sufficient. A2A intentionally focuses on interoperability and task/artifact exchange, not IDKMesh-specific resource scheduling, verification, risk, provenance, or integration policy.

### Alternative C — Use MCP Task directly as the WorkUnit

Not sufficient. MCP Tasks are asynchronous handles augmenting tool calls; they are not a complete collective-engineering work/evidence contract.

### Alternative D — Delay interoperability entirely

This risks freezing core schemas that are awkward to map later and creating unnecessary rework.

## Interoperability / compatibility

WorkUnit v0 should be designed so transport-specific bindings can be added without changing core semantics.

A first compatibility test should round-trip one logical coding Work Contract through:

1. a direct local adapter;
2. an A2A-style representation;
3. an MCP Tasks-style representation where appropriate.

Semantic information must not silently disappear during mapping. Fields without direct external equivalents should remain in an IDKMesh extension/envelope.

## Security / abuse considerations

Interoperability increases the number of trust boundaries.

The core must distinguish:

- discovery metadata from trusted capability evidence;
- worker self-report from independent verification;
- task status from correctness;
- authentication from authorization;
- artifact transport from artifact trust.

A remote agent completing an A2A/MCP task does **not** imply that IDKMesh should accept its artifact.

Verification policy remains authoritative.

## Community Impact

Positive effects:

- contributors can build adapters without changing core coordination logic;
- users can bring existing agent systems;
- IDKMesh becomes easier to integrate into external projects;
- less project effort is spent maintaining commodity protocol machinery;
- standards-oriented contributors get a clear workstream.

Costs:

- contributors need clear documentation explaining the difference between IDKMesh Work Contract semantics and A2A/MCP task lifecycles;
- compatibility tests become a permanent maintenance responsibility;
- external protocol evolution must be tracked.

## Measurable success criteria

Before accepting this IDKIP permanently:

1. One logical Work Contract can execute through at least two heterogeneous worker adapters.
2. An A2A mapping can represent the relevant worker lifecycle/artifacts without losing IDKMesh verification requirements.
3. An MCP mapping is documented for tool/task cases where it is appropriate.
4. Core scheduler/verifier code does not need model/vendor-specific branching for those adapters.
5. Adding a new worker adapter is demonstrably smaller than implementing a new coordinator path.
6. Contributors can understand the mapping from documentation/examples without reading protocol implementation internals.

## Experiment / evidence plan

### E-0001-A — semantic mapping table

Create a field-by-field mapping between WorkUnit/ResultManifest draft fields and A2A/MCP concepts. Mark each field as:

- direct mapping;
- extension metadata;
- IDKMesh-only;
- external-only;
- incompatible/ambiguous.

### E-0001-B — adapter prototype

Run the same small repository task through two adapters behind one coordinator interface.

### E-0001-C — protocol round trip

Serialize a Work Contract into an A2A-compatible structured request, execute or mock the lifecycle, and reconstruct the IDKMesh result/evidence representation.

### E-0001-D — contributor test

Ask a contributor unfamiliar with coordinator internals to implement a trivial worker adapter from the public interface/docs.

## Dissent / unresolved questions

- Should the Work Contract be one schema or a smaller core plus DomainPack extensions?
- Should A2A interoperability live in core or a plugin package?
- Is MCP primarily a worker capability interface, coordinator tool interface, or both?
- What namespaces/versioning strategy should extension metadata use?
- Should human workers have the same adapter protocol or a separate GitHub-native lifecycle mapped into the same evidence model?
- How much resource scheduling data belongs in the portable contract versus local scheduler policy?

## Migration / rollback

Issue #3 schemas are not yet frozen, so this proposal can influence them with low migration cost.

If A2A/MCP integration proves burdensome, direct adapters remain valid and external mappings can be removed without changing the core verification semantics.

## Implementation links

- Issue #3 — WorkUnit v0 and ResultManifest v0
- Issue #4 — single-machine multi-worker orchestrator
- Issue #6 — ProjectManifest and DomainPack
- `EVOLUTION.md`
- A2A: https://a2a-protocol.org/
- MCP: https://modelcontextprotocol.io/
- MCP Tasks extension: https://tasks.extensions.modelcontextprotocol.io/
- OpenHands asynchronous agents research: https://www.openhands.dev/blog/asynchronous-software-engineering-agents
- mini-SWE-agent: https://github.com/SWE-agent/mini-swe-agent

## Decision history

2026-08-28 — Added as `Experimental` to force interoperability testing before freezing WorkUnit v0.
