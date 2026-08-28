# IDKMesh Execution Target Graph

**Snapshot:** 2026-08-28  
**Purpose:** keep IDKMesh focused on the shortest evidence-producing path from its broad goals to a working, independently verified local product.

This is a current execution view. It does not replace `GOALS.md`, `ROADMAP.md`, GitHub Issues, ADRs, or future machine-generated IDKGraph views.

## North Star

> **Verified useful work per unit of human attention and compute.**

The immediate product path is:

```text
bounded goal/task
  -> canonical Work Unit
  -> isolated real worker attempts
  -> canonical ResultManifests
  -> bound EvaluatorPlan
  -> independent verifier-owned checks
  -> canonical VerificationResults
  -> Evidence Report / human integration decision
  -> replayable experiment record
```

Raw activity, issue count, agent count, stars, model confidence, or worker self-reported success are not substitutes for this evidence chain.

## Hard constraints

1. No autonomous merge into canonical `main` for v0.1.
2. One autonomous actor must not propose, approve, and merge the same protected change.
3. Worker success is not acceptance.
4. Verifier recommendation is decision support, not merge authority.
5. Evaluator control must be bound to the exact Work Unit/revision and remain outside candidate control.
6. Generated verifier/evaluator evidence must not gain authority to overwrite canonical tracked state.
7. Generation must not outrun verification/reviewer capacity.
8. Project-paid compute remains disabled under the current zero-project-spend policy.
9. Scale is earned by evidence: local -> small mesh -> larger mesh.
10. Community growth is measured by verified useful descendants, not raw activity.
11. Repository restructuring is bounded, reversible, and evidence-backed.
12. Integrate before reinventing: one canonical Work Unit, evaluator, verifier, and orchestrator path unless a competing experiment is explicitly justified.

---

# Current critical path

```text
T0 GitHub integration protection (#35)

T1 real bounded worker (#34 + #37) -------------------------+
                                                             |
T2a deterministic verifier [DONE: PR #72]                   |
T2b EvaluatorPlan / sovereignty [DONE: PR #81]              |
T2c verifier output authority [GREEN: PR #90]               |
T2d real repository patch verification (#5) ----------------+
                                                             |
T3a two-attempt orchestration [DONE: PR #78]                |
T3b canonical node adapter after T1 ------------------------+
                                                             |
                                                             v
T4 Evidence Report + replayable Verified Swarm Runner (#16)
                                                             |
                                                             v
T5 real-task diversity/verification experiment (#2/#30)
                                                             |
                                                             v
T6 evidence-driven scaling / federation decisions
```

T0 is the safety gate for stronger autonomous integration. It does not block isolated/read-only product development, but stronger autonomous write/merge authority remains prohibited until GitHub itself enforces the intended boundary.

---

# Target status

| Target | Status | Evidence now | Next gate |
| --- | --- | --- | --- |
| **T0 Protected integration** | **BLOCKED / ADMIN** | GitHub currently reports `main` as unprotected; #35 defines the target | Configure branch/ruleset protection and verify it through GitHub metadata |
| **T1 Canonical real worker** | **IN PROGRESS** | PR #34 implements canonical local node path and has prior green CI | Synchronize with current `main`; controlled Docker acceptance #37; independent sandbox/path review |
| **T2a Deterministic verifier** | **DONE FOUNDATION** | PR #72 merged `experiments/local_verifier.py` | Extend, do not replace |
| **T2b Evaluator sovereignty** | **DONE FOUNDATION** | PR #81 merged `EvaluatorPlan v0.1`, exact Work Unit/revision and validator binding | Reuse EvaluatorPlan for patch/hidden-test backends |
| **T2c Output authority** | **GREEN / REVIEW** | PR #90 restricts both verifier entrypoints to ignored root `results/`; Phase 0 + EvaluatorPlan CI pass | Independent review/integration |
| **T2d Real patch verification** | **NEXT PRODUCT WORK** | #5 now specifies node `changes.patch` verification | Implement digest + unified-diff scope + verifier-owned semantic negative tests through canonical EvaluatorPlan path |
| **T3a Two-attempt orchestration** | **DONE FOUNDATION** | PR #78 merged deterministic replayable fixture kernel | Reuse adapter boundary; do not create second orchestrator |
| **T3b Real node adapter** | **BLOCKED BY T1/T2d** | Orchestrator adapter boundary exists | Connect #34 node after Docker acceptance and patch verifier |
| **T4 v0.1 local product** | **PARTIALLY UNBLOCKED** | contracts + verifier + EvaluatorPlan + fixture orchestration exist | real worker + real patch verifier + Evidence Report/replay CLI |
| **T5 Real-task experiment** | **WAITING ON T4** | synthetic/replay research infrastructure exists | run comparable real candidates through canonical product loop |
| **T6 Larger-scale mesh** | **EVIDENCE-EARNED** | scheduling/evolution/compute research exists | promote only mechanisms supported by real T5 evidence |

