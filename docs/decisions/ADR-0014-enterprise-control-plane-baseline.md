# ADR-0014 — Enterprise Controls Are an Overlay; G0 Remains the Default

**Status:** Proposed for adoption  
**Date:** 2026-09-22  
**Related:** #667, #668-#676, #570, #596-#599, #607

## Context

IDKMesh now has a clear GitHub-first, server-optional deployment direction. That is a product advantage: a team should not need to operate an always-on control service merely to use bounded WorkUnits, external agents, verification, and protected pull-request integration.

Enterprise users introduce additional requirements that are real but not universal:

- organization/tenant isolation;
- enterprise identity and separation of duties;
- private-network execution;
- central audit export and longer retention;
- stricter data-egress and secret controls;
- queryable operational state;
- measured availability/recovery objectives;
- change/incident-management integration;
- stronger release provenance;
- multi-project operation.

A common failure mode would be to respond by making every installation depend on a permanent server, database, queue, Kubernetes cluster, or enterprise identity provider. That would increase onboarding/operational cost before the need is proven.

The opposite failure mode would be to claim that a GitHub repository and Actions automatically satisfy hostile multi-tenant or regulated enterprise requirements. They do not.

## Decision

Adopt an explicit enterprise control overlay.

1. G0/G1 remain the default onboarding and small-team deployment profiles.
2. Enterprise control requirements are expressed in a versioned Enterprise Control Profile.
3. The profile is policy input and conformance metadata; it does not grant authority by declaration.
4. G2/G3 services are introduced only when a measured product requirement or an explicit enterprise control requires persistent infrastructure.
5. GitHub remains canonical code/integration authority in G0-G3 unless a later ADR explicitly changes that boundary.
6. G3 shared control planes require tenant scope on every mutable operational resource and authorization decision.
7. Enterprise policy is deny-by-default for unknown tenant, identity, data classification, secret authority, or high-risk approval state.
8. Worker, verifier, dispatcher, integrator, and administrator authority remain distinct.
9. Privileged decisions require attributable audit records and durable evidence references.
10. Enterprise readiness/conformance must not be described as formal compliance certification.

## Why this decision

This preserves the simplest useful deployment while creating a serious path for organizations that need stronger controls.

It also prevents infrastructure from becoming a proxy for security. A large cluster without tenant isolation, policy-bound identity, recovery evidence, or authority separation is not enterprise-ready.

Conversely, GitHub-native controls can satisfy many small-team requirements without a new service. The architecture should add complexity only at the boundary where the simpler profile stops satisfying explicit controls.

## Consequences

### Positive

- normal users keep a low-operations G0/G1 path;
- enterprise controls become inspectable/versioned instead of implied;
- hosted services can be introduced with a clear reason and acceptance gate;
- multi-tenancy becomes a hard system boundary rather than a UI concept;
- compliance marketing cannot outrun engineering evidence;
- control-plane code can be tested against explicit failure modes.

### Costs

- more policy/schema surface;
- tenant context must propagate through future APIs/state stores;
- enterprise audit/DR/supply-chain controls add operational work;
- G2/G3 implementations will require stronger security review and destructive testing;
- some GitHub/platform features vary by plan and must be detected rather than assumed.

### Rejected alternatives

**Make a server mandatory now.** Rejected because it would burden the default product before evidence shows it is needed.

**Treat GitHub organization roles as the entire authorization model.** Rejected because enterprise actions depend on tenant/resource/risk/data context and stage-specific authority.

**Use one super-admin service identity for all automation.** Rejected because it destroys least privilege, provenance quality, and separation of duties.

**Call the baseline "compliant."** Rejected because engineering controls and internal conformance are not independent certification.

## Implementation

- #668: Enterprise Control Profile and preflight;
- #669: tenant isolation;
- #670: identity/authorization/SoD;
- #671: audit ledger/export;
- #672: data/egress/secrets;
- #673: SLO/DR;
- #674: supply chain;
- #675: optional G2/G3 service;
- #676: destructive conformance pilot.

See ../architecture/ENTERPRISE_CONTROL_PLANE.md and ../specifications/ENTERPRISE_CONTROL_PROFILE_V0_1.md.
