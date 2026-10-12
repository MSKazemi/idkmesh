# GitHub Workflow Runner v0.1

**Status:** experimental implementation contract  
**Issue:** #596 (runner slice that follows C8-D; the issue checklist's own C8-E owner-action item is a separate, still-open slice)  
**Authority:** `preview` and `status` are read-only. `dispatch` and `verify` fail
closed. No phase dispatches work, publishes an issue comment, reads a provider
secret, accepts a candidate, pushes, or merges.

## Purpose

The four workflows rendered by `idkmesh init --github` (see
[GitHub Bootstrap Workflow Wrappers](GITHUB_BOOTSTRAP_WORKFLOW_WRAPPERS_V0_1.md))
each run exactly one command from the pinned IDKMesh runtime:

```text
python -m idkmesh.cli github-workflow {preview,dispatch,verify,status}
```

`idkmesh/github_workflow_runner.py` implements that command and the `IDKMESH_*`
environment contract the wrappers pass. It is stdlib-only because the wrappers
install nothing after `setup-python`; a test parses the module's imports to keep
it that way.

## What each phase does

| Phase | Wrapper | Behavior |
| --- | --- | --- |
| `preview` | `idkmesh-preview.yml` | Reads one issue, reads `.idkmesh/project.json` from the trusted checkout, and prints a deterministic WorkUnit preview and digest. Performs no dispatch. |
| `status` | `idkmesh-status.yml` | Reads one run's durable ledger records, verifies the append-only chain, and prints the bounded status body. Publishes no comment. |
| `dispatch` | `idkmesh-dispatch.yml` | Fails closed with `dispatch_unavailable`. Reads no environment variable and no secret. |
| `verify` | `idkmesh-verify.yml` | Fails closed with `verify_unavailable`. Reads no environment variable, candidate, or secret. |

### Why dispatch and verify fail closed

The existing explicit-dispatch boundary
(`idkmesh.github_explicit_dispatch`, `idkmesh.github_dispatch_authorization`)
presupposes retained webhook-delivery state in a local metadata store, a
verified actor-authorization envelope, and a provider connector with a resolved
credential. A stateless Actions runner has none of the three, and wiring them in
would be new authority design, not a runner. Independent verification likewise
needs a verifier the runner cannot supply. Returning success from either phase
would be a vacuous green, so they refuse with a stable code instead. Enabling
them is a separate, reviewed slice.

### Why status publishes no comment

`sync_github_run_status_comment` keeps one comment per run by reserving
publication in a retained local store. A fresh Actions runner starts with an
empty store, so every run would create another comment. `status` therefore
renders the same bounded body, prints it, and appends it to the job summary
(`GITHUB_STEP_SUMMARY`) when GitHub provides one. The wrapper keeps
`issues: write` for the later comment slice; this runner does not use it.

## Environment contract

Every phase requires `IDKMESH_PROJECT_ROOT` (an existing directory containing
the trusted checkout), `IDKMESH_REPOSITORY` (`owner/name`), `IDKMESH_BASE_SHA`
(40 or 64 lowercase hex), and `IDKMESH_RUN_ID` (the numeric Actions run id).
Values with control characters are rejected. No other variable is read, apart
from the optional `GITHUB_STEP_SUMMARY` that Actions itself sets.

| Variable | `preview` | `status` |
| --- | --- | --- |
| `IDKMESH_ISSUE_NUMBER` | required, `[1-9][0-9]{0,9}` | required |
| `IDKMESH_GITHUB_TOKEN` | optional; used only as the bearer for the fixed GitHub API host, and not read at all with `--issue-json` | required unless `--ledger-records` is used |
| `IDKMESH_EVENT_PATH` | optional; only `issue.number` is read and must equal the issue number | not read |
| `IDKMESH_RUN_REFERENCE` | not read | required; the ledger run id |

The token is the workflow's own `github.token`, held read-only by these jobs. It
is never printed, stored, or placed in the result.

## `preview`

1. Validate the environment.
2. If the event file is present, fail with `event_issue_mismatch` when its
   `issue.number` differs. Issue titles, bodies, and labels from the event are
   never read.
3. Load `.idkmesh/project.json` (regular file, not a symlink, at most 1 MiB).
4. Derive the policy (below).
5. Fetch the issue through `GitHubRestIssueSource` (or `--issue-json`), then call
   `preview_github_issue_work_unit` with `IDKMESH_BASE_SHA` as the exact source
   revision.

### Policy comes from the project, never the issue