---

# What is already settled

## Canonical contracts

The project should not create competing formats for:

- Work Unit / ResultManifest;
- VerificationResult;
- EvaluatorPlan;
- the two-attempt orchestration run model.

Competing experiments are welcome only when they test an explicit hypothesis and preserve interoperability with canonical evidence contracts.

## Verification architecture

PR #72 established verifier-owned deterministic evaluation. PR #81 strengthened it with Evaluator Sovereignty:

```text
WorkUnit             public authority / requirements
ResultManifest       untrusted worker claim
EvaluatorPlan        verifier-owned, exact bound control plane
VerificationResult   independent evidence / recommendation
```

Any future hidden-test, static-analysis, patch, or sandbox backend should extend this control chain rather than bypass it.

## Orchestration architecture

PR #78 proved the control-plane semantics needed before real workers:

- two distinct attempt histories;
- worker-success candidate independently accepted;
- worker-success candidate independently rejected;
- peer worker failure isolation;
- ResultManifest evidence preserved through verifier failure;
- deterministic semantic replay;
- no majority-vote-as-truth;
- no automatic selection/merge;
- run output constrained to ignored `results/`.

Issue #4 remains open because real node integration is still missing.

---

# NOW queue

## 1. Protect `main` — #35

Current GitHub metadata still reports `protected=false`.

This is the highest governance/safety gap because repository instructions are not an enforcement boundary.

Done means GitHub itself reports intentional:

- PR-based integration requirements;
- force-push/deletion behavior;
- required stable checks;
- risk-appropriate review requirements;
- no autonomous bypass of the integration boundary.

This is repository-admin/settings work; another Markdown file cannot substitute for it.

## 2. Independently review/integrate PR #90

PR #90 has green Phase 0 and EvaluatorPlan CI.

It closes an authority mismatch:

```text
before: evaluator output = any repository-relative path outside candidate
now:    evaluator output = ignored root results/ only
```

Do not self-approve merely because CI is green.

## 3. Synchronize PR #34 and execute #37

T1 is now the primary physical/runtime bottleneck.

Required order:

1. synchronize PR #34 with current `main` without overwriting concurrent work;
2. rerun current node + contract CI;
3. run controlled Docker acceptance #37 against the exact synchronized SHA;
4. attach positive runtime evidence;
5. attach negative path-policy evidence;
6. obtain independent sandbox/path-policy review;
7. integrate only after those gates.

Do not claim #37 from a non-Docker/static-only environment.

## 4. Build #5 Phase B1: real patch-bundle evaluator

First bounded target: the canonical node smoke candidate.

The evaluator should inspect the candidate bundle without executing candidate code and independently prove at least:

- exact Work Unit / ResultManifest / EvaluatorPlan binding;
- candidate patch and declared log SHA-256 values;
- safe unified-diff target path extraction;
- `allowed_paths` / `forbidden_paths` enforcement;
- expected harmless README smoke property;
- rejection of a scope-valid but semantically wrong patch;
- rejection of forbidden-path and forged-digest candidates;
- fail-closed behavior when required validators are unsupported.

