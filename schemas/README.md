# IDKMesh schemas

This directory contains the machine-readable contracts used by the executable research foundation, the first local Verified Swarm Runner work, and the zero-project-spend compute router.

## Current versions

- `work-unit-v0.2.schema.json` — current bounded unit of independently executable/verifiable work. It adds vendor-neutral capability/resource requirements, explicit security/trust classification, independent-verification policy, the `benchmarking` work kind required by issue #3, and an explicit project-spend budget.
- `compute-policy-v0.1.schema.json` — repository-level financial/eligibility guard for compute. The current project policy sets project compute spend to `$0` and disables paid providers.
- `compute-offer-pool-v0.1.schema.json` — provider-neutral capacity offers used by the selector: availability, cost class, project monetary cost, trust, capabilities, resources, expected wait, success probability, and independence group.
- `result-manifest-v0.1.schema.json` — **worker self-report** for one Work Unit attempt: produced candidate artifacts, logs, resource use, self-reported claims/confidence, provenance, and a request for independent verification. It is deliberately not an acceptance verdict.
- `evaluator-plan-v0.1.schema.json` — **verifier-owned evaluation control** bound to an exact WorkUnit digest/source revision. v0.1 is deliberately `metadata_only`, may be public or hidden from the worker, and requires evaluator control data to remain outside the candidate workspace.
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
- `budget.project_spend_usd_max` states the most the IDKMesh project may pay for that Work Unit;
- `budget.paid_fallback_allowed` states whether the Work Unit would permit a paid fallback **if** repository policy also permits it;
- `dependencies` represents WorkUnit graph relationships;
- `provenance` records origin and optional source revision/timestamp.

A Work Unit cannot grant financial authority. Repository policy is applied first and acts as a hard ceiling. Therefore a Work Unit may tighten the project spending constraint but cannot relax it.

The coordinator contract remains model/provider neutral. Model and adapter details belong in worker/result provenance, not in WorkUnit scheduling semantics.

## EvaluatorPlan v0.1 and evaluator sovereignty

The public WorkUnit says **what evidence/checks are required**. The EvaluatorPlan says **how an independent verifier instantiates deterministic checks** for a particular WorkUnit/revision.

The separation is intentional:

```text
WorkUnit (public contract)
        |
        v
worker -> ResultManifest + candidate workspace
        |
        | evaluator control is verifier-owned
        v
EvaluatorPlan -> independent validator -> VerificationResult
```

Important properties of v0.1:

- `binding.work_unit_digest` pins the plan to canonical WorkUnit content;
- `source_revision` pins the expected candidate base/revision identity;
- `visibility` can be `public` or `hidden`;
- `execution_mode` is fixed to `metadata_only`;
- the plan contains a complete SHA-256 baseline snapshot plus explicitly ignored paths;
- only deterministic built-ins are supported: input schema, scope, artifact digest, provenance, and verification-request coverage;
- plan policy requires verifier control data outside the candidate root, rejects candidate symlinks, and requires candidate-local artifact resolution.

`experiments/local_validator.py` implements this contract. It does **not** execute candidate-controlled code in v0.1.

The deterministic change-scope rule is:

```text
Delta = complete_candidate_snapshot XOR trusted_baseline_snapshot

Authorized(path) =
  InAllowedPaths(path)
  AND InFilesystemWriteAuthority(path)
  AND NOT InForbiddenPaths(path)

ScopePass = all(Authorized(path) for path in Delta)
```

The verifier derives `Delta` from the workspace rather than trusting the worker's list of produced artifacts. This prevents a worker from hiding an unauthorized mutation simply by omitting it from ResultManifest.

See `docs/architecture/INDEPENDENT_VALIDATOR_RUNNER.md` and `docs/decisions/ADR-0008-evaluator-sovereignty.md`.

## Zero-project-spend compute contracts

The active machine-readable policy is `config/compute-policy.json`:

```text
project_spend_usd_max = 0
paid_providers_enabled = false
```

Allowed cost classes currently include:

- `local_owned` — a participant's own already-available machine;
- `donated` — explicitly volunteered capacity;
- `public_project_ci` — public-project CI only when the task legitimately fits that service's terms;
- `grant` — capacity funded externally without a project invoice;
- `free_tier` — genuine free quota within its terms and limits.

`paid` is represented in the offer schema for interoperability/testing but is disabled by repository policy.

The selector prototype is `experiments/free_compute_router.py`. It filters provider-neutral offers against both repository policy and Work Unit requirements. Its fail-closed invariant is:

> **No eligible zero-project-cost offer -> no selection. Never silently convert resource scarcity into project spending.**

CI includes a negative test in which a synthetic GPU Work Unit tries to authorize `$100` and paid fallback while the only available matching GPU is a paid offer. Repository policy must still reject it and return no eligible offer.

