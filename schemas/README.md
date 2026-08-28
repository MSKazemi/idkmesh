# IDKMesh schemas

This directory contains the machine-readable contracts used by the executable research foundation and the first local Verified Swarm Runner work.

## Current versions

- `work-unit-v0.2.schema.json` — current bounded unit of independently executable/verifiable work. It adds vendor-neutral capability/resource requirements, explicit security/trust classification, an independent-verification policy, and the `benchmarking` work kind required by issue #3.
- `result-manifest-v0.1.schema.json` — **worker self-report** for one Work Unit attempt: produced candidate artifacts, logs, resource use, self-reported claims/confidence, provenance, and a request for independent verification. It is deliberately not an acceptance verdict.
- `verification-result-v0.1.schema.json` — **independent verifier result** for one ResultManifest: checks, evidence, findings, resource cost, independence/correlation metadata, provenance, and a recommendation. It is deliberately decision support rather than an automated merge/integration verdict.
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

The coordinator contract remains model/provider neutral. Model and adapter details belong in worker/result provenance, not in WorkUnit scheduling semantics.

## Critical separation: candidate, verification, integration

IDKMesh keeps these concepts separate:

```text
Work Unit
   -> worker attempt
   -> ResultManifest (candidate + worker self-report)
   -> independent verifier(s)
   -> VerificationResult (checks + evidence + recommendation)
   -> experiment/integration/human decision
```

A worker may report that it completed successfully and may report confidence, but those fields are evidence about the worker's own state, not proof that the artifact is correct. The `ResultManifest` therefore does not contain an `accepted` field or an independent-verifier verdict.

Likewise, a `VerificationResult` may recommend `accept_candidate`, but that recommendation does not authorize a merge or mutate canonical state. Integration policy remains a separate layer.

The harness validates cross-object invariants in addition to JSON structure:

- VerificationResult must reference the exact ResultManifest/WorkUnit attempt;
- evidence IDs referenced by checks must exist;
- required WorkUnit validator IDs must appear as verification checks;
- validator IDs requested by the ResultManifest must appear;
- when a WorkUnit requires independence, verifier identity must differ from worker identity;
- an `accept_candidate` recommendation requires verification status `passed` and all required checks passed.

Negative fixtures:

- `examples/results/invalid-self-acceptance.result-manifest.json` adds worker-side `accepted: true` and must fail schema validation;
- `examples/results/invalid-non-independent.verification-result.json` is schema-valid but deliberately violates the WorkUnit's independence rule and must fail cross-object contract validation;
- `examples/work-units/invalid-missing-security.work-unit.json` omits required security/trust classification and must fail schema validation.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

That rule is why issue #3 is completed through `work-unit-v0.2.schema.json` instead of silently changing `work-unit-v0.1.schema.json`.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Compatibility notes

- WorkUnit v0.1 remains available for historical Phase 0 artifacts.
- The current harness validates new WorkUnits against v0.2.
- ResultManifest v0.1 remains compatible with the v0.2 smoke fixture because it references the WorkUnit by stable `id` plus document `version`; the fixture references WorkUnit version `2`.
- VerificationResult v0.1 binds to a ResultManifest plus the same WorkUnit id/version/attempt and adds independent evidence without redefining worker output semantics.
- Future ResultManifest or VerificationResult revisions should only be created when their own semantics require a breaking change.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — worker output and independent verification are separate protocol objects/stages.
3. **Verification is not integration authority** — verifier recommendations remain evidence for a later policy/human decision.
4. **Uncertainty is data** — assumptions, confidence, and unresolved statements can travel with the work without becoming truth by assertion.
5. **Cost is part of quality** — compute, time, tokens, communication, and human attention must be measurable.
6. **Provenance from day one** — experiments and outputs should be traceable.
7. **Reproducibility before sophistication** — early contracts should remain understandable and replayable.
8. **Vendor-neutral core** — WorkUnit semantics describe needed capabilities, not a specific model/provider/tool.
9. **Safe CI** — repository CI validates manifests and fixtures but does not execute commands supplied by experiment manifests.

See `docs/research/PHASE_0_SPEC.md`, `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`, issues #3, #5, #14, #15, #17, and the completed Phase 0 issue #19.
