# Verification Provenance Integrity

Status: experimental Phase 0 contract hardening

## Purpose

IDKMesh already separates:

```text
Work Unit
  -> worker ResultManifest
  -> independent VerificationResult
  -> integration / human / governance decision
```

JSON Schema can validate the shape of each object, but shape validation alone cannot prove that the objects refer to the exact same underlying work and result.

A verifier could otherwise provide a schema-valid `result_manifest_digest` or `work_unit_digest` that does not match the referenced object while the IDs still look correct.

## Canonical digest

The Phase 0 integrity rule uses deterministic JSON serialization:

```text
json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

The UTF-8 bytes are hashed with SHA-256 and encoded as:

```text
sha256:<64 lowercase hex characters>
```

This is the same canonical-digest convention already used by the Phase 0 harness.

## Required bindings

For a tuple `(WorkUnit, ResultManifest, VerificationResult)` the integrity checker requires:

1. `ResultManifest.work_unit_id == WorkUnit.id`.
2. `ResultManifest.work_unit_version == WorkUnit.version`.
3. `ResultManifest.provenance.work_unit_digest == canonical_digest(WorkUnit)`.
4. `VerificationResult.result_manifest_id == ResultManifest.id`.
5. Work Unit id, Work Unit version, and attempt agree between verification and worker result.
6. `VerificationResult.provenance.result_manifest_digest == canonical_digest(ResultManifest)`.
7. `VerificationResult.provenance.work_unit_digest == canonical_digest(WorkUnit)`.
8. `VerificationResult.provenance.source_revision == ResultManifest.provenance.source_revision`.
9. `VerificationResult.independence.worker_id_observed == ResultManifest.worker.id`.
10. When independence is claimed, verifier identity must differ from worker identity.

The existing Phase 0 harness continues to enforce validator coverage, evidence references, independent-verifier requirements, and decision-support constraints. This integrity layer complements rather than replaces those checks.

## Why this is separate from schema validation

Cross-object equality and cryptographic binding are relational properties. JSON Schema validates one document at a time and should not be stretched into pretending that it has independently loaded and hashed referenced objects.

The executable rule therefore lives in:

`experiments/provenance_integrity.py`

and runs in Phase 0 CI.

## Fixtures

Positive fixtures:

- `examples/work-units/phase0-smoke.work-unit.json`
- `examples/results/phase0-smoke.result-manifest.json`
- `examples/results/phase0-smoke.verification-result.json`

Negative fixture:

- `examples/results/invalid-mismatched-provenance.verification-result.json`

The negative fixture is deliberately schema-shaped and otherwise plausible, but declares the wrong ResultManifest digest. CI must reject it.

## Trust consequence

A matching digest proves object identity under the canonical serialization convention; it does **not** prove that the candidate is correct, that the verifier is honest, or that the result should be merged.

The trust model remains:

**proposal != proof**, and **verification evidence != final authority**.

## Evolution note

This Phase 0 convention is intentionally simple. If IDKMesh later adopts signed attestations, Merkle transparency logs, content-addressed stores, DSSE/in-toto envelopes, or another provenance standard, the same invariant should remain: every verification statement must be bound to the exact candidate and exact work specification it claims to evaluate.
