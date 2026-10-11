---
description: "Practical references for navigating installed source code, supported CLI commands, local HTTP endpoints, and troubleshooting."
---
# IDKMesh implementation reference

Use these alongside the [capability truth matrix](../CAPABILITY_MATRIX.md) and the [getting-started guide](../GETTING_STARTED.md):

1. [Module map](MODULE_MAP.md) — every direct `idkmesh/*.py` module, grouped by responsibility and linked to its versioned contract.
2. [CLI and HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) — shipped commands, routed local endpoints, read-only client, and runnable examples.
3. [As-built implementation architecture](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md) — current source paths, lifecycle boundaries, and separated authority.
4. [Troubleshooting and operator help](../help/TROUBLESHOOTING.md) — installation, SQLite, local API, verifier evidence, sandbox and tests.
5. [Dated code/documentation audit](../audits/2026-10-10-code-documentation-reconciliation.md) — precise review scope, source revision, unverified areas, and next steps.

For machine-readable protocol truth use [schemas](../../schemas/README.md); for complete HTTP payload rules consult [the Control Tower Local API contract](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md). Historical design catalogs are **not** a statement that an endpoint ships today.

**Maintenance discipline:** add or update documentation in the same PR when a CLI command, routed endpoint, module authority, source binding, schema, or safety boundary changes. Verify against current merged source and exact-head CI before publishing stronger claims.
