# Conversation record — evolution report review and top priorities

**Date:** 2026-09-02  
**Repository:** `MSKazemi/idkmesh`  
**Scope:** review of the evolution report against current canonical strategy, roadmap, live issue state, and repository protection/evidence status.

## Project owner request

The project owner asked for a review of the entire report, an opinion on its quality and purpose, the ten most important things to do next, permission to create issues where useful, and a clear statement of the report's target.

## Executive assessment

IDKMesh has a stronger implementation and evidence foundation than [`EVOLUTION_REPORT.md`](../../EVOLUTION_REPORT.md) currently communicates. The core project discipline is sound: bounded work, independent verification, explicit authority separation, reproducibility, and an insistence that synthetic mechanisms are not scientific proof.

The immediate project risk is no longer lack of concepts. It is **convergence debt**: architecture, experiments, control mechanisms, documentation, and historical tracker text can accumulate faster than real observed evidence, independent human review, and a newcomer-usable product path.

The next phase should therefore optimize for:

> **convergence + observed evidence + independent review + reproducible use**

rather than new foundational vocabulary, new protocols, larger autonomy, or premature scale.

## What the report should target

The report should be a **decision instrument**, not merely a description of the evolution philosophy.

Its primary operational question should be:

> **What is the weakest evidence-backed bottleneck in IDKMesh now, what bounded intervention is justified, and what evidence would allow the project to retain, reject, or revise it?**

For each reporting cycle it should make the following chain inspectable:

```text
current baseline
 -> weakest important deficiency / uncertainty
 -> bounded intervention or deliberate no-op
 -> exact evidence and provenance
 -> independent verification/review
 -> observed outcome
 -> explicit retain/reject/revise decision
 -> next bounded question
```

The intended audience is maintainers, contributors, independent reviewers, and researchers deciding what to work on next.

This is narrower than the project's ultimate research target. IDKMesh itself aims to determine whether humans, AI agents, tools, and heterogeneous compute can coordinate on uncertain goals to produce more **verified useful work per unit of scarce human attention, compute/resource cost, and risk** than weaker baselines.

The near-term product target is the Git-native **Verified Swarm Runner**: one bounded task should flow through replaceable workers, canonical result evidence, independent verification, non-selecting reporting/replay, and an explicit human/governance integration decision.

## Concrete report defects found

### 1. Broken report navigation

`EVOLUTION_REPORT.md` points readers to an `evolution/` directory as the location of working materials. That directory does not exist on current `main`.

This is not only cosmetic. The report currently promises a starter snapshot, loop, and backlog at a location a reader cannot open.

Tracked in #373.

### 2. The report describes a loop but does not report current state

The file explains the desired evolution loop, but it does not currently contain a source revision, current checkpoint, active evidence gates, current measured signals, current bottleneck, or the exact next decision.

That makes the name “report” stronger than the artifact's present function. It is closer to a doctrine/index today.

### 3. Canonical strategy can lag live tracker state

The roadmap still references issue #15 as the open empirical WorkUnit boundary and refers to #17 as an interoperability gate, while both issues are currently closed. Historical issue bodies can also retain unchecked items after the repository has moved on.

The report should not copy tracker text blindly. It should resolve the current state of any linked issue/PR before presenting it as an active gate.

### 4. Repository protection is now current evidence, not a future aspiration

Live `main` branch metadata checked during this review reported:

```text
protected = true
required checks = gate (3.11), gate (3.13)
```

This is consistent with the README's current-status statement. Historical issue text that says `main` is unprotected should remain history rather than being promoted into current reporting.

## Ten most important next actions

### 1. Make the evolution report auditable and current

**Tracking:** #373

Replace the broken `evolution/` pointer and make the report a concise current-state synthesis. It should name the current source revision/date, active gates, evidence levels, current bottleneck, and next bounded decision. It must remain an index/synthesis rather than becoming another evolution controller.

### 2. Finish the newcomer-usable Verified Swarm Runner v0.1 loop

**Tracking:** #16 and #4

Converge existing mechanisms into one understandable local flow instead of adding another orchestration layer. The acceptance target is a newcomer who can run a bounded task, see multiple isolated outcomes, inspect canonical evidence and independent verification, replay the run, and understand that merge/integration remains external authority.

### 3. Obtain genuine independent review for the canonical real worker boundary

**Tracking:** #138 and the canonical worker integration path

Automation, CI, and the worker itself must not manufacture the independent witness the architecture requires. This is a real governance/evidence bottleneck, not a missing test fixture. If the exact candidate changes, rebind evidence rather than inheriting approval from stale ancestry.

### 4. Prove worker interchangeability with two materially different adapters

**Tracking:** #4, #16; related future resource work in #11

