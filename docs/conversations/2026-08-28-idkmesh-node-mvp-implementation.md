# Conversation record: proceed with the first IDKMesh agent/node prototype

**Date:** 2026-08-28

## Project-owner instruction

After reviewing the proposal for free GitHub-hosted agents and volunteer `idkmesh-node` workers, the project owner instructed: **"Go head"** (proceed).

## Implementation interpretation

Proceed without waiting for further clarification by implementing the safest useful first slice:

1. a runnable local `idkmesh-node` MVP;
2. a bounded Work Unit v0.1 validator;
3. Docker sandbox execution with no network and explicit CPU/RAM/PID/time limits;
4. normalized result/provenance bundles rather than direct repository writes;
5. unit tests and GitHub CI;
6. repository-level agent instructions (`GEMINI.md`);
7. an advisory-only, manually triggered Gemini GitHub Action using read-only repository permissions.

## Security decision

The MVP does **not** turn volunteer computers into generic public-repository GitHub self-hosted runners. It does not mount host credentials or the Docker socket into task containers and does not grant direct push/merge authority.

Docker is treated as an MVP isolation mechanism, not a sufficient final boundary for arbitrary hostile Internet workloads. Stronger isolation remains an explicit research/engineering task.

## External-agent security note

The Gemini advisory workflow is pinned to `google-github-actions/run-gemini-cli` v0.1.22 commit `f77273f4c914e4bf38440cf36a0369cb64a37489`, the release that patched the April 2026 workspace-trust/tool-allowlisting security advisory affecting earlier versions. The workflow is manual and uses `contents: read` only.

## Implementation status

Implemented on branch `prototype/idkmesh-node-mvp` and opened as pull request **#21: Prototype safe local idkmesh-node worker**.

The implementation adds:

- `node/src/idkmesh_node/` — Work Unit validation, CLI, repository materialization, Docker command construction, bounded execution, result/provenance capture;
- `node/tests/` — validation and sandbox-policy tests;
- `node/examples/` — starter Work Unit example;
- `node/README.md` — safety model and usage;
- `.github/workflows/idkmesh-node-ci.yml` — read-only CI for the node tests;
- `.github/workflows/gemini-advisory.yml` — manual advisory-only Gemini pilot;
- `GEMINI.md` — repository-level AI-agent instructions.

Verification completed in this turn:

- 7 local unit tests passed;
- Python source compilation passed;
- GitHub Actions `IDKMesh Node CI` run #1 completed successfully on PR #21;
- GitHub reports PR #21 as mergeable.

End-to-end Docker execution was not performed in the assistant execution environment because Docker is not installed/exposed there. The first contributor-machine acceptance test should run one immutable IDKMesh commit inside the generated sandbox and inspect `result.json`, logs, and patch output.

The Gemini workflow is committed but cannot run until the repository has a `GEMINI_API_KEY` Actions secret. No key or credential is stored in the repository.

## Community impact

This creates a concrete contribution surface: contributors can improve Work Unit validation, sandbox isolation, result provenance, agent adapters, verification, documentation, and usability without needing to understand the eventual million-node architecture.

## Next experiments

- run the node against an immutable IDKMesh commit using a deterministic command;
- add a first local-model adapter (candidate: goose + Ollama);
- add stronger sandbox profiles;
- define signed/approved Work Units and a scheduler handshake only after the local safety envelope is tested;
- measure verified useful work, not raw agent output.
