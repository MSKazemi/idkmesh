# Auto Draft PR Steward

**Status:** Draft PR producer active on `main` via PR #635; evidence/consumer hardening under review  
**Scope:** convert new same-repository development branches into bounded Draft PR coordination records

The Auto Draft PR Steward keeps the branch as the working surface while making
active work visible through a Draft pull request early in its lifecycle.

It does not decide that work is correct, ready for review, or mergeable.

## Lifecycle

```text
new managed branch
 -> steward observes trusted repository metadata
 -> Draft PR shell
 -> contributor/agent keeps pushing to the same branch
 -> normal CI/evidence/review
 -> explicit ready-for-review decision
 -> normal integration decision
 -> source-branch cleanup after durable provenance
```

A branch remains a Git branch after the Draft PR is created. The PR is the
coordination and review record, not a replacement for the branch.

## Trusted execution boundary

The workflow is `.github/workflows/auto-draft-pr.yml`.

It runs only from trusted default-branch workflow code:

- scheduled every 15 minutes;
- after pushes to `main`;
- no non-`main` push trigger;
- no `workflow_dispatch` entry point that could select arbitrary branch code.

Permissions are intentionally narrow:

```yaml
permissions:
  contents: read
  pull-requests: write
```

The workflow never checks out a candidate branch. Candidate code, issue text,
PR text, and commit messages are not executed by the privileged steward.

## Repository prerequisite

The repository must permit its `GITHUB_TOKEN` to create pull requests.

If repository Actions policy denies that capability, the steward fails with an
explicit 403 diagnostic. Do not work around that boundary with a personal
access token or higher-authority secret. Either enable the repository-native
capability deliberately or leave automatic PR creation disabled.

## Machine policy

The behavior is configured in `config/auto-draft-pr.json`.

Important controls:

- `enabled` — global kill switch;
- `not_before` — rollout cutoff so historical orphan refs are not reopened;
- `managed_prefixes` — branch families eligible for Draft PR creation;
- `excluded_prefixes` — evidence, scratch, bot, Jules, or hold lanes that stay
  outside this automation;
- `infer_stacked_base` — prefer the nearest open-PR ancestor for stacked work;
- `max_creations_per_run` — mutation flood cap;
- `max_branch_pages` / `max_pr_pages` — fail-closed pagination bounds;
- `max_untracked_branches_per_run` — bound commit-metadata inspection;
- `max_candidate_evaluations_per_run` — bound ancestry/base evaluation;
- `max_open_pr_heads_for_stack_inference` — bound stacked-base comparisons;
- `minimum_rate_limit_remaining` — shared GitHub API reserve.

The policy loader rejects empty prefixes, overlapping managed/excluded prefixes,
non-positive scan bounds, invalid pagination limits, and unsupported schema
versions. The checked-in policy keeps a 1500-request core API reserve.

## Candidate algorithm

For each run:

1. read the GitHub core API budget;
2. stop without scanning or mutating if the configured reserve would be crossed;
3. list repository branches and complete same-repository PR history within the
   configured pagination bounds;
4. fail closed if open PR heads exceed the bounded stack-inference limit;
5. ignore `main`, excluded prefixes, and every branch that already has any
   same-repository PR history;
6. fail closed if untracked managed branches exceed the inspection bound;
7. ignore heads older than the rollout cutoff;
8. evaluate only the bounded oldest eligible heads so a creation cap does not
   starve older work;
9. infer the nearest current open-PR ancestor when stacked-base inference is
   enabled, otherwise use `main`;
10. require at least one commit ahead of the selected base;
11. re-read the exact branch head immediately before mutation;
12. if the head moved, skip it and reconsider on the next run;
13. create a Draft PR only;
14. treat a concurrent "PR already exists" response as a benign race and record
    the skip.

No direct branch merge is performed.

## Generated PR contract

Generated PRs are always Draft and state that they are coordination records.

The generated title/body:

- sanitize `#` in branch/base ref text so a branch name cannot manufacture an
  issue reference or accidental issue-closing instruction;
- bound the title length;
- record the observed planning head SHA, selected base, and ancestry comparison;
- make no correctness, evidence, approval, or merge-readiness claim.

PRs created by the repository `GITHUB_TOKEN` do not themselves trigger a new
downstream workflow cascade. A later ordinary branch push or human
review-state action provides the normal PR check surface.

## Durable run evidence

Each successful steward invocation can render a versioned evidence bundle without
making any additional GitHub API calls. The contract is
`schemas/auto-draft-pr-steward-report-v0.1.schema.json`.

The trusted workflow writes:

