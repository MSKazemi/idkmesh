# Conjunctive Evolution Control

**Status:** executable v0.1  
**Date:** 2026-08-28  
**Authority:** observation and bounded recommendation only

## Canonical composition

IDKMesh now uses three complementary mathematical control surfaces:

```text
persistent Bayesian history
        +
recomputed Repository Evolution Observatory
        +
live Pareto/UCB Repository Mathematical Portfolio
        |
        v
conjunctive bounded recommendation
        |
        v
independent verification + external GitHub governance
```

They answer different questions and must not be collapsed into one score.

### 1. Persistent Bayesian history

Canonical files:

- `scripts/evolution_math.py`
- `scripts/evolution_score.py`
- `state/evolution-state.json`
- `state/evolution-math-policy.json`

This layer accumulates uncertain historical event evidence in Beta beliefs, preserves trusted default-branch state through replayable artifacts, reports posterior confidence bounds, activity diversity, and a Lyapunov-style homeostatic diagnostic.

It is historical evidence, not causality.

### 2. Recomputed Repository Evolution Observatory

Canonical files:

- `scripts/evolution_snapshot.py`
- `scripts/repository_evolution_score.py`
- `config/evolution-policy-v1.json`
- `tests/test_evolution_observer.py`
- `docs/architecture/REPOSITORY_EVOLUTION_OBSERVATORY.md`

This layer recomputes current repository state from bounded public GitHub metadata. It combines:

- ecological/logistic carrying capacity;
- independent-review coverage;
- bounded graph/reference coordination signals;
- Shannon diversity;
- control-energy deficits;
- replicator-mutator strategy allocation;
- hard current modes such as `GUARD`, `VERIFY`, and `CONSOLIDATE`;
- anti-Goodhart exclusion of popularity/activity proxies from correctness.

It intentionally stores structural metadata rather than issue/PR/comment bodies.

### 3. Repository Mathematical Portfolio

Canonical files:

- `scripts/repository_portfolio.py`
- `state/repository-portfolio-policy.json`
- `state/repository-portfolio-state.json`
- `.github/workflows/repository-math-portfolio.yml`

This layer ranks current open work with:

- Pareto non-dominated fronts;
- NSGA-II crowding;
- explicit dependency unlock;
- entropy/Jensen-Shannon diversity;
- multiplicative attention weights;
- UCB exploration.

It allocates attention, not integration rights.

---

## Conjunctive controller

Canonical file:

- `scripts/conjunctive_evolution_control.py`

The controller combines conservative Bayesian confidence with the recomputed live decision.

For the Bayesian verification belief:

```text
verification_lower = mean - z * sqrt(variance)
```

and for Bayesian risk debt:

```text
risk_upper = mean + z * sqrt(variance).
```

The initial confidence thresholds are derived from the existing homeostatic policy rather than adding new arbitrary constants:

```text
verification_floor
  = verification_target - verification_scale

risk_ceiling
  = risk_target + risk_scale.
```

The live capacity threshold comes from `config/evolution-policy-v1.json`.

A stronger **bounded non-integrating experiment** is only a candidate when all are true:

```text
no current live blockers
AND live mode is not GUARD
AND conservative verification confidence >= verification floor
AND conservative risk upper bound <= risk ceiling
AND live review capacity >= configured minimum
AND live mode is EXPLORE, ONBOARD, or INTEGRATE.
```

Even then:

```text
integration_authority = false
merge_authority       = false
approval_authority    = false
branch_mutation       = false
spending_authority    = false
```

### Non-compensation rule

The central invariant is:

```text
live hard blocker = true
    => stronger experiment candidate = false
```

regardless of historical Bayesian fitness or confidence.

Therefore, while GitHub reports the canonical branch unprotected:

```text
main_unprotected -> GUARD -> no escalation candidate.
```

Issue #35 remains the external administrative gate.

---

## Restored cross-iteration history

