# IDKMesh Execution Target Graph

**Snapshot:** 2026-08-28  
**Mode:** convergence before expansion

**Freshness note:** This is a point-in-time graph, and some numbered PR states below are historical. Revalidate every node against live GitHub and current main before acting; do not treat stale status prose as an integration instruction.

This is the live execution view for the shortest evidence-producing path from IDKMesh's broad goals to a working, independently verified local product. It does not replace `GOALS.md`, `ROADMAP.md`, Issues, ADRs, or future machine-generated IDKGraph views.

## North Star

> **Verified useful work per unit of human attention and compute.**

The immediate evidence chain is:

```text
bounded WorkUnit
 -> isolated real worker candidate
 -> ResultManifest + candidate artifact
 -> independently bound EvaluatorPlan
 -> verifier-owned checks
 -> VerificationResult
 -> multi-attempt orchestration
 -> non-selecting Evidence Report
 -> explicit human/governance decision
 -> replayable experiment record
```

Raw activity, PR count, agent count, stars, model confidence, or worker self-reported success are not substitutes for this chain.

## Hard constraints

1. Worker success is not acceptance.
2. Verifier recommendation is decision support, not merge authority.
3. No actor should propose, approve, and merge the same protected change autonomously.
4. Generated evidence must not gain authority to overwrite canonical tracked state.
5. Generation must not outrun verification/reviewer capacity.
6. Project-paid compute remains disabled under the current zero-project-spend policy.
7. Scale is earned by evidence: local -> small mesh -> larger mesh.
8. Community growth is measured by verified useful descendants, not raw activity.
9. Integrate before reinventing: one canonical WorkUnit, evaluator, verifier, orchestrator, and report path unless a competing experiment is explicitly justified.
10. Stronger autonomous write/merge behavior remains prohibited while GitHub `main` is unprotected.

## Current graph

```text
T0  GitHub integration protection (#35) [ADMIN BLOCKED]

T1  Canonical real node PR #91
     exact head 520ad2c9...
     Node CI + Phase 0 PASS
     controlled Docker #37 PASS
                 |
                 v
T2  Independent evaluator/verifier foundation [LANDED]
     #72 verifier
     #81 EvaluatorPlan
     #103 output authority
     #107 metadata-only unified-diff evaluator
                 |
                 v
     PR #108 real node -> verifier evidence [ACTIVE]
                 |
                 v
T3  Multi-attempt + reporting foundation [LANDED]
     #78 two-attempt orchestration
     #88 non-selecting Evidence Report/replay
                 |
                 v
T4  Verified Swarm Runner v0.1 real replayable run (#16)
                 |
                 v
T5  Real-task diversity + verification experiment (#2/#30)
                 |
                 v
T6  Evidence-earned scaling / federation decisions
```

## Current status

| Target | Status | Evidence now | Next gate |
| --- | --- | --- | --- |
| **T0 Protected integration** | **BLOCKED / ADMIN** | `main` remains unprotected; #35 defines the desired external boundary | Configure and verify GitHub ruleset / branch protection |
| **T1 Canonical real worker** | **RUNTIME ACCEPTED / INTEGRATION REVIEW** | PR #91 exact head `520ad2c9aa5825476de4957da4702d6823f4edb3`; Node CI `33185901079` PASS; Phase 0 `33185901058` PASS; controlled Docker run `33186029790` PASS | Independent integration review without changing the accepted worker head |
| **T2 Evaluator/verifier** | **FOUNDATION LANDED; REAL E2E ACTIVE** | #72/#81/#103/#107 merged; #108 binds the accepted real worker to the independent metadata-only verifier | Require a real node bundle -> VerificationResult pass before calling the chain complete |
| **T3 Orchestration/reporting** | **FOUNDATION LANDED** | #78 and #88 merged; both preserve non-selection / human decision authority | Feed real verified node attempts through these landed layers |
| **T4 Verified Swarm Runner v0.1** | **NEXT PRODUCT MILESTONE** | all component contracts exist | One real replayable multi-attempt run ending in pending human decision |
| **T5 Real-task experiment** | **WAITING ON T4** | synthetic/replay research exists | Start with a small 5–10 task real cohort before expansion |
| **T6 Larger-scale mesh** | **EVIDENCE-EARNED** | scheduling/evolution/compute research exists | Promote only mechanisms supported by T5 evidence |

## Evidence from the real worker gate

The controlled Docker gate was useful because it failed before it passed.

