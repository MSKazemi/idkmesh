---
description: "E5 issue 672: bounded raw-secret checks at canonical WorkUnit source binding and enterprise audit persistence/export."
---
# E5 raw-secret write-boundary integration — 2026-10-13

## Why this slice exists

The scanner landed in PR #1118 as a **pure diagnostic**. Issue #672 requires
that raw credentials not reach durable WorkUnits, results or audit records.
A scanner which is never invoked at a write boundary is not enforcement.

## Source-aligned changes

- `idkmesh.work_unit_binding.bind_work_unit_source` and
  `validate_work_unit_source_binding` check the entire supplied JSON-shaped
  WorkUnit before recording or accepting its digest/source binding. Known
  credential literals or an incomplete scan raise `WorkUnitBindingError`.
- `idkmesh.enterprise_audit.validate_audit_event` checks the exact canonical
  audit record that `LocalEnterpriseAuditLedger.append` stores. Denial raises
  `EnterpriseAuditError`, and the append transaction rolls back.
- `JsonLinesAuditSink.write_event` independently invokes that validator,
  defending a direct caller who bypasses the SQLite export path.

Both exception types remain stable, with codes `raw_secret_detected` or
`secret_scan_incomplete`; no raw value is included in an error. The scanner
does not mutate objects, widen authority or alter canonical digest algorithms.

## Falsification / tests

The focused regressions cover recognized token values in an objective and ID,
nested credential-key literals, an unscannable object, safe env/vault-style
references, rejection after WorkUnit content changes, SQLite rollback and
continued sequence integrity after a rejected audit append, and refusal to
write a single byte of a secret-bearing direct NDJSON event.

Exact-head GitHub CI, CodeQL, markdown/reference checks and independent review
are required before merge. Tests are automated and synthetic; this is **not
independent certification**.

## Limits and remaining work

Not covered: raw GitHub issue/preview intake before binding; arbitrary JSON
WorkUnit file creation; ResultManifest, provider output, verification report,
ordinary logs, evidence publication, or non-E4 audit stores. Unknown, encoded,
split or short credentials can pass a scanner and still violate policy.
Integrate guards for those boundaries as separate, reviewed issue #672 slices.
No GitHub branch retirement, deployment, live secret, or API mutation is part
of this E5 change.

## Community impact

A clear, testable protection at two real write/admission boundaries reduces
accidental credential exposure without presenting a partial safeguard as a
universal enterprise security guarantee.
