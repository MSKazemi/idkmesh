# Running the real-node / two-attempt E2E tools locally

**Tools covered:** `tools/real_node_verifier_e2e.py`, `tools/real_two_attempt_e2e.py`
**Frozen accepted node candidate:** `520ad2c9aa5825476de4957da4702d6823f4edb3` (PR #91,
branch `integration/canonical-node-current`)
**Immutable source revision the WorkUnit fixture is pinned to:** `b1397a9be91da6570e8ae370de4fa9f4bc44df5c`

## Why `--candidate` is not a path inside this checkout

`node/examples/work-unit.canonical-smoke.json` does not exist anywhere on `main`, and it is
not supposed to. The `idkmesh-node` worker implementation under `node/` was built and
runtime-accepted on PR #91 (see `docs/acceptance/PR91_CONTROLLED_DOCKER_GATE.md`), but PR #91
was deliberately never merged: the worker/candidate tree and the evaluator/verifier tree
(this repository's `main`) stay in two separate checkouts so the verifier tooling never
shares a working tree, a Python import path, or write access with the code it is judging.
PR #91 is closed, not merged, and its head commit is retained only as a GitHub pull-request
ref (`refs/pull/91/head`) rather than a branch — see "Residual uncertainty" below.

Both `.github/workflows/real-node-verifier-e2e.yml` and
`.github/workflows/real-two-attempt-e2e.yml` already do this correctly: they check out this
repository into `evaluator/` and separately check out the exact SHA above into `candidate/`,
then run the tool with `--candidate candidate`. This document is the local equivalent of
those two checkout steps, because until now that procedure only existed inside workflow YAML
and in dated conversation records under `docs/conversations/`, and R1 requires the real
product loop to be runnable without reading research-history docs.

## Preconditions

- `make setup` (creates `.venv`, installs `pytest` and `requirements-phase0.txt`, i.e.
  `jsonschema`).
- Docker, with the allowlisted image preloaded:
  ```bash
  docker pull python:3.12-alpine
  docker image inspect python:3.12-alpine
  ```
- Network access to `github.com` to fetch the candidate's frozen commit.

## Get the exact candidate checkout

From a directory **outside** this repository's working tree (the candidate must be an
independent checkout, never a path inside the evaluator tree being verified):

```bash
git clone https://github.com/MSKazemi/idkmesh.git /path/to/candidate-520ad2c
cd /path/to/candidate-520ad2c
git fetch origin pull/91/head
git checkout --detach FETCH_HEAD
git rev-parse HEAD   # must print exactly 520ad2c9aa5825476de4957da4702d6823f4edb3
```

If PR #91's ref is ever deleted or the SHA becomes unreachable, this procedure stops working
and the frozen candidate must be re-derived (e.g. from a locally retained clone, or a new
runtime-accepted candidate substituted throughout `tools/real_node_verifier_e2e.py`,
`tools/real_two_attempt_e2e.py`, `tools/real_two_attempt_evidence_e2e.py`,
`tools/real_mixed_outcome_e2e.py`, and `tools/node_verifier_e2e_current.py`, all of which must
keep the same `CANDIDATE_SHA`; see `tests/test_real_node_e2e_candidate_reference.py`).

## Run the real single-attempt E2E

From this repository's root:

```bash
.venv/bin/python tools/real_node_verifier_e2e.py \
  --candidate /path/to/candidate-520ad2c \
  --output-root results/verification/real-node-520ad2c
```

Success prints `IDKMESH_REAL_NODE_VERIFIER_E2E_BEGIN` / `..._END` bracketing a JSON evidence
object with `"recommendation": "accept_candidate"`, `"candidate_code_executed_by_verifier":
false`, and `"human_integration_decision_required": true`.

## Run the real two-attempt orchestration E2E

```bash
.venv/bin/python tools/real_two_attempt_e2e.py \
  --candidate /path/to/candidate-520ad2c \
  --output-root results/orchestration/real-two-attempt-520ad2c
```

Success prints `IDKMESH_REAL_TWO_ATTEMPT_E2E_BEGIN` / `..._END` bracketing evidence with two
`accept_candidate` attempts, `"replay": {"match": true}`, and `"human_decision": {"status":
"pending", ...}` — the run never selects a winner or gains merge/push authority.

## What a candidate-checkout mistake looks like

Pointing `--candidate` at a checkout that is not the exact frozen SHA fails closed before
any file lookup, with e.g.:

```text
ERROR: candidate SHA drift: <actual HEAD you pointed at>; expected 520ad2c9aa5825476de4957da4702d6823f4edb3 -- see docs/acceptance/REAL_NODE_TWO_ATTEMPT_E2E_LOCAL_RUN.md
```

## Residual uncertainty

- PR #91 is **closed**, not merged. GitHub.com currently still serves
  `refs/pull/91/head` for closed pull requests, so the exact-SHA fetch above works today
  (verified 2026-09-21), but GitHub does not document this as a permanent guarantee.
- The evidence digests in this document's sibling, `docs/conversations/2026-08-28-real-node-verifier-e2e.md`,
  will not reproduce byte-for-byte on a fresh run: `ResultManifest`/`VerificationResult` ids
  embed a fresh random suffix per run, so their digests differ every time even though the
  underlying content does not. Recommendation, required-check outcomes, and
  `candidate_code_executed_by_verifier`/`independent_from_worker` booleans are the load-bearing
  fields to check, not the ids/digests.