- `steward-report.json` — machine-readable state for automation, CLI, and future
  GUI surfaces;
- `steward-report.md` — human-readable summary of the same result.

Both files are uploaded as a short-retention GitHub Actions artifact named
`auto-draft-pr-steward-<run-id>` for 14 days.

Fourteen days is an **operational retention window**, not a permanent audit
archive. The scheduled steward can run up to 96 times per day, so retaining
every routine snapshot indefinitely would create unbounded artifact inventory.
Evidence that must survive the operational window should be promoted
deliberately to a durable repository record, release artifact, or other governed
archive with its run identity/digest preserved.

The report records:

- repository and generation time;
- SHA-256 of the exact machine policy file used by the run;
- workflow/run/attempt/trusted-head provenance from GitHub Actions;
- explicit authority capabilities, with every integration authority set to
  false;
- completed, blocked, or disabled status;
- API budget observed at run start;
- candidate/planned/created/skipped counts;
- branch/base/head/ancestry records;
- created Draft PR number and canonical GitHub URL;
- skip reasons such as `head_moved` and `pr_already_exists`.

Artifact publication uses the result already held in memory. It does not rescan
branches, reread PR history, or otherwise spend additional GitHub API budget.

A report is evidence about what the steward did, not evidence that the generated
change is correct or mergeable. In particular, the report permanently states
`merge: false` and `auto_merge: false` in its authority block.

## Local/read-only diagnosis

A maintainer with a read-capable GitHub token can inspect the planned actions
without creating PRs:

```bash
GITHUB_TOKEN=... python tools/auto_draft_pr_steward.py \
  --repo MSKazemi/idkmesh \
  --policy config/auto-draft-pr.json \
  --dry-run \
  --output-json /tmp/idkmesh-steward.json \
  --output-md /tmp/idkmesh-steward.md
```

The JSON output includes:

- candidate count;
- planned branch/base pairs;
- created PRs;
- skipped candidates and reasons;
- API budget observed at run start;
- any fail-closed block reason;
- `merge_authorized: false`.

### Inspect a saved report with the installed CLI

After installing IDKMesh, a downloaded evidence artifact can be validated and
summarized completely offline:

```bash
idkmesh steward-report steward-report.json
idkmesh steward-report steward-report.json --details
```

The command requires no `GITHUB_TOKEN`, makes no network request, and has no
mutation path.

For a visual view of the same validated local evidence:

```bash
idkmesh steward-report-ui steward-report.json
idkmesh steward-report-ui steward-report.json --no-browser --port 8766
```

The dashboard binds only to `127.0.0.1`, contains no JavaScript or external
assets, performs no live GitHub request, and exposes no POST/PUT/PATCH/DELETE
mutation endpoint. It shows run status, branch lifecycle outcomes, created Draft
PRs, the explicit authority boundary, policy digest, workflow provenance, and
the raw validated JSON. The same `idkmesh.steward_report` validator runs before
the HTTP server starts, so the CLI and browser surfaces cannot disagree about
whether a report is valid.

### Aggregate multiple saved runs

To understand behavior over time, pass one or more report files or directories
to the offline history command:

```bash
idkmesh steward-history ./downloaded-steward-artifacts
idkmesh steward-history ./run-a ./run-b --details
idkmesh steward-history ./downloaded-steward-artifacts --json --pretty
```

Directory discovery is intentionally conservative: it recursively reads only
files named `steward-report.json`, so unrelated JSON files are not guessed to
be stewardship evidence. Explicit file paths may use a renamed artifact.

Offline ingestion is explicitly bounded and fails closed:

- one report file is limited to 2 MiB and must be a regular file;
- one history invocation accepts at most 128 explicit input paths;
- one history contains at most 1000 unique reports;
- directory discovery traverses at most 8 levels and 10,000 directories;
- directory symlinks are not followed during recursive discovery.

These are resource-safety contracts, not tuning hints. Raising a bound requires
an explicit reviewed contract change rather than silently accepting
unbounded local input.

Every discovered report is validated through the same strict
`idkmesh.steward_report` contract before aggregation. One history must describe
one repository, and duplicate GitHub workflow run/attempt identities are
rejected instead of double-counted.

The machine-readable history contract is
`schemas/auto-draft-pr-steward-history-v0.1.schema.json`. It records:

- the chronological report window;
- completed, blocked, and disabled run counts;
- planned, created, skipped, `head_moved`, and `pr_already_exists` totals;
- minimum/maximum observed API budget;
- distinct policy digests and chronological policy transitions;
- one provenance row per validated run.

