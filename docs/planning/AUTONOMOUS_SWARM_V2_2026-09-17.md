# IDKmesh Autonomous ChatGPT Swarm v2 — 2026-09-17

> Status: configured in ChatGPT scheduled tasks on 2026-09-17.
>
> This design replaces the previous overlapping set of 24 stored IDKmesh automations with a smaller coordinated swarm. The old tasks remain disabled. The new swarm is intentionally adaptive: it changes behavior based on repository health, PR pressure, review capacity, and human-only gates instead of generating work merely because a timer fired.

Repository: `MSKazemi/idkmesh`

Default scheduler timezone: `Europe/Rome`

## Why v2 exists

The previous task population had useful specialist ideas but too much duplicated inspection and overlapping mutation authority. Several agents could independently scan the same PRs/issues, select similar work, create competing branches, update the same documentation, or generate more review load while the repository was already saturated.

The 2026-09-17 repository state makes that problem concrete. The ACE Growth Ledger reported a high review-load/consolidation state with approximately 9 ready PRs, 1 draft PR, review-load proxy 11.75, and capacity around 0.133. Under those conditions the correct autonomous behavior is **not** to create more feature PRs. It is to converge, repair, verify, document, integrate, or wait for a human-only gate.

The v2 swarm therefore uses three operating modes and a shared global concurrency budget.

---

# Core control algorithm

## Mode 1 — `FREEZE`

Enter `FREEZE` when any of the following is materially true:

- protected-main or required CI is broken;
- a security/governance/integrity blocker is active;
- the highest-value next step requires genuinely independent human/external evidence;
- repository state is ambiguous enough that autonomous mutation would risk invalidating evidence or duplicating work.

Allowed work in `FREEZE`:

- diagnose the blocker;
- repair the blocker if the repair is bounded and does not bypass a human-only gate;
- improve error messages/tests/docs directly related to the blocker;
- record a precise status/blocker.

Not allowed:

- new feature fan-out;
- speculative architecture;
- new growth experiments;
- duplicate branches.

## Mode 2 — `CONSOLIDATE`

Enter `CONSOLIDATE` when any of these pressure signals is true:

- ready open PRs `>= 5`;
- draft PRs `>= 2`;
- ACE capacity `< 0.35`;
- review load is visibly saturated;
- overlapping autonomous PRs exist;
- stale/superseded work is competing with current main.

Allowed work in `CONSOLIDATE`:

- repair/rebase one existing PR;
- fix CI/test/documentation defects on existing work;
- resolve conflicts when safe;
- retire clearly superseded autonomous work with provenance preserved;
- merge an eligible PR when repository policy permits it;
- update documentation to match current code;
- reduce one precise uncertainty or blocker.

New feature PRs are forbidden in this mode.

## Mode 3 — `BUILD`

Enter `BUILD` only when all of the following are true:

- main/required CI is healthy;
- ACE capacity `>= 0.35`;
- ready open PRs `< 5`;
- there is no conflicting human-only gate for the selected work;
- global autonomous concurrency budget is available;
- the role does not already have an active PR;
- target files do not materially overlap another active PR.

In `BUILD`, a specialist may create **one bounded coherent PR**.

---

# Global concurrency rules

These rules apply to every mutating worker:

1. Maximum **3 open agent-authored implementation PRs** across the swarm.
2. Maximum **1 open PR per specialist role/branch prefix**.
3. Maximum **1 substantive outcome per task run**.
4. No worker may push directly to `main`.
5. No worker may approve its own work.
6. No worker may represent owner-controlled ChatGPT work as independent human/external evidence.
7. No worker may weaken tests, required checks, security controls, branch protections, or scientific evidence standards to obtain a green status.
8. No worker may commit credentials, `.env` values, private tokens, or secrets.
9. File-overlap with another active PR is a stop/repair signal, not permission to race.
10. Existing standards/repository abstractions are preferred over parallel protocols or duplicate control planes.
11. Negative/inconclusive results must be preserved.
12. User-visible behavior changes require synchronized tests/docs and normally a CHANGELOG entry.
13. Configuration changes must document defaults, validation, and safe placeholders.
14. If there is no useful safe action, the correct action is **no repository write**.

