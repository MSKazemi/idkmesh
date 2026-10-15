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

## Command line

```bash
idkmesh github-authority-audit --bindings bindings.json \
  --trusted-actors trusted-actors.json \
  [--scope TENANT/PROJECT] [--now-epoch N] [--json]
```

The verb is a thin file front end over `audit_dispatch_authority_alignment`.
It reads exactly the two named files (regular files, at most 2 MiB, strict
UTF-8 JSON, duplicate keys and `NaN`/`Infinity` rejected) and writes nothing:
no network, no GitHub call, no secret, no output file, and no clock read. Expiry
is checked only when `--now-epoch` is given and scope only when `--scope` is
given, exactly as in the library. The authorization policy is always the
enterprise baseline.

| Exit | Meaning |
|---|---|
| `0` | No `error` finding (`warning` findings may be present) |
| `1` | At least one `error` finding; the report is still printed |
| `2` | A file is missing, unreadable or invalid, or a flag is invalid; stdout is empty and `error: ...` goes to stderr |

`--json` prints the report's `to_dict()` as compact JSON with sorted keys and a
trailing newline, so equal inputs give byte-identical output. Without it a short
text summary is printed. Neither form contains login text: findings carry the
numeric actor id, and if a loader message would contain a login that appears in
the supplied files it is replaced by `<login>`.

`--bindings` is the table documented in
[Enterprise authorization](ENTERPRISE_AUTHORIZATION_V0_1.md) (schema
`schemas/enterprise-github-identity-binding-v0.1.schema.json`), parsed by the
real `parse_identity_binding_table`.

`--trusted-actors` is a plain-data serialisation of
`GitHubDispatchAuthorizationPolicy`. No repository-configured trusted-actor
file existed before this verb (the policy was only constructed in code), so
this document is the format the command reads; the repository does not ship an
instance of it. It is parsed by `parse_dispatch_trusted_actors_document`, which
rejects unknown fields and delegates role vocabulary, unique ids and logins,
the `owner/name` repository form and non-empty lists to the dataclass itself:

```json
{
  "kind": "idkmesh-github-dispatch-trusted-actors",
  "schema_version": "0.1",
  "repository": "owner/name",
  "dispatch_labels": ["agent-ready"],
  "trusted_actors": [
    {"actor_id": 1001, "login": "maintainer-login", "role": "owner"}
  ],
  "allowed_roles": ["owner", "maintainer"],
  "allowed_installation_ids": [12345]
}
```

`allowed_roles` and `allowed_installation_ids` are optional and default as in
the dataclass. There is no JSON Schema for this document yet.

## Boundaries

- An aligned report is evidence about configuration consistency, not an
  authorization decision. Both gates must still permit an action.
- Nothing calls this audit at runtime, and no workflow or CI job runs it. A
  maintainer can run it by hand with `idkmesh github-authority-audit` (below);
  wiring it into CI is a separate reviewed change because workflows are a
  protected area (see `docs/reference/GITHUB_ACTIONS_CODE_MAP.md`).
- It does not link principals across identity providers, does not read
  CODEOWNERS or repository rulesets, and does not verify that executor
  provenance fed to the `verify` separation-of-duties rule is trustworthy;
  those remain open under #598.
