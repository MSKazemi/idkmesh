# GitHub Reflex Self-Evolution Engine

**Date:** 2026-08-28  
**Status:** architecture + executable P0 policy

## Core idea

Treat GitHub as the first **reflex arc** of IDKMesh:

```text
GitHub state/events
      |
      v
Observation graph
      |
      v
Deterministic health + evidence extraction
      |
      v
Opportunity / anomaly detection
      |
      v
Bounded candidate rewrite/action rules
      |
      v
Risk + capacity + independent-evidence gates
      |
      +--> observe/report
      +--> recommend
      +--> propose issue/PR (later)
      +--> deterministic auto-merge (much later, only behind external guards)
      |
      v
Outcome measurement -> policy learning
```

This complements `SELF_EVOLVING_REPOSITORY.md`. The existing document defines repository-level graph evolution; this one defines how GitHub's collaboration substrate feeds and constrains that loop.

## State model

At epoch `t`, define GitHub state:

`X_t = (A_t, W_t, D_t, V_t, S_t, G_t)`

where:

- `A_t` = artifact state: commits, branches, PRs, files, releases;
- `W_t` = work state: issues, labels, milestones, dependencies;
- `D_t` = deliberation state: comments, discussions, reactions;
- `V_t` = verification state: reviews, checks, workflows, security alerts;
- `S_t` = social/community state: participants, forks, stars, contribution paths;
- `G_t` = governance/guard state: CODEOWNERS, rulesets, branch protection, permissions, accepted decisions.

The self-evolution system estimates a repository-health vector from `X_t`, then chooses only actions permitted by `G_t`.

## Observation graph

Represent GitHub state as a typed temporal graph.

### Node types

- repository;
- file/artifact;
- commit;
- branch/tag/release;
- issue/work unit;
- pull request/change proposal;
- comment;
- review;
- workflow/check/security result;
- contributor/agent identity;
- label/milestone/project item;
- decision/IDKIP/ADR;
- evolution candidate.

### Edge types

- authored_by;
- comments_on;
- reviews;
- reacts_to;
- mentions;
- closes;
- blocks / blocked_by;
- implements;
- touches;
- verifies / falsifies;
- supersedes;
- spawned_from;
- depends_on;
- governed_by;
- resulted_in.

All text-bearing nodes are untrusted input. The graph stores them; it does not grant them authority.

## Evidence hierarchy

Use GitHub signals differently depending on what they can establish.

### Weak discovery signals

- stars;
- forks;
- reactions;
- raw comment volume;
- raw commit count.

These can influence **where to look**, not what is true.

### Medium coordination signals

- distinct participant count;
- issue dependency structure;
- labels/milestones;
- repeated independently authored reports;
- reviewer requests;
- unresolved discussion longevity.

### Strong verification signals

- reproducible test result;
- independent PR review with concrete evidence;
- passing/failing required check;
- benchmark/reproduction artifact;
- security scanner result;
- verified ResultManifest / evidence bundle.

Popularity cannot substitute for strong verification.

## Review-capacity homeostasis

Reuse ACE's idea that growth should slow when verification becomes saturated.

For P0:

`load = open_PRs + 0.75 * PRs_without_review`

`capacity = 1 / (1 + exp((load - K)/tau))`

with initial hypotheses `K=8`, `tau=2`.

As review load rises, self-evolution proposal generation is throttled. This prevents an agent swarm from overwhelming the scarce verification bottleneck.

## Opportunity scoring

Each candidate has a vector:

`z(a) = (benefit, confidence, novelty, capacity, cost, risk)`.

A provisional ranking scalar is:

`Score(a) = benefit * confidence * novelty * capacity / (1 + cost + 2*risk_cost)`.

This scalar is only for ordering candidates. Hard invariants and Pareto trade-offs have priority.

Initial risk costs:

- low: `0.15`;
- medium: `0.50`;
- high: `1.00`;
- constitutional: `2.00`.

Examples of benefit components:

- correctness/security impact;
- expected information gain;
- dependency unlock value;
- reduction of review backlog;
- newcomer accessibility;
- documentation consistency;
- verification coverage.

### Novelty

Repeated identical activity should have diminishing returns.

A simple factor is:

`novelty = 1 / sqrt(1 + repeated_count)`.

Later replace this with correlation-aware source clustering so 20 correlated agents do not look like 20 independent observations.

## Deterministic P0 candidate rules

### `GuardAutonomy`

Trigger when:

- default branch is unprotected; or
- no repository ruleset exists.

Effect:

- cap recommended autonomy at **Level 1 — Recommend**;
- emit a constitutional-risk recommendation to establish external merge guards;
- never mutate protection settings automatically.

### `RequestIndependentReview`

Trigger when:

- PR is open long enough;
- no submitted review exists.

Effect:

- recommend review routing;
- future bounded actuator may request a reviewer, but must avoid self-review.

### `SynthesizeDiscussion`

Trigger when:

- issue is open;
- enough comments exist;
- comments include at least two distinct authors.

Effect:

- recommend a structured synthesis of claims, evidence, disagreement, and unresolved questions;
- do not infer correctness from majority opinion.

### `TriageStaleWork`