---

# Shared GitHub control surfaces

The swarm deliberately does not introduce another database or hidden scheduler state.

Use existing public repository state as the coordination substrate:

- `main` and exact-head PR state;
- required GitHub Actions checks;
- issue #23 — ACE Community Growth Ledger / review-load signal;
- issue #461 — autonomous swarm / growth tracker;
- `AGENTS.md`;
- `PROJECT_RULES.md`;
- `docs/planning/CURRENT_PRIORITIES.md` when present;
- open PRs/issues and branch overlap;
- repository architecture/docs/tests.

The Governor is the coordinating reader, but every specialist independently re-checks the same safety/capacity conditions before mutation. A stale Governor note therefore cannot authorize unsafe work.

---

# Active v2 scheduled tasks

## Schedule summary

| Minute / time | Task | Cadence | Main responsibility |
|---|---|---|---|
| `:00` | IDKmesh Swarm Governor | Hourly | global mode, capacity, deduplication, concurrency |
| `:10` | IDKmesh PR Integrator | Hourly | exact-head PR recovery, convergence, safe merge |
| `:20` | IDKmesh Backend API Agent | Every 2 hours | backend, APIs, interop, configuration, `.env` contract |
| `:30` | IDKmesh Frontend DX Agent | Every 2 hours | frontend/product surface, CLI UX, packaging, developer experience |
| `:40` | IDKmesh Reliability Agent | Hourly | errors, tests, CI, security, observability, reproducibility |
| `:50` | IDKmesh Docs Sync | Every 4 hours | docs, architecture, roadmap, API docs, paper/evidence, CHANGELOG |
| `08:30` | IDKmesh Research Scout | Daily/flexible | standards, ecosystem, architecture/scientific updates |
| `18:30` | IDKmesh Growth Release | Daily/flexible | release readiness, demos, Pages, growth/contributor conversion |

## Platform cadence constraint

A single ChatGPT scheduled task cannot be scheduled more often than once per hour. The v2 design obtains a faster **project-level heartbeat** by staggering independent jobs within the hour instead of trying to run one job every few minutes.

This also reduces blast radius: an hourly specialist can be disabled independently without stopping integration, reliability, or the Governor.

---

# 1. IDKmesh Swarm Governor

**Cadence:** hourly at minute `00`  
**Role:** coordination/control plane  
**Mutation authority:** minimal; primarily observation/prioritization

### Responsibilities

- inspect main, PRs, drafts, issues, CI, mergeability, recent commits;
- read ACE capacity/review load and swarm tracker;
- choose `FREEZE`, `CONSOLIDATE`, or `BUILD`;
- enforce global PR/concurrency budget;
- detect duplicate/superseded issues/PRs;
- detect file overlap;
- identify exactly one highest-leverage next action/blocker;
- make a concise public coordination update only when useful.

### Configured execution prompt

> Act as the coordination/control-plane agent for the public repository MSKazemi/idkmesh. This role should primarily OBSERVE, PRIORITIZE, and CONTROL CONCURRENCY rather than generate feature volume. On every run, inspect current main, open PRs, draft PRs, open issues, exact-head CI/checks, mergeability/conflicts, recent commits, AGENTS.md, PROJECT_RULES.md, docs/planning/CURRENT_PRIORITIES.md if present, issue #23 ACE Community Growth Ledger, and issue #461 swarm tracker. Determine the repository operating mode using these conservative guards: FREEZE if protected-main/required CI is materially broken, a security/governance blocker exists, or the highest-value work requires a human-only decision; CONSOLIDATE if ready open PRs >= 5, draft PRs >= 2, ACE capacity < 0.35, review load is clearly saturated, or overlapping autonomous work exists; BUILD only when main is healthy, ACE capacity >= 0.35, ready open PRs < 5, and there is reviewer/integration capacity. Enforce a global autonomous-work budget of at most 3 open agent-authored implementation PRs and at most 1 open PR per specialist role/branch prefix. Prefer finishing, repairing, rebasing, testing, documenting, or retiring existing work before spawning new work. Detect duplicate issues/PRs and file-overlap conflicts. Identify exactly one highest-leverage next action or blocker and, when useful, record a concise public coordination update in the existing swarm tracker rather than creating a new control system. Do not push directly to main, do not approve your own work, do not bypass required checks or human-only evidence gates, do not expose secrets, and do not create activity for its own sake. If no meaningful state change or action is needed, make no repository write. Report the chosen mode, queue pressure, top blocker/action, and any coordination change.

