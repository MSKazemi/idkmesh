# GitHub-first deployment and multi-user architecture — 2026-09-22

## Project-owner question

Clarify the remaining implementation work after the external-project adoption guide, with special focus on multi-user deployment and the physical/runtime location of IDKMesh:

- does it need a permanent server?
- can it live primarily in the target GitHub repository?
- where do humans, agents, models, and local compute run?
- what additional work is needed to make this real?

## Repository findings

The repository already stated that GitHub can act as a bootstrap control plane and already runs useful event-driven pieces there, including issue/model routing and Jules dispatch. The active connector-control-plane tracker (#570) also proposes GitHub-first SCM integration, SQLite/GitHub bootstrap persistence, optional HTTP service, and a GitHub App only as a later hosted target.

The missing decision was to make the deployment default explicit.

## Decision

Adopt **GitHub-first, server-optional** as the recommended first product profile.

For a normal project:

- GitHub repository = canonical project/policy state;
- Issues/Projects = work queue;
- labels = routing/risk/readiness metadata;
- Actions = event-driven coordinator;
- branches/PRs = candidate code;
- checks/reviews = verification surfaces;
- GitHub identities/teams = bootstrap human identities;
- rulesets/protected main = integration authority;
- Git-native compact run/evidence ledger = durable restart-safe state;
- hosted agents/models run on provider infrastructure;
- optional `idkmesh-node` runs on local/volunteer/project machines for special compute.

No always-on project-owned server is required in the default profile.

## New implementation gaps created

- #596 — `idkmesh init --github` + reusable no-server workflow pack.
- #597 — durable GitHub-native run ledger + restart-safe/idempotent dispatch state.
- #598 — multi-user GitHub role/claim/authority policy.
- #599 — second-project no-server pilot.

These extend rather than replace #570 and its connector queue #574–#580.

## When a server should appear

A lightweight authenticated service should be introduced only after measured need for one or more of:

- lower-latency/high-volume webhook processing;
- high-frequency leases/heartbeats/work stealing;
- long-lived bidirectional agent sessions;
- multi-project/organization tenancy;
- enterprise/private-network requirements;
- live mutating Control Tower UI;
- state/query volume that no longer fits the Git-native ledger cleanly.

The second-project pilot (#599) is intended to test whether those limits are actually reached before the product makes a server mandatory.

## Community impact

This lowers the adoption threshold: a team can start with infrastructure it already uses (GitHub) and add local nodes or a control service only as requirements grow. It also keeps integration authority visible in existing GitHub governance instead of creating a second hidden authority system.
