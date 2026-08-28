# Project Turn: Execution Targets, Goals, and Tasks

Date: 2026-08-28

## User direction

Continue working directly in the public IDKMesh repository, with emphasis on repository targets, goals, and claimable tasks.

## Initial repository finding

The repository was re-inspected rather than using an earlier planning snapshot.

The broad goals remain coherent, but implementation is moving quickly enough that trackers can become stale within one project turn. The useful planning unit is therefore not a static roadmap paragraph but a continuously reconciled dependency graph backed by observable evidence.

The durable North Star remains:

> **Verified useful work per unit of human attention and compute.**

The product critical path was normalized to:

```text
protected integration boundary
 -> canonical bounded real worker
 -> independent verifier-owned evidence
 -> multi-attempt orchestration
 -> Evidence Report + replay
 -> Verified Swarm Runner v0.1
 -> real-task flagship experiment
 -> evidence-driven scaling
```

Community growth, repository homeostasis/IDKGraph, zero-spend compute, and synthetic research remain parallel capacity-gated tracks.

---

# Planning artifacts created/refreshed

On branch `planning/execution-target-graph-v0` / PR #66:

- `docs/planning/EXECUTION_TARGET_GRAPH.md` — T0–T6 dependency graph, target status, NOW/NEXT/PARALLEL queues, convergence rules, and observable evidence gates;
- `docs/planning/README.md` — distinguishes durable goals, roadmap, current priorities, execution graph, GitHub Issues, and future IDKGraph views;
- this conversation record.

The graph was refreshed again later in the same turn after verifier/orchestrator work landed concurrently.

---

# Canonical tracker maintenance

## Issue #5 — verifier

Originally rewritten from a generic verifier/benchmark request into an executable-verifier task because the canonical VerificationResult contract had already landed.

During the turn, **PR #72 merged** as the canonical deterministic executable verifier MVP (`experiments/local_verifier.py`). The issue was therefore updated again and is now:

**`P0: Extend independent verifier to real repository candidates + benchmark cohort`**

Current #5 next work:

1. verify an actual bounded repository candidate from #34/#37;
2. bind to exact Work Unit + ResultManifest;
3. recompute artifact/log digests;
4. parse patch paths and enforce `allowed_paths` / `forbidden_paths`;
5. run at least one verifier-owned acceptance condition the worker cannot modify;
6. emit canonical VerificationResult;
7. then build a small 5–10 task replayable benchmark cohort.

## Issue #4 — orchestrator

Updated twice as dependencies moved.

With PR #72 landed, #4 is no longer completely blocked by Docker worker acceptance. It now has:

- **Phase A0:** deterministic two-attempt control kernel using fixture worker adapters + canonical verifier;
- **Phase A1:** canonical node adapter after #34/#37;
- **Phase B:** 3–5 attempts only after the two-attempt path is reliable.

## Issue #16 — Verified Swarm Runner v0.1

Refreshed to distinguish completed foundations from remaining product gates.

Completed foundations now include:

