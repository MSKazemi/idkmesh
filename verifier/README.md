# `idkmesh-verify` repository-patch evaluator

`idkmesh-verify` extends the already-merged zero-cost deterministic verifier MVP in `experiments/local_verifier.py` from isolated JSON candidates to **bounded repository patch candidates** that may require independent hidden regression/lint/security commands.

The safe metadata/JSON baseline remains preferred whenever it can answer the correctness question without executing candidate code. This package is the next higher-risk evaluator backend: pinned source reconstruction, patch integrity/application, repository scope enforcement, and verifier-owned commands in a separate Docker sandbox.

It consumes:

1. one canonical `WorkUnit v0.2`;
2. one worker `ResultManifest v0.1`;
3. a candidate patch referenced by that ResultManifest;
4. a verifier-owned **`EvaluatorPlan v0.2`** that is bound to the exact WorkUnit/source and is not supplied to the worker.

It emits:

- `VerificationResult v0.1`;
- independent evidence files for each evaluator check.

It never merges, pushes, or declares itself the final integration authority.

## One evaluator-control lineage

IDKMesh already accepted Evaluator Sovereignty and `EvaluatorPlan v0.1` for metadata-only verification. This patch evaluator therefore extends that lineage rather than defining a second `VerifierPlan` protocol.

```text
EvaluatorPlan v0.1
  execution_mode = metadata_only
  deterministic JSON/data checks

EvaluatorPlan v0.2
  execution_mode = repository_patch
  exact WorkUnit/source binding
  patch/scope checks
  verifier-owned hidden container checks
```

Schema:

`schemas/evaluator-plan-v0.2.schema.json`

The v0.2 plan repeats the accepted exact binding:

```text
work_unit_id
work_unit_version
work_unit_digest
source_revision
```

The evaluator refuses binding drift before executing hidden checks.

## Hidden-check boundary

Hidden tests are not useful if the worker receives their implementation as part of the WorkUnit.

The WorkUnit still declares required validator IDs/evidence. The hidden EvaluatorPlan decides how those requirements are implemented and must exactly declare the required/requested validator set.

```text
WorkUnit: required validator = hidden-tests
worker: knows hidden-tests evidence is required

EvaluatorPlan: exact hidden command / fixture / evaluator implementation
worker: does NOT receive this plan
```

Duplicate check IDs are rejected. A plan cannot silently overwrite an earlier check/evidence record by reusing an ID.

## Trust pipeline

```text
WorkUnit v0.2
   -> worker
   -> ResultManifest v0.1 + candidate patch
   -> EvaluatorPlan v0.2 + repository-patch evaluator
   -> VerificationResult v0.1 + evidence
   -> human/governance/policy decision
```

`accept_candidate` remains decision support only. The evaluator has no merge authority.

## Relationship to the safe deterministic verifier

Use the lowest-risk evaluator that can answer the question:

```text
isolated data/JSON candidate
    -> experiments/local_verifier.py
       EvaluatorPlan v0.1 / metadata-only
       no candidate code execution

bounded repository patch requiring build/test/lint/security checks
    -> verifier/ idkmesh-verify
       EvaluatorPlan v0.2 / repository-patch
       fresh source + verifier-owned sandbox commands
```

## MVP safety profile

The patch evaluator intentionally accepts only:

- low-risk WorkUnits;
- public data;
- `sandbox_required = true`;
- no WorkUnit secrets;
- a full immutable 40-character Git source revision;
- public HTTPS GitHub source repositories;
- patch candidate artifacts;
- exact EvaluatorPlan-to-WorkUnit/source binding;
- independent verifier identity distinct from worker identity;
- a small evaluator container-image allowlist.

Hidden commands use Docker with:

- network disabled;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID/CPU/memory limits;
- no Docker socket/home/credential mounts;
- a temporary evaluator-controlled candidate workspace.

Docker remains an MVP boundary, not sufficient containment for arbitrary hostile Internet workloads.

## Check isolation

The patched candidate used for scope/integrity measurement is kept as a base evaluator workspace.

Every `container_command` receives a **fresh disposable copy** of that patched workspace:

