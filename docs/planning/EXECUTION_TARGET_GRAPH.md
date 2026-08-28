# IDKMesh Execution Target Graph

**Snapshot:** 2026-08-28  
**Purpose:** convert the broad project goals into a small dependency-ordered set of targets, tasks, and observable evidence.

This document does **not** replace `GOALS.md`, `ROADMAP.md`, GitHub Issues, or IDKGraph. It is the current execution view: what must become true next for IDKMesh to test its central claims.

## North Star

> **Verified useful work per unit of human attention and compute.**

The immediate project objective is not maximum activity, maximum issue count, maximum agent count, or maximum documentation. It is to establish a reproducible path:

```text
bounded goal/task
  -> canonical Work Unit
  -> isolated candidate execution
  -> canonical ResultManifest
  -> independent verification
  -> VerificationResult + evidence
  -> human integration decision
  -> replayable experiment record
```

Once this path works locally, IDKMesh can measure whether additional workers, diversity, scheduling, community growth, distributed compute, and self-evolution actually improve the North Star.

## Hard constraints

These constraints dominate priority scoring. A high-value task does not bypass them.

1. **No autonomous merge into canonical `main` for the v0.1 product loop.**
2. **One autonomous actor must not propose, approve, and merge its own protected change.**
3. **Worker success is not acceptance.** Independent verification remains separate.
4. **Generation must not outrun verification capacity.**
5. **Project-paid compute remains disabled under the current zero-project-spend policy.**
6. **Scale is earned by evidence:** local -> small mesh -> larger mesh.
7. **Community growth is measured by verified useful descendants, not raw activity.**
8. **Repository restructuring is bounded, reversible, and evidence-backed.**

---

# Critical execution chain

The critical product chain is:

```text
T0 Protected integration boundary
        |
        v
T1 Canonical bounded local worker
        |
        +------------------+
        |                  |
        v                  v
T2 Executable verifier   T3 Multi-worker orchestrator
        |                  |
        +--------+---------+
                 v
T4 Verified Swarm Runner v0.1
                 |
                 v
T5 Real-task flagship experiment
                 |
                 v
T6 Evidence-driven scaling decisions
```

T0 is a safety gate. T1-T4 create the product kernel. T5 produces the first evidence that can justify or reject major scaling ideas.

---

# T0 — Protected integration boundary

**Goal supported:** reliable community-scale engineering; guarded self-evolution.  
**Tracker:** #35  
**Repository-side guard:** PR #51

## Required state

GitHub itself, not only project instructions, enforces that protected changes pass through explicit integration controls.

## Current state

Repository-side fail-closed behavior is proposed in PR #51. The final branch/ruleset configuration requires repository-admin settings and cannot be replaced by committed Markdown or workflow instructions.

## Completion evidence

- public branch metadata reports `main` as protected;
- force push/deletion behavior is intentional;
- required stable checks are configured;
- review requirements match risk class;
- autonomous systems cannot bypass the integration boundary.

## Next task

Repository administrator performs the #35 admin gate and records the resulting GitHub protection state.

**Important:** this can proceed in parallel with local code development, but stronger autonomous write/merge authority remains blocked until T0 is satisfied.

---

# T1 — Canonical bounded local worker

**Goals supported:** Goal 3 distributed Work Units; Goal 4 verification-ready engineering.  
**PR:** #34  
**Acceptance gate:** #37  
**Parent issues:** #11, #16

## Required state

One canonical worker consumes the project Work Unit contract, performs bounded execution in an isolated workspace, and emits a canonical ResultManifest without claiming acceptance.

## Current state

PR #34 is the canonical implementation path and supersedes the competing node protocol in PR #21. At this snapshot GitHub reports PR #34 as mergeable, but its branch has diverged from rapidly changing `main`; new verification-contract work exists on `main` and must be reconciled before integration.

## Completion evidence

- PR #34 is synchronized with current `main`;
- Phase 0 contract CI passes on the synchronized head;
- node unit/safety CI passes;
- controlled Docker acceptance #37 succeeds;
- negative path-policy check succeeds;
- independent review finds no blocking sandbox/path-policy regression;
- candidate output remains explicitly unverified.

## Next tasks

1. synchronize #34 with current `main` without force-overwriting concurrent work;
2. rerun checks;
3. execute #37 on a controlled Docker host;
4. integrate after independent review;
5. retire/split PR #21 so contributors see one canonical node protocol.

---

# T2 — Executable independent verifier

**Goal supported:** Goal 4 enterprise-quality verification.  
**Tracker:** #5  
**Research link:** #14

## What already exists

The repository now contains:

- `schemas/verification-result-v0.1.schema.json`;
- valid and negative VerificationResult fixtures;
- cross-object verification validation in `experiments/harness.py`;
- explicit worker/verifier independence checks;
- verification-debt/backpressure research and a controller prototype.

This means the next task is **not another verification result format**.

## Missing capability

