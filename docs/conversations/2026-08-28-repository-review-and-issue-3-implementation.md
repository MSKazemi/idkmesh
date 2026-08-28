# Repository Review and Issue #3 Implementation — 2026-08-28

## User request

Review the whole `MSKazemi/idkmesh` repository structure, determine the highest-value next step, and begin doing useful implementation work rather than only proposing more ideas.

## Repository structure reviewed

The repository was inspected recursively and through its active issue graph. The main architectural areas are now:

- `.github/` — contribution templates, CODEOWNERS, pull-request template, schema CI, and the experimental ACE community-growth workflow;
- root project documents — vision, goals, architecture, roadmap, decisions, governance, community, security, evolution, mathematical/scientific foundations, blockchain strategy, randomness/bio-inspired research, and project rules;
- `docs/architecture/` — deeper architecture proposals including volunteer nodes, IDKGraph, and self-evolving repository mechanisms;
- `docs/research/` — executable research program and Phase 0 specifications;
- `docs/findings/` — external research and project findings;
- `docs/conversations/` — durable project conversation records;
- `docs/decisions/` — architecture decision records;
- `schemas/` — WorkUnit, ResultManifest, experiment, and IDKGraph contracts;
- `examples/` — WorkUnit/result/experiment fixtures and graph examples;
- `experiments/` — the Phase 0 validation/smoke harness and research experiment code;
- `idkips/` plus `IDKIPS.md` — public IDKMesh Improvement Proposal process;
- open GitHub issues — implementation, verification, community, interoperability, distributed-node, IDKGraph, emergence, and randomness research tracks.

## Priority decision

The highest-leverage unfinished dependency was issue #3, `P0: Specify WorkUnit v0 and ResultManifest v0`.

Why it was selected:

- #4 (local multi-worker orchestrator) depends on it;
- #5 (independent validator/benchmark) depends on it;
- #16 (v0.1 Verified Swarm Runner) explicitly depends on it;
- #17 (A2A/MCP interoperability mapping) needs it before schema freeze;
- #15 studies the WorkUnit contract itself.

A repository consistency problem was also found: Phase 0 issue #19 had already been closed as complete, but the older and stricter issue #3 remained open.

## Gap analysis

The repository already contained:

- `schemas/work-unit-v0.1.schema.json`;
- `schemas/result-manifest-v0.1.schema.json`;
- valid WorkUnit and ResultManifest fixtures;
- a negative ResultManifest self-acceptance fixture;
- `experiments/harness.py`;
- CI in `.github/workflows/phase0-schema-check.yml`.

However, WorkUnit v0.1 did not satisfy every issue #3 acceptance criterion:

1. `benchmarking` was missing from the WorkUnit kinds;
2. vendor-neutral worker capability/resource requirements were not explicit;
3. risk/trust classification was not explicit;
4. verification had validators/evidence requirements but no explicit verification-policy object.

## Implementation

PR #33 implemented and merged the missing contract semantics.

### WorkUnit v0.2

Added:

`schemas/work-unit-v0.2.schema.json`

The new version preserves v0.1 for reproducibility and adds required:

- coding/testing/review/benchmarking/documentation kind coverage;
- vendor-neutral `requirements.capabilities`;
- minimum CPU/memory/disk/GPU resource requirements;
- `security.risk_class`;
- `security.data_classification`;
- `security.minimum_worker_trust`;
- `security.sandbox_required`;
- bounded network/filesystem/secrets/process permissions;
- explicit `verification_policy`;
- validators and evidence requirements;
- dependencies;
- provenance;
- uncertainty, budget, and failure semantics.

Model/provider details remain outside the WorkUnit scheduling core and stay in worker/result provenance.

### Fixtures

Updated:

- `examples/work-units/phase0-smoke.work-unit.json` to WorkUnit v0.2/document version 2;
- `examples/results/phase0-smoke.result-manifest.json` to reference WorkUnit version 2.

Added:

- `examples/work-units/invalid-missing-security.work-unit.json`.

The invalid fixture proves that security/trust classification cannot be silently omitted.

### Harness enforcement

Updated `experiments/harness.py` so validation now fails if the WorkUnit schema loses:

- any of coding/testing/review/benchmarking/documentation;
- dependencies;
- requirements;
- security;
- permissions;
- verification policy;
- validators;
- evidence requirements;
- provenance.

The harness also requires the missing-security WorkUnit fixture and worker-self-acceptance ResultManifest fixture to be rejected.

### Documentation

Updated:

- `schemas/README.md`;
- `docs/research/PHASE_0_SPEC.md`.

The documentation explains why this is v0.2 rather than a silent breaking rewrite of v0.1.

## Verification evidence

Pull request: #33 — `Complete WorkUnit contract for issue #3`

GitHub Actions run: `33179373196`

The `Phase 0 schema check` job passed, including:

- `Validate schemas and fixtures` — success;
- `Run safe built-in smoke fixture` — success.

The PR was squash-merged to `main` as commit:

`ac06fabcb1ddc2de762f03ca905c3bb0b760b728`

Issue #3 was then closed as `completed`.

## Newly unblocked next step

The next implementation layer should be issues #4 and #5 together:

1. build the smallest single-machine multi-worker orchestrator;
2. build an independent validator and small reproducible benchmark set;
3. connect them through WorkUnit v0.2 + ResultManifest v0.1;
4. run the first real candidate-generation -> independent-verification loop;
5. use failures to refine the contract rather than adding distributed networking prematurely.

This directly advances the v0.1 Verified Swarm Runner milestone (#16) and prepares Experiment #2.
