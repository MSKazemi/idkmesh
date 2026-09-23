# Enterprise Control Plane Architecture

**Status:** proposed enterprise baseline  
**Date:** 2026-09-22  
**Program:** issue #667  
**Scope:** enterprise deployment, trust boundaries, tenancy, identity, data governance, auditability, resilience, and supply-chain controls.

## 1. Decision in one sentence

IDKMesh keeps the GitHub-first G0/G1 profile as the default product experience, and adds enterprise controls as a strict overlay that can graduate to a dedicated G2/G3 control service only when tenancy, private-network, audit, state, latency, or organizational policy requires it.

Enterprise readiness is therefore not synonymous with Kubernetes, a central database, or a new login system. It means that every privileged action has a bounded authority, every tenant/data boundary is explicit, every important decision is attributable and recoverable, and operational failure has a tested safe state.

## 2. What enterprise means here

An enterprise deployment must be able to answer these questions from evidence:

1. Which tenant/project does this action belong to?
2. Which human or service identity initiated it?
3. Which policy version authorized, denied, or escalated it?
4. Which exact repository/resource revision did it operate on?
5. Which data classification and egress rules applied?
6. Which secret/workload identity was available, and only after which gate?
7. What worker/provider actually executed the work?
8. Which independent evidence was produced?
9. Who had integration authority?
10. Can the control state be reconstructed after a runner/service failure?
11. Can an auditor detect rewriting or deletion of privileged events?
12. Can the operator restore service/state within the declared recovery objectives?

A model response, a worker claim, a successful CI job, an administrator identity, or a vendor badge is not by itself an answer to these questions.

## 3. Deployment progression

The existing G0-G4 progression remains authoritative.

### G0 — repository control plane

GitHub repository + Actions + hosted connectors.

Best for a single project and normal asynchronous software work. No project-owned always-on service is required.

### G1 — repository control plane plus optional nodes

G0 plus bounded local/private workers such as a workstation, GPU node, or private-network execution node.

The node remains a worker. It is not the canonical scheduler, database, verifier, or integration authority.

### G2 — dedicated control service

Use when one organization/project needs requirements that G0/G1 cannot satisfy cleanly, such as:

- private-network API access;
- high-frequency scheduling/leases;
- long-lived provider sessions;
- enterprise identity integration;
- centralized audit export;
- larger queryable operational state;
- stronger availability/recovery targets;
- a live authenticated Control Tower.

G2 should normally be single-organization or dedicated tenancy.

### G3 — shared multi-project / multi-tenant control plane

Use only when one service deliberately manages multiple projects, repositories, or organizational tenants.

G3 adds a hard tenant boundary to every API request, state key, queue item, cache entry, audit event, secret binding, connector binding, and idempotency key.

### G4 — federation

Multiple independently operated control planes exchange bounded work/evidence. This remains future research and must not weaken the enterprise isolation requirements of G2/G3.

## 4. Enterprise reference topology

~~~text
Human users / enterprise IdP
        |
        | SSO / GitHub identity / OIDC
        v
+------------------------------+
| GitHub organization/repos    |
| code, issues, PRs, rulesets  |
| protected integration        |
+---------------+--------------+
                |
                | webhooks / Actions / GitHub App
                v
+----------------------------------------------------+
| Optional IDKMesh G2/G3 control service            |
|                                                    |
| API / ingress plane                               |
|   -> authentication                               |
|   -> tenant context                               |
|   -> authorization + policy decision              |
|                                                    |
| coordination plane                                |
|   -> WorkUnit admission                           |
|   -> claims / leases / idempotency                |
|   -> connector routing                            |
|   -> run state                                    |
|                                                    |
| evidence / audit plane                            |
|   -> append-only audit events                     |
|   -> evidence references / digests                |
|   -> SIEM/archive export                          |
|                                                    |
| state plane                                       |
|   -> durable DB / ledger                          |
|   -> encrypted backups                            |
+---------+------------------+-----------------------+
          |                  |
          | bounded dispatch | bounded dispatch
          v                  v
 hosted providers       private/local workers
          |                  |
          +--------+---------+
                   |
                   v
          candidate + evidence
                   |
                   v
             GitHub PR/checks
                   |
                   v
          protected human integration
~~~

GitHub remains the canonical code and integration authority unless a future ADR explicitly changes that boundary.

## 5. Four planes, four authorities