A verifier must actually execute an evaluation against a candidate and produce a VerificationResult from observed evidence.

## Phase A — smallest verifier MVP

Build one deterministic local verifier that takes:

```text
Work Unit
+ ResultManifest
+ pinned source/candidate artifact
+ verifier configuration
        |
        v
execute required checks independently
        |
        v
VerificationResult v0.1
```

Initial required check types should remain small:

1. schema/contract validation;
2. existing repository tests for a bounded fixture;
3. one verifier-owned hidden/independent check;
4. unauthorized-scope/path check;
5. evidence digest/provenance capture.

## Phase A acceptance evidence

- verifier implementation cannot be modified by the candidate it is verifying;
- fixed input produces reproducible check selection/result semantics;
- failed required checks prevent `accept_candidate` recommendation;
- timeout/error/inconclusive states are explicit;
- evidence digests and environment provenance are emitted;
- a deliberately bad candidate is rejected by an independent check;
- a known-good fixture produces a schema-valid VerificationResult;
- worker and verifier identities/independence satisfy the canonical contract.

## Phase B — benchmark substrate

After the executable verifier exists, build a **small first benchmark cohort** before expanding to 20-50 tasks.

Recommended first cohort: 5-10 repository-level tasks covering a mix of bug, test, code-consistency, bounded feature, and documentation/code-contract work. Every task needs an immutable source snapshot and verifier-owned acceptance evidence.

Then expand only when replay/review cost is understood.

---

# T3 — Single-machine multi-worker orchestrator

**Goals supported:** Goal 1 collective coding; Goal 7 collective-intelligence science.  
**Tracker:** #4  
**Milestone:** #16

## Required state

One coordinator dispatches the same bounded Work Unit to multiple isolated attempts, tolerates individual failures, collects canonical ResultManifests, and routes candidates to independent verification.

## Dependencies

