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
After exact-head CI succeeds, its receipt must be registered separately before
Task 001 is removed from the pending calibration set. Related: #180.
