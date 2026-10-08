# GitHub Durable Ledger Record v0.1

**Status:** experimental C9-A contract  
**Issue:** #597  
**Authority:** evidence/state record only; no dispatch, verification, acceptance, integration, Git-push, or merge authority.

## Purpose

GitHub Actions runners are ephemeral. A no-server IDKMesh project therefore needs
a compact record that can survive runner teardown and tell a later coordinator:

- which exact WorkUnit/source revision was being handled;
- why a connector was or was not eligible;
- which connector was selected;
- which deterministic dispatch/idempotency identity was used;
- which attempt/provider operation followed;
- which candidate/result/verification/human-decision evidence was retained;
- whether a failure/cancellation/recovery condition occurred.

The machine-readable contract is
`schemas/github-ledger-record-v0.1.schema.json`. A representative synthetic
dispatch record is
`examples/github-ledger/dispatch-record-v0.1.json`.

C9-A freezes the **record shape only**. C9-B/C9-C own deterministic append
serialization and optimistic/concurrent Git writes.

## Record model

One ledger record is one immutable event observation. It contains:

1. repository/project/run identity;
2. a monotonic ledger sequence and previous-record digest reference;
3. event identity, timestamp, state, trigger, initiating GitHub actor, and
   optional delivery ID;
4. exact WorkUnit ID/version/digest and 40/64-hex source revision;
5. route/policy evidence;
6. deterministic dispatch idempotency identity;
7. optional attempt/provider state;
8. optional compact evidence references;
9. human-decision state;
10. optional failure classification;
11. an all-false authority ceiling.

The record does not contain mutable “current state” that overwrites earlier
history. Later records describe later observations.

## Route evidence

The route object deliberately preserves the recovery context requested by
#601:

- `routing_digest`;
- `policy_version`;
- required capability tier;
- authority mode;
- risk class;
- every eligible connector plus supported tier;
- every ineligible connector plus reasons;
- selected connection, if any;
- deterministic selection reason list.

The tier, authority, and risk vocabularies match
`idkmesh.connector_routing` v0.1.

This allows a killed coordinator to reconstruct not only **what** was selected
but **why**.

## Idempotency

Every record carries:

- `dispatch_key`;
- canonical `request_digest`;
- `attempt_number`.

The schema does not itself reserve or execute that key. C9-D must define atomic
admission semantics so:

```text
same dispatch_key + same request_digest -> existing logical run/attempt
same dispatch_key + different request_digest -> conflict
```

Actions `concurrency` may serialize work but is never the durable idempotency
source.

## Attempt and provider references

An attempt, when present, records:

- stable attempt ID;
- attempt number;
- reason: initial, retry, escalation, or recovery;
- selected connector ID.

Provider metadata is intentionally compact:

- driver + driver version;
- submission state;
- external run/session/job identifiers.

Provider tokens, auth headers, credentials, request payloads, prompts, and raw
provider responses are outside the contract.

`submission_state=ambiguous` is preserved explicitly so recovery can avoid
blind resubmission when it is unknown whether a provider accepted the request.

## Evidence references

CandidateReference, ResultManifest, VerificationResult, and Human Decision
content are not embedded in the ledger record.

A retained reference contains only:

- evidence kind;
- canonical SHA-256 digest;
- optional repository-relative storage path.

Repository-relative paths are bounded and reject `..` traversal. They are
references to separately retained evidence; a digest/reference is not a verdict.

The ledger record intentionally does not use Actions artifacts/caches as a
canonical evidence locator because those have finite retention. C9-H will
define the retention policy.

## Human decision

Human decision state is explicit:

- `not_recorded`;
- `pending`;
- `recorded`.

When recorded, the ledger may carry the retained Human Decision Record digest
and repository-relative reference. It does not execute the decision or grant
integration authority.

## Failures and negative evidence

Failure is a first-class optional object with:

- stable code;
- coarse classification;
- retryable boolean.

Failed/cancelled/recovery-required observations remain append-only records.
C9-B/C9-E must never reconstruct state by silently dropping negative events.

## Integrity chain

`ledger_sequence` and `previous_record_digest` prepare the contract for an
append-only chain:

- the first record may use `previous_record_digest = null`;
- each later record points at the canonical digest of the previous record;
- C9-B defines canonical serialization/digest calculation;
- C9-C defines compare-and-set/optimistic write semantics.

The schema alone does not prove that a Git branch is append-only or that a
previous digest exists. Those are storage/protocol properties for later slices.

## Secret boundary

The schema is closed at the top level and every nested object. It contains no
fields for:

- tokens;
- passwords;
- API keys;
- authorization headers;
- raw secret values;
- provider request/response payloads.

External provider identifiers are identifiers only. Implementations must not
smuggle credentials into those strings.

## Authority ceiling

A valid record structurally fixes every authority flag to `false`:

- dispatch;
- verification;
- acceptance;
- canonical-state write;
- Git push;
- integration;
- merge.

The record is evidence about an operation/state transition. It is never a
credential or authorization to perform the next transition.

## Non-goals

C9-A does not implement:

- Git branch/file layout;
- append serialization;
- hash calculation beyond referenced canonical digests;
- concurrency or compare-and-set;
- dispatch;
- provider reconciliation;
- recovery;
- retention policy;
- repository mutation.

Those remain C9-B through C9-H.

## Compatibility

v0.1 is experimental but versioned. Once durable records are written under this
schema, breaking semantic changes require a new schema version so historical
ledger evidence remains interpretable.
