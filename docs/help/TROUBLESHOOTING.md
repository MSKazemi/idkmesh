---
description: "User and contributor troubleshooting for IDKMesh installation, local run state, Control Tower HTTP, verifier evidence, local-loop, sandbox admission, and test gates."
---
# IDKMesh troubleshooting and operator help

**Source checked:** `main@bee77a6125dbccb58f166ec363e978cd960f43f3` (2026-10-11). This is a **local/reference** troubleshooting guide, not hosted-service operations support. Commands and flags are source-backed in [the CLI/HTTP reference](../reference/CLI_HTTP_QUICK_REFERENCE.md) and `idkmesh --help`; behavior or compatibility on unmerged PRs is not assumed.

## Identify which path you are using

| Goal | Correct entry point | What it does **not** do |
| --- | --- | --- |
| Evaluate multiple reviewers | `idkmesh gate-audit INPUT` | Run reviewers or decide acceptance |
| Plan adoption in another GitHub repository | `idkmesh init --github --dry-run --idkmesh-ref REF` | Write files, apply a workflow, or mutate GitHub |
| Preview what a saved issue file would become, on your machine | `idkmesh work preview --issue-json FILE --repository OWNER/NAME --source-revision SHA` | Fetch from GitHub, dispatch, or write files |
| Preview an issue or read run status from a generated GitHub workflow | `idkmesh github-workflow preview` / `status` | Dispatch, verify, comment on an issue, read provider secrets, or merge |
| Persist/read local run state | `idkmesh run create/list/status/evidence/cancel` | Execute/cancel a provider process |
| Execute the bounded two-attempt reference demo | `idkmesh local-loop CONFIG` | Record a human decision or automatically replay |
| Inspect existing evidence in a browser | `idkmesh control-tower` | Publish APIs externally, dispatch workers, push, or merge |

## Installation and setup

| Symptom | Likely boundary | What to check |
| --- | --- | --- |
| `idkmesh: command not found` | Executable installed in another Python environment | Activate your virtual environment; run `python -m pip install -e .`; inspect `python -m pip show idkmesh`. |
| Python installation rejected | Package requires Python **3.11+** | Confirm `python --version` and run pip with that interpreter. |
| `No module named jsonschema` during `local-loop` | Real schema verifier is an **optional** extra | From checkout root: `python -m pip install -e '.[verify]'`. The base gate-audit remains dependency-free. |
| `local-loop` says it needs a repository checkout | `experiments/` is **not** inside the installed wheel | Clone the source repository and invoke from the checkout, retaining `experiments/`, `examples/`, and `verification/`. |
| `local-loop` output directory exists and is not empty | Replay/evidence bundles are intentionally not overwritten | Supply a new repository-relative `--output-dir` under `results/`; keep old evidence for audit. |
| `init` says apply mode is not implemented | `init` only supports GitHub **dry-run** planning | Include both `--github` and `--dry-run`, plus a pinned `--idkmesh-ref`. Inspect rendered plan and owner-only steps; do not assume files were written. |

The documented developer test setup uses `make setup` on POSIX hosts, followed by `make smoke`, `make gate`, `make test`, or `make integration` according to [testing instructions](../TESTING.md). For platforms without a suitable Make environment, create a Python virtual environment and use the direct `python -m pytest -q` path. **Do not** use `python -m unittest discover` as a proxy for the canonical suite: it misses pytest module-level functions.

## GitHub workflow runner

`idkmesh github-workflow` runs inside the workflows that `idkmesh init --github` renders. A refusal prints `error: <code>: <message>` on stderr and exits 2. See [GitHub Workflow Runner](../specifications/GITHUB_WORKFLOW_RUNNER_V0_1.md) for the full list.

