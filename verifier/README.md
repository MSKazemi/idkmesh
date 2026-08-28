# `idkmesh-verify` repository-patch verifier v0.1

`idkmesh-verify` extends the already-merged zero-cost deterministic verifier MVP in `experiments/local_verifier.py` from isolated JSON candidates to **bounded repository patch candidates** that may require independent hidden regression/lint/security commands.

The existing safe baseline (#72) remains important because it proves independent evidence without executing candidate code. This package implements the next Phase A extension described by that baseline: pinned source reconstruction, patch integrity/application, repository scope enforcement, and optional verifier-owned commands in a separate sandbox.

It consumes:

1. one canonical `WorkUnit v0.2`;
2. one worker `ResultManifest v0.1`;
3. a candidate patch referenced by that ResultManifest;
4. a **trusted verifier-side plan** that is not supplied to the worker.

It emits:

- `VerificationResult v0.1`;
- independent evidence files for each check.

It never merges, pushes, or declares itself the final integration authority.

## Relationship to the safe deterministic verifier

Use the lowest-risk verifier that can answer the correctness question.

```text
isolated data/JSON candidate
    -> experiments/local_verifier.py
       (no candidate code execution)

bounded repository patch requiring build/test/lint/security checks
    -> verifier/ idkmesh-verify
       (fresh immutable checkout + verifier-owned sandbox commands)
```

The patch verifier should not replace the safer deterministic path for tasks that do not need code execution.

## Why the verifier plan is separate

Hidden tests are not useful if the worker receives them as part of the WorkUnit.

Therefore verifier-specific execution configuration lives in:

`schemas/verifier-plan-v0.1.schema.json`

The WorkUnit still declares which validator IDs and evidence are required. The private verifier plan decides how those checks are implemented.

```text
WorkUnit says: required validator = hidden-tests
worker sees that requirement

VerifierPlan says: exact hidden command/fixture
worker does NOT receive this file
```

The verifier refuses a plan that omits a required WorkUnit validator or a validator requested in the worker ResultManifest.

## Trust pipeline

```text
WorkUnit v0.2
   -> worker
   -> ResultManifest v0.1 + candidate patch
   -> independent verifier plan/runtime
   -> VerificationResult v0.1 + evidence
   -> human/governance/policy decision
```

`accept_candidate` is decision support only. The verifier has no merge authority.

## MVP safety profile

Patch verifier v0.1 intentionally accepts only:

- low-risk WorkUnits;
- public data;
- `sandbox_required = true`;
- no WorkUnit secrets;
- a full immutable 40-character Git source revision in worker provenance;
- public HTTPS GitHub source repositories;
- patch candidate artifacts;
- independent verifier identity distinct from worker identity;
- a small container image allowlist.

Hidden/container checks execute inside Docker with:

- network disabled;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID/CPU/memory limits;
- no Docker socket/home/credential mounts;
- a temporary candidate workspace.

The temporary candidate checkout is writable because many test/build commands need local files. It is discarded after verification.

Docker remains an MVP boundary, not a sufficient final sandbox for arbitrary hostile Internet workloads.

## Built-in verifier check modes

A verifier plan can combine:

- `result_schema` — worker ResultManifest schema and exact WorkUnit lineage were validated;
- `artifact_integrity` — candidate artifact SHA-256 and clean patch application;
- `scope_policy` — changed paths obey WorkUnit allowed/write/forbidden scope;
- `container_command` — trusted hidden test/lint/security command executed independently in network-disabled Docker.

Every check writes an evidence file whose digest is recorded in `VerificationResult.evidence`.

## Install

```bash
python -m pip install -e verifier
```

## Unit tests

The unit tests mock Docker/Git execution and therefore do not execute candidate code:

```bash
PYTHONPATH=verifier/src python -m unittest discover -s verifier/tests -v
```

## Example verifier plan shape

```json
{
  "schema_version": "0.1",
  "id": "verifier/example",
  "verifier": {
    "id": "independent-verifier",
    "adapter": "docker-hidden-checks",
    "adapter_version": "0.1"
  },
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
  ]
}
```

The actual hidden plan should be stored/provisioned so candidate workers cannot inspect it.

## Run

```bash
idkmesh-verify \
  --work-unit ./work-unit.json \
  --result-manifest ./worker-output/result-manifest.json \
  --plan ./private/verifier-plan.json \
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

## Important limitations

v0.1 does **not** yet provide:

- remote verifier execution;
- signatures/attestations;
- multi-verifier quorum aggregation;
- strong microVM sandboxing;
- benchmark task corpus;
- final merge/integration authority.

It also deliberately executes verifier-owned commands only for bounded low-risk public patch candidates. The safer deterministic `experiments/local_verifier.py` path should remain preferred whenever candidate-code execution is unnecessary.

This extension should be described as realistically validated only after a controlled Docker acceptance run is recorded.
