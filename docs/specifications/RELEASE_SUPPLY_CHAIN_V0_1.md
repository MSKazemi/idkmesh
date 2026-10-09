---
description: "Release-integrity baseline: a published IDKMesh Python release must bind its Git commit, workflow identity, wheel and sdist bytes, and build provenance."
---
# Release Supply-Chain Baseline v0.1

**Status:** active release baseline  
**Issue:** #674  
**Workflow:** `.github/workflows/publish-pypi.yml`

## Goal

Every published IDKMesh Python release must carry enough independently
verifiable evidence to answer:

- which exact Git commit was built;
- which workflow identity produced the release;
- which wheel/sdist bytes were produced;
- which declared runtime and optional dependencies existed at build time;
- whether GitHub registered signed build provenance for those exact bytes.

This is a release-integrity control. It is not a correctness, security, or
acceptance oracle.

## Release evidence

The build job creates three deterministic evidence files under
`release-metadata/`:

- `checksums.txt` — SHA-256 for each wheel/sdist;
- `sbom.spdx.json` — SPDX 2.3 package inventory derived from the canonical
  `pyproject.toml` dependency declarations;
- `release-provenance.json` — source commit/ref, workflow ref/commit, workflow
  run identity, artifact hashes/sizes, and explicit authority limitations.

The build then creates a GitHub artifact attestation for `dist/*` using
`actions/attest-build-provenance`, pinned to immutable commit
`e8998f949152b193b063cb0ec769d69d929409be` (v2.4.0), and immediately verifies
each artifact with `gh attestation verify`.

The evidence files are uploaded as a workflow artifact. After the human-gated
PyPI publication succeeds, they are also attached to the matching GitHub
release so verification does not depend on short Actions-artifact retention.

## Exact source and workflow binding

The workflow checks out the requested release tag and the existing release
version check must pass before building. The metadata generator rejects source
or workflow commit identities that are not full lowercase 40-hex Git SHAs.

`release-provenance.json` binds:

- `source.commit_sha` and `source.ref`;
- `workflow.ref` and `workflow.commit_sha`;
- `workflow.run_id` and `workflow.run_attempt`;
- every produced distribution filename, byte size, and SHA-256.

A release should be treated as invalid if the checked-out revision, tag,
package version, evidence manifest, attestation subject digest, or downloaded
artifact digest disagree.

## SBOM boundary

IDKMesh has no mandatory runtime dependencies in v0.1. The SBOM still records
the root package and preserves both mandatory and optional dependency
declarations. This prevents an empty runtime dependency set from being
mistaken for an absent inventory.

The SPDX file describes declared package dependencies at release time. It does
not claim that build-host packages, operating-system packages, optional
developer tools, or transitive dependencies outside the shipped package are
part of the IDKMesh runtime.

## Feature-availability detection

Artifact attestation support is not silently assumed.

The release workflow:

1. accepts public-repository support directly because GitHub provides artifact
   attestations for public repositories;
2. for a private/internal repository, requires the maintainer to first verify
   that the repository plan supports artifact attestations and then set
   `IDKMESH_ATTESTATIONS_ENABLED=true`;
3. otherwise fails closed before attestation/publication.

This avoids presenting an unexecuted provenance step as evidence.

## Consumer verification

For a downloaded release distribution:

```bash
sha256sum -c checksums.txt
gh attestation verify ./idkmesh-*.whl --repo MSKazemi/idkmesh
gh attestation verify ./idkmesh-*.tar.gz --repo MSKazemi/idkmesh
```

Then inspect `release-provenance.json` and confirm the source commit and
workflow identity are the expected release identities.

A valid checksum proves byte identity. A valid attestation proves that the
declared GitHub workflow produced/attested those bytes under GitHub's
attestation trust model. Neither proves functional correctness, vulnerability
absence, safe behavior, or merge/integration authority.

## Dependency/update policy

- GitHub Actions and Python dependency declarations are scanned weekly by
  Dependabot.
- Security-sensitive third-party Actions must be pinned to immutable full
  commit SHAs; repository tests reject floating tags.
- Routine automated dependency updates exclude semantic major versions.
- Major-version updates require focused compatibility and trust-boundary review.
- A dependency update does not bypass normal tests/review because it is
  automated or signed.
- Known exploitable dependencies may be upgraded outside the routine cadence
  under the vulnerability-response targets in `SECURITY.md`.

## Release gate

Before a release is considered supply-chain complete:

1. tag/package identity check passes;
2. wheel and sdist build and pass `twine check`;
3. SBOM, checksums, and release identity manifest are generated;
4. checksums verify locally in the build job;
5. attestation availability is established;
6. immutable-pinned provenance action succeeds;
7. `gh attestation verify` succeeds for every distribution;
8. the human-gated PyPI publication succeeds;
9. checksums are reverified after artifact download;
10. the three evidence files are attached to the GitHub release.

Failure of any gate fails the release workflow; it must not be converted into
a warning merely to complete publication.
