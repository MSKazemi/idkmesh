# Phase 0 Executable Independent Verifier

Status: experimental MVP  
Tracker: #5  
Product milestone: #16

## Purpose

IDKMesh already has separate canonical contracts for:

```text
Work Unit
 -> worker ResultManifest
 -> independent VerificationResult
 -> human/integration decision
```

The missing Phase 0 capability is to generate the `VerificationResult` from **verifier-owned observed evidence**, instead of only validating a hand-authored verification fixture.

`experiments/independent_verifier.py` is the first deliberately narrow executable verifier.

## Safety boundary

The MVP verifies only the repository's built-in deterministic Phase 0 smoke artifact.

It does **not**:

- execute commands supplied by a candidate or manifest;
- run untrusted PR code as a verifier action;
- use network access;
- call model/provider APIs;
- use paid compute;
- mutate canonical repository state;
- merge or accept a candidate automatically.

A verifier recommendation remains decision support.

## Input contract

The verifier receives:

1. a canonical Phase 0 experiment manifest;
2. a canonical Work Unit referenced by that manifest;
3. a canonical worker `ResultManifest v0.1`;
4. the exact candidate NDJSON artifact declared by the ResultManifest.

The worker ResultManifest must already satisfy the canonical worker-result contract.

## Verifier-owned checks

### 1. Artifact integrity

The verifier computes SHA-256 over the exact candidate bytes and compares it with the digest declared by the worker ResultManifest.

A stale or substituted artifact fails verification even if its contents would otherwise reproduce.

### 2. Independent schema validation

Every candidate row is independently validated against:

`schemas/experiment-result-v0.1.schema.json`

Worker self-report is not used as schema evidence.

### 3. Independent deterministic reproduction

For the built-in `deterministic_smoke` runner, the verifier reconstructs the complete expected run set from the experiment manifest and independently recomputes:

- run identifiers;
- configuration IDs;
- seeds;
- agent counts;
- Work Unit count;
- canonical manifest digest;
- deterministic `smoke_score`.

Missing, unexpected, duplicate, or mismatched runs fail the reproduction check.

## Output contract

The verifier emits `VerificationResult v0.1` containing:

- separate verifier identity;
- explicit independence statement;
- required check results;
- evidence digests and locators;
- findings;
- verifier resource measurements;
- exact Work Unit and ResultManifest canonical digests;
- source revision;
- verifier configuration digest;
- `accept_candidate` or `reject_candidate` recommendation.

The generated object is schema-validated before it is written.

Existing cross-object provenance integrity rules remain authoritative: the VerificationResult must bind to the exact Work Unit and exact ResultManifest it claims to evaluate.

## Fail-closed behavior

The MVP supports required validator IDs:

- `schema`;
- `reproduction`.

If a Work Unit requires a validator the MVP does not implement, it raises an error rather than silently skipping the requirement.

This is intentional. Adding a validator type requires an explicit verifier adapter/check implementation and tests.

## Test matrix

`tests/test_independent_verifier.py` exercises at least:

1. **known-good candidate** -> all required checks pass, output satisfies canonical VerificationResult and provenance bindings;
2. **tampered smoke score** -> artifact digest is current and schema is valid, but independent reproduction fails and candidate is rejected;
3. **stale worker artifact digest** -> candidate can reproduce, but artifact-integrity fails and candidate is rejected.

The Phase 0 GitHub Actions workflow runs this matrix on relevant changes.

## CLI

The verifier can be called as:

```bash
python experiments/independent_verifier.py \
  --manifest examples/experiments/phase0-smoke.manifest.json \
  --worker-result <worker-result.json> \
  --candidate-result <candidate-results.jsonl> \
  --output <verification-result.json>
```

The supplied ResultManifest must declare the actual digest of the candidate artifact. The static repository ResultManifest example is primarily a contract fixture; tests construct a correctly bound candidate/result pair dynamically.

## Next evolution

This MVP proves the execution boundary, not a universal verifier.

Next #5 steps should be evidence-driven:

1. connect the verifier to real candidate artifacts emitted by the canonical local node (#34/#37);
2. add a verifier-owned hidden acceptance check for a bounded repository task;
3. add unauthorized-path/dependency checks for real patch candidates;
4. retain timeout/error/inconclusive states;
5. build a small 5–10 task benchmark cohort;
6. feed observed verification cost and backlog into #14 backpressure experiments.

Do not add a large verifier framework before the first real candidate -> observed verification -> Evidence Report loop works end-to-end.
