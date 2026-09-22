# IDKMesh Self-Growth Mechanism

**Status:** current plain-language explainer. Canonical authority rules remain in
[`EVOLUTION.md`](../../EVOLUTION.md),
[`ITERATION_MODEL.md`](../../ITERATION_MODEL.md),
[`CONSTITUTION.md`](../../CONSTITUTION.md), and the linked executable workflows.

IDKMesh "self-growth" is a **guarded feedback loop for increasing verified project
capacity**. It does not mean that one AI agent can rewrite the repository and approve
its own changes.

The shortest description is:

```text
observe repository/community state
 -> preserve evidence and history
 -> diagnose bottlenecks
 -> choose a bounded mode/action
 -> expose or execute bounded work
 -> produce candidate artifacts/PRs
 -> verify independently
 -> human/governance integration decision
 -> measure the outcome
 -> update evidence/state
 -> repeat
```

The loop is intentionally asymmetric: **many observations, few public writes, and no
self-approval**.

Self-growth is also **multi-axis**. Repository correctness and verification are only two dimensions; the controller must also observe discoverability, SEO/AEO, community acquisition, contributor retention, reviewer/leader capacity, and real adoption. See [`docs/community/VISIBILITY_AND_COMMUNITY_GROWTH_LOOP.md`](../community/VISIBILITY_AND_COMMUNITY_GROWTH_LOOP.md) for the external-growth control surface and the read-only visibility observatory.

## 1. Observe

GitHub and repository state are treated as the environment.

The evolution workflow observes bounded metadata such as:

- open issues and pull requests;
- independent-review coverage;
- branch pressure;
- starter-task supply;
- external participation;
- workflow dependency pinning;
- repository protection;
- dependency/reference structure;
- review load and carrying capacity.

The canonical workflow is
[`.github/workflows/evolution-loop.yml`](../../.github/workflows/evolution-loop.yml).
It runs on trusted repository events, manual dispatch, and a daily scheduled audit.

## 2. Remember

IDKMesh keeps inspectable state rather than relying on hidden agent memory.

The repository-evolution loop preserves:

- persistent Bayesian event/history state;
- a provenance-bound checkpoint lineage;
- fresh repository snapshots;
- generated evolution decisions and reports.

ACE, the community-growth loop, keeps a public state ledger in GitHub issue #23.

The important principle is:

> learning must leave an inspectable evidence trail.

This is not hidden model fine-tuning.

## 3. Diagnose and score

The live repository observatory computes engineering signals including:

- logistic review carrying capacity;
- independent-review coverage;
- Shannon diversity of open work;
- dependency visibility and unlock pressure;
- protection and supply-chain deficits;
- branch pressure;
- a multi-dimensional control-energy deficit.

It also computes pressures over bounded strategies:

```text
protect
verify
consolidate
integrate
onboard
explore
maintain
```

A replicator-mutator response preserves some exploration instead of allowing one
strategy to dominate forever.

These quantities are decision-support signals, not authority.

## 4. Apply hard guards

The current controller can move into modes such as:

```text
GUARD
CONSOLIDATE
VERIFY
ONBOARD
INTEGRATE
EXPLORE
```

Historical evidence cannot compensate for a current hard blocker.

Examples:

- unprotected canonical branch -> `GUARD`;
- too much review load -> `CONSOLIDATE`;
- ready PRs without independent review -> `VERIFY`;
- healthy capacity but weak newcomer supply -> `ONBOARD`.

The conjunctive controller combines historical evidence with current live state, but
its non-compensation rule is deliberately conservative:

```text
current hard blocker = true
    => stronger experiment escalation = false
```

See
[`docs/architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md`](CONJUNCTIVE_EVOLUTION_CONTROL.md).

## 5. Reproduce bounded opportunities

There are two distinct growth loops.

### Repository evolution loop

The repository-evolution workflow is currently **recommendation-only**. It can observe,
score, produce evidence, and recommend bounded needs. It does not grant itself:

- merge authority;
- approval authority;
- branch-mutation authority;
- spending authority;
- constitutional-change authority.

### ACE community reproduction loop

ACE is the current limited public-write growth mechanism.

It converts repository activity into **reproductive credit** using:

```text
DeltaCredit = ActivityEnergy * Novelty * Capacity
```

where repeated event types receive diminishing novelty and review saturation reduces
the capacity multiplier.

ACE may create a new Growth Seed only when both are true:

1. `main` is protected; and
2. repository variable `ACE_AUTONOMOUS_ACTUATION_ENABLED` is explicitly `true`.

Even then, the actuator is narrow. A merged PR must be explicitly labeled
`growth:spawn`, and ACE creates a bounded follow-up issue inviting a contributor to
reproduce, challenge, extend, or explain the result. Recovery is capped so an
unexpected backlog cannot cause mass issue creation.

The executable implementation is
[`.github/workflows/ace-community-growth.yml`](../../.github/workflows/ace-community-growth.yml).

## 6. Execute with replaceable humans and agents

The growth controller should not depend on one model.

A bounded task can be executed through humans or replaceable worker adapters such as
coding agents, local workers, A2A/MCP-connected workers, or future integrations.

The intended path is:

```text
GitHub issue / bounded goal
 -> WorkUnit
 -> selected worker/agent
 -> candidate branch/artifacts
 -> ResultManifest
```

Worker completion is never acceptance.

## 7. Verify independently

Candidate work must pass verifier-owned checks and provenance requirements.

The key separation is:

```text
worker says "done"
        !=
verifier says "evidence passes"
        !=
repository/governance says "integrate"
```

Verification capacity therefore acts as a biological-style resource constraint:
generation should slow when independent verification becomes scarce.

## 8. Integrate through external authority

Canonical project state changes only through the repository/governance integration
boundary.

The self-growth machinery may recommend or generate bounded descendants, but it cannot
approve its own high-impact changes.

This is the main safety property that makes "self-growing" different from
"self-modifying without control."

## 9. Learn from outcomes

After work is accepted, rejected, reverted, reproduced, or challenged, its outcome can
feed the next observation cycle.

Useful future outcome signals include:

- regressions and reverts;
- benchmark movement;
- verifier disagreement;
- review latency;
- time-to-verified-useful-work;
- newcomer task completion;
- contributor return rate;
- security findings.

The project should increasingly replace authored heuristics with calibrated models only
after enough observed evidence exists.

## Anti-Goodhart rule

IDKMesh explicitly avoids equating activity with improvement.

```text
stars        != correctness
forks        != correctness
commits      != improvement
comments     != evidence
agent output != acceptance
score        != authority
```

The target is **verified useful improvement per unit of scarce human and verification
attention**, not maximum repository activity.

## What "self-growth" means today

Today, IDKMesh already has:

- executable repository observation;
- persistent cross-run evolution evidence;
- carrying-capacity and review-pressure control;
- bounded recommendation logic;
- independent-verification boundaries;
- ACE's guarded Growth Seed actuator;
- agent/worker integration surfaces.

It does **not** yet have one fully autonomous end-to-end controller that discovers an
arbitrary goal, dispatches it to an agent, independently verifies it, changes its own
policy, and integrates the result without external authority.

That limitation is intentional.

The desired long-term property is not maximum autonomy. It is:

> **the repository becomes progressively better at discovering, routing, verifying,
> and learning from useful work while keeping irreversible authority outside the
> mechanism being evaluated.**

For live ACE state, read the repository's **[ACE] Community Growth Ledger** issue rather
than copying a status snapshot into this document.
