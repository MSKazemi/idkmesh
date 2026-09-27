# API Convention Envelope Fixtures

These fixtures are the machine-testable examples issue #736 (P0 API-1)
requires before `docs/specifications/API_CONVENTIONS_V0_1.md` can be frozen:
section 19 of that specification requires public objects to have canonical
JSON Schemas and requires their examples to validate in CI, not just read as
plausible prose.

- `error-envelope.example.json` — the standard error envelope from section 5,
  validated against `schemas/idkmesh-api-error-v0.1.schema.json`.
- `list-envelope.example.json` — the standard paginated list envelope from
  section 10, validated against `schemas/idkmesh-list-v0.1.schema.json`.

Both are cross-cutting transport envelopes, not domain objects: a list
endpoint's `items[]` entries and an error's `details` remain owned by the
domain specification that emits them, not by these two schemas.

`tests/test_example_contract_coverage.py` registers both fixtures against
their schema, so a future incompatible change to either envelope shape fails
CI here rather than silently drifting from the frozen specification.
