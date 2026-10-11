---
description: "Normative G2/G3 enterprise control-service boundary: plane separation, tenant authorization, durable state, private workers, idempotency, operations, and upgrade strategy."
---
# Enterprise Control Service Boundary v0.1

**Status:** normative E8 deployment reference  
**Issue:** #675  
**Parent:** #667  
**Related:** #670 #673 #674 #750  
**Architecture:** [Enterprise Control Plane](../architecture/ENTERPRISE_CONTROL_PLANE.md)

## 1. Purpose

This specification freezes the boundary for the optional always-on IDKMesh
control service used by G2 and G3 deployments.

It does **not** make an always-on service the default product path. G0/G1 remain
GitHub-first and server-optional. A team should introduce G2/G3 only when
private-network access, tenant isolation, persistent coordination, operational
SLOs, centralized audit, or similar requirements cannot be met cleanly by the
GitHub-first profile.

This document also does not select Kubernetes, PostgreSQL, Redis, a cloud
provider, an ingress product, or a secret manager. Those are deployment choices
behind the boundary defined here.

Normative terms such as **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe
the deployment contract. They are not claims that a production G2/G3 service is
already deployed or independently validated.

## 2. Authority ceiling

Moving coordination into an always-on service MUST NOT move repository
integration authority into that service.

The invariant is:

```text
control service can admit/route/coordinate
worker can execute and produce a candidate
verifier can produce evidence/recommendation
human/governance can record a decision
GitHub protected integration remains canonical
```

Unless a future reviewed ADR explicitly changes the model:

- GitHub repositories and protected branches remain canonical code state;
- GitHub rulesets/reviews/environments remain the final integration boundary;
- control-service identities MUST NOT carry a general-purpose merge credential;
- worker/provider identities MUST NOT carry merge authority;
- verifier identities MUST NOT carry merge authority;
- a Human Decision Record may authorize a later integration step but does not
  itself push or merge code;
- service/database administrator status does not imply project integration
  authority.

## 3. Required plane separation

G2/G3 deployments MUST preserve separate authorities even when several
components share one physical cluster.

| Plane | Owns | Must not own |
| --- | --- | --- |
| API / ingress | authentication handoff, request normalization, tenant context, rate/size limits, request correlation | provider execution, direct repository merge |
| Control / application | admission, authorization orchestration, idempotency, claims/leases, connector dispatch intent, run state | verifier truth, final integration |
| Worker / execution | bounded execution against an admitted WorkUnit | control DB administration, policy mutation, merge |
| Data | durable run/event/idempotency/decision records and immutable evidence references | implicit authorization decisions |
| Evidence / audit | verification evidence, privileged-event audit, export/checkpoints | execution or integration authority |
| Source / integration | repositories, PRs, rulesets, protected integration | worker execution authority |

A small G2 deployment MAY colocate processes for operational simplicity, but
the logical boundaries, identities, permissions, and data access rules above
still apply.

## 4. Request path and tenant authorization

Every product/resource request MUST establish the following context before
tenant state is read, mutated, dispatched, or materialized:

```text
authenticated transport/principal
 -> normalized ActorContext
 -> explicit TenantScope / project scope
 -> exact resource reference
 -> AuthorizationDecision
 -> idempotency/concurrency check
 -> durable intent/state transition
 -> bounded side effect
 -> audit/evidence record
```

The authorization decision MUST bind the exact tenant/project and resource
scope. Global role membership alone is insufficient.

For G3:

- tenant scope is mandatory on every product request and background job;
- tenant scope participates in durable keys, queue keys, cache keys, leases,
  idempotency keys, connector bindings, secret references, and audit records;
- cross-tenant identifiers MUST fail closed before data access;
- shared caches MUST NOT use keys that omit tenant/project scope.

`/healthz` and `/readyz` are operational endpoints rather than tenant
resource requests. They MAY be reachable without tenant context, but they MUST
return no tenant/project/run/evidence/identity/secret data.

The service consumes the identity/authorization owner defined by
[Enterprise Authorization Kernel v0.1](ENTERPRISE_AUTHORIZATION_V0_1.md); E8
does not create a second role model.

## 5. Stateless API and durable state

API replicas SHOULD be stateless wherever practical.

Canonical coordination state MUST NOT exist only in:

- process memory;
- one ephemeral runner filesystem;
- a local browser session;
- an Actions cache;
- a short-retention CI artifact;
- an in-memory queue without replayable durable intent.

Durable state is owned by an explicit database/ledger/object boundary according
to [API Storage Profiles v0.1](API_STORAGE_PROFILES_V0_1.md).

At minimum the network profile must have durable ownership for:

- run and attempt indexes;
- idempotency records;
- append-only event history;
- immutable Human Decision Records when that API is enabled;
- immutable evidence objects or content-addressed evidence references;
- connector configuration containing **secret references only**;
- authorization and audit references sufficient to reconstruct privileged
  actions.

