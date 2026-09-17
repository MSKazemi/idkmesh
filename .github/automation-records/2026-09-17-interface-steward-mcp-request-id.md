# Interface stewardship: MCP JSON-RPC request IDs

Date: 2026-09-17

## Owner requirement

Continue improving IDKMesh APIs, interfaces, protocols, and communication surfaces through bounded, testable changes. Inspect current `main`, open issues and pull requests first, avoid duplicate work, preserve compatibility where practical, update tests/documentation with interface changes, and integrate only through the normal pull-request and CI gates.

## Repository inspection

This change started from protected `main@89722e621aa4f8d1e992fc0eb0267de06b5bb0df`. Active PRs #508 and #498 already modify nearby A2A/ACP documentation, so this work avoids those files and stays scoped to the MCP decoder and focused tests.

## Finding

`from_mcp_tool_call()` correctly treats JSON-RPC `id` as transport correlation rather than canonical Work Unit identity, but it did not validate that the correlation identifier itself was protocol-valid. A malformed in-memory envelope could omit `id`, use `null`, a JSON boolean, floating-point value, array, or object and still reach Work Unit decoding if the rest of the envelope was valid.

## External protocol evidence

Checked on 2026-09-17 against MCP 2026-07-28:

- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/index.mdx
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2026-07-28/schema.ts

The normative basic specification requires every request to include a string or integer ID and explicitly disallows `null`.

## Decision and implementation

Add a narrow fail-closed request-ID validator at the MCP binding boundary:

- accept caller-selected strings and integers;
- reject missing, `null`, boolean, floating-point, array, and object IDs;
- explicitly reject Python `bool`, which is an `int` subclass but serializes as a JSON boolean;
- keep canonical Work Unit identity anchored independently by the existing namespaced Work Contract ID/digest and canonical payload digest.

This enforces the existing MCP wire contract. It does not change the Work Unit schema, Work Contract schema, protocol version, tool name, or semantic identity fields.

## Validation and compatibility

Focused tests preserve positive caller-owned correlation IDs (`"gateway-request-42"` and `42`) and add fail-closed cases for missing/invalid IDs. The first exact-head CI run found only repository-documentation bookkeeping failures caused by initially placing this record under the published `docs/conversations/` tree; the implementation tests themselves were not implicated. This record was moved to `.github/automation-records/` to keep the protocol change focused and avoid unnecessary sitemap/index churn. Exact-head protected CI must be green before merge.

Request-ID uniqueness across outstanding requests is intentionally not enforced here because this protocol-neutral decoder has no outstanding-request registry. That responsibility belongs to the caller/transport layer.

## Community impact and provenance

The boundary is easier for adapter authors to reason about: correlation IDs may vary without changing a Work Unit, but malformed MCP identifiers fail early and predictably. Prepared by the owner-controlled IDKMesh Interface Steward using ChatGPT, the connected GitHub integration, and current upstream MCP specification sources. This is not independent human review or external protocol certification.
