# IDKMesh Repository Audit — 2026-08-28

## Scope

This audit checks the current public `MSKazemi/idkmesh` repository after the project-definition, community, scalability, evolution, IDKGraph, and Phase-0 schema work.

The goal is to answer a simple question:

> Is the repository coherent, contributor-ready, and moving from research/design into an executable system?

## Executive summary

IDKMesh has progressed quickly from an ambiguous idea into a well-structured **research + architecture + community program** with a concrete first product direction.

The repository now has strong coverage of:

- vision and goals;
- mathematical and scientific foundations;
- scalability and agility;
- community/governance;
- research questions and falsifiable experiments;
- architectural decisions;
- an IDKIP improvement-proposal process;
- a concrete first reference product: the **Git-native Verified Swarm Runner**;
- IDKGraph for task/evidence/provenance/evolution modeling;
- an initial machine-readable **Work Unit v0.1** schema;
- an initial **Experiment Manifest v0.1** schema;
- a substantial issue backlog connecting research to engineering.

The most important finding is that the project has reached a transition point:

> **The design layer is strong enough. The next bottleneck is executable evidence.**

The repository should now prioritize the smallest runnable, reproducible kernel over adding more broad architecture documents.

## What is strong

### 1. The project is much clearer

The README now clearly explains:

- the community-first philosophy;
- the first reference domain (distributed software engineering);
- bounded Work Units;
- independent verification;
- the Verified Swarm Runner;
- the Fractal Autonomous Cells scalability hypothesis;
- the distinction between long-term ambition and near-term implementation.

This is a major improvement over a repository that only describes a planetary-scale idea.

### 2. The near-term product is concrete

`EVOLUTION.md` defines the first product as:

`bounded Git task -> Work Contract -> isolated heterogeneous worker attempts -> independent verification -> Evidence Report -> human decision`

This is a good wedge because it can be useful on one machine before any distributed-network layer exists.

### 3. Architecture is separated from commodity infrastructure

The repository correctly proposes to build the distinctive IDKMesh layer — coordination, verification, evidence, task/goal graphs, diversity, research metrics — while integrating existing systems for transports, agents, Git, sandboxing, provenance, and eventual P2P networking.

The principle **Integrate before reinventing** should remain an architectural invariant.

### 4. IDKGraph is a useful unifying model

`docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md` is a strong conceptual step. It avoids forcing every relationship into one DAG and instead proposes a typed temporal multiplex directed hypergraph with derived projections for:

- executable DAG/AND-OR work;
- workflow/Petri-net state;
- provenance;
- documentation/concept consistency;
- contributor/task matching;
- optional e-graph use where equality saturation is genuinely appropriate.

This is more appropriate for IDKMesh than a simple global task list.

### 5. Community infrastructure is unusually early — in a good way

The repository already has:

- `CONTRIBUTING.md`;
- `COMMUNITY.md`;
- `GOVERNANCE.md`;
- `CODE_OF_CONDUCT.md`;
- `SECURITY.md`;
- `SUPPORT.md`;
- `MAINTAINERS.md`;
- CODEOWNERS;
- issue templates;
- a pull-request template;
- community milestones and metrics.

This supports the project's thesis that community scalability is part of the system rather than later marketing.

### 6. The backlog is connected to research questions

The current issues form a credible chain:

- #13 collective-intelligence scaling law;
- #14 verification scaling;
- #15 formal Work Unit research;
- #16 Verified Swarm Runner v0.1;
- #17 A2A/MCP interoperability experiment;
- #19 Phase-0 executable schemas + harness;
- plus worker, validator, community, orchestrator, benchmark, and project/domain interface issues.

This is much better than disconnected generic TODOs.

## Current executable state

### Present

- `schemas/work-unit-v0.1.schema.json`
- `schemas/experiment-manifest-v0.1.schema.json`

The Work Unit schema already includes important concepts:

- bounded objective;
- typed inputs/outputs;
- dependencies;
- allowed/forbidden paths;
- explicit uncertainty;
- permissions;
- validators;
- evidence requirements;
- resource/human/token budget;
- provenance;
- failure semantics;
- namespaced extensions.

This is a solid v0.1 research schema.

### Missing or not yet visible in the current repository tree

- Experiment Result / Result Manifest schema;
- valid/invalid schema fixtures;
- example Work Units;
- example Experiment Manifest;
- schema-validation code;
- deterministic experiment harness;
- Python package metadata such as `pyproject.toml`;
- runnable `idkmesh` CLI;
- orchestrator implementation;
- verifier implementation;
- adapter interface implementation;
- tests;
- GitHub Actions workflows / CI;
- generated benchmark/result artifacts.

The repository currently has no `.github/workflows` directory, and the current `main` commit has no reported CI status checks.

