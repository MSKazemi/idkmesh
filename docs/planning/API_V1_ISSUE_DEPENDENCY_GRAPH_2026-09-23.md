# API v1 Issue Dependency Graph

**Date:** 2026-09-23  
**Program:** #713  
**Architecture:** `../architecture/API_CONTROL_PLANE_ARCHITECTURE.md`

This document is the claimable execution map for API professionalization.

## Priority matrix

| Issue | Priority | Outcome | Hard dependencies | Parallel with | Exit evidence |
| --- | --- | --- | --- | --- | --- |
| #735 | P0 | current local API converged/release-qualified | PR #658 + current main | planning only | exact-head green gates, 0 behind main |
| #736 | P0 | conventions/version/deprecation frozen | none after planning review | #735 | accepted spec + ADR/index links |
| #737 | P0 | full schema catalog + compatibility CI | #736 | #738 | schema/example/runtime validation |
| #738 | P0 | unified service/API ownership | #736 | #737 | architecture map + no duplicate canonical objects |
| #739 | P0 | resource-oriented read model | #735 #736 #737 #738 | #741 after contracts | project/run/work/evidence reconstruction |
| #740 | P0 | immutable Human Decision API | #736 #737 #738 #616 #670 | #739 | idempotent digest-bound decision record |
| #741 | P1 | canonical events + resumable SSE | #736 #737 #738 | #739 | historical cursor + resumable stream |
| #742 | P1 | limits/backpressure/drain | #677 | #743 #744 | overload/slow-client/drain tests |
| #743 | P1 | network security profile | #670 #736 #738 | #742 #744 | scope/auth/proxy/CORS/CSRF matrix |
| #744 | P1 | metrics/tracing/SLO | #677 | #742 #743 | bounded telemetry + SLO evidence |
| #745 | P1 | qualification suite | #736 #737 | starts early, completes late | contract/fuzz/load/security report |
| #746 | P2 | official clients + API docs | stable read contracts | #745 later | Python + typed web client examples |
| #747 | P2 | v1 beta release | declared beta-scope issues | none at final gate | tag + qualification report |

## Existing subsystem dependencies

These are dependencies, not child replacements:

| Existing issue | API program dependency |
| --- | --- |
| #677 | reusable HTTP service runtime |
| #670 | trusted actor + authorization semantics |
| #616 | restart-safe local metadata/idempotency |
| #580 | connector CLI/HTTP surface |
| #570 | connector-control program |
| #682 | end-to-end Product Spine |
| #572 | Control Tower UX |
| #667 | enterprise security/reliability program |

## Recommended waves

### Wave 0 — freeze the ground

Work:

- #735 convergence;
- #736 conventions;
- #738 architecture agreement.

Do not add new API domains before this wave is stable.

### Wave 1 — contracts

Work:

- #737 schema catalog;
- begin #745 compatibility/conformance harness.

Goal:

Every later endpoint starts from a testable contract.

### Wave 2 — complete read model

Work:

- #739 project/WorkUnit/run/evidence resources;
- #741 event envelope/query/SSE.

Goal:

A read-only Control Tower/SDK can observe the product without direct repository
file parsing.

### Wave 3 — accountable mutation

Prerequisites:

- #616 persistence/idempotency;
- #670 identity/policy;
- #736/#737/#738 contract/architecture.

Work:

- #740 Human Decision API.

Goal:

Record human/governance decisions against immutable evidence with no integration
execution.

### Wave 4 — network hardening

Work in parallel:

- #742 reliability/overload;
- #743 network security profile;
- #744 observability/SRE.

Goal:

A production transport can run behind a reviewed identity/proxy/storage boundary.

### Wave 5 — qualification and developer experience

Work:

- complete #745;
- #746 SDK/docs.

Goal:

External contributors integrate against supported contracts, not server
internals.

### Wave 6 — beta

Work:

- #747.

No beta tag before the declared beta scope has exact-source qualification.

## Critical path

```text
#735
  |
#736
  |\
  | +--> #737 ----+
  |               |
  +----> #738 ----+----> #739 ----+
                   \             |
                    +--> #741 ----+--> #745 --> #746 --> #747
                   /
#616 + #670 ------+----> #740 ----+
```

Operational parallel path:

```text
#677 ----> #742
  |          |
  +------> #744 ----+
                     +--> #745
#670 + #738 -> #743 -+
```

## Contributor slicing rule

A child implementation PR should normally close one bounded acceptance slice,
not an entire multi-month issue.

Good examples:

- one schema + fixture + compatibility test;
- one list endpoint + pagination contract + negative tests;
- one idempotency record path;
- one SSE resume fixture;
- one authorization middleware integration;
- one load-test harness.

Avoid PRs that simultaneously introduce:

- a new domain object;
- a new persistence model;
- a new auth model;
- multiple endpoint families;
- UI redesign;
- deployment infrastructure.

Those changes are difficult to independently verify and create convergence debt.

## Readiness checklist before coding an issue

The issue is implementation-ready only when:

- [ ] purpose is one sentence;
- [ ] canonical domain owner identified;
- [ ] dependencies resolved or mocked through stable interfaces;
- [ ] request/response schema named;
- [ ] authority ceiling named;
- [ ] security profile named;
- [ ] idempotency/concurrency rule named if mutating;
- [ ] expected event/audit output named;
- [ ] limits named;
- [ ] negative cases named;
- [ ] acceptance evidence named;
- [ ] docs/OpenAPI update named.

If any item is unknown, improve the issue/specification before implementation.

## Completion rule

Checkbox completion is evidence-based.

An issue is not complete because code exists on a branch. It closes only when
its acceptance artifacts are integrated and reproducible from the canonical
repository state.
