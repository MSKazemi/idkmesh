# GitHub Release Statement v0.1

Status: experimental C14-G contract for issue #609.

## Purpose

[GitHub Release Provenance v0.1](GITHUB_RELEASE_PROVENANCE_V0_1.md) (C14-F)
records which artifact digests and which public-safe run evidence a proposed
release references. C14-G renders that record as an
[in-toto Statement v1](https://in-toto.io/Statement/v1) so the same facts are
available in the interchange shape that artifact-attestation tooling consumes:
the release's distributable artifacts as **subjects**, and the whole release
record as the **predicate**.

The result is an **unsigned payload**, not an attestation. This contract exists
so that a CI job running under a GitHub workflow identity has a deterministic,
validated document to hand to an attestation step. It does not perform that
step.

The implementation is `idkmesh/github_release_statement.py`; the command is
`idkmesh release-provenance --statement`.

```python
statement = build_github_release_statement(record)   # record from C14-F
json_text = render_github_release_statement_json(statement)
```

## Command

```bash
idkmesh release-provenance --repository owner/name --tag v0.1.0 \
  --target-commit <40-hex-commit> \
  --artifact pkg-0.1.0.tar.gz=sha256:<64-hex> \
  --projection projections/run-1.json --statement
```

`--statement` is mutually exclusive with `--notes`. At least one `--artifact` is
required, because a statement without subjects attests nothing. The statement
goes to standard output; any rejected input prints `error: ...` on standard
error, writes nothing to standard output, and exits 2.

## Shape

| Field | Value |
|---|---|
| `_type` | `https://in-toto.io/Statement/v1` |
| `subject[]` | One per release artifact, in record order: `name` and `digest: {"sha256": "<64 hex>"}` (bare hex, as in-toto requires) |
| `predicateType` | The URL of this document |
| `predicate.schema_version` | `0.1` |
| `predicate.signature` | Fixed: `status = unsigned`, `signing_requires = CI workflow identity` |
| `predicate.claims` | Fixed all-false: `signed`, `attestation_registered`, `slsa_build_provenance`, `subjects_verified_against_build`, `functional_correctness` |
| `predicate.record` | The complete, validated C14-F record, including its `record_digest` |

The statement has no timestamps and no field outside the table.

## What is explicitly not claimed

- **Nothing is signed or registered.** No key, token, or workflow identity is
  read; no file, network, or GitHub call is made. Producing a real attestation
  needs a CI run with a workflow identity and a repository plan that supports
  artifact attestations. IDKMesh's release workflow already attests built
  distributions with `actions/attest-build-provenance` under
  [Release Supply Chain v0.1](RELEASE_SUPPLY_CHAIN_V0_1.md); this statement is
  not connected to that workflow and does not replace it.
- **Subjects are caller assertions.** They are the digests passed to
  `--artifact`, not digests computed from a build or a file
  (`subjects_verified_against_build = false`).
- **No SLSA build provenance.** The statement does not describe how, where, or
  from what source the artifacts were built.
- **No functional correctness.** A digest, a statement, or an eventual
  attestation never proves the software works. An attestation, once signed by
  CI, would show only that a given workflow identity vouched for the statement.
- **No authority.** The embedded record keeps every dispatch, verification,
  human-decision, push, merge, tag, release, and attestation flag `false`.

## Validation

`validate_github_release_statement` fails closed unless the statement is exactly
this shape: unknown keys anywhere, a different `_type` or `predicateType`,
relaxed `signature` or `claims`, an invalid or tampered embedded record (it is
re-validated through the C14-F validator), an empty subject list, and subjects
that differ from the embedded record's artifacts in name, digest, order, or
count are all rejected. Rendering re-validates, so a hand-built or mutated
statement cannot be emitted. Output is bounded to 2 MiB and rendered with sorted
keys.

## Non-goals

- no signing, no key handling, no attestation registration or upload;
- no computing or checking of artifact digests against files or builds;
- no workflow changes and no release or tag creation;
- no SLSA provenance predicate.
