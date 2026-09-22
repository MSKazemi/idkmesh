# External Project Adoption Guide — 2026-09-22

## Project-owner request

Clarify how IDKMesh should be used to develop a separate application in a collaborative environment. The requested path starts from creating a directory and GitHub repository, then connects LLMs, agents, humans, and tools; decomposes work into small chunks; routes work to appropriate participants; verifies results; and explains best practices in a machine- and agent-friendly way.

## Repository interpretation

The repository already contained the core pieces needed for this explanation:

- Git/GitHub as the canonical collaboration substrate;
- WorkUnit v0.2 as the bounded-task contract;
- ResultManifest, EvaluatorPlan, and VerificationResult separation;
- ProjectManifest + DomainPack interfaces for independent projects;
- protocol-neutral worker adapters and A2A/MCP mappings;
- protected integration authority separate from workers and verifiers.

The missing element was a clear external-project onboarding path that connected these pieces from an empty project through day-to-day development.

## Changes made

Added `docs/PROJECT_ADOPTION_GUIDE.md` with:

- an end-to-end flowchart;
- repository/bootstrap steps;
- ProjectManifest/DomainPack placement in the workflow;
- human, GitHub-native agent, local/hosted agent, A2A/MCP, and deterministic-tool roles;
- WorkUnit sizing and decomposition rules;
- vendor-neutral model/agent routing tiers;
- worker, verifier, and integration protocols;
- a machine-friendly state machine;
- four concrete usage scenarios;
- best practices and anti-patterns;
- a bootstrap readiness checklist;
- a distinction between what works today and the future one-command runner/bootstrap.

Updated the repository front doors so the guide is discoverable from:

- `README.md`;
- `docs/GETTING_STARTED.md`;
- `docs/README.md`;
- `docs/WHAT_IS_IDKMESH.md`.

## Key design conclusion

The clearest adoption model is:

```text
GitHub project state
  -> bounded Work Unit
  -> capability/risk routing
  -> human or agent candidate
  -> exact-revision evidence
  -> independent verification
  -> protected integration decision
  -> observed outcome
  -> next Work Unit
```

Provider/model selection comes after project policy, capability requirements, and risk classification. Larger models do not gain additional authority.

## Current capability boundary

The guide intentionally does not claim a finished external-project bootstrap or universal live model dispatcher. ProjectManifest/DomainPack validation and adapter infrastructure exist, but a polished `idkmesh init` + multi-provider Verified Swarm Runner remains future product work.

## Community impact

The change reduces the amount of architecture knowledge required for a new maintainer or contributor to answer “how do I use IDKMesh on my own project?” and gives humans and agents a shared operational vocabulary without requiring private project context.
