# ADR-0013 — GitHub-First, Server-Optional Deployment

**Status:** Proposed for adoption  
**Date:** 2026-09-22

## Context

IDKMesh is intended to coordinate humans, coding agents, model providers, deterministic tools, verifiers, and optional external compute around a Git repository without collapsing implementation, verification, and integration authority.

The repository already has:

- GitHub-native issue/model routing;
- Jules dispatch through GitHub events;
- canonical WorkUnit, ResultManifest, EvaluatorPlan, and VerificationResult contracts;
- a connector-control-plane architecture and API;
- protected-integration principles;
- optional local/volunteer execution architecture;
- a requirement to support a second, independent software project.

The remaining deployment question is whether every adopting project must operate a permanent IDKMesh service/database, or whether the first useful product can run primarily from the target GitHub repository.

Introducing an always-on server too early would increase onboarding, security, operations, tenancy, authentication, persistence, and deployment complexity before evidence shows those costs are necessary.

GitHub already provides several control-plane primitives useful to IDKMesh:

- repository state;
- Issues and Pull Requests;
- GitHub Actions;
- identities and teams;
- rulesets/branch protection;
- Environments and secret storage;
- Checks and workflow summaries;
- Projects and Issue Forms;
- Releases and optional artifact attestations;
- Pages for read-only publication.

## Decision

Adopt **GitHub-first, server-optional** as the default deployment architecture for the first productized external-project profile.

The default profile, named **G0**, is:

```text
GitHub repository
  + .idkmesh project/policy/config
  + Issues / labels / optional Projects
  + GitHub Actions event-driven coordination
  + PRs / Checks / reviews
  + compact durable Git-native run/evidence ledger
  + protected main
  + hosted agent/model connectors
```

No project-owned always-on IDKMesh server is required in G0.

Hosted agents execute on provider infrastructure. Optional local/volunteer/project machines may run `idkmesh-node` as workers, but those machines are not the central source of coordination truth.

GitHub remains canonical for code and integration authority.

## Required invariants

1. **Worker success is not acceptance.**
2. **Verification recommendation is not merge authority.**
3. **GitHub Actions is an execution substrate, not the only durable database.**
4. **Ephemeral workflow runners must be restart-safe.**
5. **Duplicate/replayed GitHub events must not create duplicate external work.**
6. **Issue/comment/Project text is untrusted input and cannot grant secrets, executable authority, network/filesystem expansion, repository-admin authority, or merge authority.**
7. **Secret values never enter tracked project configuration.**
8. **Default workflow permissions are least privilege.**
9. **A higher-capability model does not gain higher repository authority.**
10. **Optional GitHub features must fail additively: disabling Projects, Pages, artifact attestations, or OIDC must not destroy the core WorkUnit -> candidate -> verify -> human integration path.**

## Deployment profiles

### G0 — GitHub repository control plane

Primary target. No always-on IDKMesh service.

Use for:

- one repository;
- small/medium teams;
- asynchronous hosted agents;
- ordinary PR-based software development.

### G1 — GitHub + optional nodes

G0 plus one or more `idkmesh-node` workers for:

- local models;
- GPUs;
- private-network tools;
- larger test environments;
- donated/specialized compute.

The durable control state still remains outside individual nodes.

### G2 — GitHub + lightweight authenticated control service

Add only when real usage demonstrates a requirement such as:

- materially lower webhook latency;
- high-frequency leasing/heartbeats/work stealing;
- real-time bidirectional provider sessions;
- multi-repository operational queries;
- write-capable live Control Tower;
- state/query volume that no longer fits the Git-native ledger.

G2 may use SQLite for a single deployment or Postgres for shared/multi-user deployment. GitHub remains canonical for source and integration.

### G3 — shared multi-project control plane

For organizations managing many repositories/installations. Requires explicit tenancy, authentication/authorization, audit, rate limits, database migration strategy, and GitHub App installation boundaries.

### G4 — federated mesh

Long-term research only. It must not complicate G0 adoption.

## GitHub-native capability policy

### Required for G0 implementation

