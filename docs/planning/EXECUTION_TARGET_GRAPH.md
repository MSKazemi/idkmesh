# IDKMesh Execution Target Graph

**Snapshot:** 2026-08-28  
**Purpose:** keep IDKMesh focused on the shortest evidence-producing path from broad goals to a working, independently verified local product.

This is the current execution view. It does not replace `GOALS.md`, `ROADMAP.md`, GitHub Issues, ADRs, or future machine-generated IDKGraph views.

## North Star

> **Verified useful work per unit of human attention and compute.**

The immediate product path is:

```text
bounded goal/task
  -> canonical WorkUnit
  -> isolated real worker attempts
  -> canonical ResultManifests
  -> bound EvaluatorPlan
  -> independent verifier-owned checks
  -> canonical VerificationResults
  -> non-selecting Evidence Report
  -> explicit human integration decision
  -> replayable experiment record
```

Raw activity, issue count, agent count, stars, model confidence, or worker self-reported success are not substitutes for this evidence chain.

## Hard constraints

1. No autonomous merge into canonical `main` for v0.1.
2. One autonomous actor must not propose, approve, and merge the same protected change.
3. Worker success is not acceptance.
4. Verifier recommendation is decision support, not merge authority.
5. Evaluator control must be bound to the exact WorkUnit/revision and remain outside candidate control.
6. Generated verifier/evaluator/report evidence must not gain authority to overwrite canonical tracked state.
7. Generation must not outrun verification/reviewer capacity.
8. Project-paid compute remains disabled under the current zero-project-spend policy.
9. Scale is earned by evidence: local -> small mesh -> larger mesh.
10. Community growth is measured by verified useful descendants, not raw activity.
11. Repository restructuring is bounded, reversible, and evidence-backed.
12. Integrate before reinventing: one canonical WorkUnit, evaluator, verifier, orchestrator, and report path unless a competing experiment is explicitly justified.

---

# Current critical path

