# Enterprise Tenant Scope v0.1

**Status:** experimental foundation  
**Issue:** #669  
**Parent:** #667  
**Schema:** `schemas/enterprise-resource-ref-v0.1.schema.json`

## Purpose

Enterprise operational state must never rely on an unscoped run, claim,
candidate, audit, cache, queue, or idempotency identifier.

v0.1 defines the minimum scope identity:

```text
tenant_id + project_id
```

and makes that scope part of resource/storage identity.

## Core types

`TenantScope`:

```text
tenant_id
project_id
```

`ScopedResourceRef`:

```text
scope
resource_type
resource_id
```

The machine-readable projection is:

```json
{
  "kind": "idkmesh-enterprise-resource-ref",
  "schema_version": "0.1",
  "tenant_id": "tenant-a",
  "project_id": "project-main",
  "resource_type": "run",
  "resource_id": "run-17"
}
```

## Scope is identity

These are three different resources:

```text
tenant-a / project-main  / run / run-17
tenant-b / project-main  / run / run-17
tenant-a / project-other / run / run-17
```

The unscoped string `run-17` is insufficient for enterprise storage or API
authorization.

## Storage key contract

The reference implementation derives keys under:

```text
idkmesh/scope/v1/tenant/<tenant>/project/<project>/resource/<type>/<id>
```

Identifiers use a restricted alphabet and cannot contain path separators.

Storage adapters may use a different physical representation, but they must
preserve the same logical isolation and must never silently query by resource ID
alone.

## Caller scope

Ref-based operations require an explicit caller/request scope.

A resource reference with a different tenant or project fails with:

`scope_mismatch`

Changing a tenant ID in an otherwise valid resource reference must not turn
into access to another tenant's resource.

The retained adversarial fixture is:

`tests/fixtures/enterprise_scope/cross-tenant-reference.json`

## Idempotency

Enterprise idempotency keys are derived from:

- tenant ID;
- project ID;
- operation;
- logical request key;
- exact payload digest.

Therefore:

```text
same tenant + project + operation + logical key + payload
 -> same idempotency key

different tenant OR project OR payload
 -> different idempotency key
```

This prevents one tenant's replay/duplicate key from suppressing or aliasing
another tenant's work.

The resulting key is content-addressed and does not expose the logical request
key.

## Reference store

`ScopedMemoryStore` exists only as a deterministic conformance fixture.

It demonstrates:

- same resource ID in different tenants does not collide;
- same resource ID in different projects does not collide;
- cross-scope ref lookup/update/delete fails closed;
- scope listing stays inside the caller keyspace;
- store instances have no shared mutable global state.

It is **not** a production durable store.

C9/E8 storage implementations must apply the same scope contract at the
database/ledger/cache/queue/object-store query boundary.

## Authority boundary

Tenant scope answers:

> Which tenant/project namespace does this resource belong to?

It does **not** answer:

> Is this actor allowed to access it?

E3 (#670) owns authenticated actor/service identity and authorization.
A request must pass both:

```text
resource scope matches request scope
AND
actor/service policy authorizes the requested action
```

Neither check compensates for failure of the other.

## Non-goals

v0.1 does not claim:

- production multi-tenant database isolation;
- row-level security;
- organization membership;
- authentication;
- RBAC/ABAC;
- encryption at rest;
- durable transactions;
- distributed cache isolation.

Those controls belong to later E2/E3/E8 storage and service integrations.

## Exit gate for this foundation

1. tenant/project is part of resource identity;
2. storage keys are tenant/project scoped;
3. idempotency keys are tenant/project scoped;
4. retained tenant-substitution fixture fails closed;
5. same resource ID may safely exist in separate tenants/projects;
6. no class/global mutable store can silently bridge scopes;
7. published resource-ref schema matches the runtime projection.

Full E2 remains open until real durable/API/storage adapters consume the scope
contract and pass cross-tenant adversarial tests.
