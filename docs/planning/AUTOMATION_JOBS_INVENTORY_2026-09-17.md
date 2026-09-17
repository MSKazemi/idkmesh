# IDKmesh Scheduled Jobs Inventory — 2026-09-17

> Status: **automation reset completed** on 2026-09-17 at approximately 20:53 Europe/Rome.
>
> This file records every IDKmesh-related scheduled job that was **active immediately before the reset**. Those jobs were disabled after capture so a new scheduling/control algorithm can be designed from a clean slate.

## Scope

This inventory is intentionally a pre-reset snapshot of the active scheduler, not a catalog of old deleted/disabled experiments. Jobs that were already disabled before this reset are not treated as current scheduled jobs.

Repository: `MSKazemi/idkmesh`

Timezone used by the jobs: `Europe/Rome` unless otherwise noted.

## Executive summary

| # | Job | Actual period | Timing mode | Primary role | Pre-reset state | Reset state |
|---|---|---|---|---|---|---|
| 1 | IDKmesh Interface Steward | Every 2 hours | Exact schedule | APIs, protocols, interoperability, communications | Active | Disabled |
| 2 | IDKmesh Weekly Steward | Every 4 hours | Exact schedule | Repository-wide code/docs/paper/roadmap review | Active | Disabled |
| 3 | IDKMesh PR Drift Watch | Every 6 hours | Condition watch | PR/branch drift, conflicts, CI and integration queue changes | Active | Disabled |
| 4 | Agent Interop Watch | Daily | Condition watch | External agent-interoperability developments | Active | Disabled |

### Important inconsistency

The job named **IDKmesh Weekly Steward** was not weekly. Its real schedule was every **4 hours**. Job names should never be treated as authoritative schedule metadata in the next design.

---

## 1. IDKmesh Interface Steward

**Purpose**

Improve IDKmesh APIs, interfaces, protocols, and communications between internal components and external agents, tools, services, compute resources, and LLM endpoints.

**Actual cadence**

- Period: every **2 hours**
- Timing mode: `exact_schedule`
- Schedule:

```text
BEGIN:VEVENT
DTSTART:20260917T083122Z
RRULE:FREQ=HOURLY;INTERVAL=2
END:VEVENT
```

**Last run before reset**

- `2026-09-17T18:42:25Z`
- Approximately `2026-09-17 20:42 Europe/Rome`

**Main work areas**

- API design and request/response schemas
- Interface versioning and compatibility
- SDK/client interfaces
- A2A, MCP, ACP and related protocols
- Transport and messaging layers
- Webhooks/events/streaming
- Authentication handoff
- Capability discovery
- Service boundaries
- Error contracts
- Retry/timeout behavior
- Communication observability
- Interoperability examples and documentation

**Operational rules in the previous prompt**

- Inspect main, issues, PRs, tests, and documentation before acting.
- Select one bounded, high-value interface improvement per run.
- Prefer existing standards over inventing parallel protocols.
- Update tests and API/interface documentation when contracts change.
- Use branches and pull requests for substantive changes.
- Merge only when required checks and repository policies allow it.

**Full captured prompt**

> Work on the public GitHub repository https://github.com/MSKazemi/idkmesh with a strict focus on APIs, interfaces, protocols, and communications between IDKmesh components and external agents, tools, services, and compute resources. On each run, inspect current main, open issues, open PRs, tests, and documentation first to avoid duplication. Choose exactly one bounded, high-value improvement involving API design, request/response schemas, versioning, compatibility, SDK or client interfaces, agent-to-agent communication, MCP, A2A, ACP or related protocols, transport layers, messaging, events/webhooks, streaming, authentication handoff, capability discovery, service boundaries, error contracts, retries/timeouts, observability of communications, interoperability examples, or interface documentation. Prefer concrete implementation, tests, schemas, examples, adapters, compatibility fixes, or documentation that improves real interoperability. Keep interfaces minimal, explicit, versioned where appropriate, backwards-compatible when practical, and coherent with the existing architecture. Do not invent a parallel protocol when an existing standard or repository abstraction is sufficient. Add or update tests for changed behavior and update API/interface documentation whenever contracts change. Run applicable tests, linters, type checks, builds, and validation. Use a focused branch and pull request for substantive changes; do not push directly to main. Merge only when required checks pass, mergeability is clean, documentation and tests are complete, and repository policy permits it. If no safe code change is appropriate, create or improve one precise issue or design note that unblocks the communications layer. Summarize the interface problem addressed, files/contracts changed, compatibility implications, validation performed, PR or issue status, and any follow-up work.

