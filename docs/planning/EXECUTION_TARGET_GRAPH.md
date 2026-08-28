# IDKMesh Execution Target Graph

**Snapshot:** 2026-08-28  
**Purpose:** keep the repository focused on the shortest evidence-producing path from its broad goals to a working, independently verified local product.

This is a planning snapshot, not a replacement for `GOALS.md`, `ROADMAP.md`, GitHub Issues, or future machine-generated IDKGraph views.

## North Star

> **Verified useful work per unit of human attention and compute.**

The immediate engineering path is:

```text
bounded goal/task
  -> canonical Work Unit
  -> isolated worker attempt(s)
  -> canonical ResultManifest(s)
  -> independent verifier-owned checks
  -> canonical VerificationResult(s)
  -> combined evidence / human decision
  -> replayable experiment record
```

Raw activity, agent count, issue count, stars, or worker self-confidence are not progress substitutes.

## Hard constraints

1. No autonomous merge into canonical `main` for v0.1.
2. One autonomous actor must not propose, approve, and merge its own protected change.
3. Worker success is not acceptance.
4. Verifier recommendation is decision support, not merge authority.
5. Generation must not outrun verification/reviewer capacity.
6. Project-paid compute remains disabled under the current zero-project-spend policy.
7. Scale is earned by evidence: local -> small mesh -> larger mesh.
8. Community growth is measured by verified useful descendants, not raw activity.
9. Repository restructuring is bounded, reversible, and evidence-backed.
10. Integrate before reinventing: one canonical contract/verifier/orchestrator path unless evidence requires a competing experiment.

---

# Current critical path

```text
T0 GitHub integration protection (#35)

T1 real bounded worker (#34 + #37) -----------------------+
                                                           |
T2a deterministic independent verifier [DONE: PR #72]     |
        |                                                  |
        +-> T2b real repository-patch verification (#5) --+
                                                           |
T3a two-attempt control kernel [PR #78] ------------------+
        |                                                  |
        +-> T3b canonical node adapter after T1 -----------+
                                                           |
                                                           v
T4 Verified Swarm Runner v0.1 (#16)
   -> Evidence Report + replay + simple CLI
                                                           |
                                                           v
T5 real-task diversity/verification experiment (#2/#30)
                                                           |
                                                           v
T6 evidence-driven scaling decisions
```

T0 is a safety gate for stronger autonomous integration. It does not prevent local read-only/isolated experimentation, but stronger autonomous write/merge authority remains blocked until GitHub itself enforces the boundary.

---

# Target status

| Target | Status | Current evidence | Next gate |
| --- | --- | --- | --- |
| **T0 Protected integration** | BLOCKED/ADMIN | #35 + repository-side guard work | Configure and verify GitHub ruleset/branch protection |
| **T1 Canonical real worker** | IN PROGRESS | PR #34 has canonical node implementation and prior green CI | Sync with current `main`, rerun CI, execute controlled Docker gate #37 |
| **T2a Deterministic verifier MVP** | **DONE FOUNDATION** | PR #72 merged as `experiments/local_verifier.py` | Do not create a second verifier executable |
| **T2b Repository candidate verifier** | NEXT | #5 Phase B1; useful patch-scope mechanisms preserved from closed PR #61 | Verify real `changes.patch`/bundle from #34/#37 with verifier-owned scope/acceptance |
| **T3a Two-attempt orchestration kernel** | IN REVIEW | PR #78; Phase 0 CI green after control-plane safety patch | Independent integration review; no self-merge |
| **T3b Canonical node adapter** | BLOCKED BY T1 | adapter boundary exists conceptually in #4/PR #78 | Connect #34 after #37 |
| **T4 v0.1 product loop** | PARTIALLY UNBLOCKED | contracts, verifier, replay research, orchestration kernel emerging | real worker + real verifier + Evidence Report/replay CLI |
| **T5 Real-task flagship experiment** | WAITING ON T4 | synthetic/replay research exists | run real comparable candidate sets through canonical loop |
| **T6 Larger-scale mesh** | EVIDENCE-EARNED | research only | promote only mechanisms supported by T5 evidence |

---

# What changed in this iteration

## Verification converged

PR #72 merged the canonical deterministic executable verifier MVP:

- verifier-owned policy outside candidate control;
- candidate digest and file-scope checks;
- independently rejected self-consistent wrong candidate;
- canonical VerificationResult output and provenance binding;
- zero-cost/no-network/no-candidate-code execution boundary.

