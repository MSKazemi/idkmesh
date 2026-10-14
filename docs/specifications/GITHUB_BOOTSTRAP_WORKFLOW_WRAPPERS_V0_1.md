# GitHub Bootstrap Workflow Wrappers v0.1

**Status:** experimental implementation contract  
**Issue:** #596 / C8-D  
**Authority:** rendering only; no filesystem write, GitHub mutation, secret
resolution, dispatch, verification, approval, push, or merge authority. The
rendered workflows themselves hold none of those authorities either, beyond the
narrow, explicit permissions listed below.

## Purpose

C8-D turns the deterministic C8-A bootstrap file plan into the four thin GitHub
Actions wrappers a target repository would commit to run IDKMesh without an
always-on server.

The renderer lives in `idkmesh/github_bootstrap_workflows.py`. It consumes a
validated `GitHubBootstrapPlan` and emits exactly these files, reusing the C8-C
`BootstrapRenderedFile` shape (path, ownership, overwrite policy, UTF-8 content,
byte size, SHA-256 digest):

| File | Effect (from the plan) | Trigger |
| --- | --- | --- |
| `.github/workflows/idkmesh-preview.yml` | `none` | `issues: labeled` gated on the `idkmesh:preview` label, or manual dispatch |
| `.github/workflows/idkmesh-dispatch.yml` | `candidate_dispatch` | manual dispatch only |
| `.github/workflows/idkmesh-verify.yml` | `verification` | manual dispatch only |
| `.github/workflows/idkmesh-status.yml` | `publication` | manual dispatch only |

All four are `idkmesh_managed`: a later safe re-run (C8-F) may replace one only
while it still matches its retained generated digest.

## Thin by construction

A wrapper contains no orchestration logic. Each one:

1. checks out the trusted project revision (`persist-credentials: false`);
2. checks out `MSKazemi/idkmesh` at the bootstrap plan's `--idkmesh-ref` (a
   release tag or full SHA) into `.idkmesh-runtime`;
3. sets up Python;
4. probes that the pinned runtime provides the runner entry point and fails
   closed if it does not;
5. runs one command, `python -m idkmesh.cli github-workflow <phase>`, with the
   runtime directory as the working directory so a same-named package in the
   project checkout cannot shadow the pinned IDKMesh.

Event data reaches the runner through `IDKMESH_*` environment variables only.
No expression is ever interpolated into a shell script, and no workflow reads
issue titles, issue bodies, comment bodies, or head refs.

## The runner and its environment contract

The runner is `idkmesh github-workflow {preview,dispatch,verify,status}`,
implemented in `idkmesh/github_workflow_runner.py` and specified in
[GitHub Workflow Runner](GITHUB_WORKFLOW_RUNNER_V0_1.md). `preview` and `status`
are read-only; `dispatch` and `verify` fail closed with `dispatch_unavailable`
and `verify_unavailable`. Step 4 above still exists so that a wrapper pinned to
an older ref that predates the runner fails loudly with
`The pinned IDKMesh ref does not provide the github-workflow runner.` instead
of succeeding vacuously. Because apply mode is still disabled, nothing renders
these files into a repository today; they appear only in dry-run output.

The environment names the wrappers pass are the interface the runner
implements (`tests/test_github_workflow_runner.py` builds each phase's
environment from the names the rendered wrapper declares): `IDKMESH_PROJECT_ROOT`, `IDKMESH_REPOSITORY`, `IDKMESH_BASE_SHA`,
`IDKMESH_RUN_ID`, `IDKMESH_GITHUB_TOKEN` (preview, dispatch, status),
`IDKMESH_ISSUE_NUMBER`, `IDKMESH_EVENT_PATH` (preview), `IDKMESH_WORK_UNIT_DIGEST`
and `IDKMESH_CONNECTOR_ID` (dispatch), `IDKMESH_WORK_UNIT_DIGEST`,
`IDKMESH_CANDIDATE_SHA` and `IDKMESH_CANDIDATE_DIR` (verify), and
`IDKMESH_RUN_REFERENCE` (status). Changing any of them is a coordinated change
to the renderer, this specification, and the runner.

## Security properties

Every property below is asserted by `tests/test_github_bootstrap_workflows.py`;
most are also enforced by the repository's own governance linter
(`idkmesh.github_governance_preflight.lint_workflow_text`, see
[GitHub Governance Preflight](GITHUB_GOVERNANCE_PREFLIGHT_V0_1.md)), which finds
nothing in any rendered wrapper.

