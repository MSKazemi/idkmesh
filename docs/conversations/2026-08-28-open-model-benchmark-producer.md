# Open-weight benchmark producer experiment — 2026-08-28

## User direction

Continue improving `MSKazemi/idkmesh` after the pull-request convergence pass, while keeping substantive project work in the public repository.

## Repository state observed

The repository had already advanced beyond the earlier planning snapshot:

- the Phase B2 first-five benchmark definition was already frozen on `main`;
- all five benchmark task evidence slots were still `pending`;
- the benchmark contract workflow intentionally validated definitions only and executed no candidate code;
- PR #91 remained separately human-review gated and therefore was not used as an implicit authority shortcut;
- the canonical coordinator already had an execution-neutral `WorkerAdapter` / result-bundle boundary;
- a concurrent commit on `main` fixed the task-001 repository-path bug, but benchmark outcome evidence remained explicitly separate.

The frozen benchmark source remains `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`. Any candidate-generation experiment must use that snapshot rather than exposing later solutions to the producer.

## Important capability distinction

The accepted PR #91 node is an execution sandbox, not a goal-to-code reasoning engine. Its demonstrated smoke WorkUnit contains an explicit `org.idkmesh.node.execution` container command. The frozen benchmark WorkUnits contain coding objectives and constraints but deliberately do not contain such commands.

Therefore directly feeding the benchmark tasks to #91 would misrepresent what the node does. The missing experimental capability is a goal-level candidate producer that can emit a canonical candidate bundle for the existing verifier/coordinator path.

## External resource finding

A previously attractive option, GitHub Models, cannot be used: GitHub's current documentation says the GitHub Models playground/catalog/inference API were fully retired on 2026-07-30.

GitHub documentation also states that standard GitHub-hosted runners are free for public repositories. The experiment therefore uses only a standard public-repository runner and requests no larger runner, paid inference API, model secret, artifact upload, or cache.

References:

- https://docs.github.com/en/github-models
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-actions

GitHub Copilot cloud agents were not selected for this experiment because current documentation describes them as a paid-Copilot capability that consumes AI credits. The goal here is to preserve the repository's zero-project-spend experiment boundary.

## Selected first producer

The smallest probe uses:

- model: `Qwen/Qwen2.5-Coder-0.5B-Instruct`;
- model revision: `bbf27711794f58ebd1796058f4280b53c32e19fc`;
- published license: Apache-2.0;
- deterministic decoding: `do_sample=false`, seed `0`;
- one frozen benchmark item: task `001-cohort-path-boundary`;
- structural signature: `single-worker-baseline-v1`.

Model reference:

- https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct

This first 0.5B model is intentionally weak enough to make failure plausible. The experiment should be able to discover that a small/free producer is not useful; a negative result is evidence rather than a reason to weaken the benchmark.

## Anti-leakage design

The model must not see the already-landed solution or evaluator-owned semantic expectation.

The inference container receives only:

1. the frozen WorkUnit objective/context;
2. the frozen allowed target-file text.

It does **not** receive:

- the current `main` checkout;
- the evaluator plan;
- GitHub credentials or `GITHUB_TOKEN`;
- repository secrets;
- the later task-001 fix.

## Runtime boundary

Provisioning and candidate generation are separated.

During trusted provisioning, the workflow may use network access to install pinned Python packages and fetch the pinned public model snapshot. Candidate inference then runs in a separate Docker container with:

- network `none`;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID/CPU/RAM bounds;
- non-root UID;
- no source-repository mount;
- no evaluator mount;
- no credentials/secrets.

Model output is untrusted text. The host harness accepts only one textual Git diff for the exact WorkUnit allowed path, applies it only to a disposable checkout of the immutable source revision, normalizes the resulting patch with Git, and never executes candidate code.

## Evidence path

If the producer emits a usable patch:

```text
frozen WorkUnit
 -> isolated open-weight model text generation
 -> bounded normalized candidate patch
 -> ResultManifest v0.1 (worker self-report only)
 -> frozen public EvaluatorPlan v0.2
 -> independent metadata-only unified-diff verifier
 -> VerificationResult v0.1
 -> probe evidence
```

If the model emits malformed or out-of-scope output, that is recorded as `producer_output_rejected`. If the independent verifier rejects a structurally valid candidate, that is recorded as a real rejection. Neither case is converted into CI harness failure merely to manufacture a green model result.

Harness/invariant errors remain CI failures.

## Authority invariant

The experiment has no authority to:

- modify canonical state from the workflow;
- push;
- merge;
- approve;
- select a winning candidate automatically.

`human_integration_decision_required` remains true.

The workflow uploads no artifact and uses no Actions cache. Concise evidence is written to the job summary/logs. This first probe does **not** change the frozen cohort evidence fields. Attaching evidence is a separate step after the run is inspected and provenance/reproducibility are adequate.

## Decision

Use one bounded, zero-secret, open-weight producer probe to test whether free public-repository compute can create a real goal-level coding candidate while preserving IDKMesh's existing WorkUnit -> ResultManifest -> EvaluatorPlan -> VerificationResult trust chain.

Do not create a new task protocol, do not modify the frozen benchmark definition after observing the result, and do not bypass PR #91's separate human-review gate.