Raw credentials MUST NOT be stored in API/control state.

## 6. Horizontal scale and idempotency

A G2/G3 control service MUST remain correct with more than one API/control
replica before it is described as horizontally scalable.

Required semantics:

1. replicas share the same durable coordination state;
2. no correctness rule depends on sticky sessions;
3. every externally visible mutation uses an idempotency identity bound to the
   tenant/project, action, target resource/revision, and canonical request
   meaning;
4. duplicate webhook/event/API delivery does not duplicate provider work;
5. claims/leases use atomic compare-and-set or equivalent transactional
   semantics;
6. lease ownership uses fencing/revision data so a stale replica cannot resume
   authority after a newer owner exists;
7. provider dispatch records enough intent/provenance to distinguish
   `not_submitted`, `submission_unknown`, and `provider_accepted`;
8. retries after an ambiguous external call fail safe or reconcile provider
   state rather than blindly resubmitting;
9. caches are advisory and reconstructable from durable state;
10. background workers use the same tenant/idempotency rules as synchronous API
    requests.

Scaling throughput is not allowed to weaken separation of duties or create a
second integration authority.

## 7. Private-network and self-hosted runner pattern

The reference G2/G3 worker pattern is outbound/bounded:

```text
private/self-hosted runner
 -> receives one admitted WorkUnit / execution binding
 -> resolves only authorized short-lived secret material
 -> executes in its bounded substrate
 -> returns candidate artifacts + provenance/evidence references
 -> loses the temporary execution authority
```

Workers SHOULD be reachable through a private network, brokered job channel, or
outbound polling model appropriate to the deployment.

Workers MUST NOT require:

- direct administrative access to the control database;
- a GitHub token with merge/admin authority;
- host SSH credentials from the control-service operator;
- unrestricted secret-store browsing;
- permission to broaden their own WorkUnit/network/filesystem policy.

A self-hosted runner may create a candidate branch/PR only through a narrowly
scoped, audited integration adapter when project policy permits it. Candidate
publication is not protected integration.

## 8. Health, readiness, and degraded mode

Every G2/G3 service deployment MUST expose separate operational probes:

### `GET /healthz`

Process/container liveness only. It answers whether the service process is
capable of serving requests. It MUST NOT perform expensive dependency queries or
expose tenant state.

### `GET /readyz`

Traffic readiness. It MUST fail when the instance cannot safely serve its
declared profile, including incompatible schema/migration state or unavailable
dependencies required for correctness.

Readiness MAY include coarse dependency states such as database/audit/identity
adapter readiness, but MUST NOT expose secrets, tenant identifiers, raw errors,
prompts, or evidence.

A dependency outage must map to a documented degraded/fail-closed mode. For
example, losing an optional SIEM exporter may preserve bounded coordination
while retaining audit locally, but losing the authoritative durable store must
make mutation readiness fail.

## 9. Database migration lifecycle

Schema migration is an explicit deployment phase.

Requirements:

- the durable store carries an explicit schema/version identity;
- migrations are ordered, replayable, and reviewed;
- startup refuses a store version it cannot safely interpret;
- rolling upgrades use **expand -> migrate/backfill -> contract** when old and
  new replicas must overlap;
- destructive contraction occurs only after no supported old replica depends on
  the removed representation;
- an irreversible migration requires a verified backup/restore point and a
  documented roll-forward/restore plan;
- migrations preserve tenant keys, idempotency identities, immutable decision
  records, event ordering, and audit references;
- a migration is never treated as permission to rewrite immutable evidence.

## 10. Backup and restore boundary

The deployment MUST define backup ownership for every durable component required
to reconstruct control state.

The backup set includes, as applicable:

- database/ledger state;
- immutable evidence/object storage or its durable content-addressed source;
- audit checkpoints/archives needed to detect truncation;
- versioned configuration and policy references.

Backup copies MUST be encrypted according to the deployment data policy.
Retention, RPO, and RTO are deployment/profile fields, not universal product
claims.

Restore procedure MUST specify:

1. stop or fence new mutations/dispatch;
2. restore the durable state set to a mutually consistent point;
3. verify schema/version compatibility;
4. verify digest/audit integrity where contracts provide it;
5. reconcile ambiguous external provider sessions before redispatch;
6. re-enable readiness only after reconstruction checks pass.

Observed restore-time and data-loss evidence belongs to E6/E9. This E8
specification defines the boundary; it does not manufacture a successful DR
exercise.

## 11. Upgrade and rollback strategy

### Compatible change

For API/application changes compatible with the current durable schema:

1. mark the old replica set draining;
2. add new replicas;
3. wait for readiness;
4. shift traffic;
5. remove drained old replicas.

