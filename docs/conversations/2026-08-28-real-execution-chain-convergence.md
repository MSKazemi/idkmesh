# Project Turn: Real Execution Chain Convergence

Date: 2026-08-28

## User direction

Continue working directly in the IDKMesh repository on targets, goals, and tasks.

## Result of this turn

The repository's execution chain was repeatedly reconciled against current `main` instead of preserving stale tracker assumptions.

The most important outcome is that IDKMesh now has a much narrower real-product bottleneck:

```text
controlled real node runtime
 -> real patch/log bundle
 -> bound independent patch evaluation
 -> two-attempt real orchestration
 -> non-selecting Evidence Report/replay
 -> explicit human integration decision
```

The repository is no longer blocked primarily by missing schemas, verifier concepts, or fixture orchestration.

## Canonical components identified

### Real worker

PR #91 supersedes old #34 and is the canonical WorkUnit v0.2 node candidate.

Frozen #37 acceptance SHA:

`d638a2f78e4a89353b98e91052233e365f56f90a`

Node CI and Phase 0 schema validation are green on the exact frozen head. #37 still requires positive and negative runtime evidence from an explicitly controlled Docker host.

That runtime evidence was not fabricated or substituted with static CI in this turn.

### Independent verification

PR #72 is the canonical executable verifier foundation.

PR #81 is the canonical EvaluatorPlan / Evaluator Sovereignty layer.

A safety audit found that verifier/evaluator CLI output could target arbitrary repository-relative files. The original fix PR #90 became stale after rapid `main` movement, so it was rebuilt as clean PR #103 directly on current `main`.

PR #103 restricts generated verifier/evaluator evidence to ignored root `results/` and rejects canonical tracked paths such as `README.md`. All relevant CI passed and #103 merged.

### Real patch evaluator

A metadata-only unified-diff evaluator was implemented without creating a second verifier package.

The implementation adds EvaluatorPlan v0.2 and a canonical `unified_diff` backend that independently reconstructs:

- patch SHA-256;
- declared stdout/stderr SHA-256 values;
- old/new paths from unified-diff headers;
- WorkUnit allowed/forbidden/write authority;
- verifier-owned required added text;
- exact WorkUnit / ResultManifest / EvaluatorPlan bindings.

It does not apply patches or execute candidate code.

The initial stacked PR #102 was green but was superseded by clean PR #105 on the clean #103 safety base.

PR #105 reproduced green EvaluatorPlan Binding, Phase 0, and Evolution checks and remains the canonical review target for this backend.

### Multi-attempt orchestration

PR #78 is merged and is the canonical deterministic two-attempt control-plane foundation.

It already proves:

- separate attempt histories;
- worker-success candidate independently supported;
- worker-success candidate independently rejected;
- peer worker failure isolation;
- ResultManifest evidence preserved through verifier failure;
- deterministic semantic replay;
- no majority-vote-as-truth;
- no automatic selection or merge.

Issue #4 therefore now focuses on connecting the real PR #91 node through the existing adapter boundary after #37 and real patch verification.

### Evidence Report / replay

PR #88 already provides a green non-selecting Evidence Report/replay layer.

A current-dependency comment was added so its real integration path is explicit:

```text
#91/#37 real attempts
 -> ResultManifests + patch/log bundles
 -> EvaluatorPlan v0.2
 -> canonical patch verification
 -> PR #78 run record
 -> PR #88 Evidence Report
 -> human_decision.status=pending
```

The report must preserve disagreement and evidence rather than select a winner.

## Stale/duplicate paths removed

The turn actively reduced ambiguity:

- old PR #34 references were replaced by canonical PR #91;
- duplicate verifier PR #75 was previously closed as superseded;
- old second-verifier PR #61 was closed while preserving useful path/digest ideas as reference;
- stale safety PR #90 was replaced by clean merged PR #103;
- stale stacked patch-evaluator PR #102 was replaced by clean PR #105;
- drifting planning PR #66 was closed earlier;
- planning PR #99 was found to conflict with newer planning/index changes on `main`, so a smaller current-main execution-graph branch was created instead of overwriting newer canonical planning material.

## Canonical issue updates

Issues #4, #5, and #16 were rewritten to the current real state.

### #4

Now treats PR #78 as completed foundation and focuses on:

- #91/#37 real node acceptance;
- canonical real node adapter;
- real EvaluatorPlan-bound verification per attempt;
- later 3–5 worker bounded fan-out.

### #5

Now focuses on:

- one real #91/#37 patch bundle through the canonical patch evaluator;
- exact WorkUnit / ResultManifest / EvaluatorPlan provenance;
- patch/log digests;
- independent patch path scope;
- verifier-owned semantic expectation;
- then a first 5–10 task benchmark cohort.

### #16

Now identifies the remaining v0.1 gates as:

1. #37 controlled Docker evidence for #91;
2. real node bundle through the canonical patch evaluator;
3. real node adapter behind PR #78;
4. real run through PR #88 Evidence Report/replay;
5. one trivial heterogeneous second real adapter.

## Runtime-bundle handoff

A detailed downstream handoff comment was added to #37.

The positive controlled-runtime bundle should preserve:

- WorkUnit;
- ResultManifest;
- `changes.patch`;
- stdout/stderr;
- exact source/node SHA;
- image identifier/digest;
- runtime command/config needed for replay.

Negative A–E runtime cases should preserve the attempted input and observed failure/log evidence even when no normal candidate patch is produced.

A corresponding integration comment was added to PR #91 so the node implementation does not reopen protocol design after #37.

## Governance status

`main` remains unprotected in GitHub metadata, so #35 remains the highest integration-governance safety gap.

A fresh #35 comment records that urgency after the verifier/EvaluatorPlan/orchestrator layers landed.

No stronger autonomous write/merge authority should be introduced until GitHub itself enforces the intended boundary.

## Current execution order

```text
1. Protect main (#35) when repository-admin settings action is available.
2. Independently review/integrate PR #105.
3. Execute frozen controlled Docker gate #37 for PR #91.
4. Replay the real #37 bundle through the canonical EvaluatorPlan v0.2 patch backend.
5. Connect PR #91 behind PR #78's real worker adapter boundary.
6. Exercise PR #88 over the real two-attempt run.
7. Produce the first complete real replayable v0.1 evidence loop.
8. Add one trivial heterogeneous second real adapter.
9. Build the first 5–10 task benchmark cohort.
10. Only then run the real-task diversity/verification experiment #2/#30 and promote scaling mechanisms from evidence.
```

## Deliberate non-actions

- no self-approval or self-merge;
- no attempt to fake #37 without the required controlled Docker host;
- no second verifier/evaluator/orchestrator/report protocol;
- no new large issue cohort;
- no broad repository restructure in the real product critical path;
- no claim that synthetic or fixture scale proves real-world coding-swarm quality.

This conversation record and the current execution graph are stored publicly under the project's repository-memory rule.
