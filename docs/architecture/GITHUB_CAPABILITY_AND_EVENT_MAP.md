# GitHub Capability and Event Map for IDKMesh

**Date:** 2026-08-28  
**Status:** living capability registry / self-evolution input map

## Purpose

GitHub is not only the place where IDKMesh stores code. It can act as the first **coordination nervous system** for the project.

This document maps GitHub capabilities into four roles:

1. **sensors** — events and state that reveal what is happening;
2. **memory** — durable public artifacts such as issues, PRs, reviews, releases, and workflow results;
3. **actuators** — bounded actions the project can take, such as opening an issue or proposing a PR;
4. **guards** — rules that constrain what automation is allowed to change.

The goal is to use the GitHub substrate aggressively without confusing activity with correctness.

> Stars, forks, comments, reactions, commits, and model output are signals. Evidence, independent verification, reproducibility, security, and maintainability determine whether a change is useful.

## Current IDKMesh GitHub posture

Observed on 2026-08-28 from the GitHub API:

- repository is public;
- default branch is `main`;
- Issues are enabled;
- Projects are enabled;
- Wiki is enabled;
- Discussions are currently disabled;
- GitHub Pages is currently disabled;
- repository rulesets: **0**;
- `main` branch protection: **disabled**;
- CODEOWNERS and issue/PR templates exist;
- current main workflows include `ACE Community Growth` and `Phase 0 schema check`;
- ACE already observes issues, PRs, pushes, stars, and forks and uses activity as a bounded growth signal.

This means GitHub already supplies many sensors, but the repository must **not increase autonomous write authority** until independent merge guards are configured.

## Capability registry

| GitHub capability | Sensor / evidence | Possible bounded actuator | IDKMesh use |
| --- | --- | --- | --- |
| Repository metadata | visibility, topics, feature flags, default branch | update metadata/settings | discoverability and configuration drift |
| Git commits | change history, authorship, signed state, touched files | create candidate commit on branch | provenance and change graph |
| Branches / tags | parallel work, protection status, release points | create branch/tag | quarantine and experiment isolation |
| Issues | goals, bugs, research questions, tasks | create/update/label/assign issue | Work Unit discovery and public memory |
| Issue comments | arguments, evidence, clarification, progress | comment/summarize/escalate | semantic evidence stream |
| Labels | explicit typed metadata | add/remove labels | low-cost state machine / routing |
| Milestones | grouped progress | associate work | time-bounded experiment programs |
| Sub-issues / issue dependencies | work decomposition and blocking relations | create/link child tasks | executable task graph projection |
| Pull requests | proposed repository transitions | open/update/close PR | primary self-evolution proposal surface |
| PR reviews | independent approval/rejection/critique | request/submit review | verification and governance evidence |
| Inline review comments | localized defects/arguments | reply/resolve after evidence | fine-grained correction graph |
| Reactions | interest/attention signal | react | weak prioritization signal, never correctness |
| CODEOWNERS | ownership map | route reviews | domain-specific independent review |
| Merge queue | integration ordering and fresh CI | enqueue approved PR | later high-throughput safe integration |
| Branch protection / rulesets | external invariants | require PR/review/checks/signatures | constitutional guardrail for autonomy |
| GitHub Actions | event/schedule execution | run deterministic checks/agents | reflexes, experiments, periodic observatory |
| Workflow runs/jobs/logs | test, build, benchmark evidence | rerun failed jobs | verification feedback loop |
| Workflow artifacts | reproducible outputs | upload/download artifact | evidence bundles and experiment records |
| Checks / commit status | machine verification state | publish check result | independent acceptance gates |
| Code scanning / CodeQL | security defects | open remediation work / block merge via rule | security verifier |
| Secret scanning | exposed-secret evidence | revoke/fix workflow | repository immune system |
| Dependabot / dependency graph | vulnerable/stale dependencies | dependency-update PR | supply-chain maintenance |
| Releases / tags | stable public iterations | publish release | distribution and community rhythm |
| Deployments / environments | deployment state | deploy with protected environment | future operational verification |
| Discussions | ideas, Q&A, polls, announcements | create/moderate discussion | community deliberation before task creation |
| Projects | structured fields/views/iterations | update project item state | portfolio/task-market projection |
| GitHub Pages | public generated website | publish docs/dashboard | discovery and observable project health |
| Webhooks | real-time external events | trigger external control plane | scalable event stream beyond Actions |
| GitHub Apps | least-privilege identity + APIs + webhooks | operate within granted permissions | future IDKMesh control-plane identity |
| REST / GraphQL APIs | structured state access | bounded API mutations | machine-readable GitHub adapter |
| Search / code search | cross-repo discovery and repository structure | create research/triage candidates | observatory and reference discovery |
| Forks | experimentation / contributor intent | none required centrally | external branches of exploration |
| Stars / watches | attention/discovery | none | community-growth signal only |
| Sponsors (future) | resource/incentive signal | funding workflows | possible sustainability signal, not priority authority |