| `GitHubIssueWorkPolicy` field | Source |
| --- | --- |
| `repository` | `IDKMESH_REPOSITORY` |
| `kind` | `coding`; the manifest's `allowed_work_unit_kinds` must include it |
| `risk_class` | `risk_policy.maximum_autonomous_risk` (`none` is refused) |
| `allowed_paths` | `metadata.github_issue_preview.allowed_paths` (required) |
| `forbidden_paths` | `metadata.github_issue_preview.forbidden_paths` plus, always, `.github/**` and `.idkmesh/**` |
| `required_capabilities` | `git`, `coding-agent`, plus the manifest's `worker_constraints.required_capabilities` |
| everything else | `GitHubIssueWorkPolicy` defaults (network `none`, no secrets, no paid fallback) |

The runner also refuses any project whose `integration_policy` allows automatic
merge or waives the human decision.

**A freshly bootstrapped project cannot preview yet.** The C8-C seed carries no
write scope, so `preview` fails with `preview_scope_unconfigured` until the
owner adds, for example:

```json
"metadata": {
  "github_issue_preview": {
    "allowed_paths": ["src/**", "tests/**"],
    "forbidden_paths": ["SECURITY.md"]
  }
}
```

Choosing where an automated candidate may write is an owner decision, so the
runner does not guess a default. A fresh-repository fixture that walks
bootstrap to preview belongs to C8-G.

### Output safety

Issue text reaches the WorkUnit objective but never the human output or the job
summary, which carry only identifiers, digests, and project-configured paths.
`--json` output is one compact line, so a hostile issue body cannot start a
line with `::` and inject a workflow command into the log.

## `status`

1. Validate the environment and project manifest.
2. Read the run's records: from `--ledger-records` (a JSON array), or from the
   `idkmesh-ledger` branch through `GitHubLedgerBranchStore`.
3. Verify the complete append-only chain with `serialize_github_ledger_chain`.
4. Project the latest record into `GitHubRunStatus` and render the body with
   `render_github_run_status_comment`.

The live path wraps the Git-data transport so that only `get_branch_head`,
`get_commit_tree`, `get_tree`, and `get_blob` exist; any other call raises
`read_only_violation`. It also observes the branch first, because
`GitHubLedgerBranchStore` would otherwise initialize a missing ledger branch,
which is a write. A missing branch is reported as `ledger_unavailable`.

A record that belongs to another repository, a broken chain, or a record that
cannot be projected is `ledger_invalid`; a run with no records is
`ledger_run_not_found`. The record carries no issue number, so the issue binding
is the dispatcher's `IDKMESH_ISSUE_NUMBER` input.

## CLI and exit codes

```bash
idkmesh github-workflow preview --issue-json issue.json --json
idkmesh github-workflow status --ledger-records ledger.json --json
```

Success exits 0. Every refusal prints `error: <code>: <message>` on stderr and
exits 2. Results carry `dispatch_performed: false`,
`github_mutation_performed: false`, and `secret_values_accessed: false`.

## Stable error codes

| Code | Meaning |
| --- | --- |
| `invalid_environment` | A required `IDKMESH_*` variable is missing, malformed, or points at an unreadable file |
| `project_policy_missing` | `.idkmesh/project.json` is absent |
| `project_policy_invalid` | The manifest is unreadable, oversized, a symlink, allows automatic merge, or has an unusable scope/risk |
| `preview_scope_unconfigured` | `metadata.github_issue_preview.allowed_paths` is not set |
| `event_issue_mismatch` | The triggering event concerns a different issue |
| `issue_unavailable` | The issue could not be read or normalized (includes the connector error code) |
| `preview_refused` | The issue is closed, locked, or over the configured bounds |
| `ledger_unavailable` | The ledger branch or transport could not be read |
| `ledger_invalid` | The ledger chain or latest record is inconsistent |
| `ledger_run_not_found` | The run has no ledger records |
| `read_only_violation` | A mutating Git-data call was attempted through the status transport |
| `dispatch_unavailable` | `dispatch` fails closed |
| `verify_unavailable` | `verify` fails closed |

## Tests

`tests/test_github_workflow_runner.py` renders the real wrappers through
`cli.main(["init", "--github", "--dry-run", ...])`, builds each phase's
environment from the names the wrapper declares, and asserts that the runner
accepts it, reads nothing the wrapper does not declare, and names any missing
variable. It covers the policy derivation, hostile issue text, the symlink and
size bounds, the read-only ledger transport, and that `dispatch` and `verify`
touch no environment. No test calls GitHub.

## Non-goals

- Dispatching work, resolving a provider secret, or creating a candidate.
- Verifying, accepting, approving, pushing, or merging anything.
- Publishing or updating an issue comment.
- Writing repository files or changing repository settings.
- Reading a pull request or the head of a candidate branch.

## Follow-on

- Stateless explicit dispatch, behind its own reviewed authority design.
- Independent verification of an exact candidate revision.
- Idempotent comment publication once a retained idempotency source exists.
- Owner-action checklist and safe apply/re-run (C8-E checklist item, C8-F).
- Fresh-repository bootstrap-to-preview fixture (C8-G), including the write
  scope step above.
