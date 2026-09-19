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

## Active role

| Role | Repository-facing responsibility |
| --- | --- |
| **IDKmesh Weekly Steward** | Review current code, tests, architecture, human/agent documentation, roadmap/future work, issue/PR overlap, and paper claim-to-evidence alignment; make bounded repository improvements; validate exact integration candidates; and record substantive outcomes publicly. |

The historical name does not imply that this file is a scheduling contract. The
role's cadence may change without changing its repository responsibilities.

## Operating contract

The active steward should:

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