Trigger when:

- issue has aged substantially with no discussion.

Effect:

- recommend clarification, decomposition, dependency linking, or human closure review;
- never auto-close in P0.

### `RepairVerification`

Trigger when:

- recent workflow/check failures exist.

Effect:

- elevate verification repair ahead of additional generation.

## Comment-to-evidence transformation

For each comment/review `c`, preserve:

`E_c = (source, actor, actor_association, parent, timestamp, body_hash, body, reactions, links, type)`.

Set `untrusted_text=true`.

A later semantic classifier may derive:

- claim;
- question;
- evidence pointer;
- reproduction report;
- disagreement;
- decision proposal;
- blocker;
- progress update.

The classifier output is a **derived node with confidence**, while the original GitHub object remains immutable evidence/provenance.

### Independence score

For a claim cluster, estimate independent support using distinct actors, independent artifacts, and distinct verification methods rather than comment count.

A future approximation:

`IndependentSupport = sum_j w_method(j) * (1 - correlation_j)`.

Do not use contributor reputation alone as truth weight. Reputation may help route reviewers but cannot override evidence.

## Autonomy gates

The engine computes an autonomy ceiling from external repository guards.

Current provisional rule:

```text
if default_branch_unprotected OR rulesets == 0:
    ceiling = 1  # recommend only
else:
    ceiling = 2  # bounded PR proposals may be considered
```

Levels:

- 0 — observe;
- 1 — recommend;
- 2 — propose issue/PR;
- 3 — deterministic auto-merge;
- 4 — guarded structural evolution;
- 5 — policy evolution.

The P0 observatory itself always runs at Level 0 regardless of the ceiling.

## Actuator matrix

| Action | Risk class | Earliest autonomy | Required evidence |
| --- | --- | ---: | --- |
| produce report/artifact | low | 0 | deterministic collector |
| recommend issue/PR review | low | 1 | GitHub state |
| open bounded triage issue | low | 2 | deduplication + rate limit |
| request reviewer | low/medium | 2 | independent-review rule |
| open docs/index PR | low | 2 | deterministic diff + checks |
| modify code | medium/high | 2 | separate worker + verifier |
| auto-merge generated index | low | 3 | external ruleset + required checks |
| close issue automatically | medium | 3+ | explicit policy + appeal/reopen path |
| change architecture/protocol | high | 4 | IDKIP/ADR + independent review |
| change governance/security | constitutional | 5 | explicit human governance approval |
| weaken tests/rulesets | constitutional | never self-authorized | external approval only |

## Learning which reflexes are useful

Do not optimize rule firing count. Record each proposal's outcome:

`O = (rule, context, predicted_delta, accepted?, reviewer_effort, actual_health_delta, regressions, revert?)`.

After enough observations, allocate experiment budget among safe rule variants using a contextual multi-armed bandit or Thompson sampling.

Reward should approximate:

`verified_useful_improvement - reviewer_burden - regression_cost - coordination_cost`.

A rule that creates many accepted-looking PRs but increases maintainer work should lose budget.

## Relationship to ACE

ACE and the Reflex Engine solve different control problems:

- **ACE:** community reproduction / attention / review-capacity dynamics;
- **Reflex Engine:** repository state, evidence, verification, and bounded self-maintenance.

They share:

- novelty decay;
- capacity throttling;
- events as signals rather than goals;
- public provenance;
- conservative actuators.

Future versions should consume one shared event ledger rather than duplicate API collection.

## Relationship to Issue #20 repository observatory

Issue #20 focuses primarily on the **repository/document/task graph**: files, headings, links, decisions, WorkUnits, and deterministic structural defects.

The GitHub Reflex Observatory focuses on the **collaboration/control graph**: issues, PRs, comments, reviews, workflows, protection, releases, and security state.

The combined P1 state is:

`IDKGraph = RepositoryGraph union GitHubCollaborationGraph union EvidenceGraph`.

That union gives the self-evolution loop both structural and social/verification context.

## P0 implementation

`tools/github_observatory.py`:

- read-only GitHub REST collection;
- standard-library Python, no extra dependency;
- collects issue/PR bodies and comments as untrusted public evidence;
- collects PR reviews and inline review comments;
- collects workflows/recent runs, releases, branches, contributors;
- best-effort security-alert collection;
- computes review capacity and deterministic evolution candidates;
- emits JSON + Markdown.

`.github/workflows/github-reflex-observatory.yml`:

- runs on a schedule and collaboration events;
- always checks out the **default branch**, never PR head code under `pull_request_target`;
- uses read-only GitHub permissions;
- uploads an observation artifact;
- writes the report to the Actions job summary;
- performs no repository mutation.

## Next safe steps

1. Merge/review the P0 observatory.
2. Connect its GitHub graph to Issue #20's structural repository graph.
3. Add deterministic deduplication and stable event IDs.
4. Add incremental webhook ingestion when full snapshots become expensive.
5. Add a proposal-only workflow that can create **one bounded issue/PR** per epoch, with rate limits.
6. Configure external repository rulesets before allowing Level 2+ autonomy.
7. Measure whether recommendations actually reduce reviewer/maintainer effort.
