# IDKMesh Architecture

This directory contains architecture hypotheses and implementation directions. Architecture documents are proposals/evolving specifications unless an ADR or project rule makes a decision explicit.

## Start here

- [`SCALABILITY_AND_AGILITY.md`](SCALABILITY_AND_AGILITY.md) — scale-from-one-to-millions architecture and Fractal Autonomous Cells.
- [`IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`](IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md) — typed temporal hypergraph for goals, tasks, evidence, provenance, and evolution.
- [`SELF_EVOLVING_REPOSITORY.md`](SELF_EVOLVING_REPOSITORY.md) — guarded self-evolution architecture and autonomy ladder.
- [`REPOSITORY_HOMEOSTASIS_ALGORITHM.md`](REPOSITORY_HOMEOSTASIS_ALGORITHM.md) — deterministic structural-pressure/evolution-epoch controller for repository maintenance.
- [`AGENT_NETWORK_AND_VOLUNTEER_NODES.md`](AGENT_NETWORK_AND_VOLUNTEER_NODES.md) — agent/compute participation and volunteer-node architecture.

## Relationship between self-evolution documents

`SELF_EVOLVING_REPOSITORY.md` describes the broad guarded self-evolution system.

`REPOSITORY_HOMEOSTASIS_ALGORITHM.md` is its proposal-first deterministic controller for deciding **when repository structure deserves intervention** and generating bounded restructuring candidates.

Issue #20 tracks the executable P0 repository observatory/IDKGraph work.

## Architecture rule

Do not turn architecture hypotheses directly into autonomous authority. New mechanisms should progress through:

`proposal -> executable prototype/simulation -> independent verification -> measured evidence -> reviewed adoption`
