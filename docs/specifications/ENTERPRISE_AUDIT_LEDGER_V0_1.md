---
description: "Enterprise Audit Ledger v0.1: a compact evidence stream of identities, authorization decisions, resource revisions, and outcomes of privileged operations."
---
# Enterprise Audit Ledger v0.1

**Status:** experimental  
**Issue:** #671  
**Parent:** #667  
**Schema:** `schemas/enterprise-audit-event-v0.1.schema.json`

## Purpose

The Enterprise Audit Ledger is a compact security/audit evidence stream for
privileged enterprise operations. It is deliberately separate from:

- ordinary application/access logs; and
- the Product Spine lifecycle event stream.

The Product Spine event source answers "what lifecycle transition happened?"
for the run model. This ledger answers "which authenticated identities,
authorization decision, scoped resource revision, and outcome were involved in
a privileged enterprise operation?"

An audit event is **evidence only**. It does not authorize or execute the action
it records.

## Runtime boundary

The dependency-free implementation is
`idkmesh.enterprise_audit.LocalEnterpriseAuditLedger`.

Appending requires one `AuditEventInput` composed from:

- an existing `AuthorizationDecision`;
- the matching normalized `ActorContext`;
- a trusted service `ActorContext` that is scoped to the target project;
- an exact immutable resource revision;
- an explicit operation outcome;
- an optional run id and evidence/result digest;
- an explicit minimum retention period.

The recorder does not accept an arbitrary payload/metadata map. In particular,
it does not copy the authorization decision's free-form explanatory
`message`. The retained reason is the stable decision `code`.

This deliberately shrinks the surface on which prompts, headers, tokens,
credentials, or other secret material could accidentally become audit data.

## Event contract

Every event binds:

- monotonically increasing `sequence`;
- deterministic `event_id` (`audit-000000000001`, ...);
- caller-supplied `occurred_at_epoch`;
- exact tenant and project;
- request id and optional run id;
- actor principal/type/issuer/identity revision;
- audit-writing service principal/type/issuer/identity revision;
- action;
- resource type/id and exact immutable revision;
- authorization effect and stable reason code;
- policy id + policy revision;
- approval principal/reference where applicable;
- canonical digest of the complete authorization decision;
- operation outcome;
- optional evidence/result digest;
- minimum retention period and derived eligibility epoch;
- previous event digest;
- current event digest;
- an explicit no-authority ceiling.

The event has no generic `payload`, `headers`, `metadata`, `prompt`, or
`secret` field.

## Authorization relationship

The audit writer reuses the existing E3 authorization objects rather than
creating a second policy engine.

The `AuthorizationDecision` supplies the requested tenant/project,
principal, action, resource identity, policy revision, effect, reason code and
approval evidence. The event stores a canonical SHA-256 digest of the complete
decision object.

The supplied actor must match the decision principal and identity revision.

The actor is **not required to be authorized for the target scope**. That is
intentional: a denied cross-tenant access attempt is important audit evidence.
The trusted service writing the audit record **must** be bound to the target
tenant/project scope.

## Append-only storage

The local reference adapter uses a dedicated SQLite database with
`PRAGMA user_version = 1`.

The `enterprise_audit_events` table has:

- an `INTEGER PRIMARY KEY AUTOINCREMENT` sequence;
- a unique event id;
- a unique event digest;
- the previous digest;
- canonical JSON for the full event;
- scope/time columns needed for bounded queries.

Two SQLite triggers abort every `UPDATE` and `DELETE`. The public ledger
API has no update or delete method.

Appending runs under `BEGIN IMMEDIATE`, so concurrent writers serialize the
selection of the previous head, next sequence, hash-chain construction, and
insert.

## Hash chain and tamper verification

The event digest is:

`sha256(canonical-json(event-without-event_digest))`

The canonical JSON rule is sorted keys, compact separators and UTF-8.

Each event includes the previous event's digest, so replay verification checks:

1. sequences are gap-free and ordered;
2. row metadata matches canonical event content;
3. each event digest recomputes exactly;
4. each previous-digest link matches the preceding event.

This detects rewrite, reordering and interior deletion.

### Tail-truncation boundary

A hash chain by itself cannot prove that the final rows were not silently
removed if the verifier has no prior knowledge of the old head.

For that reason the ledger exposes an `AuditCheckpoint`:

- `event_count`;
- `head_sequence`;
- `head_digest`.

`verify(expected_checkpoint=...)` compares the current ledger against that
saved checkpoint. A tail deletion then fails event-count, head-sequence and/or
head-digest verification.

A production deployment that needs truncation evidence must persist/checkpoint
the head in a separately governed location (for example a durable archive,
attestation service, or external SIEM). The local SQLite file cannot
self-authenticate its own missing suffix.

## Export / SIEM contract

`AuditExportSink` is the vendor-neutral export protocol:

`write_event(event: Mapping[str, Any]) -> None`

`LocalEnterpriseAuditLedger.export_to_sink(...)` requires an explicit
`tenant_id`, optionally narrows to one `project_id`, reads validated events in
sequence order and calls that boundary. Unscoped cross-tenant export is not a
convenience default. Export does not mutate ledger state.

`JsonLinesAuditSink` is the dependency-free reference sink. It emits one
canonical event per NDJSON line, suitable for:

- a governed file/archive;
- a local forwarder;
- a future Splunk/Elastic/Sentinel/syslog/OTel bridge.

Vendor-specific delivery, authentication, retries and acknowledgement semantics
belong in adapters above this contract. A failed sink call cannot alter the
ledger.

## Retention and legal hold

Each event records:

- `minimum_days`;
- deterministic `eligible_after_epoch`.

The helper `retention_state(...)` returns one of:

- `retain`;
- `eligible_for_expiry`;
- `legal_hold`.

A governed external legal-hold system may supply a
`legal_hold_hook(event) -> bool`.

This module intentionally does **not** implement deletion. Reaching retention
eligibility is evidence that an external retention controller may consider the
event for expiry; it is not deletion authority.

## Secret boundary

The contract is fixed-shape and stores identifiers/digests rather than
arbitrary request data. Raw credential values, Authorization headers, API
tokens, prompts and secret material must never be passed as identifiers.

No software can infer whether an opaque identifier string was actually copied
from a secret. Operators/adapters therefore remain responsible for supplying
only normalized identities, references, stable reason codes and digests. The
ledger reduces the accidental-leak surface; it does not make a false claim that
arbitrary strings can be classified perfectly.

## Failure behavior

The ledger fails closed when:

- its SQLite schema version is newer than supported;
- the audit-writing service is untrusted, revoked, expired, or out of scope;
- actor identity does not match the authorization decision;
- timestamps/revisions/digests are malformed;
- authorization effect and recorded outcome contradict one another;
- retained event JSON or row metadata fails integrity validation.

A denied actor may still be recorded because denial itself is security
evidence.

## Authority

Every event fixes the following authority ceiling:

```json
{
  "audit_only": true,
  "authorizes_action": false,
  "canonical_state_write": false,
  "git_push": false,
  "merge": false
}
```

A valid hash chain proves consistency of retained audit evidence relative to
its checkpoint. It does not prove the underlying operation was correct, that
all privileged operations were instrumented, or that an external compliance
standard is satisfied.

## Relationship to later enterprise work

This E4 ledger is a reusable evidence primitive for E8/E9 service integration.
Future middleware can append events after authorization and operation outcomes
without changing the E3 policy kernel.

Completeness of real production event coverage remains an integration concern:
the pure E3 `authorize()` function stays side-effect free and does not write
audit state itself.
