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
- `control-tower-metrics.example.json` — a privacy-safe aggregate
  `GET /api/v1/metrics` response, validated against
  `schemas/idkmesh-api-operational-metrics-v0.1.schema.json`. It demonstrates
  fixed-cardinality counters, latency buckets, bounded concurrency/admission
  state, and the explicit absence of payload- or identity-derived labels.
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
- `control-tower-run-evidence-response.example.json` — the success envelope
  returned by `GET /api/v1/runs/{run_id}/evidence`, validated against
  `schemas/idkmesh-control-tower-run-evidence-response-v0.1.schema.json`. It
  retains the full `idkmesh-run-evidence-report` for the same run.
- `control-tower-inspection-response.example.json` — the success envelope
  returned by `POST /api/v1/run-evidence/inspect`, validated against
  `schemas/idkmesh-control-tower-inspection-response-v0.1.schema.json`. Its
  `snapshot` member is a full `idkmesh-control-tower-snapshot` built by
  `idkmesh.control_tower_api.build_snapshot()` from the same evidence report,
  and the snapshot itself validates against
  `schemas/control-tower-snapshot-v0.1.schema.json` — the frozen contract the
  response wrapper deliberately does not duplicate.
- `control-tower-project-response.example.json` — the success envelope
  returned by `GET /api/v1/projects/{project_id}`, validated against
  `schemas/idkmesh-control-tower-project-response-v0.1.schema.json`. Its
  `runs_by_state` is zero-filled with every canonical run state, as the
  resource contract requires.
- `control-tower-work-unit-response.example.json` — the success envelope
  returned by `GET /api/v1/work-units/{work_unit_id}`, validated against
  `schemas/idkmesh-control-tower-work-unit-response-v0.1.schema.json`.
- `event.example.json` — one `idkmesh-event` envelope, the document each SSE
  `data:` frame of `GET /api/v1/events/stream` carries, validated against
  `schemas/idkmesh-event-v0.1.schema.json`. It mirrors the event the Product
  Spine store commits for a run creation.

## Request bodies and record contracts

- `run-evidence-report.example.json` — a canonical
  `idkmesh-run-evidence-report` v0.1, validated against
  `schemas/run-evidence-report-v0.1.schema.json`. It is the request body of
  `POST /api/v1/run-evidence/inspect` and the document embedded in the
  run-evidence response above, and it passes
  `idkmesh.control_tower_api.validate_run_evidence_report()` — the same
  contract-focused validator the endpoint runs before serving anything.
- `idempotency-admission.example.json` and
  `idempotency-conflict.example.json` — the two forms of the
  `idkmesh-idempotency-v0.1` `oneOf`, both validated against
  `schemas/idkmesh-idempotency-v0.1.schema.json`. The admission form reserves
  one idempotency key against one canonical request digest; the conflict form
  is the same key presented with a different digest.
- `human-decision-record.example.json` — an
  `idkmesh-human-decision-record` v0.1 companion record, validated against
  `schemas/human-decision-record-v0.1.schema.json` and produced by
  `experiments/record_human_decision.py`'s builder. It decides the evidence
  report above by content digest without mutating it, and it carries no
  canonical-state-write, git-push, or merge authority. The run response
  fixture shows `run/example-1` before this decision was recorded (its
  `human_decision_record_digest` is still null there).

## Negative fixture

- `invalid-missing-status.readiness.json` — a readiness document with the
  required `status` property removed; committed to prove
  `schemas/idkmesh-readiness-v0.1.schema.json` rejects it.

The fixtures describe one consistent example world: `run/example-1` on
`work/example-1` in `project.example`, with a failed first attempt and a
verified second one. All ids, timestamps, and revisions are deterministic
placeholders — no real tokens, hostnames, or personal data appear here — and
so is every digest that names content these fixtures do **not** embed (a
WorkUnit document, a result manifest, a create request).

A digest that names content a fixture does embed is different: it is the real
canonical digest of that content, because the digest binding is the trust
property those envelopes advertise ("a caller can detect a swapped or
corrupted snapshot without re-deriving it"). The evidence report's digest, the
inspection snapshot's digest, and the event payload's digest all recompute,
`tests/test_api_contract_conformance.py` re-derives each of them in CI, and
the same evidence-report digest is named from three fixtures — so the set
cannot quietly split into three different reports either.

`tests/test_example_contract_coverage.py` registers every fixture in this
directory against its schema (or records why it has none), so a future
incompatible change to any contract shape fails CI here rather than silently
drifting from the frozen specification.

`tests/test_api_contract_conformance.py` additionally binds each fixture to
the exact response it documents and resolves the target schema from
`openapi.yaml`, so the endpoint, the advertised contract, and the schema this
README names must all agree — a fixture cannot keep validating against a
schema the API no longer advertises.