| Symptom | Interpretation | Action |
| --- | --- | --- |
| Wrapper fails at "Require the pinned IDKMesh GitHub workflow runner" | The pinned `--idkmesh-ref` predates the runner | Bootstrap again with an `--idkmesh-ref` that contains `idkmesh github-workflow`. |
| `preview_scope_unconfigured` | The bootstrap seed deliberately has no write scope | Set `metadata.github_issue_preview.allowed_paths` in `.idkmesh/project.json`; `.github/**` and `.idkmesh/**` stay forbidden regardless. |
| `project_policy_invalid` | The manifest allows automatic merge, skips the human decision, has a risk ceiling of `none`, or has an unsafe path | Restore `automatic_merge_allowed: false` and `human_decision_required: true`; fix the named field. |
| `event_issue_mismatch` | The triggering event concerns a different issue than `IDKMESH_ISSUE_NUMBER`; the generated wrappers never produce this, so the workflow file was edited | Restore the wrapper from `idkmesh init --github --dry-run`. |
| `policy_denied` from `idkmesh work preview` | The issue is closed, locked, a pull request, over the size bounds, or its Issue Form asks only for paths outside the project scope | Same fix as `preview_refused`; or widen `metadata.github_issue_preview.allowed_paths` yourself. The issue cannot. |
| `issue_invalid` / `issue_unreadable` from `idkmesh work preview` | The `--issue-json` file is not one strict-JSON GitHub issue object (duplicate keys, `NaN`, over 1 MiB), or its URL/number does not match `--repository` / `--issue` | Save the REST object for exactly that issue and repository. |
| `preview_refused` | The issue is closed, locked, or over the configured size bounds | Reopen or unlock the issue, or shorten it; a human decides, the runner does not override. |
| `ledger_unavailable` with a missing `idkmesh-ledger` branch | No run has been recorded on the ledger branch yet | Nothing to repair; `status` never creates the branch. |
| `ledger_run_not_found` | The `idkmesh_run_id` input matches no ledger run | Copy the run id from the ledger or dispatch record exactly. |
| `dispatch_unavailable`, `verify_unavailable` | These phases are intentionally not implemented in a stateless runner | Not a fault; dispatch and verification stay outside the workflow until their own authority design lands. |

## Local Product Spine store

| Symptom | Interpretation | Action |
| --- | --- | --- |
| `run status` cannot find a run | Wrong `--store` path or `run_id`, or record not created | Use the **same SQLite path** for create/status/list; compare exact IDs. |
| Create retry conflicts | Idempotency key was previously bound to a *different* request digest | Choose a new key for a logically new request; do not overwrite stored identity. |
| `run evidence` says `evidence_not_available` | The retained run lacks a canonical evidence report | Produce/retain actual evidence by the proper orchestration path; `run create` alone creates no evidence. |
| `run evidence` says `evidence_integrity_error` | Stored report digest does not match the run's bound digest | Stop using this report as evidence; investigate source/store integrity. Never edit the digest to make it pass. |
| `run cancel` succeeds but worker remains active | Only local lifecycle metadata was transitioned | Cancel/terminate a provider through its own separately authorized operator path. |
| List cursor fails | Cursors are opaque and bind to a listing contract | Copy `next_cursor` verbatim; use the same list filter context and query; do not decode/construct it manually. |

Source: [`product_spine_run_store.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/product_spine_run_store.py), [`product_spine.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/product_spine.py), [Product Spine spec](../specifications/PRODUCT_SPINE_SERVICE_V0_1.md). The local SQLite store is **not** a multi-user hosted ledger.

## Control Tower and HTTP

Start a headless local server with an **operator-chosen secret**, shared only with intended clients:

```bash
# In one trusted terminal (example generates a fresh, safe token):
export IDKMESH_CONTROL_TOWER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
idkmesh control-tower --no-browser --port 8770 --product-spine-store state.sqlite

# In a second trusted terminal, first set the SAME token privately:
# export IDKMESH_CONTROL_TOWER_TOKEN='<token from terminal one>'
curl --fail-with-body \
  -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/status
```

Do not copy the token into an issue, CI log, diagnostic report, or publicly shared command transcript. Set it separately for each trusted process; shell environment variables do not automatically propagate to unrelated sessions.

