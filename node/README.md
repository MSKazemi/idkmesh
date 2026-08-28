# `idkmesh-node` v0.1

`idkmesh-node` is the first local execution backend for the **canonical IDKMesh Work Unit v0.1**.

It executes one bounded Work Unit in a disposable Docker container and emits the canonical **worker ResultManifest v0.1** plus logs and a candidate patch.

It is intentionally **not**:

- a public self-hosted GitHub runner;
- a remote shell;
- a scheduler;
- a verifier;
- an autonomous merger.

## Contract model

The Work Unit remains transport/runtime neutral. Docker-specific settings live under the namespaced extension:

```text
extensions.org.idkmesh.execution.docker
```

The canonical Work Unit still owns:

- objective;
- inputs/outputs;
- allowed and forbidden paths;
- permissions;
- validators;
- evidence requirements;
- budgets;
- provenance;
- failure semantics.

The local runtime requires exactly one `git_ref` input. Its locator is an HTTPS public GitHub repository and its digest is an immutable full commit SHA written as:

```text
git:<40-character-sha>
```

This structure lets future local, A2A, MCP, OpenHands, mini-SWE-agent, or other adapters share the same Work Contract.

## Safety defaults

The Docker backend requires:

- `permissions.network = none`;
- no Work Unit secrets;
- `process_execution = true`;
- an immutable source commit;
- a hard-coded container-image allowlist;
- Docker network mode `none`;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID, CPU, memory, and wall-time limits;
- no host home directory, SSH keys, cloud credentials, or Docker socket mounted;
- post-execution path-policy checks against `constraints.allowed_paths` and `constraints.forbidden_paths`.

Docker is an MVP boundary, not a sufficient final isolation mechanism for arbitrary hostile Internet workloads. Stronger backends such as rootless containers, gVisor, or microVMs remain future work.

## Important trust rule

A process exit code of zero does **not** mean accepted.

The worker emits:

```text
ResultManifest.status = succeeded | failed | timeout | ...
```

and requests independent validation through `verification_request`. A separate verifier/evidence policy must decide whether the candidate deserves integration.

If the sandbox modifies a forbidden path or a path outside the Work Unit's allowed scope, the worker result is marked `failed` even when the command exits successfully.

## Requirements

- Python 3.11+
- Git
- Docker

Install from the repository checkout:

```bash
python -m pip install -e ./node
```

## Run unit tests

```bash
PYTHONPATH=node/src python -m unittest discover -s node/tests -v
```

The unit tests do not require Docker. They test schema binding, sandbox command policy, path-policy enforcement, and canonical ResultManifest generation using mocks.

## Validate the checked-in Work Unit

```bash
PYTHONPATH=node/src python -m idkmesh_node validate \
  node/examples/canonical-doc-probe.work-unit.json
```

## Run the local acceptance probe

On a machine with Docker:

```bash
PYTHONPATH=node/src python -m idkmesh_node run \
  node/examples/canonical-doc-probe.work-unit.json \
  --output ./node-result
```

The output directory contains:

- `result-manifest.json` — schema-valid worker self-report;
- `changes.patch` — bounded unverified candidate patch;
- `stdout.txt`;
- `stderr.txt`.

The checked-in example creates a disposable documentation candidate under `docs/`; it does not modify the canonical checkout.

## Interoperability

See [`../docs/interoperability/A2A_MCP_MAPPING_V0_1.md`](../docs/interoperability/A2A_MCP_MAPPING_V0_1.md).

The design target is:

```text
one canonical Work Contract
        |
        +-- local Docker worker
        +-- future mini-SWE-agent adapter
        +-- future OpenHands adapter
        +-- A2A binding
        +-- MCP binding
```

Adapters execute work. IDKMesh verification decides trust.
