# Tutorial: create a run and read it back (CLI and local API)

This walkthrough creates one Product Spine run through the `idkmesh run` CLI,
inspects and cancels it, and then reads the same run back over the Control
Tower local HTTP API. Every command below was run from a repository checkout
and the output is copied from that session; the commands match `--help` on
current `main`.

The run is a local SQLite projection: nothing is dispatched to a provider, no
Git is pushed, and nothing is merged. The whole tutorial is safe to run on a
clean checkout and leaves only one scratch directory that you delete at the
end.

## Prerequisites

- Python 3.11 or 3.13 (see [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the
  environment setup used by the project);
- a clone of this repository, with all commands run from the repository root;
- the `idkmesh` CLI on your `PATH`, which one editable install provides:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

(`python -m idkmesh.cli` works everywhere `idkmesh` does; the transcripts
below use the installed command.)

## Step 1 — create a run

`idkmesh run create` persists one canonical Product Spine run projection in a
local SQLite store. The projection file is the committed example fixture
[`../examples/api/product-spine-run.example.json`](../examples/api/product-spine-run.example.json)
(a `state="proposed"` run for `run/example-1`), and `--idempotency-key` is a
caller-chosen identity for this create request.

```bash
mkdir -p tutorial-demo
idkmesh run create examples/api/product-spine-run.example.json \
  --store tutorial-demo/state.sqlite --idempotency-key tutorial-1
```

```text
created: run/example-1 state=proposed
```

Re-running the same command with the same key and the same projection replays
the original create instead of storing a second run. `idkmesh run create
--help` lists the remaining flags (`--json` for deterministic machine-readable
output, `--created-at` for an explicit ISO-8601 timestamp).

## Step 2 — read the run back

```bash
idkmesh run status run/example-1 --store tutorial-demo/state.sqlite
```

```text
run: run/example-1
state: proposed
project: project.example
work_unit: work/example-1
merge_authority: no
```

`merge_authority: no` is not a status detail: it is the fixed authority block
of the projection. A run record never carries canonical-state-write, git-push,
or merge authority.

## Step 3 — list retained runs

```bash
idkmesh run list --store tutorial-demo/state.sqlite
```

```text
run/example-1	state=proposed
```

A fresh store lists nothing; `--limit`, `--cursor`, `--state`, and
`--project-id` bound larger listings (see `idkmesh run list --help`).

## Step 4 — cancel the run

```bash
idkmesh run cancel run/example-1 --store tutorial-demo/state.sqlite
```

```text
cancelled: run/example-1
provider_execution_terminated: no
merge_authority: no
```

Cancellation is a lifecycle transition in this store only. It does **not**
terminate an external or provider process — `provider_execution_terminated:
no` says so explicitly.

## Step 5 — read the run over the local API

The Human Control Tower serves a read-only HTTP API over the same store. It
is headless-token mode here: choose your own token of 32 to 4096 characters made only of letters, digits,
`-`, `.`, `_` and `~` (for example the output of `openssl rand -hex 32`), and
keep it out of shell history and version control.

In one terminal, start the server:

```bash
export IDKMESH_CONTROL_TOWER_TOKEN='replace-with-at-least-32-random-characters'
idkmesh control-tower --no-browser --port 8770 \
  --product-spine-store tutorial-demo/state.sqlite
```

In a second terminal, first see that the API rejects a request without the
token:

```bash
curl -s -i -H "Accept: application/json" http://127.0.0.1:8770/api/v1/runs
```

```text
HTTP/1.0 403 Forbidden
Server: IDKMeshControlTower/0.1
...
```

In this second terminal, set the same value first, then send the token in the
`X-IDKMesh-UI-Token` header:

```bash
export IDKMESH_CONTROL_TOWER_TOKEN='<the token you chose>'
curl -s -H "X-IDKMesh-UI-Token: $IDKMESH_CONTROL_TOWER_TOKEN" \
  -H "Accept: application/json" \
  http://127.0.0.1:8770/api/v1/runs | python -m json.tool
```

```json
{
    "items": [
        {
            "attempts": [],
            "authority": {
                "canonical_state_write": false,
                "git_push": false,
                "merge": false
            },
            "evidence_report_digest": null,
            "human_decision_record_digest": null,
            "kind": "idkmesh-product-spine-run",
            "project_id": "project.example",
            "request_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "routing": {
                "admitted_connectors": [],
                "authority_mode": "agent_candidate",
                "policy_version": "c1-v0.1"
            },
            "run_id": "run/example-1",
            "schema_version": "0.1",
            "state": "cancelled",
            "work_unit": {
                "digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "id": "work/example-1",
                "source_revision": "0123456789abcdef0123456789abcdef01234567",
                "version": 1
            }
        }
    ],
    "kind": "idkmesh-list",
    "page": {
        "limit": 50,
        "next_cursor": null
    },
    "schema_version": "0.1"
}
```

The HTTP read surface shows the same run — now `state=cancelled` — through the
same application service the CLI used; the `authority` block is still all
`false`. Stop the server with `Ctrl-C`.

### Security and authority boundaries

The Control Tower server binds only to `127.0.0.1` (loopback-only), refuses
API requests that lack a valid `X-IDKMesh-UI-Token` header (only `/healthz`,
`/readyz` and the HTML page are exempt), serves evidence read-only,
and has no merge or push authority. It cannot dispatch workers, select
candidates, write canonical state, push Git, or merge anything, and the
responses it serves carry the same fixed `authority` block shown above.

## Cleanup

```bash
rm -rf tutorial-demo
```

## Where to go next

- [`specifications/PRODUCT_SPINE_SERVICE_V0_1.md`](specifications/PRODUCT_SPINE_SERVICE_V0_1.md) —
  the run lifecycle and the store behind `idkmesh run`.
- [`specifications/CONTROL_TOWER_LOCAL_API_V0_1.md`](specifications/CONTROL_TOWER_LOCAL_API_V0_1.md) —
  every local API endpoint, including single-run and attempts reads.
- [`specifications/API_CONVENTIONS_V0_1.md`](specifications/API_CONVENTIONS_V0_1.md) —
  the shared error, pagination, and idempotency conventions.
- Newer read surfaces on `main`: `idkmesh work-unit list|status`,
  `idkmesh project status`, `idkmesh events list` and `idkmesh run evidence`
  (see the two specifications above for what each one does and does not cover).