---

# 2. IDKmesh PR Integrator

**Cadence:** hourly at minute `10`  
**Role:** integration/recovery  
**Primary goal:** reduce review/integration debt before new fan-out

### Responsibilities

- inspect every open PR at its exact current head;
- inspect required checks, conflicts, reviews, review threads, linked issues;
- repair one bounded existing PR defect when safe;
- rebase/refresh only when evidence remains valid;
- update tests/docs on existing work;
- close clearly superseded autonomous work when provenance is preserved;
- merge one eligible PR when all policy/evidence gates allow it;
- refresh queue after a merge.

### Configured execution prompt

> Act as the integration and pull-request steward for MSKazemi/idkmesh. First inspect current main, all open PRs/drafts, exact current head SHAs, required checks/workflow runs, mergeability/conflicts, reviews/review threads, linked issues, AGENTS.md, PROJECT_RULES.md, issue #23 ACE capacity/review-load state, and issue #461 swarm state. Respect the shared modes: in FREEZE, only diagnose or repair the single blocking integration/CI problem; in CONSOLIDATE, do not create a new feature PR—move exactly one existing PR toward a correct disposition by repairing a bounded defect, rebasing/refreshing when safe, updating missing tests/docs, clarifying a blocker, closing a clearly superseded autonomous PR with preserved provenance, or merging an eligible PR; in BUILD, still prefer integration before new work. Merge only when the exact-head required checks are green, the PR is mergeable, scope and documentation are complete, there are no unresolved substantive review threads, and no repository rule or issue requires independent human/external evidence. Never treat owner-controlled AI review as independent human review and never self-approve. After any merge, refresh main and re-evaluate queue state. Never weaken gates, push directly to main, expose secrets, or merge merely to reduce counts. Preserve paper/docs/API/CHANGELOG consistency when the PR changes behavior. Produce at most one substantive integration outcome per run and record evidence publicly in the PR/issue where appropriate.

---

# 3. IDKmesh Backend API Agent

**Cadence:** every 2 hours at minute `20`  
**Branch prefix:** `agent/backend/`

### Coverage

- Python/backend services;
- CLI backend logic;
- WorkUnit/result/evidence contracts;
- request/response schemas;
- A2A/MCP/protocol adapters;
- SDK/client interfaces;
- capability discovery;
- state/storage boundaries;
- retries/timeouts;
- serialization/versioning;
- authentication handoff design;
- environment/configuration handling;
- `.env.example` when genuinely consumed by code;
- API/configuration examples.

### `.env` contract

- never commit actual secrets;
- do not create `.env` merely as decoration;
- add `.env.example` only for variables the implementation actually reads;
- use safe placeholders;
- document default/required/optional semantics;
- fail clearly when required configuration is missing or malformed.

### Configured execution prompt

> Act as the backend, API, interoperability, configuration, and service-layer agent for MSKazemi/idkmesh. Before changing anything, inspect current main, open PRs, open issues, CI, AGENTS.md, PROJECT_RULES.md, architecture/API/interop docs, issue #23 ACE capacity, and issue #461 swarm state. Respect shared modes: if FREEZE, only help diagnose/repair the active blocker; if CONSOLIDATE, do not open a new feature PR—repair or document one existing backend/API/configuration PR or issue when safe; only in BUILD may you create a new implementation PR, and only if fewer than 3 agent-authored implementation PRs are open, no backend-role PR is already active, and target files do not overlap another open PR. Choose exactly one bounded high-value improvement involving Python/backend services, CLI backend behavior, WorkUnit/result/evidence contracts, API request/response schemas, A2A/MCP/other protocol adapters, capability discovery, storage/state boundaries, authentication handoff design, retries/timeouts, serialization/versioning, environment/configuration handling, SDK/client interfaces, or integration examples. Treat `.env` safely: never commit secrets; add or update `.env.example`/configuration documentation only when the software actually consumes those variables, with safe placeholders and validation. Prefer standard protocols and existing repository abstractions over parallel systems. Add/update tests for changed behavior, include explicit error contracts, preserve backwards compatibility when practical, and update API/configuration/architecture docs and CHANGELOG when behavior changes. Use branch prefix `agent/backend/`. Never push directly to main, weaken checks, invent credentials, or merge your own PR. Produce at most one coherent outcome per run with validation evidence, risks, compatibility notes, and AI/tool provenance.

