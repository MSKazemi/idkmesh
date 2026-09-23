# ADR-0017 — Local Coding Agents Require an Enforced Sandbox Boundary

**Status:** Accepted for C4 implementation  
**Date:** 2026-09-23

## Context

IDKMesh now has three pieces needed for a local coding-agent path:

- maintainer-owned `AgentPreset` metadata;
- exact-SHA disposable Git workspaces;
- an execution-neutral bounded subprocess primitive.

Those pieces are useful foundations, but they do not make raw host process
execution a hostile-code sandbox. In particular, a coding agent may create child
processes, open network connections, consume CPU/RAM/disk/PIDs, inspect host
resources, or attempt to reach credentials and sockets that are outside the
candidate workspace.

The C4 product goal explicitly requires network policy, resource ceilings,
credential/socket isolation, candidate capture outside worker authority, and no
merge authority. Treating `sandbox_required=true` as documentation instead of
an enforced runtime precondition would turn a safety declaration into a false
claim.

## Decision

A local coding-agent preset may execute only through a `LocalSandboxExecutor`
that exposes an explicit `SandboxCapabilities` contract and satisfies every
required enforcement bit before the worker starts.

IDKMesh core intentionally provides **no raw-process fallback** for this path.

The local-agent orchestrator must fail closed unless the executor attests:

1. process-tree isolation and cleanup;
2. CPU limit enforcement;
3. memory limit enforcement;
4. writable-disk limit enforcement;
5. process/PID limit enforcement;
6. filesystem isolation;
7. credential isolation;
8. network enforcement compatible with both the WorkUnit permission and
   maintainer-owned AgentPreset.

The WorkUnit must also explicitly:

- require a sandbox;
- permit process execution;
- expose no secret permission on this first C4 path;
- use bounded, non-unrestricted network permission;
- provide a positive wall-time budget;
- provide a non-empty candidate path scope.

The sandbox interface is an authority boundary. A backend implementation is
responsible for proving that its capability claims are true; issue #804 owns the
first production backend and adversarial evidence.

## Candidate/evidence boundary

After the sandboxed worker exits and its process tree is contained, IDKMesh—not
the worker—captures the candidate and logs.

Candidate capture must:

- enumerate all changed paths;
- reject forbidden or out-of-scope changes;
- bound retained patch bytes;
- include untracked candidate files;
- write candidate/log artifacts outside both the worker workspace and canonical
  repository;
- content-address those files before ResultManifest normalization.

Prompt files may not be written into the candidate workspace unless a future
sandbox backend provides an isolated input mount that is excluded by
construction. Until then, file prompt transport fails closed.

## Authority invariant

```text
sandbox execution != candidate verification
worker success != verifier success
ResultManifest != acceptance
candidate capture != merge authority
```

No local-agent worker receives repository integration credentials or acceptance
authority.

## Consequences

### Positive

- `sandbox_required=true` becomes an enforceable precondition;
- provider-neutral orchestration can advance without pretending raw subprocesses
  are isolated;
- C4-D can be implemented/replaced independently behind a small interface;
- canonical WorkUnit objective/permissions constrain the run;
- candidate artifacts are durable and outside worker authority;
- later goose/Gemini/mini-SWE-agent adapters cannot bypass the same boundary.

### Costs

- no real local coding agent may run until a conforming sandbox backend exists;
- sandbox implementations need platform-specific work and adversarial tests;
- unrestricted network is deliberately unsupported in the initial C4 profile;
- file prompt transport is deferred until isolated input mounting exists.

## Alternatives considered

### Use `run_bounded_process` directly for coding agents

Rejected. Wall/output limits and a disposable worktree do not enforce network,
CPU/RAM/disk/PID, credential, or process-tree isolation.

### Treat sandbox capability flags as optional warnings

Rejected. That would make the safety declaration non-binding and allow callers
to silently downgrade the boundary.

### Make Docker the canonical sandbox

Deferred. Docker may be one backend, but granting the worker or orchestrator an
unconstrained Docker socket creates a stronger authority problem. The contract
should not couple C4 semantics to one runtime.

## Ownership

- #577 owns the C4 local-agent product exit gate.
- #804 owns the first real sandbox backend.
- C4-E candidate capture/normalization may land before #804 because it operates
  after an abstract conforming sandbox boundary and executes no real coding
  agent by itself.
