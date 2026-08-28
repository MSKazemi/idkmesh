# Project Turn: Executable Independent Verifier

Date: 2026-08-28

## Context

The project owner asked ChatGPT to continue working directly on IDKMesh repository targets, goals, and tasks.

The execution-planning pass identified the current critical path as:

```text
protected integration
 -> canonical bounded local worker
 -> executable independent verifier
 -> multi-worker orchestrator
 -> Verified Swarm Runner v0.1
 -> real-task flagship experiment
```

Issue #5 was updated accordingly: the canonical VerificationResult format already exists, so the next missing capability is an executable verifier that produces evidence rather than another result schema.

## Implementation decision

Implement the smallest safe verifier that can run now without waiting for a Docker host or arbitrary candidate execution.

The Phase 0 deterministic smoke artifact provides a controlled candidate format whose expected results can be recomputed independently.

The verifier therefore performs:

1. candidate artifact SHA-256 verification against the worker ResultManifest;
2. independent ExperimentResult schema validation;
3. independent deterministic smoke reproduction from the experiment manifest;
4. generation of canonical `VerificationResult v0.1`;
5. exact cryptographic binding to the Work Unit and worker ResultManifest.

## Files added

- `experiments/independent_verifier.py`
- `tests/test_independent_verifier.py`
- `docs/specifications/PHASE0_EXECUTABLE_VERIFIER.md`

The Phase 0 GitHub Actions workflow is updated to execute the verifier tests.

## Safety boundary

The verifier does **not** execute candidate-supplied commands, manifest commands, provider calls, network requests, or paid compute.

It supports only the built-in deterministic Phase 0 smoke verification requirements and fails closed when a Work Unit requires an unsupported validator.

It does not merge or integrate candidates. `accept_candidate` remains a verifier recommendation for human/integration decision support.

## Test cases

The implementation includes three initial cases:

- known-good candidate -> pass;
- candidate with a tampered deterministic score but a current artifact digest -> reproduction failure/reject;
- reproducible candidate with a stale worker-declared artifact digest -> provenance/integrity failure/reject.

The positive test also exercises the existing canonical VerificationResult cross-object validation and provenance-integrity binding.

## Next step

After CI/review, connect this verifier boundary to a real ResultManifest/candidate emitted by the canonical local node (#34/#37). Then add one verifier-owned hidden acceptance check for a bounded repository task before expanding the benchmark inventory.

No self-merge or autonomous integration is performed in this turn.
