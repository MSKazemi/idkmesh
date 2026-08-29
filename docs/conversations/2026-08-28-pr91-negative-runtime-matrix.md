# Project Conversation — PR #91 Negative Runtime Matrix

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

> Continue

Repository context: `https://github.com/MSKazemi/idkmesh`

## Context

By this point the repository had converged substantially:

- ACE safety convergence PR #98 was merged; issue #35 remained an external GitHub-admin protection gate;
- verifier output authority PR #103 was merged;
- run Evidence Report/replay PR #88 was merged;
- unified-diff evaluator PR #107 was merged;
- post-merge evaluator evidence-completeness hardening PR #111 was independently merged after exact-head green CI;
- PR #110 had placed a controlled-host acceptance helper on `main` for frozen node PR #91;
- issue #37 remained the only missing real-Docker acceptance boundary for that exact frozen node candidate.

The frozen node head remains:

`d638a2f78e4a89353b98e91052233e365f56f90a`

This continuation did not move that SHA.

## Why continue the acceptance harness

PR #110 automated the positive controlled-host path but intentionally left the five issue #37 negative runtime cases manual.

That preserved safety, but it also left a high-friction community task: a contributor would need to construct temporary WorkUnit variants correctly, distinguish expected worker failure from harness failure, retain evidence, and avoid leaving test state behind.

The next useful repository-internal improvement was therefore:

> make the negative runtime matrix reproducible without reducing it to mocked CI or changing the candidate under test.

## New `run-negatives` command

`scripts/pr91_acceptance.py` now adds a controlled-host command:

```text
run-negatives
```

The command:

- runs only against a checkout whose HEAD exactly equals the frozen PR #91 SHA;
- requires the same Docker/image preflight as the positive path;
- creates temporary WorkUnit variants under `/tmp` rather than committing destructive fixtures;
- executes the actual PR #91 node CLI and Docker boundary;
- retains A–D failed ResultManifest bundles for independent inspection;
- records command return class, evidence summaries, and per-case errors;
- emits one aggregate JSON report;
- grants no merge or integration authority.

## Negative A — path-policy failure

A temporary WorkUnit asks the real node to produce a tracked change outside the canonical allowed path.

The harness requires the worker to fail closed while still retaining the changed path and path-policy evidence.

The purpose is to prove that a task cannot turn an out-of-scope tracked change into a successful candidate merely because the task process itself exits normally.

## Negative B — ignored untracked output

The source revision ignores the `results/` subtree.

A temporary WorkUnit allows that subtree for path/write scope, then emits an ignored untracked file. This isolates the artifact-completeness rule from ordinary path-policy rejection.

The harness requires:

- the ignored file to remain observable;
- nonzero untracked-file accounting;
- unpackaged-artifact evidence;
- worker failure.

This is the runtime counterpart to the node's fail-closed rule that `.gitignore` cannot make candidate output disappear from evidence.

## Negative C — candidate-visible Git control state

A temporary task attempts to alter the task-visible Git pointer while also making a normal allowed tracked change.

The expected invariant is not that the task-visible pointer is magically immutable. The invariant is that **the candidate cannot control the host-owned Git metadata used to measure the candidate**.

The harness therefore requires:

- protected-metadata violation evidence;
- the allowed tracked change to remain visible in worker changed-path evidence;
- the stored patch to remain independently parseable as containing that tracked change;
- worker failure.

This tests the separation introduced by PR #91 between task-writable workspace state and host-owned read-only Git metadata.

## Negative D — incomplete bounded candidate artifact

A temporary WorkUnit uses a deliberately small candidate-patch byte bound and creates a larger otherwise-allowed tracked change.

The harness requires:

- patch truncation to be observable;
- output-policy failure;
- worker failure;
- the stored diagnostic bytes to remain within the configured bound;
- the ResultManifest artifact digest to continue matching those stored diagnostic bytes.

The point is that an incomplete candidate artifact may be retained diagnostically but cannot become a successful candidate.

## Negative E — immutable container identity

The node allows two small image tags in this MVP. The acceptance host is instructed to preload only the positive `python:3.12-alpine` candidate image.

For safe automation, the harness refuses to replace any pre-existing alternate allowlisted Docker tag.

On a clean controlled host it then checks two failure modes:

1. an allowed-but-absent alternate image remains absent after the node refuses it, demonstrating no implicit pull;
2. a temporary local tag pointing at the already-inspected positive image still lacks a matching immutable repository digest for the alternate repository identity, so both the harness parser and frozen node must reject it.

The temporary tag is removed in a guaranteed cleanup path and absence is rechecked. If the alternate tag existed before the run, the harness refuses the test rather than mutating that host state.

## Evidence semantics

A–D are expected to return a normal worker-attempt failure class with a retained ResultManifest/evidence bundle.

E is expected to be refused before normal candidate execution because immutable image evidence is missing or mismatched.

The aggregate report records:

```text
exact frozen SHA
host / Docker / image preflight
case A..E command observations
case A..D retained evidence validation
case E image-identity observations + cleanup state
per-case passed/errors
aggregate passed/failed_cases
automatic_merge = false
integration_decision = null
```

A report is evidence for issue #37 human review. It is not itself authority to close the issue or merge PR #91.

## CI boundary

GitHub-hosted CI still does **not** run Docker for this acceptance gate.

The existing harness check continues to compile the script and run its Docker-free deterministic self-test. The self-test now also checks the negative WorkUnit mutations and repository-digest mismatch logic without pretending those synthetic checks are runtime acceptance.

## Critical path after this change

```text
current main acceptance harness
 -> separate exact PR #91 checkout
 -> positive controlled Docker run
 -> A-E controlled Docker negative matrix
 -> issue #37 human evidence review
 -> real bundle replay through patch verifier v0.1.1
 -> VerificationResult + Evidence Report/replay
 -> human integration decision
 -> first 5-10 benchmark tasks
```

No self-merge or autonomous integration is introduced by this continuation.
