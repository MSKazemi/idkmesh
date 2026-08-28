# Local Orchestrator Phase A0

**Status:** experimental executable kernel for issue #4  
**Scope:** deterministic, single-machine, exactly two attempts  
**Authority:** evidence production only; no merge/integration authority

## Purpose

Phase A0 is the smallest falsifiable IDKMesh multi-worker loop:

```text
same bounded Work Unit
  -> isolated attempt 1 -> ResultManifest -> independent VerificationResult
  -> isolated attempt 2 -> ResultManifest -> independent VerificationResult
                                      |
                                      v
                              orchestration report
                                      |
                                      v
                              human integration only
```

It exists to prove that IDKMesh can retain multiple candidate histories and independent verifier outcomes in one replayable run before introducing a real Docker worker, distributed scheduling, model diversity, or autonomous integration.

## Executable entry point

```bash
python experiments/local_orchestrator.py self-test
```

The default demonstration is:

```bash
python experiments/local_orchestrator.py run \
  --run-id phase-a0-good-bad \
  --scenario good-bad
```

Output is bounded to:

```text
results/orchestrator/<run-id>/
```

A run contains:

```text
.idkmesh-orchestrator-run
attempt-1/
  candidate-root/candidate.json
  result-manifest.json
  verification-result.json
attempt-2/
  ...
orchestration-report.json
```

The orchestrator will only delete/recreate a pre-existing run directory when the directory contains its matching ownership marker. It never recursively cleans the repository or a parent output directory.

## Phase A0 worker adapters

The current workers are deterministic fixtures, not general coding agents.

Supported behaviors:

- `good`: emits the verifier-owned expected JSON;
- `bad`: emits a self-consistent but incorrect JSON candidate with a correct artifact digest;
- `error`: records a worker failure without aborting the sibling attempt.

The default `good-bad` scenario is intentionally stronger than a crash-only test:

```text
attempt 1: worker says succeeded -> verifier passes
attempt 2: worker says succeeded -> verifier rejects
```

The bad worker's own artifact hash is valid. Its rejection comes from verifier-owned acceptance evidence, demonstrating that worker success and self-consistency are not acceptance.

The `good-error` scenario demonstrates failure isolation:

```text
attempt 1: completes and verifies
attempt 2: worker error -> verification not run
```

Both attempt records remain in the final report.

## Canonical contracts

Successful fixture workers emit `ResultManifest v0.1` and are passed directly to the already-landed `experiments/local_verifier.py`, which emits `VerificationResult v0.1`.

The Phase A0 Work Unit is:

```text
examples/work-units/orchestrator-smoke.work-unit.json
```

The verifier policy remains verifier-owned:

```text
verification/fixtures/verifier-smoke-policy.json
```

The candidate root cannot contain that policy or verifier implementation.

## Run metadata and replay

`orchestration-report.json` records:

- run ID and scenario;
- exact Work Unit ID/version/digest/source revision;
- verifier policy ID/digest;
- ordered attempts;
- worker adapter/version/behavior;
- per-attempt workspace and ResultManifest/VerificationResult locators;
- worker status;
- independent verification status/recommendation;
- explicit human-only integration authority;
- replay parameters;
- a semantic signature excluding incidental workspace paths.

`self-test` executes the same `good-bad` configuration twice in separate roots and requires identical semantic signatures.

Fixture timestamps are logical deterministic timestamps. A future real worker adapter should use observed runtime timestamps while preserving a separate replay signature.

## Safety invariants

1. Exactly two attempt records are retained.
2. Attempt candidate roots are distinct.
3. One attempt failure does not abort the sibling.
4. Worker success never implies acceptance.
5. Verification is linked to the exact ResultManifest ID and attempt number.
6. No majority vote is used.
7. No candidate is automatically merged or integrated.
8. CLI output is restricted to `results/orchestrator/`.
9. Cleanup requires a matching run-ownership marker.
10. No candidate-supplied code, network operation, secret, paid compute, or Docker task is executed in Phase A0.

## What Phase A0 does not prove

It does **not** prove:

- the canonical local node is safe for arbitrary public workloads;
- Docker isolation is sufficient;
- hidden repository tests are complete;
- parallel scheduling improves quality;
- more workers improve outcomes;
- a distributed/volunteer compute fabric is ready;
- automatic merge is safe.

Those claims require separate evidence.

## Phase A1 adapter boundary

After PR #34 is synchronized and controlled-Docker acceptance #37 succeeds, a real node adapter should replace only the worker-adapter portion:

```text
FixtureWorkerAdapter -> CanonicalNodeAdapter
```

The following should remain stable:

- Work Unit dispatch interface;
- isolated per-attempt workspace;
- canonical ResultManifest collection;
- independent verifier routing;
- per-attempt evidence retention;
- orchestration report;
- replay metadata;
- human-only integration boundary.

This separation is the main architectural result of Phase A0.

## Next evidence after Phase A0

Once this kernel is independently reviewed and merged:

1. connect the accepted canonical local node as the first real worker adapter;
2. bind node runtime acceptance to the exact tested revision;
3. connect repository-candidate verifier plugins from issue #5;
4. retain the same failure-isolation/replay tests;
5. only then extend from two attempts to bounded 3–5 attempt parallelism.

Refs: #4 #5 #16 #34 #37.
