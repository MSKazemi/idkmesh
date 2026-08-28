# Conversation record: real node runtime falsification and independent verification

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

The project owner repeatedly instructed the assistant to continue collaborating on and improving IDKMesh, with substantive project work preserved publicly in the repository.

This turn therefore continued the executable critical path rather than adding another architecture catalog.

## Starting point

The repository already contained:

- WorkUnit v0.2;
- worker ResultManifest v0.1;
- VerificationResult v0.1;
- EvaluatorPlan / Evaluator Sovereignty;
- a deterministic metadata-only patch verifier;
- a deterministic two-attempt orchestration kernel;
- a non-selecting run Evidence Report/replay layer.

The major missing evidence was a real canonical-node execution and independent verification of its actual patch/log bundle.

## Runtime acceptance: failure was evidence

The first frozen node candidate under test was:

`d638a2f78e4a89353b98e91052233e365f56f90a`

It had green Node CI and Phase 0 schema checks, but the first real Docker acceptance run falsified it.

The allowlisted image resolved correctly and the worker reached the task container, but the canonical smoke command failed with a Python `SyntaxError`. JSON decoding had converted newline escapes into literal newline characters inside a single-quoted `python -c` source string.

This was a useful negative result: static schema/unit validation had not proved the actual smoke command executable.

The repair was deliberately narrow:

1. the fixture switched to an escape-free `chr(10)` construction;
2. regression coverage compiled the actual decoded `python -c` payload;
3. runtime evidence was rerun from scratch instead of inherited across a changed candidate tree.

## Accepted exact node head

The current frozen node candidate is:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Exact-head prerequisite checks:

- Node CI `33185901079` — success;
- Phase 0 `33185901058` — success.

The independent Docker acceptance matrix subsequently passed for this exact head. Positive execution produced only the intended `README.md` change and retained immutable container/source provenance. Negative cases failed closed for:

- forbidden/out-of-scope tracked change;
- ignored untracked artifact;
- task-visible Git metadata pointer tampering;
- oversized/truncated candidate patch;
- absent local image;
- locally retagged image without matching immutable repository digest.

The worker remained unable to approve or merge its own result.

## First real node -> verifier proof

A clean follow-up branch/PR was created from then-current `main` rather than extending the closed runtime-acceptance PR.

PR **#113** runs:

```text
exact node 520ad2c...
 -> real ResultManifest + changes.patch + stdout/stderr
 -> evaluator-owned EvaluatorPlan v0.2
 -> metadata-only unified-diff verifier
 -> canonical VerificationResult v0.1
 -> human decision remains external
```

The worker checkout and evaluator checkout are separate. Checkout credentials are not persisted, repository permissions are read-only, no repository secrets are passed to candidate code, and the EvaluatorPlan is constructed only after candidate generation.

The harness derives evolving evaluator details from the current canonical EvaluatorPlan fixture rather than hardcoding verifier-version fields.

## Real E2E result

PR #113 workflow run `33186566651`, job `98900978240`, passed.

Exact evidence:

### WorkUnit

- id: `node/canonical-smoke`
- version: `2`
- digest: `sha256:40993e892a5b83962364686809f7ec6e94ef379e10aaea9492a0526ed7695e2e`
- source revision: `b1397a9be91da6570e8ae370de4fa9f4bc44df5c`

### Worker

- id: `local/idkmesh-node`
- ResultManifest id: `node/canonical-smoke/attempt-1-5bead4f97b`
- ResultManifest digest: `sha256:b45426954a9355629d4746d24ba3b4680962ec96bf7575fd056478a033cfa502`
- candidate patch digest: `sha256:8383a0dd5217e9472e5f55eb658248620e539394cb96012dc61c24a3cc33f6cf`
- status: `succeeded`

### Evaluator

- plan id: `verification/real-node-520ad2c-plan`
- plan digest: `sha256:893e59d8d1f8be5bb30e664561eca7bc31d9eb8d3c743225f7e63662b0912c1b`
- backend: `unified_diff`
- verifier adapter version: `0.1.1`
- required logs: `stdout`, `stderr`

### VerificationResult

- id: `node/canonical-smoke/attempt-1-5bead4f97b/patch-verification`
- digest: `sha256:f52686e8e715ecc19ca9788c221d268b4772846aa4a756c18a43ebbf952711cd`
- status: `passed`
- recommendation: `accept_candidate`
- `independent_from_worker: true`
- `result-manifest-schema: passed`
- `independent-review: passed`

The canonical patch-verifier negative self-test matrix also passed before the real bundle was evaluated.

The E2E evidence explicitly records:

```text
candidate_code_executed_by_verifier = false
human_integration_decision_required = true
```

## Important authority distinction

`accept_candidate` is verifier decision support. It is **not** repository integration authority.

At no point did the worker, evaluator harness, verifier, or this assistant grant itself automatic merge authority.

PR #91 remains draft until the separately required human/reviewer inspection of its exact-head runtime evidence.

PR #113 remains a reviewable proof/harness change rather than being self-merged by the same proposing assistant.

## Tracker convergence

Issue #5 was updated to mark the substantive real single-bundle verification checks complete.

The remaining run-level evidence item should not fabricate a two-attempt run by duplicating one attempt. The next executable step is instead:

```text
real node adapter
 -> two isolated real attempts
 -> independent VerificationResult per completed candidate
 -> existing non-selecting Evidence Report/replay
 -> external human/governance decision
```

That work belongs to issue #4 / #16.

## Scientific/engineering lesson

The most useful result in this turn was not only the final pass. The first real-Docker failure demonstrated the project principle:

> Schema validity and green unit tests are evidence, but executable reality can still falsify the candidate.

IDKMesh should therefore continue promoting mechanisms through increasingly realistic evidence while preserving failed experiments and preventing generators from certifying themselves.
