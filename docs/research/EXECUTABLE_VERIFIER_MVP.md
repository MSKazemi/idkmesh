# Executable Independent Verifier MVP

Status: Phase A MVP for issue #5

## Why this exists

IDKMesh already had machine-readable contracts for:

```text
WorkUnit -> worker ResultManifest -> independent VerificationResult
```

A contract is not yet a verifier. The missing step was an executable component that observes a candidate independently of the worker and produces a `VerificationResult v0.1` from those observations.

`experiments/local_verifier.py` is the first deliberately small implementation.

## Trust model

The MVP consumes four inputs:

1. canonical WorkUnit v0.2;
2. canonical worker ResultManifest v0.1;
3. an isolated candidate directory;
4. verifier-owned policy outside the candidate directory.

The worker may control candidate bytes and its own self-report. It must not control verifier policy or verifier code used to evaluate that same attempt.

The verifier produces decision support only. It has no GitHub push/merge authority.

## Checks

The fixture Work Unit requires three checks.

### 1. Artifact digest

The verifier hashes the candidate bytes it actually reads and compares that hash with the worker ResultManifest.

This answers:

> Are these the exact bytes the worker claimed to produce?

It does **not** answer whether the bytes are correct.

### 2. Candidate scope

The verifier recursively enumerates the isolated candidate root and compares the observed file set with the verifier-owned allowlist.

Unsafe relative paths, path traversal, and candidate symlinks are rejected.

This answers:

> Did the candidate stay inside the bounded artifact surface expected by the verifier?

### 3. Independent acceptance

The verifier parses the candidate JSON and compares the observed value with deterministic expectations loaded from `verification/fixtures/verifier-smoke-policy.json`.

This answers:

> Does the candidate satisfy an evaluator-owned correctness condition rather than merely agree with its own self-report?

## The important negative fixture

The bad fixture is intentionally **self-consistent**:

- the candidate contains `answer = 41`;
- the worker ResultManifest contains the correct SHA-256 for those exact bad bytes;
- the candidate stays inside the allowed file scope.

Therefore:

```text
artifact-digest        -> PASS
candidate-scope        -> PASS
independent-acceptance -> FAIL
final verifier status  -> FAILED
recommendation         -> reject_candidate
```

This distinguishes provenance integrity from correctness.

## Run the self-test

From repository root:

```bash
python -m pip install -r requirements-phase0.txt
python experiments/local_verifier.py self-test \
  --good-candidate-root examples/verifier/good/candidate-root \
  --bad-candidate-root examples/verifier/bad/candidate-root
```

Phase 0 CI runs the same check.

## Verify one bundle

```bash
python experiments/local_verifier.py verify \
  --work-unit examples/work-units/local-verifier-smoke.work-unit.json \
  --result-manifest examples/verifier/good/result-manifest.json \
  --candidate-root examples/verifier/good/candidate-root \
  --policy verification/fixtures/verifier-smoke-policy.json \
  --output results/local-verifier-result.json
```

The emitted file validates against `schemas/verification-result-v0.1.schema.json` and is additionally checked by `experiments/provenance_integrity.py`.

## Safety properties of this MVP

- no candidate code execution;
- no network access;
- no secrets;
- no provider API;
- no project-paid compute;
- bounded candidate size;
- verifier policy must live outside the candidate root;
- exact Work Unit and ResultManifest provenance binding;
- verifier and worker identities remain distinct;
- failure yields `reject_candidate`, not an implicit success;
- `accept_candidate` is decision support, not merge authority.

## What this does not prove

The current fixture is JSON-only and deterministic. It does not yet prove that IDKMesh can safely verify arbitrary repository patches, hostile code, complex builds, or hidden tests at scale.

Issue #5 should remain open.

## Next Phase A extension

After the canonical node path passes the controlled-host Docker gate in #37, connect the verifier to a real bounded repository candidate and add verifier-owned checks such as:

1. pinned source/candidate reconstruction;
2. repository regression tests;
3. one evaluator-owned hidden or independent acceptance test;
4. unauthorized file/dependency change detection;
5. timeout/error/inconclusive behavior;
6. stable evidence capture and replay.

Only after that path is reliable should the benchmark substrate expand to the first 5–10 real tasks.

## Research consequence

This executable boundary also gives the verification-scaling work in #14 a real unit of measurement: verifier wall time, resource cost, failed checks, evidence production, and decision-support outcomes can now be measured instead of inferred only from schemas.
