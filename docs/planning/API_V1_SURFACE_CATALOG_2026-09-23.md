# IDKMesh API v1 Surface Catalog

**Date:** 2026-09-23  
**Status:** planned inventory; not a claim that every endpoint is implemented  
**Program:** #713  
**Convention owner:** #736  
**Architecture owner:** #738

This catalog gives the API program one visible inventory. “Planned” entries are
not promises of current behavior and must not appear as implemented in user
documentation until their owning issue is integrated.

## Status vocabulary

- **implemented-draft** — implementation exists on an unmerged PR and is not a
  canonical release surface;
- **design-existing** — a repository specification describes the behavior but no
  canonical HTTP implementation is released;
- **planned** — accepted into the API program issue graph;
- **future** — useful direction but not part of the declared first beta scope.

## Operational / discovery

| Surface | Status | Auth | Mutates | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| `GET /healthz` | implemented-draft (#658) | none | no | #677/#735 | process liveness only |
| `GET /readyz` | implemented-draft (#658) | none | no | #677/#735 | bounded runtime readiness only |
| `GET /api/v1/status` | implemented-draft (#658) | local session / future principal | no | #735 | capabilities and service contract |
| `GET /api/v1/openapi.json` | implemented-draft (#658) | local session / future principal | no | #735/#737 | machine-readable transport contract |
| metrics endpoint/adapter | planned | deployment-specific | no | #744 | exact path deferred |

## Evidence inspection

| Surface | Status | Auth | Mutates | Owner | Authority ceiling |
| --- | --- | --- | --- | --- | --- |
| `POST /api/v1/run-evidence/inspect` | implemented-draft (#658) | local session | no durable mutation | #735 | inspect/project evidence only |
| Gate Audit UI/API | existing specialized tool | local | no | #572 | diagnostic only |

The inspection POST is computational/read-only: it accepts an evidence document
and returns a deterministic projection. It is not a state-creating mutation.

## Project / WorkUnit read model

Owned by #739 after conventions/schema/architecture freeze.

| Surface | Status | Auth | Mutates |
| --- | --- | --- | --- |
| `GET /api/v1/projects/{project_id}` | planned | evidence/project read scope | no |
| `GET /api/v1/work-units` | planned | work read scope | no |
| `GET /api/v1/work-units/{id}` | planned | work read scope | no |

List endpoints require deterministic ordering, bounded page size, opaque cursor,
and enumerated filters.

## Run read model

Owned by #739.

| Surface | Status | Auth | Mutates |
| --- | --- | --- | --- |
| `GET /api/v1/runs` | planned | runs:read | no |
| `GET /api/v1/runs/{id}` | planned | runs:read | no |
| `GET /api/v1/runs/{id}/attempts` | planned | runs:read | no |
| `GET /api/v1/runs/{id}/evidence` | planned | evidence:read | no |
| `GET /api/v1/runs/{id}/decisions` | planned | decisions/read policy | no |

These surfaces expose canonical Product Spine/run/evidence objects rather than
inventing UI-only replacements.

## Human decision

Owned by #740.

| Surface | Status | Auth | Mutates |
| --- | --- | --- | --- |
| `POST /api/v1/human-decisions` | planned | trusted human/governance principal + decisions:write | creates immutable decision record |

Required:

- exact evidence-report digest;
- rationale;
- explicit decider;
- selected attempt validation;
- idempotency key;
- conflict semantics;
- immutable audit event.

Forbidden:

- Git push;
- merge;
- canonical application-code mutation;
- automatic conversion of verifier recommendation into a decision.

## Events

Owned by #741.

| Surface | Status | Auth | Mutates |
| --- | --- | --- | --- |
| `GET /api/v1/events` | planned | scoped read | no |
| scoped WorkUnit/run event query | planned | scoped read | no |
| resumable SSE stream | planned | scoped read | no |

The canonical event store is append-only. SSE is delivery, not canonical state.

## Connector/control plane

Existing design owner: #580/#570 and
`docs/specifications/CONNECTOR_CONTROL_API_V0_1.md`.

The legacy design currently names `/v1` paths. #736/#738 must reconcile these
into the common product namespace before implementation is frozen.

Intended use cases:

| Use case | Current design | Planned common ownership |
| --- | --- | --- |
| list/read project connections | design-existing | #580 + #738 |
| configure connection | design-existing | #580 + identity/policy |
| probe connection | design-existing | #580 |
| WorkUnit preview | design-existing | #580/#682 |
| route resolution | design-existing | #570/#580 |
| run creation | design-existing | #580/#682 |
| run cancel | design-existing | #580/#682 |
| run state | design-existing | #580/#739 |
| GitHub webhook ingress | design-existing | #580 + security profile |

No connector endpoint may bypass:

- secret-reference policy;
- zero-project-spend constraints;
- source/revision binding;
- principal authorization;
- idempotency where external side effects occur.

## Integration handoff

Integration execution is deliberately not part of the first Human Decision API.

Potential future surfaces are **future**, not first-beta commitments.

If introduced, they require:

- separate `integration:execute` authority;
- protected-repository policy;
- decision/evidence binding;
- idempotency;
- separation of duties;
- auditable postcondition.

No generic `POST /merge` endpoint is planned.

## Common public object catalog

Existing canonical/domain objects to reuse:

- ProjectManifest;
- DomainPack;
- WorkUnit;
- RoutingDecision;
- CandidateReference;
- ResultManifest;
- EvaluatorPlan;
- VerificationResult;
- Run Evidence Report;
- Human Decision Record;
- ActorContext;
- AuthorizationDecision;
- compute/resource admission contracts.

API-specific objects that #737 must freeze:

- API status;
- readiness document;
- inspection success envelope;
- API error envelope;
- list/page envelope;
- event envelope;
- read-model summaries/projections;
- Human Decision request/result envelope;
- idempotency/conflict metadata.

## Storage profiles

Storage is not a UI detail and not one universal backend.

- local developer metadata/idempotency composes #616;
- GitHub-first durable run/evidence/event state composes #597;
- network/multi-user storage profile is owned by #750.

All profiles must preserve the same canonical object identities/digests and
must not grant authority merely because they can persist a record.

## Authority matrix

| API class | Observe | Compute projection | Create durable record | Dispatch external work | Push/Merge |
| --- | ---: | ---: | ---: | ---: | ---: |
| status/read model | yes | bounded | no | no | no |
| evidence inspection | yes | yes | no | no | no |
| human decision | yes | validation | decision only | no | no |
| connector preview/route | yes | yes | maybe decision metadata | no unless explicit dispatch API | no |
| connector dispatch/run create | yes | yes | run/idempotency | yes with authorization | no |
| integration service (future) | yes | yes | audit/postcondition | maybe | only with separate protected authority |

## Beta-scope recommendation

The first API beta should include:

1. operational discovery;
2. complete project/WorkUnit/run/evidence read model;
3. canonical historical events + SSE;
4. immutable Human Decision recording;
5. selected connector-control operations needed for the Product Spine;
6. identity/policy integration for every mutation;
7. persistence/idempotency;
8. production runtime/security/observability profile;
9. official Python client and web client;
10. qualification evidence.

It need not include arbitrary integration execution, general-purpose admin APIs,
or every future provider adapter.

## Catalog maintenance rule

Any issue/PR that adds, removes, renames, or materially changes a public API
surface must update this catalog or explicitly state why the change is internal
only.
