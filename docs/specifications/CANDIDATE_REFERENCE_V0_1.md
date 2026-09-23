# CandidateReference v0.1

**Status:** experimental contract  
**Date:** 2026-09-23  
**Authority:** identity/provenance only; a reference grants no verification, acceptance, merge, release, or integration authority.

## 1. Purpose

A worker/provider can finish before IDKMesh has a trustworthy candidate identity.
CandidateReference v0.1 is the small provider-neutral object that closes that gap.

It answers:

> **Exactly which immutable candidate should downstream normalization and verification inspect?**

It deliberately does not answer:

> Is the candidate correct, acceptable, safe to merge, or authorized for integration?

Those are later evidence and authority stages.

The lifecycle is:

```text
worker/provider completion
        |
        v
candidate discovery hint
        |
        v
trusted candidate identity resolution
        |
        v
CandidateReference v0.1
        |
        v
ResultManifest normalization
        |
        v
independent verification
        |
        v
human/governance integration decision
```

## 2. Version

```json
{"schema_version": "0.1"}
```

Breaking changes require a new schema version. Historical v0.1 references keep
their original meaning.

Machine-readable schema:

`schemas/candidate-reference-v0.1.schema.json`

Reference implementation:

`idkmesh/candidate_reference.py`

## 3. GitHub pull-request form

```json
{
  "schema_version": "0.1",
  "type": "github_pull_request",
  "repository": "MSKazemi/idkmesh",
  "number": 123,
  "head_sha": "0123456789abcdef0123456789abcdef01234567"
}
```

Required identity:

- exact repository in `owner/name` form;
- exact pull-request number;
- exact immutable PR head object ID.

The branch name, PR URL, provider session ID, PR title, or provider claim that a
PR exists is not sufficient candidate identity.

`head_sha` accepts 40- or 64-hex Git object IDs so the contract does not hard-code
SHA-1 as Git's only object format. The reference implementation normalizes the
digest to lowercase.

The human-facing URL is derivable from the reference:

```text
https://github.com/{repository}/pull/{number}
```

and is intentionally not part of immutable identity.

### Resolution rule

A coding provider may return a PR URL as a **discovery hint**. The provider must
not be trusted to fill `head_sha` merely because it created the candidate.

For GitHub-backed candidates, the SCM boundary resolves the configured repository
and pull-request number and observes the current exact head SHA. Candidate
readiness is reached only after this binding exists.

If the PR head moves later, that is a different candidate revision and must be
re-observed/re-normalized. Historical evidence stays bound to the old SHA.


### Jules discovery-hint to SCM binding

The first concrete provider-to-SCM bridge is `idkmesh/jules_candidate_binding.py`.

It consumes a `JulesPullRequestHint` only after the Jules adapter has already bound that hint to the trusted Session repository. The bridge then:

1. verifies that the hint is a Jules Session observation and that its canonical URL agrees with the bound repository/PR number;
2. calls the provider-neutral GitHub PR reader with **only** repository + PR number;
3. obtains the exact head object ID from the SCM reader, never from Jules;
4. translates SCM identity failures into the shared connector error taxonomy without copying raw SCM/provider payloads;
5. returns the shared `GitHubPullRequestResolution` unchanged.

The bridge has no `candidate_ready`, verification, acceptance, merge, or integration field. The upper control plane may advance to candidate readiness only after this SCM-backed resolution succeeds.

This keeps the trust chain explicit:

```text
Jules Session output
 -> JulesPullRequestHint
 -> JulesCandidateBindingService
 -> GitHubPullRequestCandidateReader
 -> GitHubPullRequestCandidateReference(repo, PR, exact head)
```

A Jules URL cannot supply or override `head_sha`, and a provider-specific adapter must not bypass the shared SCM reader with its own head-resolution rule.

## 4. Artifact-bundle form

```json
{
  "schema_version": "0.1",
  "type": "artifact_bundle",
  "locator": "file:///tmp/idkmesh/run-123/candidate.tar",
  "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "media_type": "application/x-tar"
}
```

Required identity:

- a stable locator usable by the configured execution/evidence boundary;
- a lowercase SHA-256 content digest.

`media_type` is optional descriptive metadata. The digest, not the locator,
is the immutable content identity.

A local path without a digest is not a candidate-ready reference.

### Resolution rule for local artifact bundles

For local execution, the reference reader is
`idkmesh/local_candidate_reader.py`.

It accepts only a **relative file path beneath an explicitly configured
workspace root** and an explicit maximum byte budget. The reader:

1. rejects absolute paths and parent traversal;
2. rejects symlink aliases below the trusted root;
3. resolves the path and proves it remains beneath that root;
4. requires a regular file;
5. enforces the byte ceiling before and during reading;
6. computes SHA-256 itself from the bytes it reads;
7. detects common replacement/mutation races by comparing file identity and
   metadata before, after, and at the final path;
8. optionally compares an expected worker-supplied digest, treating it only as a
   claim to check;
