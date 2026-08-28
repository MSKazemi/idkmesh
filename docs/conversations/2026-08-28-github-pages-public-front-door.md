# Conversation Record — GitHub Pages Public Front Door

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`  
**Context:** continuation after IDKGraph P1 cohort work.

## Project-owner direction

Continue developing IDKMesh and preserve useful output in the public repository.

## Live-state observation

At this continuation point, the repository had advanced rapidly on technical experiments, including new verifier/quorum research, while the ACE Bootstrap Cohort Observatory still reported:

- zero distinct external participants;
- zero claimed Bootstrap Cohort seeds;
- zero candidate community PRs.

Issue #173 already identified GitHub-native discoverability as a P0 bottleneck and listed repository-admin actions such as description/topics/Discussions/Pages activation.

## Decision

Do not create another internal simulator merely because implementation capacity is available.

Use the available repository-write surface to prepare the part of #173 that can be completed safely without repository-admin settings: a dependency-free GitHub Pages public front door under `docs/`.

## Implemented artifacts

- `docs/index.html` — one-page public landing source;
- `docs/PAGES_SETUP.md` — explicit owner/admin activation and post-activation verification procedure.

The page intentionally:

- uses no JavaScript or external dependencies;
- does not introduce analytics/trackers;
- states that IDKMesh is a research preview, not production software;
- emphasizes bounded work, independent verification, evidence, and explicit integration decisions;
- points to live contribution/review surfaces instead of claiming external adoption;
- keeps the repository as the canonical source of truth rather than creating a second documentation system.

## Highlighted first-contact paths at implementation time

- #24 — newcomer-path audit;
- #167 — independent review of the first IDKGraph orphan-warning cohort;
- #138 — expert independent review of canonical-node runtime evidence.

These links must be maintained as live bounded paths; the landing page should not accumulate stale historical tasks.

## Activation boundary

Actual GitHub Pages enablement, repository homepage configuration, description/topics, and Discussions remain repository-owner/admin settings and are not claimed as completed by this repository change.

## Measurement principle

The page should not be optimized for page views, stars, or raw activity.

The useful first-contact funnel is:

```text
discover
 -> understand
 -> choose bounded work
 -> leave inspectable claim/question/contribution
 -> receive verification/review
```

The first meaningful external-growth event is one genuinely external participant reaching a bounded project surface and leaving inspectable evidence of engagement.

## Community impact

This reduces the amount of repository context a newcomer must absorb before finding useful work, while keeping all deeper technical evidence and governance in canonical GitHub artifacts.