- **Immutable Action pins.** Every `uses:` is a full 40-hex commit SHA with the
  upstream tag in a trailing comment (`actions/checkout` v4,
  `actions/setup-python` v5). One Action resolves to one SHA across the pack.
- **Pinned IDKMesh runtime.** The runtime checkout `ref:` and a header comment
  both carry the explicit bootstrap ref. Floating refs are already rejected by
  the C8-A plan.
- **Least privilege.** Workflow-level `permissions: contents: read`; each job
  restates its own set. Only the status job holds a write permission
  (`issues: write`, for its status comment). No job has `contents: write`,
  `pull-requests: write`, `id-token`, or administration access.
- **No privileged triggers.** No `pull_request`, `pull_request_target`,
  `workflow_run`, `push`, or `schedule` trigger. Dispatch, verify, and status
  are manual; preview is read-only and label-gated.
- **Protected-branch only.** Every job runs only when `github.ref` is the
  plan's integration branch, so project policy is read from the protected
  branch, never from an arbitrary dispatched ref.
- **Secrets only where owner approval gates them.** Only the dispatch job
  references a secret, in one step, and is bound to the `idkmesh-dispatch`
  environment so release depends on the owner's configured protection. The
  secret names are derived from the C8-C connector seed's `env:` references, so
  the profile and the wrapper cannot drift. No value is ever read or rendered.
- **Untrusted candidate is data.** The verify job validates the candidate SHA
  against `^[0-9a-f]{40}$` before fetching it, checks it out into a separate
  directory with no persisted credentials, and holds read-only permissions, no
  token, and no secrets.
- **No integration authority.** No wrapper enables auto-merge, pushes, merges,
  approves, or accepts. Dispatching produces a candidate; verification
  produces a recommendation; neither is integration.

A governance integration check evaluates the rendered dispatch wrapper against
the committed `governance-pass-v0.1.json` fixture for the
`secret_bearing_dispatch` and `high_risk_dispatch` operations, and the other
three wrappers for `read_only`; all are allowed.

## Dry-run integration

`idkmesh init --github --dry-run` now also reports the four wrappers. The JSON
form adds `rendered_workflow_files` beside `rendered_config_files`, with exact
content, digest, size, ownership, and overwrite metadata. The human form prints
a `rendered C8-D workflow wrappers:` list of paths and digests. Zero writes,
zero GitHub mutation, zero secret access; apply mode stays fail-closed.

## Failure semantics

Rendering fails closed with `BootstrapRenderError` when:

- the object is not a `GitHubBootstrapPlan`;
- the plan's C8-D file set differs from the four expected paths
  (`workflow_plan_mismatch`);
- the connector seed carries a secret reference that is not `env:NAME` with an
  upper-case name (`invalid_secret_reference`);
- a renderer returns text that is not tab-free and newline-terminated.

A plan/renderer mismatch is never treated as permission to omit or add a
workflow.

## Non-goals

This slice does not:

- implement the `github-workflow` runner (see the runner specification) or any
  preview, dispatch, verification, or status behavior;
- write files, create directories, or apply anything;
- create the `idkmesh-dispatch` environment, labels, secrets, or branch
  protection (C8-E owner actions);
- run the workflows or call GitHub;
- add observation or recovery workflows (named in
  [GitHub-First Operations](GITHUB_FIRST_OPERATIONS_V0_1.md) as later work);
- automatically chain status from other workflows.

## Follow-on

- **Runner:** done for `preview` and `status`; `dispatch` and `verify` remain
  fail-closed until a stateless authority design exists (see the runner
  specification).
- **C8-E:** done; see the owner-action checklist
  ([environment, label, secrets, protection](../operations/GITHUB_BOOTSTRAP_OWNER_ACTIONS_V0_1.md)).
- **C8-F:** done; safe apply/re-run using the digests rendered here
  ([Safe Apply](GITHUB_BOOTSTRAP_SAFE_APPLY_V0_1.md)).
- **C8-G:** done; `tests/test_github_bootstrap_fresh_repo.py` installs these
  wrappers into a bare repository and runs the runner with the environment they
  declare (see the runner specification's Tests section).
- Refresh the two Action pins when upstream releases move; the pack's shape
  tests do not pin the values.
