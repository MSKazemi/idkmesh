# Enterprise Control Profile v0.1

**Status:** experimental  
**Issue:** #668  
**Parent:** #667  
**Schema:** `schemas/enterprise-control-profile-v0.1.schema.json`

## Purpose

The Enterprise Control Profile declares the controls that an IDKMesh deployment
is expected to enforce.

It is deliberately a **policy input**, not an authorization object and not
evidence that any control is actually deployed.

Every valid v0.1 profile says:

```json
{
  "profile_role": "policy_input_only",
  "control_evidence": "declared_not_observed",
  "grants_runtime_authority": false
}
```

That separation prevents a configuration file from being presented as proof of
compliance, security, or effective enforcement.

## Deployment profiles

The control profile uses the existing G0/G1/G2/G3 deployment vocabulary.

### G0 — local operator

- one trusted local operator;
- local process coordinator;
- no remote API;
- process identity;
- single-project scope.

This profile is useful for local CLI/Control Tower development. It is not an
enterprise multi-user claim.

### G1 — GitHub-native team

- GitHub is the human identity source;
- GitHub Actions is the service execution identity;
- coordinator is ephemeral;
- no long-lived remote control API;
- GitHub protected integration remains canonical;
- high-risk work requires distinct approval;
- egress defaults to deny.

This is the primary serverless/team enterprise path.

### G2 — self-hosted team service

- one project or organization boundary;
- long-lived control service;
- remote API enabled;
- federated/external human identity;
- workload/service identity stronger than process identity;
- backups and restore exercises required;
- default-deny egress.

G2 is the first profile that needs normal always-on service operations.

### G3 — multi-tenant service

G3 adds mandatory tenant scope and stronger controls:

- tenant scope must be `multi_tenant`;
- long-lived remote service;
- federated workload identity;
- distinct high-risk approval;
- enabled tamper-evident audit;
- backups + restore testing;
- default-deny egress;
- immutable action pins, SBOM, and build/release provenance.

G3 is not implied by G2 and requires the E2/E3 isolation/identity program.

## Control domains

The v0.1 document covers:

- deployment/tenant mode;
- human and service identity sources;
- separation-of-duty requirements;
- integration authority boundaries;
- data classification and external-processing policy;
- secret backend and long-lived-key policy;
- audit enablement/retention/export;
- declared reliability objectives;
- backup/restore requirements;
- software-supply-chain controls;
- change-management/break-glass controls;
- audit vs enforce mode.

## Non-compensating invariants

The dependency-free validator rejects contradictory profiles before runtime
admission.

Examples include:

- `enforce` mode with unknown controls configured to `warn`;
- break-glass enabled without audit and required rationale;
- OIDC workload identity while long-lived cloud keys are allowed;
- G1 configured with local-only human identity;
- G2 without a long-lived control service;
- G2/G3 without required backup/restore behavior;
- G3 without multi-tenant scope;
- G3 without tamper-evident audit;
- G3 without immutable pins, SBOM, and provenance;
- any enterprise profile that allows workers or verifiers to merge;
- any profile that permits raw secret material in WorkUnits/evidence;
- default data classification not present in the admitted classification set.

These checks are intentionally fail-closed.

## Structural vs semantic validation

Two layers are retained:

1. **JSON Schema Draft 2020-12** — published machine-readable structure,
   enums, required fields, and authority constants.
2. **`idkmesh.enterprise_profile`** — standard-library parser and semantic
   validator for cross-field contradictions.

Core `pip install .` does not require the optional `jsonschema` dependency
to perform the semantic validation boundary.

Repository CI meta-validates the schema when `jsonschema` is available.

## Examples

Retained examples:

- `examples/enterprise/g1-github-native.example.json`;
- `examples/enterprise/g2-self-hosted.example.json`.

They are examples of **declared target controls** only.

A valid example does not prove:

- the GitHub ruleset exists;
- an IdP actually authenticated a user;
- backups were successfully restored;
- audit records are complete;
- an SBOM was generated;
- a provider respected an egress policy.

Observed/enforced evidence belongs to E9 conformance and the relevant runtime
control domains.

## Versioning

`schema_version: "0.1"` is frozen once durable external profiles rely on it.

A change is breaking when:

- a previously valid profile may become invalid;
- an existing field changes meaning;
- deployment-profile semantics are tightened in a way that changes admission.

Breaking changes require a new schema version/file.

Additive fields should still be introduced deliberately because this v0.1
schema rejects unknown fields to prevent typo-driven policy bypass.

## Authority

This profile never grants:

- repository write authority;
- merge authority;
- secret access;
- worker execution;
- verifier acceptance authority;
- tenant access.

Runtime services must combine the declared profile with actual authenticated
actor/service identity, resource state, policy version, and enforcement
evidence.

## Relationship to the enterprise program

This contract is E1 under #667.

Follow-on work:

- E2 (#669) tenant/project isolation;
- E3 (#670) identity/RBAC/ABAC/separation of duties;
- E4 (#671) tamper-evident audit;
- E5 (#672) data/egress/secrets;
- E6 (#673) SLO/backup/DR;
- E7 (#674) supply chain;
- E8 (#675) hosted control service;
- E9 (#676) destructive conformance pilot.

## Exit gate

E1 is complete when:

1. the schema meta-validates;
2. retained G1 and G2 examples validate;
3. dependency-free runtime validation rejects contradictory profiles;
4. profile semantics remain declaration-only and grant no authority;
5. breaking-change/version rules are documented.
