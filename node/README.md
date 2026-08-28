# `idkmesh-node` canonical local worker

`idkmesh-node` is the first bounded execution backend for IDKMesh. It executes **one canonical IDKMesh WorkUnit v0.2** in a disposable local Docker container and emits the canonical **worker ResultManifest v0.1** containing an unverified candidate artifact.

It does not define its own Work Unit protocol, accept remote shell commands, act as a public self-hosted GitHub runner, or decide that its own output is correct.

## Contract boundary

The shared contracts remain authoritative:

- `schemas/work-unit-v0.2.schema.json`
- `schemas/result-manifest-v0.1.schema.json`
- `schemas/verification-result-v0.1.schema.json`

Execution-only details live in:

- `schemas/node-execution-binding-v0.1.schema.json`

A Work Unit opts into this backend through the namespaced extension:

```json
"extensions": {
  "org.idkmesh.node.execution": {
    "schema_version": "0.1",
    "source_input_id": "source-repository",
    "source_revision": "<full-40-character-git-commit>",
    "capabilities": ["git", "container-execution", "python"],
    "container": {
      "image": "python:3.12-alpine",
      "command": ["python", "-c", "..."]
    },
    "limits": {
      "timeout_seconds": 30,
      "cpus": 1.0,
      "memory_mb": 256,
      "pids_limit": 64
    },
    "output_limits": {
      "max_patch_bytes": 1000000,
      "max_log_bytes": 262144
    }
  }
}
```

`source_input_id` must identify a canonical Work Unit input of type `git_ref`. For node v0.1, its locator must be a public `https://github.com/owner/repo` URL. The immutable Git commit is stored separately as `source_revision` in the execution binding; canonical artifact `digest` fields remain content SHA-256 values and are not overloaded as Git revision identifiers. The binding revision must match `provenance.source_revision` so execution and canonical provenance cannot silently point at different commits.

See `node/examples/work-unit.canonical-smoke.json`.

## WorkUnit v0.2 policy enforcement

The worker checks the v0.2 scheduling/trust/budget contract before execution:

- all `requirements.capabilities` must be provided by the execution binding;
- configured CPU and memory must satisfy the Work Unit minimums;
- GPU-required work is rejected by the current CPU-only profile;
- only `security.risk_class = low` is accepted by this Docker MVP;
- only public data is accepted;
- the current profile satisfies only `minimum_worker_trust = untrusted`;
- independent verification must be required and at least one independent verifier must be requested;
- `budget.wall_seconds` must be positive and is treated as a whole-attempt deadline;
- `budget.project_spend_usd_max` must be `0`;
- `budget.paid_fallback_allowed` must be `false`.

The monetary checks mirror the repository-wide `config/compute-policy.json`: IDKMesh itself cannot pay for compute. Local-owned, donated, public-project CI, grants, and explicit free-tier resources can be modeled separately, but a Work Unit routed to this backend cannot silently authorize paid fallback.

The whole-attempt deadline covers local image resolution, source preparation, and task-container execution. Post-run capture records a policy failure if total measured attempt time still exceeds the Work Unit wall budget.

These restrictions are deliberately conservative. Stronger isolation/identity profiles can widen the accepted risk/trust classes later without changing the core Work Unit.

## Safety envelope

Node v0.1 requires and enforces:

- immutable full Git commit revision with matching canonical provenance;
- public HTTPS GitHub source;
- small container-image allowlist;
- the allowlisted image must already be present on the controlled host;
- the image tag is resolved to an immutable local Docker image ID before execution, and the container runs by that ID;
- `permissions.network = none`;
- no Work Unit secrets;
- Docker `--network none`;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- CPU, memory, PID, and whole-attempt wall-time limits;
- no host home directory, credentials, or Docker socket mounted into the task;
- trusted Git metadata stored outside the task-writable workspace and mounted read-only for task-side Git reads;
- host Git result capture isolated from inherited/global/system Git configuration;
- repository path policy checked against both `constraints.allowed_paths` and `permissions.filesystem_write`;
- `constraints.forbidden_paths` rejection;
- zero project spend / no paid fallback;
- result output remains an **unverified candidate** requiring independent verification.

The writable repository work tree is temporary. Path policy in this version is checked after execution; therefore Docker is still only an MVP isolation boundary, not sufficient containment for arbitrary hostile Internet workloads.

