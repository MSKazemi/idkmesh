# PR Backlog Convergence and Real-Node Evidence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner request

> Continue. We also have many pull requests.

## Interpretation

The repository had reached a form of integration backpressure: candidate work, research branches, planning branches, controller experiments, and evidence paths were being generated faster than the project could integrate or reject them.

The appropriate response was therefore **convergence before expansion**:

1. inventory the live PR queue;
2. merge bounded, current, green, canonical changes;
3. close stale/superseded/deferred branches with explicit successor paths;
4. preserve useful ideas as public provenance rather than keeping every branch live;
5. prioritize the real worker -> independent verifier evidence path;
6. avoid creating another feature PR during cleanup;
7. keep the final independent human-review boundary intact.

The first quick count undercounted the backlog; a full refresh showed **24 open PRs**. The correction was made immediately and the full queue became the convergence target.

## Convergence actions

### Merged during this pass

- **#88 — non-selecting Evidence Report/replay**: integrated the replayable evidence-report layer without selection or merge authority.
- **#106 — clean ACE cohort observer**: replaced stale #40 with the current trusted cohort/exposure observer.
- **#104 — ACE live open-work carrying capacity**: replaced irreversible cumulative historical review-load pressure with recoverable live open-work pressure while preserving fail-closed actuation gates.
- **#99 — current execution target graph + repository improvement loop**: landed one current planning surface and absorbed the durable convergence-before-expansion contract from #53.
- **#112 — fail-closed ACE Phase-B activation gate**: landed an offline deterministic guard that remains BLOCKED unless protection, real independently verified descendant evidence, capacity, write-budget, and safety conditions all pass. It adds no GitHub mutation or autonomous merge authority.
- **#113 — real node -> independent verifier E2E**: landed the exact-SHA bridge from the accepted canonical node candidate to the current hardened EvaluatorPlan v0.2 / deterministic unified-diff verifier.