- canonical Work Unit/ResultManifest contracts: **landed** (#3 closed);
- canonical worker execution path: **T1 / #34**;
- executable verifier: **T2 / #5**.

## First implementation slice

Do not begin with a complex scheduler.

Start with:

- 2 independent local attempts;
- one shared worker-adapter interface;
- explicit attempt IDs/seeds/config provenance;
- deterministic fan-out order;
- timeout/failure isolation;
- candidate collection;
- call into the independent verifier;
- replayable run manifest;
- cleanup.

Then increase to 3-5 workers after the two-worker loop is reliable.

## Completion evidence

- failed worker A does not prevent worker B completing;
- attempts cannot modify canonical working state;
- each candidate has independent provenance;
- verifier runs outside the candidate's own success claim;
- a saved run description can be replayed;
- no merge/write to canonical `main` occurs.

---

# T4 — Verified Swarm Runner v0.1

**Primary milestone:** #16

## Product definition

```text
install
 -> choose bounded repository task
 -> run 2+ isolated candidate attempts
 -> independently verify each candidate
 -> inspect Evidence Report
 -> human accept / reject / refine
 -> replay if needed
```

## Already-established foundations

- Work Unit + ResultManifest contracts (#3 completed);
- IDKIP process (#7 completed);
- canonical VerificationResult contract on `main`;
- experiment/run schemas and Phase 0 harness;
- canonical local node path under review (#34).

## Remaining product gates

1. integrate T1 canonical local worker;
2. complete T2 executable verifier;
3. complete T3 multi-worker coordinator;
4. define minimal Evidence Report assembled from ResultManifest + VerificationResult artifacts;
5. save replayable run/experiment provenance;
6. provide one trivial second heterogeneous adapter after the core loop is stable;
7. document the adapter boundary without adding provider-specific branches to the coordinator.

## v0.1 exit evidence

A newcomer can run one bounded repository task through at least two attempts, observe isolation, inspect independent verification, reproduce the run, and understand why the human integration decision is distinct from both worker success and verifier recommendation.

---

# T5 — First real-task flagship experiment

**Trackers:** #2, #13, #14, #30

Synthetic R1 diversity experiments are useful mechanism tests, but they are not yet evidence that multi-agent coding improves real repository work.

## Experiment question

> Under a fixed resource/review budget, when does structural diversity plus independent verification outperform homogeneous replication on real repository-level tasks?

## Minimum arms

1. one baseline worker;
2. replicated homogeneous attempts;
3. seed-only variation;
4. structurally diverse attempts;
5. diverse attempts + independent verifier assignment.

## Required metrics

- verified task success;
- independent/hidden check success;
- escaped regressions/security failures;
- pairwise error correlation;
- compute/resource use;
- latency;
- human review attention;
- verified utility per unit cost;
- negative/harmful regimes.

## Activation gate

Do not call this a coding-swarm result until T4 can replay actual candidate artifacts through the canonical verification pipeline.

---

# T6 — Evidence-driven scaling decisions

Only after T5 should the project materially increase complexity in:

- advanced scheduling (#31);
- evolutionary orchestration (#32);
- larger volunteer compute (#1);
- A2A/MCP networking/interoperability (#17);
- ProjectManifest/DomainPack complexity (#6);
- broader distributed/federated control planes.

Evidence may show that some of these should be accelerated, changed, or abandoned.

---

# Parallel track A — Community reproduction

**Goal supported:** Goal 5 scalable open-source community.  
**Trackers:** #9, #10, #23, #24-#28, PR #40, PR #48, #57

## Current rule

Do not expand community automation because raw activity is high. The current ACE ledger is already in a high-review-load/consolidation regime.

## Near-term tasks

1. review/integrate lineage evidence PR #48 or equivalent (#25);
2. review/integrate cohort observability PR #40 or equivalent;
3. complete ACE threat model #26 before stronger permissions;
4. obtain real newcomer evidence via #24;
5. evaluate verified descendants and reviewer attention before Cohort 2;
6. keep ACE v1 #57 offline/advisory until its activation gates are satisfied.

## Success signal

```text
verified useful descendants
---------------------------
reviewer + maintainer minutes
```

increases without overloading review capacity.

---

# Parallel track B — Repository homeostasis and IDKGraph

**Goals supported:** collaboration under uncertainty; guarded self-evolution.  
**Trackers:** #20, #35, #38, PR #36, PR #43, #46

## Near-term tasks

1. refresh/revalidate stale RHE PR #36 against current `main`;
2. keep RHE proposal-only;
3. establish a fresh structural baseline;
4. run only Structural Migration 001 (#38) first;
5. preserve zero broken internal links;
6. measure migration cost vs structural improvement;
7. fuse repository/GitHub/evidence graphs only after the lower-level observers are stable.

This track should reduce project navigation/coordination cost, not compete with T1-T4 for unlimited attention.

---

# Parallel track C — Zero-spend local compute

**Constraint/trackers:** current compute policy, #52, #11

The next compute step is local capability discovery and a provider-neutral zero-cost offer, not a global resource market.

Do not let distributed compute networking block the local Verified Swarm Runner. T4 should first prove useful work on one controlled machine.

---

# Task-selection policy

When choosing the next repository task, use this ordering:

```text
1. remove a blocker on T0-T4;
2. repair a verification/safety regression;
3. integrate duplicated competing implementations;
4. produce evidence for T5;
5. reduce community/reviewer friction with measured benefit;
6. reduce repository structural pressure with measured benefit;
7. only then add new architecture or scaling mechanisms.
```

A candidate task should be demoted when it:

- adds another protocol where a canonical contract exists;
- adds autonomy before protection/verification gates;
- increases generated work without verifier/reviewer capacity;
- duplicates an active PR;
- optimizes activity/popularity instead of verified value;
- creates large migration cost without a measurable structural gain.

---

# Current claimable execution queue

## NOW

| Priority | Task | Tracker | Observable done condition |
| --- | --- | --- | --- |
| P0 | Protect `main` in GitHub settings | #35 | GitHub reports protection/ruleset active |
| P0 | Synchronize canonical worker with current `main` | PR #34 | current contracts + node CI pass on one head |
| P0 | Run controlled Docker acceptance | #37 | positive + negative runtime evidence attached |
| P0 | Build executable verifier MVP | #5 | real candidate -> schema-valid independent VerificationResult |

## NEXT

| Priority | Task | Tracker | Observable done condition |
| --- | --- | --- | --- |
| P1 | Build two-worker coordinator loop | #4 | two isolated candidates survive independent failure |
| P1 | Assemble minimal Evidence Report/replay record | #16 | newcomer can inspect and replay one verified swarm run |
| P1 | Add one second trivial heterogeneous adapter | #16/#17 | coordinator core unchanged across adapters |
| P1 | Replay real task cohort through v0.1 | #2/#30 | raw candidate + verification evidence published |

## PARALLEL, CAPACITY-GATED

| Track | Task | Tracker |
| --- | --- | --- |
| Community | lineage + cohort evidence | PR #48, PR #40, #25 |
| Community | ACE threat model | #26 |
| Repository | refresh RHE, then Migration 001 | PR #36, #38 |
| Compute | local capability discovery | #52 |
| Research | continue synthetic mechanism maps when they feed T5 | #14, #30, #49 |

## LATER / EVIDENCE-EARNED

- global scheduling;
- token/economic mechanisms;
- large autonomous controller promotion;
- broad repository reorganizations;
- large volunteer mesh deployment;
- sophisticated evolutionary orchestration in production.

---

# How to update this graph

This file is a snapshot, not a permanent truth. Update it when evidence changes a dependency or target state.

A target is complete only when its stated **observable evidence** exists. A merged document or a high activity count is not automatically completion.

Future IDKGraph tooling should derive more of this view automatically from GitHub Issues/PRs, schemas, verification artifacts, and repository state while preserving human-readable explanations of why tasks are prioritized.
