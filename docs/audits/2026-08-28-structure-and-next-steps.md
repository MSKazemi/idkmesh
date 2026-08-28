# Repository Structure and Next-Steps Audit

Date: 2026-08-28

## Current assessment

IDKMesh has crossed from a small exploratory repository into a multi-track project.

The repository now contains:

- machine-readable Work Unit / Result / experiment contracts;
- a deterministic Phase 0 harness and CI;
- architecture for the Verified Swarm Runner, IDKGraph, federation, and self-evolution;
- substantial research tracks in collective intelligence, verification, Work Units, randomness, evolution, and distributed scheduling;
- community/governance/ACE infrastructure;
- a growing public conversation and findings archive;
- active implementation trackers for the local orchestrator, independent verifier, volunteer node, repository observatory, and v0.1 runner.

This is healthy expansion, but structural pressure is becoming visible.

## Structural concerns

### 1. Root-document crowding

Many substantial topic documents are still at repository root even though typed `docs/` subtrees now exist.

Examples include architecture/evolution, scientific/mathematical foundations, blockchain/randomness research, project goals/questions, and community-growth strategy.

Root should increasingly function as the project front door, not the complete knowledge base.

### 2. Two taxonomies are emerging

The repository has both:

- top-level topic Markdown files; and
- typed `docs/architecture`, `docs/research`, `docs/community`, `docs/findings`, `docs/decisions`, `docs/specifications`, `docs/audits`, and `docs/conversations`.

If this continues without a migration policy, contributors and agents must learn two parallel rules for where new knowledge belongs.

### 3. Documentation is growing faster than executable core

The Phase 0 contracts/harness are real and CI-verified, but the central product path still depends on:

- #4 — single-machine multi-worker orchestrator;
- #5 — independent validator/benchmark;
- #16 — local Git-native Verified Swarm Runner.

The next development cycle should keep executable artifacts ahead of new architecture layers.

### 4. Self-evolution already has an appropriate tracker

Issue #20 defines the P0 IDKGraph repository observatory and explicitly forbids automatic document moves in the first stage. The Repository Homeostasis Engine should become the deterministic structural controller feeding that effort rather than create a competing self-evolution architecture.

### 5. `main` is currently unprotected

Repository metadata currently reports the `main` branch as unprotected. This is acceptable during very early bootstrap, but it is incompatible with higher levels of autonomous repository evolution.

Before RHE/ACE/agents receive stronger write capabilities, branch/ruleset protection and required independent checks should become explicit project invariants.

## Restructure recommendation

**Yes, restructure — incrementally, not as a bulk cleanup.**

Suggested first migration experiment:

1. create `docs/foundations/README.md`;
2. move a small coherent group such as `VISION.md`, `GOALS.md`, and scientific/mathematical foundation documents into `docs/foundations/`;
3. repair all inbound links mechanically;
4. run repository homeostasis + existing CI;
5. compare before/after navigation and orphan/link metrics;
6. request independent review;
7. merge only if the migration is clearly simpler than the old structure.

Do **not** simultaneously reorganize research, architecture, community, schemas, experiments, and governance. Small migrations provide evidence and are easy to revert.

## Recommended root policy

Keep root focused on entrypoints and repository-health/community files:

- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `COMMUNITY.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- `GOVERNANCE.md`
- `MAINTAINERS.md`
- `ROADMAP.md`
- `PROJECT_RULES.md`
- `IDKIPS.md`
- build/package metadata as implementation matures

Most deep scientific, architecture, research, and strategy documents should converge under typed `docs/` modules.

## Priority order from here

### P0 — protect and observe

1. establish branch/ruleset protection for `main` before stronger automation;
2. merge/test Repository Homeostasis Engine v0;
3. use RHE output to extend #20 into a machine-readable IDKGraph observatory;
4. perform one small evidence-backed root-to-`docs/` migration.

### P0 — build the product loop

In parallel, prioritize:

1. #4 local multi-worker orchestrator;
2. #5 independent verifier;
3. #16 Verified Swarm Runner integration;
4. #17 A2A/MCP mapping while contracts are still experimental;
5. #11 safe local volunteer-node prototype after the local execution boundary is stable.

### P1 — run real research

Once the local verified loop works:

- #2 / #13 many-small-vs-strong scaling experiment;
- #14 verification scaling/backpressure;
- #29–#32 stochastic/randomness experiments;
- #22 vague-goal/emergence experiment.

## Architectural conclusion

The repository should become self-maintaining through a feedback loop:

`observe -> measure pressure -> propose bounded rewrite -> simulate/check -> review -> merge -> measure actual effect -> update policy evidence`

Iteration count controls when to look. **Evidence and structural pressure control whether to reorganize.**
