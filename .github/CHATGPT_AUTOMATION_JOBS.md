# ChatGPT Automation Jobs for IDKmesh

_Last reviewed: 2026-09-19_

This document records the **currently active repository-facing ChatGPT automation
roles** for the public `MSKazemi/idkmesh` repository. It exists so maintainers,
contributors, and other agents can understand what automated stewardship may
change or report without relying on old issue or conversation text.

> These are ChatGPT-side automations, not GitHub Actions. Scheduling and enabled
> state are managed outside the repository and can change independently of this
> file. Treat the live automation configuration as the execution source of truth;
> treat this file as the public responsibility/provenance map.

## Active roles

The live ChatGPT-side swarm is intentionally staggered in the `Europe/Rome` timezone so the repository gets frequent independent attention without several mutating workers racing the same files.

| Role | Cadence | Repository-facing responsibility |
| --- | --- | --- |
| **IDKMesh Git Watch** | Hourly | Read-only monitoring for new commits, PR/issue activity, CI failures, review blockers, conflicts, and workflow changes; notifies only on meaningful changes. |
| **IDKmesh Swarm Governor** | Hourly at `:00` | Choose FREEZE / CONSOLIDATE / BUILD, enforce global concurrency and deduplication, and identify the highest-leverage next action. |
| **IDKmesh PR Integrator** | Hourly at `:10` | Recover, refresh, validate, converge, and when policy permits merge one exact-head eligible PR. |
| **IDKmesh Backend API Agent** | Every 2 hours at `:20` | Backend/core Python, APIs, interoperability, schemas, configuration, SDK/client boundaries, and related tests/docs. |
| **IDKmesh Frontend DX Agent** | Every 2 hours at `:30` | Pages/product surfaces, CLI UX, packaging, examples, onboarding, accessibility, and developer experience. |
| **IDKmesh Reliability Agent** | Hourly at `:40` | CI/CD, tests, errors, reproducibility, security, observability, performance, and regression prevention. |
| **IDKmesh Docs Sync** | Every 4 hours at `:50` | README/contributor docs, architecture, roadmap, API/config references, CHANGELOG, and paper/evidence synchronization. |
| **IDKmesh Research Scout** | Daily at `08:30` | Current standards, ecosystem, architecture, scientific-method, and relevant dependency/security research. |
| **IDKmesh Growth Release** | Daily at `18:30` | Release readiness, demos, Pages/front door, packaging, reusable integrations, and contributor conversion. |

The scheduler cannot run any one task more frequently than hourly. The staggered specialist design therefore creates a faster project-level heartbeat while preserving independent per-role safety boundaries.

## Operating contract

The active automation set should:

1. start from current `main` and inspect open PRs/issues before changing anything;
2. prefer repairing, integrating, documenting, or closing a concrete gap over
   creating speculative work;
3. keep setup, architecture, interface, testing, contribution, and agent-facing
   documentation synchronized with current code;
4. distinguish implementation, synthetic evidence, observed real-run evidence,
   accepted conclusions, and unresolved hypotheses;
5. use focused branches/PRs for substantive repository changes and require
   exact-head validation before integration;
6. never weaken a quality/security gate merely to obtain a green check;
7. never represent owner-controlled ChatGPT activity as independent human or
   external scientific review;
8. preserve negative/inconclusive evidence and historical provenance;
9. avoid duplicate issues/PRs by checking current work first;
10. leave a concise public repository record when a run materially changes
    code, documentation, paper evidence, issues, or integration state.

## Relationship to GitHub-native automation

Repository workflows under [`.github/workflows/`](workflows/) remain the
canonical GitHub-native CI, verification, observability, and publication
mechanisms. ChatGPT-side stewardship may inspect those workflows and act on their
evidence, but it does not replace branch protection, required checks, human-only
evidence gates, or explicit integration authority.

## Maintenance rule

This page intentionally lists only roles that are active at the time of the
review. Removed or disabled automation roles should not remain here as if they are
still operating; Git history preserves their provenance. If the live automation
set changes materially, refresh this file rather than accumulating a historical
catalog in the current-state section.