---

## 2. IDKmesh Weekly Steward

**Purpose**

Perform a broad repository review spanning code, tests, architecture, documentation, roadmap/future work, GitHub issues, and the project paper.

**Actual cadence**

- Period: every **4 hours** — despite the word “Weekly” in the title
- Timing mode: `exact_schedule`
- Schedule:

```text
BEGIN:VEVENT
RRULE:FREQ=HOURLY;INTERVAL=4;BYMINUTE=0
END:VEVENT
```

**Last run before reset**

- `2026-09-17T17:07:32Z`
- Approximately `2026-09-17 19:07 Europe/Rome`

**Main work areas**

- Repository-wide code review
- Test and architecture review
- Human- and agent-friendly documentation
- Setup and contribution workflows
- Agent integration documentation
- Roadmap and future-work maintenance
- New issue creation where appropriate
- Paper improvement and synchronization with implementation
- Validation and quality checks

**Operational rules in the previous prompt**

- Review the repository as a whole.
- Keep documentation synchronized with code.
- Improve future-work and roadmap material.
- Create well-scoped issues for concrete work.
- Keep the paper aligned with architecture, implementation, experiments, limitations, and future work.
- Prefer high-quality integrated work to speculative churn.

**Full captured prompt**

> Review the entire MSKazemi/idkmesh repository for the past week's changes. Check code, tests, architecture, and documentation. Make the documentation easy for both humans and autonomous agents to understand and contribute to, including setup, architecture, interfaces, contribution workflows, agent integration points, and coverage of all meaningful code areas. Update documentation to match code changes. Improve roadmap/future-work documentation, identify scientifically and practically valuable new ideas, and create well-scoped GitHub issues for concrete future work where appropriate. Review and improve the project's paper so it accurately reflects the implementation, architecture, experiments, related work, limitations, and future work. Run relevant tests or validation before proposing or merging changes. Prefer high-quality, integrated changes over speculative ones, and avoid duplicating existing issues or plans. Commit repository-safe documentation/code/paper improvements through the GitHub workflow, using a focused branch and pull request when direct edits are not appropriate. Summarize what changed, what was validated, which issues were created or updated, and the most important next actions.

---

## 3. IDKMesh PR Drift Watch

**Purpose**

Monitor pull-request and branch drift and notify only when a meaningful maintainer action is needed.

**Actual cadence**

- Period: every **6 hours**
- Timing mode: `condition_watch`
- Schedule:

```text
BEGIN:VEVENT
DTSTART:20260828T185234Z
RRULE:FREQ=HOURLY;INTERVAL=6
END:VEVENT
```

**Last run before reset**

- `2026-09-17T13:10:49Z`
- Approximately `2026-09-17 15:10 Europe/Rome`

**Main work areas**

- Newly opened or updated pull requests
- Branches that moved after merge
- Stale/orphan branches with unique commits
- Cleanup-eligible branches
- Mergeability and conflicts
- CI failures
- Changes to the canonical integration queue

**Behavior**

This job was intended to be quiet: it should notify only when a meaningful change requires maintainer attention.

**Full captured prompt**

> Check https://github.com/MSKazemi/idkmesh for meaningful pull-request and branch drift. Focus on newly opened or updated PRs, branches that moved after merge, stale or orphan branches with unique commits, cleanup-eligible branches, mergeability/conflicts, CI failures, and any change to the canonical integration queue. Notify me only when there is a meaningful change that needs maintainer attention; otherwise do not notify me.

