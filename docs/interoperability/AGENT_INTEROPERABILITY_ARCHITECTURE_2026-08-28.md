# Agent interoperability architecture convergence — 2026-08-28

**Status:** proposed current-main architecture guidance  
**Related:** IDKIP-0001, issues #17 and #127

## Why this document exists

IDKMesh now has many historical branches, but branch existence is not evidence that work should be merged. The repository's branch-convergence policy is explicit: stale or divergent branches must not be bulk-merged merely because they are ahead. Useful unique deltas should be rebuilt or extracted onto current `main` with fresh validation.

This document records the current architecture direction for agent interoperability after reviewing the landed A2A/MCP bindings, provenance model, branch-convergence state, and the wider 2026 agent ecosystem.

## Architecture decision

IDKMesh should not invent another generic agent wire protocol.

The preferred stack is:

```text
IDKMesh WorkUnit / policy / verification contract
        |
        +--> direct adapter (local, mini-SWE-agent, OpenHands, human/GitHub)
        |
        +--> A2A adapter for remote agent discovery, messages, tasks, artifacts
        |
        +--> MCP adapter for tools, resources, context, and long-running tool tasks

candidate output
        -> ResultManifest
        -> independent VerificationResult
        -> separate integration / human / governance decision
```

External protocol completion is execution evidence only. It is never equivalent to IDKMesh acceptance.

## Protocol boundary

### A2A

Treat A2A as the primary horizontal agent-to-agent interoperability layer where a remote autonomous agent exposes discovery metadata, receives work, reports task lifecycle, and returns artifacts.

IDKMesh should:

- preserve the complete canonical WorkUnit in a namespaced extension payload;
- retain explicit A2A version and extension negotiation;
- use Agent Cards for discovery and capability hints;
- normalize returned Artifacts into ResultManifest candidate artifacts;
- keep task completion distinct from independent verification;
- validate real SDK/TCK behavior rather than relying only on hand-shaped dictionaries.

### MCP

Treat MCP primarily as the vertical tool/context interface below or beside an agent. MCP Tasks are useful when a tool invocation itself is long-running, but MCP Task state is not a replacement for the IDKMesh WorkUnit or verification model.

IDKMesh should:

- map tool-capable work to `tools/call` where appropriate;
- use Tasks only for durable asynchronous tool execution;
- keep the canonical WorkUnit and its digest in an IDKMesh extension;
- avoid coupling the coordinator to one MCP SDK implementation;
- preserve a direct/local adapter path even when MCP is available.

## Direct coding-agent adapters

OpenHands and mini-SWE-agent should be treated as adapter targets, not as canonical protocol definitions.

A coordinator-facing adapter should expose the same minimal semantic boundary regardless of harness:

```text
capabilities()
prepare(work_unit)
execute(work_unit)
collect_candidate()
normalize_result_manifest()
cancel()
```

Provider-, harness-, model-, and sandbox-specific details belong in adapter configuration and provenance, not in the WorkUnit core.

## Identity and provenance binding

The current ResultManifest v0.1 already records worker identity, adapter identity, environment, WorkUnit digest, and source revision. That should remain the stable core.

Do **not** add mandatory A2A-specific fields directly to the ResultManifest yet. Until identity/delegation standards stabilize, interoperable identities should travel through a namespaced extension, for example:

```json
{
  "extensions": {
    "org.idkmesh.identity-binding": {
      "protocol": "a2a",
      "subject": "agent-card-or-workload-subject",
      "credential_digest": "sha256:...",
      "verified": true
    }
  }
}
```

The exact extension schema should be versioned before external durable artifacts depend on it.

For A2A, a future implementation should bind a worker result to the exact discovered/signed Agent Card or equivalent identity evidence. For MCP, workload/delegated identity should remain abstract in the IDKMesh core so emerging OAuth/workload-identity mechanisms can be adopted without breaking WorkUnit semantics.

## Artifact and task provenance

