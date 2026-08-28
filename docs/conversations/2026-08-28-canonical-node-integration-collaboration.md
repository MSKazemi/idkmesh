# Conversation Record — Canonical Node Integration Collaboration

**Date:** 2026-08-28

## Project-owner instruction

The project owner asked ChatGPT to continue collaborating on and improving the public IDKMesh repository without requiring a new detailed instruction for every next step.

## Repository state discovered

The repository had advanced beyond the earlier Phase 0 plan. `main` already contained:

- canonical Work Unit v0.1;
- Experiment Manifest and Experiment Result schemas;
- worker ResultManifest v0.1;
- a safe deterministic Phase 0 harness;
- passing Phase 0 CI;
- ACE community-growth automation;
- extensive research and architecture documents.

The latest repository audit identified open PR #21 as the immediate executable-core blocker. PR #21 contained a useful bounded local Docker worker, but it predated the canonical Phase 0 contracts and defined a second incompatible object also called Work Unit v0.1 plus a custom `result.json` protocol.

## Decision

Do not merge a second Work Unit/result protocol.

Preserve one backend-neutral canonical Work Unit and add node-specific execution settings as a namespaced extension. Preserve the canonical worker ResultManifest as the worker output boundary.

The new extension is:

`extensions.org.idkmesh.node.execution`

and is specified by:

`schemas/node-execution-binding-v0.1.schema.json`

The extension references a canonical Work Unit input of type `git_ref` rather than replacing the Work Unit's shared input model.

## Implementation

Created branch:

`integration/canonical-node-v0.1`

and opened PR **#34 — Integrate canonical Work Unit node backend**.

The integration adds:

- `schemas/node-execution-binding-v0.1.schema.json`;
- `node/` Python package v0.2.0;
- canonical Work Unit validation through JSON Schema;
- immutable public GitHub `git_ref` source handling;
- node policy requiring network `none`, no secrets, explicit filesystem write scope, and process-execution permission;
- bounded Docker command construction preserving read-only root, dropped capabilities, `no-new-privileges`, PID/CPU/RAM/time limits, and no Docker socket/credential mounts;
- changed-path checks against both `constraints.allowed_paths` and `permissions.filesystem_write`, with forbidden-path detection;
- canonical worker `ResultManifest v0.1` output with candidate patch/log digests, Work Unit and worker-config digests, source revision, resource metrics, path-policy results, and required validator IDs;
- explicit separation between successful execution and independent acceptance;
- canonical smoke fixture;
- negative test proving the old private node Work Unit object is rejected;
- sandbox policy tests;
- a node CI workflow that also runs the shared Phase 0 validator.

## Parallel-main synchronization

While the integration branch was being developed, `main` advanced with ACE community automation and README work.

Those changes were non-conflicting. The branch was synchronized using a two-parent merge commit while preserving the exact newer `main` blobs rather than overwriting parallel collaboration.

Synchronized integration head:

`f429eaaa8ec941c088ab1f5e518507cfa051655a`

## Verification evidence

Two GitHub Actions workflows passed on PR #34:

1. **IDKMesh Node CI** run `33179470677`
   - node package installation: passed;
   - shared Phase 0 contract validation: passed;
   - canonical node fixture validation: passed;
   - node unit tests: passed.

2. **Phase 0 schema check** run `33179470667`
   - Phase 0 dependency installation: passed;
   - schema and fixture validation: passed;
   - deterministic built-in smoke fixture: passed.

The assistant execution environment could not perform an end-to-end Docker run because Docker is not exposed there. This limitation was not hidden or replaced by a weaker claim.

## Remaining merge gate

Created **issue #37 — Acceptance: run canonical idkmesh-node smoke on a controlled Docker host** and labeled it `help wanted`.

The issue specifies:

- exact install/validate/run commands;
- expected result bundle;
- ResultManifest checks;
- artifact digest checks;
- changed-path checks;
- a negative out-of-scope path test;
- host/Docker/head-SHA evidence to report.

PR #34 should remain open until this controlled Docker acceptance evidence is supplied. Green schema/unit CI is necessary but should not be misrepresented as proof of runtime sandbox behavior.

## Architectural consequence

The executable kernel path is now clearer:

```text
canonical Work Unit
        |
        +-- backend-neutral semantics
        |
        +-- namespaced execution binding
                 |
                 v
          bounded local node
                 |
                 v
       canonical ResultManifest
                 |
                 v
       independent verifier(s)
                 |
                 v
          evidence / verdict
                 |
                 v
      human/governance decision
```

This preserves a single shared coordination language while allowing multiple future execution adapters.

## Next highest-value engineering step

After the Docker acceptance gate, define the independent verifier/evidence boundary and connect one local generator and one independent validator into a minimal Verified Swarm Runner. The worker must never be able to certify its own candidate as accepted.
