# Interop branch rescue and A2A v1 conformance correction

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Context

The branch-convergence pass identified `interop-runtime-integration` as a large orphan branch with two very different kinds of work:

- a stale `node/` runtime overlapping the current canonical worker path;
- unique A2A/MCP Work Contract bindings that had never reached a pull request.

The correct convergence action was **not** to merge the 100+ commit-behind branch wholesale. The interop-only delta was rescued onto current `main` through PR #181, while the obsolete node runtime was left out.

## PR #181 — useful rescue, one conformance defect

PR #181 restored:

- `interop/bindings.py`;
- A2A/MCP mapping documentation;
- interop tests;
- a scoped CI workflow.

It also widened Work Unit support from hard-coded schema v0.1 to the additive supported set `{0.1, 0.2}` and added tests so future schema drift cannot silently rot the bindings again.

However, post-merge spec review found one A2A v1 conformance bug:

```python
A2A_PROTOCOL_VERSION = "1.0.0"
```

A2A distinguishes a specification patch release from the negotiated protocol version. Protocol negotiation uses `Major.Minor` such as `1.0`; patch versions do not affect compatibility and should not be sent in requests/responses/Agent Cards.

A2A clients also carry the `A2A-Version` service parameter on requests, and extension activation is represented by `A2A-Extensions`.

## PR #183 — narrow correction

PR #183 corrected the rescued binding without reopening the stale source branch or touching the canonical node path.

Changes:

- negotiated A2A protocol version is now `1.0`;
- the transport-neutral envelope explicitly models:

```text
A2A-Version: 1.0
A2A-Extensions: https://idkmesh.org/extensions/work-contract/v0.1
```

- the decoder fails closed if the internal A2A version, negotiated service version, or extension activation is absent/mismatched;
- tests cover wrong version and missing extension activation;
- docs explain that a future HTTP adapter maps these neutral service parameters to standard headers or allowed request parameters;
- MCP remains pinned to `2026-07-28` and is otherwise unchanged.

Exact PR #183 head:

`376cb8dcf8099affea6d8e95c5e52c1cc79bfeee`

Exact-head checks:

- Interoperability bindings check `33195609555` — success;
- IDKGraph `33195608625` — success;
- Evolution `33195608657` — success.

PR #183 merged as:

`a0b4a9c811b68b6139fc34d423f3e0d0ec4c2f6e`

## Authority boundary

The rescued interop binding remains a semantic envelope/round-trip layer, not a network runtime or acceptance authority.

```text
external A2A/MCP execution completion
    !=
IDKMesh verified/accepted/integrated
```

The full canonical Work Unit remains carried with a digest, and external completion still normalizes to:

```text
execution_status = succeeded
acceptance_status = pending_verification
```

No node changes, candidate execution authority, verifier authority, push/approval/merge authority, or automatic integration behavior were added.

## Next interoperability work

Issue #17 remains open for the parts not yet demonstrated:

1. validate the semantic binding against official A2A v1 SDK/TCK types and current MCP SDK/generated types;
2. build at least two heterogeneous coordinator-facing adapters (local plus A2A or MCP);
3. perform one bounded end-to-end round-trip that reconstructs Result/Evidence metadata while preserving independent-verification requirements;
4. keep protocol completion separate from IDKMesh acceptance.

The stale `interop-runtime-integration` branch should now be treated as provenance/extraction history, not as a future merge candidate.