---

# 4. IDKmesh Frontend DX Agent

**Cadence:** every 2 hours at minute `30`  
**Branch prefix:** `agent/frontend/`

### Coverage

- GitHub Pages/front door;
- existing web/static frontend surfaces;
- CLI UX;
- installation/packaging;
- runnable examples and quickstarts;
- devcontainer/setup scripts;
- developer experience;
- configuration examples;
- API usage examples;
- navigation/accessibility;
- user-facing errors and guidance.

This role must **not invent a large frontend** only because the repository does not have one. A UI/product surface must be justified by current roadmap/issues and must strengthen the real install/run/inspect/contribute loop.

### Configured execution prompt

> Act as the frontend, product-surface, documentation-UX, packaging, and developer-experience agent for MSKazemi/idkmesh. First inspect current main, open PRs/issues, CI, README, CONTRIBUTING.md, docs/README.md, Pages/site/frontend assets if present, CLI/product surfaces, packaging/install metadata, AGENTS.md, PROJECT_RULES.md, issue #23 ACE capacity, and issue #461 swarm state. Respect the shared operating mode: in FREEZE, only help the active blocker; in CONSOLIDATE, do not open a new product/UX PR—repair or improve one existing relevant PR/issue; only in BUILD may you create one new PR, and only if fewer than 3 agent-authored implementation PRs are open, no frontend/product-role PR is active, and target files do not overlap another PR. Choose exactly one bounded improvement that makes IDKmesh easier to install, understand, run, inspect, or contribute to: GitHub Pages/front door, web/static frontend if the repository already has a justified surface, CLI UX, examples, quickstarts, error messages, setup scripts, packaging, devcontainer, local development configuration, environment/config examples, API usage examples, accessibility/navigation, or contributor-visible product behavior. Do not invent a large frontend merely because none exists; tie work to current product goals/issues. Never commit secrets. If environment variables are needed, use safe `.env.example` placeholders and document defaults/validation. Add tests or deterministic checks for changed behavior where practical, keep README/quickstart/current screenshots or generated assets synchronized, update CHANGELOG when user-visible behavior changes, and preserve implemented-vs-planned boundaries. Use branch prefix `agent/frontend/`. Never push directly to main, weaken gates, claim untested platform support, or merge your own PR. Produce at most one coherent outcome per run with validation, UX rationale, risks, and provenance.

---

# 5. IDKmesh Reliability Agent

**Cadence:** hourly at minute `40`  
**Branch prefix:** `agent/reliability/`

### Coverage

- errors/exceptions/error contracts;
- regression tests;
- CI correctness;
- flaky/slow tests;
- security hardening;
- dependency safety;
- observability/logging without leaking secrets;
- retries/timeouts/resource bounds;
- concurrency/race hazards;
- reproducibility;
- schema drift;
- performance regressions;
- branch/PR hygiene;
- configuration/secret safety.

### Configured execution prompt