```text
base patched candidate
  -> copy A -> hidden check A -> discard
  -> copy B -> hidden check B -> discard
  -> copy C -> hidden check C -> discard
```

A hidden test/build command may create local build artifacts in its own copy, but it cannot contaminate the candidate seen by later checks or rewrite the base scope/integrity measurement.

This is required by `EvaluatorPlan v0.2.policy.fresh_workspace_per_container_check = true`.

## Built-in evaluator check modes

An EvaluatorPlan may combine:

- `result_schema` — ResultManifest schema plus exact WorkUnit/EvaluatorPlan lineage;
- `artifact_integrity` — candidate artifact SHA-256 and clean patch application;
- `scope_policy` — changed paths obey WorkUnit allowed/write/forbidden scope;
- `container_command` — verifier-owned hidden test/lint/security command executed independently in network-disabled Docker.

Every check writes an evidence file whose digest is recorded in `VerificationResult.evidence`.

## Install and test

```bash
python -m pip install -e verifier
PYTHONPATH=verifier/src python -m unittest discover -s verifier/tests -v
```

Unit tests mock Docker/Git candidate execution; controlled real Docker acceptance remains a separate gate.

## Example EvaluatorPlan v0.2 shape

```json
{
  "schema_version": "0.2",
  "id": "evaluator/repository-patch-example",
  "binding": {
    "work_unit_id": "example/work-unit",
    "work_unit_version": 2,
    "work_unit_digest": "sha256:<exact-work-unit-digest>",
    "source_revision": "<full-40-character-git-sha>"
  },
  "visibility": "hidden",
  "execution_mode": "repository_patch",
  "verifier": {
    "id": "independent-verifier",
    "type": "system",
    "adapter": "docker-hidden-checks",
    "adapter_version": "0.2"
  },
  "required_validator_ids": [
    "artifact-integrity",
    "hidden-tests",
    "schema",
    "scope-policy"
  ],
  "source_input_id": "source-repository",
  "candidate_artifact_id": "candidate-patch",
  "container_image": "python:3.12-alpine",
  "checks": [
    {
      "id": "schema",
      "type": "schema",
      "required": true,
      "mode": "result_schema"
    },
    {
      "id": "artifact-integrity",
      "type": "policy",
      "required": true,
      "mode": "artifact_integrity"
    },
    {
      "id": "scope-policy",
      "type": "policy",
      "required": true,
      "mode": "scope_policy"
    },
    {
      "id": "hidden-tests",
      "type": "test",
      "required": true,
      "mode": "container_command",
      "command": ["python", "-m", "pytest", "-q", "hidden_tests/"],
      "timeout_seconds": 300
    }
  ],
  "policy": {
    "require_plan_outside_candidate_root": true,
    "require_output_outside_candidate_root": true,
    "require_verifier_distinct_from_worker": true,
    "fresh_workspace_per_container_check": true
  }
}
```

The actual hidden plan must be provisioned so candidate workers cannot inspect it.

## Run

```bash
idkmesh-verify \
  --work-unit ./work-unit.json \
  --result-manifest ./worker-output/result-manifest.json \
  --plan ./private/evaluator-plan-v0.2.json \
  --artifact-root ./worker-output \
  --output ./verification-output
```

Output:

```text
verification-output/
  verification-result.json
  evidence/
    <check>-evidence.txt
```

## Current limitations / remaining acceptance work

This branch still does **not** provide final maturity evidence for repository-patch execution. Before merge/readiness it still needs:

- synchronization with current `main` and green contract/unit CI;
- controlled real Docker acceptance for this evaluator tier;
- immutable evaluator container-image runtime provenance comparable to the hardened node path;
- a bounded whole-evaluation time/resource policy;
- stronger source/Git configuration isolation where verifier-host Git reconstructs untrusted repositories;
- benchmark corpus work required by issue #5;
- richer dependency/security/fuzz/property checks.

It also deliberately does not provide:

- remote verifier execution;
- signatures/attestations;
- multi-verifier quorum aggregation;
- final merge/integration authority.

The safer `experiments/local_verifier.py` path should remain preferred whenever candidate-code execution is unnecessary.
