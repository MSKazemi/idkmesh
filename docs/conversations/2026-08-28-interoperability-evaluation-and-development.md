# Conversation record — interoperability evaluation and development

**Date:** 2026-08-28  
**Repository:** `https://github.com/MSKazemi/idkmesh`

## Project-owner request

The project owner asked IDKMesh to:

1. check system interoperability;
2. evaluate multiple aspects of the project;
3. proceed with development rather than stopping at analysis.

## Repository inspection

The repository was inspected through the connected GitHub integration.

At the start of the turn, the project already contained more executable work than the earlier roadmap implied:

- WorkUnit and worker ResultManifest schemas;
- a deterministic Phase 0 experiment harness and CI;
- community/governance/ACE mechanisms;
- self-evolution and repository-homeostasis research;
- local worker prototypes;
- multiple active experiment/research branches.

The first major gap identified was semantic interoperability: A2A/MCP had been selected as targets in IDKIP-0001, but no executable field mapping or round-trip compatibility test existed.

## External interoperability research

Current official material was reviewed for:

### A2A

The current released A2A line is 1.0, with Agent Cards, skills/capabilities, Messages/Parts, asynchronous Tasks, Artifacts, and protocol extensions.

Relevant official references:

- https://a2a-protocol.org/latest/specification
- https://a2a-protocol.org/latest/whats-new-v1/
- https://a2a-protocol.org/latest/topics/extension-and-binding-governance/

### MCP

The current MCP protocol revision is 2026-07-28. Relevant changes include the stateless core, formal extension mechanism, routing/version metadata, and the `io.modelcontextprotocol/tasks` extension for asynchronous work.

Relevant official references:

- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://tasks.extensions.modelcontextprotocol.io/

Tasks support remains uneven across SDK implementations, so MCP Tasks should remain optional for the local kernel.

### Existing coding-agent runtimes

OpenHands and mini-SWE-agent were considered as future worker adapters, not core dependencies. The project should integrate existing execution systems rather than embed vendor/model-specific behavior in the coordinator.

## Core interoperability conclusion

The project adopted/reinforced this architecture:

```text
canonical WorkUnit
  -> local/A2A/MCP/agent adapter
  -> worker execution
  -> worker ResultManifest
  -> independent VerificationResult
  -> human/policy integration decision
```

Critical rule:

```text
external execution completed != IDKMesh accepted
```

A2A/MCP solve execution interoperability. IDKMesh remains responsible for security/trust, permissions, verification policy, evidence, provenance, diversity/correlation, and integration decisions.

## Development performed

### WorkUnit v0.2 interoperability branch

A dedicated branch was created:

`interop/work-contract-v0.2`

It adds:

- `interop/bindings.py`;
- `interop/tests/test_bindings.py`;
- `interop/__init__.py`;
- `docs/interoperability/A2A_MCP_MAPPING_V0_2.md`;
- `.github/workflows/interoperability-check.yml`;
- an updated `idkips/0001-interoperability-first-work-contract.md`.

The executable semantic bindings:

- target A2A 1.0 and MCP 2026-07-28;
- carry the complete canonical WorkUnit v0.2 plus a canonical SHA-256 digest;
- use protocol-native fields where semantics align;
- preserve all IDKMesh-specific fields in a namespaced extension payload;
- reject tampering/digest mismatch;
- explicitly prevent external completion from becoming acceptance;
- treat MCP Tasks as optional rather than a local-kernel dependency.

### ResultManifest / VerificationResult correction

