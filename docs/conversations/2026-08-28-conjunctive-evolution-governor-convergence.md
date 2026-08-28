# Conjunctive evolution governor convergence pass

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

Continue strengthening the mathematical/algorithmic background and implement it with GitHub-native capabilities while preserving the public repository record.

## Starting point in this pass

Two new canonical layers had already been merged:

- PR #137: Mathematical Evolution Kernel + persistent Bayesian observer;
- PR #143: live Repository Mathematical Portfolio using Pareto/NSGA, graph unlock, entropy/JSD, multiplicative attention, and UCB exploration.

The first canonical portfolio run succeeded, consumed a trusted Bayesian checkpoint, and retained its exact repository snapshot/output.

That live portfolio then surfaced open PRs #142 and #144 as review-attention candidates. This exposed a useful self-convergence test: multiple parallel evolution-observer branches were now competing with the canonical mathematical stack.

## Convergence decision

PR #144 proposed a separate recomputed observatory that would replace the persistent Bayesian evolution loop. That would duplicate/erase canonical state semantics, so its architecture is superseded.

PR #142 was the stronger complementary design. It explicitly preserved the Bayesian kernel and added unique current-state/governance properties:

- bounded live repository evidence;
- hard default-branch protection gate;
- carrying-capacity/review-pressure model;
- independent-review coverage;
- newcomer/external-witness signals;
- workflow immutable-SHA pin ratio;
- branch-pressure signal;
- live homeostatic potential;
- `GUARD/CONSOLIDATE/VERIFY/ONBOARD/INTEGRATE/EXPLORE` modes;
- a safer `pull_request_target` trust boundary;
- immutable GitHub Action pins.

Rather than merge its stale/conflicting branch, this pass ports only those unique ideas onto the current canonical main state, preserving both #137 and #143.

## New canonical composition

```text
persistent Bayesian history
        +
hard current-state governor
        +
live Pareto/UCB portfolio
        |
        v
bounded recommendation surface
        |
        v
independent verification + external GitHub governance
```

Historical Bayesian evidence cannot compensate for a failed hard current constraint.

## Trust-boundary hardening

Both live mathematical observer workflows now separate trusted live observation from proposed-code testing.

For live PR metadata observation:

- `pull_request_target` uses the default-branch workflow definition;
- the live job explicitly checks out the trusted default branch;
- PR-head code is never executed with live observer token scopes;
- persisted checkout credentials are disabled.

For ordinary `pull_request`:

- only deterministic compile/unit tests run;
- the PR-head job has `contents: read` only;
- no trusted checkpoint restore or live repository observation is executed.

This closes the most important remaining workflow-level trust ambiguity in the mathematical control plane.

## Artifact-state concurrency

Trusted observers use one global concurrency group with `cancel-in-progress: true`. This makes them latest-state observers rather than event-accounting ledgers and avoids concurrent runs restoring the same checkpoint and publishing forked successor states.

## Supply-chain hardening

The mathematical workflows pin reviewed GitHub Actions to immutable commit SHAs for checkout, Python setup, upload-artifact, and download-artifact. The live governor independently scans all repository workflows and reports the repository-wide pin ratio, so local hardening does not become a false claim that the whole repository is already pinned.

## Anti-Goodhart rule

Stars, forks, reactions, raw comments, and raw commit counts are excluded from the live hard-governor fitness. They can be community observations, but they are not correctness/safety evidence.

## Remaining external hard gate

Public GitHub branch metadata still reports `main` as unprotected. Therefore the live governor must resolve to `GUARD` until issue #35 is satisfied externally.

No repository workflow can truthfully substitute for that administrative control.
