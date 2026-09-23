# ADR-0015 — Normalize Candidate Identity into ResultManifest Without Pretending Reference Digests Are Content Verification

- **Status:** Proposed / experimental
- **Date:** 2026-09-23
- **Related:** #579, CandidateReference v0.1, ResultManifest v0.1, ADR-0013

## Context

C6 must erase provider-specific candidate differences without changing the already-frozen ResultManifest v0.1 contract.

The two first candidate classes have different native identity material:

- a local artifact bundle has a stable locator plus a SHA-256 content digest;
- a GitHub pull request is independently resolved to repository + PR number + exact Git head object ID.

ResultManifest v0.1 requires each produced artifact to carry a SHA-256 `digest`. For a PR candidate, C6-C does **not** yet possess a SHA-256 hash of patch bytes, and inventing one from provider text or relabeling a Git SHA as `sha256:` would be false evidence.

Changing ResultManifest for one provider would also violate the C6 goal that provider-specific candidate differences disappear after normalization.

## Decision

C6 normalization keeps ResultManifest v0.1 unchanged and represents the normalized **CandidateReference document itself** as the first evidence artifact.

### Canonical reference digest

For every CandidateReference v0.1:

```text
candidate_reference.to_dict()
 -> canonical JSON
    json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
 -> UTF-8
 -> SHA-256
 -> sha256:<lowercase hex>
```

This is the same canonical-digest convention already used for WorkUnit and ResultManifest provenance.

The resulting value is a **candidate-reference envelope digest**.

It means:

> these exact normalized identity fields were handed to downstream verification.

It does not mean:

> IDKMesh independently hashed every byte reachable through the candidate locator.

### ResultManifest projection

C6-E emits one primary produced artifact with:

- stable artifact ID, default `candidate`;
- `type = "other"`;
- media type `application/vnd.idkmesh.candidate-reference+json`;
- a locator derived from the CandidateReference;
- digest equal to the canonical CandidateReference envelope digest.

The exact CandidateReference object and the same reference digest are retained under the namespaced ResultManifest extension:

```text
org.idkmesh.candidate_reference
```

For a GitHub PR, the human-readable locator also carries the exact resolved head SHA in its fragment. For a local artifact bundle, the CandidateReference itself retains the independently computed content digest from C6-D.

### Verification remains separate

The reference digest is identity/provenance evidence only.

It is not:

- a verifier verdict;
- proof that the code is correct;
- proof that a remote PR diff was independently content-hashed by C6;
- merge/release authority;
- permission to skip EvaluatorPlan/VerificationResult processing.

A later verifier may materialize the exact Git head or local bundle and produce stronger content/test/reproduction evidence.

### Validation ownership

C6-E also:

- validates the retained WorkUnitSourceBinding before normalization;
- derives expected validator IDs from the WorkUnit instead of provider output;
- records worker/provider self-report separately from verification;
- records an explicit `self_report_source`;
- preserves only normalized worker/model/environment metadata;
- rejects malformed time/resource/metric/digest values before emitting the manifest.

## Consequences

### Positive

- PR and local candidates enter the same ResultManifest shape;
- no provider-specific field is added to the canonical schema;
- no Git SHA is mislabeled as SHA-256;
- local content hashes remain visible inside the CandidateReference;
- downstream verification receives one stable identity object regardless of provider;
- existing provenance-integrity tooling can reuse the same digest convention.

### Trade-offs

- the produced-artifact digest is a digest of the normalized reference envelope, not necessarily the candidate bytes;
- verifiers that require byte-level content evidence must materialize the referenced candidate and produce their own evidence;
- the namespaced extension is required to interpret the normalized reference artifact correctly.

These trade-offs are intentional and explicit. They are preferable to false content-hash claims or a provider-specific ResultManifest fork.

## Alternatives considered

### Relabel the Git head SHA as `sha256:...`

Rejected. Git object IDs may use a different algorithm and have different semantics. Relabeling would create false provenance.

### Hash provider-returned PR URL/title/description

Rejected. Those fields are mutable descriptive metadata and do not establish candidate content identity.

### Change ResultManifest v0.1 for GitHub PRs

Rejected for C6. The component is required to normalize into the existing canonical contract. A future ResultManifest v0.2 may introduce a first-class candidate-reference field if real evidence demonstrates that the extension is insufficient.

### Require C6-C to download and hash all remote candidate bytes

Deferred. That is potentially useful stronger evidence, but it couples the identity resolver to repository materialization and is not required to preserve exact Git candidate identity. It belongs in a verifier or a separately bounded artifact-materialization slice.

## Implementation requirements

1. C6-E must validate WorkUnitSourceBinding before emitting a manifest.
2. CandidateReference envelope digest must use the repository canonical JSON digest convention.
3. The candidate reference/digest must be retained under a namespaced extension.
4. PR and local candidates must produce the same canonical ResultManifest shape.
5. Expected validator IDs must come from WorkUnit, not provider output.
6. ResultManifest must contain no acceptance, verification verdict, human decision, merge, or integration authority.
7. Focused tests must validate emitted documents against `result-manifest-v0.1.schema.json`.

## References

- `docs/specifications/CANDIDATE_REFERENCE_V0_1.md`
- `docs/specifications/RESULT_MANIFEST_V0_1.md`
- `docs/specifications/VERIFICATION_PROVENANCE_INTEGRITY.md`
- `docs/decisions/ADR-0013-provider-completion-candidate-readiness.md`
- `idkmesh/work_unit_binding.py`
