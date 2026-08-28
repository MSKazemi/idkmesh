# Conversation record: real two-attempt evidence and peer-failure isolation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Instruction

The project owner instructed the assistant to continue improving IDKMesh and preserve substantive project work publicly in the repository.

## Real two-attempt milestone

PR #116 extended the existing deterministic two-attempt kernel rather than introducing another orchestrator. It preserved the legacy verifier-policy path and added:

- canonical EvaluatorPlan v0.2 routing;
- execution-neutral `result-bundle` consumption;
- explicit verification-control kind/backend/digest provenance;
- unchanged no-write/no-push/no-merge/no-auto-selection authority.

Its Phase 0 and run-evidence checks passed.

Stacked PR #120 then executed two fresh real node attempts using exact node candidate:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Both attempts used the same immutable WorkUnit/source revision, produced distinct ResultManifest identities, and independently produced the same deterministic patch bytes. Both were independently supported through one EvaluatorPlan. The existing non-selecting Run Evidence Report retained both attempts and selected neither.

Measured evidence from workflow run `33187138621`, job `98902944926`:

- WorkUnit digest: `sha256:40993e892a5b83962364686809f7ec6e94ef379e10aaea9492a0526ed7695e2e`;
- EvaluatorPlan digest: `sha256:bdd8a982b47e91d9ef1e1d0e18eb0ab69cd94b8ff7b4e1d1988fc559ea755e94`;
- config digest: `sha256:65c5f623ab7242a609519c5d05bfb1832c0acec7d8322146b49ce4b6f559370f`;
- saved/replayed run digest: `sha256:7394db0990d031b86b26cd457b4b94395740218865d3d45d0f150cf2dda2ece6`;
- replay match: `true`;
- report digest: `sha256:f6775b4d7a53a6b7b0522e6dbbd49acf4646a58cfbcd22b4ff5bc48f592f8096`;
- supported attempts: `2`;
- selected attempt: `null`;
- human decision: `pending`.

This completed the real multi-attempt report/replay evidence item in issue #5 Phase B1.

## Remaining v0.1 gap selected next

The next unproven product property was not another protocol. It was real peer-failure isolation:

> Can one real worker fail before producing a ResultManifest while its peer still completes, is independently verified, is preserved in the run-level report, and the mixed outcome replays exactly?

## Failure experiment design

The test keeps the **same WorkUnit** for both attempts.

1. Attempt 001 runs normally and produces a canonical ResultManifest/candidate bundle.
2. The controlled host removes the local `python:3.12-alpine` tag.
3. Attempt 002 invokes the same exact WorkUnit through the same exact node SHA.
4. Node image-resolution policy fails closed before ResultManifest creation.
5. The actual CLI failure is recorded with exit code plus stdout/stderr SHA-256 values.
6. Only **after observing the failure** is the replay configuration created.
7. Existing `fixture-failure` is used only as a replay representation of that already-observed external worker failure; no synthetic failure is substituted before the observation.
8. The successful peer is consumed through `result-bundle` and EvaluatorPlan.
9. The existing Run Evidence Report must preserve one supported attempt and one `worker_error`, select nobody, and replay exactly.

This avoids inventing a new failure protocol before evidence shows one is needed.

## Authority boundary

- PR #91 remains draft pending separate human/reviewer inspection;
- direct node execution inside coordinator core is still deferred until that gate;
- worker execution in these experiments remains outside coordinator core;
- metadata-only verifier executes no candidate code;
- all report/merge/selection authority remains external;
- no assistant self-merge is performed.

## Tracker convergence

Issues #4, #5, and #16 were updated so the project now distinguishes:

- experimentally proven real precollected-bundle orchestration/report/replay;
- remaining real failure isolation;
- later direct node adapter after human review;
- benchmark cohort only after the current stacked changes are reviewed/integrated.
