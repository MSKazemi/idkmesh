# IDKMesh API v1 Requirements Traceability Matrix

**Date:** 2026-09-23  
**Status:** planning control document  
**Program:** #713  
**Planning PR:** #749

This matrix answers one question:

> For every property expected from a professional IDKMesh API, who owns the
> underlying capability, which API issue integrates it, and what evidence will
> prove it?

It prevents duplicate subsystem work and makes missing ownership visible before
implementation starts.

## Status vocabulary

- **existing owner** — canonical subsystem issue already exists;
- **API integration** — API-specific issue composes that subsystem into the
  public contract;
- **release evidence** — observable proof required before the capability is
  considered delivered.

## Contract and compatibility

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| one product HTTP namespace | ADR-0013 / planning PR #749 | #736 #738 | specs agree on `/api/v1`; no undocumented competing namespace |
| URL/object version rules | API conventions baseline | #736 | accepted lifecycle/version spec |
| stable error envelope/codes | Control Tower draft + conventions | #736 #737 | error schema + runtime conformance + compatibility test |
| public object schemas | existing domain schemas | #737 | all public refs resolve and runtime examples validate |
| OpenAPI accuracy | Control Tower draft | #737 #745 | OpenAPI validator + response/schema conformance |
| backwards compatibility | none complete | #737 #745 | automated breaking-change diff |
| deprecation/migration policy | none complete | #736 #746 | policy + migration guide template |

## Domain / resource model

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| WorkUnit identity | canonical WorkUnit contracts / #682 | #738 #739 | resource response binds canonical WorkUnit |
| route semantics | #570 connector kernel | #738 | no API-only RoutingDecision clone |
| run lifecycle | #682 Product Spine | #738 #739 | run state reconstructable through common service |
| candidate/result identity | #579 / ResultManifest contracts | #738 #739 | exact candidate/result digest visible |
| verification/evidence | verifier contracts / Run Evidence Report | #739 | evidence resource retains raw provenance |
| human decision | Human Decision Record schema / #682 | #740 | immutable digest-bound decision |
| integration execution | GitHub protected authority / ADR-0013 | future separate owner | no decision API merges/pushes |

## Read/query ergonomics

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| projects read | Product Spine / ProjectManifest | #739 | stable project resource |
| WorkUnit list/get | Product Spine | #739 | bounded cursor pagination |
| run list/get | Product Spine | #739 | deterministic list + detail |
| attempt/evidence detail | run/evidence contracts | #739 | complete run reconstruction |
| bounded filters | conventions | #736 #739 | unknown filter fails; page-size bounds |
| opaque cursors | conventions | #736 #737 #739 | schema + replayable pagination tests |

## Eventing and audit

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| GitHub-native durable events | #597 | #741 #750 | restart reconstruction |
| enterprise tamper-evident audit | #671 | #741 #743 #744 | integrity-link/replay/export proof |
| canonical event envelope | none frozen | #737 #741 | JSON Schema + append-only fixture |
| historical event query | #597 concepts | #741 | cursor query tests |
| resumable live stream | none | #741 | SSE reconnect/Last-Event-ID tests |
| no invented timestamps | Run Evidence boundary | #741 | source/event timestamp tests |
| security-event attribution | #671 #670 | #741 #743 | principal/policy/evidence refs |

## Identity, tenancy, authority

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| local session boundary | Control Tower draft | #735 | loopback/token negative tests |
| GitHub-first roles | #598 | #743 | two-actor authorization fixture |
| enterprise ActorContext/RBAC/ABAC | #670 | #743 | scope/role/risk negative matrix |
| tenant/project isolation | #669 | #739 #743 #750 | cross-tenant substitution tests |
| separation of duties | #598 #670 | #740 #743 | self-approval/high-risk negative tests |
| stale/revoked identity | #670 | #743 | freshness/revocation tests |
| GitHub governance/secret gate | #607 | #743 | protected/secret-bearing preflight evidence |
| integration authority separation | ADR-0013 / GitHub rules | #738 #740 | decision endpoint lacks merge/push authority |

## Data, secrets, privacy

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| data classification | #672 | #743 #750 | policy fixtures for public/internal/confidential/restricted |
| external-processing/egress policy | #672 | #743 | disallowed provider/egress fails closed |
| secret references only | #570 #607 #672 | #738 #743 | raw-secret negative tests |
| workload identity/OIDC | #607 #672 | #743 | short-lived identity example |
| evidence retention | #597 #671 | #750 | retention matrix |
| legal/audit retention hook | #671 | #750 | retained audit/export policy |
| telemetry data minimization | #677 #671 #672 | #744 | logs/metrics/traces contain no secret/raw evidence |

## Persistence and recovery

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| local restart-safe metadata | #616 | #750 | restart/idempotency fixture |
| GitHub-first durable ledger | #597 | #750 | killed-runner recovery |
| network durable storage | #675 | #750 | storage adapter/profile + migrations |
| schema migrations | #675 | #750 | forward migration test |
| backup/restore | #673 #675 | #750 | restore verification |
| RPO/RTO profile | #673 | #742 #750 | documented targets + exercise |
| corruption detection | digest/provenance contracts | #750 | tamper/corruption negative fixture |
| immutable history | #597 #671 | #750 | rewrite/deletion detectable |

