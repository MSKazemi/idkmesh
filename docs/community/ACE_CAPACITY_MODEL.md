# ACE Live Carrying-Capacity Model

**Status:** proposed bootstrap model / stacked on ACE hardening PR #98  
**Date:** 2026-08-28

ACE uses the ecological gate:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

The gate is useful only if `L` represents **current recoverable pressure**.

## Problem with cumulative event load

The first ledger implementation updated review load as an event accumulator:

```text
L_(t+1) = max(0, L_t + delta(event))
```

with positive increments for pushes, opened issues, and opened PRs, and smaller negative increments for many completed events.

That creates a structural bias:

```text
completed work can leave residual load
pushes create permanent residual load
historical activity accumulates indefinitely
Capacity(L) -> 0 as project history grows
```

A project could therefore remain in `CONSOLIDATE` even after its actual review queue cleared.

That violates the intended ecological interpretation. Carrying capacity should recover when pressure is removed.

## Live-open-work-v1

Replace cumulative event pressure with a snapshot of open work:

```text
L_t =
    1.00 * P_ready
  + 0.25 * P_draft
  + 0.50 * S_open
  + 0.10 * min(I_open, 20)
```

where:

- `P_ready` = open, non-draft pull requests;
- `P_draft` = open draft pull requests;
- `S_open` = open `growth-seed` issues;
- `I_open` = other open human-facing issues, excluding ACE machine-state issues;
- the other-issue term is capped at 20 so a long research backlog cannot permanently dominate the capacity gate.

This is a **bootstrap heuristic**, not an empirical law.

### Why these weights?

The starting ordering is:

```text
review-ready PR > Growth Seed > draft PR > ordinary open issue
```

A review-ready PR is an immediate integration/review request. A Growth Seed is an actively advertised contribution surface that may create review demand. A draft PR reserves some future attention but explicitly signals that it is not yet ready for full review. A general research/roadmap issue can remain open without continuously consuming equivalent reviewer capacity.

The coefficients `1.00`, `0.50`, `0.25`, `0.10`, the issue cap `20`, and the current `K/tau` remain hypotheses that must be calibrated from evidence.

## Recovery property

The important mathematical property is recoverability:

```text
if current open pressure decreases and all else is equal:
    L_(t+1) <= L_t
    Capacity_(t+1) >= Capacity_t
```

Examples:

```text
ready PR -> draft PR
    reduces immediate review pressure

open PR -> merged/closed
    removes that PR's pressure

open Growth Seed -> completed/closed
    removes seed pressure
```

Historical event counts do not enter `L_t`.

This separates:

```text
event counts -> historical observation / novelty
open work    -> current review pressure
```

## Current empirical preview

GitHub search on 2026-08-28 observed:

```text
21 open review-ready PRs
5 open draft PRs
4 open Growth Seeds
36 open non-PR issues total
```

Using the capped general-issue term, a conservative preview is:

```text
L ~= 21 + 0.25*5 + 0.50*4 + 0.10*20
  = 26.25
```

With current bootstrap parameters:

```text
K = 8
tau = 2
```

this still implies very low capacity.

That is an important result: **the corrected model reaches the same qualitative `CONSOLIDATE` conclusion, but for current observable pressure rather than irreversible historical accumulation.**

The empirical counts will change continuously and are not fixtures for policy. They are evidence that the repository presently has substantial integration/review work outstanding.

## Current capacity parameters

The bootstrap controller uses:

```text
K = 8
tau = 2
```

so:

```text
Capacity(L) = 1 / (1 + exp((L - 8)/2))
```

These remain hypotheses.

A future empirical model should estimate sustainable capacity from signals such as:

- median/p95 first-review latency;
- number of active independent reviewers;
- oldest unreviewed PR age;
- unresolved verification/security blockers;
- reviewer/maintainer minutes where measurable;
- fraction of Growth Seeds receiving timely feedback.

## Machine-state transparency

The Growth Ledger stores components such as:

```json
{
  "review_load": 7.75,
  "review_load_components": {
    "model": "live-open-work-v1",
    "ready_pull_requests": 4,
    "draft_pull_requests": 1,
    "open_growth_seeds": 3,
    "other_open_issues": 20,
    "other_open_issues_capped_at": 20
  }
}
```

This makes the capacity result inspectable rather than hiding it behind one scalar.

## Safety interaction

This change does **not** weaken the external protection gate.

Even if the live review queue is healthy:

```text
mainProtected == false
```

still forces ACE to `CONSOLIDATE` and disables reproductive actuation in the converged safety workflow.

Capacity is one gate. Protected integration is another independent gate.

## Anti-Goodhart rule

Do not optimize the repository to reduce `L` artificially by closing useful issues/PRs prematurely or marking review-ready work as draft without cause.

The desired system property is:

> reduce real coordination/review burden while preserving verified useful progress.

Therefore `L` must be interpreted together with verified throughput, latency, descendant evidence, and project risk.