The merged Repository Evolution Observatory improved live-state measurement but temporarily replaced the artifact-backed Bayesian update in `.github/workflows/evolution-loop.yml`.

The converged workflow restores Bayesian persistence without removing the new observatory.

On each trusted observation it:

1. searches recent **successful default-branch runs from an explicit trusted-event allowlist** of the same workflow;
2. finds the newest run with the exact unexpired `evolution-checkpoint-v2-<run-id>` artifact;
3. verifies a manifest binding repository, workflow, run, head SHA, event, parent run, file sizes, and SHA-256 digests;
4. validates state schema, finite/bounded beliefs, authority invariants, counters, and ledger lineage before use;
5. performs the Bayesian update;
6. recomputes the live observatory from fresh GitHub evidence;
7. evaluates the conjunctive controller;
8. retains all three evidence layers in the next `evolution-checkpoint-v2-*` artifact.

Ordinary `pull_request` runs are excluded by event type, not inferred safe from a
branch name. Once a checkpoint has been selected, download, manifest, or semantic
validation failure aborts the run; only the absence of any eligible checkpoint
permits the deterministic repository seed.

---

## GitHub trust boundary

Live API observation and proposed-code testing are separated.

### Trusted live observation

For PR metadata, the live observers use `pull_request_target` and:

- use the workflow definition from the default branch;
- explicitly check out the default branch;
- never execute PR-head code;
- use only job-local read permissions;
- disable persisted checkout credentials;
- pin the core Actions by immutable SHA.

Direct `pull_request_review` events do not run the checkpoint-producing observer.
Review state is refreshed by trusted PR-target lifecycle events and scheduled snapshots.
Review coverage counts only the latest non-author, non-bot `APPROVED` or
`CHANGES_REQUESTED` review attached to the PR's exact current head SHA; approvals
remain a separate signal.

### Proposed-code verification

Ordinary `pull_request` jobs:

- check out PR-head code;
- receive `contents: read` only;
- run deterministic compile/unit/invariant tests;
- do not restore trusted checkpoints;
- do not execute live GitHub API observation.

The same separation is applied to the Repository Mathematical Portfolio.

---

## Artifact-state concurrency

Artifact-backed observer state cannot safely have two concurrent successors restoring the same parent checkpoint.

Trusted observers therefore use one repository-level concurrency group with `cancel-in-progress: true`.

The semantics are explicit:

> this is a latest-state observer, not a lossless accounting ledger of every GitHub event.

Rapid event bursts converge to the newest current-state observation. This avoids forked Bayesian/portfolio artifact histories until IDKMesh has a transactional state store.

---

## Supply-chain posture

The core mathematical workflows pin reviewed Action versions to immutable commits:

```text
actions/checkout
  3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1

actions/setup-python
  5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0

actions/upload-artifact
  043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1

actions/download-artifact
  3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c  # v8.0.1
```

The live observatory measures the repository-wide pin ratio, so hardening these workflows does not become a false statement that all repository workflows are already fully pinned.

---

## Anti-Goodhart invariants

```text
stars          != correctness
forks          != correctness
raw comments   != correctness
raw commits    != improvement
Bayesian score != causality
Pareto rank    != approval
UCB focus      != trust
replicator mass != integration authority
```

Current hard guards and independent verification remain necessary regardless of activity or popularity.

---

## Scientific next step

The next major mathematical advance should be calibration, not more unmeasured formulas.

The repository now retains enough replayable state to join historical decisions to delayed outcomes such as:

- regressions and reverts;
- verifier disagreement;
- benchmark movement;
- review latency and burden;
- issue reopen rate;
- newcomer task completion;
- contributor retention;
- security findings;
- time-to-verified-useful-work.

Candidate predictive models should then be compared on held-out data using calibration error, Brier score, log loss, ranking regret, and uncertainty coverage.

Only after that evidence exists should experiment allocation move from proxy UCB toward contextual bandits or Thompson sampling driven by measured outcomes.
