# IDKmesh Automation Operating Model — 2026-09-19

> Repository: `MSKazemi/idkmesh`  
> Scheduler timezone: `Europe/Rome`  
> Snapshot date: 2026-09-19  
> Purpose: one source of truth for IDKmesh automation roles, repository-native scheduled workflows, recommended ChatGPT agent cadences, overlap rules, and activation policy.

## Executive summary

IDKmesh should use two automation layers with different responsibilities:

1. **GitHub Actions** owns deterministic checks, scheduled repository measurements, security scanning, branch/evolution audits, and artifact production.
2. **ChatGPT scheduled agents** should consume those signals and perform bounded reasoning-heavy work: prioritization, PR integration, repairs, implementation, documentation, research synthesis, release/growth work, and paper maintenance.

At this snapshot there are **no active ChatGPT scheduled tasks** for IDKmesh. The repository contains **52 GitHub Actions workflow files**, of which **9 have recurring schedules**.

Live repository pressure is high: the current snapshot has **10 open PRs (9 ready and 1 draft)** and **31 open issues**. Under the swarm control rules, this is a **CONSOLIDATE** state because the ready/open PR queue is above the build threshold. The scheduler should therefore prioritize integration, CI/reliability repair, documentation synchronization, and queue reduction before creating new feature PRs.

## Design principles

- Prefer **convergence over fan-out** while the PR queue is saturated.
- One role owns each system boundary; do not create generic workers that race specialists.
- Maximum **3 open agent-authored implementation PRs** globally.
- Maximum **1 open PR per specialist role/branch prefix**.
- One substantive repository outcome per agent run.
- No agent pushes directly to `main`.
- No agent approves its own work or substitutes owner-controlled AI output for independent human/external evidence.
- Never weaken tests, checks, security controls, branch rules, or evidence standards to obtain a green result.
- Never commit secrets, tokens, real `.env` values, or private credentials.
- File overlap with an active PR is a stop/repair signal.
- A no-op is correct when there is no safe high-value action.
- Repository-native scheduled workflows should not be duplicated by ChatGPT polling.
- ChatGPT scheduled tasks cannot run more frequently than once per hour; use staggering rather than sub-hour polling.

---

# Layer 1 — Repository-native scheduled GitHub Actions

GitHub cron is UTC. The Europe/Rome wall-clock time therefore shifts by one hour between CET and CEST.

| Workflow | File | Cron (UTC) | Approx. Rome time today (CEST) | Role |
|---|---|---|---|---|
| Branch Convergence Audit | `.github/workflows/branch-convergence-audit.yml` | `17 4 * * *` | Daily 06:17 | Audit branch convergence, produce deterministic merge planning evidence, monitor API budget, and upload artifacts. |
| IDKMesh Evolution Loop | `.github/workflows/evolution-loop.yml` | `17 5 * * *` | Daily 07:17 | Maintain trusted evolution/evidence state, validate checkpoint lineage, run mathematical/evolution tests, and emit evolution artifacts. |
| Free Resource Source Audit | `.github/workflows/free-resource-source-audit.yml` | `23 6 * * *` | Daily 08:23 | Check freshness/liveness of free-resource evidence without silently re-dating sources; upload freshness evidence. |
| ACE Cohort Observer | `.github/workflows/ace-cohort-observer.yml` | `17 6 * * 1` | Monday 08:17 | Build ACE cohort snapshots, review-load/capacity observations, and human-review recommendations without auto-creating a new cohort. |
| Collaboration Observables | `.github/workflows/collaboration-observables.yml` | `37 5 * * 1` | Monday 07:37 | Collect bounded collaboration metadata, structural debt metrics, and preregistered review-latency observations. |
| CodeQL | `.github/workflows/codeql.yml` | `43 4 * * 1` | Monday 06:43 | Run Python CodeQL analysis and code-scanning security checks. |
| Mathematical Evolution Kernel | `.github/workflows/mathematical-evolution-kernel.yml` | `43 4 * * 2` | Tuesday 06:43 | Validate mathematical evolution invariants across supported Python versions and publish deterministic evidence. |
| Repository Mathematical Portfolio | `.github/workflows/repository-math-portfolio.yml` | `29 6 * * 1,4` | Monday/Thursday 08:29 | Maintain portfolio/checkpoint evidence and combine trusted repository/evolution signals. |
| OpenSSF Scorecard | `.github/workflows/scorecard.yml` | `19 3 * * 6` | Saturday 05:19 | Evaluate supply-chain/security posture and upload SARIF/diagnostic evidence. |

