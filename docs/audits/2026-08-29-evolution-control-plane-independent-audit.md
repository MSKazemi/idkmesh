# Evolution control-plane independent audit — 2026-08-29

## Scope and independence

This audit answers issue #151. A read-only Codex audit agent, separate from the
implementation agent and instructed not to modify repository or GitHub state,
inspected the current-main workflows, implementation, tests, live run metadata,
and retained artifacts. This is AI-assisted independent review; it does not claim
human or organizational independence.

The initial audit was performed against `origin/main` at `566bee13`. The fixes below
were then implemented on a clean branch and must receive a second exact-head review
and green required checks before integration.

## Initial verdict

The control plane preserved its read-only authority and hard non-compensation
rules, but was not ready to close #151. Five concrete blockers and one documentation
defect were found.

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | Branch-name-only lookup could admit an ordinary PR artifact from a fork branch named `main`. | Selectors now allowlist trusted event types, use a new v2 trust epoch, require one exact unexpired run-bound artifact, and bind API run/head/event provenance in a verified manifest. |
| Medium | State and ledger were only JSON-parsed; unsupported versions and inconsistent counters were accepted. | Strict semantic validation now rejects unsupported versions, non-finite/out-of-range beliefs, inconsistent fitness/counters, authority-policy changes, malformed ledgers, and state/ledger lineage mismatch. |
| Medium | Selected artifact/API/download failures could silently reset history to the repository seed. | API errors, duplicate artifacts, download errors, missing files, manifest mismatch, and semantic invalidity now fail the run. Seed is used only when no eligible checkpoint is selected. |
| Medium | Stale, dismissed, and comment-only reviews could clear the review-coverage guard. | Review evidence is tied to the exact current head, collapsed to the latest state per eligible reviewer, excludes author/bots/comment-only/dismissed records, and separates approval count. |
| Medium | `pull_request_review` directly launched the checkpoint-producing observer. | The privileged trigger was removed; trusted PR lifecycle observation remains on `pull_request_target`, with scheduled refresh for review changes. |
| Low | Portfolio documentation claimed retention of a raw snapshot that the workflow excludes. | Documentation now consistently describes ephemeral raw text and retained derived evidence only. |

## Trust-boundary result

- Live jobs explicitly check out the default branch with `persist-credentials: false`.
- Ordinary PR-head jobs have `contents: read` only and do not restore checkpoints or call the live observer.
- `pull_request_target` observations cannot become canonical checkpoint parents;
  the persistent allowlist is limited to issue, push, manual, and scheduled runs.
- Core external Actions are pinned to immutable 40-character commits.
- Issue and PR text is parsed as data and is never passed to a shell or evaluator.
- Checkpoint selection does not infer trust from the branch name: ordinary
  `pull_request` runs are excluded even if their head branch is named `main`.
- Checkpoint manifests bind repository, workflow, run ID, head SHA, event name,
  optional parent run, exact file set, byte size, and SHA-256 digest.

## Persistence and concurrency result

- All pages of successful runs are searched server-side with ordinary PR runs
  excluded; only allowlisted events with one exact, unexpired artifact are candidates.
- A selected artifact is mandatory: download, file presence, manifest, or semantic
  validation failure aborts without publishing a successor.
- Bayesian event counts must equal both cumulative activity-count maps; the latest
  retained event must match state, and the ledger remains bounded.
- Portfolio controller arms, weights, probabilities, and Bayesian health inputs
  receive finite/range/version checks before use.
- Static repository-level concurrency groups retain one latest-state successor model.
  The observer remains explicitly non-lossless during event bursts.

## Mathematical and governance result

- Live blockers remain conjunctive and cannot be compensated by posterior history,
  Pareto rank, UCB opportunity, popularity, or activity volume.
- Stars, forks, and raw comment counts remain excluded from the scoring result.
- The portfolio remains advisory. Neither workflow can approve, merge, label,
  assign, mutate branches/settings/rulesets, read secrets, authorize spend, or
  amend constitutional policy.
- `autonomous_merge` is validated as false and
  `constitutional_changes_require_review` as true in restored Bayesian state.

## Artifact minimization result

The portfolio checkpoint retains derived state, ranked features, report, policy,
and integrity provenance. It does not retain the raw repository snapshot or raw
issue/PR bodies. Exact historical replay therefore requires reacquisition or a
separately governed evidence-retention contract.

## Verification required for closure

The implementation branch adds regression coverage for fork-head branch-name
collisions, exact artifacts, fail-closed restoration, manifest tampering,
unsupported/forged state, ledger mismatch, current-head review evidence, and raw
snapshot exclusion. Issue #151 is closable only after the PR's exact head is
independently reviewed, its current-main diff is inspected, and required checks
are green for that same SHA.
