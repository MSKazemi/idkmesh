---
description: "Enterprise Data Policy Kernel v0.1: pure, fail-closed decisions for external processing, egress, credential kinds and secret access, plus a deterministic raw-secret scanner for JSON documents."
---
# Enterprise Data Policy Kernel v0.1

**Status:** experimental E5 foundation; decision kernel and raw-secret scanner, neither wired into any runtime path  
**Issue:** #672  
**Parent:** #667  
**Depends on:** [Enterprise Control Profile](ENTERPRISE_CONTROL_PROFILE_V0_1.md), [Enterprise Authorization Kernel](ENTERPRISE_AUTHORIZATION_V0_1.md)

## Purpose

The enterprise control profile declares which data classes may be admitted, which
may be processed by an external provider, the egress default, the secret backend
and whether long-lived cloud keys are allowed. Before this kernel nothing read
those declarations. `idkmesh/enterprise_data_policy.py` turns them into pure
allow/deny decisions that can be recorded in the audit ledger.

A decision is evidence only. It performs no network I/O, reads no environment
variable and no secret value, and never executes, merges or accepts anything.

## Decisions

| Function | Question | Denies when |
|---|---|---|
| `decide_external_processing` | May data of this class go to this provider? | the profile is invalid; the class is unknown or not admitted; the profile flag **for that exact class** is not true; the provider is malformed or not on the explicit approved list |
| `decide_egress` | May a worker reach this host? | the destination is not a bare hostname; any allowlist entry is malformed; the profile default is deny and the host is not an exact allowlist entry |
| `decide_credential` | May this credential kind be used? | the kind is unknown; the profile has no secret backend; the kind is not supplied by the profile's backend; a long-lived cloud key is requested while the profile forbids it or uses workload identity |
| `authorize_secret_access` | May this secret be accessed now? | there is no prior `AuthorizationDecision`; its effect is not `allow` (`requires_approval` is not enough); its action is not `dispatch` or `execute`; `requested_backend` differs from the profile backend; the credential decision denies |

## Rules that are easy to get wrong

- **Eligibility does not compensate.** The check for one data class never reads
  the flag of another, so a permissive `public` setting cannot excuse a
  `restricted` request.
- **Hostnames are exact.** No URL, port, userinfo, path, wildcard or suffix
  match is ever expanded; a malformed allowlist entry denies everything instead
  of being skipped.
- **Allowlist arguments must be collections.** Approved-provider IDs and egress
  host allowlists reject scalar strings/bytes, mappings, malformed entries, and
  more than 256 entries. They accept bounded iterables including generators;
  a scalar string cannot accidentally become a list of one-character entries.
  Invalid collections deny with `invalid_approved_providers` or
  `invalid_allowlist`; neither is interpreted as permission.
- **The profile chooses the secret source.** Provider or task text can only
  corroborate the backend, never select it.
- **Only a side-effecting stage unlocks a secret.** Secret materialization
  follows an allowed `dispatch` or `execute` decision, as in the authorization
  flow. An allow for `read`, `claim`, `release`, `verify`, `integrate`,
  `manage_policy` or `audit_export` does not.
- **Decisions never echo untrusted text.** The `subject` is the value only when
  it is a well-formed identifier; otherwise it is the marker `<invalid>`.

## Decision shape

Each decision serialises to a fixed shape (`kind`, `schema_version`, `control`,
`effect`, `code`, `message`, `subject`, and an `authority` block whose four
flags are all false) that carries identifiers and reason codes only.

## Raw-secret scanner

`idkmesh/enterprise_secret_scan.py` is the other half of "raw secrets never
enter WorkUnits, results or audit": the kernel above decides who may *obtain* a
secret, the scanner checks that a JSON-shaped document does not already
*contain* one. `scan_for_secrets(document)` returns a report and never raises on
content; `assert_no_secrets(document, context=...)` raises `SecretLeakError`
unless the report is clean.

| Rule | Detects |
| --- | --- |
| `private_key_block` | a PEM `PRIVATE KEY` header (public certificates are not flagged) |
| `github_token` | `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` and `github_pat_` tokens |
| `aws_access_key_id` | `AKIA`/`ASIA` access key ids |
| `slack_token` | `xoxa`/`xoxb`/`xoxp`/`xoxr`/`xoxs` tokens |
| `google_api_key` | `AIza` API keys |
| `api_key_sk` | `sk-`, `sk-ant-` and `sk-proj-` API keys of at least 32 characters |
| `jwt` | three-part JWTs whose header and payload start `eyJ` |
| `bearer_credential` | `Bearer` followed by at least 20 token characters |
| `url_userinfo` | `scheme://user:password@host` |
| `sensitive_key_literal` | a literal string of at least 8 characters under an exact credential-named key (`password`, `api_key`, `authorization`, `token`, ...) |

Properties:

- **A finding never carries the matched text.** It holds a rule id and a JSON
  Pointer location only: no prefix, length or hash. A mapping key that is not a
  short plain identifier, or that itself looks like a secret, appears as
  `<key:N>`, so a secret used as a key cannot leak through the location.
- **Fail-closed.** A depth, node or string-size limit, or a value that is not
  JSON-shaped (bytes, sets, arbitrary objects, non-string keys), makes the
  report `complete: false`, and an incomplete report is never `clean`.
  Defaults: depth 32, 100,000 nodes, 262,144 characters per string.
- **References are not secrets.** `env:NAME`, `secret:...`, `vault:...`,
  `${NAME}`, `<placeholder>` and `***` values are accepted under credential
  keys, matching the secret-reference convention of `connector_secrets`.
  Key matching is exact, so `max_tokens` and `secret_ref` are not credential
  keys.
- **Deterministic and linear.** Traversal is iterative and sorted; every pattern
  uses bounded quantifiers, and a test bounds CPU time on pathological inputs.

Limits, stated plainly: a clean report is evidence about the scanned text only.
Formats without a rule, encoded or split values, low-entropy passwords, and
credential values shorter than 8 characters under a credential key are not
detected. The scanner performs no I/O, reads no environment variable, and grants
no authority; it does not redact (redaction stays in `connector_secrets`).

## Not in this slice

- Wiring the kernel in front of connectors, workers or `connector_secrets`.
- An egress allowlist and an approved-provider list in the profile schema. They
  are function arguments today; adding them to the schema is a separate
  decision.
- Calling the scanner from the WorkUnit, result or audit write paths. The
  scanner below exists; nothing invokes it yet.
- Detecting secrets the scanner has no rule for (see its limits).
- Recording decisions in the audit ledger.
