# Enterprise Readiness Execution Plan — 2026-09-22

**Status:** active implementation plan  
**Umbrella:** #667  
**Architecture:** ../architecture/ENTERPRISE_CONTROL_PLANE.md  
**ADR:** ../decisions/ADR-0014-enterprise-control-plane-baseline.md  
**Contract:** ../specifications/ENTERPRISE_CONTROL_PROFILE_V0_1.md

## 1. Outcome

Deliver an enterprise-operable IDKMesh profile without turning the default GitHub-first product into an infrastructure project.

The execution sequence is control-first:

~~~text
E1 versioned control profile
        |
        +------------------------+
        |                        |
        v                        v
E2 tenant isolation       E3 identity/SoD
        |                        |
        +------------+-----------+
                     |
          +----------+----------+
          |                     |
          v                     v
   E4 audit ledger        E5 data/secrets
          |                     |
          +----------+----------+
                     |
          +----------+----------+
          |                     |
          v                     v
       E6 SLO/DR           E7 supply chain
          |                     |
          +----------+----------+
                     |
                     v
          E8 optional G2/G3 service
                     |
                     v
          E9 destructive conformance pilot
~~~

G0/G1 work can use many of these controls without waiting for E8.

## 2. Definition of enterprise-ready

The program is not complete when all documents exist.

It is ready for a scoped enterprise pilot when evidence shows:

- tenant/project isolation cannot be bypassed with a changed identifier;
- authority is evaluated before side effects/secrets;
- high-risk separation of duties cannot be self-approved where required;
- data classification blocks forbidden egress;
- raw secret values do not enter durable task/evidence/audit records;
- privileged decisions are attributable to policy revision and exact resource revision;
- event replay and coordinator restart are idempotent/recoverable;
- backup/restore exercises meet declared objectives;
- CI/review saturation applies backpressure;
- release provenance can be verified;
- workers/verifiers still cannot merge by themselves.

## 3. Phase E1 — control profile (#668)

### E1-A schema

Deliver JSON Schema Draft 2020-12 for EnterpriseControlProfile v0.1.

### E1-B reference profile

Add one production-oriented example that passes the deterministic baseline.

### E1-C stdlib preflight

Add deterministic PASS/WARN/FAIL checks for cross-field enterprise invariants.

### E1-D negative fixtures/tests

At minimum:

- G3 without enforced tenant isolation;
- production in audit-only mode;
- restricted external processing;
- long-lived cloud keys in production;
- missing MFA/SoD;
- unaudited/unbounded break-glass;
- non-append-only production audit.

### E1 exit gate

One versioned profile can be inspected deterministically without network access, and the tool explicitly states that declaration readiness is not observed enforcement.

## 4. Phase E2 — tenant isolation (#669)

Suggested PR slices:

- E2-A tenant/project identifier type;
- E2-B tenant scope in run/idempotency/claim keys;
- E2-C scoped durable-store queries;
- E2-D scoped queue/cache keys;
- E2-E cross-tenant negative fixtures;
- E2-F background-job tenant propagation;
- E2-G storage adapter isolation tests.

Exit: a cross-tenant reference cannot read, mutate, claim, retry, or attach evidence to another tenant.

## 5. Phase E3 — identity and authority (#670)

Suggested slices:

- E3-A normalized ActorContext;
- E3-B GitHub/App/Actions/service identity adapters;
- E3-C role + attribute policy evaluator;
- E3-D policy-revision binding;
- E3-E high-risk distinct-actor requirement;
- E3-F revocation/expiry/cache invalidation;
- E3-G break-glass object;
- E3-H unauthorized task-text escalation tests.

Exit: authority derives from trusted identity/policy state, not task text/provider output.

## 6. Phase E4 — audit (#671)

Suggested slices:

- E4-A AuditEvent v0.1 schema;
- E4-B canonical serialization and digest;
- E4-C append/hash-chain fixture;
- E4-D privileged-event instrumentation;
- E4-E tamper/rewrite detection;
- E4-F secret/content minimization;
- E4-G SIEM/archive adapter interface;
- E4-H retention/legal-hold policy hooks.

Exit: privileged history can be reconstructed and silent rewrite/removal is detectable within the selected ledger model.

## 7. Phase E5 — data, egress, secrets (#672)

Suggested slices:

- E5-A data-class lattice;
- E5-B external-processing hard filter;
- E5-C egress policy contract;
- E5-D secret-reference/workload-identity resolver;
- E5-E authorization-before-secret materialization;
- E5-F restricted-data adversarial fixtures;
- E5-G provider/domain allowlist;
- E5-H private-network worker reference.

Exit: a task/model cannot downgrade classification, select an unauthorized secret, or route restricted data to a forbidden provider.