Enterprise deployments must not collapse these planes into one privileged service account.

### 5.1 Source/integration plane

Owns repositories, protected branches, releases, rulesets, and final integration.

A worker/provider does not receive this authority merely because it can create a candidate branch or pull request.

### 5.2 Control plane

Owns admission, routing, claims, run state, retry/idempotency, policy evaluation, and operator status.

The control plane may decide that work is eligible to execute. It does not decide that the resulting candidate is correct or merged.

### 5.3 Execution plane

Runs untrusted or semi-trusted work in hosted providers, CI sandboxes, local nodes, private runners, containers, VMs, or other substrates.

Execution identity is provenance, not repository authority.

### 5.4 Evidence/audit plane

Records verification evidence and privileged control events.

Evidence can recommend or document a decision. The audit stream records what happened. Neither one is permission to integrate.

## 6. Tenant boundary

For G3 and any deployment claiming shared tenancy:

- tenant/project identity MUST be explicit before mutable state is read or written;
- tenant scope MUST be part of run IDs, claims, idempotency keys, queue/cache keys, connector bindings, audit events, and durable state queries;
- authorization MUST be evaluated against the requested tenant/resource, not only against the caller's global role;
- cross-tenant references MUST fail closed;
- background jobs MUST carry the same tenant context as synchronous requests;
- caches MUST NOT be keyed only by unscoped resource IDs;
- tenant scope MUST survive retries and event replay;
- a missing/unknown tenant MUST be an error, not a default tenant.

Issue #669 owns executable isolation work.

## 7. Identity and authority

The normalized identity model should distinguish at least:

- human GitHub/enterprise identity;
- GitHub Actions workflow identity;
- GitHub App installation identity;
- IDKMesh service identity;
- hosted provider identity/session;
- local/private node identity;
- verifier identity;
- integrator/administrator identity.

Enterprise authorization is stage-specific.

~~~text
actor + tenant + action + resource + risk + data class + policy revision
                            |
                            v
                 allow / deny / approval required
~~~

High-risk operations should support separation of duties. A single person may hold multiple organizational roles, but enterprise policy can require distinct actors for a particular execution/integration path.

Break-glass access must be explicit, time bounded, reason required, and audited. It must not silently become the normal operating path.

Issue #670 owns the identity/RBAC/ABAC/SoD implementation.

## 8. Data classification and egress

The enterprise baseline uses four minimum data classes:

- public;
- internal;
- confidential;
- restricted.

A WorkUnit or project policy can tighten classification. An agent/model cannot lower it.

External processing is a non-compensating eligibility check. If policy forbids a data class from leaving the approved trust boundary, model quality, cost, speed, or administrator convenience cannot override that rule.

Enterprise workers should support:

- deny-by-default or allowlisted network egress;
- explicit provider/domain policy;
- private-network execution for restricted systems;
- bounded artifact transfer;
- no secret values in WorkUnits, ResultManifests, verification reports, issue text, audit records, or logs.

Issue #672 owns the data/egress/secrets boundary.

## 9. Secret and workload identity

Tracked configuration stores references, never credential values.

Preferred order for enterprise/cloud access:

1. short-lived workload identity / OIDC;
2. enterprise secret manager reference;
3. GitHub Environment/repository secret where appropriate;
4. long-lived cloud access keys only where policy explicitly permits them.

Authorization happens before secret materialization.

Secret access should be auditable as a decision and resource reference without recording the secret value.

## 10. Audit model

Ordinary application logs are not the enterprise audit ledger.

A privileged audit event should bind:

- tenant/project;
- correlation/request/run ID;
- initiating actor;
- effective service/workload identity;
- action and resource;
- exact repository/resource revision;
- policy version;
- decision: allow / deny / approval-required;
- approval/reason reference when applicable;
- outcome;
- relevant evidence/result digests;
- event timestamp;
- integrity linkage when the selected storage supports it.

The baseline requires append-only semantics. G2/G3 production deployments should support export to an organization-controlled archive/SIEM.

Audit evidence records decisions; it does not grant authority by existing.

Issue #671 owns the audit ledger/export contract.

## 11. Reliability and recovery

Enterprise operation requires explicit objectives rather than adjectives such as "high availability."

The Enterprise Control Profile records:

- availability target;
- recovery point objective (RPO);
- recovery time objective (RTO);
- restore-test interval;
- backpressure requirement.

