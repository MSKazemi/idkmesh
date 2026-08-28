# Repository Check — Current IDKMesh State

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`
**Snapshot:** `main` at `8614a669043f18246dd9727b81a8b7d42f686bd8` (`Add randomness and bio-inspired coordination strategy`)

## Executive assessment

IDKMesh has crossed from a pure research/documentation repository into an **executable-contract phase**, but the first real worker runtime is still not on `main`.

`main` currently contains:

- canonical Work Unit v0.1, Experiment Manifest v0.1, Experiment Result v0.1, and worker ResultManifest v0.1 schemas;
- a safe deterministic Phase 0 harness and fixtures;
- a passing Phase 0 GitHub Actions workflow;
- an operational ACE Community Growth workflow;
- extensive architecture/research/community documentation;
- new randomness/bio-inspired coordination research.

The most important immediate integration issue is open PR #21 (`Prototype safe local idkmesh-node worker`). The prototype is useful and its own CI passed, but **it should not be merged as-is** because it predates the canonical Phase 0 contracts now on `main`.

## Current repository health

- Visibility: **public**.
- Default branch: `main`.
- Repository description is currently unset in GitHub metadata. For a community-first project this is a discoverability gap.
- Current `main` tree contains `experiments/`, `schemas/`, examples, research/docs, and GitHub workflows.
- Current `main` does **not** contain the `node/` implementation from PR #21.

## Automation status

### Phase 0

The Phase 0 schema/harness workflow has a confirmed successful run. It validates the machine-readable contracts and runs only the built-in deterministic smoke path; it does not execute arbitrary manifest commands.

### ACE Community Growth

The ACE workflow was repaired after earlier invalid-YAML/zero-job failures. Subsequent runs succeeded, including the latest observed run for the current research push.

ACE now has a living growth ledger (#23), plus bounded growth-seed issues such as #24 and #25. This is promising, but ACE should be evaluated on **verified useful descendants per scarce human attention**, not raw issue/event generation.

## Open PR #21 — useful prototype, current integration blocker

PR #21 is open and GitHub reports it as mergeable. Its `IDKMesh Node CI` passed on its branch. It adds:

- a local Docker-isolated `idkmesh-node` prototype;
- immutable Git SHA input;
- network-off execution;
- read-only container root;
- capability dropping / `no-new-privileges`;
- CPU, memory, PID, and wall-time limits;
- logs, patch capture, and untrusted-candidate status;
- a manual read-only Gemini advisory workflow.

However the branch is currently **28 commits behind `main` and 2 commits ahead**.

### Critical contract mismatch

PR #21 defines its own object called Work Unit v0.1 with roughly:

```text
version
id
source { repo_url, revision }
execution { image, command, network, limits }
output { patch/log limits }
```

The canonical `schemas/work-unit-v0.1.schema.json` on `main` instead requires the shared IDKMesh contract including:

```text
schema_version
id
version
kind
objective
inputs
outputs
dependencies
constraints
uncertainty
permissions
validators
evidence_requirements
budget
provenance
failure_semantics
```

These are not interchangeable. Merging PR #21 unchanged would create **two incompatible definitions both called Work Unit v0.1**.

### Result mismatch

The node prototype also writes a custom `result.json`. `main` now has the canonical worker `ResultManifest v0.1`, deliberately designed so worker self-report is separate from independent acceptance/verification.

The node should emit a schema-valid `ResultManifest v0.1` (or a clearly versioned adapter-specific envelope that maps losslessly to it) rather than creating a second worker-result protocol.

## Recommended merge gate for PR #21

Before merging:

1. rebase/update the branch against current `main`;
2. replace the private node Work Unit parser contract with the canonical Work Unit v0.1 schema or define an explicit execution-binding profile referenced from the canonical Work Unit;
3. emit canonical worker ResultManifest v0.1;
4. add positive and negative schema integration tests;
5. preserve the Docker safety defaults;
6. run the node CI plus Phase 0 contract validation together;
7. perform one real Docker acceptance run against an immutable IDKMesh commit on a machine with Docker available;
8. inspect that the worker result remains an unverified candidate and requires an independent verifier.

Only after those checks should the node prototype move to `main`.

## Current issue priorities

The highest-value near-term chain remains:

```text
#3 canonical WorkUnit / ResultManifest
    -> #4 local multi-worker orchestrator
    -> #5 independent validator / benchmark
    -> #16 local Verified Swarm Runner v0.1
```

PR #21 can supply much of the execution/sandbox substrate for this chain once its contract mismatch is resolved.

Other valuable tracks should remain parallel rather than block the executable core:

- #17 A2A/MCP semantic mapping;
- #20 IDKGraph repository observatory;
- #13–#15 scaling/verification/Work Unit research;
- #9–#10 and #23–#25 community-growth experiments.

## Research-documentation balance

The latest `RANDOMNESS_AND_BIOINSPIRED_ALGORITHMS.md` is a useful experiment catalog. The next value should come from implementing one or two measurable mechanisms (for example Thompson/UCB worker allocation, power-of-two choices, or diversity-aware verifier selection) inside simulations or the local runner rather than adding more untested algorithm catalogs.

Project discipline should remain:

> **New mechanisms graduate through executable artifacts, simulations, benchmarks, or falsifiable experiments.**

## Community/discoverability gap

The repository is public but GitHub metadata currently has no description. Once the executable runner path is coherent, improve the GitHub front door with:

- concise repository description;
- accurate topics;
- social preview;
- a runnable quick-start near the top of README;
- real starter issues tied to code/tests rather than only research documents.

## Recommended immediate next action

Do **not** start another large architecture layer.

Bring PR #21 onto current contracts and turn it into the first canonical execution backend. Then connect it to an independent verifier and run one real bounded repository task end-to-end:

```text
canonical Work Unit
 -> isolated local worker
 -> canonical ResultManifest
 -> independent verification
 -> Evidence Report
 -> human decision
```

That is the shortest path from the current repository to a useful IDKMesh v0.1 kernel.
