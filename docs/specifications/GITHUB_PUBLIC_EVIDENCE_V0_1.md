# GitHub Public Evidence Projection v0.1

Status: experimental C14-D contract for issue #609.

## Purpose

IDKMesh needs a read-only GitHub publication surface that remains useful after a
runner exits without copying raw evidence into Pages, comments, or other public
surfaces. This contract defines a **strict whitelist projection** over canonical
Product Spine state and optional digest-bound Run Evidence Report /
CandidateReference details.

The implementation is `idkmesh/github_public_evidence.py`; the machine-readable
shape is `schemas/github-public-evidence-v0.1.schema.json`.

## Publication gate

Projection requires a trusted `GitHubPublicEvidencePolicy` with:

- the exact `owner/repository`;
- `data_classification = public`;
- `public_projection_enabled = true`.

The Product Spine `project_id` must match that repository. This policy is not
derived from issue text, worker output, model output, or provider metadata.

This module does **not** call GitHub to prove repository visibility. The caller
must establish that the repository/data is actually public before constructing
an enabling trusted policy. A false trusted policy is a configuration error, not
evidence that the data was safe to publish.

## Included fields

Only these classes of information are projected:

- run ID/state;
- WorkUnit ID/version/digest;
- exact source revision;
- retained evidence/decision digests;
- attempt ID/order/connector/state;
- retained CandidateReference / ResultManifest / VerificationResult digests;
- same-repository GitHub PR number/head SHA/URL, when a bound PR reference is supplied;
- artifact-bundle content digest, **never its locator**;
- Run Evidence Report evidence-state and closed recommendation vocabulary;
- aggregate evidence counts/disagreement/control-failure booleans;
- whether a human decision is not recorded, pending, or recorded;
- explicit all-false authority ceiling.

Optional CandidateReference and Run Evidence Report objects are used only after
their canonical digests match the Product Spine projection.

## Always excluded

The projection never copies:

- issue/request text;
- prompts or model messages;
- stdout/stderr or raw logs;
- provider request/response payloads;
- provider/session references;
- raw Run Evidence Report warnings or error strings;
- individual check IDs/status text;
- worker identity;
- verifier identity;
- artifact-bundle filesystem/object locator;
- auth tokens, credentials, secret refs, or secret values;
- human decision rationale/body;
- executable commands.

The schema carries explicit privacy flags for these exclusions.

## Candidate rules

A supplied candidate must match the exact retained
`candidate_reference_digest`.

For `github_pull_request`, the candidate repository must equal the publication
repository. The safe projection may then expose PR number, immutable head SHA,
and canonical GitHub URL.

For `artifact_bundle`, only the content digest is emitted. Locator and media
type are intentionally dropped because a locator may contain a private path,
signed URL, object key, or other environment detail.

## Evidence rules

A supplied Run Evidence Report must match:

1. the retained report digest;
2. run ID;
3. WorkUnit ID/version/digest;
4. the exact attempt set and order;
5. connector identity per attempt;
6. retained ResultManifest digest;
7. retained verification semantic digest.

Only closed-vocabulary evidence state/recommendation and aggregate counts are
copied. Raw warnings, errors, checks, worker IDs, and verifier IDs are not
public-projection inputs.

## Authority

The projection is presentation evidence only. Every authority flag is fixed to
`false`:

- dispatch;
- verification;
- human decision;
- canonical-state write;
- Git push;
- integration;
- merge.

Publishing a digest or verifier recommendation does not accept a candidate.

## Determinism and bounds

`render_github_public_evidence_json()` emits strict deterministic JSON with
sorted keys, no NaN values, and a 128 KiB UTF-8 ceiling. It performs no file,
network, GitHub, verification, decision, or repository mutation.

The renderer is itself a publication boundary: before serializing, it rejects
any mapping whose root, run, attempt, candidate, or summary objects carry a key
outside the v0.1 whitelist, and any mapping whose authority ceiling or privacy
flags differ from the fixed values above. A hand-built or mutated mapping
therefore cannot smuggle extra fields past the projection builder.

## Relationship to other C14 slices

- C14-A (PR #932) renders a richer ephemeral Actions summary for operators.
- C14-D (this contract) is the narrower public-safe data boundary.
- C14-E should generate read-only Pages **from this projection or an equally
  strict reviewed successor**, not from raw provider/evidence JSON.
- C14-C (`idkmesh/github_evidence_link.py`) owns durable, commit-pinned
  evidence links after runner teardown; this projection carries no links
  beyond the canonical same-repository PR URL.
- Pages availability must never become a coordination or authority dependency.

## Non-goals

- no durable ledger;
- no GitHub Pages generator;
- no issue/PR comment mutation;
- no repository-visibility API probe;
- no secret scanner;
- no redaction of arbitrary text by pattern matching (unsafe text is excluded by
  field whitelist instead);
- no functional-correctness claim from publication.
