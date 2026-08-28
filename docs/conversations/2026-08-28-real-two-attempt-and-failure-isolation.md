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

## Real failure-isolation result

PR #124 (`E2E: test real peer failure isolation`) ran the experiment successfully.

Workflow evidence:

- workflow run: `33187647090`;
- job: `98904699777`;
- exact accepted node candidate: `520ad2c9aa5825476de4957da4702d6823f4edb3`;
- immutable source revision: `b1397a9be91da6570e8ae370de4fa9f4bc44df5c`;
- WorkUnit digest: `sha256:40993e892a5b83962364686809f7ec6e94ef379e10aaea9492a0526ed7695e2e`;
- EvaluatorPlan digest: `sha256:0c066392ee33397c1cec125b42ff0b812955f9ef51b01fd42922490ed8c3b244`.

Successful peer:

- ResultManifest id: `node/canonical-smoke/attempt-1-f9795d8d80`;
- ResultManifest digest: `sha256:9437c840359c980a8a9d7531d4fcb21433e14bede25a3d3be3a9aec29c16c9a6`;
- candidate patch digest: `sha256:8383a0dd5217e9472e5f55eb658248620e539394cb96012dc61c24a3cc33f6cf`;
- coordinator state: `verified`;
- independent recommendation: `accept_candidate`.

Failed peer:

- real node exit code: `2`;
- ResultManifest created: `false`;
- observed failure digest: `sha256:8d2e47786207ab9f22539b06dbd98d52a42909936b48e38dd1a26372dd376d4b`;
- failure stderr digest: `sha256:65d3764925cb0fd7df5a1d7db365004f0cdb199b21c74ffa687f263fc960228c`;
- coordinator state: `worker_error`;
- report evidence state: `worker_error`.

Run/report/replay:

- mixed run digest: `sha256:84a0e47cd9e3f7a51fbf13d5ec26b10a68c6c0532c539725d9690b740a73b234`;
- replayed run digest: same exact digest;
- replay match: `true`;
- report digest: `sha256:500af0cbd743a319dd1a5b06e3e35417bed156f5a263f14d01a466a02d4ba8bf`;
- attempts: `2`;
- supported: `1`;
- rejected: `0`;
- control errors: `1`;
- control failure present: `true`;
- verification disagreement: `false`;
- selected attempt: `null`;
- human decision: `pending`;
- integration authority: `external_human_or_governance`.

The evidence explicitly records that the real worker failure was observed **before** replay-config construction. The successful peer still reached independent verification. The failed peer did not acquire an invented ResultManifest or VerificationResult. The report preserved the failure rather than dropping it, and replay reproduced the exact mixed run.

## Authority boundary

- PR #91 remains draft pending separate human/reviewer inspection;
- direct node execution inside coordinator core is still deferred until that gate;
- worker execution in these experiments remains outside coordinator core;
- metadata-only verifier executes no candidate code;
- all report/merge/selection authority remains external;
- no assistant self-merge is performed.

## Tracker convergence

Issues #4, #5, and #16 distinguish:

- experimentally proven real precollected-bundle orchestration/report/replay;
- experimentally proven real peer-failure isolation;
- later direct node adapter after human review;
- benchmark cohort only after the current stacked changes are reviewed/integrated.

The next v0.1 implementation gate is therefore not another failure experiment. It is the separate human review of PR #91, followed by a minimal direct node adapter behind the already-proven worker-adapter boundary if the reviewed candidate remains unchanged.