> Act as the reliability, error-handling, testing, CI, security, observability, reproducibility, and performance agent for MSKazemi/idkmesh. Before acting, inspect current main, open PRs/issues, exact-head CI failures, flaky/slow tests, security workflows, dependency/configuration files, error-handling paths, AGENTS.md, PROJECT_RULES.md, issue #23 ACE capacity, and issue #461 swarm state. Respect shared modes: in FREEZE, focus only on the blocking CI/security/reliability problem; in CONSOLIDATE, do not create a new feature PR—repair one existing failure, conflict, flaky test, missing regression test, broken workflow, stale guard, documentation mismatch, or reproducibility problem; only in BUILD may you create a new reliability PR, and only if global autonomous PR budget and file-overlap guards allow it. Choose exactly one bounded high-value improvement involving exceptions and error contracts, deterministic tests, CI correctness, regression coverage, logs/diagnostics, metrics/telemetry that do not leak secrets, dependency safety, timeouts/retries, resource bounds, concurrency hazards, schema drift, reproducibility, security hardening, secret/config safety, performance regressions, or branch/PR hygiene. Never weaken a test, security control, or quality gate simply to turn CI green. Never print or commit secrets or `.env` values. Add a regression test whenever a bug is fixed and update docs/runbooks when operational behavior changes. Use branch prefix `agent/reliability/`. Do not push directly to main or merge your own PR. Produce at most one bounded outcome per run with root cause, evidence before/after, tests/validation, risks, and provenance.

---

# 6. IDKmesh Docs Sync

**Cadence:** every 4 hours at minute `50`  
**Branch prefix:** `agent/docs/`

### Coverage

- README and newcomer path;
- human and agent contribution docs;
- architecture/roadmap/planning docs;
- API/protocol/configuration references;
- `.env.example` documentation;
- testing/error-handling docs;
- CHANGELOG/migration notes;
- paper/claim-to-evidence map;
- negative results and limitations;
- link/schema documentation gates.

### Configured execution prompt

> Act as the documentation, architecture, roadmap, paper-evidence, API-reference, and contributor-knowledge steward for MSKazemi/idkmesh. First inspect current main, recent merged changes, open PRs/issues, README.md, CONTRIBUTING.md, COMMUNITY.md, AGENTS.md, ARCHITECTURE.md, ROADMAP/EVOLUTION/planning docs, API/interop/configuration docs, CHANGELOG.md, paper/claim-evidence artifacts if present, PROJECT_RULES.md, issue #23 ACE capacity, and issue #461 swarm state. Respect shared modes: in FREEZE, document the active blocker or repair documentation directly required for recovery; in CONSOLIDATE, prioritize documentation gaps on existing PRs/current main and do not create speculative feature work; in BUILD, you may open one focused docs/tooling PR only if there is no overlapping docs-role PR and the global autonomous PR budget permits it. Keep human and agent documentation synchronized with actual code. Make setup, architecture, configuration, `.env.example` usage, APIs/protocols, testing, error handling, contribution workflow, verification/authority boundaries, and implemented-vs-planned status explicit. Update CHANGELOG and migration notes for user-visible or contract changes. Keep paper/claim-to-evidence mappings scientifically conservative: distinguish implementation, synthetic evidence, observed real-run evidence, independent review, hypotheses, negative results, and limitations; never promote owner-controlled AI output into independent evidence. Prefer exact paths, commands, schemas, examples, source revisions, and acceptance criteria. Detect contradictory or stale docs and repair one bounded cluster per run. Run link/doc/schema checks when relevant. Use branch prefix `agent/docs/`. Never push directly to main or merge your own PR. Produce at most one coherent documentation/synchronization outcome with validation and provenance.

---

# 7. IDKmesh Research Scout

**Cadence:** daily around `08:30` Europe/Rome (flexible)  
**Branch prefix:** `agent/research/`

### Coverage

- A2A/MCP/Agent Client Protocol and related standards;
- agent execution/sandboxing;
- Kubernetes/agent runtime developments;
- OpenHands/mini-SWE-agent/coding-agent ecosystem;
- provenance/evaluation standards;
- distributed/HPC execution;
- free/open compute/resource integration;
- dependency/action security advisories actually relevant to IDKmesh;
- scientific methods that can change an active decision.

### Rule

Research does not earn a PR merely by being new. It must materially affect a current architecture/implementation decision or reduce an active uncertainty.

### Configured execution prompt

