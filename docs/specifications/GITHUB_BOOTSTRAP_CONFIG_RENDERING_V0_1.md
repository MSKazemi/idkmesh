# GitHub Bootstrap Config Rendering v0.1

**Status:** experimental implementation contract  
**Issue:** #596 / C8-C  
**Authority:** rendering only; no filesystem write, GitHub mutation, secret
resolution, dispatch, verification, approval, push, or merge authority.

## Purpose

C8-C turns the deterministic C8-A bootstrap file plan into deterministic bytes
for the project-side configuration portion of a GitHub-first installation.

The renderer consumes a validated
`idkmesh.github_bootstrap.GitHubBootstrapPlan` and emits exactly these files:

- `.idkmesh/README.md`;
- `.idkmesh/project.json`;
- `.idkmesh/connections.json`;
- `.idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json`.

Workflow wrappers remain C8-D. Filesystem application and safe re-run behavior
remain C8-F.

## Determinism and generated identity

For the same bootstrap plan, rendering must produce byte-identical UTF-8,
newline-terminated output.

Every rendered file carries:

- repository-relative path;
- C8-A ownership class;
- C8-A overwrite policy;
- render source;
- byte length;
- SHA-256 content digest;
- explicit false authority/secret-access claims.

The content digest is evidence for a later apply/re-run boundary. It does not
authorize overwriting a file by itself; C8-F must compare retained generated
identity with the actual target content and preserve user edits.

## ProjectManifest seed

The generated `.idkmesh/project.json` is a valid ProjectManifest v0.1 seed.

Safety defaults include:

- protected-PR integration mode;
- automatic merge disabled;
- explicit human decision required;
- human integration required by verification policy;
- maximum autonomous risk limited to `low`;
- repository read capability required;
- merge/governance mutation authority forbidden;
- repository-local software-engineering DomainPack;
- bootstrap metadata stating that project identity/goals must be customized
  before dispatch.

The generated target branch comes from the validated bootstrap plan.

## Connector seed

The generated `.idkmesh/connections.json` is valid connector-profile input.

The initial template contains one Jules connector because it demonstrates the
secret-reference boundary without inventing a credential value.

It is deliberately:

- `enabled: false`;
- limited to low-risk coder work;
- zero project-spend ceiling;
- plan-approval required;
- configured with `auth.secret_ref = env:JULES_API_KEY`;
- configured with placeholder Source identity
  `sources/github/OWNER/REPOSITORY`.

The bootstrap never reads `JULES_API_KEY`. The owner must configure the secret
outside tracked repository files and must update the Source identity before
enabling the connector.

## Vendored DomainPack

The generated software-engineering DomainPack is semantically identical to the
canonical checked-in
`examples/domain-packs/software-engineering-v0.1.domain-pack.json`.

Tests compare the rendered document with that canonical source and validate it
against `schemas/domain-pack.schema.json`. Drift therefore fails CI rather than
silently creating a second software-engineering policy.

## Generated README

The generated `.idkmesh/README.md` explains:

- which files are `user_seed` versus `idkmesh_managed`;
- that user-seed files must not be overwritten by later bootstrap runs;
- that managed-file replacement requires generated-digest matching in C8-F;
- required owner actions before enabling a provider;
- secret handling;
- the no-merge/no-self-acceptance authority boundary;
- that C8-C is rendering-only.

## Dry-run integration

`idkmesh init --github --dry-run` continues to perform zero writes.

Its JSON form additionally emits `rendered_config_files`, including content,
digest, size, ownership, and overwrite metadata. Human-readable output shows
the rendered paths and digests without printing secret material.

Apply mode remains fail-closed.

## Failure semantics

Rendering fails closed when:

- the object is not a `GitHubBootstrapPlan`;
- the C8-A plan no longer contains exactly the expected C8-C file set;
- a known C8-C file has no renderer;
- a renderer does not return newline-terminated text.

A C8-A/C8-C mismatch must not be treated as permission to silently omit or add
project files.

## Non-goals

This slice does not:

- create directories or write files;
- generate C8-D workflow wrappers;
- inspect or mutate GitHub repository settings;
- create GitHub secrets or environments;
- resolve secret references;
- validate a live Jules Source;
- dispatch a WorkUnit;
- run a worker/verifier;
- apply generated files;
- overwrite user edits;
- grant approval, push, merge, or repository-administration authority.

## Verification

Focused tests cover:

- deterministic bytes and SHA-256 digests;
- exact four-file C8-C inventory;
- ProjectManifest schema validity;
- connector-profile parser validity;
- disabled provider default and secret-reference-only behavior;
- DomainPack equality with the canonical source and schema validity;
- protected/human integration defaults;
- C8-A plan-drift failure;
- CLI dry-run content/digest projection;
- zero filesystem writes.

## Follow-on

- **C8-D:** render thin pinned workflow wrappers.
- **C8-E:** owner-action checklist/preflight.
- **C8-F:** safe filesystem apply/re-run with user-edit preservation.
- **C8-G:** fresh-repository bootstrap-to-preview acceptance fixture.