## What ChatGPT should not duplicate

The ChatGPT layer should read or react to the outputs above instead of independently re-running equivalent audits. In particular:

- do not create a separate hourly branch-drift scanner when Branch Convergence Audit already exists;
- do not create another scheduled CodeQL/security-scorecard poller;
- do not create an hourly evolution-metrics collector;
- do not repeatedly probe free-resource freshness outside the native audit unless acting on a concrete stale-source finding;
- do not rebuild ACE cohort/collaboration metrics in parallel.

---

# Layer 2 — Recommended ChatGPT agent set

The preferred operating set is **9 roles**, but only the first three should be high-frequency. The rest are deliberately slower to reduce duplicate work and reviewer load.

| Priority | Agent | Recommended cadence | Suggested minute/time | Main role | Write behavior in current CONSOLIDATE mode |
|---:|---|---|---|---|---|
| 1 | Swarm Governor | Every 2 hours | `:05` | Determine FREEZE / CONSOLIDATE / BUILD, enforce concurrency, deduplicate work, pick the highest-leverage blocker | Mostly observe; update one coordination surface only when state materially changes |
| 2 | PR Integrator | Every 2 hours | `:35` | Exact-head PR review, CI/review/conflict recovery, safe merge/close/rebase decisions | Move one existing PR toward a correct disposition; no feature fan-out |
| 3 | Reliability & Repository Health | Every 4 hours | `:50` | CI, tests, bugs, exceptions, security, workflow failures, reproducibility, branch hygiene | Repair one existing failure/regression/blocker and add regression evidence |
| 4 | Backend & Interoperability | Every 6 hours | `:15` | Backend/core Python, API contracts, A2A/MCP/ACP, configuration, serialization, retries/timeouts | Repair/document existing backend/interop work; create no new feature PR while consolidated |
| 5 | Product & Developer Experience | Every 12 hours | `:25` | CLI/install/package, Pages/product surface, quickstarts, devcontainer, user-facing UX | Improve existing product/onboarding work without opening extra feature streams |
| 6 | Documentation & Paper Sync | Every 12 hours | `:45` | README, agent docs, architecture, API/config docs, roadmap, CHANGELOG, paper/claim-evidence synchronization | Repair current-code/PR documentation drift; keep scientific claims conservative |
| 7 | Research & Standards Scout | Tuesday + Friday | 09:30 Europe/Rome | A2A/MCP/ACP, agent runtimes, sandboxing, HPC/distributed systems, relevant upstream security/ecosystem changes | Produce at most one evidence-backed decision input; implementation only for an active blocker |
| 8 | Growth & Release | Monday + Wednesday + Friday | 18:30 Europe/Rome | Release readiness, demos, Pages, reusable integrations, newcomer funnel, contributor conversion | Finish existing release/onboarding work; avoid campaign/feature fan-out |
| 9 | Weekly Deep Steward | Saturday | 11:00 Europe/Rome | Whole-repository code/docs/architecture/roadmap/paper review; identify high-value next work | Prefer a single synchronization PR or a small set of well-scoped issues, not broad implementation fan-out |

## Why these frequencies are better

### Governor and PR Integrator: every 2 hours

The current bottleneck is integration pressure, not lack of ideas. These two jobs should react fastest because a merge, CI failure, conflict, or human review can immediately change what work is safe next.