> Act as the external research, standards, ecosystem, and architecture-scout agent for MSKazemi/idkmesh. On each run, first inspect current main, architecture/interop/research docs, open PRs/issues, issue #23 ACE capacity, issue #461 swarm state, and current repository priorities. Then check current primary upstream sources for developments that could materially affect IDKmesh, especially A2A, MCP, Agent Client Protocol, agent execution/sandbox standards, Kubernetes agent runtimes, OpenHands/mini-SWE-agent/coding-agent tooling, provenance/evaluation standards, distributed/HPC execution, free/open compute/resource integrations, relevant Python/package ecosystem changes, and security advisories for dependencies/actions actually used by the repository. Do not chase novelty for its own sake. Separate upstream facts from hypotheses and vendor claims. Respect shared modes: in FREEZE or CONSOLIDATE, prefer a concise evidence-backed issue/comment/docs correction that reduces uncertainty on existing work; do not start a new implementation branch unless it directly removes an active blocker. In BUILD, one bounded compatibility/design/experiment PR is allowed only if global autonomous PR budget, role exclusivity, and file-overlap guards permit it. Prefer existing standards over inventing IDKmesh-specific protocols. When proposing adoption, state version/date/source, compatibility implications, security/maintenance cost, fallback, and a falsifiable reason it helps IDKmesh. Preserve negative findings. Use branch prefix `agent/research/` for implementation/doc changes. Never push directly to main, expose credentials, or merge your own PR. Produce at most one actionable research outcome per run; if nothing material changed, make no repository write.

---

# 8. IDKmesh Growth Release

**Cadence:** daily around `18:30` Europe/Rome (flexible)  
**Branch prefix:** `agent/growth/`

### Coverage

- release readiness;
- product packaging and runnable demos;
- GitHub Pages/public front door;
- release notes/checklists;
- reusable integrations/Actions;
- newcomer conversion;
- contributor task quality;
- public evidence/case studies;
- community growth from utility rather than spam.

### Configured execution prompt

> Act as the product-growth, release-readiness, community-conversion, and public-demo agent for MSKazemi/idkmesh. First inspect current main, open PRs/issues, releases, README/Pages/demo/product surfaces, contributor onboarding, issue #23 ACE capacity, issue #461 swarm state, issue #10 community engine, issue #374 release gate, and current product/release blockers. Optimize for useful adoption and recurring contributors, not raw activity. Respect shared modes: in FREEZE, only surface the release/community blocker; in CONSOLIDATE, do not create new promotional or feature work—help finish an existing product/release/onboarding PR, make one evidence-backed documentation/demo improvement if it does not add queue pressure, or update one existing issue with a precise blocker; in BUILD, at most one bounded PR/issue action is allowed when global autonomous PR budget, role exclusivity, and file-overlap guards permit it. Focus on a real discover -> understand -> install/run -> inspect evidence -> contribute loop: packaging, release notes, GitHub Pages, runnable demos, examples, reusable integrations/Actions, newcomer task quality, contributor conversion, and public evidence/case studies. Never spam, mass-mention, manufacture stars/forks, send unsolicited outreach, fake external participation, or count owner-controlled agents as community growth. Preserve human-only evidence gates. When a release is genuinely ready, prepare release artifacts/checklists/notes but do not claim validation not actually observed. Use branch prefix `agent/growth/` for repository changes. Never push directly to main, expose secrets, or merge your own PR. Produce at most one substantive outcome per run with hypothesis, evidence, metric to watch, risks, and provenance.

---

# Software-stack coverage map

