---
description: "Enterprise Data Policy Kernel v0.1: pure, fail-closed decisions for external processing, egress, credential kinds and secret access, derived from the enterprise control profile."
---
# Enterprise Data Policy Kernel v0.1

**Status:** experimental E5 foundation; decision kernel only, not wired into any runtime path  
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

## Not in this slice

- Wiring the kernel in front of connectors, workers or `connector_secrets`.
- An egress allowlist and an approved-provider list in the profile schema. They
  are function arguments today; adding them to the schema is a separate
  decision.
- Scanning WorkUnits, results and audit records for raw secrets.
- Recording decisions in the audit ledger.
