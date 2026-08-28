# Conjunctive Evolution Control

**Status:** proposed executable convergence in PR #146  
**Date:** 2026-08-28  
**Authority:** observation, evidence, attention allocation, hard-current guarding, and bounded recommendation only

## Canonical composition

IDKMesh now has complementary mathematical control surfaces that should not be collapsed into one score or allowed to compete as parallel controllers:

```text
#137 persistent Bayesian history
        +
#146 hard recomputed current-state governor
        +
#143 live Pareto/UCB attention portfolio
        |
        v
bounded recommendation surface
        |
        v
independent verification + external GitHub governance
```

PR #144's stateless `repository_evolution_score.py` remains useful as an **offline comparison/falsification baseline** for current-state recommendations. It is not treated as an additional autonomous controller.

No layer grants approval or merge authority.

---

## 1. Persistent Bayesian history — #137

Canonical core:

- `scripts/evolution_math.py`
- `scripts/evolution_score.py`
- `state/evolution-state.json`
- `state/evolution-math-policy.json`

This layer answers: **what has accumulated over trusted historical observations, and how uncertain are we?**

It includes Bayesian soft evidence, correlation-aware verification aggregation, Pareto/NSGA primitives, UCB, multiplicative weights, graph unlock, entropy/JSD, and homeostatic-potential mathematics.

Trusted-main checkpoint artifacts preserve state across runs. Soft event evidence is not causal proof.

---

## 2. Hard recomputed current-state governor — #146

Canonical proposed files:

- `scripts/evolution_snapshot.py`
- `scripts/evolution_live_governor.py`
- `state/evolution-live-policy.json`
- `tests/test_evolution_live_governor.py`

This layer answers: **are the hard current repository conditions healthy now?**

Its evidence is recomputed rather than accumulated so pressure can recover when open work disappears.

### Live carrying capacity

Reuse ACE `live-open-work-v1`:

```text
L =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_issues, 20)

Capacity(L) = 1 / (1 + exp((L-K)/tau))
```

Bootstrap values remain `K=8`, `tau=2` until real review-latency/backlog evidence supports recalibration.

Required property:

```text
open work decreases -> L decreases -> capacity recovers
```

### Hard current signals

The bounded snapshot/governor measures:

- actual default-branch protection;
- review-ready vs draft PR pressure;
- independent-review coverage;
- starter-task supply;
- distinct non-owner/non-bot public witness/participant presence;
- workflow immutable-SHA pin ratio;
- branch-count coordination pressure;
- open-work Shannon diversity;
- project-memory archive/rule surfaces.

It reuses the canonical `normalized_entropy()` and `homeostatic_potential()` primitives from `evolution_math.py` rather than creating a second mathematics package.

### Modes

```text
GUARD
CONSOLIDATE
VERIFY
ONBOARD
INTEGRATE
EXPLORE
```

The mode is conjunctive, not compensatory. In particular:

```text
main_protected = false => GUARD
```

Historical Bayesian fitness, Pareto rank, UCB opportunity, popularity, or activity cannot override this condition.

---

## 3. Live Pareto/UCB attention portfolio — #143

Canonical files:

- `scripts/repository_portfolio.py`
- `state/repository-portfolio-policy.json`
- `state/repository-portfolio-state.json`
- `.github/workflows/repository-math-portfolio.yml`

This layer answers: **where is present reviewer/research attention likely to be most informative under multiple objectives?**

It uses dependency graph structure, Pareto fronts/crowding, entropy/JSD, multiplicative attention weights, Bayesian health deficits, and UCB exploration.

It allocates attention only. A target can be interesting to inspect while the hard governor remains `GUARD`.

### Historical-health input repair

The portfolio should consume the trusted persistent Bayesian checkpoint from the Evolution Loop. PR #146 restores the `evolution-checkpoint-*` contract so portfolio health does not silently fall back to the repository seed after #144's stateless artifact naming changed.

---

## 4. Stateless #144 observer as comparison baseline

PR #144's `scripts/repository_evolution_score.py` is retained on `main` as a valuable independent/stateless comparison surface.

Use it to ask:

- does a stateless snapshot produce the same high-level recommendation as the persistent+hard-governor system?;
- where do they disagree?;
- does disagreement expose bad priors, stale historical state, or weak live proxies?

It should not be wired as a second actuator/controller. Divergence is evidence for falsification and calibration.

---

## 5. GitHub Actions trust boundary

### Trusted live observation

For pull-request metadata, live observers use `pull_request_target` so the workflow definition comes from the trusted default branch. They explicitly check out the default branch and **never execute PR-head code** with live-observer token scopes.

The evolution live job uses only the read permissions required for metadata plus trusted artifact restoration:

```text
contents: read
issues: read
pull-requests: read
actions: read
```

The portfolio live observer has the same read-only shape.

### Proposed-code verification

Ordinary `pull_request` jobs:

- check out proposed PR code;
- have `contents: read` only;
- disable persisted checkout credentials;
- run deterministic compile/unit/invariant tests;
- do not restore trusted checkpoints;
- do not run live GitHub metadata observers;
- receive no repository secrets explicitly.

This prevents a proposed workflow/script from converting observer token authority into arbitrary PR-head behavior.

### Persistent-state concurrency

Trusted artifact-backed observers use latest-state concurrency with `cancel-in-progress: true`, preventing multiple runs from restoring one checkpoint and publishing competing successors.

This state is therefore a **latest-state observer**, not an immutable event-accounting ledger.

---

## 6. Evidence minimization and untrusted text

The hard-governor snapshot retains no issue/PR/comment bodies. Natural-language GitHub content is untrusted input; it keeps bounded structural metadata such as labels, age, deduplicated same-repository `#N` references, and reviewer/participant counts.

The Pareto portfolio still needs issue/PR text ephemerally for deterministic classification/reference extraction, but PR #146 changes the retained artifact boundary:

```text
raw body snapshot -> /tmp only -> portfolio calculation -> discarded with runner
```

The uploaded portfolio checkpoint contains derived state/output/policy/Markdown only. It **must not contain `repository-snapshot.json` with raw bodies**.

---

## 7. Supply-chain posture

Core mathematical workflows pin reviewed external actions to immutable commits:

```text
actions/checkout          3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
actions/setup-python      5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
actions/upload-artifact   043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
actions/download-artifact 3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c  # v8.0.1
```

The live governor separately scans the entire workflow directory and reports repository-wide pin coverage. Hardening this control plane is not a claim that every repository workflow is already fully pinned.

---

## 8. Anti-Goodhart boundary

Hard-governor fitness excludes:

- stars;
- forks;
- reactions;
- raw comments;
- raw commits.

And more generally:

```text
Bayesian posterior != causality
Pareto front        != correctness
UCB focus           != approval
activity volume     != improvement
popularity          != trust
```

These signals can be informative in bounded contexts, but cannot create authority.

---

## 9. Automatic authority permitted today

Allowed:

- read public repository metadata;
- restore trusted observer checkpoints;
- compute/recompute evidence;
- retain minimized replayable artifacts;
- rank attention targets;
- report blockers and recommendations;
- run deterministic tests/simulations;
- publish job summaries.

Not granted:

- merge;
- approve;
- branch mutation;
- issue/PR label, assignment, closure, or creation by the controller;
- repository-settings/ruleset changes;
- constitutional/governance mutation;
- secrets access;
- spending money;
- treating self-generated evidence as independent review.

Issue #35 remains the external branch-protection gate. Issue #138 remains a public surface for the separate human review required by PR #91.

---

## 10. Falsification and next mathematical step

The next major improvement should be **calibration from delayed outcomes**, not another hand-authored controller.

Join retained observations to later outcomes such as:

- regressions/reverts;
- verifier disagreement;
- review latency and human burden;
- benchmark movement;
- issue reopen rate;
- newcomer completion;
- external contributor retention;
- security findings;
- time-to-verified-useful-work.

Compare predictive variants with held-out metrics such as Brier score, log loss, calibration error, and ranking regret.

Treat the current model as wrong or incomplete if carrying capacity fails to predict review burden, live potential improves while coordination worsens, stateless/persistent recommendations diverge without useful explanation, or portfolio attention repeatedly fails to create verified value.

Negative results are first-class evidence.
