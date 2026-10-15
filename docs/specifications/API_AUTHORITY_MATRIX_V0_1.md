---
description: "Which authenticated principal may call which Control Tower endpoint: the proposed endpoint-to-authority mapping for the network profile, built on the enterprise authorization kernel, and what is enforced today."
---
# API Authority Matrix v0.1

**Status:** **proposed** mapping for the network/multi-user profile; the served API enforces only the local profile described below  
**Issue:** #743 (API-8), #670; parent #713  
**Authority:** documentation and a completeness guard. It enforces nothing and grants no authority.

## What is true today

The Control Tower API is a **loopback, single-token, read/inspect** service. It
authenticates a *local session* (the `X-IDKMesh-UI-Token` header), not a person or
a service. No request carries a principal, a role or a tenant; no endpoint
distinguishes callers; and nothing served records a decision, dispatches work,
verifies a candidate, pushes or merges. The session token is a local boundary, not
an identity ([Control Tower Local API](CONTROL_TOWER_LOCAL_API_V0_1.md)).

The "Enforced today" column below states exactly that, per endpoint. The other
columns are the **proposal** a network profile would have to enforce, expressed in
the vocabulary of the [Enterprise Authorization Kernel](ENTERPRISE_AUTHORIZATION_V0_1.md):
an `ActorContext` from a trusted authentication adapter, a role from the kernel's
role set, and one of the kernel's actions. Scope is not authorization and
authorization does not repair a scope mismatch: every project-scoped row needs
both the tenant/project check and the action check. Nothing in this matrix may be
read as already implemented, and adopting it as the network profile is a human
decision (issue #743).

## Matrix: endpoints the server serves

Roles are the kernel's: `owner`, `admin`, `integrator`, `worker`, `reviewer`,
`dispatcher`, `node_operator`, `auditor`. "Any" means any authenticated principal
bound to the project. Data-class floors use the kernel's `public < internal <
confidential < restricted`.

| Endpoint | Kernel action | Scope | Proposed roles | Data-class floor | Enforced today |
|---|---|---|---|---|---|
| `GET /healthz` | none (probe) | none | unauthenticated | public | loopback Host check only |
| `GET /readyz` | none (probe) | none | unauthenticated | public | loopback Host check only |
| `GET /api/v1/status` | `read` | deployment | any | public | session token |
| `GET /api/v1/openapi.json` | `read` | deployment | any | public | session token |
| `GET /api/v1/metrics` | `read` | deployment | owner, admin, auditor, node_operator | internal | session token |
| `GET /api/v1/metrics/prometheus` | `read` | deployment | owner, admin, auditor, node_operator | internal | session token |
| `GET /api/v1/connections` | `read` | project | owner, admin, dispatcher, integrator, auditor | internal | session token |
| `GET /api/v1/connections/{connection_id}` | `read` | project | owner, admin, dispatcher, integrator, auditor | internal | session token |
| `GET /api/v1/connector-drivers` | `read` | deployment | owner, admin, dispatcher, integrator, auditor | internal | session token |
| `GET /api/v1/projects/{project_id}` | `read` | project | any | internal | session token |
| `GET /api/v1/work-units` | `read` | project | any | internal | session token |
| `GET /api/v1/work-units/{work_unit_id}` | `read` | project | any | internal | session token |
| `GET /api/v1/runs` | `read` | project | any | internal | session token |
| `GET /api/v1/runs/{run_id}` | `read` | project | any | internal | session token |
| `GET /api/v1/runs/{run_id}/attempts` | `read` | project | any | internal | session token |
| `GET /api/v1/runs/{run_id}/evidence` | `read` | project | owner, admin, integrator, reviewer, auditor | confidential | session token |
| `GET /api/v1/events` | `read` | project | any | internal | session token |
| `GET /api/v1/events/stream` | `read` | project | any | internal | session token |
| `POST /api/v1/run-evidence/inspect` | `read` | none (validates a supplied report; persists nothing) | any | the supplied report's class | session token |

Notes:

- Every served endpoint is read-only or inspect-only, so every row maps to the
  kernel's `read`. No row maps to `dispatch`, `execute`, `verify`, `integrate`,
  `manage_policy` or `audit_export`, because the server exposes none of them.
- `GET /api/v1/runs/{run_id}/evidence` is the one read held at a higher floor: the
  retained report can contain candidate and verification detail.
- Access to a resource outside the caller's tenant/project is `404`, not `403`, so
  existence does not leak ([API Conventions §6](API_CONVENTIONS_V0_1.md)).

## Matrix: endpoints that do not exist yet

| Endpoint | Required authority | Why it is not served |
|---|---|---|
| `POST /api/v1/human-decisions` | a human `ActorContext` (never a service, provider or node), role `integrator`, `owner` or `admin`; kernel action `decide` (defined in the baseline policy, human actors only, high-risk decisions need a distinct human approver); `human_decision_gateway.py` enforces it and writes one audit event per attempt | needs a live authenticated, accountable principal, which the local session token is not; owned by #740 (blocked on #670 identity/policy and #743 network boundary). The gateway is transport-neutral and unrouted: no HTTP path calls it |
| any dispatch, verify, integrate or policy-management endpoint | the matching kernel action, with the kernel's separation of duties | out of scope for the local API by design |

The kernel's baseline separation of duties applies unchanged: a worker or node
never integrates, a reviewer verifies but does not integrate, a dispatcher
dispatches but does not integrate, and a provider or node never integrates.

## What the guard checks

`tests/test_api_authority_matrix.py` keeps this document honest:

- every endpoint in the running server's discovery document has a row, and every
  row marked as served is in the discovery document, so a new route cannot ship
  without an authority decision;
- every kernel action and role named exists in `idkmesh.enterprise_authz`;
- no served row maps to a mutating action;
- the "enforced today" claim is checked against the code: every `/api/v1` route
  answers `403 invalid_session_token` without the token, and no route accepts a
  principal.

## Not covered

- Enforcement. Adopting the network profile means building an authentication
  adapter that produces `ActorContext` and wiring `authorize()`, TLS and rate
  limiting in front of each row (#743). The checks exist as a library
  ([Network API Security Profile](NETWORK_API_SECURITY_PROFILE_V0_1.md)), but no
  served listener calls them.
- Per-tenant data partitioning of the store ([API Storage Profiles](API_STORAGE_PROFILES_V0_1.md)
  keeps tenant boundaries as a requirement, not an implementation).
- The authority of the GitHub-first profile, which is GitHub identity and branch
  protection rather than this API.
