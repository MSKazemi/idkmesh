# IDKMesh schemas

This directory contains the machine-readable contracts used by the executable research foundation and the first local Verified Swarm Runner work.

## Current versions

- `work-unit-v0.1.schema.json` — bounded unit of independently executable/verifiable work.
- `result-manifest-v0.1.schema.json` — **worker self-report** for one Work Unit attempt: produced candidate artifacts, logs, resource use, self-reported claims/confidence, provenance, and a request for independent verification. It is deliberately not an acceptance verdict.
- `experiment-manifest-v0.1.schema.json` — preregistered experiment design: hypotheses, configurations, metrics, seeds, budgets, and stopping rules.
- `experiment-result-v0.1.schema.json` — one normalized **experiment-run result** with metrics, costs, verification outcomes, artifacts, and provenance.

All current schemas use JSON Schema Draft 2020-12.

## Critical separation: candidate vs acceptance

IDKMesh keeps these concepts separate:

```text
Work Unit
   -> worker attempt
   -> ResultManifest (candidate + worker self-report)
   -> independent verifier(s)
   -> verification evidence
   -> experiment/integration decision
```

A worker may report that it completed successfully and may report confidence, but those fields are evidence about the worker's own state, not proof that the artifact is correct. The `ResultManifest` therefore does not contain an `accepted` field or an independent-verifier verdict.

`examples/results/invalid-self-acceptance.result-manifest.json` intentionally tries to add `accepted: true`. CI requires that this fixture be rejected.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — worker output and independent verification are separate protocol objects/stages.
3. **Uncertainty is data** — assumptions, confidence, and unresolved statements can travel with the work without becoming truth by assertion.
4. **Cost is part of quality** — compute, time, tokens, communication, and human attention must be measurable.
5. **Provenance from day one** — experiments and outputs should be traceable.
6. **Reproducibility before sophistication** — early contracts should remain understandable and replayable.
7. **Safe CI** — repository CI validates manifests and fixtures but does not execute commands supplied by experiment manifests.

See `docs/research/PHASE_0_SPEC.md`, issue #3, and issue #19.