The important invariant is not which protocol transported an artifact. The important invariant is that the verifier can prove which exact task specification, worker attempt, external lifecycle, candidate artifact, and execution environment the evidence refers to.

Therefore the durable chain should remain:

```text
canonical WorkUnit digest
  -> external protocol request / task identity
  -> worker identity binding
  -> artifact digests
  -> ResultManifest digest
  -> VerificationResult digest bindings
  -> integration decision
```

Existing `experiments/provenance_integrity.py` already enforces WorkUnit / ResultManifest / VerificationResult digest relationships. Future protocol identity evidence should extend this chain rather than replace it.

## Supply-chain provenance direction

When IDKMesh begins producing durable signed attestations, prefer interoperable provenance envelopes such as in-toto/DSSE-style statements and Sigstore-compatible signing/transparency where they fit, instead of inventing a repository-specific signature format.

This is an implementation priority only after the current canonical digest bindings and identity-extension semantics are exercised end-to-end.

## Sandboxing boundary

Interoperability expands trust boundaries, so sandbox behavior must remain independent from protocol identity.

A remote agent being authenticated does not make its code safe to execute. A signed artifact does not grant filesystem, network, secret, or process authority.

IDKMesh should continue to model sandbox policy through WorkUnit permissions/security and worker/runtime provenance. Implementations may use containers, gVisor-like user-space kernels, microVMs, or another isolation mechanism, but should report the actual confinement controls used and fail closed when a task requires a stronger boundary than the adapter can provide.

The core architectural distinction is:

```text
identity/authentication != authorization != sandbox confinement != verification != integration authority
```

## Branch convergence implications

The repository currently contains historical interop and provenance branches whose useful work has already been rescued or superseded. Do not merge these branches wholesale.

Examples:

- `interop-runtime-integration` — stale combined node + interop branch; useful interop surface was rescued through merged PR #181 and corrected in #183;
- `interop/work-contract-v0.2` — contains older protocol assumptions, including an obsolete A2A patch-version negotiation model; do not merge wholesale;
- `fix/verification-provenance-binding` — its core executable provenance checker already exists on `main`; do not re-merge the stale branch just to preserve ancestry.

Branch reduction should therefore proceed by retirement/deletion of cleanup-safe refs after exact-head revalidation, not by merging them into `main`.

## Immediate implementation priorities

1. **A2A conformance** — validate `SendMessage`, service negotiation, extension payload round-trip, Agent Card discovery, and artifact mapping against the current official SDK/TCK.
2. **Heterogeneous adapter interface** — make one coordinator path run both a direct/local adapter and an A2A- or MCP-backed adapter.
3. **External completion -> ResultManifest** — normalize one bounded remote/mock lifecycle into canonical ResultManifest artifacts and provenance.
4. **Identity-binding extension v0.1** — define a small optional namespaced schema that can carry Agent Card/workload identity evidence without coupling the core schema to one protocol.
5. **End-to-end verification** — bind WorkUnit digest, external task/reference, worker identity evidence, artifact digests, ResultManifest, and independent VerificationResult.
6. **Sandbox evidence normalization** — record actual confinement properties in worker provenance and make capability/security mismatches fail closed.
7. **Signed attestations later** — only after the preceding invariants work, add interoperable signed supply-chain provenance rather than a custom signature format.

## Explicit non-goals

- no bulk merge of historical branches;
- no new generic IDKMesh network protocol;
- no assumption that A2A or MCP completion means correctness;
- no protocol-specific identity fields made mandatory in ResultManifest v0.1;
- no autonomous merge authority granted to workers, verifiers, CI, or protocol peers;
- no weakening of the human/reviewer gate on the active canonical worker PR.

## Repository convergence rule

For every old branch:

```text
if useful_delta_is_already_on_main:
    retire_ref_when_safe
elif useful_unique_delta_exists:
    extract_to_clean_current_main_branch
else:
    preserve_as_evidence_or_retire
```

Never use:

```text
branch_is_ahead -> merge
```

as an integration rule.
