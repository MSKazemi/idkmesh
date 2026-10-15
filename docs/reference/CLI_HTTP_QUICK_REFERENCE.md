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
| `api-storage {plan-migrations,apply-migrations} DATABASE --migrations DIR [--adopt-existing] [--apply] [--json]` | Show or run forward-only checksummed SQLite migration steps from `NNNN_name.sql` files (#750). `plan-migrations` and `apply-migrations` without `--apply` are read-only dry runs; `--apply` commits every pending step, ledger row and `user_version` in one transaction | Local files only; refuses edited history, ledger gaps, a newer database, an unadopted legacy schema and symlinked paths; no existing IDKMesh store is migrated onto it |
| `api-storage plan-retention --records FILE --expendable-days N --ephemeral-days N (--decisions-store PATH \| --assume-no-decisions) [--now TS] [--json]` | Print keep/expire decisions for a JSON record list; essential/configuration records and anything a Human Decision refers to are always kept | Plans only: never deletes or schedules anything; a missing or unreadable decisions store is an error, never "unreferenced" |
| `api-storage backup SOURCE BACKUP [--apply]`, `api-storage verify-backup BACKUP [--manifest PATH] [--max-schema-version N]`, `api-storage restore BACKUP TARGET [--manifest PATH] [--max-schema-version N] [--apply]` | Digest-bound SQLite snapshot with a `BACKUP.manifest.json`, read-only verification, and atomic restore to a new path | `backup` and `restore` are dry runs unless `--apply`; neither overwrites (move an existing target aside), follows a symlink or needs a network; a digest detects corruption, not a writer who can rewrite both files |
| `connections validate/list/import/stored/probe` | Parse, inspect, locally persist connector metadata, use offline fake probes | No implicit live-provider dispatch |
| `doctor PROFILE` | Offline connector readiness | Diagnostic only; no dispatch |
| `doctor --github OBSERVATION --operation OP [--workflow PATH]` | Evaluate the read-only C12 GitHub governance preflight and optional workflow-source checks | Uses trusted normalized observations; no GitHub admin mutation, secret access, acceptance, or merge |
| `doctor --enterprise-conformance [--json]` | Run the in-process E9 failure-mode scenarios (unauthorized actor, cross-tenant reference, replay, secret loss, audit-exporter outage, ledger restore, stale identity, self-approval, release-record tampering) and report PASS/WARN/FAIL/UNKNOWN per scenario | Temp dirs and fakes only; exit 1 on FAIL or UNKNOWN; every scenario is now exercised, but each reports WARN while a named deployment gap remains (the overall status is WARN, exit 0, never PASS); a scenario with no runner reports UNKNOWN; not a SOC 2/ISO 27001/FedRAMP claim |
| `route explain PROFILE DECISION` | Offline connector routing eligibility/explanation | Does not dispatch work or grant authority |
| `init --github --dry-run\|--check\|--apply --idkmesh-ref REF [--target DIR]` | Render bootstrap plan, inspect local conflicts, or explicitly apply eight pinned generated files | Dry-run has no writes; check reads local files; apply makes digest-guarded local writes only, never GitHub/API mutations; dispatch/verify still fail closed |
| `github-workflow {preview,status} [--issue-json PATH \| --ledger-records PATH] [--json]` | Runner the generated `idkmesh-*.yml` wrappers call; reads `IDKMESH_*` environment variables. `preview` derives a WorkUnit preview and digest for one issue; `status` projects one run's latest durable-ledger record into the bounded status body and job summary | Read-only; no dispatch, issue comment, provider secret, or merge; refusals print `error: <code>: <message>` and exit 2 |
| `work preview --issue-json PATH --repository OWNER/NAME --source-revision SHA [--project-root DIR] [--issue N] [--no-intake-form] [--json]` | Offline WorkUnit preview (C7-C): one issue snapshot file plus `.idkmesh/project.json` policy (same derivation as `github-workflow preview`) to a canonical WorkUnit, digest and warnings; an IDKMesh Issue Form in the body is composed by default | Read-only; no network, secret, environment variable, file write, dispatch or HTTP route (`POST /api/v1/work-units:preview` is specified, not served); the form only narrows scope or raises risk; refusals print `error: <code>: <message>` and exit 2 |
| `github-workflow {dispatch,verify}` | Reserved wrapper phases | Always fail closed with `dispatch_unavailable` / `verify_unavailable`; read no environment or secret |
| `pages-fallback --repository OWNER/NAME --projection PATH... --out DIR [--json]` or `pages-fallback --verify DIR [--json]` | C14-H: render the same C14-D public-safe projections as an offline escaped-Markdown + JSON bundle with a SHA-256 `MANIFEST.json`, or re-verify an existing bundle read-only | Local files only: no upload, publication, workflow, network or GitHub call; `--out` must not exist or be empty and is never replaced; `--verify` refuses symlinks, extra files, digest mismatches and any file that differs from a fresh re-render |
| `pages-site --repository OWNER/NAME --projection PATH... --out DIR [--force] [--json]` | Validate C14-D public-safe projections, render the C14-E static Pages file map, and write exactly those files to a local directory all-or-nothing | Local files only: no publication, workflow, network or GitHub call; refuses `..`/absolute/symlinked paths, a symlinked or foreign non-empty `--out` (replaced only with `--force`, never the cwd, its ancestors, home, or a `.git` directory) |
| `release-provenance --repository OWNER/NAME --tag TAG --target-commit SHA [--artifact NAME=sha256:HEX]... [--projection PATH...] [--notes | --statement]` | Validate C14-D public-safe projections and print the C14-F release metadata/provenance record as JSON, draft release notes with `--notes`, or the unsigned C14-G in-toto Statement with `--statement` (needs at least one `--artifact`) | stdout only: no tag, GitHub Release, signing, attestation, network or GitHub call; commit and artifact digests are caller-supplied and recorded as unverified; no timestamps; exit 2 and empty stdout on any rejected input |
| `github-authority-audit --bindings PATH --trusted-actors PATH [--scope TENANT/PROJECT] [--now-epoch N] [--json]` | Run the C10 alignment audit: compare an `enterprise-github-identity-binding` table with a C5 dispatch trusted-actor document and report unbound, login-mismatched, wrong-kind, revoked, expired, out-of-scope and unbacked trusted actors | Reads the two named files only: no network, GitHub call, secret, clock read or write; never prints login text (findings name numeric actor ids); exit 0 when no `error` finding, 1 when at least one, 2 (empty stdout) on an unreadable or invalid input; an aligned report is evidence, not an authorization decision; no workflow runs it |
| `egress-policy check --policy PATH --profile PATH --classification CLASS --destination HOST [--provider ID] [--json]` | Decide offline whether data of one classification (`public`, `internal`, `confidential`, `restricted`) may go to one destination under an E5 egress policy and an enterprise control profile, using the real strict loaders and `decide_classified_egress`; prints the stable reason code, matching destination id and policy digest | Reads the two named files only: no DNS resolution, network, environment variable, secret, clock read or write; the host is normalised exactly as the library does and matched exactly (a look-alike such as `example.com.evil.test` is denied); `--provider` can only tighten (`provider_mismatch`), the provider always comes from the policy; exit 0 allowed, 1 denied, 2 (empty stdout) for an unreadable or invalid file or a malformed `--destination` / `--classification`; evidence for a later enforcement point, not an enforcement action |
| `secret-reference check REF [--profile PATH] [--json]` | Validate the grammar of a secret reference (`env:`, `gh-secret:`, `secret:`, `vault:`) with `parse_secret_reference`; with `--profile`, also check the profile's secret backend supplies that credential kind (`decide_credential`) | Never resolves the reference, reads an environment variable or vault, contacts a network or prints a rejected argument (a mistaken raw secret is `inline_secret_forbidden` and is not echoed); reports `authorization_evaluated: false` because a real secret access still needs an allowed `dispatch`/`execute` decision; exit 0 acceptable, 1 refused with a stable code, 2 (empty stdout) for an unreadable or invalid profile |
| `local-loop CONFIG [--output-dir PATH]` | Two-attempt reference orchestration and verification/evidence bundle | Checkout + `[verify]` extra; never replays or records a decision on its own |
| `local-loop-replay BUNDLE` | Replay a saved `local-loop` bundle against the same fixtures and compare must-match vs expected-to-vary fields; same report and exit codes (0 PASS, 1 diverged, 2 unusable path) as `python experiments/replay_run.py replay` | Checkout + `[verify]` extra; writes nothing; no write, push, merge or selection authority |
| `local-loop-record-decision EVIDENCE_REPORT --output PATH --decision-id ID --decision {accept,reject,escalate} --rationale TEXT --decider-id ID [--decider-type TYPE] [--decider-display-name NAME] [--selected-attempt-id ID] [--decided-at TS]` | Record one explicit human decision bound to the evidence-report digest; same behavior as `python experiments/record_human_decision.py record` | Checkout + `[verify]` extra; `--output` must be under `results/` and not the report; record's `canonical_state_write`, `git_push` and `merge` are `false`; integrates nothing |
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

# Same preview from a local shell, no wrapper environment needed:
idkmesh work preview --issue-json issue.json --repository OWNER/REPO \
  --source-revision 0123456789abcdef0123456789abcdef01234567 --json

# Write a Pages site from public-safe projections to a local directory; nothing is published:
idkmesh pages-site --repository owner/name --projection run-1.json --out site

# Pages disabled? Write an offline bundle (nothing is uploaded), then verify it:
idkmesh pages-fallback --repository owner/name --projection run-1.json --out fallback
idkmesh pages-fallback --verify fallback

# Print release metadata for a proposed tag; nothing is tagged, released, or attested:
idkmesh release-provenance --repository owner/name --tag v0.1.0 \
  --target-commit <40-hex-commit> --projection run-1.json

# Print the UNSIGNED in-toto Statement for a proposed release; nothing is signed or attested:
idkmesh release-provenance --repository owner/name --tag v0.1.0 \
  --target-commit <40-hex-commit> --artifact pkg-0.1.0.tar.gz=sha256:<64-hex> \
  --projection run-1.json --statement

# Audit that the identity binding table and the dispatch trusted-actor list agree; read-only,
# exit 0 aligned, 1 error finding, 2 unusable input:
idkmesh github-authority-audit --bindings bindings.json --trusted-actors trusted-actors.json \
  --scope tenant-a/project-main --now-epoch 1760000000 --json

# Decide offline whether public data may go to a host under an egress policy and profile; no DNS or
# network, exit 0 allowed, 1 denied (reason code + policy digest), 2 unusable input:
idkmesh egress-policy check --policy egress-policy.json --profile profile.json \
  --classification public --destination packages.registry.example --json

# Check a secret reference's grammar only; nothing is resolved or printed besides the name:
idkmesh secret-reference check gh-secret:DEPLOY_REF --profile profile.json --json

# Evaluate the committed C12 fixture only; no GitHub API/admin mutation:
idkmesh doctor --github examples/github-governance/governance-pass-v0.1.json \
  --operation integration --json


# With checkout and optional verification extra installed:
idkmesh local-loop examples/orchestration/two-attempt-good-vs-bad.json \
  --output-dir results/idkmesh-local-loop/manual-demo

# Replay that saved run, then record an explicit human decision against it:
idkmesh local-loop-replay results/idkmesh-local-loop/manual-demo/replay-source.json
idkmesh local-loop-record-decision \
  results/idkmesh-local-loop/manual-demo/evidence-report.json \
  --output results/idkmesh-local-loop/manual-demo/human-decision-record.json \
  --decision-id manual-demo.decision.001 --decision accept \
  --rationale "reviewed the evidence report" --decider-id my-id

# Storage operations: dry run first, then --apply; restore refuses to overwrite:
idkmesh api-storage apply-migrations state.sqlite --migrations migrations/
idkmesh api-storage backup state.sqlite backups/state-1.sqlite --apply
idkmesh api-storage verify-backup backups/state-1.sqlite
idkmesh api-storage restore backups/state-1.sqlite restored.sqlite --apply

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
| GET | `/api/v1/metrics/prometheus` | The same metrics as Prometheus text exposition 0.0.4 (`text/plain; version=0.0.4; charset=utf-8`); session token required, no query string, `Accept` must allow `text/plain` |
| POST | `/api/v1/run-evidence/inspect` | Strict validation and projection of supplied report (no persistent mutation) |
| GET | `/api/v1/connections` | Secret-free persisted connector summaries |
| GET | `/api/v1/connections/{connection_id}` | One secret-free connector summary (no probe, no secret resolution, no authority) |
| GET | `/api/v1/connector-drivers` | Static driver declarations (kind, driver, version) of the offline fake-driver registry; no store needed, no probe, no authority |
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

`ControlTowerClient` exposes `status`, `get_openapi` (download of the running OpenAPI definition), `get_metrics` (aggregate operational metrics), `inspect_run_evidence`, `list_connections`, `get_connection`, `list_connector_drivers`, `list_runs`, `get_run`, `get_run_attempts`, `get_run_evidence`, `list_work_units`, `get_work_unit`, `get_project`, and `list_events`, plus `stream_events` (one bounded, strictly parsed read of `GET /api/v1/events/stream`; resuming with `Last-Event-ID` is the caller's job); it does **not** expose a human-decision mutation. Read-list pagination uses opaque cursors and a maximum page size of 200; `iter_runs` / `iter_run_pages` walk run pages lazily under a mandatory page cap. By default every call is exactly one HTTP exchange; an explicit `RetryPolicy` opts idempotent `GET` reads into bounded, deterministic retry of transport failures and server-declared retryable capacity errors (never the `POST` inspection or event streams). Error classes include `ClientConfigurationError`, `TransportError`, `ProtocolError`, `IntegrityError`, and `ApiResponseError` (see [source](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/api_client.py)). No JavaScript runtime client is claimed here; TypeScript *type declarations* generated from the OpenAPI document are checked in at `clients/typescript/idkmesh-api.d.ts` (regenerate with `python tools/generate_api_types.py`, verify with `--check`; see the [API overview](API_OVERVIEW.md#web-client-types-typescript-declarations)).

## Source-of-truth and future endpoints

- Source commands: [`idkmesh/cli.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/cli.py); source HTTP methods: [`idkmesh/control_tower_ui.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/control_tower_ui.py); generated OpenAPI: [`idkmesh/control_tower_api.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/control_tower_api.py).
- Detailed request/response/error semantics: [Control Tower Local API v0.1](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md), [API Conventions v0.1](../specifications/API_CONVENTIONS_V0_1.md), [API examples](https://github.com/MSKazemi/idkmesh/blob/main/examples/api/README.md).
- **Not served by this local Control Tower:** `POST /api/v1/human-decisions`, generic connector dispatch/configure, network/multi-user mutations, and merge/integration endpoints. `human_decision_gateway.py` (kernel `decide` authorization plus audit) and `human_decision_service.py` are separate service-layer kernels, not a routed authenticated HTTP endpoint.
- Historical planning candidates: [API surface catalog](../planning/API_V1_SURFACE_CATALOG_2026-09-23.md). An older `planned` row there does **not** override the router on current `main`.

Integrator pages: [API overview](API_OVERVIEW.md) (authentication, routes, schema catalog, clients), [API quickstart](API_QUICKSTART.md) (executable curl and Python examples), [error catalog](API_ERROR_CATALOG.md) (every stable error code with status and retry rule) and [service limits](API_LIMITS.md) (timeouts, concurrency, body, header and event-stream bounds).

For user-facing failures use [troubleshooting](../help/TROUBLESHOOTING.md). For file-by-file ownership use [module map](MODULE_MAP.md).