An earlier frozen #91 candidate reached Docker and correctly resolved the immutable container identity, but its canonical smoke command failed with a Python `SyntaxError` caused by JSON newline decoding. The defect was fixed using an escape-free command construction, and a regression test now compiles the decoded command before runtime acceptance.

The final accepted exact worker head is:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

For that head:

- Node CI: `33185901079` — PASS;
- Phase 0: `33185901058` — PASS;
- controlled Docker acceptance: `33186029790` — PASS;
- positive result: one `README.md` patch, zero policy violations, matching artifact/log digests;
- fail-closed negatives passed for forbidden tracked path, ignored untracked artifact, Git metadata tampering, patch truncation, absent image, and locally retagged image;
- immutable image ID and matching repository digest were retained;
- worker acceptance authority remained false.

This is exactly the desired project behavior: **failed evidence changed the candidate; the corrected candidate was re-frozen and re-tested rather than redefining success.**

## What is already settled

Do not create competing canonical formats or packages for:

- WorkUnit / ResultManifest;
- EvaluatorPlan;
- VerificationResult;
- two-attempt run records;
- non-selecting Evidence Reports.

The canonical trust relationship is:

```text
WorkUnit             authoritative bounded task/requirements
ResultManifest       untrusted worker claim + artifacts
EvaluatorPlan        verifier-owned exact bound control plane
VerificationResult   independent evidence / recommendation
Evidence Report      non-selecting synthesis
Human decision       integration authority
```

Competing experiments are welcome when they test an explicit hypothesis and preserve interoperability with this chain.

## NOW

### 1. Finish PR #108 real node -> verifier evidence

Use exact accepted worker SHA `520ad2c9...`.

The evaluator must remain outside candidate control and the unified-diff backend must remain metadata-only. Completion evidence is a real worker ResultManifest/candidate patch producing a bound independent VerificationResult while preserving `human_integration_decision_required = true`.

### 2. Review PR #91 for integration

Do not modify the worker merely to chase a moving `main` if GitHub can integrate the accepted head cleanly. A real conflict that changes the worker tree invalidates exact-head runtime evidence and requires re-testing.

Do not treat the successful Docker gate as self-approval.

### 3. Connect the accepted worker behind the landed two-attempt boundary — #16

Run two isolated real attempts from one immutable WorkUnit/revision and preserve worker/verifier support, rejection, and failure independently.

### 4. Exercise the landed non-selecting Evidence Report over that real run — #16

The report must preserve candidate/evaluator/verifier identities and digests, errors/disagreement, resources, and a pending human decision. It must not choose a winner automatically.

### 5. Protect `main` — #35

This remains an administrative safety dependency for stronger autonomous repository behavior. No Markdown rule can substitute for an externally enforced GitHub integration boundary.

## NEXT

After the first complete real v0.1 loop:

- add one trivial heterogeneous second real adapter without vendor branches in coordinator core;
- build a small 5–10 task real benchmark cohort;
- compare baseline, homogeneous replication, controlled diversity, and diversity + independent verification under fixed budgets;
- measure verified success, escaped defects, failure correlation, compute, latency, and human attention;
- expand only if evidence and review capacity support it.

## Parallel, capacity-gated tracks

Community growth, repository observability/IDKGraph, scheduling, evolutionary algorithms, and stigmergic routing remain useful research tracks. They should not displace the real T1–T4 evidence path.

Prefer:

- parent -> seed -> verified-descendant lineage over raw activity;
- proposal-first structural observability over autonomous rewrites;
- measured reviewer capacity over cumulative historical activity;
- one canonical simulator per research surface rather than parallel stacks;
- synthetic results as hypotheses, not proof of real-world swarm quality.

## Task-selection rule

Choose the next repository task in this order:

```text
1. repair a safety / authority / verification invariant;
2. remove a blocker on the real T1–T4 evidence path;
3. converge duplicate implementations or PRs;
4. produce real replayable evidence;
5. reduce reviewer/community friction with measured benefit;
6. reduce repository structural pressure with measured benefit;
7. only then promote new scaling or autonomy mechanisms.
```

Demote work that creates a second canonical path, adds autonomy before protection/verification gates, increases generation without review capacity, duplicates an active branch, or presents synthetic scale as real-system proof.

## Completion rule

A target is complete only when its **observable acceptance evidence** exists.

A merged design document, worker self-test, green fixture, model confidence, or large commit count is not by itself evidence that a real target is satisfied.

Future IDKGraph tooling should derive more of this view automatically from Issues, PRs, WorkUnits, ResultManifests, EvaluatorPlans, VerificationResults, Evidence Reports, CI, and repository state while preserving a human-readable explanation of *why* each target is prioritized.