A concurrent second implementation (PR #75) was deliberately **closed as superseded** rather than merged. Its deterministic smoke-reproduction idea remains available as a future check adapter/fixture if useful.

An older candidate-bundle verifier (PR #61) was also **closed as superseded architecture**. Its unique useful mechanisms—unified-diff target parsing, allowed/forbidden path checks, artifact/log digest recomputation, and fail-closed unsupported-validator handling—are retained as reference for T2b and should be integrated into the canonical verifier rather than revive a second package.

## Orchestration became partially unblocked

With PR #72 landed, #4 can test coordination semantics before Docker worker acceptance.

PR #78 now provides a deterministic two-attempt fixture control kernel that demonstrates:

- separate attempt records;
- independent verification per candidate;
- worker-success candidate accepted by verifier;
- worker-success but independently wrong candidate rejected by verifier;
- peer worker failure isolation;
- deterministic semantic replay;
- no automatic candidate selection/merge.

A control-plane audit added two important fixes on PR #78:

1. CLI output is restricted to `results/` so the orchestrator cannot truthfully claim `canonical_state_write=false` while accepting `README.md` as an output path.
2. A verifier error no longer erases an already-collected ResultManifest from the run record.

Phase 0 CI is green on the patched head. Integration still requires independent review.

---

# NOW queue

These are the highest-leverage current tasks.

## 1. Protect `main` in GitHub settings — #35

**Why:** repository files/instructions are not an enforcement boundary.

Done means GitHub publicly reports the intended protection/ruleset state, required checks, force-push/deletion behavior, and review constraints.

This is admin/settings work and cannot be replaced by another Markdown file or agent promise.

## 2. Independently review/integrate PR #78

**Why:** this establishes the first replayable multi-attempt control plane without waiting for real Docker workers.

Review should focus on:

- output/write authority;
- preservation of ResultManifest evidence on worker/verifier errors;
- deterministic replay semantics;
- adapter isolation assumptions;
- absence of automatic selection/merge;
- whether exceptions are classified without hiding programming defects.

Do not close #4 after this PR; it completes Phase A0, not the real worker path.

## 3. Synchronize PR #34 and execute #37

**Why:** T1 is the remaining physical execution bottleneck.

Required order:

1. synchronize PR #34 with current `main` without overwriting concurrent work;
2. rerun current contract/node CI;
3. run #37 on a controlled Docker host against the exact head SHA;
4. attach positive and negative path-policy runtime evidence;
5. obtain independent sandbox/path-policy review;
6. integrate only after those gates.

## 4. Extend the canonical verifier to the node patch bundle — #5 Phase B1

**Why:** v0.1 needs independent evidence about a real repository candidate, not only `answer=42` fixtures.

First bounded target: the canonical node smoke Work Unit, whose candidate patch must touch only `README.md` and add the intended harmless marker.

Required verifier-owned checks should include:

- exact Work Unit/ResultManifest binding;
- observed artifact/log digest checks;
- safe parsing of unified-diff target paths;
- `allowed_paths` / `forbidden_paths` enforcement;
- at least one verifier-owned acceptance condition the worker cannot modify;
- a scope-valid but semantically wrong negative candidate;
- fail-closed treatment of required validators not implemented by the verifier;
- canonical VerificationResult output.

**Convergence rule:** extend `experiments/local_verifier.py` or a clearly subordinate check/plugin boundary; do not add another canonical verifier executable/package.

Before expansion, also correct the canonical verifier CLI output boundary so a component described as read-only cannot overwrite arbitrary repository files through `--output`.

## 5. Connect PR #78 adapter boundary to the canonical node

Only after T1/#37 succeeds.

The orchestrator core should remain unchanged; the new adapter should provide the same collected-candidate boundary and retain per-attempt provenance/errors.

---

# NEXT queue

## Minimal Evidence Report / replay UX — #16

Take the run record and per-attempt ResultManifest/VerificationResult evidence and present:

- worker status;
- verifier status/recommendation;
- required check outcomes/findings;
- source/attempt/verifier provenance;
- resource signals;
- disagreements/errors;
- explicit `human decision: pending/accept/reject/refine` state.

No majority-vote shortcut and no auto-merge.

## Small benchmark cohort — #5

After one real node candidate is replayable, build 5–10 tasks before the original 20–50 ambition.

Each needs an immutable source snapshot, bounded Work Unit, worker result, verifier-owned acceptance method, replay instructions, and meaningful negative evidence where appropriate.

## Real-task R1 — #2/#30

Use comparable real candidate sets under fixed resource/review budgets to test replication vs structural diversity + independent verification.

Synthetic and replay tools are mechanism research, not proof that coding swarms improve real work.

---

# Parallel capacity-gated tracks

## Community reproduction — #9/#10/#24–#28

Continue only as reviewer capacity permits.

Priority:

1. parent -> seed -> verified-descendant evidence;
2. ACE threat model;
3. real newcomer-path observations;
4. measure verified descendants per reviewer/maintainer minute;
5. expand cohorts only when evidence/capacity supports it.

## Repository homeostasis / IDKGraph — #20/#36/#38

- refresh stale RHE work against current `main`;
- keep proposal-only behavior;
- rerun structural baseline;
- perform only bounded Migration 001 first;
- preserve zero broken links;
- measure structural benefit vs migration/review cost.

Do not let repository restructuring consume the product critical path.

## Zero-spend compute

Local capability discovery and provider-neutral zero-cost offers can continue, but distributed compute must not block the local verified loop.

---

# Task-selection rule

Choose the next task in this order:

```text
1. repair a safety/verification invariant;
2. remove a blocker on T1–T4;
3. converge duplicate implementations into one canonical path;
4. produce real replayable evidence for T5;
5. reduce reviewer/community friction with measured benefit;
6. reduce repository structural pressure with measured benefit;
7. only then add new large-scale architecture/mechanisms.
```

Demote work that:

- creates a second canonical protocol/verifier/orchestrator;
- adds autonomy before protection/verification gates;
- increases generation without verifier/reviewer capacity;
- duplicates an active branch/PR;
- optimizes activity/popularity rather than verified value;
- makes broad restructuring changes without measured structural gain.

---

# Completion rule

A target is complete only when its **observable evidence** exists.

A merged design document, green worker self-test, high model confidence, or many commits is not by itself evidence that the target is satisfied.

Future IDKGraph tooling should derive more of this graph automatically from Issues, PRs, contracts, verification artifacts, CI, and repository state while preserving a human-readable explanation of *why* each task is prioritized.
