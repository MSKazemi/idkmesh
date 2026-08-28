# Conversation: Phase 0 executable foundation

Date: 2026-08-28

## Context

After defining ten field-level research questions and prioritizing collective-intelligence scaling, verification scaling, and Work Unit theory, the project created research issues #13, #14, and #15 plus `docs/research/FIRST_RESEARCH_PROGRAM.md`.

The next agreed action was Phase 0: implement a versioned Work Unit schema, experiment manifest/result schemas, and a minimal reproducible harness.

## User direction

The user said: **"Go head"**, meaning proceed with the concrete Phase 0 implementation in the public `MSKazemi/idkmesh` repository.

## Implementation decisions

1. Use JSON Schema Draft 2020-12 for the first machine-readable contracts.
2. Version the initial contracts as `0.1` and retain old versions for reproducibility.
3. Make the shared schema core strict while preserving a namespaced `extensions` escape hatch for research fields.
4. Treat a Work Unit as more than a prompt: it includes bounded scope, dependencies, permissions, uncertainty, validators, evidence, budget, provenance, and failure semantics.
5. Require experiment manifests to preregister hypotheses, configurations, metrics, seeds, stopping rules, environment, and budget.
6. Normalize each experiment run into a result object that records metrics, costs, verification outcomes, artifacts, and provenance.
7. Keep Phase 0 small: Python plus the `jsonschema` package rather than a larger framework.
8. Add a deterministic built-in smoke runner whose score tests reproducibility plumbing and is explicitly not scientific evidence.
9. Never execute commands supplied by experiment manifests in repository CI. The smoke command fails closed for `command` and `external` runner types.
10. Use Phase 1 experiments to discover which v0.1 schema fields are actually useful; schema failures/friction are themselves research evidence.

## Files added

- `schemas/work-unit-v0.1.schema.json`
- `schemas/experiment-manifest-v0.1.schema.json`
- `schemas/experiment-result-v0.1.schema.json`
- `schemas/README.md`
- `examples/work-units/phase0-smoke.work-unit.json`
- `examples/experiments/phase0-smoke.manifest.json`
- `experiments/harness.py`
- `requirements-phase0.txt`
- `.github/workflows/phase0-schema-check.yml`
- `.gitignore`
- `docs/research/PHASE_0_SPEC.md`

Tracking issue: #19.

## Intended next step

Phase 1 should build a small real software-engineering benchmark (roughly 5-20 tasks) and compare a single-worker baseline, independent workers, a role-specialized team, and independent verification using the Phase 0 contracts. It should measure schema friction and revise the contracts only based on observed needs.
