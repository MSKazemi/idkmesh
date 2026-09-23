# Conversation record — Control Tower GUI, interface, and local API

**Date:** 2026-09-22  
**Base revision:** `51c9e425bd3633e4ae67804bc342dbff1ea09875`  
**Related:** issue #572

## Project-owner requirement

> Check the repo and improve the gui and user interface and api

## Repository state checked

The earlier Gate Audit GUI work from PR #560 is already merged into `main`.
Issue #572 now defines the broader Human Control Tower direction and decomposes
it into read-first UI slices.

No open pull request was found implementing the Control Tower.

The repository already contains a committed, replayable Run Evidence Report v0.1
fixture under:

`results/orchestration/replay-fixture-evaluator-plan-good-vs-bad/`

That report is the correct first system-level GUI source because it preserves
worker claims, independent verification, disagreement, failures, pending human
authority, and exact provenance without selecting a candidate.

## Implementation in this turn

A new dependency-free product surface is added:

`idkmesh control-tower [optional-evidence-report.json]`

The first Control Tower includes:

- overview / human-attention screen;
- Run Evidence Report editor/file loader;
- attempt-by-attempt worker-claim and independent-evidence rendering;
- explicit authority layer rather than one collapsed pass/fail badge;
- semantic background activity timeline;
- Local API discovery/capability screen;
- a Verification Tools page that keeps Gate Audit conceptually separate.

The built-in demo mirrors the repository's committed good-vs-bad replay fixture:
one attempt is independently supported, one rejected, and verifier disagreement
is preserved for human review.

## API improvement

A versioned local read API is introduced:

- `GET /api/v1/status`
- `POST /api/v1/run-evidence/inspect`
- `GET /healthz`

The API:

- rejects duplicate JSON keys;
- validates the Run Evidence Report kind/version and all rendered evidence;
- recomputes summary counts and verification disagreement instead of trusting
  presentation fields;
- rejects recommendation/evidence-state mismatches;
- fails closed if a report grants canonical-write, Git-push, merge, or automatic
  candidate-selection authority;
- fails closed if the report does not leave the human decision pending;
- returns a stable structured error envelope.

The semantic timeline is deterministic and sequence-based. Run Evidence Report
v0.1 is not a complete wall-clock event stream, so the UI does not fabricate
timestamps.

## Shared local-UI security

Gate Audit and Control Tower now share the same helper for:

- loopback host;
- per-process random session token;
- 2 MiB body limit;
- loopback Host-header check;
- no-store caching;
- content-type, frame, referrer, cross-origin, permissions-policy, and CSP
  browser headers.

This removes two local browser surfaces drifting independently on their security
boundary.

## Authority decision

The Control Tower is read-only in this slice.

It cannot:

- execute workers;
- replace independent verification;
- record a human decision;
- select a candidate;
- write canonical project state;
- push Git;
- merge.

Human-decision recording remains a later #572 slice and must bind to immutable
evidence rather than being smuggled into a presentation endpoint.

## Verification status

The implementation includes focused model/API/UI/CLI tests.

A local clone/test run from the execution container was attempted but outbound
DNS to github.com is unavailable in that environment. The exact-head GitHub PR
gate is therefore the executable verification boundary for this turn.

## Community impact

This is a progressive-disclosure improvement: a newcomer can inspect a real
two-attempt swarm run without reading experiment scripts or raw evidence JSON,
while maintainers still see the exact digests, failed checks, disagreement, and
authority limits that prevent the UI from becoming an opaque "AI status score."

## Next slices

After this read path is verified, issue #572 can continue with:

1. deeper ResultManifest / VerificationResult provenance;
2. immutable human-decision recording;
3. real event-source timeline;
4. verification debt/capacity;
5. participants/resources/authority matrix;
6. IDKGraph repository health;
7. goal/uncertainty views.

## AI/tool provenance

Implementation and repository updates were produced with ChatGPT using the
connected GitHub tools. No claim of independent human review is made.
