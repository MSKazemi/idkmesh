# IDKMesh schemas

This directory contains the machine-readable contracts used by the Phase 0 research harness.

## Current versions

- `work-unit-v0.1.schema.json` — bounded unit of independently executable/verifiable work.
- `experiment-manifest-v0.1.schema.json` — preregistered experiment design: hypotheses, configurations, metrics, seeds, budgets, and stopping rules.
- `experiment-result-v0.1.schema.json` — one normalized run result with metrics, costs, verification, artifacts, and provenance.

All three use JSON Schema Draft 2020-12.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — validators and evidence requirements are explicit.
3. **Uncertainty is data** — assumptions and unresolved statements can travel with the work.
4. **Cost is part of quality** — compute, time, tokens, communication, and human attention must be measurable.
5. **Provenance from day one** — experiments and outputs should be traceable.
6. **Reproducibility before sophistication** — Phase 0 prefers understandable contracts over a large framework.
7. **Safe CI** — repository CI validates manifests but does not execute commands supplied by experiment manifests.

See `docs/research/PHASE_0_SPEC.md` and issue #19.