Reuse the useful mechanisms explored in closed PR #61, but extend the canonical verifier/EvaluatorPlan path rather than reviving `verifier/deterministic.py`.

## 5. Connect the real node adapter to PR #78 orchestration

Only after T1 and T2d are stable.

The merged orchestrator core should not need node-specific branches beyond an adapter that returns the same candidate/result boundary.

---

# NEXT queue

## Minimal Evidence Report / replay UX — #16

For each attempt show:

- worker status;
- ResultManifest identity/digest;
- EvaluatorPlan identity/digest/backend;
- verifier status/recommendation;
- required check outcomes/findings;
- artifact/evidence locators;
- resource signals;
- errors/disagreement;
- explicit human integration state: `pending | accept | reject | refine`.

No majority-vote shortcut and no auto-merge.

## First real benchmark cohort — #5

After one node patch bundle replays cleanly, build 5–10 tasks before expanding toward 20–50.

Every benchmark item needs:

- fixed source snapshot;
- bounded Work Unit;
- bound EvaluatorPlan;
- candidate ResultManifest/bundle;
- verifier-owned acceptance evidence;
- replay instructions;
- meaningful negative/seeded-failure evidence;
- resource/reviewer-attention accounting.

## Real-task R1 — #2/#30

Only after T4 can generate comparable real candidate/evidence sets.

Test under fixed budgets:

1. one baseline worker;
2. homogeneous replication;
3. seed-only variation;
4. structural/adapter diversity;
5. diversity + independent verification.

Measure verified success, escaped defects, pairwise failure correlation, compute, latency, and human attention.

Synthetic scheduling/evolution studies inform hypotheses; they do not prove the real coding-swarm claim.

---

# Parallel capacity-gated tracks

## Community reproduction — #9/#10

Growth Seed #28 has completed its five-task IDKGraph decomposition. Do not interpret completion of one seed as permission to flood the tracker.

Continue prioritizing:

- parent -> seed -> verified-descendant lineage;
- ACE threat model;
- real newcomer-path evidence;
- verified descendants per reviewer/maintainer minute;
- cohort expansion only when review capacity supports it.

## Repository homeostasis / IDKGraph — #20/#36/#38

- refresh/revalidate stale Repository Homeostasis work against current `main`;
- keep structural changes proposal-first;
- rerun structural baseline;
- perform bounded Migration 001 before broader cleanup;
- preserve zero broken links;
- measure migration/review cost vs structural benefit.

This track should reduce product/community navigation cost, not consume unlimited product attention.

## Scheduling / evolutionary research

R2/R3 synthetic scale and evolutionary work can continue as research, but promotion into the real product remains evidence-gated.

A large synthetic worker count is not a substitute for T1–T5 real evidence.

---

# Task-selection rule

Choose the next repository task in this order:

```text
1. repair a safety/authority/verification invariant;
2. remove a blocker on T1–T4;
3. converge duplicate implementations into one canonical path;
4. produce real replayable evidence for T5;
5. reduce reviewer/community friction with measured benefit;
6. reduce structural pressure with measured benefit;
7. only then promote new scaling/autonomy mechanisms.
```

Demote work that:

- creates a second canonical protocol/verifier/evaluator/orchestrator;
- adds autonomy before GitHub protection and verification gates;
- increases generation without verification/reviewer capacity;
- duplicates an active branch or landed implementation;
- optimizes activity/popularity rather than verified value;
- makes broad structural changes without measurable gain;
- presents synthetic scale as proof of real-world system quality.

---

# Completion rule

A target is complete only when its **observable acceptance evidence** exists.

A merged design document, worker self-test, high model confidence, or many commits is not by itself evidence that the target is satisfied.

Future IDKGraph tooling should derive more of this view automatically from Issues, PRs, contracts, EvaluatorPlans, VerificationResults, CI, and repository state while preserving a human-readable explanation of *why* each task is prioritized.
