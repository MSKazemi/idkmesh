# Conversation record — Goals and next steps

**Date:** 2026-08-28

## Project-owner questions

- What are the next steps for IDKMesh?
- Have the project goals been worked out?
- What are the actual goals of the project?

## Finding

The project already had a broad vision, decision log, research questions, and a detailed staged roadmap, but its goals were distributed across multiple documents. A dedicated `GOALS.md` was added to make the goal hierarchy explicit.

## Current North Star

Build an open collective software-engineering system in which large numbers of humans, AI agents, and heterogeneous computers can collaborate on useful projects and produce **verified useful work** that improves as participation grows.

## Primary goals

1. Determine when coordinated smaller/heterogeneous coding agents can outperform an individual-agent baseline.
2. Enable useful collaboration even when the global target is ambiguous or disputed.
3. Define portable, bounded Work Units that can be executed across heterogeneous machines and workers.
4. Build verification and integration strong enough to support enterprise-quality software without trusting individual contributors or agents.
5. Create an open-source community and governance system that can scale with the technical network.
6. Keep the coordination protocol independent of any one model, hardware type, or repository forge.
7. Produce reproducible scientific knowledge about collective software intelligence, including negative results.

## Main KPI

**Verified useful work per unit of human attention and compute.**

This must be accompanied by a multi-objective scorecard for correctness, security, maintainability, human review time, compute cost, reproducibility, diversity, and contributor health.

## Immediate execution priority

Do not start by building a huge distributed network. First prove the coordination loop locally:

1. Specify Work Unit and Result Manifest schemas.
2. Build a single-machine coordinator with multiple worker adapters.
3. Isolate candidate implementations with Git branches/worktrees and sandboxing.
4. Build an independent validator that candidate workers cannot modify.
5. Run Experiment 001: one strong model versus different small-model ensembles and specialized teams.
6. Publish positive and negative results.
7. Only after this loop works, move to 3–10 and then 10–20 real laptops.

## Decision

The project should distinguish clearly between:

- **vision:** planetary-scale collective software intelligence;
- **scientific goals:** discover the rules under which many imperfect workers become collectively useful;
- **near-term product:** a verification-first multi-agent software-engineering orchestrator;
- **first proof:** a reproducible 1-vs-N coding-agent experiment.

The project should earn scale rather than assume it.