- Actions;
- Issues/PRs;
- workflow concurrency plus durable idempotency;
- branch/ruleset preflight;
- repository/environment secret references;
- exact revision binding;
- durable compact run/evidence state.

### Strongly recommended

- CODEOWNERS for sensitive control/evaluator/workflow paths;
- Environments for high-risk/provider-secret lanes;
- Issue Forms for structured WorkUnit intake;
- workflow/job summaries for run evidence.

### Optional/additive

- Projects;
- Pages read-only dashboard;
- OIDC for cloud authentication;
- artifact attestations for release provenance;
- GitHub App / Checks API;
- merge queue.

None of these optional capabilities may become an implicit correctness or acceptance authority.

## Persistence decision

Do not rely on:

- runner-local files;
- process memory;
- Actions cache;
- expiring workflow artifacts;
- provider session history alone.

G0 must have a compact durable ledger containing sufficient metadata/digests to reconstruct run state after workflow termination.

Large logs may remain in Actions/provider storage if the ledger retains stable references/digests and enough canonical evidence for later interpretation.

The exact storage representation is defined by the GitHub-first operations specification, not this ADR.

## Multi-user identity decision

GitHub identity is the bootstrap human identity provider for G0/G1.

Do not create a separate IDKMesh username/password system for the first product.

Project policy distinguishes stage-specific capabilities such as:

- owner/admin;
- dispatcher;
- worker;
- verifier/reviewer;
- maintainer/integrator;
- node operator.

A person may hold several roles where policy permits, but the system records the actor and stage independently.

## Security consequences

### Positive

- no public project-owned API server to secure in the default profile;
- existing GitHub repository governance remains visible and familiar;
- provider secrets can remain in GitHub Environments/repository secret stores;
- Actions workflows can use explicit least-privilege permissions;
- rulesets/CODEOWNERS can protect governance surfaces;
- cloud integrations can use OIDC when appropriate.

### Risks

- GitHub becomes an operational dependency;
- Actions quotas/startup latency may limit high-frequency workloads;
- Git-backed ledger writes need conflict/idempotency handling;
- repository-plan differences affect available protection features;
- GitHub-native identity is insufficient for some enterprise/federated scenarios.

These are accepted for G0 and become revisit triggers for G2/G3.

## Alternatives considered

### A. Mandatory central server from first install

Rejected for the first product. It creates deployment/auth/database/tenancy/operations burden before a second-project pilot proves it is necessary.

### B. Store all state only in GitHub issue comments and Actions artifacts

Rejected. Comments are poor machine-state primitives and Actions artifacts are not an adequate sole durable authority surface.

### C. Local-only coordinator on a maintainer laptop

Rejected as the default. It creates a hidden single-machine dependency and weakens multi-user/restart semantics. Local mode can remain a development/testing option.

### D. GitHub-first with optional service escalation

Chosen.

## Acceptance evidence required before calling G0 proven

The no-server second-project pilot must demonstrate:

- a fresh repository bootstrapped without a permanent server;
- multiple human GitHub actors;
- at least ten bounded WorkUnit attempts;
- duplicate/replayed dispatch protection;
- coordinator-workflow kill/restart recovery;
- candidate normalization and independent verification;
- protected human integration;
- release provenance;
- retained failed/cancelled attempts;
- measured reviewer/compute/provider cost and setup friction.

If the pilot exposes an unmet requirement, record that evidence before promoting G2 into the default installation.

## Implementation references

- umbrella: #570
- connector kernel: #574
- GitHub dispatch: #578
- normalization: #579
- CLI/API: #580
- bootstrap: #596
- durable state: #597
- multi-user policy: #598
- no-server pilot: #599
- governance/security baseline: #607
- structured intake/Projects: #608
- GitHub evidence/release UX: #609

## Revisit conditions

Revisit this ADR when any of these are measured:

- workflow/event latency materially limits useful work;
- lease/heartbeat frequency requires a persistent broker;
- one installation manages many repositories/organizations;
- ledger contention/size makes Git storage operationally poor;
- enterprise requirements mandate private networking/SSO/central audit;
- a live write-capable Control Tower becomes a product requirement.

Until one of those conditions is demonstrated, a server remains optional.