### Git-metadata integrity rule

The task must not control the Git metadata later used to measure its output. Node v0.1 therefore keeps the real Git directory outside `/workspace`, mounts it read-only at `/git-meta`, uses an isolated host Git configuration, and detects tampering with the task-visible `.git` pointer.

This prevents a task from committing/repointing its own changes and then using candidate-controlled Git state to make host-side `git diff` or path-policy evidence disappear.

### Untracked-artifact rule

Node v0.1 packages a bounded tracked-file Git patch. It does **not** yet package arbitrary untracked files. Therefore any untracked file produced by the task is treated as a policy failure and the worker ResultManifest is marked failed.

Ignored files are still observed as task outputs; `.gitignore` does not make an untracked artifact disappear from evidence.

This is deliberately fail-closed. A future protocol may add explicit typed/size-bounded untracked artifact packaging, but the current worker must never report success while silently omitting candidate output.

### Candidate-patch size rule

`changes.patch` is the canonical candidate artifact for node v0.1. If the tracked diff exceeds `output_limits.max_patch_bytes`, the file is truncated only as diagnostic evidence and the attempt **fails**. A truncated candidate artifact can never accompany `status: succeeded`.

Stdout/stderr may be deliberately truncated to their declared log bound; those truncation flags remain visible in metrics.

### Container-image evidence rule

The Work Unit's allowlisted tag is a routing/configuration selector, not sufficient runtime provenance by itself. Before execution, the worker resolves the preloaded tag with Docker and obtains an immutable local image ID (`sha256:...`). Docker is then invoked with that image ID, and the ID is recorded under `extensions.org.idkmesh.node.v0_1.container_image_id`.

A controlled acceptance report should retain both the configured tag and resolved image ID. A later contract version may move immutable image identity directly into the execution binding.

## Install and test

From the repository root:

```bash
python -m pip install -e node
python -m unittest discover -s node/tests -v
```

Validate the checked-in canonical Work Unit:

```bash
idkmesh-node validate node/examples/work-unit.canonical-smoke.json
```

## Execute one Work Unit

On an explicitly controlled machine with Git and Docker, preload the allowlisted image first:

```bash
docker pull python:3.12-alpine
docker image inspect --format '{{.Id}}' python:3.12-alpine
idkmesh-node run node/examples/work-unit.canonical-smoke.json --output ./node-result
```

The node does not perform an implicit image pull during task execution. This keeps image acquisition outside the Work Unit's task authority and lets the acceptance record bind the run to the exact local image ID.

The output directory must be empty. It receives:

- `result-manifest.json` — canonical worker ResultManifest v0.1;
- `changes.patch` — bounded tracked-file candidate patch;
- `stdout.txt`;
- `stderr.txt`.

The ResultManifest contains artifact digests, immutable source revision, Work Unit digest, worker configuration digest, resource measurements, changed paths, untracked-path accounting, policy violations, the resolved container image ID, and a request for the Work Unit's required independent validators.

## Trust rule

A successful process exit is **not** acceptance.

```text
canonical WorkUnit v0.2
      -> idkmesh-node
      -> ResultManifest v0.1 + candidate patch
      -> independent verifier / EvaluatorPlan
      -> VerificationResult v0.1 + evidence
      -> human or governance integration decision
```

The node intentionally has no merge/push authority.

## Relationship to current `main`

The repository already contains two important downstream pieces:

- a zero-cost independent verifier that emits provenance-bound `VerificationResult v0.1`;
- a deterministic two-attempt orchestration kernel that demonstrates worker-attempt isolation and independent verification routing.

This worker therefore fills the missing **real execution backend** between canonical Work Units and those verification/orchestration layers.

## Next engineering milestone

The next milestone is one controlled end-to-end acceptance run:

```text
WorkUnit v0.2
 -> real local Docker worker
 -> ResultManifest v0.1
 -> independent verifier with evaluator-owned checks
 -> VerificationResult v0.1
 -> retained evidence/provenance
 -> human integration decision
```

That run should use an immutable IDKMesh source commit, record the exact Docker image ID, stay at zero project spend, preserve evaluator sovereignty, and demonstrate that a generated candidate cannot certify itself.

Only after that evidence should the project connect `idkmesh-node` as a concrete adapter behind the multi-attempt orchestration kernel or widen the worker's risk/trust envelope.
