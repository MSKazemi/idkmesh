# Changelog

All notable changes to IDKMesh are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). IDKMesh is
pre-1.0 research software and does not yet follow semantic versioning: contracts under
`schemas/` carry their own explicit versions (for example `work-unit-v0.2`), and those
versions — not the release tag — are what downstream code should depend on.

This file starts at the first public release. Changes before it are recorded in the git
history and in the release notes for that tag.

## [Unreleased]

### Added

- `scripts/demo.py`, a narrated sixty-second tour of the acceptance contract. It walks one
  bounded task through the real schemas in `schemas/` and fixtures in `examples/`: three
  objects are accepted and four are rejected, including three that report success. It
  reuses the validators in `experiments/harness.py` and `experiments/provenance_integrity.py`
  rather than reimplementing them, and exits non-zero if any rejection stops happening, so
  it is a regression test as well as a demonstration.
- `tests/test_demo.py`, guarding the demo, including a red-green case that weakens the
  self-acceptance fixture and asserts the demo fails.
- `CITATION.cff`, so the project can be cited.
- `.devcontainer/devcontainer.json`, so the project can be tried without a local install.
- This changelog.

### Changed

- `README.md` now opens with a runnable "See it work in sixty seconds" section above the
  status and scope material.
- `CONTRIBUTING.md` now opens with the demo rather than three documents to read first.

## [research-preview-2026-08-29] — 2026-08-29

First public research-preview snapshot, published as a prerelease. See the
[release notes](https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29)
for the full contents, which include the Work Unit, ResultManifest, EvaluatorPlan and
VerificationResult foundations, the repository and branch observatories, bounded
recommendation layers with no merge authority, synthetic experiments, and the CI security
surfaces.

As stated in those notes, this is research software rather than a production-ready
distributed agent platform, and the held-out real coding corpus, external independent-review
gates, and community reproduction experiment were not complete at that point.

[Unreleased]: https://github.com/MSKazemi/idkmesh/compare/research-preview-2026-08-29...main
[research-preview-2026-08-29]: https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29
