# Local Agent Execution Boundary v0.1

**Status:** experimental implementation contract  
**Date:** 2026-09-23  
**Owner:** C4 local agent runner (#577)  
**Sandbox backend:** #804

## Purpose

This contract defines the boundary between provider-neutral local-agent
orchestration and a platform-specific hostile-process sandbox.

It deliberately separates three layers:

```text
WorkUnit + AgentPreset
        |
        v
admission / policy checks
        |
        v
LocalSandboxExecutor  <-- platform-specific enforcement
        |
        v
untrusted worker process
        |
        v
outside-authority candidate/log capture
        |
        v
CandidateReference -> ResultManifest -> independent verification
```

The raw `run_bounded_process()` helper remains an execution-neutral primitive.
It is not a valid implementation of `LocalSandboxExecutor`.

## Required inputs

### WorkUnit v0.2

The orchestration path requires:

- non-empty `objective`;
- `security.sandbox_required = true`;
- `permissions.process_execution = true`;
- `permissions.secrets = []`;
- `permissions.network` equal to `none` or `allowlist`;
- positive `budget.wall_seconds`;
- non-empty `constraints.allowed_paths`;
- explicit `constraints.forbidden_paths` array;
- resource requirements compatible with configured sandbox memory/disk limits.

`objective` is the canonical task text. Alternate ad-hoc fields such as
`prompt`, `goal`, or issue title are not execution authority.

### AgentPreset

The preset owns executable, fixed argv, prompt transport, model/execution
connection references, environment allowlist, network policy, and candidate-only
authority.

Issue or WorkUnit text cannot choose an executable or shell.

### SandboxLimits

Every run supplies positive ceilings for:

- wall seconds;
- CPU seconds;
- memory MiB;
- writable disk MiB;
- process count;
- retained stdout/stderr bytes;
- stdin bytes;
- candidate patch bytes.

A production backend may enforce stricter values but not weaker ones.

## SandboxCapabilities and SandboxPolicy

Before execution, the orchestrator requires the backend to attest all of:

- `network_enforcement`;
- `process_tree_isolation`;
- `cpu_limit`;
- `memory_limit`;
- `disk_limit`;
- `process_limit`;
- `filesystem_isolation`;
- `writable_path_enforcement`;
- `credential_isolation`.

A missing capability is a hard error.

Capability flags alone are not enough to execute a worker. Each call also passes
an immutable `SandboxPolicy` containing:

- `network_mode`;
- exact `network_allowlist` destinations;
- exact WorkUnit `writable_paths`;
- exact WorkUnit `forbidden_paths`.

The production backend is responsible for enforcing those values, not merely
reporting them after execution. In the initial profile,
`permissions.filesystem_write` must exactly equal
`constraints.allowed_paths`; this intentionally avoids ambiguous competing
write-scope declarations.

## Network mapping

Initial v0.1 policy is intentionally narrow:

| WorkUnit | Preset | Extra trusted input | SandboxPolicy | Outcome |
| --- | --- | --- | --- | --- |
| `none` | `disabled` | none | `disabled` | admissible |
| `allowlist` | `allowlisted` | none | exact WorkUnit allowlist | admissible |
| `allowlist` | `model_only` | connection-derived model destinations | exact WorkUnit allowlist | admissible only when WorkUnit destinations are a subset of trusted model destinations |
| `allowlist` | `model_only` | missing | — | rejected |
| `unrestricted` | any | any | — | rejected |
| mismatch | any | any | — | rejected |

A `model_only` preset therefore cannot turn task-authored hostnames into network
authority. A trusted model/connection layer must resolve permitted destinations
first, and the runner verifies the WorkUnit allowlist does not exceed them.

The sandbox backend owns actual packet/namespace/firewall enforcement. A string
claim without enforcement evidence is insufficient for production acceptance.

## Environment and credentials

The local-agent path never inherits the host environment implicitly.

Only names already approved by `AgentPreset.env_allowlist` may be copied from
an explicit caller-supplied environment mapping. The preset contract already
forbids common GitHub/SSH/cloud/Docker credentials and secret-like suffixes.

Docker socket authority is rejected even if smuggled through another allowed
environment variable value.

## Prompt transport

- `stdin`: supported.
- `argument`: supported; the maintainer-owned prompt flag remains in AgentPreset.
- `file`: rejected until a sandbox backend provides an isolated input mount
  outside the candidate filesystem.

## Candidate scope

After worker termination, the orchestrator asks Git for the complete changed path
set, including untracked files. Each changed path must:

1. not match any WorkUnit forbidden-path pattern;
2. match at least one allowed-path pattern.

Matching follows verifier-style `fnmatchcase` glob semantics, with literal
directory entries also matching descendants.

A scope violation rejects the candidate rather than silently dropping the
unauthorized change.

## Artifact capture

Patch and logs are generated/read by the orchestrator after sandbox execution.

Requirements:

- artifact root must be outside the canonical repository;
- artifact root must be outside the disposable worker workspace;
- patch capture is byte-bounded;
- untracked files are included;
- artifact files are content-addressed through `LocalArtifactBundleReader`;
- ResultManifest receives the provider-neutral CandidateReference;
- observed tool versions are omitted unless actually measured.

The first implementation emits one bounded unified-diff candidate plus bounded
stdout/stderr log files.

## Process-tree hardening

The raw execution-neutral helper starts a new POSIX session and now performs
best-effort process-group cleanup on **every** exit, not only timeout. This
prevents a normally exiting parent with a background child inheriting output
pipes from hanging the reader threads.

This hardening does not upgrade the raw helper into a sandbox.

## Failure semantics

All admission, sandbox capability, scope, artifact-bound, and provenance
violations fail closed. A failed attempt never receives verification or merge
authority by implication.

## Non-goals for v0.1

- choosing a production sandbox technology;
- running goose/Gemini/mini-SWE-agent on the host without #804;
- unrestricted network;
- secret materialization;
- candidate verification;
- merge/push authority.
