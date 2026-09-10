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

- `scripts/free_resource_source_audit.py` and a scheduled workflow reporting freshness of
  every offer in the free-resource registry. `free_resource_planner.py` already drops an
  offer whose evidence has aged past its own `source.max_age_days`, but only when a planning
  run happens to ask; the audit makes the same arithmetic visible on a schedule, so an offer
  about to expire is seen before a planning run silently stops selecting it. It is read-only
  by construction — `permissions: contents: read`, and it never refreshes `checked_at`,
  edits the registry, opens a pull request, or selects an offer, because re-dating an offer
  without a human re-reading its terms is the failure `max_age_days` exists to prevent.
  `--fail-on {never,stale,expiring}` chooses whether freshness gates the run.

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

- The free-resource audit's per-offer date fields are named for whose clock they are on:
  `expires_on` and `days_until_expiry` become `evidence_stale_on` and
  `days_until_evidence_stale`. Both are `source.checked_at + source.max_age_days` — the day
  *our* recorded reading of an offer's terms ages out — and neither says anything about the
  provider; this registry holds no expiry date for any offer. The old name was read as a
  provider deadline within an hour of shipping, and a reviewer nearly reported a free tier
  as lapsing the next day. Renamed now because the only consumer is the tool's own tests
  and no schema pins the output, so the cost will never be lower.

- The open-model benchmark probe reports the model it actually ran, instead of naming one
  from constants in its own source. Identity is now resolved from the producer image's
  recorded digest: an unregistered digest is rejected rather than relabelled, a missing
  identity block is a harness failure, and an expected-digest mismatch aborts. The
  fingerprint covers file names as well as bytes, so swapping two weight files changes it.
- `tests/test_open_model_provenance_binding.py`, including a regression guard asserting the
  probe's source carries no `MODEL_NAME`, `MODEL_REVISION` or written-in manifest id — the
  host cannot observe those, so it may not assert them.

- `tests/test_example_contract_coverage.py` checks that every file named in a
  `NO_SCHEMA_CONTRACT` exemption reason still exists. Those reasons are prose —
  "validated in code by X", "consumed by X" — and prose is not checked, so renaming
  or deleting X silently turned the justification false and left the example with no
  coverage and no record of having lost it. The assertion stops at existence on
  purpose: `idkmesh/gate_audit.py` validates the panel-votes example without naming
  it, because the test is what loads the file and passes it in, so requiring the
  mention would fail a true claim.

- `tests/test_calibration_path_filter.py` reads a `paths:` filter written in any valid
  YAML spelling. Its first parser matched only double-quoted sequence entries, so a
  single-quoted or bare block parsed to nothing and every watched file was then reported
  as unwatched — a purely cosmetic reformat produced a failure that blamed the workflow.
  The same flaw in a one-off script over-counted a repository-wide survey threefold, so
  the parser now also fails loudly if a filter parses to zero entries rather than
  treating an empty result as a finding.

- The GitHub Pages build works again. `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md`
  documented a GitHub Actions concurrency expression inside a `yaml` code fence.
  Jekyll expands Liquid delimiters before Markdown runs, so the fence did not
  protect it: Liquid read the Actions interpolation as one of its own variables,
  found no terminator, and failed the deployment for the entire site. Six
  consecutive Pages builds failed from 2026-09-09T23:53Z, 7307b41 through
  c798726, while every repository test stayed green.
- `tests/test_pages_liquid_safety.py` fails on any unwrapped Liquid delimiter in
  published Markdown, on an unbalanced raw region, and on the scan finding almost
  no files — the last so the check cannot pass vacuously.

- The ACE growth controller no longer lets an unnamed event vote. Its dispatch chain
  seeded `q`/`d`/`r` at 0.05 before branching and had no terminal `else`, so any event
  it does not name — `workflow_dispatch` today, and any `schedule:` added later — fell
  through carrying those seeds. Since `credit` selects the controller's mode (EXPLORE
  at 2, GROW at 8), such an event both scored and opened its own row in the published
  counts table. Unnamed events are now typed `<event>:reconcile` and score zero;
  scoring for every named event is unchanged.
- `tests/test_ace_unnamed_event_credit.py`, which fails if the terminal `else` is
  removed, if it awards any credit, or if the pre-branch seed becomes zero and leaves
  the guard proving nothing.

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
