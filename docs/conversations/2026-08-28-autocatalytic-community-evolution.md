# Conversation Record — Autocatalytic Community Evolution

**Date:** 2026-08-28  
**Project:** IDKMesh  
**Topic:** Can repository activity itself create more useful community participation with low maintainer effort?

## Prompt / motivation

The project asked whether IDKMesh can become self-evolving and self-growing in community terms: each commit, issue, pull request, push, review, or other GitHub activity should ideally increase the probability of future useful contributions instead of requiring continuous manual social-media promotion.

The requested inspiration included biology, economics, political science, physics, and other distributed/adaptive systems.

## Main conclusion

A repository should not optimize raw activity. It should optimize **verified community reproduction**:

> A useful contribution should leave behind clearer knowledge, lower friction, and one or more bounded opportunities that make the next useful contribution easier.

This became **ACE — Autocatalytic Community Evolution**.

## Core model

The principal community reproduction metric is:

```text
R_community(W) = verified descendant contributions / verified parent contributions
```

The aim is to achieve sustainable reproduction above one while constraining growth by verification/review capacity.

A useful high-level loop is:

```text
GitHub activity
  -> structured event evidence
  -> quality / novelty / capacity gate
  -> reproductive credit
  -> bounded Growth Seed
  -> contributor/reviewer/reproducer
  -> verification
  -> measured descendant
  -> adapt future strategy
```

## Scientific inspirations incorporated

- **branching processes:** useful contributions can have descendants;
- **ecological carrying capacity:** growth must slow when review capacity is saturated;
- **evolutionary/replicator dynamics:** strategies producing durable verified descendants receive more future allocation;
- **mutation/exploration:** retain a non-zero probability for new growth strategies;
- **stigmergy:** public repository traces coordinate contributors without a central dispatcher;
- **economics:** optimize marginal verified value per unit of scarce reviewer/maintainer attention;
- **polycentric governance:** local autonomy plus shared safety/verification constraints;
- **psychology:** reduce friction while preserving contributor autonomy and meaningful competence growth;
- **information theory:** prioritize tasks with high information gain and downstream unlock value;
- **control theory:** use backpressure instead of allowing generation to outrun review.

## Anti-Goodhart decision

ACE must not directly optimize stars, forks, comments, commit count, issue count, PR count, reactions, or impressions. These can be signals, but popularity is not proof and activity is not verified value.

A more meaningful objective is approximately:

```text
verified useful descendants
--------------------------------------------
reviewer time + maintainer time + compute
```

## GitHub-native v0 implemented

The repository now contains:

- `COMMUNITY_GROWTH_ENGINE.md` — ACE design and equations;
- `.github/workflows/ace-community-growth.yml` — event-driven Growth Ledger workflow;
- issue #23 — public ACE Growth Ledger;
- `docs/community/ACE_BOOTSTRAP_EXPERIMENT.md` — first controlled community-reproduction experiment.

The workflow uses metadata-only `pull_request_target` handling for pull-request events and must not check out or execute untrusted PR code.

## Bootstrap cohort

Five bounded Growth Seeds were created as Cohort 1:

- #24 — audit the 15-minute newcomer path;
- #25 — define ACE parent-to-descendant evidence links;
- #26 — threat-model the ACE GitHub workflow;
- #27 — build a tiny ACE population simulator;
- #28 — decompose one research track into five claimable microtasks.

They intentionally cover multiple niches: documentation/community, measurement, security, coding/modeling, and research/coordination.

All use GitHub's `good first issue` and `help wanted` labels.

## Capacity decision

Do not immediately generate dozens more issues.

Cohort 2 should be gated by evidence from Cohort 1 plus healthy review capacity. This is the first application of ACE's ecological/control-theoretic backpressure principle.

## Next research questions

1. What counts as a verified parent/descendant link strongly enough to estimate `R_community`?
2. Which Growth Seed types convert first-time contributors into repeat contributors?
3. How should reviewer/maintainer attention be measured without invasive individual surveillance?
4. When should ACE switch between `DORMANT`, `EXPLORE`, `GROW`, and `CONSOLIDATE`?
5. Can strategy allocation be learned from outcomes using replicator-mutator dynamics or contextual bandits?
6. Can the ACE mechanism eventually be generalized into a reusable GitHub Action for other open-source communities?

## Principle preserved

The repository is the canonical public project record. This conversation was distilled into design, implementation, issues, an experiment, and this conversation record rather than kept only in private chat context.