- Work Unit / ResultManifest contracts;
- IDKIP process;
- VerificationResult contract;
- cross-object provenance binding;
- verification backpressure baseline;
- deterministic executable verifier MVP (#72).

Remaining hard path:

```text
#34/#37 real worker
+ #5 real repository candidate verifier
+ #78 two-attempt kernel -> real node adapter
+ Evidence Report/replay UX
= v0.1
```

---

# Verifier convergence

## PR #72 became canonical

While an executable verifier was being implemented on another branch, PR #72 landed first and provided the stronger canonical Phase A boundary:

- verifier-owned policy outside candidate control;
- digest verification;
- candidate scope checks;
- path/symlink/size protections;
- known-good candidate accepted;
- self-consistent incorrect candidate with an honest artifact hash independently rejected;
- canonical VerificationResult + provenance binding;
- zero-cost/no-network/no-candidate-code execution path.

## PR #75 deliberately closed as superseded

A concurrent `experiments/independent_verifier.py` implementation was developed and its Phase 0 verifier tests passed. A cross-workflow CI issue was also diagnosed: randomness-lab runs root tests without Phase 0 dependencies, so the new verifier test needed to skip outside the Phase 0 dependency environment.

However, after PR #72 merged, keeping the second verifier executable would violate **integrate before reinventing**.

PR #75 was closed without merge.

One useful idea is preserved as reference: independently recomputing deterministic Phase 0 run outputs may become a check adapter/fixture inside the canonical verifier if it adds evidence value.

## PR #61 deliberately closed as superseded architecture

Older PR #61 contained a second `verifier/deterministic.py` package. It was also closed rather than merged after #72 became canonical.

Unique mechanisms preserved for extraction into the canonical verifier:

- unified-diff target path parsing;
- `allowed_paths` / `forbidden_paths` matching;
- artifact/log digest recomputation;
- fail-closed unsupported-validator handling;
- patch-scope negative fixtures.

These are directly relevant to #5 Phase B1 and the #34/#37 `changes.patch` bundle.

---

# Canonical worker gate

PR #34 was rechecked.

Its prior head had green Node CI + Phase 0 contract validation, but `main` continued moving. A PR comment records the safe integration order:

1. synchronize #34 with current `main`;
2. rerun current Node + contract CI;
3. run controlled Docker acceptance #37 on that exact head SHA;
4. attach positive + negative path-policy runtime evidence;
5. obtain independent sandbox/path-policy review;
6. integrate as the canonical real-worker boundary.

The assistant environment does not provide the controlled Docker host required by #37, so runtime acceptance was not fabricated or claimed.

---

# Two-attempt orchestration

An exact Phase A0 implementation appeared concurrently on branch `feature/two-attempt-orchestrator` / PR #78, so no duplicate orchestrator branch was created.

PR #78 provides:

- replayable two-attempt configuration;
- fixture-result and fixture-failure adapters;
- separate attempt records;
- canonical ResultManifest collection;
- routing through the canonical local verifier;
- known-good verifier support and self-consistent wrong-candidate rejection;
- worker failure isolation;
- deterministic semantic run record;
- no automatic candidate selection or merge.

## PR #78 audit findings and patch

The branch initially had two control-plane inconsistencies:

1. `run --output` accepted any repository-relative path even while the run record claimed `canonical_state_write=false`;
2. a verifier error discarded an already-loaded ResultManifest from the run record.

The existing branch was patched rather than replaced:

- CLI output is now restricted to the `results/` subtree and the self-test explicitly rejects `README.md` as an output target;
- verifier errors retain collected ResultManifest identity/attempt/worker/digest evidence;
- verifier error handling was narrowed so arbitrary programming defects are not silently normalized into expected attempt failures;
- ResultManifest `attempt` is preserved in the run record.

Phase 0 CI passed on patched commit `49d13071dd13b0074b7289888a5081373b232e48`.

PR #78 remains open for independent integration review; no self-merge was performed.

---

# New safety finding

The same output-boundary pattern exists in the merged canonical `experiments/local_verifier.py`: its CLI resolves `--output` inside the repository but does not currently restrict writes to `results/`, despite the component being described as read-only/evidence-only.

A follow-up branch `fix/local-verifier-output-boundary` was created to address this before expanding the verifier to patch-bundle evaluation.

This safety fix is higher priority than adding more verifier features because claimed authority should match executable authority.

---

# Current target state at end of this record

```text
T0  #35 GitHub protection                    -> admin/settings gate
T1  #34 + #37 real worker                    -> physical runtime bottleneck
T2a PR #72 deterministic verifier             -> DONE FOUNDATION
T2b #5 real patch/bundle verification         -> NEXT
T3a PR #78 two-attempt fixture kernel         -> GREEN, IN REVIEW
T3b real node adapter                         -> waits on T1
T4  #16 Evidence Report/replay local product  -> partially unblocked
T5  #2/#30 real-task experiment               -> waits on T4
```

## Immediate priority order

1. enforce/fix safety invariants before feature expansion;
2. independently review/integrate PR #78;
3. protect `main` (#35) when repository-admin settings access is available;
4. synchronize PR #34 and complete #37 on a controlled Docker host;
5. extract patch/digest/path-policy checks into the canonical verifier (#5 B1);
6. connect the real node adapter to the two-attempt orchestrator;
7. build minimal Evidence Report/replay UX;
8. only then run the real-task diversity/verification experiment.

## Deliberate non-actions

- no autonomous merge;
- no self-approval of PR #78;
- no second canonical verifier;
- no second orchestrator branch after concurrent work was discovered;
- no large new issue cohort;
- no broad repository restructure in the product critical path;
- no claim that synthetic/replay studies prove real coding-swarm improvement.

## Project-memory rule

This turn is stored publicly in the repository under the standing project rule. The project history includes both implemented work and deliberate non-merges/closures so future contributors can understand why the canonical path was chosen.
