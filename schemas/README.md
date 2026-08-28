# IDKMesh schemas

This directory contains the machine-readable contracts used by the executable research foundation and the first local Verified Swarm Runner work.

## Current versions

- `work-unit-v0.2.schema.json` — current bounded unit of independently executable/verifiable work. It adds vendor-neutral capability/resource requirements, explicit security/trust classification, an independent-verification policy, and the `benchmarking` work kind required by issue #3.
- `result-manifest-v0.1.schema.json` — **worker self-report** for one Work Unit attempt: produced candidate artifacts, logs, resource use, self-reported claims/confidence, provenance, and a request for independent verification. It is deliberately not an acceptance verdict.
- `evidence-report-v0.1.schema.json` — **verifier evidence** about one worker ResultManifest/candidate: verifier identity and independence basis, evaluated artifact digests, checks, evidence artifacts, resource use, limitations, and a bounded verdict. Its `acceptance_scope` is always `evidence_only`; it cannot merge or accept a candidate by itself.
- `experiment-manifest-v0.1.schema.json` — preregistered experiment design: hypotheses, configurations, metrics, seeds, budgets, and stopping rules.
- `experiment-result-v0.1.schema.json` — one normalized **experiment-run result** with metrics, costs, verification outcomes, artifacts, and provenance.

All current schemas use JSON Schema Draft 2020-12.

## WorkUnit v0.2 contract

The current WorkUnit contract explicitly separates several concerns that were implicit or missing in v0.1:

- `kind` supports at least coding, testing, review, benchmarking, and documentation work;
- `requirements.capabilities` describes vendor-neutral worker capabilities;
- `requirements.resources` describes minimum CPU/memory/disk/GPU needs;
- `security` declares risk class, data classification, minimum worker trust, and whether sandboxing is required;
- `permissions` bounds network, filesystem, secret, and process authority;
- `verification_policy` states how independent validation is combined;
- `validators` states concrete required checks;
- `evidence_requirements` tells a verifier what evidence must exist without needing a worker's private reasoning;
- `dependencies` represents WorkUnit graph relationships;
- `provenance` records origin and optional source revision/timestamp.

The coordinator contract remains model/provider neutral. Model and adapter details belong in worker/result/verifier provenance, not in WorkUnit scheduling semantics.

## Critical separation: task, candidate, evidence, decision

IDKMesh keeps four concepts separate:

```text
Work Unit
   -> worker attempt
   -> ResultManifest (candidate + worker self-report)
   -> independent verifier attempt
   -> EvidenceReport (checks + evidence + bounded verdict)
   -> experiment/integration/human/governance decision
```

A worker may report that it completed successfully and may report confidence, but those fields are evidence about the worker's own state, not proof that the artifact is correct. The `ResultManifest` therefore does not contain an `accepted` field or an independent-verifier verdict.

An Evidence Report may say that its checks `supports_candidate`, `rejects_candidate`, are `inconclusive`, or that the verifier itself failed. That still does not grant repository acceptance. `acceptance_scope` is fixed to `evidence_only` so a later integration/governance layer remains the authority that decides what happens to canonical project state.

### Independence is a semantic contract

JSON Schema can validate the shape of an Evidence Report, but independence also depends on relationships between protocol objects. The Phase 0 harness therefore additionally checks that:

- the report references the exact worker ResultManifest by canonical digest;
- Work Unit id/version and Work Unit provenance digest match;
- the `validator_id` was requested by the worker ResultManifest;
- evaluated artifact ids and digests match artifacts actually produced by the worker;
- checks reference evidence artifacts that exist in the report;
- a report claiming `independent` does not use the same verifier id as the worker id;
- `supports_candidate` is forbidden when any required check did not pass.

These cross-object rules deliberately live in the harness/protocol semantics rather than pretending JSON Schema alone can prove independence.

## Negative fixtures

The repository includes adversarial contract fixtures:

- `examples/results/invalid-self-acceptance.result-manifest.json` intentionally tries to add `accepted: true`; CI requires rejection.
- `examples/work-units/invalid-missing-security.work-unit.json` intentionally omits required security/trust classification; CI requires rejection.
- `examples/results/invalid-self-verification.evidence-report.json` is intentionally schema-shaped like an Evidence Report but uses the worker itself as a verifier while claiming independence; the semantic harness requires rejection.

The positive verification fixture is `examples/results/phase0-smoke.evidence-report.json`.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

That rule is why issue #3 is completed through `work-unit-v0.2.schema.json` instead of silently changing `work-unit-v0.1.schema.json`.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Compatibility notes

- WorkUnit v0.1 remains available for historical Phase 0 artifacts.
- The current harness validates new WorkUnits against v0.2.
- ResultManifest v0.1 remains compatible with the v0.2 smoke fixture because it references the WorkUnit by stable `id` plus document `version`; the fixture now references WorkUnit version `2`.
- EvidenceReport v0.1 references ResultManifest v0.1 by id, worker id, and canonical SHA-256 digest and is therefore explicit about the exact candidate report it evaluated.
- A future ResultManifest or EvidenceReport revision should only be created when its own semantics require a breaking change.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — worker output and independent verification are separate protocol objects/stages.
3. **Evidence is not authority** — even an independent Evidence Report cannot autonomously change canonical repository state.
4. **Uncertainty is data** — assumptions, confidence, and unresolved statements can travel with the work without becoming truth by assertion.
5. **Cost is part of quality** — compute, time, tokens, communication, and human attention must be measurable.
6. **Provenance from day one** — experiments and outputs should be traceable.
7. **Reproducibility before sophistication** — early contracts should remain understandable and replayable.
8. **Vendor-neutral core** — WorkUnit semantics describe needed capabilities, not a specific model/provider/tool.
9. **Safe CI** — repository CI validates manifests and fixtures but does not execute commands supplied by experiment manifests.

See `docs/research/PHASE_0_SPEC.md`, issue #3, issue #5, issue #15, issue #16, issue #17, and the completed Phase 0 issue #19.