```text
T0 GitHub integration protection (#35)

T1 PR #91 + #37 canonical real worker ----------------------+
                                                              |
T2a PR #72 deterministic verifier [DONE]                    |
T2b PR #81 EvaluatorPlan sovereignty [DONE]                 |
T2c PR #103 output authority [DONE]                         |
T2d PR #105 unified-diff evaluator [GREEN / REVIEW] --------+
                                                              |
T3a PR #78 two-attempt orchestration [DONE]                 |
T3b real-node adapter after T1/T2d -------------------------+
                                                              |
T4 PR #88 Evidence Report/replay [GREEN / REVIEW] ----------+
                                                              |
                                                              v
Verified Swarm Runner v0.1 real replayable run (#16)
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
| **T0 Protected integration** | **BLOCKED / ADMIN** | GitHub still reports `main` unprotected; #35 defines the desired boundary | Configure/verify GitHub ruleset or branch protection |
| **T1 Canonical real worker** | **GREEN STATIC / RUNTIME GATED** | PR #91 frozen at `d638a2f78e4a89353b98e91052233e365f56f90a`; Node CI + Phase 0 green | Controlled Docker acceptance #37 + independent sandbox/path review |
| **T2a Deterministic verifier** | **DONE FOUNDATION** | PR #72 merged canonical `experiments/local_verifier.py` | Extend canonical backends only |
| **T2b Evaluator sovereignty** | **DONE FOUNDATION** | PR #81 merged exact WorkUnit/revision/validator binding | Reuse for real evaluators |
| **T2c Output authority** | **DONE** | clean PR #103 merged; verifier/evaluator generated output restricted to ignored root `results/` | Preserve this boundary in all evaluator/report paths |
| **T2d Patch-bundle evaluator** | **GREEN / REVIEW** | clean PR #105 implements EvaluatorPlan v0.2 unified-diff backend; EvaluatorPlan + Phase 0 + Evolution checks green | Independent review/integration, then replay a real #91/#37 bundle |
| **T3a Two-attempt orchestration** | **DONE FOUNDATION** | PR #78 merged deterministic replayable two-attempt kernel | Reuse adapter boundary |
| **T3b Real node adapter** | **BLOCKED BY T1/T2d** | canonical adapter boundary already exists | Connect PR #91 node after #37 and real patch evaluator |
| **T4 Evidence Report/replay** | **GREEN / REVIEW** | PR #88 provides non-selecting fixture report/replay; Run Evidence + Phase 0 green | Integrate and exercise over real node attempts |
| **T5 Real-task experiment** | **WAITING ON T4 REAL RUN** | synthetic/replay research infrastructure exists | Run comparable real candidates through canonical loop |
| **T6 Larger-scale mesh** | **EVIDENCE-EARNED** | scheduling/evolution/compute research exists | Promote only mechanisms supported by T5 evidence |

---

# Canonical trust chain

The project should converge on one durable evidence path:

```text
WorkUnit             authoritative bounded task/requirements
ResultManifest       untrusted worker claim + artifacts
EvaluatorPlan        verifier-owned exact bound control plane
VerificationResult   independent evidence / recommendation
Evidence Report      non-selecting synthesis
Human decision       integration authority
```

Do not create competing canonical formats for these roles unless a competing experiment is explicit and remains interoperable with the established evidence chain.

## Verification

PR #72 established verifier-owned deterministic evaluation. PR #81 made evaluator control content-addressed and bound to the exact WorkUnit/revision and required validator set. PR #103 made executable output authority match the intended read-only/evidence-only role.

PR #105 extends the same canonical verifier with a metadata-only unified-diff backend. It independently reconstructs patch/log digests, patch paths, WorkUnit path authority, and a verifier-owned semantic expectation without executing candidate code.

## Orchestration

PR #78 already proves the control-plane invariants needed before real workers:

- distinct attempt histories;
- worker-success candidate independently supported;
- worker-success candidate independently rejected;
- peer worker failure isolation;
- ResultManifest evidence preserved through verifier failure;
- deterministic semantic replay;
- no majority-vote-as-truth;
- no automatic selection/merge;
- generated run output restricted to ignored `results/`.

Issue #4 remains open because the real node adapter and later 3–5 worker extension are still missing.

## Reporting

PR #88 provides a non-selecting Evidence Report/replay layer for fixture runs. Its job is to preserve evidence and disagreement, not choose a winner.

The real product exit gate is to exercise that same report over real node attempts and leave the human decision explicitly external.

---

# NOW queue

## 1. Protect `main` — #35

GitHub metadata still reports the integration boundary as unprotected.

Done means GitHub itself enforces intentional:

- PR-based integration requirements;
- force-push/deletion behavior;
- required stable checks;
- risk-appropriate independent review;
- no autonomous bypass of protected integration.

This is repository-admin/settings work. Another Markdown file or agent rule cannot substitute for it.

## 2. Independently review/integrate patch evaluator PR #105

PR #105 is the clean successor to closed #102 and is now directly downstream of merged #103.

It adds:

- EvaluatorPlan v0.2 `unified_diff` backend;
- exact WorkUnit/revision/validator binding;
- independent patch SHA-256;
- independent declared-log SHA-256;
- safe old/new unified-diff path extraction;
- WorkUnit allowed/forbidden/write-scope enforcement;
- verifier-owned semantic added-line expectation;
- good / wrong-semantic / forbidden-path / forged-digest / binding-drift tests;
- no patch application or candidate-code execution.

All relevant workflows are green. Green CI is necessary but not self-approval.

## 3. Execute the frozen controlled-Docker gate — #37 / PR #91

This is the principal physical/runtime bottleneck.

Use exact SHA:

`d638a2f78e4a89353b98e91052233e365f56f90a`

Required evidence:

1. controlled Docker positive run;
2. ResultManifest + `changes.patch` + stdout/stderr bundle;
3. negative A–E path/runtime/provenance cases required by #37;
4. independent review of sandbox, path authority, pinned image, cleanup, and provenance.

Do not claim this gate from static CI or an environment without the required controlled Docker host.

## 4. Replay the real #37 bundle through the canonical evaluator — #5

Once the positive bundle exists:

```text
#37 bundle
 -> bind EvaluatorPlan v0.2 to exact WorkUnit/revision
 -> PR #105 unified-diff evaluator
 -> VerificationResult v0.1