## Important consistency observations

### Result naming needs consolidation

Different parts of the repository use terms such as:

- `ResultManifest`;
- `Experiment Result`;
- `Evidence Report`;
- candidate artifact / verification evidence.

Before the first implementation becomes widely depended on, define the relationship between these objects explicitly.

A useful separation could be:

1. **WorkResult** — what one worker attempted and produced.
2. **VerificationResult** — what an independent verifier observed.
3. **ExperimentResult** — aggregate result for a controlled experiment configuration/run.
4. **EvidenceReport** — user-facing composition of worker + verifier + provenance evidence.

Do not collapse worker self-report and verifier evidence into one trusted object.

### `WorkUnit` vs `Work Contract`

The conceptual documents frequently use **Work Contract**, while the schema uses **Work Unit**.

This can be coherent if explicitly defined:

- `WorkUnit` = the versioned machine-readable core object;
- `Work Contract` = WorkUnit plus bound project/domain policy and execution/verification obligations.

If that is the intended relationship, document it once and use it consistently.

### IDKGraph should not block Phase 0

IDKGraph is valuable, but the Phase-0 runner should not require implementation of the full temporal hypergraph.

A simple persisted task/evidence DAG or append-only JSONL event stream is enough for the first executable kernel, as long as it can later map into IDKGraph.

This protects agility.

## Highest-priority next step

Issue **#19** is currently the correct bottleneck and should be treated as the project execution focus.

The fastest path from specification to evidence is:

1. finish `experiment-result-v0.1.schema.json`;
2. add one valid Work Unit fixture;
3. add one valid Experiment Manifest fixture;
4. add one deterministic smoke configuration;
5. implement a tiny Python validator/harness;
6. emit a schema-valid Experiment Result;
7. add unit tests;
8. add GitHub Actions that validate schemas/fixtures but never execute arbitrary embedded commands;
9. document one command a newcomer can run after cloning;
10. publish the first reproducible result artifact.

Only after this loop works should the project invest heavily in multi-agent adapters or federation.

## Suggested Phase-0 repository shape

```text
schemas/
  work-unit-v0.1.schema.json
  experiment-manifest-v0.1.schema.json
  experiment-result-v0.1.schema.json

examples/
  work-units/
    hello-verification.json
  experiments/
    smoke-v0.1.json
  results/
    smoke-v0.1.expected.json

src/idkmesh/
  __init__.py
  schemas.py
  experiment.py
  cli.py

tests/
  test_schemas.py
  test_smoke_experiment.py

.github/workflows/
  ci.yml

pyproject.toml
```

This is deliberately small.

## Recommended immediate sequencing

### P0 — make the repository executable

Complete issue #19.

Definition of success:

> A new contributor can clone the repository, install one development dependency set, run one command, validate the example schemas, run a deterministic safe smoke experiment, and receive a schema-valid result.

### P1 — independent verification loop

Implement the smallest worker-result + verifier-result separation.

Use a deterministic worker first. Do not begin with a complicated autonomous coding agent.

### P2 — two heterogeneous worker adapters

Only after the deterministic path works, connect two different adapters behind the same coordinator interface.

### P3 — Experiment 001

Run the first reproducible comparison of one strong worker vs small/homogeneous/heterogeneous teams under recorded resource budgets.

### P4 — distributed/cell simulation

Then implement and benchmark global vs sharded vs autonomous-cell coordination using the same Work Unit / evidence contracts.

## Repository health assessment

| Dimension | Current assessment | Comment |
| --- | --- | --- |
| Vision | Strong | ambitious but increasingly bounded by falsifiable experiments |
| Architecture | Strong | many good hypotheses; must now be benchmark-driven |
| Research program | Strong | clear questions, metrics, and negative-result orientation |
| Community foundation | Strong for project age | unusually good early contributor/governance structure |
| Decision history | Strong | ADRs, IDKIPs, conversation archive |
| Executable kernel | Early | schemas started; harness not yet present |
| Tests | Missing/early | no visible test suite yet |
| CI | Missing | no `.github/workflows` yet |
| Reproducible experiments | Planned | first manifest schema exists; no complete loop yet |
| User-installable product | Not yet | Verified Swarm Runner remains a target |

## Bottom line

The repository is **conceptually strong and substantially more coherent than a normal project at this age**. Its main risk is now the opposite of the original problem: it can accumulate sophisticated documents faster than executable evidence.

The project should therefore adopt this near-term rule:

> **No new major architecture layer without either an executable artifact, a benchmark, a simulation, or a falsifiable experiment attached to it.**

For the next milestone, the highest-value work is to complete #19 and make IDKMesh runnable in a deterministic, safe, reproducible form on one laptop.
