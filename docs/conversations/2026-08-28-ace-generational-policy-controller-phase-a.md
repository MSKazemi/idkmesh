# Conversation Record — ACE Generational Policy Controller Phase A

**Date:** 2026-08-28

## Project-owner direction

The project owner asked IDKMesh work to continue after the repository gained:

- an ACE community reproduction/growth model;
- a constraint-aware generational evolution design;
- a Bootstrap Cohort observer proposal;
- a parent -> seed -> descendant lineage proposal;
- a population/review-capacity simulator proposal;
- Issue #57 defining the next evidence-gated generational policy controller.

The standing project rule requires substantive IDKMesh chat outputs and implementation work to be preserved in the public repository.

## Repository state observed

Several ACE-related changes are intentionally concurrent and reviewable rather than directly merged by the proposing assistant:

- PR #40 — evidence-gated Bootstrap Cohort observability;
- PR #44 — deterministic ACE population simulator;
- PR #48 — parent -> seed -> descendant lineage evidence;
- Issue #26 — ACE workflow threat model;
- Issue #57 — generational policy controller.

PR #48 had also been reconciled to remove its overlapping population-simulator portion, leaving PR #44 as the bounded implementation of Growth Seed #27. This made it important not to recreate or combine those surfaces again.

## Decision

Implement **Phase A of Issue #57 only** as an offline deterministic policy controller.

Do not add a GitHub actuator.

The implementation is isolated in branch:

`ace-generational-controller-phase-a`

## Mathematical policy

The initial strategy set is:

```text
reproduce
challenge
extend
explain
review
onboard
consolidate
```

Only explicitly verified descendants contribute positive value to strategy fitness:

```text
f_i = verified_value_i / (1 + reviewer_minutes_i + maintainer_minutes_i)
      - lambda_latency * added_review_latency_i
      - lambda_noise * public_writes_i
```

Then use a replicator-mutator update:

```text
w_i* = w_i * exp(eta * (f_i - mean_fitness))
w_i' = (1 - mu) * normalize(w_i*) + mu/n
```

The mutation/exploration term keeps every strategy reachable.

## Homeostasis / carrying capacity

The existing ACE capacity function remains mandatory:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

When capacity becomes unhealthy, probability mass shifts toward `consolidate`. This is treated as a safety/homeostasis override rather than positive learned fitness.

The controller can therefore enter:

```text
DORMANT
EXPLORE
GROW
CONSOLIDATE
```

Even strong verified reproduction cannot override the consolidation gate when review capacity is overloaded.

## Anti-Goodhart / duplicate-event rule

Each descendant evidence record has a stable ID.

- identical repeated evidence is counted once;
- conflicting reuse of the same ID fails closed;
- unverified activity cannot create positive fitness;
- stars, comments, issue volume, and PR volume are not positive objective values.

This prevents repeated GitHub delivery or duplicate observations from multiplying strategy fitness.

## Action-budget rule

The code enforces:

```text
public autonomous ACE actions per generation <= 1
```

Configuration requesting more than one action is invalid.

The modeled action list is empty when:

- Issue #57's external activation gate has not passed;
- actuation is disabled;
- capacity is below the action floor;
- there is no evidence-backed recommendation;
- the controller is in `CONSOLIDATE` mode.

Phase A has no GitHub mutation adapter, so this is currently a testable model of future authority rather than real authority.

## Implementation artifacts

Added on the review branch:

- `experiments/ace_policy_controller.py` — pure deterministic controller and fixtures;
- `tests/test_ace_policy_controller.py` — invariant tests;
- `docs/community/ACE_POLICY_CONTROLLER_PHASE_A.md` — design and safety semantics;
- `.github/workflows/ace-policy-controller-check.yml` — read-only Python 3.11/3.13 validation;
- this conversation record.

## Deterministic fixtures

The controller contains three qualitative fixtures:

1. **under-reproduction** — activity exists but no verified descendants; no positive fitness or public action is invented;
2. **healthy reproduction** — `R_community >= 1` with healthy review capacity can enter `GROW` and make at most one modeled recommendation/action;
3. **overload** — verified descendants exist but high review load forces `CONSOLIDATE`, increases consolidation policy weight, and emits zero public growth actions.

These fixtures are illustrative engineering tests, not empirical community measurements.

## Verification discipline

The change is being proposed through a normal pull request and is not self-merged. This preserves the IDKMesh invariant that one actor should not propose, verify, and integrate its own protected change without an independent integration boundary.

The new workflow is `contents: read` only and contains no GitHub mutation step.

## Next dependency-aware step

After Phase A passes CI and review, the project should **not immediately enable autonomous Growth Seed creation**.

The next safe research step is to replay real/curated lineage snapshots from the observer/lineage surfaces through this pure controller, compare recommendations with human evaluation, and complete the ACE security/protection gates. A Phase-B metadata adapter should be proposed only after those prerequisites are satisfied.
