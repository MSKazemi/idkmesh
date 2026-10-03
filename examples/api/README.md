# API Convention and Control Tower Fixtures

These fixtures are the machine-testable examples issue #736 (P0 API-1)
requires before `docs/specifications/API_CONVENTIONS_V0_1.md` can be frozen:
section 19 of that specification requires public objects to have canonical
JSON Schemas and requires their examples to validate in CI, not just read as
plausible prose. Issue #900 extends the same coverage to the frozen Control
Tower response schemas.

## Cross-cutting transport envelopes

- `error-envelope.example.json` — the standard error envelope from section 5,
  validated against `schemas/idkmesh-api-error-v0.1.schema.json`.
- `list-envelope.example.json` — the standard paginated list envelope from
  section 10, validated against `schemas/idkmesh-list-v0.1.schema.json`.

Both are cross-cutting transport envelopes, not domain objects: a list
endpoint's `items[]` entries and an error's `details` remain owned by the
domain specification that emits them, not by these two schemas.

## Control Tower and Product Spine domain documents

- `product-spine-run.example.json` — a canonical
  `idkmesh-product-spine-run` v0.1 projection in `state="proposed"`,
  validated against `schemas/idkmesh-product-spine-run-v0.1.schema.json`.
  The same shape is accepted by `idkmesh run create`, so this file doubles as
  a runnable input fixture.
- `control-tower-status.example.json` — the `GET /api/v1/status`
  discovery/status document from
  `docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md`, validated against
  `schemas/idkmesh-control-tower-status-v0.1.schema.json`. Its values mirror
  `idkmesh.control_tower_api.status_document()`.
- `readiness.example.json` — a `GET /readyz` readiness document, validated
  against `schemas/idkmesh-readiness-v0.1.schema.json`.
- `control-tower-run-response.example.json` — the success envelope returned
  by `GET /api/v1/runs/{run_id}`, validated against
  `schemas/idkmesh-control-tower-run-response-v0.1.schema.json`. It wraps a
  realistic run with two attempts: a first `worker_error` attempt and a
  second `verified` attempt, matching the two-attempt orchestrator policy.
- `control-tower-run-attempts-response.example.json` — the success envelope
  returned by `GET /api/v1/runs/{run_id}/attempts`, validated against
  `schemas/idkmesh-control-tower-run-attempts-response-v0.1.schema.json`. It
  lists the same two attempts as the run response above.

## Negative fixture

- `invalid-missing-status.readiness.json` — a readiness document with the
  required `status` property removed; committed to prove
  `schemas/idkmesh-readiness-v0.1.schema.json` rejects it.

All digests, ids, timestamps, and revisions in these fixtures are
deterministic placeholders: no real tokens, hostnames, or personal data
appear here.

`tests/test_example_contract_coverage.py` registers every fixture in this
directory against its schema (or records why it has none), so a future
incompatible change to any contract shape fails CI here rather than silently
drifting from the frozen specification.
