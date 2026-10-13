---
description: "Enterprise Authorization Kernel v0.1: may this authenticated actor perform this action on this exact resource and scope? Scope is not authorization."
---
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
reviewer          -> verify (never work they executed), not integrate
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

## Verifier is not the executor

A principal that executed the work must not verify it. The rule mirrors the
distinct-approval threshold: `PolicyRule.executor_distinct_at_risk` is a risk
threshold, and an `AuthorizationRequest` carries `executor_principal_ids`, the
principals that executed the work under review.

At or above the threshold (effective risk, after the rule's floor):

- no `executor_principal_ids` returns `deny / executor_identity_required`. This is
  fail-closed on purpose: a rule the caller could disable by omitting a field
  would not be a control;
- the actor's `principal_id` among them returns
  `deny / self_verification_forbidden`. It is a plain `deny`, not
  `requires_approval`, because no approver can make the executor an acceptable
  verifier of their own work. Taking part in a multi-party execution is enough.

The baseline `verify` rule sets the threshold to `low`, so it applies at every
risk. A project that accepts self-verification for low-risk work must say so in
its policy by raising the threshold to `medium`; below the threshold the field
is ignored and an omitted executor is tolerated. `None` disables the rule. The
check runs after the role, actor-type and data-class checks, so a principal
without the `verify` role still gets `role_denied`. The field is ignored for
every other action.

Callers must take `executor_principal_ids` from the retained run or attempt
record, never from the verifier's own claim. The kernel can show that the actor
is not among the principals it was told about; it cannot establish that the list
is complete or true.

## Identity freshness

Authorization takes an explicit `evaluated_at_epoch`.

The actor/approver is denied or rejected as approval evidence when:

- unauthenticated;
- revoked;
- expired at the evaluation time.

The decision records the exact `identity_revision` and policy revision used. Later service caches must key/invalidate against those revisions; a stale cached decision is not permanent authority.

### Freshness-bound decision cache (E3-D)

`idkmesh/enterprise_authz_cache.py` provides `AuthorizationDecisionCache`, a bounded LRU in front of `authorize`. Its guarantees are structural:

- the key digests the whole normalized actor and approver (roles, scopes, clearance, `revoked`, expiry, `identity_revision`), the executor principal set, the policy id, revision and a digest of the rule content (including `executor_distinct_at_risk`), and the scope/resource/action/risk/data class, so a cached ALLOW for one executor set is never replayed for another. A revoked, re-scoped or demoted identity, or an edited policy, is a miss even when no revision string was bumped;
- `request_id` and `evaluated_at_epoch` are not in the key. Time is enforced by the entry window `[stored_at, valid_until)`, where `valid_until` is the earliest of the max age (default 300 s), the actor expiry and the approver expiry. An identity that has expired never keeps cached authority, and a clock that moves backwards cannot revive an entry;
- `invalidate_principal` drops every entry that used a principal as actor or approver, for a revocation feed;
- every operation (lookup, store, eviction, `invalidate_principal`, `clear`) is serialised by one lock, so concurrent request threads cannot corrupt the LRU order or the hit/miss counters, and a revocation cannot interleave with a lookup into a stale ALLOW;
- a hit is re-stamped with the new `request_id` and `evaluated_at_epoch` and still carries no execution, state-write or merge authority.

No live service consumes the cache yet; wiring it in front of dispatch/API enforcement is E3-F.

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
- `self_verification_forbidden`;
- `executor_identity_required`;
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

## E3-B: trusted GitHub identity adapter

`idkmesh.enterprise_identity_github` (schema:
`enterprise-github-identity-binding-v0.1.schema.json`) is the first trusted
authentication adapter that produces an `ActorContext`. It composes with
this kernel rather than replacing any of its checks.

Two inputs, both already trusted before this adapter runs:

- `GithubActorClaims` — already-authenticated GitHub actor fields (a
  verified webhook's `sender_id`/`sender_login`, or a GitHub Actions run's
  own `github.actor`/`github.actor_id` context). Issue/PR/comment title and
  body text is never a claims source.
- `GithubIdentityBindingTable` — a maintainer-reviewed, versioned table
  binding each trusted numeric GitHub actor id to its `ActorContext` roles,
  tenant/project scopes, data clearance, and issuer. The numeric actor id is
  the primary trust key, because a GitHub login can be renamed or re-registered
  while the numeric id cannot; a login reused under a different id, or an id
  whose login changed, is denied rather than trusted. This matches the
  actor-id-primary pattern `idkmesh.github_dispatch_authorization` uses for the
  separate C5 dispatch lane, which answers a different question — may this actor
  dispatch — and returns a boolean decision rather than an `ActorContext`. No
  module on `main` builds `GithubActorClaims` from a live webhook or Actions
  payload yet; that producer is E3-F scope.

`actor_context_from_github` fails closed with `GithubIdentityAdapterError`
for:

- an actor id with no reviewed binding;
- a login that does not match the id's bound login;
- a GitHub actor kind (human user vs. bot) inconsistent with the bound
  `actor_type` — a `human` binding backed by a bot account, or a
  `github_app`/`github_actions` binding backed by a human account, is a
  configuration or spoofing mismatch, not a valid identity.

It does not re-check revocation or expiry itself. Those live on the
resolved `ActorContext` and are enforced exactly once, by this kernel's own
`authorize`, so the adapter and the kernel cannot disagree about what
"expired" means.

`enterprise-github-identity-binding-v0.1` field-level identity errors
(an unknown role, an invalid data clearance, ...) are validated by
`ActorContext` itself and surface as this kernel's own
`AuthorizationContractError`, not a separate error type — the binding
contract composes with `ActorContext`'s validation rather than
duplicating it.

This closes only the GitHub identity source. E3-E (audited break-glass grant), E3-F (dispatch/API
enforcement integration) and E3-H (service middleware/conformance) remain open E3 slices, and
E3-G (two-principal acceptance fixture) is delivered for the enterprise kernel only (see below); E3-C (enterprise
IdP/OIDC/SAML adapter) is covered separately below.

## E3-C: enterprise IdP adapter contract (OIDC/SAML/SSO)

`idkmesh.enterprise_identity_oidc` (schema:
`enterprise-oidc-identity-binding-v0.1.schema.json`) is a trusted
authentication adapter that produces an `ActorContext` from an enterprise
identity provider reached through OIDC, SAML, or another SSO protocol. It
composes with this kernel rather than replacing any of its checks, the same
way the E3-B GitHub identity adapter does.

Two inputs, both already trusted before this adapter runs:

- `OidcIdentityClaims` — already-verified IdP claims (an OIDC ID token's
  `iss`/`sub`/`aud`/`iat`/`exp`, or the equivalent normalized fields of a
  verified SAML assertion). Issue/PR/comment title and body text is never a
  claims source, and signature/assertion verification happens upstream —
  this adapter never re-derives trust from an unverified token. No module on
  `main` builds these claims from a live IdP response yet; that producer is
  E3-F scope.
- `OidcIdentityBindingTable` — a maintainer-reviewed, versioned table
  binding each trusted `(issuer, subject)` pair to its `ActorContext` roles,
  tenant/project scopes, data clearance, and expected relying-party
  audience. Unlike E3-B's single numeric GitHub actor id, a subject claim is
  only unique within its issuing IdP, so the composite `(issuer, subject)`
  pair is the primary trust key: the same subject string bound under two
  different issuers is two distinct identities, not a collision.

`actor_context_from_oidc` fails closed with `OidcIdentityAdapterError` for:

- claims already expired at the supplied evaluation time — an OIDC/SAML
  claim is an ephemeral per-session credential with its own `exp`, distinct
  from the durable identity's own expiry, so this check runs before any
  binding lookup;
- claims not yet valid at that evaluation time — the comparison is
  two-directional, so a post-dated claim and a caller whose clock precedes the
  claim's own `issued_at_epoch` are both refused rather than read as fresh;
- an `(issuer, subject)` pair with no reviewed binding;
- claims whose `audience` does not match the binding's configured
  relying-party audience (a token replayed against the wrong relying
  party).

`issuer`, `subject` and `audience` are opaque IdP-controlled strings that this
adapter only ever compares, so they are compared byte for byte and a value
carrying leading or trailing whitespace is refused rather than trimmed. Trimming
would fold every leading and trailing variant of the code points Python's
`str.strip()` removes — TAB, NBSP, IDEOGRAPHIC SPACE and 26 others — onto one
bound identity, and `audience` is this adapter's replay check.

It does not re-check revocation, or the *bound identity's* own expiry,
itself. Those live on the resolved `ActorContext` and are enforced exactly
once, by this kernel's own `authorize`, so the adapter and the kernel cannot
disagree about what "revoked" or "expired" means for the underlying
identity — only claim freshness is this adapter's own concern.

`enterprise-oidc-identity-binding-v0.1` field-level identity errors (an
unknown role, an invalid data clearance) are validated by `ActorContext`
itself and surface as this kernel's own `AuthorizationContractError`, not a
separate error type — the binding contract composes with `ActorContext`'s
validation rather than duplicating it. Structural errors in the table
document (missing or unknown fields, a wrong `kind`/`schema_version`, an
unsupported `actor_type`, a duplicate `(issuer, subject)` pair) stay with
the adapter and raise `OidcIdentityAdapterError`.

This closes only the enterprise IdP identity source. E3-E (audited break-glass grant), E3-F
(dispatch/API enforcement integration, including a live claims producer for
both this adapter and E3-B) and E3-H (service middleware/conformance) remain open E3
slices; E3-G (two-principal acceptance fixture) is delivered for the enterprise kernel only.

## E3-G: two-principal acceptance fixture (enterprise kernel)

`tests/test_enterprise_two_principal_acceptance.py` drives the shipped enterprise kernel together --
`authorize` behind `AuthorizationDecisionCache`, with every outcome appended to the
[Enterprise Audit Ledger](ENTERPRISE_AUDIT_LEDGER_V0_1.md) -- using fake `ActorContext` identities only.
The GitHub two-user case is owned by `tests/test_c10_two_user_acceptance.py` (#598) and is not repeated.
What the fixture pins:

- proposer, dispatcher, reviewer and integrator paths: a worker cannot dispatch or integrate, a reviewer
  verifies, and high-risk dispatch, execute and integrate each need a distinct authorized approver (a missing
  approver, the actor itself, a wrong-role approver, a provider approver and an other-tenant approver all stay
  `requires_approval`);
- a cached ALLOW granted with one approver is not served to a different approver, a demoted approver, no
  approver, or the actor itself;
- a cached ALLOW is never served across a tenant boundary, including the same principal id and resource id in
  another tenant, and the audit ledger lists each tenant's events only;
- revocation, expiry, and a policy edit (with or without a revision bump) are re-evaluated and the denied or
  `requires_approval` outcome is recorded with its reason code; a stale ALLOW cannot be audited as the
  revoked identity's decision once its `identity_revision` has moved;
- audit events carry reason codes and revisions, never the decision message or identity claims.

Known gaps this fixture exposes but does not change (policy semantics are owned by the policy author, not the test):

- **Cross-action separation of duties is now explicit, not automatic (#598).** The kernel still evaluates one
  request at a time and does not remember who executed what. The baseline `verify` rule now refuses a principal
  listed in `executor_principal_ids` (see "Verifier is not the executor"), but only as true as the list the caller
  supplies from its retained record. Nothing yet calls `verify` in production, so no enforcement point builds that
  list; E3-F must do so.
- **No principal linking.** Self-approval is compared on `principal_id`. The same human reachable under two
  principal ids (for example two IdPs) is two principals to the kernel.
- **The audit event names the policy by id and revision only.** An edit that does not bump `revision` is a cache
  miss and is evaluated correctly, but the ledger cannot show that the rule content changed. Bump the revision on
  every edit.
- **`approval_reference` is stored verbatim.** It is validated as an identifier only, so a token-shaped value
  would be retained in the decision and the audit event. Callers must pass an opaque review reference, never a credential.

This does not wire the cache into live dispatch or API paths (E3-F), implement break-glass (E3-E), or add a
service middleware conformance check (E3-H).

## Non-goals

v0.1 does not claim:

- live OIDC/SAML/SSO token or assertion verification, or a live IdP claims
  producer — E3-C only normalizes already-verified claims into
  `ActorContext`; verifying a token/assertion against a real IdP is E3-F
  scope;
- a live GitHub claims producer — E3-B normalizes already-authenticated
  GitHub actor claims only; building `GithubActorClaims` from a verified
  webhook envelope or Actions run context is likewise E3-F scope;
- organization/team synchronization;
- a production policy database;
- a live consumer of the decision cache (the cache exists, see E3-D; wiring it into dispatch/API enforcement is E3-F);
- break-glass implementation;
- secret/egress enforcement (the decision kernel exists, see [Enterprise Data Policy Kernel](ENTERPRISE_DATA_POLICY_V0_1.md), but is not wired into any runtime path);
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
