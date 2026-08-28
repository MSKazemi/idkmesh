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

## Community impact

This creates a concrete contribution surface: contributors can improve Work Unit validation, sandbox isolation, result provenance, agent adapters, verification, documentation, and usability without needing to understand the eventual million-node architecture.

## Next experiments

- run the node against an immutable IDKMesh commit using a deterministic command;
- add a first local-model adapter (candidate: goose + Ollama);
- add stronger sandbox profiles;
- define signed/approved Work Units and a scheduler handshake only after the local safety envelope is tested;
- measure verified useful work, not raw agent output.