```

Independently confirm:

- patch/log digests;
- patch path authority;
- verifier-owned harmless README smoke semantics;
- exact WorkUnit required validator IDs;
- evaluator/verifier provenance.

Fixture success does not complete this target; one real #91 bundle must replay cleanly.

## 5. Connect PR #91 behind the landed PR #78 adapter boundary — #4

After T1 and T2d:

- run exactly two isolated real attempts from one WorkUnit/revision;
- preserve worker errors, verifier errors, support, and rejection independently;
- keep orchestrator core worker-implementation-neutral;
- retain replayable run metadata.

## 6. Exercise PR #88 over the real two-attempt run — #16

The report must preserve:

- ResultManifest identity/digest;
- EvaluatorPlan identity/digest/backend;
- VerificationResult identity/digest/status;
- worker/verifier errors and disagreement;
- resource signals;
- `human_decision.status = pending` until external human/governance action;
- no automatic selected attempt.

That creates the first complete real v0.1 evidence loop.

---

# NEXT queue

## Add one trivial heterogeneous second real adapter — #16

Only after the canonical node path is stable. Prove that a second real adapter can plug into the same coordinator boundary without model/vendor branches in coordinator core.

## First real benchmark cohort — #5

After one real node bundle and one real two-attempt run replay cleanly, build **5–10 tasks** before expanding toward 20–50.

Every benchmark item needs:

- immutable source revision;
- bounded WorkUnit;
- bound EvaluatorPlan;
- ResultManifest/candidate bundle;
- independent VerificationResult;
- replay instructions;
- meaningful negative/seeded-failure evidence;
- resource/reviewer-attention accounting.

## Real-task R1 — #2/#30

Only after T4 produces comparable real candidate/evidence sets.

Compare under fixed budgets:

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

Growth Seed #28 is complete. Do not turn one successful seed into issue-volume growth.

Continue prioritizing:

- parent -> seed -> verified-descendant lineage;
- ACE threat model;
- real newcomer-path evidence;
- verified descendants per reviewer/maintainer minute;
- cohort expansion only when reviewer capacity supports it.

## Repository homeostasis / IDKGraph — #20/#36/#38

- refresh/revalidate Repository Homeostasis work against current `main`;
- keep structural changes proposal-first;
- rerun structural baseline;
- perform bounded Migration 001 before broader cleanup;
- preserve zero broken links;
- measure structural benefit against migration/review cost.

This track should reduce navigation/coordination cost, not consume the product critical path.

## Scheduling / evolutionary research

R2/R3 synthetic scale and evolutionary work can continue as research, but promotion into the real product remains evidence-gated.

A large synthetic worker count is not a substitute for T1–T5 real evidence.

---

# Task-selection rule

Choose the next repository task in this order:

```text
1. repair a safety/authority/verification invariant;
2. remove a blocker on the real T1–T4 evidence path;
3. converge duplicate implementations into one canonical path;
4. produce real replayable evidence for T5;
5. reduce reviewer/community friction with measured benefit;
6. reduce repository structural pressure with measured benefit;
7. only then promote new scaling/autonomy mechanisms.
```

Demote work that:

- creates a second canonical protocol/verifier/evaluator/orchestrator/report path;
- adds autonomy before GitHub protection and verification gates;
- increases generation without verification/reviewer capacity;
- duplicates an active branch or landed implementation;
- optimizes activity/popularity rather than verified value;
- makes broad structural changes without measurable gain;
- presents synthetic scale as proof of real-world system quality.

---

# Completion rule

A target is complete only when its **observable acceptance evidence** exists.

A merged design document, worker self-test, green fixture, high model confidence, or many commits is not by itself evidence that a real target is satisfied.

Future IDKGraph tooling should derive more of this view automatically from Issues, PRs, WorkUnits, ResultManifests, EvaluatorPlans, VerificationResults, Evidence Reports, CI, and repository state while preserving a human-readable explanation of *why* each task is prioritized.