Each run also carries a semantic `report_sha256`: SHA-256 over the validated
report serialized as canonical strict JSON. The history carries an
`input_set_sha256` over the full path-independent run projections, including
their report digests, state, counts, API observation, policy digest, and workflow
provenance. Local source paths and JSON key order are excluded from that
identity, so copied evidence can be compared across machines without treating
formatting or filesystem layout as changes.

Runs are ordered by timestamp and then semantic run identity/report digest; the
local source path is only the final presentation tie-breaker for semantically
identical evidence. This prevents same-timestamp policy transitions from changing
merely because artifacts were unpacked under different directory names.

Before text, JSON, or browser rendering, the history validator recomputes
aggregate counts, semantic ordering, API-budget extrema, policy transitions,
workflow-run uniqueness, state/count consistency, and the input-set digest. A
document whose summary and run rows disagree—or whose projection was altered
while aggregate totals were adjusted to match—is rejected rather than displayed.

History aggregation is entirely offline. It downloads no artifacts, polls no
workflow, uses no GitHub token, and exposes no mutation capability.

### Compatibility and schema evolution

The report and history consumers are intentionally fail-closed. They accept only
their exact published v0.1 contracts and reject unknown fields/versions.

Once a schema version is integrated into `main`, its meaning is immutable.
Any incompatible shape or semantic change must publish a new schema identifier
(for example v0.2) and an explicit compatibility path. Existing v0.1 consumers
must never silently reinterpret newer evidence.

This also means an apparently additive field is a versioned contract change:
both v0.1 schemas use `additionalProperties: false` so automation cannot depend
on fields that an older validator would ignore.

The offline readers reject malformed or ambiguous evidence before rendering,
including:

- duplicate JSON keys and Python-only `NaN` / `Infinity` constants;
- unsupported report schema versions or extra contract fields;
- authority blocks that grant merge, approval, deletion, contents-write, or
  other capabilities outside the steward boundary;
- malformed commit SHAs or policy digests;
- created-PR URLs that do not match the report repository and PR number;
- summary counts that disagree with the actual arrays;
- created/skipped outcomes that do not correspond to a planned candidate;
- invalid completed/blocked/disabled state combinations.

This command is the supported local consumer contract for future UI/dashboard
work; consumers should not scrape GitHub workflow logs.

## Troubleshooting

### No PR appears for a new branch

Check, in order:

1. the branch prefix is managed and not excluded;
2. the branch has no same-repository PR history;
3. the current head commit is at or after `not_before`;
4. the branch is ahead of the selected base;
5. the API budget is above `minimum_rate_limit_remaining`;
6. the latest steward run summary for a `head_moved` or other skip;
7. repository Actions policy permits `GITHUB_TOKEN` PR creation.

### The branch is stacked on another branch

The steward selects the nearest open same-repository PR head that is an ancestor
of the candidate. If none is an ancestor, `main` is used.

Base inference is coordination assistance only. A wrong or obsolete stack should
be corrected explicitly in the PR before review.

### A historical branch still has no PR

That is intentional when the branch predates the rollout cutoff or already has
closed/merged PR history. Historical cleanup remains governed by
`docs/planning/BRANCH_CONVERGENCE_POLICY.md`; the steward does not reopen old
work merely to reduce the branch count.

### The steward reports low API budget

No mutation occurred. The run is intentionally fail-closed. Wait for the shared
GitHub API budget to recover rather than lowering the threshold during a busy
automation period.

## Authority boundary

The steward may:

- read repository metadata;
- create a bounded Draft PR.

It may not:

- mark a Draft ready for review;
- approve or dismiss reviews;
- merge or enable auto-merge;
- delete or force-move branches;
- write repository contents;
- close issues;
- mutate labels;
- change repository or Actions settings;
- introduce a PAT/app-secret fallback.

All normal exact-head CI, evidence, independent review, branch protection, and
integration rules remain in force.

## Verification

The deterministic regression suite is
`tests/test_auto_draft_pr_steward.py`. It covers the repository policy contract,
historical/excluded refs, stacked-base inference, fork-name collisions, generated
ref sanitization, title bounds, duplicate-creation races, exact-head movement,
API-budget blocking, oldest-first ordering, the per-run mutation cap, workflow
artifact bounds, policy/provenance digests, report rendering, output-path
collision safety, and instance validation against the published report schema.

The offline history consumer is covered by
`tests/test_steward_history.py`, including conservative discovery, deduplication,
mixed-repository rejection, duplicate workflow-run rejection, chronological
aggregation, policy-transition counts, semantic report/input-set digests,
bounded file/discovery limits, internal aggregate consistency, schema validation,
rendering, and CLI mode contracts.

Use the repository's normal PR gate for integration evidence.
