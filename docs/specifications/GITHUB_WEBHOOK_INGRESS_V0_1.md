# GitHub Webhook Ingress v0.1

Status: experimental contract
Tracking issue: #578

## Purpose

This contract defines the authenticated, bounded ingress boundary for GitHub-triggered IDKMesh coordination.

It covers only C5-A/C5-B:

- raw webhook signature verification;
- delivery/event/action parsing and allowlists;
- exact configured-repository binding;
- minimal actor/issue/label identity projection;
- raw-payload provenance digest.

It does **not** create a WorkUnit, choose a connector, resolve a secret reference, authorize dispatch, create a run, or write back to GitHub.

## Security order

The receiver processes one request in this order:

```text
bounded raw bytes
 -> required security/identity headers
 -> HMAC-SHA256 over exact raw bytes
 -> delivery/event syntax
 -> event allowlist
 -> strict UTF-8 JSON (duplicate keys + non-finite numbers rejected)
 -> action allowlist
 -> repository binding
 -> sender/issue/label identity
 -> minimal envelope + sha256(raw body)
```

Signature verification precedes JSON parsing. An invalid signature on malformed JSON is therefore an authentication failure, not a parser oracle.

## Required headers

- `X-Hub-Signature-256` — canonical `sha256=<64 lowercase hex>`;
- `X-GitHub-Delivery` — bounded opaque delivery identity;
- `X-GitHub-Event` — canonical lowercase event name.

Header names are matched case-insensitively. Multiple spellings of the same required header in one mapping are rejected as ambiguous. Unrelated HTTP headers are ignored and do not become authorization policy.

Legacy `X-Hub-Signature` / SHA-1 is not accepted.

## Webhook secret

The v0.1 application boundary receives the webhook secret at runtime and never places it in the normalized envelope or error details.

The reference implementation requires at least 16 secret bytes. Deployment guidance should use a high-entropy secret and a secret manager; this module does not resolve secret references itself.

## Bounded body

The default raw-body limit is 1 MiB. Configuration may lower it or increase it up to a hard 8 MiB ceiling.

Requests over the configured limit fail before payload parsing.

## Initial allowlist

The default event allowlist contains only `issues`.

The initial allowed `issues` actions are:

- `opened`;
- `edited`;
- `labeled`;
- `unlabeled`;
- `reopened`;
- `closed`.

Other events/actions fail with `policy_denied` until a maintainer-owned configuration explicitly admits them. Admission to this parser is still **not dispatch authorization**.

## Repository binding

The payload `repository.full_name` must match the configured `owner/name` project identity case-insensitively. The normalized envelope retains the configured spelling.

A foreign repository is a `conflict`, not a routeable event.

## Normalized envelope

`GitHubWebhookEnvelope v0.1` contains only:

- schema version;
- delivery ID;
- event and action;
- configured repository identity + GitHub repository numeric ID;
- sender login + numeric ID;
- issue number when applicable;
- label name only for label actions;
- optional installation numeric ID;
- `sha256:` digest of the exact raw payload bytes;
- raw payload byte count.

Issue title/body/comment text is deliberately omitted. Later preview logic may retrieve or bind issue content under its own exact-revision/provenance rules.

## Label semantics

A label name in the envelope is untrusted intent metadata. It cannot choose credentials, executable argv, filesystem/network permissions, merge authority, or a connector by itself.

Later C5 routing/authorization slices must compare it to maintainer-owned policy and canonical RoutingDecision evidence.

## Error mapping

The reference implementation reuses the shared `ConnectorError` vocabulary:

- `authentication_error` — missing/noncanonical/bad signature;
- `result_normalization_error` — ambiguous headers, malformed delivery/event, strict-JSON failure, or missing identity fields;
- `policy_denied` — event/action not allowlisted;
- `conflict` — repository mismatch.

Errors do not retain the raw body, signature, or webhook secret.

## Negative invariants

The ingress envelope must not contain:

- dispatch approval;
- a WorkUnit;
- RoutingDecision;
- connector/credential selection;
- secret references;
- run ID;
- verification or acceptance verdict;
- push/merge/integration authority.

## Next boundaries

C5-C may consume the authenticated delivery ID + payload digest for idempotency/replay protection.

C5-D may use the repository + issue number to build an exact issue-to-WorkUnit preview under a separate read/provenance boundary.

C5-F/G remain responsible for actor authorization and explicit dispatch. Passing C5-A/B never implies either.

## Reference implementation

- `idkmesh/github_webhook_ingress.py`
- `tests/test_github_webhook_ingress.py`

Related contracts:

- `CONNECTOR_CONTROL_API_V0_1.md`
- `API_CONVENTIONS_V0_1.md`
- `GITHUB_FIRST_OPERATIONS_V0_1.md`
