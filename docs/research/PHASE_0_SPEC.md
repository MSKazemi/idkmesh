# Phase 0: Executable Research Foundation

Phase 0 turns the first IDKMesh research program into machine-readable contracts that contributors can validate before the project attempts real multi-agent experiments.

Tracking issue: #19. Research tracks: #13, #14, #15.

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
Experiment Result JSON/JSONL
      |
      v
analysis / comparison / future scheduler
```

## 1. Work Unit v0.1

A Work Unit is a bounded piece of work that can be assigned to a human or agent with explicit authority and explicit verification.

Its required dimensions are:

- identity and version;
- work kind and objective;
- inputs and expected outputs;
- dependency edges;
- scope/policy constraints;
- uncertainty;
- permissions;
- validators;
- evidence requirements;
- resource budget;
- provenance;
- failure semantics.

A Work Unit is not merely a prompt. It is intended to become the contract between decomposition, scheduling, execution, verification, and integration.

Schema: `schemas/work-unit-v0.1.schema.json`

Fixture: `examples/work-units/phase0-smoke.work-unit.json`

## 2. Experiment Manifest v0.1

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

## 3. Experiment Result v0.1

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

## 4. Minimal harness

`experiments/harness.py` provides two commands.

### Validate

```bash
python -m pip install -r requirements-phase0.txt
python experiments/harness.py validate
```

This checks all three schema documents, validates the manifest, validates every referenced Work Unit, checks duplicate/mismatched Work Unit identifiers, and prevents repository-relative paths from escaping the repository root.

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

The first contracts are `0.1`. During the experimental period:

- additive experimentation should prefer namespaced extensions;
- semantic changes or new required fields require a new schema version;
- old schema files stay available so old results remain reproducible;
- migrations should eventually be explicit tools rather than silent reinterpretation.

## Relationship to the first three research tracks

### #13 Collective-intelligence scaling

The manifest gives every configuration explicit agent count, topology, seeds, metrics, budget, and verification policy. This is the minimum data needed to fit empirical scaling curves later.

### #14 Verification scaling

Work Units carry validators/evidence requirements, while results carry verification policy/check outcomes and costs. Future versions can add verifier diversity, queue pressure, risk scores, and escaped-defect measurements through extensions before standardization.

### #15 Work Unit theory

The v0.1 schema is itself a falsifiable hypothesis: these fields may or may not be the right contract. Experiments should measure which fields reduce context, rework, coupling, integration failures, and verification cost.

## Phase 0 definition of done

Phase 0 is complete when:

1. all three schemas exist and are versioned;
2. at least one Work Unit and manifest fixture validate;
3. a contributor can run the validator locally with one Python dependency;
4. the deterministic smoke path emits schema-valid result records;
5. CI validates the stack without executing manifest-supplied commands;
6. changes are documented and discoverable from issue #19.

## Next step: Phase 1

Do not build a giant distributed runtime next.

The next useful experiment is a small real benchmark runner with approximately 5-20 software tasks and a common adapter interface for:

- single worker baseline;
- several independent workers;
- planner/implementer/tester/reviewer configuration;
- independent verification.

Phase 1 should reuse these contracts and report where the v0.1 schemas fail in practice. Those failures are research results, not merely schema bugs.