## 8. Phase E6 — reliability and DR (#673)

Suggested slices:

- E6-A SLO/RPO/RTO declaration/report;
- E6-B readiness/liveness/degraded-state contract;
- E6-C backup manifest + encrypted-storage reference;
- E6-D deterministic restore verifier;
- E6-E coordinator-kill recovery test;
- E6-F provider outage/degraded-mode test;
- E6-G queue saturation/backpressure;
- E6-H incident/runbook evidence record.

Exit: the operator can prove restart/restore behavior against declared objectives.

## 9. Phase E7 — supply chain (#674)

Suggested slices:

- E7-A immutable Action/workflow reference checker;
- E7-B release dependency inventory;
- E7-C SBOM generation;
- E7-D provenance/attestation workflow;
- E7-E artifact verify command/runbook;
- E7-F release source/workflow binding;
- E7-G vulnerability-response policy;
- E7-H plan-aware capability preflight.

Exit: release artifacts can be traced to exact source/build identity, and provenance is verifiable without being misrepresented as correctness.

## 10. Phase E8 — optional G2/G3 control service (#675)

Do not begin by selecting Kubernetes/Postgres/Redis.

First freeze the service boundary:

- authenticated ingress;
- tenant context;
- authorization;
- idempotent command semantics;
- durable state interface;
- connector dispatch interface;
- audit event interface;
- health/readiness;
- migration lifecycle;
- backup/restore lifecycle.

Then choose implementation technologies using measured load and deployment constraints.

Suggested slices:

- E8-A service API contract;
- E8-B single-tenant reference process;
- E8-C durable store adapter;
- E8-D tenant middleware;
- E8-E worker/connector service boundary;
- E8-F observability;
- E8-G packaging/deployment reference;
- E8-H rolling/bounded-downtime upgrade + rollback.

Exit: G2 can restart without losing admitted state; G3 adds proven tenant isolation before being called multi-tenant.

## 11. Phase E9 — conformance pilot (#676)

Run destructive scenarios rather than a happy-path demo.

Required scenarios:

1. unauthorized actor;
2. cross-tenant ID substitution;
3. duplicate event;
4. coordinator crash after provider acceptance;
5. stale claim/retry;
6. provider outage/quota failure;
7. secret revoked/missing;
8. audit exporter unavailable;
9. restore from backup;
10. stale identity/policy cache;
11. high-risk self-approval attempt;
12. release provenance verification.

Every scenario records expected safe state and observed result.

## 12. Enterprise control matrix

| Domain | Primary issue | Required evidence |
| --- | --- | --- |
| profile/contract | #668 | schema + passing/negative preflight |
| tenant isolation | #669 | adversarial cross-tenant tests |
| identity/SoD | #670 | authorization fixtures + distinct actor tests |
| audit | #671 | tamper/replay/export evidence |
| data/secrets | #672 | forbidden egress/secret negative tests |
| reliability/DR | #673 | restart + restore evidence |
| supply chain | #674 | SBOM/provenance verification |
| service boundary | #675 | restart-safe G2 + tenant-safe G3 |
| conformance | #676 | destructive scenario report |

## 13. GitHub platform controls

Use platform capabilities where they strengthen the boundary:

- rulesets / protected branches;
- CODEOWNERS;
- Environments and deployment protection;
- OIDC/workload identity;
- GitHub Apps with least privilege;
- artifact attestations;
- organization audit capabilities;
- Dependabot/dependency review/security scanning where available.

Do not make plan-dependent capabilities silent requirements for G0. Enterprise preflight should report PASS/WARN/FAIL/UNKNOWN with the reason and feature availability.

## 14. Reliability targets are objectives, not claims

The example enterprise profile includes concrete targets to make the contract testable.

They become claims only after observed service/pilot evidence exists.

A useful enterprise report therefore separates:

~~~text
declared target
implemented mechanism
test evidence
observed production/pilot measurement
independent audit/certification
~~~

## 15. Development rules

Every enterprise implementation PR should include:

- exact threat/control being changed;
- tenant/authority/data-class impact;
- failure-path tests;
- least-privilege analysis;
- migration/backward-compatibility impact;
- observability/audit impact;
- rollback/recovery behavior;
- AI/tool provenance;
- explicit non-goals.

For security-sensitive changes, a green worker-generated test suite is necessary but not sufficient evidence for integration.

## 16. Immediate next order

1. land/review #668 baseline contract/preflight;
2. implement #669 and #670 in parallel;
3. use their types in #671/#672;
4. add #673/#674 operational controls;
5. build #675 only after the boundaries are stable;
6. run #676 before any production multi-tenant claim.

This sequence makes enterprise hardening an evidence program rather than a collection of infrastructure features.
