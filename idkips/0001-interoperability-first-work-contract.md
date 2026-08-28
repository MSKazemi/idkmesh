# IDKIP-0001: Interoperability-first Work Contract

- **Status:** Experimental
- **Authors:** IDKMesh bootstrap project
- **Created:** 2026-08-28
- **Discussion:** GitHub issue #17
- **Implementation:** WorkUnit v0.2, `interop/`, node adapter work, issues #4/#16/#17

## Summary

IDKMesh should keep **WorkUnit v0.2** as its scheduling, authority, verification-policy, evidence-requirement, and provenance contract while mapping it onto existing agent/task protocols instead of inventing another generic remote-agent transport.

Initial interoperability targets:

- Agent2Agent (A2A) 1.0 for remote autonomous agents;
- Model Context Protocol (MCP) 2026-07-28 for tools/context and optional Tasks-style asynchronous work;
- direct adapters for local workers and coding agents such as `idkmesh-node`, mini-SWE-agent, and OpenHands.

The defining trust rule is:

> **External execution completion is not IDKMesh acceptance.**

## Problem

A2A and MCP solve important interoperability problems, but neither defines all semantics required by verification-first collective engineering.

WorkUnit v0.2 explicitly contains IDKMesh-specific requirements including:

- vendor-neutral worker capabilities/resources;
- allowed files/actions/network/secrets;
- risk class, data classification, minimum worker trust, and sandbox requirement;
- dependency graph;
- explicit uncertainty;
- independent verification policy;
- required validators and evidence;
- budgets;
- provenance;
- failure semantics.

Recreating agent discovery, asynchronous task lifecycle, artifact transport, or generic tool calling inside IDKMesh would spend community effort on commodity infrastructure and reduce interoperability.

## Proposal

### 1. Canonical semantic contract

WorkUnit v0.2 remains transport-neutral and model/provider-neutral.

```text
WorkUnit v0.2
    -> adapter/binding
    -> worker execution
    -> worker ResultManifest v0.1
    -> independent verifier evidence
    -> human/policy integration decision
```

Provider/protocol-specific data belongs in namespaced extensions or adapter provenance.

### 2. Lossless external bindings

Bindings SHOULD use native external protocol fields where semantics match, but MUST preserve the complete canonical WorkUnit plus a canonical digest whenever external concepts do not cover the full IDKMesh contract.

A mapping must not silently discard:

- `security`;
- `permissions`;
- `verification_policy`;
- `validators`;
- `evidence_requirements`;
- budgets or provenance;
- dependency/failure semantics.

A digest mismatch is a binding error.

### 3. A2A mapping

A2A 1.0 is the preferred first remote-agent binding candidate.

Conceptual mapping:

```text
worker discovery/capability
    <-> Agent Card / skills / capabilities

WorkUnit invocation
    -> Message / Task with IDKMesh extension data

long-running execution
    <-> Task lifecycle

candidate output
    <-> Artifact / Parts

IDKMesh security + verification semantics
    -> IDKMesh extension payload
```

The binding should use a declared extension rather than modifying A2A core semantics.

### 4. MCP mapping

MCP remains especially useful for tool and context integration.

```text
IDKMesh operation
    -> tools/call

optional long-running execution
    -> io.modelcontextprotocol/tasks

final worker output
    <- tool/task result
```

MCP Tasks is an optional extension, not a dependency of the local IDKMesh kernel.

### 5. Direct adapters remain first-class

The first Verified Swarm Runner remains local-first and must work without network protocols.

Candidate adapters:

- `idkmesh-node`;
- local subprocess/test fixture;
- mini-SWE-agent;
- OpenHands;
- human/GitHub task;
- A2A remote agent;
- MCP-backed tool/task.

### 6. Worker ResultManifest remains a self-report

An earlier version of this proposal described ResultManifest as becoming an “Evidence Report.” Implementation evidence showed that wording was unsafe/ambiguous.

**Current decision:**

- `result-manifest-v0.1.schema.json` is the worker self-report boundary;
- it may contain candidate artifacts, logs, resource use, worker claims/confidence, provenance, and a request for validation;
- it must not contain an authoritative `accepted` verdict;
- independent verifier evidence is a separate object/stage;
- integration/merge is a later human/policy decision.

This separation prevents a generator from certifying its own artifact.

## Alternatives considered

### Invent a complete IDKMesh agent wire protocol now

Not selected. It duplicates rapidly standardizing ecosystem primitives and increases maintenance burden. A custom transport remains possible later if measured requirements cannot be satisfied by adapters/extensions.

