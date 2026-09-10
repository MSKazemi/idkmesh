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

- `tests/test_documented_hook_snippets.py`, holding the copy-pasteable hook setup in
  `docs/TESTING.md` to what a reader can actually run: the settings block must parse as
  JSON and declare `hooks`, each shell block must parse under `bash -n`, each must go
  through `scripts/testkit.py` rather than calling pytest directly, and every script the
  settings block registers must be one the section shows the reader how to create. That
  last check is made against the section's prose with the fenced blocks stripped — run
  against the whole section it passed a renamed command happily, because the path it was
  looking for was still there, in the very block under test.

- `tests/test_documented_tier_scopes.py`, comparing the tier scopes `docs/TESTING.md`
  publishes against the marker expressions `scripts/testkit.py` actually passes to pytest.
  The expressions are read out of the script with `ast`, so a marker named only in one of
  that file's many comments cannot be mistaken for one that runs. The comparison is
  asymmetric on purpose: every expression a tier runs must appear somewhere in the
  document, and every expression the tier *table* publishes must be one a tier runs, while
  prose elsewhere stays free to show teaching examples. Absolute test counts are
  deliberately not pinned — those rot on a third of commits, the failure
  `tests/test_documented_test_counts.py` records at length; a marker expression changes
  only when someone moves a tier boundary on purpose.

- `tests/test_nightly_tier_has_something_to_run.py`, guarding the precondition that makes
  `scripts/testkit.py`'s nightly tier meaningful. That tier treats pytest's exit 5 — "no
  tests matched the marker" — as a pass, which is right for a repository with no simulation
  tests and wrong for this one, where `-m "sim or slow"` selects 369. If the tier markers
  were ever deleted or renamed, nightly would report success having run none of them. The
  scan reads `pytestmark` assignments with `ast`, so a marker named only inside a string
  literal is not mistaken for one that is applied.

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

- `docs/TESTING.md` stops presenting a local setup as repository content. Its automation
  section described `.claude/settings.json` and two hook scripts as though a contributor
  could open them; `.gitignore` excludes `.claude/`, deliberately, because it holds
  per-agent configuration and personal notes, so those files are in nobody's checkout and
  no `git pull` will bring them. The section now says so and reproduces all three files in
  full, which is the only way the page can hand them over. Its verification claim is scoped
  to match: the snippets were checked against a deliberately failing test — green tree exit
  0, red tree exit 2 with the failure on stderr, `"stop_hook_active":true` exit 0 so an
  unfixable failure blocks once instead of looping — in the checkout where they were
  authored, which the suite cannot re-check for a file it does not contain. The section's
  counts were re-measured too: 418 tracked `.md` files, not 398, and 1320 tracked files
  (~29 MB), not 1232.

- `scripts/testkit.py` no longer prints `PASS` on a run that exits 1. A tier fails for two
  independent reasons — red tests, or a blown CPU budget — and the previous fix routed the
  exit code and the result cache through `tier_passed` so they could not disagree. The
  status word on the summary line was a third consumer and kept reading `result.ok`, so a
  green suite that overran its ceiling printed
  `[testkit] unit: PASS in 100.0s wall / 100.0s cpu (budget 90 cpu-s)` and then exited 1.
  The `BUDGET EXCEEDED` explanation goes to stderr, which a hook capturing the streams
  separately, a CI log pane, or `--quiet` need not show beside stdout — so the one line a
  human was guaranteed to read was the wrong one. All three now derive from `tier_passed`,
  and `tests/test_testkit_budget_cache.py` asserts the printed word against the exit code
  across all four green/red x under/over-budget combinations.

- The unit tier's budget headroom is recorded honestly in `scripts/testkit.py`. The comment
  above `BUDGETS` still described a ~36 CPU-second suite with roughly 2.5x headroom; the
  suite has grown from 870 tests to 1865 and the tier measured 65.0 CPU-s on 2026-09-10,
  which is 72% of the 90 CPU-s ceiling. Recorded, deliberately not acted on: the documented
  response to a tight budget is to make the suite cheaper, never to raise the number.