9. emits the computed content digest in an `ArtifactBundleCandidateReference`.

The reader does not trust a worker-supplied digest as content identity and does
not grant candidate acceptance or verification authority. The local `file:`
locator is an execution/evidence locator; a later durable artifact-store stage
may replace the storage location while preserving the same content digest.

## 5. Provider neutrality

CandidateReference contains no Jules, Codex, OpenHands, goose, model-provider,
or agent-framework field.

Provider/worker identity belongs in run/ResultManifest provenance. After
candidate normalization, downstream verification should not need provider-specific
candidate semantics.

This supports the C6 exit gate:

> remote PR and local artifact candidates enter the same evidence/verification path.

## 6. Non-authority rules

A CandidateReference:

- does **not** assert worker success;
- does **not** assert the candidate is complete or correct;
- does **not** satisfy an EvaluatorPlan;
- does **not** contain a verifier recommendation;
- does **not** authorize merge/integration;
- does **not** permit mutable provider output to overwrite historical evidence.

The core relation is:

```text
worker_completed != candidate_ready != verified != integrated
```

CandidateReference is the evidence required for the second state boundary only.

## 7. Validation and failure behavior

The v0.1 parser/schema fail closed on:

- unknown candidate types;
- unknown schema versions;
- unexpected fields;
- malformed repository identity;
- non-positive or boolean PR numbers;
- branch names or other non-digest values in `head_sha`;
- missing/invalid artifact digests;
- empty locators/media types.

Cross-field/source checks that require live SCM or artifact access belong to the
candidate reader/resolver (C6-C/C6-D), not this pure contract.

## 8. Relationship to other contracts

- **WorkUnit** defines authorized bounded work.
- **Run/provider observation** establishes worker lifecycle state.
- **CandidateReference** establishes immutable candidate identity.
- **ResultManifest** records worker result/provenance/artifacts.
- **EvaluatorPlan** is verifier-owned evaluation control data.
- **VerificationResult** records independent evidence/recommendation.
- **Human/governance decision** remains a separate integration-authority stage.

The companion provider-completion decision is proposed as **ADR-0013 — Separate
Provider Completion from Candidate Readiness** in PR #707. This contract remains
reviewable independently and does not require that separate stacked branch to be
present in the repository tree.

## 9. Next slices

C6-A defines identity only. Follow-up work remains intentionally separate:

1. C6-B — WorkUnit/source binding checks;
2. C6-C — PR candidate reader / SCM exact-head resolution;
3. C6-D — local artifact-bundle reader;
4. C6-E — ResultManifest builder;
5. C6-F — evaluator-owned verification handoff;
6. C6-G — PR/local equivalence fixture.

## 10. SCM resolution boundary

For GitHub PR candidates, the reference implementation is
`idkmesh/github_candidate_reader.py`.

The reader takes only provider-neutral target identity:

```text
repository + PR number
        |
        v
trusted GitHub/SCM lookup
        |
        +-- target repo mismatch -> fail closed
        +-- PR number mismatch   -> fail closed
        +-- malformed head SHA   -> fail closed
        |
        v
GitHubPullRequestCandidateReference
(repository + number + exact head SHA)
```

The reader also records descriptive GitHub state/draft flags for operator
visibility, but those fields do not become acceptance or verification
authority. A closed or draft PR can still be *identified* precisely; whether it
is eligible for further processing belongs to policy/verification, not identity
parsing.

A provider adapter must not implement its own alternate head-SHA trust rule.
Connector-specific error translation also remains outside this provider-neutral
identity reader.

### Production GitHub REST source

`idkmesh/github_rest_source.py` provides the concrete public-GitHub transport for the PR identity reader.

The trust split remains:

```text
GitHubRestPullRequestSource
  = fixed-host transport + bounded JSON decoding + transport error normalization

GitHubPullRequestCandidateReader
  = repository/PR/URL/state/head identity validation
```

The REST source intentionally does **not** decide whether the returned object is the requested candidate. It returns an untrusted decoded object to the reader.

Transport controls:

- endpoint host is fixed to `https://api.github.com`; caller input cannot choose an arbitrary URL;
- repository identity is restricted to `owner/name` before network I/O;
- PR number must be a positive integer;
- optional bearer token exists only in the in-memory request header and is never copied into error details;
- connection ID is explicit so audit/error envelopes identify the configured SCM connection;
- requests carry the pinned GitHub REST API version `2022-11-28` and vendor media type;
- response reads are bounded (1 MiB default, 8 MiB hard configuration ceiling);
- malformed UTF-8/JSON, non-object JSON, and oversized responses fail closed;
- 401/403/404/408/429/5xx and network timeouts are normalized to the shared ConnectorError taxonomy without retaining response bodies.

This v0.1 source targets public `github.com` only. GitHub Enterprise Server support should use a separately validated connection configuration; the candidate resolver must not accept an arbitrary provider-returned API base because that would turn candidate discovery into an SSRF surface.
