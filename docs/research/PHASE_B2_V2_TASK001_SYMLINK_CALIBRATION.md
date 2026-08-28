# Task 001 Symlink-Boundary Calibration

## Question

Can the evaluator distinguish rejecting a direct repository symlink before
resolution from checking `is_symlink()` only after `.resolve()` has erased the
link identity?

## Novelty and proxy audit

The frozen Task 001 defect is not the already-solved historical cohort-path
escape. Repository history and pull-request search found no published repair
for this direct in-repository symlink case at source
`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`.

The initial proxy required only an added `is_symlink()` and removal of the
single-line resolve assignment. An inert change can split the resolve across
two lines, move/reword the existing post-resolution symlink check, and satisfy
both markers while still accepting a direct symlink. The proxy is therefore
ordering-insensitive and Goodhartable.

The mutable pre-freeze plan now requires three transition markers:

1. construct an unresolved repository path;
2. reject that unresolved object when it is a symlink;
3. resolve only after the rejection.

Plan digest:

`sha256:b6e3b0bc2627b3600a7a91ec5bd647d800d612228acb7c721795dc2ab0c5ab5e`

## Behavioral calibration

The separate evaluator-owned matrix checks an ordinary repository file, a
direct symlink to that file, parent traversal, an absolute path, and a missing
file. The straightforward candidate must preserve normal file resolution and
all existing boundary failures while rejecting the symlink. The inert decoy
must reproduce the vulnerable symlink acceptance and be rejected by the
corrected metadata proxy.

The workflow checks out exact frozen source without credentials, emits bound
ResultManifest and VerificationResult artifacts, and has read-only repository
permissions. It does not publish the production repair or a scored outcome.

## Exact calibration evidence

PR #235 exact head `8b9e4a238853b92d9546d06f36066283e5816bdb` passed:

- run `33221041390`, job `99014922387`;
- artifact `9705160930`;
- artifact ZIP `sha256:875c5fe2e444d15c91b1cd53b3ec5f06cf35f3a7986935d03ea4373d0b394c81`;
- straightforward ResultManifest `sha256:2bcf82bb7893ab1f49ba6e1ac757b236ac581fcc1e5e0a298226556f30bb3285`;
- straightforward VerificationResult `sha256:76d466dce4490528e43645990a5ae5606036ff2cbb54a0bdfbff3b504d9f0783`;
- inert-decoy ResultManifest `sha256:65c1802dfae66b24eb7fba29cd8b63b3555ad710f45880b8387ddea3ff1af6ac`;
- inert-decoy VerificationResult `sha256:948da8a76b71739d942eeaee5648defbe2d0b5681b5fdc72f8f356ad8ac92137`.

PR #235 merged as `b6505bd624f7e6a2b9285a9fe936288ea3920e4d`. With the
receipt registered, all five calibration gates are complete and
`freeze_ready=true`. This does not freeze the scaffold: it remains
`stage=scaffold`, has no `definition_digest`, and contains no scored outcomes.
The active predecessor cohort must still complete or be explicitly retired,
and a fresh novelty audit remains required before a separate freeze decision.
Related: #180.