No admitted request may be silently abandoned merely to make deployment finish.

### Schema-changing rolling upgrade

Use the expand/migrate/contract sequence in section 9. Mixed-version operation
is permitted only inside an explicitly tested compatibility window.

### Breaking or unsafe-to-overlap change

Use bounded downtime:

1. stop new dispatch/mutations;
2. drain in-flight work or record its recoverable state;
3. take/verify the required recovery point;
4. perform migration/upgrade;
5. run readiness/integrity checks;
6. resume service.

Rollback MUST NOT start old code against a newly incompatible schema. Recovery
must be a supported down-migration, roll-forward, or restore operation.

## 12. Reference deployment topology

The reference is technology-neutral:

```text
                   GitHub / protected integration
                           ^
                           | candidate PRs, checks, decisions
                           |
enterprise IdP -> private/reviewed ingress
                           |
                   +-------+-------+
                   | API replicas  |  stateless where practical
                   +-------+-------+
                           |
                 tenant + authorization
                           |
                   +-------+-------+
                   | control svc   |  admission/idempotency/dispatch
                   +---+-------+---+
                       |       |
             durable DB/ledger  +------> audit/export sink
                       |
              immutable evidence refs
                       |
              +--------+---------+
              |                  |
       hosted connectors   private/self-hosted runners
              |                  |
              +--------+---------+
                       |
                candidate/evidence
```

The data plane is not exposed directly to workers. The execution plane is not
used as a durable database. GitHub remains the source/integration plane.

A G2 deployment may run one replica when its declared availability objective
permits that. A G3 deployment should normally run multiple failure-isolated API
replicas and a durable state layer suitable for the declared SLO/RPO/RTO, but
replica counts are deployment policy rather than hard-coded product constants.

## 13. G2 versus G3

| Requirement | G2 | G3 |
| --- | --- | --- |
| Always-on service | required | required |
| Tenant/project scope | explicit | mandatory and isolation-critical |
| Multi-tenant shared state | not required | supported only with proven isolation |
| Per-request authorization | required | required with tenant/resource binding |
| Durable coordination state | required | required |
| Audit | required for privileged actions | tenant-scoped and tamper-evident |
| Worker merge authority | forbidden | forbidden |
| Horizontal scale semantics | defined even if deployed single-replica | required before shared-service scale claim |
| Backup/restore lifecycle | defined and exercised per E6 profile | defined and exercised per E6 profile |
| GitHub canonical integration | yes | yes |

A G2 service MUST NOT be renamed G3 merely because it hosts several projects.
G3 requires the tenant-isolation evidence owned by E2/E3/E9.

## 14. Deployment readiness checklist

Before enabling G2 mutations/dispatch:

- authenticated identity source is configured;
- TenantScope/project scope is present;
- authorization runs before secret materialization and side effects;
- durable state and idempotency storage are configured;
- audit sink/ledger behavior is defined;
- workers lack merge/admin credentials;
- health/readiness are wired;
- migration version is compatible;
- backup/restore ownership and RPO/RTO are declared;
- GitHub protected integration remains external to worker authority.

Before claiming G3, additionally verify:

- cross-tenant negative tests;
- tenant-scoped caches/queues/idempotency/secret bindings;
- tenant-aware audit/export;
- background jobs preserve tenant context;
- destructive conformance evidence demonstrates fail-closed isolation.

## 15. Acceptance mapping for issue #675

| #675 acceptance criterion | Frozen contract |
| --- | --- |
| API/worker/data planes separated | sections 3 and 12 |
| stateless API where practical; durable explicit DB/ledger | section 5 |
| per-tenant authorization at every request | section 4 |
| no direct merge authority in worker services | sections 2, 3, and 7 |
| private-network/self-hosted runner pattern | section 7 |
| horizontal scale/idempotency semantics | section 6 |
| migrations/backups/health/readiness defined | sections 8-10 |
| zero- or bounded-downtime upgrade strategy | section 11 |
| GitHub remains canonical code/integration authority | sections 2 and 12 |

This mapping means the **E8 boundary/reference is specified**. It does not mean
a particular deployment has demonstrated these properties.

## 16. Non-goals and evidence boundary

This specification does not:

- certify SOC 2, ISO 27001, FedRAMP, or another framework;
- prove E2 tenant isolation, E3 identity freshness, E6 restore objectives, or E9
  destructive scenarios;
- introduce a new canonical run/evidence/decision model;
- require a particular infrastructure vendor;
- make the current loopback Control Tower a production network server.

Operational proof remains evidence-gated:

- E2/E3 prove tenant and identity/authorization behavior;
- E6 proves SLO/backup/restore/incident objectives;
- E7 binds release provenance;
- E9 performs destructive conformance scenarios.

The service boundary is therefore complete as an architectural contract while
production deployment claims remain conditional on those observed controls.
