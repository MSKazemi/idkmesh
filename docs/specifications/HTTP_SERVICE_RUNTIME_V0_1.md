# HTTP Service Runtime Baseline v0.1

**Status:** experimental productionization baseline  
**Issue:** #677  
**Related:** #580 #597 #598 #607 #609 #572

## Purpose

IDKMesh has several HTTP-facing or browser-facing surfaces in development.
They should not each reinvent request correlation, operational probes, response
identity, or logging behavior.

This baseline defines dependency-free runtime behavior that can be reused by:

- the local Human Control Tower;
- future C7 control-plane HTTP services;
- GitHub/native evidence adapters that expose HTTP health;
- bounded self-hosted deployments.

It is deliberately smaller than an application framework.

## Required response metadata

Every HTTP response produced by an IDKMesh service using this baseline should
carry:

- `X-Request-ID`;
- `X-IDKMesh-Service`;
- `X-IDKMesh-Service-Version`;
- `X-IDKMesh-Read-Only`;
- `X-IDKMesh-API-Version` when an API version exists.

These headers describe the responding service and request. They do not grant
identity, authorization, trust, verification, or integration authority.

## Request correlation

A caller may send:

`X-Request-ID: <opaque-id>`

Accepted IDs are bounded to 128 characters and a conservative visible ASCII
alphabet. Invalid or oversized values are replaced with a locally generated
opaque identifier and are never reflected verbatim.

Request IDs:

- are correlation metadata only;
- are not user identity;
- are not authorization credentials;
- must not affect deterministic domain response bodies or content digests.

## Liveness and readiness

Services should separate:

### Liveness

`GET /healthz`

Answers only whether the process can serve requests.

### Readiness

`GET /readyz`

Answers whether the service runtime is ready to serve its declared API mode.

A readiness document may include service name, package version, mode, and API
version. It must not expose project state, run IDs, WorkUnits, evidence,
credentials, prompts, secrets, or user identity.

External dependency health should be added only when the service actually
depends on that dependency to satisfy its declared contract.

## Structured access logging

Access logging is opt-in through:

`IDKMESH_HTTP_ACCESS_LOG=1`

Each line is compact JSON containing only bounded operational metadata:

- event type;
- service;
- request ID;
- HTTP method;
- URL path without query string;
- response status;
- response byte count;
- duration;
- UTC event time.

The logging API intentionally does not accept request/response bodies or request
headers. This reduces the chance of leaking:

- authorization/session tokens;
- provider secrets;
- secret references;
- prompts;
- source code;
- evidence payloads;
- query-string data.

## Security boundary

This runtime is not authentication or authorization.

Responsibility remains split:

- C7 owns network/mutating HTTP authorization;
- C9 owns durable/idempotent run state;
- C10 owns actor identity, role, claim, and authority policy;
- C12 owns GitHub governance and secret-access preflight;
- C14 owns public-safe evidence publication;
- domain services own their own data validation and authority invariants.

A service marked `X-IDKMesh-Read-Only: true` must not silently expose a
write-capable endpoint.

## Determinism

Request correlation and operational metadata belong in headers/logs, not
deterministic domain documents.

For the same valid domain input, a deterministic read endpoint should preserve
the same response body and content digest even when:

- request IDs differ;
- access logging is enabled or disabled;
- a reverse proxy is present.

## Deployment profile

The baseline has no third-party runtime dependency and is suitable for the core
`pip install .` installation.

It does not require:

- OpenTelemetry;
- Prometheus;
- a service mesh;
- an external log collector;
- a database;
- an identity provider.

Those can be integrated later behind optional deployment profiles without
changing the base semantics.

## Exit gate

The baseline is ready to reuse when:

1. request IDs are safely propagated/replaced;
2. liveness and readiness are distinct;
3. stable service metadata appears on responses;
4. access logs are opt-in and payload-free;
5. direct unit tests cover injection/size boundaries;
6. at least one real IDKMesh HTTP surface consumes the baseline;
7. the consuming surface preserves its existing authority and determinism rules.