During the turn, a parallel PR (#47) landed the independent `VerificationResult v0.1` contract and relationship checks.

This exposed an ambiguity in the original IDKIP-0001 wording. The proposal previously described the worker ResultManifest itself as becoming an Evidence Report.

That was corrected.

Current separation:

1. WorkUnit v0.2 — work/security/verification contract;
2. ResultManifest v0.1 — worker self-report/candidate artifacts;
3. VerificationResult v0.1 — independent verifier evidence/recommendation;
4. final integration — human/governance/policy decision.

A worker must not certify itself.

### Canonical local-node integration

An older PR (#21) had useful Docker isolation but its own private Work Unit/result format.

A newer PR (#34) already existed to port the local worker onto canonical contracts. Rather than create a competing runtime, this turn contributed to #34's branch and aligned it with WorkUnit v0.2.

The v0.2 worker policy now checks or was updated to check:

- required capabilities;
- CPU/memory resources;
- GPU requirement incompatibility;
- risk class;
- public-data restriction for the MVP profile;
- minimum worker trust profile;
- independent verification required;
- zero project-spend and no paid fallback;
- network off/no secrets;
- immutable Git source revision and provenance consistency.

Docker-specific information remains a namespaced node execution binding rather than a second WorkUnit protocol.

The repository is changing concurrently, so the node branch repeatedly advanced during integration. GitHub correctly rejected stale non-fast-forward updates. No branch was force-updated and no parallel commits were overwritten.

A separate controlled Docker acceptance issue (#37) remains an important merge/validation gate for the node backend.

## Project evaluation

A durable audit was added:

`docs/audits/2026-08-28-interoperability-and-system-maturity.md`

Main conclusions:

- community/research/contracts are more mature than the runnable product;
- WorkUnit v0.2 is a strong portable contract;
- independent VerificationResult now exists but real hidden evaluator/check execution is still incomplete;
- semantic A2A/MCP interoperability is now executable, but official SDK conformance is still needed;
- local worker implementation is close to a useful MVP but still requires controlled runtime evidence;
- multi-worker orchestration remains a major product gap;
- `main` is still reported as unprotected, making issue #35 a P0 safety gate;
- ordinary Docker should not be treated as sufficient isolation for arbitrary hostile public workloads;
- community/repository activity is already demonstrating that integration/review capacity is a scarce resource.

## Important empirical observation from project operation

During this turn, both `main` and active branches advanced repeatedly while integration work was being prepared.

This is directly relevant to the project thesis:

> parallel generation is easy to increase; coherent integration is a scarce ordered resource.

IDKMesh should measure branch/PR integration contention, stale-base frequency, reviewer load, and verification backlog rather than simply maximizing parallel agent output.

The ACE community ledger was also observed in `CONSOLIDATE` mode with high review-load pressure, reinforcing the decision to avoid spawning unnecessary new work.

## Current recommended development order

### P0

1. Complete/review canonical local-node PR #34 and satisfy Docker acceptance #37.
2. Finish issue #5's actual verifier execution (hidden tests/checks, unauthorized-change/dependency checks, benchmark tasks).
3. Implement one common coordinator worker-adapter interface with at least two heterogeneous adapters.
4. Connect `WorkUnit -> ResultManifest -> VerificationResult -> human decision` end-to-end.
5. Enable actual GitHub protection/ruleset for `main` (#35) before stronger autonomous write authority.

### P1

6. Merge/review semantic A2A/MCP interoperability work from `interop/work-contract-v0.2`.
7. Validate A2A binding using official A2A 1.0 SDK/generated types.
8. Validate MCP binding against a 2026-07-28 implementation, keeping Tasks optional.
9. Normalize real remote output into ResultManifest and pass it through the same verifier used for local workers.
10. Run the public many-small-vs-one-strong experiment with measured verification/human attention/error correlation.

### Later

Only after the local trust loop works should the project move to 3–10 real nodes and then larger federation/network experiments.

## Community impact

The interoperability design creates bounded contribution surfaces without requiring contributors to understand the entire future architecture:

- A2A SDK conformance;
- MCP conformance;
- local/mini-SWE/OpenHands adapters;
- capability normalization;
- verifier plugins;
- sandbox backends;
- interoperability documentation/examples;
- security/provenance tests.

The current community bottleneck is review/integration capacity, so these tasks should be opened/decomposed only when reviewers can absorb them.