Hourly execution would create a large amount of repeated inspection for limited additional value. Every two hours is a better default while keeping a responsive control loop.

### Reliability: every 4 hours

Reliability can directly unblock multiple PRs, but an hourly mutating reliability worker risks overlapping with PR integration and GitHub-native checks. Four hours is frequent enough to catch broken CI, regressions, workflow drift, and security/reproducibility problems without constant churn.

### Backend: every 6 hours

Backend/API work is important but should not generate new branches when the queue is already saturated. Every six hours keeps the role available for repair/compatibility work while reducing speculative implementation pressure.

### Product/DX and Docs/Paper: every 12 hours

These roles are naturally downstream of code and integration events. Twice daily is enough to keep setup, examples, configuration, docs, paper claims, and user-facing surfaces synchronized without editing the same files after every small commit.

### Research: twice per week

Standards and ecosystem changes rarely justify daily repository writes. A twice-weekly scan is enough for A2A/MCP/ACP, runtime, sandbox, HPC/distributed-compute, dependency, and ecosystem changes. Urgent security advisories should be handled by Reliability when they affect dependencies actually used by the repository.

### Growth/Release: three times per week

Community and adoption metrics need time to accumulate. Running growth automation hourly or even daily can encourage shallow activity. Three focused runs per week are more appropriate for release readiness, demos, onboarding, and contributor conversion.

### Weekly Deep Steward

A weekly full review is the right place for broader architecture, roadmap, documentation completeness, and manuscript synchronization. This separates slow strategic maintenance from fast operational repair.

---

# Ownership map

| Project surface | Primary ChatGPT owner | Secondary support | Native GitHub signal |
|---|---|---|---|
| PR queue / mergeability | PR Integrator | Governor | Branch Convergence Audit |
| CI / flaky tests / regression bugs | Reliability & Repository Health | PR Integrator | PR workflows + CodeQL |
| Security / workflow hardening | Reliability & Repository Health | Research Scout | CodeQL + OpenSSF Scorecard |
| Backend/core Python | Backend & Interoperability | Reliability | project CI |
| A2A / MCP / ACP / protocol adapters | Backend & Interoperability | Research Scout + Docs | interoperability checks |
| Configuration / `.env.example` | Backend & Interoperability | Product/DX + Docs | config/schema tests |
| CLI / install / packaging / Pages | Product & Developer Experience | Growth + Reliability | packaging/CI workflows |
| README / contributor docs | Documentation & Paper Sync | Product/DX | link/schema checks |
| Architecture / roadmap | Documentation & Paper Sync | Research + Governor | evolution evidence |
| Paper / claim-to-evidence map | Documentation & Paper Sync | Research | evolution/portfolio artifacts |
| Free/open compute sources | Backend when implementing; Research when evaluating | Reliability | Free Resource Source Audit |
| ACE/community capacity | Governor | Growth | ACE Cohort Observer + Collaboration Observables |
| Release / demo / adoption | Growth & Release | Product/DX + Docs | release/build workflows |
| Repository-wide strategic audit | Weekly Deep Steward | all roles as evidence sources | all scheduled native workflows |

---

# Work-mode contract

## FREEZE

Enter FREEZE when required CI/main integrity is materially broken, a security/governance blocker exists, or the next necessary action requires independent human/external evidence.

Allowed: diagnose/repair the blocker, improve directly related tests/docs, record a precise blocker.

Not allowed: new feature PRs, new growth experiments, speculative architecture, duplicate branches.

## CONSOLIDATE

Enter CONSOLIDATE when any of the following is true:

- ready/open PR pressure is high (default threshold: `>= 5`);
- draft PRs `>= 2`;
- ACE/reviewer capacity is low;
- overlapping autonomous work exists;
- stale/superseded work is competing with current main.

Allowed: repair, rebase when evidence remains valid, test, document, resolve conflicts, close superseded autonomous work with provenance preserved, merge eligible work.

Not allowed: new feature fan-out.

**Current snapshot: CONSOLIDATE.**

