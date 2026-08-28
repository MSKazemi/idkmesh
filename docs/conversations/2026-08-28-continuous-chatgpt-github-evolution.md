# Conversation record: continuous GitHub + ChatGPT repository evolution

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Prompt / goal

Explore whether IDKMesh can use the capabilities of GitHub plus ChatGPT's connected GitHub access/scheduled work to continuously inspect the repository, identify the next useful issue, let another agent/human solve it, and use each iteration to improve both the repository and the size/independence of its community.

The desired behavior is not merely self-modifying code. The repository should create better conditions for the next useful contribution and gradually require less manual community manufacturing by the bootstrap maintainer.

## Key clarification

GitHub Actions can be always-on/event-driven repository infrastructure, but they cannot implicitly create or invoke this exact ChatGPT web conversation. ChatGPT is a separate control plane.

As of this conversation, OpenAI documents that ChatGPT scheduled tasks can run recurring work and can use supported connected apps such as GitHub where available. That makes a useful two-plane design possible:

1. **GitHub reflex plane** — deterministic, event-driven, metadata-only observation and bounded issue creation.
2. **ChatGPT cognitive plane** — recurring scheduled inspection of the ONE queue and implementation/analysis of one bounded task per run.

The repository must remain functional when the ChatGPT plane is unavailable.

## Decision

Introduce **ONE — One Next Evolution**.

The controller asks:

> Given the repository state right now, what is the single highest-value bounded action that improves verified capability, community reproduction, or the repository's ability to improve itself?

The v0 controller uses an explicit carrying-capacity gate and permits at most one active generated task.

## Iteration definition

An iteration is an evolution epoch, not a commit/event:

```text
observe
 -> state
 -> candidate actions
 -> capacity/risk gate
 -> select one bounded action
 -> public task
 -> human/agent execution
 -> independent evidence/review
 -> integrate/reject
 -> measure outcome and descendants
 -> next epoch
```

## Community-growth thesis

The fastest sustainable growth should come from improving the contribution funnel and reproduction coefficient:

```text
visitor
 -> understands
 -> finds bounded work
 -> contributes
 -> receives review
 -> returns
 -> enables another contributor
```

The algorithm should therefore optimize useful descendants per reviewer/maintainer attention rather than stars, comments, issue count, or commit volume.

High-leverage mechanisms include:

- each verified contribution leaving a reproduce/challenge/explain/extend surface;
- 15–60 minute newcomer tasks with observable acceptance criteria;
- public reproducible experiments/results that are worth discovering and sharing;
- role diversity beyond coding;
- independent ownership and reviewer creation;
- aggressive backpressure when review load grows;
- replication of issue/task patterns that empirically produce verified descendants.

Explicitly rejected tactics include fake engagement, fake accounts, automated star manipulation, mass unsolicited mentions, misleading claims, and issue/comment spam.

## Implementation created

- `docs/architecture/ONE_CONTINUOUS_EVOLUTION_CONTROLLER.md`
- `.github/workflows/one-continuous-evolution.yml`

The workflow maintains one `[ONE] Continuous Evolution Queue` and, when capacity and duplication gates permit, creates at most one `one:agent-task` issue.

It is metadata-only and does not check out or execute PR-head content.

## ChatGPT recurring-worker instruction

The companion recurring task should:

```text
Inspect MSKazemi/idkmesh through the connected GitHub app. Read the ONE queue,
CURRENT_PRIORITIES, the repository improvement loop, and open ONE agent tasks.
If one ONE task is open, advance the highest-priority bounded task with an
inspectable GitHub artifact (branch/PR/test/research/review evidence) when safe.
Do not merge or approve your own changes. Do not create duplicate work. If the
repository is review-saturated, prefer verification/consolidation. If no ONE task
exists, inspect the repository and propose at most one high-value bounded issue
only when it passes the capacity and duplication gates. Record community impact
and evidence. Stop after one bounded outcome.
```

## Actual activation in this conversation

The implementation was published as **PR #64 — Add ONE continuous GitHub + ChatGPT evolution controller**.

A recurring ChatGPT task named **IDKMesh ONE Worker** was also enabled at an hourly cadence (the maximum cadence supported by the scheduled-task path in this environment). Its prompt follows the bounded-worker instruction above: inspect the connected GitHub repository, prefer an existing `one:agent-task`, produce at most one inspectable outcome, avoid duplicate work, and never self-approve/self-merge.

The repository-side ONE workflow becomes active only after the PR is reviewed and merged. The ChatGPT worker can meanwhile inspect the repository and existing priority surfaces, but it should not pretend that an unmerged workflow already exists on `main`.

## Research questions created by the design

1. Does one-task-at-a-time automation produce more verified useful descendants per reviewer minute than a larger autonomous issue fan-out?
2. Which GitHub-visible signals best predict reviewer carrying capacity?
3. Which task archetypes produce the highest first-contribution -> second-contribution conversion?
4. When is it safe to increase the generated-task branching factor from 1 to 2 or more?
5. Can a scheduled ChatGPT worker reduce maintainer bottlenecks without creating correlated low-quality output?
6. Which public evidence artifacts create durable discovery/community growth rather than transient attention?
7. Can contributor/reviewer ownership become less centralized as ONE iterates?

## Success condition

ONE is successful only if future measurements show that it increases independently verified useful work and useful community descendants while keeping review latency, coordination noise, security risk, and maintainer concentration bounded.
