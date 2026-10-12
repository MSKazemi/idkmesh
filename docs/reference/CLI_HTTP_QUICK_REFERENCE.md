---
description: "Current CLI, local HTTP, and Python client quick reference derived from idkmesh/cli.py and Control Tower handlers; excludes unmerged API proposals."
---
# CLI and local HTTP quick reference

**Verified against source:** `main@bee77a6125dbccb58f166ec363e978cd960f43f3` (2026-10-11). This is a navigational **as-built** reference, not a replacement for `idkmesh <command> --help`, [the versioned HTTP contract](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md), or the [capability matrix](../CAPABILITY_MATRIX.md). It describes the code on this commit, **not** pending API PRs.

## Install and find help

From a repository checkout, with Python 3.11 or later:

```bash
python -m pip install -e .
idkmesh --version
idkmesh --help
idkmesh gate-audit --help
idkmesh control-tower --help
```

The wheel intentionally installs only `idkmesh/`. Running the research-backed `local-loop` additionally requires the **repository checkout** and optional schema verifier dependency: `python -m pip install -e '.[verify]'`. Other examples, fixtures, workflows and research scripts are not shipped in the wheel.

## Present CLI commands and what they do

| Command | Implemented behavior | Authority / dependency boundary |
| --- | --- | --- |
| `gate-audit INPUT` | Audit ground-truthed reviewer verdicts; `--bootstrap` opts into v0.2 uncertainty | Diagnostic only; `--out`, `--markdown`, `--pretty` |
| `gate-audit-dependence INPUT` | Export observed pairwise verifier error-dependence | Does not infer provider independence or route work |
| `gate-marginal INPUT --current ID` | Retrospective add-one-verifier marginal contribution | Does not select the next verifier |
| `gate-marginal-benchmark CONFIG` | Evaluate a fixed selector against held-out baselines | Held-out benchmark; no routing or merge |
| `gate-marginal-synthesis CONFIG` | Synthesize frozen benchmark reports | Descriptive only; no strategy winner |
| `gate-audit-ui [INPUT]` | Local browser editor/diagnostic | Loopback `127.0.0.1:8765` by default |
| `control-tower [REPORT]` | Local read-only evidence browser and HTTP API | Loopback `127.0.0.1:8770` by default |
| `run create PROJECTION --store PATH --idempotency-key KEY` | Persist a canonical proposed run in local SQLite | No worker dispatch or verification |
| `run status RUN_ID --store PATH` | Inspect stored run | Read-only |
| `run evidence RUN_ID --store PATH` | Read retained evidence, verifying its digest | Errors on missing or mismatched evidence |
| `run list --store PATH` | Deterministic paged run list (`--limit`, `--cursor`, `--state`, `--project-id`) | Cursor opaque; no mutation |
| `run cancel RUN_ID --store PATH` | Record legal lifecycle cancellation | Does **not** stop external provider work |
| `work-unit list/status`, `project status`, `events list` | Derived reads from local retained runs/events | Supply `--store PATH`; check each subcommand's help |
| `connections validate/list/import/stored/probe` | Parse, inspect, locally persist connector metadata, use offline fake probes | No implicit live-provider dispatch |
| `doctor PROFILE` | Offline connector readiness | Diagnostic only; no dispatch |
| `doctor --github OBSERVATION --operation OP [--workflow PATH]` | Evaluate the read-only C12 GitHub governance preflight and optional workflow-source checks | Uses trusted normalized observations; no GitHub admin mutation, secret access, acceptance, or merge |
| `doctor --enterprise-conformance [--json]` | Run the in-process E9 failure-mode scenarios (unauthorized actor, cross-tenant reference, replay, secret loss, audit-exporter outage, ledger restore, stale identity, self-approval) and report PASS/WARN/FAIL/UNKNOWN per scenario | Temp dirs and fakes only; exit 1 on FAIL or UNKNOWN; scenarios not yet exercised report UNKNOWN; not a SOC 2/ISO 27001/FedRAMP claim |
| `route explain PROFILE DECISION` | Offline connector routing eligibility/explanation | Does not dispatch work or grant authority |
| `init --github --dry-run --idkmesh-ref REF` | Pure deterministic GitHub-first bootstrap **plan**/render of config and pinned workflow wrappers (`rendered_config_files`, `rendered_workflow_files` in `--json`) | Apply mode is **not** implemented; no repo writes; the wrappers call `github-workflow` below |
| `github-workflow {preview,status} [--issue-json PATH \| --ledger-records PATH] [--json]` | Runner the generated `idkmesh-*.yml` wrappers call; reads `IDKMESH_*` environment variables. `preview` derives a WorkUnit preview and digest for one issue; `status` projects one run's latest durable-ledger record into the bounded status body and job summary | Read-only; no dispatch, issue comment, provider secret, or merge; refusals print `error: <code>: <message>` and exit 2 |
| `github-workflow {dispatch,verify}` | Reserved wrapper phases | Always fail closed with `dispatch_unavailable` / `verify_unavailable`; read no environment or secret |
| `pages-site --repository OWNER/NAME --projection PATH... --out DIR [--force] [--json]` | Validate C14-D public-safe projections, render the C14-E static Pages file map, and write exactly those files to a local directory all-or-nothing | Local files only: no publication, workflow, network or GitHub call; refuses `..`/absolute/symlinked paths, a symlinked or foreign non-empty `--out` (replaced only with `--force`, never the cwd, its ancestors, home, or a `.git` directory) |
| `local-loop CONFIG [--output-dir PATH]` | Two-attempt reference orchestration and verification/evidence bundle | Checkout + `[verify]` extra; decisions/replay remain manual |
| `steward-report INPUT`, `steward-report-ui INPUT` | Validate and display retained single-run steward evidence | Offline read/loopback UI |
| `steward-history INPUTS...`, `steward-history-ui INPUTS...` | Aggregate/show retained steward history | No GitHub polling or mutation |

