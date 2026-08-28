# Conversation Record — ACE Live Capacity Recovery

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner asked IDKMesh to continue evolving so GitHub activity improves the system/community through explicit algorithms rather than raw activity amplification.

## Empirical trigger

During the continuation, the live ACE Growth Ledger (#23) was inspected.

It reported approximately:

```text
mode = CONSOLIDATE
review_load = 45.55
capacity = 0.000
observed raw events = 173
```

The Bootstrap Cohort issues #24–#28 were also inspected and remained predominantly repository-owner driven. This correctly argued against spawning Cohort 2 from raw activity alone.

However, the ledger exposed a deeper model defect.

## Defect: review load was historical accumulation

The original workflow updated load as:

```text
L_(t+1) = max(0, L_t + delta(event))
```

with positive deltas for pushes, issue opens, and PR opens, while many closes/merges removed less load than their corresponding opens added.

Consequences:

- a completed PR could leave residual load;
- a completed issue could leave residual load;
- every push added permanent load;
- historical activity drove `L` upward even if current queues recovered;
- eventually `Capacity(L)` tended toward zero by construction.

That means the carrying-capacity gate was partly measuring project age/activity history rather than current review pressure.

This violates the intended biological/homeostatic interpretation: when stressors disappear, the system should be able to recover.

## Architectural decision

Keep historical event counts for:

- observation;
- novelty/diminishing returns;
- experiment telemetry.

But compute carrying-capacity pressure from **current open work**.

A stacked branch/PR is used rather than silently expanding the security convergence PR #98.

## Live-open-work-v1

Proposed bootstrap pressure:

```text
L_t =
    1.00 * P_open
  + 0.50 * S_open
  + 0.10 * min(I_open, 20)
```

where:

- `P_open` = open pull requests;
- `S_open` = open `growth-seed` issues;
- `I_open` = other open human-facing issues, excluding ACE machine-state issues.

The exact weights are hypotheses. The important structural property is **recoverability**:

```text
open work decreases
    -> L decreases
    -> Capacity(L) increases
```

Historical event count is no longer an input to `L`.

## Workflow change

`.github/workflows/ace-community-growth.yml` now recomputes live pressure on every observed event.

It records transparent components in `ACE_STATE`:

```json
{
  "review_load_components": {
    "model": "live-open-work-v1",
    "open_pull_requests": 4,
    "open_growth_seeds": 3,
    "other_open_issues": 20,
    "other_open_issues_capped_at": 20
  }
}
```

The ledger also separates:

```text
historical event counts != current review load
```

## Safety independence

This capacity correction does not override protected integration.

Even with healthy capacity:

```text
mainProtected == false
```

still forces `CONSOLIDATE` and disables ACE reproductive actuation under the #98 safety model.

This preserves independent gates:

```text
healthy capacity
AND protected main
AND verified lineage/evidence
AND accepted controller/security layers
```

before any future Phase-B action.

## Documentation and tests

Added:

- `docs/community/ACE_CAPACITY_MODEL.md`;
- `tests/test_ace_live_capacity_model.py`.

Extended:

- `.github/workflows/ace-workflow-hardening-check.yml`.

Tests assert:

- the workflow uses the live-open-work model;
- cumulative `loadDelta` is removed;
- machine state exposes load components;
- closing open work increases capacity;
- historical event count cannot change load at fixed current-open-work state;
- ordinary-issue backlog contribution is bounded;
- open PR pressure > Growth Seed pressure > general issue pressure.

## Scientific status

`1.00 / 0.50 / 0.10`, cap `20`, `K=8`, and `tau=2` are bootstrap hypotheses, not measured truths.

A future calibration should use real:

- review latency;
- reviewer count;
- oldest pending PR age;
- verification/security blockers;
- reviewer/maintainer minutes;
- Growth Seed response latency.

## Anti-Goodhart warning

Do not optimize the model by closing legitimate issues or PRs prematurely.

The objective is not minimum open-work count. It is:

> lower real coordination/review burden while preserving verified useful progress.

Capacity must therefore be interpreted together with verified throughput, risk, latency, and descendant evidence.
