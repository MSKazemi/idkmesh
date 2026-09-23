# Enterprise Authorization Kernel v0.1

**Status:** experimental E3 foundation  
**Issue:** #670  
**Parent:** #667  
**Depends on:** E2 tenant scope (#669 / PR #690)

## Purpose

E2 answers:

> Which tenant/project owns this resource?

E3 answers:

> Is this authenticated actor/service allowed to perform this action against that exact resource and scope?

Enterprise execution must pass both checks. Scope is not authorization, and authorization cannot repair a scope mismatch.

## Trusted identity boundary

`ActorContext` is normalized identity input from a trusted authentication adapter.

It distinguishes:

- human;
- GitHub App;
- GitHub Actions workflow;
- IDKMesh/service identity;
- hosted provider;
- node.

An actor context contains:

- stable principal ID;
- actor type;
- trusted issuer;
- role set;
- tenant/project scope bindings;
- data clearance;
- identity revision;
- authenticated/revoked state;
- optional expiry.

Issue text, WorkUnit text, provider/model output, labels, comments, prompts, and ResultManifest content are **not** valid identity sources.

The existing `identity-binding-v0.1` contract remains provenance evidence only. It must not be promoted into authorization merely because it says an identity was verified.

## Role vocabulary

v0.1 uses:

- owner;
- admin;
- integrator;
- worker;
- reviewer;
- dispatcher;
- node_operator;
- auditor.

Roles are inputs from trusted identity/policy adapters. This module does not infer organization/team membership itself.

## Actions

The baseline kernel evaluates:

- read;
- claim;
- release;
- dispatch;
- execute;
- verify;
- integrate;
- manage_policy;
- audit_export.

The rule table is explicit and replaceable through `AuthorizationPolicy`.

## Baseline separation of duties

The default baseline preserves IDKMesh authority boundaries:

~~~text
worker/node       -> execute/claim, not integrate
reviewer          -> verify, not integrate
dispatcher        -> dispatch, not integrate
integrator human  -> integrate
owner/admin human -> policy/integration authority according to rule
provider/node     -> never integrate under the baseline
~~~

An actor can hold more than one trusted role, but the requested action is checked against its exact rule and actor type.

## High-risk distinct approval

For selected actions, effective risk at or above the rule threshold returns:

~~~text
requires_approval
~~~

until a distinct eligible approver is supplied.

The baseline requires distinct approval for high/critical:

- dispatch;
- execute;
- integrate;
- manage_policy (risk floor is high).

A principal cannot approve its own high-risk request.

The approver must:

- be a different principal;
- be bound to the same tenant/project;
- be authenticated, non-revoked, and non-expired;
- have an allowed approval role/type;
- have sufficient data clearance.

The request carries an explicit approval reference so later audit instrumentation can bind the decision to the external approval/review evidence.

## Risk floor

Policy rules may raise the effective risk of an action.

For example, `manage_policy` has a high risk floor. A caller cannot label a policy mutation "low" to bypass separation of duties.

The decision records both:

- requested_risk;
- effective_risk.

## Data classification

v0.1 uses:

~~~text
public < internal < confidential < restricted
~~~

The actor and approver must have clearance at least as high as the request classification.

This is an authorization attribute check only. E5 (#672) owns external-provider/egress policy; E3 does not make a restricted external route valid.

## Identity freshness

Authorization takes an explicit `evaluated_at_epoch`.

The actor/approver is denied or rejected as approval evidence when:

- unauthenticated;
- revoked;
- expired at the evaluation time.

The decision records the exact `identity_revision` and policy revision used. Later service caches must key/invalidate against those revisions; a stale cached decision is not permanent authority.

## Tenant isolation

The request has an explicit `TenantScope`, and its `ScopedResourceRef` must carry the exact same scope.

The actor and any approver must also be bound to that exact tenant/project.

A resource from another tenant/project returns `deny / scope_mismatch`.

The retained adversarial fixture is:

`tests/fixtures/enterprise_authz/cross-tenant-authorization.json`

## Decision effects

The kernel returns one of:

- `allow`;
- `deny`;
- `requires_approval`.

Representative stable codes include:

- `authorized`;
- `authorized_with_distinct_approval`;
- `scope_mismatch`;
- `actor_scope_denied`;
- `actor_unauthenticated`;
- `actor_revoked`;
- `actor_expired`;
- `actor_type_denied`;
- `role_denied`;
- `data_clearance_denied`;
- `distinct_approval_required`;
- `self_approval_forbidden`;
- `approver_scope_denied`;
- `approver_role_denied`.

## Decision is not execution

`AuthorizationDecision` is auditable policy evidence.

Its machine-readable projection always declares:

~~~json
{
  "authority": {
    "executes_action": false,
    "canonical_state_write": false,
    "merge": false
  }
}
~~~

An `allow` result means the trusted policy evaluator authorizes a later
executor to attempt that bounded operation. The decision object does not
perform the operation and cannot merge code on its own.

## Enterprise service integration

The future E8 service request path should be:

~~~text
authenticated request
 -> trusted ActorContext
 -> mandatory TenantScope
 -> ScopedResourceRef scope match
 -> AuthorizationPolicy evaluation
 -> allow / deny / requires_approval
 -> audit decision
 -> only then side effect / secret materialization / connector call
~~~

Authorization should run again when a relevant identity or policy revision changes.

## Non-goals

v0.1 does not claim:

- SAML/OIDC/GitHub authentication implementation;
- organization/team synchronization;
- a production policy database;
- policy caching;
- break-glass implementation;
- secret/egress enforcement;
- database row-level security;
- merge execution;
- regulatory certification.

Those remain E3/E5/E8 integration work.

## Exit gate for this foundation

1. actor/service identity has a strict normalized representation;
2. tenant/project scope is mandatory and exact;
3. role and actor type are both checked;
4. data clearance is checked;
5. revoked/expired identities fail closed;
6. policy risk floors prevent caller risk downgrades;
7. high-risk actions can require a distinct human approver;
8. worker/reviewer/provider/node cannot gain integration authority from task text;
9. decisions bind policy revision + identity revision;
10. decision evidence itself performs no side effect.
