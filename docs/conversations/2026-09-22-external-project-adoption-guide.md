# 2026-09-22 — External-project adoption and machine-friendly quick start

## Project-owner request

Clarify how IDKMesh should be used to develop a new, separate application in a collaborative environment. The requested path starts from creating a local directory and GitHub repository, then connecting humans, LLM-backed agents, tools, and verification into a clear development loop. The guidance should identify suitable users and scenarios, define best practices, explain how work should be divided into small chunks, and provide a solid flowchart that both machines and people can follow.

## Repository review

The repository already contained the essential primitives:

- the GitHub-native work/evidence/integration lifecycle in README and ARCHITECTURE;
- ProjectManifest + DomainPack contracts for independent projects;
- WorkUnit v0.2 for bounded tasks, permissions, risk, validators, evidence, budgets, provenance, and failure semantics;
- ResultManifest / VerificationResult separation;
- A2A/MCP interoperability surfaces;
- protected integration and explicit human/governance authority;
- agent/network architecture proposals and execution-substrate abstractions.

The main documentation gap was discoverability: ProjectManifest/DomainPack already described the reusable external-project boundary, but that path was buried in specifications and was not presented as the obvious answer to “how do I use IDKMesh to build my own application?”

## Implemented documentation

Added `docs/PROJECT_ADOPTION_GUIDE.md` with:

- who should use IDKMesh for external software projects;
- the separation between the application repository, IDKMesh coordination contracts, and replaceable participants;
- an end-to-end Mermaid flowchart;
- repository creation and branch-protection steps;
- a recommended `.idkmesh/` project-side layout, clearly labeled as a convention rather than a finished bootstrap command;
- guidance for connecting human contributors, GitHub-native coding agents, local/hosted agents, A2A/MCP integrations, and deterministic tools;
- small WorkUnit design rules;
- vendor-neutral worker/model routing tiers;
- worker, candidate, verifier, integration, and state-machine protocols;
- four adoption scenarios;
- best practices and anti-patterns;
- a machine-friendly bootstrap checklist;
- the automation path that a future `idkmesh init` / Verified Swarm Runner should converge toward;
- explicit current-vs-future capability boundaries.

Also surfaced this guide from:

- `README.md`;
- `docs/GETTING_STARTED.md`;
- `docs/README.md`;
- `docs/WHAT_IS_IDKMESH.md`.

## Key interpretation

The smallest useful mesh is not “many agents.” It is a repeatable authority-separated loop:

```text
bounded work
 -> limited worker
 -> candidate + provenance
 -> independent verification
 -> protected integration
 -> observed outcome
 -> next bounded work
```

Model size, worker confidence, transport success, CI success, or reviewer count do not by themselves grant merge authority.

## Product gap exposed by this work

The contracts are substantially ahead of the external-project UX. A future product milestone should make the documented path executable through a bootstrap workflow roughly equivalent to:

```text
idkmesh init
 -> inspect repository
 -> create project configuration
 -> choose DomainPack
 -> install workflow templates
 -> configure adapters
 -> validate policy/branch assumptions
 -> emit first bounded Work Units
```

That should remain an implementation target until the repository actually provides and validates it; documentation must not present it as a current command.
