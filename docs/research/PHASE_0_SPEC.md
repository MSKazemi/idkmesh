# Phase 0: Executable Research Foundation

Phase 0 turns the first IDKMesh research program into machine-readable contracts that contributors can validate before the project attempts real multi-agent experiments.

Initial implementation tracking issue: #19. WorkUnit completion issue: #3. Research tracks: #13, #14, #15.

## Why this exists

IDKMesh cannot learn scaling laws if every experiment invents its own task representation, metrics, cost accounting, and result format. Phase 0 creates the smallest shared vocabulary needed to compare experiments without pretending that the vocabulary is already final.

The initial stack is intentionally boring:

```text
Work Unit JSON
      |
      v
Experiment Manifest JSON
      |
      v
Phase 0 Harness
      |
      v
Worker ResultManifest + Experiment Result JSON/JSONL
      |
      v
independent verification / analysis / future scheduler
```

## 1. Work Unit v0.2

A Work Unit is a bounded piece of work that can be assigned to a human or agent with explicit authority and explicit verification.

The original Phase 0 implementation created v0.1. Issue #3 exposed additional requirements that are necessary before the orchestrator/validator work should depend on the contract. Because those additions are breaking, v0.1 remains available and the current contract advances to v0.2.

Its required dimensions are:

- identity and document version;
- work kind and objective;
- inputs and expected outputs;
- dependency edges;
- vendor-neutral capability requirements;
- minimum resource requirements;
- scope/policy constraints;
- uncertainty;
- security risk and data classification;
- minimum worker trust and sandbox requirement;
- bounded execution permissions;
- independent-verification policy;
- concrete validators;
- evidence requirements;
- resource/time budget;
- provenance;
- failure semantics.

The required work kinds include:

- coding;
- testing;
- review;
- benchmarking;
- documentation.

Additional kinds currently include research, integration, governance, and `other`.

A Work Unit is not merely a prompt. It is intended to become the vendor-neutral contract between decomposition, scheduling, execution, verification, and integration. Model/provider details are not scheduling fields in the WorkUnit core.

Current schema: `schemas/work-unit-v0.2.schema.json`

Historical schema: `schemas/work-unit-v0.1.schema.json`

Valid fixture: `examples/work-units/phase0-smoke.work-unit.json`

Negative fixture: `examples/work-units/invalid-missing-security.work-unit.json`

## 2. Worker ResultManifest v0.1

A worker ResultManifest is a self-report for one attempt at a Work Unit. It records:

- WorkUnit identity/version;
- worker and adapter/model provenance;
- attempt status and timestamps;
- produced artifact locators and SHA-256 digests;
- logs and metrics;
- resource use;
- worker claims and confidence;
- source/environment provenance;
- the requested independent validators/evidence artifacts.

It deliberately does **not** contain an independent acceptance verdict. Worker completion and system acceptance are different states.

Schema: `schemas/result-manifest-v0.1.schema.json`

Valid fixture: `examples/results/phase0-smoke.result-manifest.json`

Negative fixture: `examples/results/invalid-self-acceptance.result-manifest.json`

## 3. Experiment Manifest v0.1

The manifest preregisters enough of an experiment to make later comparisons meaningful:

- research track(s);
- falsifiable hypotheses;
- referenced Work Units;
- configurations;
- agent count and coordination topology;
- verification policy;
- runner type;
- metrics and their direction;
- repetitions and random seeds;
- stopping rules;
- execution environment;
- resource budget.

This helps reduce accidental benchmark drift and hindsight selection of metrics.

Schema: `schemas/experiment-manifest-v0.1.schema.json`

Fixture: `examples/experiments/phase0-smoke.manifest.json`

## 4. Experiment Result v0.1

Every run emits a normalized record containing:

- experiment/run/configuration identity;
- seed and status;
- timestamps;
- named metrics;
- wall time, compute, human attention, and optional token cost;
- verification policy and check outcomes;
- artifact references;
- harness/manifest provenance;
- optional namespaced extensions.

Schema: `schemas/experiment-result-v0.1.schema.json`

The long-term goal is for results from very different orchestration strategies to remain comparable on common dimensions such as verified useful work, human attention, cost, latency, escaped defects, and communication.

## 5. Minimal harness

`experiments/harness.py` provides two commands.

### Validate

```bash
python -m pip install -r requirements-phase0.txt
python experiments/harness.py validate
```

This:

