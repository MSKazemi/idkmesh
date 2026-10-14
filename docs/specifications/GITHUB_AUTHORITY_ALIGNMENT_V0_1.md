# GitHub authority alignment audit v0.1

**Status:** executable offline audit, a bounded remainder of C10 (issue
[#598](https://github.com/MSKazemi/idkmesh/issues/598)).
**Module:** [`idkmesh/github_authority_alignment.py`](https://github.com/MSKazemi/idkmesh/blob/main/idkmesh/github_authority_alignment.py).

## Why it exists

Two configurations describe the same GitHub actors and are maintained
separately:

| Configuration | Question it answers | Consumer |
|---|---|---|
| `GithubIdentityBindingTable` ([E3-B](ENTERPRISE_AUTHORIZATION_V0_1.md)) | Which enterprise roles, scopes and freshness does this numeric actor id have? | `enterprise_authz.authorize` |
| `GitHubDispatchAuthorizationPolicy` (C5-F, `github_dispatch_authorization.py`) | May this actor cross the issue-label dispatch gate? | `authorize_github_dispatch` |

Before this audit the two were kept in agreement only by one acceptance test
(`tests/test_c10_two_user_acceptance.py`), as recorded in the #598 progress
note. A maintainer could therefore trust an actor at the label gate while the
binding table said the actor was revoked, was a different login, or held no
role that the authorization policy lets dispatch.

## What it does

`audit_dispatch_authority_alignment(table, dispatch_policy, *,
authorization_policy=None, scope=None, now_epoch=None)` returns an
`AlignmentReport` of deterministically ordered findings (sorted by actor id,
then code). It is pure and read-only: it calls no network, resolves no secret,
mutates neither configuration and never allows or denies an action.

`error` findings (an actor can pass one gate while the other configuration
contradicts or cannot back that authority):

- `dispatch_actor_unbound`: trusted at the label gate, no binding.
- `dispatch_actor_login_mismatch`: same actor id, different login (case
  insensitive).
- `dispatch_actor_kind_mismatch`: the dispatch role `automation` must be bound
  to `github_app`/`github_actions`; `owner`/`maintainer`/`triager` to `human`.
- `dispatch_actor_binding_revoked`.
- `dispatch_actor_binding_expired`: only when `now_epoch` is supplied.
- `dispatch_actor_scope_missing`: only when `scope` is supplied.
- `dispatch_actor_lacks_kernel_dispatch_role`: the actor can cross the label
  gate (their C5 role is in the policy's `allowed_roles`) but holds no role,
  or has an actor type, that the authorization policy's `dispatch` rule
  allows. A policy with no `dispatch` rule leaves every such actor unbacked.

`warning` finding (drift that fails closed):

- `kernel_dispatcher_not_dispatch_gate_trusted`: a non-revoked binding holds a
  kernel dispatch role but cannot cross the label gate.

`aligned` means no `error` finding; `clean` means no finding at all. The
report's `to_dict()` always carries `"grants_authority": false`, and findings
carry actor ids, never login text.

## Boundaries

- An aligned report is evidence about configuration consistency, not an
  authorization decision. Both gates must still permit an action.
- Nothing calls this audit at runtime yet; a maintainer or CI job must run it
  against the reviewed configurations. No such job exists in this change.
- It does not link principals across identity providers, does not read
  CODEOWNERS or repository rulesets, and does not verify that executor
  provenance fed to the `verify` separation-of-duties rule is trustworthy;
  those remain open under #598.