- `docs/TESTING.md` no longer misstates what the gates run. Four claims had drifted, two
  of them wrong on the day the document landed. The unit tier's scope was published as
  `-m "not sim"` while the code it describes has always run `-m "not sim and not slow"`,
  so the column a contributor reads to learn what their pre-commit gate covers named a
  filter no tier uses. The prose asserted that `nightly` is equivalent to `integration`
  because no test carried `@pytest.mark.sim` — while the baseline table one section above
  it already recorded 369 deselected tests. 311 tests carry `sim` today and
  `-m "sim or slow"` selects 369, every one of which runs only in the scheduled tier. The
  workflow-hardening section still said that work was "**not** on `main` yet"; all 51
  workflows now carry a `concurrency` group, a `cancel-in-progress` value and
  `timeout-minutes`, pinned by `tests/test_workflow_ci_hygiene.py`. The measured baseline
  was re-taken: 1865 collected, 1494 passed / 2 skipped / 369 deselected / 3000 subtests,
  65.0 CPU-s against a 90 CPU-s budget, on 4 cores at load average 1.02 — recorded because
  the document's own argument for CPU-seconds is that a figure without its load is not
  comparable to one taken elsewhere.

- Seven more guards fail when they inspect nothing. An AST audit of `tests/` found every
  test that asserts inside a loop over a discovered set — a glob, a directory listing, a
  regex scan — with no check that the set was non-empty. Each now counts what it inspected
  and fails on zero: SHA-pinning of external actions (13 today), sitemap `lastmod` and
  `priority` (325 entries each), the sim-module test list (25), starter-task rendered links
  and blob-root targets, and catalogue path references. Without the counter, a pattern that
  stops matching turns the check into a silent pass.

- The workflow-hygiene guard's `cancel-in-progress` check fails when it inspects nothing.
  It iterated whatever its pattern matched, so a reformat as small as a space before the
  colon dropped it from 49 inspected values to 0 while the file still reported "4 passed" —
  only the subtest count moved, from 154 to 105, and nobody reads subtest counts. The
  sibling timeout check already counted its work; this one now does too.

- `scripts/testkit.py` caches the gate verdict rather than only whether the tests were
  green. A tier that passed its tests but blew its CPU budget exited non-zero while writing
  `"ok": true` to the result cache, so the next invocation on an unchanged tree
  short-circuited to "cached pass" and exited 0 — a failed gate turning green on the second
  run, which disarms the budget for as long as nothing changes. The exit code and the cache
  now both derive from one `tier_passed()` helper, so they cannot disagree.
- `tests/test_testkit_budget_cache.py` guards that: the tier verdict, the cache contents
  after a budget failure, the second-run short-circuit, the `auto` tier sharing it, and that
  a Markdown, YAML or Python edit each move the cache fingerprint.

- The scheduled-delay note on the free-resource audit is corrected. It quoted a 12-run
  sample min/max as a predicted window of "10:15–11:30 UTC"; the next scheduled run started
  at 11:31:34, 94 seconds outside it. A sample min/max is not a bound — the chance the next
  observation falls outside n prior ones is roughly 2/(n+1) — so the note now gives the mean
  (4.6 h over 21 runs of three workflows) as the expectation and says plainly that a run
  later than any yet seen is not a fault either.

- The free-resource audit's `schedule:` block records that its cron time is nominal.
  Measured over 12 scheduled runs of two unrelated workflows on 2026-09-10, GitHub started
  them 3.85–5.15 h after their cron expression (mean 4.49 h), so this job is expected around
  10:15–11:30 UTC rather than 06:23, and its absence at the nominal minute is not a fault.
  Re-tuning the expression cannot move the start; the delay is on GitHub's side.

- The free-resource freshness report is written to the GitHub job summary, not only to the
  step log. `--fail-on stale` turns the run red once evidence has *already* aged out, but
  the warning window — the state this audit exists to catch — lands on a run that is green,
  and nobody opens the log of a green run. The report now appears on the run page itself,
  with a note that a WARN line means our recorded reading is ageing, not that anything
  expires at the provider. The step captures the report before re-raising the tool's exit
  status, because the tool prints in full and then exits non-zero; summarising only on
  success would drop the report exactly when it matters most.

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
