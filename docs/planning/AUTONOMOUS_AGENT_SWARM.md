# Autonomous Agent Swarm v0.1

This document defines a bounded, repository-native operating policy for several autonomous development agents working on IDKmesh through GitHub.

## Goal

Continuously improve IDKmesh without turning the repository into an unreviewable stream of branches and pull requests. Agents may discover work, implement a bounded change, push a short-lived branch, and open or update a pull request. They must not push directly to `main` or merge their own work.

The swarm optimizes for validated improvements, not commit volume.

## Topology

Run three worker roles plus one steward role. Workers are staggered through each hour so they do not all select work from the same repository snapshot.

| Role | Minute | Scope | Branch prefix |
| --- | ---: | --- | --- |
| Product Evolution | `:05` | installable product surfaces, CLI/interop usability, concrete features | `agent/product/` |
| Reliability | `:25` | tests, CI, deterministic tooling, performance, reproducibility | `agent/reliability/` |
| Community & Research | `:45` | ACE/community growth, experiments, biological/economic coordination ideas | `agent/community/` |
| Integration Steward | `:55` | queue health, drift, conflicts, CI diagnosis, cleanup; no new feature work | n/a |

Each role is invoked hourly, but invocation does not imply creating a new PR.

## Shared admission rules

Before changing code, every worker must:

1. Fetch current `main`, open PRs, active branches, and recent CI.
2. Look for an already-open PR with its own branch prefix. If one exists, work only on that PR: diagnose CI, update from current `main` when safe, reduce scope, or document the blocker. Do not start another PR.
3. Count active autonomous-agent PRs. The swarm may have at most **three** active worker PRs total.
4. Inspect changed filenames of open PRs. Do not start work that overlaps files already owned by another active PR unless the task is specifically to reconcile that PR.
5. Prefer an existing issue with clear acceptance evidence. If no suitable issue exists, derive one bounded improvement from repository evidence and explain why it matters in the PR body.

If these conditions are not satisfied, make no repository write.

## Bounded-change rule

A worker may implement work directly only when it can plausibly fit in one reviewable PR. Default bounds:

- at most 8 changed files;
- at most roughly 500 net changed lines;
- no secret, token, permission, branch-protection, billing, or deployment change;
- no broad dependency migration;
- no repository-wide mechanical rewrite;
- no architectural change whose correctness cannot be demonstrated by focused evidence.

If the best next improvement exceeds those bounds, open or refine an issue/design note instead of producing a large speculative implementation.

## Development loop

For an admitted task:

1. Start from the current `main` head and create a uniquely named branch beneath the role prefix.
2. State the hypothesis: what observable repository problem should improve?
3. Implement the smallest coherent change that tests that hypothesis.
4. Add or update regression evidence where appropriate.
5. Run focused tests locally when execution tools are available. Otherwise rely on GitHub Actions and inspect failed job steps/logs before making follow-up commits.
6. Push the branch and open a PR with motivation, evidence, risks, Community Impact, and AI/tool provenance, following the repository template and `AGENTS.md`.
7. On later hourly invocations, repair that same PR until it is green and current enough for maintainer review. Do not self-merge.

## Role definitions

### Product Evolution agent

Optimize for something a user or contributor can actually use. Good targets include the installable `gate-audit` surface, interoperability adapters, CLI ergonomics, examples that execute end-to-end, and small missing product capabilities supported by tests. Avoid documentation-only churn unless it removes a demonstrated onboarding failure.

### Reliability agent

Reduce failure probability and maintenance cost. Good targets include flaky or misleading tests, CI failures, runtime/test performance, stale guards, deterministic fixtures, schema drift, workflow correctness, branch/PR hygiene automation, and reproducibility. Do not weaken a gate just to make it green.

### Community & Research agent

Explore IDKmesh's distinctive thesis: systems that improve their own contributor/community dynamics using measurable mechanisms from biology, economics, distributed systems, and collective intelligence. Prefer executable experiments with explicit metrics over prose-only ideas. Keep experiments deterministic and isolated from production authority until evidence justifies promotion.

### Integration Steward

The steward does not invent new features. Each run should inspect open PRs, branch drift, mergeability, CI, duplicate work, orphan branches, and the canonical integration order. It may update or comment on agent PRs, retire clearly superseded agent branches/PRs when safe, or surface a blocker. It must not merge unreviewed work and must not push directly to `main`.

## Stop conditions

An agent should stop and make no write when:

- its previous PR is waiting on a human decision rather than a technical fix;
- the target files overlap another active PR;
- required CI is broadly failing on `main` and the proposed work is unrelated;
- evidence would require credentials or external authority not available to the agent;
- the only available task would be cosmetic churn;
- repository state is ambiguous enough that a maintainer decision is the real next step.

## Why hourly invocation is acceptable

Hourly *selection* is useful because GitHub state can change quickly. Hourly *PR creation* is not. The one-active-PR-per-worker rule and the three-PR global cap turn the hourly schedule into a feedback loop: most runs maintain or validate existing work rather than create more work.

This is intentionally closer to an ecological population with carrying capacity than an unconstrained job queue: new work is admitted only when review capacity exists.