Several other canonical pieces also landed concurrently from other repository work while the convergence pass was running, including the clean evaluator/output-authority and security-hardening path (#103, #107, #111) and the ACE shadow/controller foundation (#68). The queue was refreshed repeatedly rather than acting on stale snapshots.

### Closed as stale, superseded, or deliberately deferred

- **#59** old scheduling implementation — superseded by the landed R2 scheduling/churn/scale program.
- **#56** large ACO/HSR simulator stack — canonical stigmergy path is now the smaller R4 `randomness_lab` implementation; unique homeostatic ideas remain candidates for focused policy variants.
- **#53** separate repository-improvement planning branch — its durable operating contract was absorbed into #99.
- **#40** old ACE cohort observer — superseded by merged #106.
- **#55** mixed memory-audit + criticality draft — criticality remains a focused research question rather than a mixed-scope live branch.
- **#36** stale Repository Homeostasis draft — bounded repository-observatory/migration work remains under the current structural issues instead of a second control plane.
- **#63** interoperability/A2A/MCP draft — deferred until the local real worker/evidence loop is stable.
- **#89** old Phase-B activation branch — replaced by the refreshed, fail-closed current-state guard #112.
- **#44** early ACE toy population simulator — preserved as historical mechanism evidence; current ACE capacity/controller paths supersede it.
- **#43** old GitHub Reflex Observatory draft — preserved as public observability/self-evolution provenance but removed from active review capacity while the real product evidence path is prioritized.
- **#108** evaluator-owned runtime evidence branch — used to discover/falsify runtime assumptions, then closed rather than becoming a permanent parallel subsystem after its useful evidence was incorporated into the canonical path.

## Real worker evidence: failure first, then pass

The most important outcome of convergence was not simply fewer pull requests. It was that the real runtime gate found a genuine defect that static/schema CI had missed.

### First frozen runtime attempt

An older PR #91 candidate:

`d638a2f78e4a89353b98e91052233e365f56f90a`

reached real Docker execution and correctly resolved the immutable `python:3.12-alpine` image identity, but the positive smoke task failed with a Python `SyntaxError`.

Root cause: JSON decoding turned newline escapes inside the `python -c` smoke command into literal newlines inside a single-quoted Python string.

The gate was **not weakened** and the failed result was preserved as useful evidence.

### Worker correction

The canonical smoke task was changed to an escape-free construction using `chr(10)`. A regression test was then added that parses the actual canonical WorkUnit and compiles the decoded `python -c` command before runtime acceptance.

This produced the current exact worker candidate:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Exact-head prerequisites passed:

- Node CI `33185901079` — success;
- Phase 0 `33185901058` — success.

### Controlled Docker acceptance

The full exact-head controlled-runtime matrix then passed for `520ad2c9...`.

Positive evidence included:

- schema-valid succeeded ResultManifest;
- only `README.md` changed;
- zero untracked/path/unpackaged-artifact/protected-metadata/output/runtime/aggregate policy violations;
- non-truncated candidate patch;
- independently matching candidate/stdout/stderr digests;
- immutable image ID:
  `sha256:1148adc3b50891ee01e6add44be22d277dedeb8dcac2f7cc8b700dd710c75c4d`;
- matching repository digest:
  `python@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31`;
- network none, read-only root, dropped capabilities, no-new-privileges, PID/CPU/RAM bounds, read-only Git metadata, no Docker socket, immutable image execution;
- worker acceptance authority remained false.

Required negative cases all failed closed:

1. forbidden/out-of-scope tracked path;
2. ignored untracked artifact;
3. task-visible Git-pointer tampering;
4. oversized/truncated candidate patch;
5. absent local image;
6. locally retagged image without matching repository digest.

Issue #37 was completed for the exact corrected worker head.

## Evaluator evidence: another useful failure

The first attempt to connect the real accepted worker to the canonical independent verifier exposed a second integration defect, this time in the evaluator-owned harness rather than the worker.

The stale E2E plan failed schema validation because current EvaluatorPlan v0.2 requires:

- `backend.required_log_types`;
- deterministic patch-verifier adapter version `0.1.1`.

The worker was not modified. The canonical evaluator had already been hardened in #111 to require explicit `stdout`/`stderr` evidence and conservative unified-diff structure.

A clean replacement E2E in #113 fixed plan drift by deriving from the current canonical evaluator plan fixture instead of hardcoding evolving evaluator-version details.

## Real node -> independent verifier E2E

PR #113 exact-head workflow run `33186566651` passed.

Observed evidence:

- accepted worker candidate: `520ad2c9aa5825476de4957da4702d6823f4edb3`;
- candidate code executed by verifier: **false**;
- canonical patch negative matrix: **passed**;
- WorkUnit: `node/canonical-smoke`, version 2;
- WorkUnit digest:
  `sha256:40993e892a5b83962364686809f7ec6e94ef379e10aaea9492a0526ed7695e2e`;
- ResultManifest digest:
  `sha256:b45426954a9355629d4746d24ba3b4680962ec96bf7575fd056478a033cfa502`;
- candidate patch digest:
  `sha256:8383a0dd5217e9472e5f55eb658248620e539394cb96012dc61c24a3cc33f6cf`;
- EvaluatorPlan digest:
  `sha256:893e59d8d1f8be5bb30e664561eca7bc31d9eb8d3c743225f7e63662b0912c1b`;
- required evaluator log types: `stdout`, `stderr`;
- verifier adapter version: `0.1.1`;
- verifier independent from worker: **true**;
- `result-manifest-schema`: passed;
- `independent-review`: passed;
- VerificationResult status: **passed**;
- VerificationResult digest:
  `sha256:f52686e8e715ecc19ca9788c221d268b4772846aa4a756c18a43ebbf952711cd`;
- recommendation: `accept_candidate` as decision support only;
- `human_integration_decision_required`: **true**.

Issue #5 Phase B1 is therefore complete. The next verification milestone is a small 5–10 task real replayable cohort before any larger benchmark expansion.

## Final PR state

At the end of this convergence turn, the active pull-request queue is:

- **#91 only** — canonical local `idkmesh-node` worker candidate.

This is intentional. #91 remains draft because the project explicitly requires a **separate human/reviewer inspection** of the exact-head CI and controlled-runtime evidence before integration. It has been labeled `help wanted` to make that community review need visible.

The low PR count is not permission to weaken the final independence boundary.

## Durable operating lesson

IDKMesh should treat PR backlog like verification debt:

```text
proposal generation > review/integration capacity
  -> open-work pressure rises
  -> context and merge drift grow
  -> duplicate mechanisms accumulate
  -> integration quality falls
```

The corrective controller is:

```text
high open-work pressure
 -> convergence mode
 -> stop optional new branches
 -> merge current bounded evidence
 -> close/defer superseded work
 -> preserve provenance
 -> repair real failures
 -> re-measure the queue
```

A failed test, runtime gate, or verifier run is not wasted work. If it reveals a real incompatibility and produces a regression guard, it is high-value project evidence.

## Community impact

Reducing the PR queue from **24 to 1** makes the repository easier for a newcomer or independent reviewer to understand. The remaining open contribution surface is also unusually concrete: review exact worker head `520ad2c9...` and its already-recorded CI/runtime/E2E evidence without needing to reason about two dozen competing branches.

The next product work after that review should remain evidence-first: integrate the canonical worker, run real multi-attempt orchestration through the landed verifier and non-selecting Evidence Report, then build the first small real benchmark cohort.