### Copyable examples

```bash
# Stdlib-only, installed-package gate audit:
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty

# Local Product Spine record; fixture is intentionally in proposed state:
idkmesh run create examples/api/product-spine-run.example.json \
  --store state.sqlite --idempotency-key documentation-demo-1
idkmesh run list --store state.sqlite --json

# Plan only. No bootstrap files are written:
idkmesh init --github --dry-run --idkmesh-ref v0.1.0 --json

# Runner phase as a generated wrapper invokes it; offline issue, no GitHub call:
IDKMESH_PROJECT_ROOT=. IDKMESH_REPOSITORY=OWNER/REPO IDKMESH_RUN_ID=1 \
  IDKMESH_BASE_SHA=0123456789abcdef0123456789abcdef01234567 IDKMESH_ISSUE_NUMBER=7 \
  idkmesh github-workflow preview --issue-json issue.json
# Write a Pages site from public-safe projections to a local directory; nothing is published:
idkmesh pages-site --repository owner/name --projection run-1.json --out site

# Evaluate the committed C12 fixture only; no GitHub API/admin mutation:
idkmesh doctor --github examples/github-governance/governance-pass-v0.1.json \
  --operation integration --json


# With checkout and optional verification extra installed:
idkmesh local-loop examples/orchestration/two-attempt-good-vs-bad.json \
  --output-dir results/idkmesh-local-loop/manual-demo

# Expose existing local run state to the read-only HTTP API:
idkmesh control-tower --no-browser --product-spine-store state.sqlite
```

Use a fresh empty `results/` output directory for each `local-loop` run; existing non-empty destinations are rejected. `v0.1.0` above is a *syntax example for a pinned tag*, not a claim that such a release tag has been published; for a real plan use an existing immutable release tag or 40-character lowercase commit SHA.

## Control Tower HTTP contract currently routed

