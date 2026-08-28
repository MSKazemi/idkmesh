# Live repository mathematical portfolio implementation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Continuation direction

After merging the Mathematical Evolution Kernel and proving its Bayesian checkpoint persistence across two real `main` iterations, the next useful step was to apply the mathematics to live repository work rather than add more isolated formulas.

The owner asked for a more solid, smarter mathematical/algorithmic foundation implemented through GitHub Actions and GitHub-native capabilities.

## Why this layer was added

The repository already had reusable implementations for:

- Bayesian evidence;
- correlated-verifier effective evidence;
- Pareto/NSGA selection;
- multiplicative weights;
- UCB exploration;
- entropy/Jensen-Shannon diversity;
- graph unlock value;
- homeostatic/Lyapunov diagnostics.

The missing operational question was:

> How should the live open issue/PR portfolio be observed with these algorithms without granting the observer repository authority?

## Implementation

Added a read-only `Repository Mathematical Portfolio` layer.

### Live snapshot

The Action uses GitHub CLI under read-only token permissions to snapshot up to 200 open issues and 200 open pull requests, including public metadata such as title/body/labels/comments/author/timestamps.

The normalized snapshot is retained with the resulting report so every ranking can be replayed against the exact observed repository state.

### Strategy partition

Open work is deterministically classified into:

- community;
- exploration;
- maintenance;
- product;
- safety;
- verification.

The vocabulary is versioned in `state/repository-portfolio-policy.json` rather than hidden in workflow code.

### Explicit dependency graph

The parser creates graph edges only for explicit phrases:

- `blocked by #N`;
- `depends on #N`;
- `requires #N`;
- `blocks #N`.

A generic `#N` mention does not create a dependency.

This rule is regression-tested to prevent the system from inventing graph structure from ordinary cross-references.

### Multi-objective features

Each issue/PR receives transparent bounded proxy features:

- impact;
- information gain;
- unlock;
- diversity;
- risk;
- cost;
- review burden.

They are fed to non-dominated Pareto sorting and NSGA-II crowding. A small scalar opportunity score exists only as a deterministic explanatory/tie-break diagnostic, not as the primary optimizer.

### Graph unlock

Open issues use the canonical mathematical kernel's discounted directed unlock value. Only explicit dependency edges contribute.

### Diversity

The observer computes strategy entropy and Jensen-Shannon divergence between the live open-issue portfolio and the previous attention mixture.

### Health-aware attention

The latest trusted Bayesian evolution checkpoint is downloaded on trusted `main` runs.

Distance from homeostatic targets becomes a strategy **attention need**, which updates strategy mixture weights with multiplicative weights and an exploration floor.

This is explicitly not described as causal reward.

### UCB exploration

The portfolio state counts how often each strategy has received exploration focus. Current live opportunity plus historical attention count drives a UCB exploration choice.

An unseen strategy receives exploration priority, preventing the repository from permanently focusing only on historically dominant work classes.

Again, UCB selects a recommended exploration focus, not an issue mutation or merge action.

## Persistent GitHub-native state

The workflow uses the proven artifact-checkpoint pattern:

- on trusted default-branch runs, restore the previous successful portfolio checkpoint;
- update strategy weights/UCB counts;
- publish a new 30-day checkpoint artifact;
- on PR runs, use the checked-in seed and never promote PR-generated state into trusted future-main memory.

It separately restores the latest trusted Bayesian evolution checkpoint for health signals.

## Permissions and authority

The workflow requests only:

- `contents: read`;
- `issues: read`;
- `pull-requests: read`;
- `actions: read`.

It cannot label, assign, comment, approve, close, merge, or write repository contents.

This is intentional while `main` remains externally unprotected under canonical issue #35.

## Scientific value

The most important output is not the current ranking itself. It is a replayable longitudinal dataset:

```text
repository snapshot
+ policy version
+ Bayesian health state
+ dependency graph
+ feature vectors
+ Pareto fronts
+ diversity state
+ UCB/attention state
```

That dataset can later be joined to delayed real outcomes and used to calibrate the proxy model empirically.

The long-term direction remains:

```text
transparent hypotheses
 -> replayable observations
 -> delayed outcomes
 -> predictive calibration
 -> bounded experimental policy updates
 -> independent governance
```