- validates all active schema documents;
- checks that WorkUnit v0.2 retains the required work kinds;
- checks that the WorkUnit contract retains explicit dependency, capability/resource, security, permissions, verification, evidence, and provenance fields;
- validates the manifest and every referenced Work Unit;
- checks duplicate/mismatched Work Unit identifiers;
- checks a ResultManifest against the referenced WorkUnit document version;
- checks that requested evidence artifact IDs were actually produced;
- requires the missing-security WorkUnit negative fixture to fail;
- requires the worker-self-acceptance ResultManifest negative fixture to fail;
- prevents repository-relative paths from escaping the repository root.

### Smoke

```bash
python experiments/harness.py smoke --output results/phase0-smoke.jsonl
```

The smoke runner exercises the full manifest -> Work Unit -> result path. It creates deterministic `smoke_score` values from experiment/configuration/seed identity, validates every emitted result, and records the canonical manifest SHA-256 digest.

`smoke_score` is an infrastructure fixture, **not scientific evidence**.

## Security boundary

Experiment manifests may eventually describe external or command-based runners, but repository CI must not execute contributor-controlled commands merely because they appear in a manifest.

Therefore the Phase 0 `smoke` command has a hard rule:

> It executes only the built-in `deterministic_smoke` runner and fails closed if a configuration uses `command` or `external`.

The GitHub Actions workflow uses only validation and this safe built-in smoke path.

Future execution engines should use sandboxing, capability restrictions, explicit approval, resource limits, and artifact provenance before running untrusted Work Units.

## Extension strategy

The schemas are deliberately strict at the shared core (`additionalProperties: false`) but each top-level object includes `extensions` with arbitrary namespaced fields.

This allows experiments to add fields such as:

```json
{
  "extensions": {
    "org.idkmesh.scheduler.queue_pressure": 0.42,
    "org.example.research.special_metric": 17
  }
}
```

A field should graduate into the common schema only after multiple experiments show that it is stable, reusable, and well defined.

## Versioning

The contracts are pre-1.0 and experimental, but historical reproducibility still matters:

- additive experimentation should prefer namespaced extensions;
- semantic changes or new required fields require a new schema version;
- old schema files stay available so old results remain reproducible;
- migrations should be explicit tools rather than silent reinterpretation.

This is why the stricter issue #3 contract is `work-unit-v0.2.schema.json` rather than an in-place rewrite of v0.1.

## Relationship to research and implementation tracks

### #13 Collective-intelligence scaling

The manifest gives every configuration explicit agent count, topology, seeds, metrics, budget, and verification policy. This is the minimum data needed to fit empirical scaling curves later.

### #14 Verification scaling

WorkUnits carry explicit verification policy, validators, and evidence requirements, while results carry verification outcomes and costs. Future versions can add verifier diversity, queue pressure, risk scores, and escaped-defect measurements through extensions before standardization.

### #15 Work Unit theory

The v0.2 schema is still a falsifiable hypothesis. Experiments should measure which fields reduce context, rework, coupling, integration failures, and verification cost.

`docs/specifications/WORK_UNIT_COMPOSABILITY_V0_2.md` defines the reference
five-arm benchmark, metrics, formal example DAG, and validation interface. Its
committed observations are explicitly synthetic infrastructure fixtures; only
controlled independent runs may be promoted to research evidence.

### #17 interoperability

The WorkUnit stays model/vendor neutral so its semantics can be mapped to external agent/task protocols without forcing the coordinator to branch by provider.

### #4 and #5

The single-machine orchestrator and independent validator can now build against a contract that explicitly states worker requirements, authority, risk, verification policy, and expected evidence.

## Phase 0 / issue #3 definition of done

The executable schema foundation is ready for the next implementation layer when:

1. active schemas are versioned and pass Draft 2020-12 validation;
2. a valid WorkUnit/manifest/ResultManifest path validates;
3. negative WorkUnit and ResultManifest fixtures are rejected;
4. coding/testing/review/benchmarking/documentation kinds are represented by the WorkUnit contract;
5. capability/resource, security/trust, execution permission, dependency, verification, evidence, and provenance semantics are explicit;
6. a contributor can run validation locally with one Python dependency;
7. deterministic smoke execution emits schema-valid result records;
8. CI validates the stack without executing manifest-supplied commands.

## Next step: Phase 1

Do not build a giant distributed runtime next.

The next useful implementation is the local multi-worker orchestrator in #4 together with the independent validator/benchmark in #5. Start with a small real software-task set and a common adapter interface for:

- single-worker baseline;
- several independent workers;
- planner/implementer/tester/reviewer configuration;
- independent verification.

Phase 1 should reuse these contracts and report where WorkUnit v0.2 fails in practice. Those failures are research results, not merely schema bugs.
