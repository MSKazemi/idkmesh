# WorkUnit v0.2 interoperability mapping — A2A and MCP

**Status:** Experimental  
**Proposal:** IDKIP-0001  
**Tracking:** issue #17

## Decision

IDKMesh should **bind to** A2A and MCP rather than recreate their generic interoperability layers.

The canonical IDKMesh object remains **WorkUnit v0.2**. External protocols execute or transport work; they do not decide whether the result is correct or acceptable.

```text
WorkUnit v0.2
      |
      +-- local execution binding
      +-- A2A binding
      +-- MCP binding
      +-- future agent adapters
                |
                v
       worker ResultManifest v0.1
                |
                v
       independent verification
                |
                v
          evidence / decision
```

## Protocol roles

### A2A 1.0

Use primarily for remote autonomous-agent interoperability:

- Agent Card discovery;
- skills/capabilities;
- Messages and Parts;
- asynchronous Task lifecycle;
- Artifacts;
- task/context references;
- extensions.

### MCP 2026-07-28

Use primarily for tool/context integration and optional long-running operations:

- tool discovery and `tools/call`;
- request-local capability advertisement;
- formal protocol extensions;
- `io.modelcontextprotocol/tasks` when asynchronous task handles are useful and supported.

MCP Tasks is not required for the local IDKMesh kernel.

## Semantic mapping matrix

| IDKMesh WorkUnit v0.2 concept | A2A 1.0 | MCP 2026-07-28 | IDKMesh decision |
| --- | --- | --- | --- |
| `id` | message/task metadata | request/tool metadata | native hint + canonical payload |
| `objective` | user Message text Part | tool arguments | native |
| `inputs` | structured/data Parts, references | arguments/resources | partial |
| `outputs` | Artifact expectations | tool result expectations | partial |
| `requirements.capabilities` | Agent Card skills/capabilities | server/tool capabilities | scheduler maps discovery evidence |
| `requirements.resources` | extension | extension/tool args | IDKMesh-authoritative |
| `dependencies` | task/context references + extension | handles/arguments + extension | partial |
| `constraints` | extension | extension/tool args | IDKMesh-authoritative |
| `uncertainty` | extension | extension | IDKMesh-authoritative |
| `security` | auth + extension | auth + extension | IDKMesh-authoritative policy |
| `permissions` | auth + extension | auth/tool policy + extension | IDKMesh-authoritative policy |
| `verification_policy` | extension | extension | **IDKMesh-only acceptance semantic** |
| `validators` | separate agent/task + extension | separate tool/task + extension | **IDKMesh-only acceptance semantic** |
| `evidence_requirements` | artifact conventions + extension | task/tool result + extension | IDKMesh-authoritative |
| `budget` | extension | extension | IDKMesh-authoritative |
| `provenance` | metadata/artifacts + extension | metadata/result + extension | partial; canonical record remains IDKMesh |
| `failure_semantics` | Task states + coordinator policy | task/tool states + coordinator policy | partial |
| integration/merge decision | not defined | not defined | **outside worker protocol** |

## Lossless binding rule

A protocol binding may expose selected fields using native protocol concepts, but it must also carry:

1. the complete canonical WorkUnit v0.2 document;
2. its canonical SHA-256 digest;
3. a namespaced IDKMesh extension identifier.

This prevents a mapping from silently dropping security, verification, budget, or provenance requirements merely because the external protocol has no direct equivalent.

Executable reference code lives in `interop/bindings.py`.

## A2A binding

The current semantic fixture uses:

- A2A version `1.0.0`;
- role `ROLE_USER`;
- a text Part containing the human-readable objective;
- a data Part containing the complete WorkUnit + digest;
- extension URI `https://idkmesh.org/extensions/work-contract/v0.2`;
- output mode hints for structured data, text, and patches.

The next conformance step is to implement the same mapping using official A2A 1.0 SDK/generated types and confirm Agent Card extension negotiation.

## MCP binding

The current semantic fixture targets protocol revision `2026-07-28` and models a `tools/call` operation that:

- carries the complete WorkUnit + digest as tool arguments;
- advertises the IDKMesh Work Contract extension;
- advertises `io.modelcontextprotocol/tasks` as an optional asynchronous extension;
- uses current protocol/version/method/name routing metadata.

The next conformance step is to test against an SDK implementing the 2026-07-28 extension model. Tasks support is still uneven across SDKs, so IDKMesh must preserve a synchronous/direct-adapter path.

## Critical trust invariant

```text
A2A Task completed
or
MCP task/tool completed

!=

IDKMesh accepted
```

The binding code normalizes a successful external completion to:

```text
execution_status = succeeded
acceptance_status = pending_independent_verification
```

A worker cannot transform its own completion event into an integration verdict.

## Worker result vs independent evidence

WorkUnit v0.2 dispatch produces a worker **ResultManifest v0.1**. That object remains a worker self-report containing candidate artifacts, logs, resource use, provenance, confidence/claims, and a verification request.

Independent verifier evidence must be stored separately. Do **not** overload the worker ResultManifest with an `accepted` bit or make the producer its own verifier.

This corrects an early wording in IDKIP-0001 that described ResultManifest itself as the Evidence Report.

## Capability discovery

Future scheduler adapters should normalize external discovery into a common internal capability view:

```text
A2A Agent Card skills/capabilities
MCP server/tool discovery
local worker profile
human contributor profile
        |
        v
requirements.capabilities/resources/trust match
```

Discovery claims are not automatically trusted capability evidence. Where risk requires it, IDKMesh should require historical evidence, attestation, tests, or human approval.

## Compatibility policy

Bindings are versioned independently from the WorkUnit schema.

- historical WorkUnit v0.1 remains reproducible;
- the current binding targets v0.2;
- future breaking WorkUnit revisions receive new binding fixtures/tests;
- protocol changes should normally affect adapter code, not the core WorkUnit semantics.

## Current evidence delivered by issue #17

Implemented now:

- field-level mapping;
- explicit IDKMesh-only semantics;
- executable A2A/MCP semantic envelopes;
- lossless round-trip tests;
- tamper/digest tests;
- test proving protocol completion cannot become acceptance.

Still required before IDKIP-0001 can move from `Experimental` toward `Accepted`:

1. official A2A SDK conformance test;
2. MCP 2026-07-28 SDK conformance test;
3. at least two heterogeneous worker adapters behind one coordinator interface;
4. conversion of remote protocol outputs into canonical worker ResultManifest v0.1;
5. contributor test showing a new adapter can be added without editing coordinator internals.
