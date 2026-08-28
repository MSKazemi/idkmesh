# `idkmesh-node` canonical local worker

`idkmesh-node` is the first bounded execution backend for IDKMesh. It executes **one canonical IDKMesh WorkUnit v0.2** in a disposable local Docker container and emits the canonical **worker ResultManifest v0.1** containing an unverified candidate artifact.

It does not define its own Work Unit protocol, accept remote shell commands, act as a public self-hosted GitHub runner, or decide that its own output is correct.

## Contract boundary

The shared contracts remain authoritative:

- `schemas/work-unit-v0.2.schema.json`
- `schemas/result-manifest-v0.1.schema.json`

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

`source_input_id` must identify a canonical Work Unit input of type `git_ref`. For node v0.1, its locator must be a public `https://github.com/owner/repo` URL. The immutable Git commit is stored separately as `source_revision` in the execution binding; canonical artifact `digest` fields remain content SHA-256 values and are not overloaded as Git revision identifiers.

See `node/examples/work-unit.canonical-smoke.json`.

## WorkUnit v0.2 policy enforcement

The worker now checks the v0.2 scheduling/trust contract before execution:

- all `requirements.capabilities` must be provided by the execution binding;
- configured CPU and memory must satisfy the Work Unit minimums;
- GPU-required work is rejected by the current CPU-only profile;
- only `security.risk_class = low` is accepted by this Docker MVP;
- only public data is accepted;
- the current profile satisfies only `minimum_worker_trust = untrusted`;
- independent verification must be required and at least one independent verifier must be requested.

These restrictions are deliberately conservative. Stronger isolation/identity profiles can widen the accepted risk/trust classes later without changing the core Work Unit.

## Safety envelope

Node v0.1 requires and enforces:

- immutable full Git commit revision;
- public HTTPS GitHub source;
- small container-image allowlist;
- `permissions.network = none`;
- no Work Unit secrets;
- Docker `--network none`;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- CPU, memory, PID, and wall-time limits;
- no host home directory, credentials, or Docker socket mounted into the task;
- repository path policy checked against both `constraints.allowed_paths` and `permissions.filesystem_write`;
- `constraints.forbidden_paths` rejection;
- result output remains an **unverified candidate** requiring independent verification.

The writable repository workspace is temporary. Path policy in this version is checked after execution; therefore Docker is still only an MVP isolation boundary, not sufficient containment for arbitrary hostile Internet workloads.

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

On an explicitly controlled machine with Git and Docker:

```bash
idkmesh-node run node/examples/work-unit.canonical-smoke.json --output ./node-result
```

The output directory must be empty. It receives:

- `result-manifest.json` — canonical worker ResultManifest v0.1;
- `changes.patch` — bounded tracked-file candidate patch;
- `stdout.txt`;
- `stderr.txt`.

The ResultManifest contains artifact digests, immutable source revision, Work Unit digest, worker configuration digest, resource measurements, changed paths, policy violations, and a request for the Work Unit's required independent validators.

## Trust rule

A successful process exit is **not** acceptance.

```text
canonical Work Unit
      -> idkmesh-node
      -> ResultManifest + candidate patch
      -> independent verifier(s)
      -> evidence / verdict
      -> human or governance decision
```

The node intentionally has no merge/push authority.

## Next engineering step

The next layer should be an independent verifier/evidence contract and a local orchestration path that can execute a Work Unit, invoke a separate verifier, and retain both worker and verifier provenance without allowing the generator to certify itself.