| Method | Path | Role |
| --- | --- | --- |
| GET | `/healthz`, `/readyz` | Local process health/readiness probes |
| GET | `/api/v1/status` | Runtime capabilities/limits |
| GET | `/api/v1/openapi.json` | Machine-readable **running** API definition |
| GET | `/api/v1/metrics` | Fixed-cardinality privacy-safe metrics |
| POST | `/api/v1/run-evidence/inspect` | Strict validation and projection of supplied report (no persistent mutation) |
| GET | `/api/v1/connections` | Secret-free persisted connector summaries |
| GET | `/api/v1/runs`, `/api/v1/runs/{run_id}` | Local durable Product Spine run views |
| GET | `/api/v1/runs/{run_id}/attempts`, `/api/v1/runs/{run_id}/evidence` | Attempt view and digest-checked retained report |
| GET | `/api/v1/work-units`, `/api/v1/work-units/{work_unit_id}` | Derived WorkUnit lists and details |
| GET | `/api/v1/projects/{project_id}` | Derived project summary |
| GET | `/api/v1/events`, `/api/v1/events/stream` | Paginated event list and read-only SSE stream |

**Authentication and deployment:** the browser server binds to `127.0.0.1`, not a public interface. Versioned API requests require the local UI token in `X-IDKMesh-UI-Token`. For a headless client, set a private 32-4096-character safe-ASCII `IDKMESH_CONTROL_TOWER_TOKEN` in the process environment and supply that same token from the client. An auto-generated browser session token is not a general authenticated multi-user identity. Neither `/healthz` nor `/readyz` is a repository integration permission. Report POSTs have a 2 MiB body ceiling; client count, request concurrency, timeout and SSE count are bounded. Unsupported/misframed requests receive structured errors; HTTP availability does not imply a configured local store.

### Standard-library Python client (read and inspect only)

```python
import os
from idkmesh.api_client import ControlTowerClient

client = ControlTowerClient(
    "http://127.0.0.1:8770",
    token=os.environ["IDKMESH_CONTROL_TOWER_TOKEN"],
    timeout=10.0,
)
result = client.status()
print(result.value)
```

`ControlTowerClient` exposes `status`, `get_openapi` (download of the running OpenAPI definition), `get_metrics` (aggregate operational metrics), `inspect_run_evidence`, `list_connections`, `list_runs`, `get_run`, `get_run_attempts`, `get_run_evidence`, `list_work_units`, `get_work_unit`, `get_project`, and `list_events`; it does **not** expose a human-decision mutation or an SSE subscription helper. Read-list pagination uses opaque cursors and a maximum page size of 200. Error classes include `ClientConfigurationError`, `TransportError`, `ProtocolError`, `IntegrityError`, and `ApiResponseError` (see [source](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/api_client.py)). No public typed JavaScript client is claimed here.

## Source-of-truth and future endpoints

- Source commands: [`idkmesh/cli.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/cli.py); source HTTP methods: [`idkmesh/control_tower_ui.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/control_tower_ui.py); generated OpenAPI: [`idkmesh/control_tower_api.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/control_tower_api.py).
- Detailed request/response/error semantics: [Control Tower Local API v0.1](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md), [API Conventions v0.1](../specifications/API_CONVENTIONS_V0_1.md), [API examples](https://github.com/MSKazemi/idkmesh/blob/main/examples/api/README.md).
- **Not served by this local Control Tower:** `POST /api/v1/human-decisions`, generic connector dispatch/configure, network/multi-user mutations, and merge/integration endpoints. `human_decision_service.py` is a separate service-layer kernel, not a routed authenticated HTTP endpoint.
- Historical planning candidates: [API surface catalog](../planning/API_V1_SURFACE_CATALOG_2026-09-23.md). An older `planned` row there does **not** override the router on current `main`.

Integrator pages: [API quickstart](API_QUICKSTART.md) (executable curl and Python examples), [error catalog](API_ERROR_CATALOG.md) (every stable error code with status and retry rule) and [service limits](API_LIMITS.md) (timeouts, concurrency, body, header and event-stream bounds).

For user-facing failures use [troubleshooting](../help/TROUBLESHOOTING.md). For file-by-file ownership use [module map](MODULE_MAP.md).
