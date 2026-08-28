# Conversation Record — Complete Next Steps and Project Evolution

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## Project-owner request

The project owner asked:

> complete the next steps find the ideas and how we want to evolve this project? https://github.com/MSKazemi/idkmesh

Standing project rules also require substantive IDKMesh conversations to be preserved in the public repository and all changes to be considered through a community-first lens.

---

## Repository state reviewed

The repository already contained a substantial research roadmap, goal hierarchy, community foundation, mathematical/scientific research, distributed-compute ideas, and open implementation/research issues.

Key existing work included:

- `GOALS.md` — North Star and primary goals;
- `ROADMAP.md` — progressive `1 -> 10 -> 100 -> 10,000 -> 1,000,000` research path;
- issues #2–#6 — first coding experiment, schemas, orchestrator, verifier, and Core/DomainPack interfaces;
- issue #7 — IDKIP proposal process;
- issues #9–#10 — community growth and repository-driven community engine;
- issues #11–#12 — safe local volunteer node and GitHub-hosted agent pilots;
- issues #13–#15 — research tracks on collective-intelligence scaling, verification scaling, and Work Unit formalization.

The main gap was not a shortage of long-range ideas. It was a need to make the **near-term product wedge and evolutionary sequence explicit**.

---

## External ecosystem research

Current official/project sources were reviewed for relevant 2026 developments.

### OpenHands / CAID

OpenHands described asynchronous multi-agent software-engineering work using Git worktrees, branches, merges, and test-based verification. The important lesson for IDKMesh is that integration is a major bottleneck and additional agents help only while there is genuinely parallelizable work.

OpenHands also described a software-agent stack as harness + orchestrator + control plane.

Implication adopted:

IDKMesh should not primarily compete as another coding-agent harness. It should focus on coordination, evidence, verification, heterogeneous adapter interoperability, evolving goals, and scientifically measurable collective behavior.

Sources:

- https://www.openhands.dev/blog/asynchronous-software-engineering-agents
- https://www.openhands.dev/blog/agent-control-plane

### mini-SWE-agent

mini-SWE-agent intentionally keeps its agent architecture very small while supporting multiple models/environments.

Implication adopted:

It is a strong first real coding-agent adapter target because its integration surface is understandable and it reduces the chance that IDKMesh experiments are dominated by opaque harness complexity.

Source:

- https://github.com/SWE-agent/mini-swe-agent

### Agent2Agent (A2A)

A2A is now a Linux Foundation-hosted open interoperability protocol. It defines Agent Cards, skills, stateful Tasks, Messages, Artifacts, and extension mechanisms. The Linux Foundation reported broad organizational/cloud adoption in 2026.

Implication adopted:

Do not invent a generic remote-agent discovery/task protocol as P0. Test an IDKMesh-specific Work Contract as an extension/envelope mapped onto A2A Task/Artifact semantics.

Sources:

- https://a2a-protocol.org/
- https://a2a-protocol.org/latest/topics/key-concepts/
- https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year

### Model Context Protocol (MCP)

The 2026-07-28 MCP release introduced a stateless core and formal extension framework. MCP Tasks are now a durable asynchronous task mechanism for long-running tool calls.

Implication adopted:

Use MCP where IDKMesh workers/coordinators need tool/context integration or long-running tool work. Do not duplicate MCP's transport, but do not confuse an MCP Task with an IDKMesh verification/evidence contract.

Sources:

- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://tasks.extensions.modelcontextprotocol.io/

### Supply-chain/security standards

Sigstore/Rekor, in-toto, OpenSSF Scorecard, and the OSPS Baseline were reviewed.

Implication adopted:

IDKMesh should model work -> artifact -> verification -> acceptance as an evidence/provenance chain and reuse existing attestation/transparency patterns where practical.

Sources:

- https://docs.sigstore.dev/logging/overview/
- https://in-toto.io/docs/getting-started/
- https://openssf.org/scorecard/
- https://baseline.openssf.org/

### Sandboxing/reproducibility

Candidate technologies reviewed included gVisor, Firecracker, WASI, and Nix/reproducible builds.

Implication adopted:

Use a risk-tiered execution-backend interface instead of hard-coding one runtime into the protocol.

Sources:

- https://gvisor.dev/
- https://firecracker-microvm.github.io/
- https://wasi.dev/
- https://reproducible.nixos.org/

---

## Main evolution decision

The strongest concise identity found during this work is:

> **IDKMesh is a verification-first coordination fabric for humans, AI agents, and heterogeneous compute working on uncertain goals.**

This is more distinctive and actionable than describing IDKMesh only as "many AI agents coding together."

The project should integrate existing commodity/open standards and spend its complexity budget on:

- Goal/Evidence Graphs;
- bounded Work Contracts;
- task decomposition and scheduling;
- diversity/error-correlation-aware orchestration;
- independent verification;
- evidence/provenance;
- integration policy;
- human-attention allocation;
- community-scale coordination and governance;
- scientifically reproducible experiments.

---

## First reference product decision

A new decision record establishes a **Git-native Verified Swarm Runner** as the first reference product.

Initial conceptual user flow:

