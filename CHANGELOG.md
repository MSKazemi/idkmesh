# Changelog

Notable changes are summarized here; this is not an exhaustive commit log.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). IDKMesh is
pre-1.0 research software and does not yet follow semantic versioning: contracts under
`schemas/` carry their own explicit versions (for example `work-unit-v0.2`), and those
versions, not the release tag, are what downstream code should depend on.

This file starts at the first public release. Earlier changes remain in git history
and the release notes for that tag.

## [Unreleased]

### Added

- `scripts/demo.py`, a narrated contract tour using the repository's real validators
  and committed synthetic fixtures: three positive checks and four rejection checks.
  It does not run an agent or prove live independence, accepted work, or merge authority.
- `tests/test_demo.py`, including regression checks that unexpected process/programming
  failures cannot count as expected contract rejections. Temporary fixtures keep the
  tests from modifying shared repository evidence.
- `.devcontainer/devcontainer.json`, including both `tests/` and `interop/tests/` in
  the editor's pytest discovery and an automatic fixture demo on attach. Hosted
  environment availability and cost are not guaranteed by this configuration.
- `CITATION.cff` and this changelog.
- `actions/gate-audit/`, the composite Action integrated through PR 395, with an
  exact-head self-test checking report-byte identity and the authority disclaimer.
- Ignore rules for the private files that agents and editors leave in a working
  tree: `CLAUDE.md`, `GEMINI.md`, `.note*`, `.env*`, `*.local`, `.vscode/` and
  `.DS_Store`. None of these were ignored before, so a single `git add -A` would
  have published local configuration or secrets from this public repository.
  `AGENTS.md` is deliberately excluded from the rule and stays tracked.
- `tests/test_private_file_ignore_rules.py`, which asks `git check-ignore` itself
  what `git add` would do rather than parsing `.gitignore`, and asserts the
  `AGENTS.md` exception so a later tidy-up cannot quietly hide the contributor
  contract every coding agent reads.
- `tests/test_patch_verifier_singularity.py`, holding two invariants in the
  unfiltered suite rather than in a path-gated workflow: every
  `experiments/*_patch_verifier.py` is imported by the runner (parsed with `ast`,
  so a name in a docstring cannot fake dispatch), and every workflow reference to
  such a module names one that exists and is dispatched, unless the line asserts
  the module's absence.
- `docs/audits/2026-09-05-orphaned-v04-patch-verifier.md`, recording the trace and
  its re-verification against a later base.

### Changed

- `Task 001 canonical v0.4 calibration` now watches the files it actually reads.
  The calibration runs against the checked-out pull-request head, but its `paths:`
  filter listed only the two calibration tools — so `requirements-phase0.txt`,
  `experiments/evaluator_plan_runner.py`, `experiments/transition_patch_verifier.py`
  and `tests/test_patch_evaluator_transition_v04.py` could all change without the
  calibration that certifies them ever running.
- `tests/test_calibration_path_filter.py` derives that dependency set from the
  workflow's own steps rather than from a second hand-maintained list, and also
  fails if the filter names a file that no longer exists.

- README introduces the synthetic contract demo with virtual-environment setup and
  links the existing contributor invitation. Installation time is environment-dependent.
- Support and issue-template entry points route open-ended questions to Discussions.
- The newer CONTRIBUTING.md instructions from PRs 405 and 408 are preserved rather
  than replaced by another setup sequence.

### Removed

- `experiments/transformation_patch_verifier.py`, the pre-#171 spelling of the v0.4
  patch verifier. It was imported by nothing after #171 rewired dispatch to
  `transition_patch_verifier.py`, but a later commit restored it, so
  `Task 001 canonical v0.4 calibration` failed its provenance guard on every pull
  request touching its paths — seven consecutive runs. No calibration result is
  retracted: dispatch always reached `transition_patch_verifier`. What was wrong was
  the evidence trail, since a `py_compile` step named the orphan as "the calibrated
  evaluator path" and the workflow's `paths:` filter watched it, so editing the
  module the run actually depends on did not trigger the run.

## [research-preview-2026-08-29] - 2026-08-29

First public research-preview snapshot, published as a prerelease. See the
[release notes](https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29)
for the Work Unit, ResultManifest, EvaluatorPlan and VerificationResult foundations,
repository/branch observatories, bounded recommendation layers, synthetic experiments,
and CI security surfaces.

This is research software, not a production-ready distributed agent platform. The
release notes preserve its evidence and independent-review limitations.

[Unreleased]: https://github.com/MSKazemi/idkmesh/compare/research-preview-2026-08-29...main
[research-preview-2026-08-29]: https://github.com/MSKazemi/idkmesh/releases/tag/research-preview-2026-08-29