---

## 4. Agent Interop Watch

**Purpose**

Track external agent-interoperability developments that could materially affect IDKmesh architecture or implementation priorities.

**Actual cadence**

- Period: **daily**
- Timing mode: `condition_watch`
- Schedule:

```text
BEGIN:VEVENT
DTSTART:20260828T141331Z
RRULE:FREQ=DAILY
END:VEVENT
```

**Last run before reset**

- `2026-09-17T13:53:07Z`
- Approximately `2026-09-17 15:53 Europe/Rome`

**Main work areas**

- A2A
- MCP
- OpenHands
- mini-SWE-agent
- Agent task/artifact protocols
- Provenance approaches
- Sandboxing standards
- Other interoperability changes with architectural impact

**Behavior**

This job should notify only for meaningful developments that could change IDKmesh architecture, interoperability decisions, or implementation priorities.

**Full captured prompt**

> Check current developments in agent interoperability that could materially affect IDKMesh, including A2A, MCP, OpenHands, mini-SWE-agent, agent task/artifact protocols, provenance, and relevant sandboxing standards. Notify me only when there are meaningful new changes that could affect IDKMesh architecture, interoperability decisions, or implementation priorities. If there are no meaningful changes, do not notify me.

---

## Reset performed

All four jobs listed above were disabled after this snapshot was captured.

The scheduler is therefore intentionally left with **no active IDKmesh jobs from this active set** while the replacement algorithm is designed.

## Why the previous set should be redesigned

The active jobs were individually reasonable, but the set had structural problems:

1. **No single scheduler/controller.** Each job independently decided what to inspect and what to change.
2. **Overlapping repository scans.** Multiple jobs repeatedly read main, PRs, issues, tests, architecture, and docs.
3. **Overlapping authority.** More than one job could decide that repository changes or issues were appropriate.
4. **Cadence was not tied to repository state.** Work ran because a clock fired, not because value, urgency, reviewer capacity, or dependency state justified it.
5. **No global concurrency budget.** There was no shared limit preventing competing autonomous work from being generated simultaneously.
6. **No shared work ledger/lock.** Jobs could independently converge on related files, issues, or PRs.
7. **Monitoring and mutation were mixed.** Watchers, researchers, maintainers, and code-changing roles were scheduled separately but without a common decision layer.
8. **Naming drift existed.** “Weekly Steward” actually ran every four hours.
9. **Redundant external research.** Interoperability research overlapped with the Interface Steward's remit.
10. **Insufficient feedback control.** Frequency did not automatically decrease when the repository was blocked, review capacity was low, CI was unhealthy, or no valuable work existed.

## Requirements for the replacement algorithm

The next automation design should preferably have:

- one lightweight **orchestrator/control loop** rather than many independent mutation loops;
- explicit repository state collection once per control cycle;
- a shared queue or work ledger;
- deduplication by issue/PR/files/component;
- a global concurrency/PR budget;
- role selection based on current bottlenecks rather than fixed independent clocks;
- event/condition-driven monitoring where possible;
- dynamic cooldown/backoff when no useful work is available;
- priority based on expected verified value, risk, dependencies, and reviewer attention;
- separate **observe → decide → act → verify → integrate → measure** phases;
- clear human-review boundaries;
- one canonical integration queue;
- provenance and evidence for every autonomous action;
- measurable outcomes rather than PR/issue volume;
- automatic prevention of simultaneous overlapping changes;
- periodic higher-level research/planning that feeds the same queue instead of directly spawning uncontrolled implementation.

## Suggested next step

Design a single **IDKmesh Adaptive Steward Controller** that wakes on a modest control cadence, inspects repository state, computes the highest-value eligible action, delegates at most one bounded task when capacity exists, and otherwise does nothing. Research, PR monitoring, reliability, documentation, interface work, community growth, and issue solving should become policies/capabilities selected by that controller rather than separate competing timers.
