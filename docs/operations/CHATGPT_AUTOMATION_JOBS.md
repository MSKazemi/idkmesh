# ChatGPT Automation Jobs for IDKmesh

_Last reviewed: 2026-09-17_

This document records the currently active ChatGPT automation jobs that operate on or monitor the public `MSKazemi/idkmesh` repository. It is intended to make the automation layer visible to maintainers, contributors, and other agents.

> Note: these are ChatGPT-side scheduled jobs, not GitHub Actions. Their schedules and enable/disable state are managed in ChatGPT.

| Job | Cadence | Role |
| --- | --- | --- |
| IDKMesh Hourly Steward | Every hour | Inspect the repository and improve one high-leverage aspect such as architecture, agent interoperability, cloud/HPC/distributed computing, reliability, testing, documentation, usability, community growth, or free/open compute integration. |
| IDKmesh PR Steward | Every hour | Review open pull requests, inspect diffs and exact-head checks, repair bounded problems where safe, update tests/docs where needed, and merge only when quality and repository gates are satisfied. |
| IDKmesh Issue Steward | Every hour | Select one valuable open issue, implement it on a dedicated branch with tests and documentation, open/update a focused PR, and merge only when validation and repository requirements are satisfied. |
| IDKMesh Weekly Steward | Every 4 hours | Perform a broader repository review covering code, tests, architecture, documentation, roadmap/future work, scientifically useful ideas, issue creation, and paper alignment. Despite the historical name, the current schedule is every four hours. |
| IDKMesh PR Drift Watch | Every 6 hours | Watch for meaningful pull-request and branch drift, including new/updated PRs, stale branches, conflicts, CI failures, and changes to the integration queue; surface only actionable changes. |
| IDKMesh Health Watch | Daily | Watch repository health for failing workflows, risky branch state, stale/conflicting PRs, duplicate implementations, archive/project-memory drift, broken tests, important unresolved issues, and structural inconsistencies. |
| Agent Interop Watch | Daily | Monitor meaningful changes in agent interoperability and execution standards that could affect IDKmesh, including A2A, MCP, agent task/artifact protocols, provenance, OpenHands/mini-SWE-agent, and sandboxing. |

## Functional grouping

### Build and improve

- **IDKMesh Hourly Steward**: broad continuous improvement.
- **IDKmesh Issue Steward**: issue-to-implementation pipeline.
- **IDKMesh Weekly Steward**: deeper repository, documentation, roadmap, and paper review.

### Review and integrate

- **IDKmesh PR Steward**: pull-request quality, repair, validation, and safe integration.
- **IDKMesh PR Drift Watch**: integration-queue and branch-drift monitoring.

### Monitor ecosystem and repository health

- **IDKMesh Health Watch**: repository-health monitoring.
- **Agent Interop Watch**: external agent-protocol and interoperability monitoring.

## Operating principle

The active job set intentionally separates implementation, pull-request integration, repository-health monitoring, and external ecosystem monitoring. Jobs should avoid duplicate work, preserve provenance, respect repository review and CI gates, and prefer small verifiable changes over speculative churn.
