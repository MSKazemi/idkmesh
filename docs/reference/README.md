# IDKMesh implementation reference

Use these alongside the [capability truth matrix](../CAPABILITY_MATRIX.md) and the [getting-started guide](../GETTING_STARTED.md):

1. [Module map](MODULE_MAP.md) — every direct `idkmesh/*.py` module, grouped by responsibility and linked to its versioned contract.
2. [CLI and HTTP quick reference](CLI_HTTP_QUICK_REFERENCE.md) — shipped commands, routed local endpoints, read-only client, and runnable examples.
3. [Source-backed API metrics interval guide](API_METRICS_INTERVAL_GUIDE.md) — a runnable Python-only comparison, fixed latency buckets, and safe handling of UNKNOWN windows.
4. API pages for integrators: [quickstart](API_QUICKSTART.md) (curl and the Python client), [error catalog](API_ERROR_CATALOG.md) (every stable code, status and retry rule), and [service limits](API_LIMITS.md) (timeouts, caps, body and header bounds) — each is drift-tested against the code.
5. [As-built implementation architecture](../architecture/AS_BUILT_IMPLEMENTATION_MAP.md) — current source paths, lifecycle boundaries, and separated authority.
6. [Troubleshooting and operator help](../help/TROUBLESHOOTING.md) — installation, SQLite, local API, verifier evidence, sandbox and tests.
7. [Research/interoperability module map](RESEARCH_MODULE_MAP.md) — experiments, simulations, randomness lab, A2A/MCP and evidence boundaries.
8. [Operational Python module map](OPERATIONS_MODULE_MAP.md) — tool/script navigation and explicit external side effects.
9. [GitHub Actions code and authority map](GITHUB_ACTIONS_CODE_MAP.md) — every workflow, its trigger families, explicit write scopes, relevant code and side-effect boundaries.
10. [Workflow-to-code audit](../audits/2026-10-13-workflow-code-trace.md) — pinned review and validation limits.
11. [Non-package audit](../audits/2026-10-13-nonpackage-python-audit.md) — source coverage, limitations, follow-up checks.
12. [Dated code/documentation audit](../audits/2026-10-10-code-documentation-reconciliation.md) — precise review scope, source revision, unverified areas, and next steps.

For machine-readable protocol truth use [schemas](https://github.com/MSKazemi/idkmesh/blob/main/schemas/README.md); for complete HTTP payload rules consult [the Control Tower Local API contract](../specifications/CONTROL_TOWER_LOCAL_API_V0_1.md). Historical design catalogs are **not** a statement that an endpoint ships today.

**Maintenance discipline:** add or update documentation in the same PR when a CLI command, routed endpoint, module authority, source binding, schema, or safety boundary changes. Verify against current merged source and exact-head CI before publishing stronger claims.
