# Enterprise Control Profile v0.1

**Status:** experimental implementation contract  
**Date:** 2026-09-22  
**Schema:** ../../schemas/enterprise-control-profile-v0.1.schema.json  
**Example:** ../../examples/enterprise-control-profile.example.json  
**Tool:** ../../tools/enterprise_profile.py  
**Program:** #667; E1 implementation: #668

## 1. Purpose

The Enterprise Control Profile is a versioned, machine-readable statement of the control posture a project/deployment intends to enforce.

It exists so "enterprise" is not an adjective. A deployment can state, review, diff, test, and later observe concrete controls for tenancy, identity, data movement, secrets, audit, recovery, supply chain, and emergency change.

A profile declaration is **not evidence that the control is actually enforced**.

The v0.1 preflight tool performs deterministic declaration/contradiction checks. Later issues bind those declarations to observed GitHub/service/runtime evidence.

## 2. Version and kind

v0.1 uses:

~~~json
{
  "api_version": "idkmesh.io/v1alpha1",
  "kind": "EnterpriseControlProfile"
}
~~~

Breaking semantic changes require a new explicit profile/schema version.

## 3. Conformance status

Preflight findings use:

- PASS — the declaration satisfies this v0.1 baseline check;
- WARN — usable but weaker than the recommended enterprise baseline, plan-dependent, or requires operator review;
- FAIL — contradictory or below a non-compensating baseline invariant;
- UNKNOWN — reserved for later observed checks where evidence cannot be retrieved.

A profile is declaration-ready when it has zero FAIL findings.

Declaration-ready does not mean production-ready, secure against every threat, independently audited, or certified.

## 4. Profile sections

### metadata

Required fields:

- name;
- environment: development / staging / production;
- enforcement_mode: audit / enforce.

Production enterprise profiles must use enforcement_mode=enforce.

### deployment

Fields:

- profile: G0 / G1 / G2 / G3;
- tenant_mode: single_project / single_organization / multi_tenant;
- tenant_isolation: not_applicable / declared / enforced;
- network_mode: public / controlled_egress / private_network.

Rules:

- G3 must use multi_tenant + tenant_isolation=enforced;
- G0/G1 cannot claim shared multi-tenant service isolation;
- G2 is normally dedicated/single-organization;
- missing tenant context is never interpreted as a default tenant.

### identity

Fields:

- human_identity_source: github / enterprise_sso / oidc / saml;
- service_identity: github_actions / github_app / oidc_workload / managed_identity;
- mfa_required;
- high_risk_separation_of_duties.

Production requires MFA and high-risk separation of duties in the baseline.

This does not require IDKMesh to become an identity provider. Identity should normally federate from GitHub/enterprise IdP and be normalized into stage-specific authorization context.

### data

Fields:

- default_classification;
- external_processing_allowed_classes;
- egress_mode.

Minimum classifications:

- public;
- internal;
- confidential;
- restricted.

restricted must not appear in external_processing_allowed_classes.

Production should use allowlist or deny_by_default egress rather than unrestricted egress.

### secrets

Fields:

- backend;
- workload_identity;
- long_lived_cloud_keys_allowed.

Backends:

- github_environment;
- external_secret_manager;
- provider_managed.

Workload identity:

- none;
- github_oidc;
- external_oidc;
- managed_identity.

Production G2/G3 must not rely on long-lived cloud keys and should use a workload identity when external/cloud service access is required.

Secret references are configuration metadata. Raw values must not be stored in this profile.

### audit

Fields:

- append_only;
- integrity;
- retention_days;
- external_export_required;
- actor_policy_revision_required.

Integrity modes:

- git_history;
- hash_chain;
- external_worm.

Production requires append-only audit and actor/policy-revision binding. G2/G3 production requires external export capability.

The baseline recommends at least 365 days retention. Shorter retention is WARN rather than a universal FAIL because legal/organizational requirements vary.

### reliability

Fields:

- availability_target_percent;
- rpo_minutes;
- rto_minutes;
- restore_test_interval_days;
- backpressure_required.

These are objectives, not measured claims.

Production requires backpressure. Restore tests less frequent than every 90 days produce a warning in v0.1.

### supply_chain

Fields:

- immutable_action_pins_required;
- sbom_required;
- provenance_attestation_required;
- vulnerability_response_sla_hours.

Production requires immutable action pinning for the controlled release/security lanes and an SBOM declaration.

Provenance attestation is strongly recommended; the preflight reports WARN rather than FAIL when disabled because platform/plan/release applicability varies.

### change_management

Fields:

- high_risk_two_person_rule;
- break_glass:
  - enabled;
  - time_bound_minutes;
  - reason_required;
  - audit_required.

Production requires the high-risk two-person rule.

If break-glass is enabled it must be time bounded, reason required, and audit required.

## 5. Non-compensating invariants

These controls cannot be offset by better model quality, lower cost, more reviewers, or administrator confidence:

1. tenant mismatch;
2. unknown/expired authority;
3. restricted-data external-processing prohibition;
4. missing high-risk separation of duties where required;
5. raw secret persistence;
6. direct worker/verifier integration authority;
7. missing durable audit for privileged production actions;
8. missing recovery state for a service claiming restart-safe execution.

Future routing and admission must apply these as hard eligibility checks.

## 6. Required enterprise audit context

Later runtime implementations should be able to bind privileged events to:

~~~text
tenant/project
request/correlation/run ID
initiating actor
effective service identity
action
resource
exact revision
risk/data classification
policy version
decision
approval/reason reference
outcome
evidence/result digest
timestamp
integrity linkage
~~~

The profile declares the required posture; #671 implements the durable event contract.

## 7. Separation from WorkUnit

EnterpriseControlProfile is repository/deployment policy.

WorkUnit is bounded task intent.

A WorkUnit may tighten enterprise policy for one task. It cannot relax it.

Examples:

- project allows external processing for public/internal, WorkUnit says public only -> public only;
- project forbids restricted external processing, WorkUnit requests it -> reject;
- enterprise profile requires high-risk two-person rule, WorkUnit says one reviewer -> still two-person;
- project forbids long-lived cloud keys, task text cannot authorize one.

## 8. Separation from compliance

The profile may eventually support mappings to external control frameworks, but v0.1 intentionally does not contain a field such as compliant=true.

A deployment may retain evidence useful to an audit. Certification/attestation by an external authority remains separate.

## 9. Preflight tool

Run:

~~~bash
python tools/enterprise_profile.py examples/enterprise-control-profile.example.json
python tools/enterprise_profile.py examples/enterprise-control-profile.example.json --json
~~~

Exit behavior:

- 0: no FAIL findings;
- 1: one or more FAIL findings;
- 2: profile cannot be parsed/inspected.

The tool never:

- mutates GitHub;
- provisions infrastructure;
- changes identity/roles;
- creates secrets;
- claims controls are observed;
- grants execution or merge authority.

## 10. GitHub enterprise surfaces

Where available and appropriate, an implementation can use GitHub rulesets, Environments/protection rules, OIDC, artifact attestations, GitHub Apps, organization identity, and audit capabilities.

These are implementation surfaces beneath the IDKMesh control contract. Availability varies by GitHub plan/repository visibility and must be detected rather than assumed.

## 11. Evolution

v0.1 is experimental.

#668 can complete the declaration contract and deterministic preflight. #669-#676 progressively bind it to observed runtime/platform evidence.

The contract should grow only when a control needs stable machine-readable meaning. Vendor-specific details belong in adapters/extensions rather than in the shared core where possible.
