# Interface stewardship: MCP JSON-RPC request IDs

Date: 2026-09-17

## Owner requirement

Continue improving IDKMesh APIs, interfaces, protocols, and communication surfaces through bounded, testable changes. Inspect current `main`, open issues and pull requests first, avoid duplicate work, preserve compatibility where practical, update tests/documentation with interface changes, and integrate only through the normal pull-request and CI gates.

## Repository inspection

The run started from protected `main@89722e621aa4f8d1e992fc0eb0267de06b5bb0df` after inspecting the open pull-request queue and existing interoperability tests. Two active documentation changes overlap nearby surfaces:

- #508 updates A2A semantic-identity documentation and the paper evidence map;
- #498 defines ACP protocol scope and also touches `interop/README.md`.

To avoid overlap, this change is limited to the MCP decoder, its focused regression tests, and this stewardship record.

## Finding

`from_mcp_tool_call()` already treats JSON-RPC `id` correctly as transport correlation rather than canonical Work Unit identity. A caller or gateway can therefore replace IDKMesh's generated request ID with its own string or integer without changing Work Unit semantics.

However, the decoder did not validate that the correlation identifier itself was protocol-valid. An in-memory envelope could omit `id`, use `null`, a JSON boolean, a floating-point value, array, or object and still reach Work Unit decoding if all other fields were valid.

## External protocol evidence

The current MCP 2026-07-28 specification was checked on 2026-09-17:

- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/index.mdx
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2026-07-28/schema.ts

The normative basic specification requires MCP requests to include a string or integer request ID and explicitly disallows `null`. The identifier is correlation state; it is not IDKMesh Work Unit identity.

## Decision and implementation

Add a narrow fail-closed request-ID validator at the MCP binding boundary:

- accept caller-selected strings;
- accept caller-selected integers;
- reject a missing ID;
- reject `null`;
- reject JSON booleans (Python `bool` must not pass accidentally as `int`);
- reject floating-point, array, and object IDs;
- leave canonical Work Unit identity anchored by the existing namespaced ID/digest metadata and canonical payload digest.

This is validation of the existing MCP wire contract, not a new IDKMesh protocol. No Work Unit schema, Work Contract schema, protocol version, tool name, or semantic identity field changes.

## Tests

`interop/tests/test_mcp_work_unit_identity.py` now preserves the positive transport-correlation cases (`"gateway-request-42"` and `42`) and adds fail-closed cases for missing and invalid request IDs.

The execution environment for this stewardship run could not resolve GitHub from its local shell, so no local full-suite result is claimed. Exact-head repository CI remains the integration evidence. The protected branch requires `gate (3.11)` and `gate (3.13)` before merge.

## Compatibility and risk

Existing conforming MCP clients are unchanged: string and integer correlation IDs continue to decode, independent of Work Unit identity. Only malformed request envelopes that the MCP specification does not permit are newly rejected.

The validation deliberately does not enforce request-ID uniqueness across outstanding requests because this protocol-neutral decoder has no transport/session request registry. That responsibility belongs to the caller/transport layer rather than a stateless Work Contract parser.

## Community impact

The boundary is easier for contributors and adapter authors to reason about: protocol-owned correlation identifiers may vary, but they still have to be valid MCP identifiers, while IDKMesh semantic identity continues to fail closed on its separate namespaced metadata and digest surfaces.

## AI/tool provenance

Prepared by the owner-controlled IDKMesh Interface Steward using ChatGPT, the connected GitHub integration, and current upstream MCP specification sources. This is not independent human review or external protocol certification.
