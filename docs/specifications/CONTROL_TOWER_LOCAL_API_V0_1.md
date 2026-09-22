# Control Tower Local API v0.1

**Status:** experimental, local-only, read-only  
**Issue:** #572  
**Product surface:** `idkmesh control-tower`

## Purpose

The Control Tower is the first system-level browser surface for the IDKMesh
Verified Swarm Runner. It renders already-produced evidence for a human without
becoming a scheduler, verifier, decision maker, repository writer, or merge
authority.

Its first supported source contract is:

`idkmesh-run-evidence-report / schema_version 0.1`

The API exists so the browser UI and future local clients consume the same
validated presentation model instead of each reinterpreting evidence files.

## Trust boundary

The service binds only to `127.0.0.1`.

Every API request except `/healthz` and the HTML document itself requires a
random per-process token in:

`X-IDKMesh-UI-Token`

The browser receives that token only in the locally served page. The server also
requires a loopback `Host` header and rejects cross-origin preflight.

Responses carry no-store caching plus frame, referrer, content-type,
cross-origin-resource/opener, permissions-policy, and CSP restrictions shared
with the Gate Audit local UI.

This is local process isolation, not a claim that localhost is a complete
sandbox against a compromised machine.

## Authority invariant

The Control Tower must never turn presentation into authority.

A Run Evidence Report is refused unless its authority object is exactly:

```json
{
  "canonical_state_write": false,
  "git_push": false,
  "merge": false,
  "automatic_candidate_selection": false
}
```

and its human-decision object remains:

```json
{
  "status": "pending",
  "selected_attempt_id": null,
  "integration_authority": "external_human_or_governance"
}
```

v0.1 therefore cannot:

- execute workers;
- run or replace independent verification;
- record a human decision;
- select a candidate;
- mutate canonical project state;
- push Git;
- merge.

Those capabilities require separately reviewed contracts and authority.

## Endpoints

### `GET /healthz`

Simple process-liveness response:

```text
ok
```

It does not reveal report or project state.

### `GET /api/v1/status`

Returns API discovery and the capabilities that are intentionally disabled.

Example shape:

```json
{
  "api_version": "v1",
  "service": "idkmesh-control-tower",
  "mode": "local-read-only",
  "source_contracts": [
    "idkmesh-run-evidence-report/0.1"
  ],
  "capabilities": {
    "run_evidence_inspection": true,
    "semantic_timeline": true,
    "human_decision_recording": false,
    "worker_execution": false,
    "canonical_state_write": false,
    "git_push": false,
    "merge": false,
    "automatic_candidate_selection": false
  }
}
```

### `POST /api/v1/run-evidence/inspect`

Content type:

`application/json`

Body:

one complete `idkmesh-run-evidence-report` v0.1 document.

The service rejects malformed JSON, duplicate JSON keys, unsupported report
versions/kinds, malformed digests, invalid attempt states, recommendation /
evidence-state mismatches, summary drift, authority drift, or a non-pending
human decision.

The response is a read-only `idkmesh-control-tower-snapshot`.

## Snapshot semantics

The snapshot has five human-facing layers.

### Source

It retains the run, config, verifier-policy, and WorkUnit identifiers/digests.

### Summary

Counts are recomputed from `attempts[]`; the API does not trust the report's
summary fields merely because they are present.

The service independently recomputes:

- attempt count;
- supported count;
- rejected count;
- inconclusive count;
- control-error count;
- verification disagreement;
- control-failure presence.

A mismatch fails closed.

### Human attention

The Control Tower emits explicit reasons for attention, currently including:

- verification disagreement;
- control-path failure;
- rejected attempt evidence;
- pending human integration decision.

These are explanatory alerts, not a ranking or automated decision.

### Attempts

Every attempt is displayed as separate layers:

```text
worker claim
  -> independent evidence / recommendation
  -> human authority remains pending
```

The UI deliberately avoids one green/red status that would collapse those
different meanings.

### Semantic timeline

The timeline is derived from evidence order and types:

- observation;
- worker claim;
- independent evidence;
- verifier recommendation;
- control error;
- attention condition;
- authority boundary.

Run Evidence Report v0.1 does not contain a complete wall-clock event log.
Therefore v0.1 uses a deterministic `sequence` and does **not** invent
timestamps.

A future event-source contract can add real timestamps without silently changing
the meaning of v0.1.

## Error envelope

API errors use:

```json
{
  "api_version": "v1",
  "ok": false,
  "error": {
    "code": "invalid_run_evidence",
    "message": "human-readable explanation"
  }
}
```

Stable v0.1 codes include:

- `invalid_host`;
- `invalid_session_token`;
- `unsupported_media_type`;
- `length_required`;
- `invalid_content_length`;
- `payload_too_large`;
- `invalid_utf8`;
- `invalid_run_evidence`;
- `preflight_not_supported`;
- `not_found`.

## Interpretation rules

Every client must preserve these project boundaries:

```text
worker success != verified correctness
verifier recommendation != human integration decision
multiple recommendations != majority truth
replay equality != correctness
```

## CLI

Start with the repository demo loaded:

```bash
idkmesh control-tower
```

Open a specific generated report:

```bash
idkmesh control-tower path/to/evidence-report.json
```

Headless/server-only:

```bash
idkmesh control-tower --no-browser --port 8770
```

## Relationship to Gate Audit

`gate-audit-ui` and `control-tower` are complementary.

Gate Audit answers:

> How much independent evidence does this verifier panel actually provide?

Control Tower answers:

> What happened in this multi-attempt run, what evidence exists, where is there
> disagreement/failure, and what still needs a human decision?

Both local UIs share one browser-security helper, but they retain separate
domain contracts.

## Next compatible extensions

Issue #572 defines the next read-first slices:

1. deeper ResultManifest / VerificationResult provenance;
2. human-decision recording bound to immutable report digest;
3. real semantic event-source timeline;
4. verification-debt/capacity panel;
5. participants/resources/authority matrix;
6. IDKGraph repository-health panel;
7. goal/uncertainty view.

Write/actuation endpoints are explicitly outside v0.1.