```text
bounded Git issue/task
 -> IDKMesh Work Contract
 -> multiple isolated worker attempts
 -> independent verifier
 -> Evidence Report
 -> human accept / reject / refine
```

Important constraints:

- local one-machine operation first;
- no decentralized networking required for v0.1;
- no autonomous merge into canonical `main`;
- replaceable worker adapters;
- worker self-reported success remains separate from independent verification;
- saved manifests make runs reproducible.

This does not abandon the long-term million-node vision. It creates an evidence-producing path toward it.

---

## Interoperability decision / IDKIP

The previously open IDKIP-process task was implemented on the evolution branch:

- `IDKIPS.md`;
- `idkips/0000-template.md`;
- `idkips/0001-interoperability-first-work-contract.md`.

IDKIP-0001 is currently **Experimental**.

Its key proposal is:

- A2A/MCP should handle generic interoperability/lifecycle where useful;
- the IDKMesh Work Contract remains the semantic envelope for risk, resources, dependencies, verification, evidence, provenance, replication/diversity, and integration requirements;
- direct local adapters remain first-class for v0.1;
- external task completion never implies IDKMesh acceptance.

---

## Existing backlog alignment

Instead of creating competing duplicate roadmaps, comments were added to existing issues:

- **#3** — test A2A/MCP semantic mapping before WorkUnit schema freeze;
- **#4** — treat the orchestrator as the v0.1 Verified Swarm Runner;
- **#5** — verifier output should become a richer independent Evidence Report;
- **#6** — keep Core narrow and put domain/provider-specific behavior into DomainPacks/adapters;
- **#11** — make the local volunteer node reuse the same Work Contract/evidence/execution interfaces rather than creating a separate stack;
- **#15** — add A2A/MCP semantic round-trip research to formal Work Unit research.

Two new executable issues were added:

- **#16 — v0.1: Ship the local Git-native Verified Swarm Runner**;
- **#17 — IDKIP-0001 experiment: map Work Contract semantics to A2A and MCP**.

---

## New durable repository artifacts

Added on the evolution branch:

- `EVOLUTION.md` — community-readable evolution path and v0.1 definition;
- `IDKIPS.md` — improvement-proposal governance;
- `idkips/0000-template.md`;
- `idkips/0001-interoperability-first-work-contract.md`;
- `docs/findings/2026-08-28-agent-ecosystem-and-idkmesh-evolution.md`;
- `docs/decisions/ADR-0004-verified-swarm-runner-first-product.md`;
- this conversation record.

The README was updated to surface the first product, evolution strategy, IDKIP process, and the principle **Integrate before reinventing**.

---

## Proposed evolution sequence

```text
community + IDKIP process
 -> interoperability mapping
 -> Work/Result contracts
 -> local Verified Swarm Runner
 -> two heterogeneous agent adapters
 -> independent benchmark/verifier
 -> flagship public experiment
 -> GitHub issue/PR bridge
 -> provenance + stronger sandboxing
 -> 3–10 machine mesh
 -> 10–20 laptop self-improvement study
 -> federation / economics / very-large-scale research
```

The project should not move to the next complexity layer only because it is exciting. Each stage should create evidence that justifies the next one.

---

## New research ideas identified

The evolution work highlighted several experiments worth prioritizing:

1. **Diversity budget:** spend fixed compute on more identical attempts, heterogeneous attempts, specialized roles, or stronger verification?
2. **Adaptive fan-out:** allocate more agents only when uncertainty/risk justifies the verification cost.
3. **Verification market/capacity:** route high-risk changes to stronger verification and apply backpressure when generation outruns validators.
4. **Error-correlation routing:** select workers that add independent evidence rather than redundant correlated failures.
5. **Goal ambiguity as branching search:** preserve competing interpretations and let evidence prune/promote branches.
6. **Human-attention scheduler:** treat reviewer time as a scarce system resource and escalate by risk/information gain.
7. **Community as distributed-system layer:** measure onboarding, retention, review topology, and leadership bottlenecks alongside compute scaling.
8. **Reputation by verified durability:** separate implementation, review, security, reproduction, research, and community reputation dimensions.
9. **Competitive verifier ensembles:** study useful verifier diversity and disagreement.
10. **Bounded self-improvement:** eventually allow policy improvement proposals only behind external benchmarks, rollback, evidence, and constitutional human approval.

---

## Community impact

This evolution deliberately narrows the immediate product without narrowing contribution opportunities.

The v0.1 runner can be decomposed into independently useful contributions around:

- adapter implementations;
- CLI/developer experience;
- schemas;
- benchmark tasks;
- verifier plugins;
- sandbox backends;
- experiment analysis;
- docs/tutorials;
- GitHub integration;
- provenance;
- community usability testing.

The key community principle is:

> A contributor should be able to improve one adapter, verifier, benchmark, explanation, or experiment without understanding every future distributed-systems layer.

---

## Standing recommendation after this conversation

The next engineering objective is **not** "build the million-node mesh." It is:

> **Make one bounded Git task run through multiple heterogeneous, isolated workers and independent verification, producing a reproducible Evidence Report that a human can trust enough to review.**

If that loop becomes valuable and extensible, IDKMesh has earned the right to distribute it across more machines.