“Zero cost to the project” does not mean zero real-world cost. Donors can bear electricity, bandwidth, thermal load, hardware wear, and opportunity cost. Donated compute therefore must remain opt-in, transparent, resource-capped, and easy to stop.

## Critical separation: candidate, evaluator, verification, integration

IDKMesh keeps these concepts separate:

```text
Work Unit
   -> worker attempt
   -> ResultManifest (candidate + worker self-report)
   -> verifier-owned EvaluatorPlan
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

The local validator adds runtime trust-boundary checks:

- EvaluatorPlan must bind the exact WorkUnit digest/version;
- verifier identity cannot equal worker identity when independence is required;
- evaluator control data is rejected if it is inside the candidate workspace;
- verification output is written outside the candidate workspace;
- candidate paths cannot escape the candidate root;
- a complete baseline snapshot detects undeclared added/modified/deleted files;
- produced artifact hashes are recomputed independently;
- WorkUnit and source-revision provenance are recomputed/compared;
- required WorkUnit validators must be covered even if the worker omits them from its request.

Negative fixtures/tests include:

- `examples/results/invalid-self-acceptance.result-manifest.json` adds worker-side `accepted: true` and must fail schema validation;
- `examples/results/invalid-non-independent.verification-result.json` is schema-valid but deliberately violates the WorkUnit's independence rule and must fail cross-object contract validation;
- `examples/work-units/invalid-missing-security.work-unit.json` omits required security/trust classification and must fail schema validation;
- `python experiments/local_validator.py self-test` creates unauthorized-path, artifact-tampering, and candidate-owned-evaluator cases that must fail.

## Versioning rule

`0.x` schemas are experimental. A change is breaking when a previously valid document can become invalid or when the meaning of an existing field changes. Breaking changes require a new schema file/version; old schema files remain in the repository so historical experiments stay reproducible.

That rule is why issue #3 is completed through `work-unit-v0.2.schema.json` instead of silently changing `work-unit-v0.1.schema.json`.

**Compatibility note:** adding mandatory monetary-budget fields to v0.2 is currently an in-development contract change made before a stable release. Once a schema version is used for durable external artifacts, future breaking changes must use a new version rather than modifying that file in place.

Additive research-specific data should normally go in the `extensions` object, using a namespaced key such as `org.example.my_metric`, until there is evidence that the field belongs in the shared core.

## Compatibility notes

- WorkUnit v0.1 remains available for historical Phase 0 artifacts.
- The current harness validates new WorkUnits against v0.2.
- The valid v0.2 Phase 0 smoke fixture includes the new zero-project-spend budget fields.
- The deliberately invalid Work Unit fixture remains invalid and is used only as a negative test.
- ResultManifest v0.1 remains compatible with the v0.2 smoke fixture because it references the WorkUnit by stable `id` plus document `version`; the fixture references WorkUnit version `2`.
- EvaluatorPlan v0.1 is an additive verifier-control contract; it does not change ResultManifest semantics.
- VerificationResult v0.1 binds to a ResultManifest plus the same WorkUnit id/version/attempt and adds independent evidence without redefining worker output semantics.
- Future EvaluatorPlan versions may add sandboxed executable checks only after the execution boundary is implemented; v0.1 remains metadata-only.
- Future ResultManifest or VerificationResult revisions should only be created when their own semantics require a breaking change.

## Design principles

1. **Bounded authority** — a Work Unit states scope and permissions.
2. **Proposal is not proof** — worker output and independent verification are separate protocol objects/stages.
3. **Evaluator sovereignty** — a worker cannot control the evaluator used to judge its own candidate.
4. **Verification is not integration authority** — verifier recommendations remain evidence for a later policy/human decision.
5. **Uncertainty is data** — assumptions, confidence, and unresolved statements can travel with the work without becoming truth by assertion.
6. **Project spending is an authority boundary** — task inputs and agents cannot authorize billing; repository policy is the hard ceiling.
7. **Cost is part of quality** — project money, donated resource use, compute, time, tokens, communication, and human attention must be distinguishable and measurable.
8. **Provenance from day one** — experiments and outputs should be traceable.
9. **Reproducibility before sophistication** — early contracts should remain understandable and replayable.
10. **Vendor-neutral core** — WorkUnit semantics describe needed capabilities, not a specific model/provider/tool.
11. **Safe CI** — repository CI validates manifests and fixtures but does not execute commands supplied by experiment manifests or candidate-controlled code.

See `PROJECT_RULES.md`, `docs/decisions/ADR-0006-zero-project-spend-compute.md`, `docs/decisions/ADR-0008-evaluator-sovereignty.md`, `docs/architecture/OPPORTUNISTIC_COMPUTE_FABRIC.md`, `docs/architecture/INDEPENDENT_VALIDATOR_RUNNER.md`, `docs/research/PHASE_0_SPEC.md`, `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`, issues #3, #5, #11, #14, #15, #17, and the completed Phase 0 issue #19.