### Use A2A Task directly as WorkUnit

Insufficient. A2A intentionally does not define IDKMesh-specific scheduling, risk, verification, evidence, and integration policy.

### Use MCP Task directly as WorkUnit

Insufficient. MCP Tasks provide asynchronous lifecycle around operations; they are not a complete collective-engineering trust contract.

### Delay interoperability entirely

Rejected. The contract is already executable; testing mappings now is cheaper than discovering coupling after multiple worker implementations exist.

## Security / abuse considerations

Interoperability adds trust boundaries. IDKMesh must distinguish:

- discovery claims from verified capability;
- authentication from authorization;
- worker self-report from independent evidence;
- task completion from correctness;
- artifact transport from artifact trust;
- protocol metadata from project policy.

Remote agents must never receive authority beyond the WorkUnit permissions/risk policy merely because the remote protocol authenticated them.

## Community Impact

Expected benefits:

- contributors can add adapters without editing coordinator core;
- existing agent ecosystems can participate;
- standards specialists have bounded contribution surfaces;
- less project energy is spent on transport machinery;
- WorkUnit semantics become easier to test against heterogeneous implementations.

Costs:

- compatibility tests become permanent maintenance work;
- external standards must be tracked;
- documentation must clearly explain external completion versus IDKMesh acceptance.

## Measurable success criteria

Before moving this IDKIP to `Accepted`:

1. A field-by-field WorkUnit v0.2 mapping exists for A2A and MCP.
2. A2A and MCP semantic round trips preserve the complete WorkUnit and reject tampering.
3. External task completion cannot create an IDKMesh acceptance verdict.
4. At least two heterogeneous worker adapters execute through one coordinator interface.
5. Remote outputs normalize to canonical worker ResultManifest v0.1.
6. Coordinator/verifier core contains no mandatory vendor/model branching for those adapters.
7. A contributor unfamiliar with coordinator internals can implement a small adapter from public docs/tests.

## Evidence so far

WorkUnit v0.2 completed issue #3 and now explicitly represents capabilities/resources, security/trust, independent verification policy, validators, and evidence requirements.

Issue #17 / `docs/interoperability/A2A_MCP_MAPPING_V0_2.md` add:

- explicit field mapping;
- A2A 1.0 semantic binding fixture;
- MCP 2026-07-28 semantic binding fixture;
- lossless digest-protected round trips;
- tamper tests;
- completion-vs-acceptance tests.

This is sufficient to keep the proposal `Experimental`, not to accept it permanently.

## Remaining experiments

### E-0001-A — official SDK conformance

Represent the same fixture using official/generated A2A 1.0 types and an MCP implementation matching the 2026-07-28 extension model.

### E-0001-B — heterogeneous adapters

Run one bounded WorkUnit through at least two worker adapters behind the same coordinator interface.

### E-0001-C — canonical result normalization

Normalize local and remote worker output into worker ResultManifest v0.1, then send it to an independent verifier.

### E-0001-D — contributor adapter test

Ask an external contributor to implement a trivial adapter using only public docs/interfaces/tests. Record friction.

## Dissent / unresolved questions

- Should A2A/MCP bindings live in core or a separate plugin package?
- Should human workers use the same adapter interface or a GitHub-native binding into the same evidence model?
- How should capability claims from Agent Cards/MCP discovery be attested for higher-risk WorkUnits?
- Which WorkUnit fields should eventually gain standardized A2A extensions rather than an opaque namespaced payload?
- When SDK support for MCP Tasks is uneven, what minimum synchronous contract should every MCP adapter support?

## Migration / rollback

WorkUnit v0.1 remains available for historical reproducibility. Current bindings target v0.2 and are versioned independently.

If A2A/MCP integration proves burdensome, direct adapters remain valid; external bindings can be removed without changing IDKMesh verification semantics.

## Implementation links

- Issue #17 — interoperability experiment
- Issue #16 — Verified Swarm Runner
- `schemas/work-unit-v0.2.schema.json`
- `schemas/result-manifest-v0.1.schema.json`
- `docs/interoperability/A2A_MCP_MAPPING_V0_2.md`
- A2A: https://a2a-protocol.org/
- MCP: https://modelcontextprotocol.io/
- MCP Tasks extension: https://tasks.extensions.modelcontextprotocol.io/

## Decision history

- **2026-08-28:** Added as `Experimental` to force interoperability testing before contract freeze.
- **2026-08-28:** Updated after WorkUnit v0.2 landed. Corrected ResultManifest semantics so worker self-report and independent verifier evidence remain separate.