These are declared objectives until measured by a pilot.

Required failure behavior:

- duplicate event -> idempotent/no duplicate external attempt;
- coordinator crash -> durable state can reconstruct the run;
- provider outage -> degraded/blocked state, not silent reroute across forbidden policy;
- audit exporter outage -> durable local audit remains intact and export can recover;
- database/ledger loss -> restore procedure with evidence;
- Actions/reviewer backlog -> generation backpressure;
- expired identity/policy -> fail closed until re-evaluated.

Issue #673 owns operational SLO/DR work.

## 12. Supply chain

Enterprise release controls should progressively provide:

- immutable pinning for security-sensitive third-party Actions/reusable workflows;
- dependency inventory/SBOM;
- source revision and build workflow identity;
- provenance attestation where supported;
- artifact verification instructions;
- vulnerability-response policy;
- plan-aware feature detection rather than assuming every GitHub capability exists.

GitHub artifact attestations and OIDC can support these controls, but an attestation proves provenance/integrity facts, not functional correctness.

Issue #674 owns release/supply-chain hardening.

## 13. Observability

Operational telemetry and audit evidence are separate.

Metrics/logs/traces should support:

- request/correlation ID;
- tenant/project dimension;
- connector/provider dimension;
- queue depth and age;
- dispatch/admission latency;
- verification debt;
- error/failure class;
- retry/idempotency behavior;
- policy denials/escalations;
- restore/backup health.

Telemetry must avoid secret values and should minimize sensitive task content.

## 14. Change and incident management

Enterprise operation needs an accountable control loop:

~~~text
proposed change
 -> reviewed policy/config/code
 -> exact revision
 -> staged validation
 -> deployment
 -> observed health
 -> rollback or acceptance
~~~

Security incidents should have stable incident identifiers that can be referenced by audit events, emergency changes, and post-incident evidence.

Emergency access must leave more evidence than normal access, not less.

## 15. G2/G3 service requirements

The optional service tracked by #675 should be introduced only after the repository-only pilot identifies a need or an enterprise control explicitly requires it.

Minimum service qualities:

- authenticated API ingress;
- mandatory tenant context;
- policy evaluation before side effects;
- idempotent commands;
- durable state outside process memory;
- readiness/liveness health surfaces;
- explicit schema/database migrations;
- encrypted backups;
- graceful restart;
- bounded retry;
- no worker merge authority;
- versioned API/contracts;
- deploy/rollback runbook;
- observable saturation/backpressure.

A database, queue, container orchestrator, or cloud vendor is an implementation choice beneath these invariants.

## 16. Conformance, not certification

IDKMesh may map controls to common enterprise frameworks in future, but the project MUST distinguish:

- implemented control;
- test evidence;
- pilot evidence;
- independent audit;
- formal certification.

A passing IDKMesh enterprise preflight is not a SOC 2, ISO 27001, FedRAMP, HIPAA, PCI DSS, or similar certification claim.

Issue #676 owns destructive conformance testing.

## 17. Current implementation boundary

Implemented on main today:

- GitHub-first/server-optional architecture;
- protected-main integration model;
- WorkUnit security/data fields;
- evidence/provenance contracts;
- deterministic connector routing kernel;
- GitHub-native automation/security mechanisms.

Planned/open enterprise work:

- #668 enterprise profile/preflight;
- #669 tenant isolation;
- #670 identity/SoD;
- #671 audit ledger/export;
- #672 data/egress/secrets;
- #673 SLO/DR;
- #674 supply chain;
- #675 G2/G3 control service;
- #676 enterprise conformance pilot.

Do not describe the planned controls as production-enforced until their issues and acceptance evidence are complete.

## 18. Enterprise success gate

The baseline is ready for an enterprise pilot only when the system can demonstrate that:

- unauthorized actor attempts fail;
- cross-tenant references fail;
- duplicate/replayed events do not duplicate provider work;
- high-risk SoD cannot be bypassed through task text or a model;
- restricted data cannot route to a forbidden external provider;
- secrets remain outside durable task/evidence/audit objects;
- privileged events are reconstructable and tamper-evident;
- control state survives coordinator failure;
- restore objectives are tested;
- supply-chain provenance binds the release to exact source/build identity;
- normal protected integration remains outside worker/verifier authority.

That evidence, rather than infrastructure size, is what makes the system enterprise-operable.