| Project need | Primary task | Secondary guard/support |
|---|---|---|
| Backend/core Python | Backend API Agent | Reliability Agent |
| APIs/request-response contracts | Backend API Agent | Docs Sync |
| A2A/MCP/interoperability | Backend API Agent | Research Scout + Docs Sync |
| `.env` / configuration | Backend API Agent | Frontend DX + Reliability + Docs Sync |
| Frontend/Pages/product UX | Frontend DX Agent | Growth Release |
| CLI/install/package/devcontainer | Frontend DX Agent | Reliability + Docs Sync |
| Runtime errors/exceptions | Reliability Agent | Backend API Agent |
| CI failures/flaky tests | Reliability Agent | PR Integrator |
| Security/secrets/dependencies | Reliability Agent | Research Scout |
| Observability/logging | Reliability Agent | Backend API Agent |
| Documentation | Docs Sync | every implementation agent |
| Architecture/roadmap | Docs Sync | Research Scout + Governor |
| Paper/evidence synchronization | Docs Sync | Research Scout |
| PR merge/convergence | PR Integrator | Governor |
| Global prioritization/dedup | Swarm Governor | all agents independently re-check |
| Release/demo/adoption | Growth Release | Frontend DX + Docs Sync |
| Community conversion | Growth Release | Governor / ACE capacity |
| Current ecosystem research | Research Scout | Backend/Reliability when actionable |

---

# Why there is no separate generic “issue solver”

A generic issue-solving job was a major source of overlap in the previous generation. In v2, issues are solved by the specialist who owns the relevant system boundary:

- API issue -> Backend API Agent;
- setup/UI/product issue -> Frontend DX Agent;
- failing test/security/error issue -> Reliability Agent;
- stale docs/paper issue -> Docs Sync;
- standards/research uncertainty -> Research Scout;
- release/community issue -> Growth Release;
- PR/integration blocker -> PR Integrator.

This gives every autonomous implementation an explicit owner and branch namespace.

---

# Why there is no separate security-only hourly agent

Security is inseparable from CI, dependencies, configuration, error handling, workflows, and execution boundaries. A separate high-frequency security writer would overlap Reliability and Backend. Security remains an explicit first-class responsibility of the Reliability Agent, with current upstream advisories fed by the Research Scout.

A dedicated security campaign can still be created temporarily for a specific audit, but it should not be permanently scheduled unless evidence shows the combined role is insufficient.

---

# Expected behavior right now

At the time v2 was configured, repository review capacity was already saturated. Therefore the swarm should initially behave as:

```text
Governor -> CONSOLIDATE
    |
    +-> PR Integrator reduces open integration debt
    +-> Reliability repairs blockers/failing checks
    +-> Backend/Frontend avoid new feature PRs
    +-> Docs repairs drift on existing/current work
    +-> Research avoids speculative implementation
    +-> Growth avoids new campaign fan-out
```

As the queue clears and ACE capacity rises, the same schedules automatically unlock bounded `BUILD` work without needing a completely different set of jobs.

---

# Evaluation metrics for the swarm itself

Do not evaluate the scheduler by number of runs or PRs.

Track instead:

- open PR queue size and age;
- median time from candidate PR to correct disposition;
- CI failure recurrence;
- merge-conflict/stale-branch frequency;
- regressions after autonomous changes;
- percentage of behavior changes accompanied by tests/docs;
- documentation drift findings;
- reviewer/maintainer minutes per accepted change;
- duplicate/overlapping autonomous work incidents;
- number of autonomous runs that correctly did nothing;
- release/install success from clean environments;
- external contributor conversion and recurrence;
- verified useful output per scarce human attention.

A high `no-op` rate during blocked/high-load periods is a feature, not a failure.

---

# Future improvements to v2

Possible later improvements, only after v2 produces evidence:

1. machine-readable swarm state block instead of prose coordination comments;
2. explicit file/component lease records with expiry;
3. automatic detection of agent-authored PR prefixes for concurrency accounting;
4. a deterministic priority score combining value, urgency, risk, dependency depth, review cost, and information gain;
5. event-triggered integration checks where the ChatGPT scheduler/platform supports them cleanly;
6. a per-role success/cost ledger so cadences can be reduced or increased based on verified outcomes;
7. automatic cooldown after repeated no-op runs;
8. temporary specialist agents spun up only for bounded campaigns rather than permanent background jobs.

These should be introduced only when they demonstrably reduce collision, review cost, or time-to-useful-integration.

---

# Relationship to the historical inventory

See:

- `docs/planning/AUTOMATION_JOBS_INVENTORY_2026-09-17.md`

That file records the previous ChatGPT scheduled-task population. This v2 document is the replacement operating design.