| HTTP / symptom | Meaning | Response |
| --- | --- | --- |
| Cannot connect to `127.0.0.1:8770` | Server not running, port in use, wrong port, or process is on another machine | Inspect server startup/port; use `--port`. The loopback-only bind is intentional; don't rebind to `0.0.0.0`. |
| 401 / token invalid | Missing or mismatched `X-IDKMesh-UI-Token` | Supply the running process's local token; a browser-opened UI does **not** grant your separate script implicit access. |
| Unexpected Host rejection | Browser/HTTP client forwarded a disallowed Host value | Access through `127.0.0.1` on the same machine without reverse-proxy rewriting. |
| 405 Method Not Allowed | Called a read route with POST or tried an unsupported mutation | Consult `GET /api/v1/openapi.json`; `/run-evidence/inspect` is a special computational POST. |
| 406 / 415 | HTTP `Accept` negotiation or request `Content-Type` mismatch | Use `Accept: application/json` and JSON `Content-Type` for the inspection POST. |
| 400 invalid length/framing | Bad/conflicting `Content-Length` or transfer framing | Let your HTTP client construct framing; avoid hand-built malformed headers. |
| 413 Request Entity Too Large | JSON report exceeds local UI's **2 MiB** body limit | Produce a smaller valid report; do not bypass bounds. |
| 503 with `Retry-After` | Bounded concurrent-request or SSE admission, draining, or unavailable backing store | Respect retry instructions; check `/readyz` and store configuration. This is not an authorization to retry an external side effect. |
| `/runs` list is empty or read endpoints unavailable | Optional local `--product-spine-store` absent, empty or mismatched | Start Control Tower with the **existing** local SQLite store path; no hosted datastore is implied. |
| An SSE client disconnects | Bounded streams, lifetime and heartbeats | Re-read event state with paginated `/events` and the documented stream cursor rather than assuming no events were lost. With the Python client, open a new `stream_events(last_event_id=...)` from the last sequence you saw. |

`GET /healthz` is liveness and `GET /readyz` is bounded readiness; neither constitutes evidence of worker quality or trusted actor identity. `GET /api/v1/metrics` is privacy-safe aggregate telemetry, not a trace of prompts or private candidate content. `idkmesh.api_client.ControlTowerClient` supplies typed transport/protocol/integrity errors and is preferred to hand-coded HTTP parsers.

## Agent execution and authority

| Symptom | Explanation / safe response |
| --- | --- |
| Bubblewrap not installed | `BubblewrapSandbox` rejects admission. Install/provision a sandbox via the host's trusted operator process; never fall back to direct untrusted process execution. |
| Linux backend rejects `network_policy=model-only` or `allowlist` | The implemented bubblewrap backend enforces **disabled network** only. A future separately qualified backend must enforce other egress policies. |
| Workspace/process timeouts | Raw `run_bounded_process()` and disposable worktrees are **not** equivalent to a hostile-code sandbox; see [execution boundary](../specifications/LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md). |
| Jules marks worker completed but no candidate is ready | Jules PR links are untrusted discovery hints. Candidate readiness needs independently observed GitHub head identity and a canonical CandidateReference. |
| Verification passed but nothing merged | Correct by design: verification is evidence; trusted human/governance decision and GitHub integration remain separate authorities. |
| Request to record human decision via local HTTP returns 404/405 | The `human_decision_service.py` domain service does **not** expose a mutation route in the local Control Tower. Don't bypass identity/authz by inventing one. |

## Diagnostic escalation

For a reproducible GitHub bug report, collect **sanitized** command line and expected/actual behavior, `idkmesh --version`, Python version, OS/platform, exact checkout commit SHA, relevant JSON contract version, and the smallest non-sensitive fixture. Report secret or vulnerability details privately through [SECURITY.md](https://github.com/MSKazemi/idkmesh/blob/main/SECURITY.md), not in an issue. For CI, use [the test tiers](../TESTING.md), distinguish test **not run** from a genuine pass, and always cite the exact Git/PR head that produced results. If documentation disagrees with live code, include the code path and a focused correction PR instead of treating a future design document as already implemented.