## Mutation correctness

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| idempotency key | #616 #597 | #736 #740 | same key/same digest same result |
| key/digest conflict | #616 | #740 | same key/different request -> 409 |
| optimistic concurrency | #597 | #736 #740 #750 | concurrent writer conflict test |
| immutable human decision | Human Decision Record | #740 | update/rewrite rejected |
| audit event on mutation | #671 | #740 #741 | decision event retained |
| no hidden retry of side effects | conventions | #736 #746 | client/service tests |

## HTTP runtime and reliability

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| request IDs | #677 | #735 | safe reflection/replacement tests |
| liveness/readiness | #677 | #735 #744 | probes expose no project/secrets |
| service/version headers | #677 | #735 | response metadata tests |
| access logs | #677 | #744 | bounded body/token-free logs |
| request/header/body time/size limits | #677 baseline | #742 | boundary/slow-client tests |
| concurrency/queue bounds | none complete | #742 | overload test |
| 429/503 semantics | conventions | #742 | Retry-After tests |
| graceful drain | #673 #675 concepts | #742 | in-flight/drain test |
| provider outage/degraded mode | #673 | #742 | outage fixture |
| production transport | #675 | #743 #742 | no direct public stdlib-server exposure |

## Browser/network security

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| TLS/proxy boundary | #675 | #743 | deployment profile |
| trusted forwarded headers | API threat model | #743 | spoof/proxy tests |
| CORS | API threat model | #743 | allow/deny matrix |
| CSRF/origin for mutations | API threat model | #743 | browser mutation tests |
| request-smuggling normalization | API threat model | #743 #745 | proxy/backend fuzz |
| webhook verification/replay | #580 #607 | #743 #745 | signature/replay tests |
| SSRF/connector destination policy | #570 #672 | #743 #745 | blocked destination fixtures |
| rate-limit identity key | #670 | #742 #743 | per-principal tests |
| break-glass | #670 | #743 | explicit expiry/reason/audit tests |

## Observability / SRE

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| bounded logs | #677 | #744 | log schema/redaction |
| metrics | #673 operational goals | #744 | counters/histograms/gauges |
| tracing | none complete | #744 | W3C traceparent propagation |
| SLOs | #673 | #744 | declared + measured targets |
| dependency readiness | #673 | #744 | safe readiness detail |
| audit/SIEM export | #671 | #744 | export fixture |
| incident IDs | #673 | #744 | incident/audit correlation |

## Supply chain and release

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| pinned sensitive CI dependencies | #607 #674 | #745 #747 | workflow/dependency checks |
| SBOM | #674 | #747 | release SBOM |
| build provenance/attestation | #674 | #747 | exact source/workflow binding |
| vulnerability response policy | #674 | #747 | release policy |
| reproducible tagged API release | #374 #747 | #747 | tag + qualification report |

## Qualification

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| enterprise destructive pilot | #676 | #745 #747 | failure-mode report |
| contract conformance | none complete | #745 | repeatable CI artifact |
| parser/header fuzz | threat model | #745 | fuzz corpus/results |
| tenant/auth negative matrix | #669 #670 | #745 | security qualification |
| load/soak/memory | #673 goals | #745 | benchmark report |
| restore/recovery | #673 #676 | #745 #750 | restore exercise |
| exact-source release gate | project rules | #747 | exact tagged SHA evidence |

## Client/developer experience

| Requirement | Existing owner / source | API integration owner | Release evidence |
| --- | --- | --- | --- |
| Python SDK | none | #746 | typed supported client |
| TypeScript/web client | #572 consumer | #746 | generated/type-checked client |
| mandatory client timeouts | conventions | #746 | client tests |
| stable exception taxonomy | conventions/error catalog | #746 | public exception tests |
| no unsafe hidden mutation retry | idempotency rules | #746 | retry tests |
| quickstart/auth/error/limits docs | docs program | #746 | clean-user walkthrough |
| migration guides | #736 lifecycle | #746 #747 | migration template/release doc |

## Deployment-profile traceability

### G0 local operator

Must compose:

- #735 local API baseline;
- #677 runtime;
- #736/#737 contracts;
- no network mutation claim.

### G1 GitHub-native team

Must compose:

- #598 roles;
- #607 governance/secrets;
- #597 durable ledger;
- Product Spine #682;
- API conventions/read/decision/event surfaces as applicable.

### G2 self-hosted team service

Must additionally compose:

- #669 tenant/project scope even for one-org service where scoped identity is
  declared;
- #670 trusted identity/policy;
- #672 data/egress/secrets;
- #673 SLO/backup/restore;
- #675 service boundary;
- #742/#743/#744/#750 API operational integration;
- #745 qualification.

### G3 multi-tenant

Requires all G2 controls plus explicit multi-tenant isolation/destructive
qualification from #669/#676. G2 success does not imply G3 readiness.

## Gap rule

If implementation discovers a professional requirement that has:

1. no existing subsystem owner;
2. no API integration owner;
3. no named release evidence;

then work pauses and the traceability matrix/issue graph is updated before that
requirement is implemented.

## Maintenance rule

Any API planning or implementation PR that changes ownership, scope, deployment
profile, or release requirements must update this matrix or explain why no
traceability row changes.
