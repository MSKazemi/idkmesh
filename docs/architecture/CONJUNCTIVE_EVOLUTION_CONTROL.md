# Conjunctive Evolution Control

**Status:** executable v0.1 architecture  
**Date:** 2026-08-28  
**Authority:** observation, evidence, attention allocation, and bounded recommendation only

## Why three mathematical layers

IDKMesh now has three complementary control surfaces. They must not be collapsed into one mystical score.

```text
persistent Bayesian history
        +
recomputed hard live governor
        +
live Pareto/UCB portfolio
        |
        v
bounded recommendation surface
        |
        v
independent verification + GitHub governance
```

Each layer answers a different question:

1. **Bayesian evolution kernel:** what does accumulated uncertain historical evidence suggest about repository health?
2. **Live governor:** are hard current constraints healthy right now?
3. **Mathematical portfolio:** where is current attention/experimentation most informative under multiple objectives?

No layer grants approval or merge authority.

---

## 1. Persistent Bayesian history

Canonical files:

- `scripts/evolution_math.py`
- `scripts/evolution_score.py`
- `state/evolution-state.json`
- `state/evolution-math-policy.json`

The historical state uses Beta beliefs and retained trusted-main artifacts. Soft event evidence changes posterior beliefs and uncertainty, but is not interpreted as causal proof.

This layer is intentionally persistent across GitHub Actions runs.

---

## 2. Recomputed current-state governor

Canonical files:

- `scripts/evolution_snapshot.py`
- `scripts/evolution_live_governor.py`
- `state/evolution-live-policy.json`
- `tests/test_evolution_live_governor.py`

The governor is recomputed from fresh public GitHub evidence. It intentionally stores no issue/PR/comment bodies. Natural-language repository content is untrusted input; the retained snapshot contains bounded structural signals only.

### Carrying-capacity model

For current open work:

```text
L =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_issues, 20)
```

and

```text
Capacity(L) = 1 / (1 + exp((L-K)/tau)).
```

The initial reviewed policy uses `K=8`, `tau=2`; these remain calibration hypotheses.

### Hard live signals

The snapshot/governor measures:

- default-branch protection;
- review-ready/draft PR pressure;
- independent-review coverage;
- newcomer starter-task supply;
- distinct external public participant/witness presence;
- workflow immutable-SHA pin ratio;
- branch-count pressure;
- bounded open-work diversity;
- project-memory preservation surfaces.

### Homeostatic potential

The live governor reuses the canonical quadratic potential:

```text
V = sum_j q_j * ((x_j - target_j) / scale_j)^2.
```

This is a current-state diagnostic, not a merge rule.

### Modes

The current-state governor can emit:

```text
GUARD
CONSOLIDATE
VERIFY
ONBOARD
INTEGRATE
EXPLORE
```

The ordering is conjunctive. Examples:

- unprotected default branch -> `GUARD`;
- exhausted review capacity -> `CONSOLIDATE`;
- ready work without independent review -> `VERIFY`.

### Non-compensation theorem for v0 governance

For a configured hard guard `g`, historical fitness cannot compensate for its failure:

```text
hard_guard(g) = false
    => stronger autonomous authority is forbidden
```

regardless of Bayesian posterior means, Pareto rank, UCB focus, stars, forks, reactions, comments, or commit count.

In particular:

```text
main_protected = false => GUARD
```

Issue #35 remains the external administrative gate.

---

## 3. Live Pareto/UCB repository portfolio

Canonical files:

- `scripts/repository_portfolio.py`
- `state/repository-portfolio-policy.json`
- `state/repository-portfolio-state.json`
- `.github/workflows/repository-math-portfolio.yml`

This layer maps current open issues/PRs into transparent multi-objective proxies and computes Pareto fronts, crowding, explicit graph unlock, entropy/JSD, multiplicative attention, and UCB exploration.

It allocates **attention**, not integration rights.

The portfolio may recommend looking at an item while the hard governor simultaneously says `GUARD`. That is not a contradiction: useful work can continue while authority remains bounded.

---

## 4. GitHub trust boundary

Live API observation and proposed-code verification are deliberately separated.

### Trusted live observation

For pull-request metadata, live observers use `pull_request_target` and:

- execute the workflow definition from the default branch;
- explicitly check out the default branch;
- never check out PR-head code;
- use only read permissions required by the observer;
- disable persisted checkout credentials;
- pin third-party/first-party Actions by immutable SHA.

### Proposed-code verification

Ordinary `pull_request` runs:

- check out PR-head code;
- receive only `contents: read`;
- compile and run deterministic unit/invariant tests;
- receive no explicit live API token environment;
- do not restore trusted checkpoints or execute live observers.

This prevents a proposed workflow/script from converting read-observer token authority into arbitrary PR-head behavior.

---

## 5. Persistent-state concurrency

Artifact-backed state is vulnerable to forked histories if two runs restore the same checkpoint and publish competing successors.

Trusted live observers therefore use a single repository-level concurrency group with `cancel-in-progress: true`.

Interpretation:

- the state is a **latest-state observer**, not an immutable accounting ledger of every GitHub event;
- rapid event bursts converge to the newest observation;
- cancelled intermediate observations are not treated as missing correctness evidence;
- downstream decisions must rely on current repository evidence and replayable retained checkpoints, not raw event counts.

This is preferable to concurrent state forks under the current artifact-only persistence model.

---

## 6. Supply-chain posture

Core mathematical workflows pin the reviewed action versions by immutable commit:

```text
actions/checkout      3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
actions/setup-python  5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
actions/upload-artifact 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
actions/download-artifact 3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
```

The live governor scans all repository workflows and reports the total immutable-SHA pin ratio. It does not claim the entire repository is fully pinned merely because the mathematical workflows are.

---

## 7. Anti-Goodhart boundary

Hard-governor fitness explicitly excludes:

- stars;
- forks;
- reactions;
- raw comment volume;
- raw commit volume.

These may be useful community observations elsewhere, but they cannot prove correctness or safety.

Likewise:

```text
Bayesian posterior != causality
Pareto front       != correctness
UCB focus          != approval
activity volume    != improvement
popularity         != trust
```

---

## 8. What the system may do automatically

Allowed under current v0 architecture:

- read public repository metadata;
- compute/recompute evidence;
- retain bounded replayable artifacts;
- restore prior trusted-main observer checkpoints;
- rank/recommend attention targets;
- report hard blockers;
- run deterministic tests and simulations;
- publish GitHub job summaries.

Not granted:

- merge;
- approve;
- label/assign/close issues or PRs;
- mutate branches;
- create constitutional changes;
- spend money;
- treat self-generated evidence as independent review.

---

## 9. Scientific next step

The next mathematical improvement should be **calibration**, not another hand-authored objective.

Retained historical artifacts should be joined to delayed outcomes such as:

- regressions/reverts;
- verifier disagreement;
- review latency and burden;
- benchmark movement;
- issue reopen rate;
- newcomer completion;
- external contributor retention;
- security findings;
- time-to-verified-useful-work.

Candidate predictive models can then be compared using held-out calibration metrics such as Brier score, log loss, calibration error, and ranking regret.

Only after this dataset exists should UCB evolve toward contextual bandits or Thompson sampling based on measured outcomes rather than current proxy opportunity.
