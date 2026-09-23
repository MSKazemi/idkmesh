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