## BUILD

Enter BUILD only when:

- required CI/main is healthy;
- ready/open PRs are below the pressure threshold;
- reviewer capacity exists;
- no human-only evidence gate blocks the selected task;
- fewer than 3 agent-authored implementation PRs are open;
- no same-role PR is active;
- target files do not overlap active work.

A specialist may then create one bounded coherent PR.

---

# Activation order

Do not activate all roles simultaneously.

## Phase A — queue reduction

Activate first:

1. Swarm Governor
2. PR Integrator
3. Reliability & Repository Health
4. Documentation & Paper Sync

Run this set until open PR pressure drops below the BUILD threshold and main/CI are healthy.

## Phase B — controlled implementation

Then enable:

5. Backend & Interoperability
6. Product & Developer Experience

These roles still obey the global 3-PR budget and one-PR-per-role rule.

## Phase C — slower expansion

Then enable:

7. Research & Standards Scout
8. Growth & Release
9. Weekly Deep Steward

This prevents a fresh burst of research/growth/documentation work from competing with integration.

---

# Recommended scheduler definitions

These are the intended cadences if/when activated in ChatGPT.

```text
Swarm Governor:
  RRULE:FREQ=HOURLY;INTERVAL=2;BYMINUTE=5

PR Integrator:
  RRULE:FREQ=HOURLY;INTERVAL=2;BYMINUTE=35

Reliability & Repository Health:
  RRULE:FREQ=HOURLY;INTERVAL=4;BYMINUTE=50

Backend & Interoperability:
  RRULE:FREQ=HOURLY;INTERVAL=6;BYMINUTE=15

Product & Developer Experience:
  RRULE:FREQ=HOURLY;INTERVAL=12;BYMINUTE=25

Documentation & Paper Sync:
  RRULE:FREQ=HOURLY;INTERVAL=12;BYMINUTE=45

Research & Standards Scout:
  RRULE:FREQ=WEEKLY;BYDAY=TU,FR;BYHOUR=9;BYMINUTE=30

Growth & Release:
  RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=18;BYMINUTE=30

Weekly Deep Steward:
  RRULE:FREQ=WEEKLY;BYDAY=SA;BYHOUR=11;BYMINUTE=0
```

For day/time schedules, use `Europe/Rome` timezone semantics so DST is handled as local project time.

---

# Agent output contract

Every mutating agent should report the same compact record:

- operating mode observed;
- repository/main/head SHA examined;
- issue/PR selected, if any;
- why it was the highest-value safe action;
- files/contracts changed;
- tests/checks executed and exact evidence;
- documentation/CHANGELOG updates;
- security/backward-compatibility/scientific risks;
- branch/PR URL or blocker;
- provenance: AI/tool-produced, human-reviewed, independently verified, or not independently verified.

Do not report activity count as success. Prefer metrics such as:

- PR time-to-correct-disposition;
- CI recurrence rate;
- stale/conflict rate;
- accepted change per reviewer minute;
- regression rate;
- install/run success from clean environments;
- documentation drift;
- duplicate autonomous work incidents;
- external contributor conversion and recurrence;
- verified useful output per unit of human attention.

---

# Relationship to existing planning documents

This document is the current operating recommendation and should be read together with:

- `docs/planning/AUTONOMOUS_SWARM_V2_2026-09-17.md` — earlier role/control design;
- `docs/planning/AUTOMATION_JOBS_INVENTORY_2026-09-17.md` — historical inventory snapshot;
- `docs/planning/REPOSITORY_IMPROVEMENT_LOOP.md` — evidence-bearing iteration rules;
- `docs/planning/BRANCH_CONVERGENCE_POLICY.md` — branch/merge evidence rules;
- `docs/planning/CURRENT_PRIORITIES.md` — historical priority snapshot; recompute live state before acting.

The scheduler state and repository queue are dynamic. This document should be refreshed whenever active task topology, PR pressure, native scheduled workflows, or project control rules materially change.