Put the direct canonical worker behind the existing coordinator-facing adapter boundary, then add one small heterogeneous adapter without changing coordinator core. Measure semantic equivalence, provenance quality, adapter-specific failures, and reviewer cost.

The important claim is not “many workers exist”; it is that worker implementations can be replaced while preserving IDKMesh semantics and trust boundaries.

### 5. Collect and publish the first held-out real coding corpus

**Tracking:** #70; enables #30 and contributes to #13

This is one of the largest scientific gaps. The repository has extensive synthetic/mechanism validation, but the major multi-agent claims need real bounded work, equal attempt budgets, independent verification, retained failed candidates, and frozen analysis rules.

A negative result is valuable. The experiment must be able to conclude that diversity or multi-agent execution does not help on the measured task classes.

### 6. Execute controlled comparative collective-intelligence experiments on real work

**Tracking:** #2, #13, #30, #70 and related benchmark work

Use real tasks and matched budgets to compare strong single workers, replication, heterogeneous workers, specialized roles, and decomposition strategies. Preserve hidden evaluation, human-review minutes, regressions, resource use, error correlation, and integration cost.

Do not reopen old schema work merely because an older roadmap sentence names it. The question is now empirical performance and boundary conditions.

### 7. Ship the first reproducible public Verified Swarm Runner release

**Tracking:** #374

Package the existing foundation into a small install/run/inspect/replay experience with exact contract versions, one canonical example, saved evidence, replay instructions, security boundaries, known limitations, and a clean-environment reproduction procedure.

This is the bridge between “research repository with working pieces” and “reference product outsiders can actually test.”

### 8. Increase real independent reviewer and recurring-contributor capacity

**Tracking:** #9, #10, #109, #167, #151

The project should optimize for verified external participation rather than issue/PR volume. The ACE bootstrap observer checked during this review still reported zero claimed seeds, zero candidate PRs, zero verified descendants, and zero distinct external participants for the original cohort.

The immediate social target is therefore not a larger cohort. It is getting a small number of real external people to complete bounded work or independent review, measuring their friction and reviewer minutes, and improving the path based on observed behavior.

### 9. Calibrate the mathematical/evolution control plane against real outcomes

**Tracking:** #86 and #151

Continue replacing hand-authored or weakly grounded priors with observables only when the new metric predicts something decision-relevant. Prioritize human attention, review latency/concentration, recurrence, worker/verifier error correlation, and uncertainty.

A mathematically elegant score is not progress unless it survives falsification, helps allocate scarce attention, and remains subordinate to hard safety/authority gates.

### 10. Earn the first bounded multi-machine/volunteer experiment only after local convergence

**Tracking:** #1, #11, #12; roadmap R5

After the local runner and release are coherent and real-work evidence exists, run a small 3–10 machine/resource experiment. Measure churn, retries, stragglers, heterogeneous environments, artifact transfer, coordinator recovery, isolation, provenance, verification cost, and human governance load.

Do not jump from simulations and GitHub workflows to Internet-scale claims. Scale should be earned one evidence gate at a time.

## Issues created by this review

Two new issues were created because the gaps were not already cleanly represented by current open work:

- #373 — **Evolution report: make current state, evidence, and gates auditable**
- #374 — **Release gate: ship the first reproducible Verified Swarm Runner package**

The remaining priorities deliberately reuse existing issues rather than increasing tracker volume with duplicates.

## Recommended sequencing

The critical sequence is approximately:

```text
report/current-truth repair (#373)
        +
independent worker review (#138)
        |
        v
finish local runner + two adapters (#4/#16)
        |
        +--> reproducible release (#374)
        |
        v
real held-out corpus (#70)
        |
        v
comparative real experiments (#30/#13/#2)
        |
        +--> measured contributor/reviewer capacity (#9/#10)
        |
        v
small multi-machine / volunteer experiment (#1/#11/#12)
```

Some work can run in parallel, especially independent review, report repair, contributor onboarding, and real-corpus preparation. The dependency rule is that downstream claims must not outrun their evidence gates.

## Bottom line

The project does **not** currently need a larger vision. The vision is already broad enough.

It needs a narrower proof surface:

> **one coherent product loop, independently reviewed; one reproducible release; one real held-out corpus; a few real external participants; and decisions that change only when observed evidence justifies them.**

If IDKMesh can repeatedly turn those into verified useful work while keeping reviewer attention, cost, risk, and authority boundaries inspectable, the larger scaling and collective-intelligence research program becomes substantially more credible.

## Durable links

- [`EVOLUTION_REPORT.md`](../../EVOLUTION_REPORT.md)
- [`EVOLUTION.md`](../../EVOLUTION.md)
- [`ROADMAP.md`](../../ROADMAP.md)
- [`ITERATION_MODEL.md`](../../ITERATION_MODEL.md)
- [`README.md`](../../README.md)
- #373 — report-current-state gate
- #374 — reproducible-release gate
