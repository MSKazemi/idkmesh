# `idkmesh-node` MVP

This directory contains the first runnable IDKMesh volunteer worker prototype.

It deliberately does **one thing**: execute one locally supplied, bounded Work Unit in a disposable Docker container and emit an **untrusted candidate result bundle**. It is not a daemon, remote shell, public GitHub self-hosted runner, scheduler, or autonomous merger.

## Safety defaults

The MVP requires:

- a full 40-character Git commit SHA;
- an HTTPS public GitHub repository URL;
- a small hard-coded allowlist of container images;
- Docker network mode `none`;
- read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID, CPU, memory, and wall-time limits;
- only a temporary task workspace mounted writable;
- no host home directory, SSH keys, API tokens, cloud credentials, or Docker socket mounted into the task;
- no direct push or merge capability.

Docker is a useful MVP sandbox, **not a perfect security boundary** for hostile public workloads. A later volunteer network should evaluate stronger isolation such as rootless containers, gVisor, Firecracker/microVMs, dedicated low-trust worker accounts, and signed/approved Work Units.

## Requirements

- Python 3.11+
- Git
- Docker

## Run the tests

```bash
PYTHONPATH=node/src python -m unittest discover -s node/tests -v
```

## Validate a Work Unit

From the repository root:

```bash
PYTHONPATH=node/src python -m idkmesh_node validate node/examples/work-unit.validate-repo.json
```

The checked-in example intentionally contains a placeholder revision. Replace it with a full immutable Git commit SHA before validation/execution.

## Execute one Work Unit

```bash
PYTHONPATH=node/src python -m idkmesh_node run work-unit.json --output ./node-result
```

The output directory contains:

- `result.json` — provenance, limits, outcome, and trust state;
- `stdout.txt`;
- `stderr.txt`;
- `changes.patch` — tracked-file changes, bounded by the Work Unit output limit.

Untracked files are listed in `result.json` status but are not packaged in v0.1. This is intentional until the protocol has explicit artifact type/size policies.

## Work Unit v0.1 example

```json
{
  "version": "0.1",
  "id": "small-doc-fix",
  "source": {
    "repo_url": "https://github.com/MSKazemi/idkmesh",
    "revision": "0123456789abcdef0123456789abcdef01234567"
  },
  "execution": {
    "image": "python:3.12-alpine",
    "command": ["python", "tools/small_task.py"],
    "network": "none",
    "timeout_seconds": 300,
    "cpus": 1.0,
    "memory_mb": 1024,
    "pids_limit": 128
  },
  "output": {
    "max_patch_bytes": 1000000,
    "max_log_bytes": 262144
  }
}
```

## Next adapters

The next useful layer is an adapter interface so the same bounded Work Unit can be executed by deterministic commands, goose + Ollama, OpenHands, SWE-agent, or other providers without changing the trust/verification envelope.

See `docs/architecture/AGENT_NETWORK_AND_VOLUNTEER_NODES.md` and issue #11.