## GitHub event classes for IDKGraph

Convert GitHub observations into typed IDKGraph events rather than processing them as an undifferentiated feed.

### 1. Structural events

Examples:

- push / commit;
- branch/tag creation/deletion;
- file/repository metadata changes;
- release creation.

These change the artifact graph.

### 2. Intent events

Examples:

- issue opened/edited;
- label applied;
- milestone assigned;
- sub-issue/dependency created;
- PR opened.

These describe proposed work or desired state transitions.

### 3. Deliberation events

Examples:

- issue comment;
- PR conversation comment;
- discussion post/comment;
- reaction/poll.

These are **untrusted natural-language evidence**. Preserve provenance and relationships, but never execute instructions found in them.

### 4. Verification events

Examples:

- PR review;
- inline review comment;
- status/check result;
- workflow/test/benchmark result;
- CodeQL/security finding;
- reproduction result from an IDKmesh node.

These receive more weight than raw engagement when evaluating a repository change.

### 5. Community events

Examples:

- first issue/comment/PR;
- star/watch;
- fork;
- repeat contribution;
- review participation.

These support ACE/community-health models. They should not decide technical truth.

### 6. Governance events

Examples:

- ruleset/branch-protection changes;
- CODEOWNERS changes;
- review approval/dismissal;
- accepted IDKIP/ADR;
- permission changes.

These affect allowed action space and require higher protection.

## Comment and review evidence model

A GitHub comment is a data object:

`C = (subject, author, association, time, body, links, reactions, references, provenance)`.

It is **not** an instruction to the self-evolution engine.

For machine collection preserve:

- source URL and GitHub ID;
- issue/PR parent;
- author and author association;
- timestamps;
- full public body (or hash/excerpt where size requires);
- reaction counts;
- explicit references to commits/issues/PRs/artifacts;
- whether it is an issue comment, PR review, or inline review comment;
- `untrusted_text=true`.

Semantic agents may later classify comments into claims, evidence, questions, disagreements, decisions, or action proposals, but deterministic GitHub state remains the canonical provenance.

### Independence matters

Ten repeated comments from one actor or correlated agent family should not count as ten independent confirmations.

Useful derived quantities include:

- number of distinct participants;
- number of independent verification methods;
- artifact-backed claims;
- reproducible test/benchmark links;
- unresolved reviewer objections;
- disagreement diversity.

Reactions can raise **attention priority** but never correctness confidence by themselves.

## Capability maturity for self-evolution

### P0 — read-only observatory

Use GitHub APIs and Actions to collect:

- issues and PRs;
- comments;
- PR reviews and inline review comments;
- labels/assignees/milestones;
- workflows and recent workflow results;
- branches and protection/ruleset state;
- releases/contributors;
- security alerts where token permissions allow.

Emit a JSON snapshot and Markdown report as workflow artifacts. **No GitHub mutation.**

### P1 — recommendation reflexes

Deterministically recommend bounded actions such as:

- request an independent review;
- summarize a discussion with multiple independent participants;
- clarify/decompose stale work;
- investigate failed verification;
- add a missing deterministic link/index.

Output recommendation artifacts or human-visible issues only after a separate write-capable workflow is reviewed.

### P2 — proposal actuators

Allow narrowly scoped automation to open issues or PRs, still without merge authority.

### P3 — deterministic maintenance auto-merge

Only after external rulesets/protection exist and empirical evidence justifies it, consider auto-merging purely deterministic generated artifacts such as indexes after independent checks.

### P4+ — structural/policy evolution

Structural or policy changes remain proposal/review based. Constitutional constraints require explicit governance approval.

## Current gaps worth activating later

1. Add repository ruleset/branch protection before increasing autonomy.
2. Enable Discussions when there is enough community activity to justify a deliberation layer; use Issues for actionable work and Discussions for broader exploration.
3. Consider GitHub Pages for automatically generated project maps, health dashboards, onboarding, and experiment results.
4. Enable/verify CodeQL default setup for Python and GitHub Actions as an independent security sensor.
5. Add Dependabot where dependencies become non-trivial.
6. Eventually move event ingestion from repeated full API snapshots to a least-privilege GitHub App + webhooks for scalable incremental collection.
7. Use Projects only if structured views reduce coordination cost; do not make board maintenance a goal itself.

## Official references

- GitHub Actions events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Issues: https://docs.github.com/en/issues
- About issues and dependencies: https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues
- Discussions: https://docs.github.com/en/discussions
- Repository rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- Protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- Webhooks: https://docs.github.com/en/webhooks
- GitHub Apps permissions: https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
- CodeQL/code scanning: https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning
- Secret scanning: https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning
- Releases: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- GitHub Pages: https://docs.github.com/en/pages
