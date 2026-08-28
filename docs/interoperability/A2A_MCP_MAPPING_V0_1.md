# IDKMesh Work Contract interoperability mapping v0.1

**Status:** Experimental  
**Related:** IDKIP-0001, issue #17

## Conclusion

IDKMesh should **bind to** A2A and MCP, not replace them.

- **A2A 1.0** is a strong fit for remote agent discovery, task lifecycle, messages, artifacts, asynchronous progress, and protocol extensions.
- **MCP 2026-07-28** is a strong fit for tool/context integration. Its `io.modelcontextprotocol/tasks` extension provides a durable asynchronous task handle for long-running tool calls.
- Neither protocol, by itself, means that a returned result satisfies IDKMesh verification, risk, provenance, or integration policy.

Therefore the binding rule is:

> Use protocol-native fields where semantics match. Carry the complete canonical IDKMesh Work Unit in a namespaced extension payload for semantics the external protocol does not define. Verify a canonical SHA-256 digest on round-trip. Never infer IDKMesh acceptance from external task completion.

## Mapping matrix

| IDKMesh concept | A2A 1.0 | MCP 2026-07-28 | Binding decision |
| --- | --- | --- | --- |
| Work Unit identity | message/task metadata and task ID relationship | request ID / tool arguments | native hint + canonical extension payload |
| objective | user `Message` text part | `tools/call` arguments | protocol native |
| worker capability | Agent Card skills/capabilities | `server/discover`, tools/list, extension capabilities | protocol native discovery; IDKMesh scheduler interprets capabilities |
| execution lifecycle | `Task` states | synchronous tool result or Tasks extension | protocol native |
| candidate artifacts | A2A `Artifact` + `Part` | tool result/resources/task final result | protocol native transport; normalize to ResultManifest artifacts |
| inputs | message parts / URLs / data | tool arguments/resources | partial; canonical Work Unit remains authoritative |
| outputs expected | accepted output modes + extension metadata | tool input contract / tool result expectations | partial |
| dependencies | context/reference task IDs plus extension data | explicit handles/arguments | partial; Work Unit DAG remains IDKMesh semantic |
| constraints / allowed paths | extension data | tool arguments/custom extension | IDKMesh semantic |
| uncertainty | extension data | tool arguments/custom extension | IDKMesh semantic |
| permissions / risk | auth + extension data | authorization + extension data | partial; IDKMesh policy remains authoritative |
| validators | extension data | custom extension/tool arguments | IDKMesh semantic |
| evidence requirements | artifact conventions + extension data | tool/task result + custom extension | IDKMesh semantic |
| resource budget | extension data | tool arguments/custom extension | IDKMesh semantic |
| provenance requirements | artifact/task metadata + extension data | result metadata/custom extension | partial; IDKMesh canonical provenance remains authoritative |
| failure semantics | task states + client policy | task states + client policy | partial |
| independent verification | separate verifier task/agent | separate verifier tool/task | **IDKMesh semantic; never implied by worker completion** |
| integration/merge decision | not defined | not defined | **IDKMesh-only** |

## A2A binding

`interop.bindings.to_a2a_send_message()` emits an A2A 1.0-oriented `SendMessage` payload with:

- `ROLE_USER`;
- a text part containing the Work Unit objective;
- a JSON data part containing the complete canonical Work Unit and its canonical digest;
- the IDKMesh extension URI `https://idkmesh.org/extensions/work-contract/v0.1`;
- accepted output modes appropriate for structured result data, text, and patches.

The full Work Unit is preserved because A2A Task completion describes **agent execution**, not IDKMesh acceptance.

A future network adapter should fetch and inspect Agent Cards before dispatch, negotiate the IDKMesh extension when supported, and otherwise use a configured compatibility adapter.

## MCP binding

`interop.bindings.to_mcp_tool_call()` emits an MCP `tools/call` request for protocol revision `2026-07-28`.

It advertises:

- `io.modelcontextprotocol/tasks` for asynchronous execution;
- `org.idkmesh/work-contract` as the IDKMesh binding extension;
- the complete Work Unit plus canonical digest in tool arguments;
- modern routing headers: `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name`.

A server may return a normal tool result or a Tasks handle. Either path is normalized as worker execution; independent IDKMesh verification still follows.

## Round-trip invariant

For both bindings:

```text
canonical Work Unit
  -> protocol envelope
  -> protocol transport/execution
  -> binding extraction
  -> canonical Work Unit
```

The reconstructed Work Unit must be identical and its digest must match. If fields are removed or modified, the binding rejects the envelope rather than silently weakening constraints.

## Completion invariant

```text
A2A TASK_STATE_COMPLETED
or
MCP task status = completed

!=

IDKMesh accepted
```

The normalized IDKMesh state is:

```text
execution_status = succeeded
acceptance_status = pending_verification
```

Only a separate verifier/evidence policy may advance the candidate toward integration.

## Versioning risk

Both ecosystems are evolving. Bindings therefore pin explicit protocol revisions and remain outside the canonical Work Unit schema. This lets transport/protocol adapters change without renaming IDKMesh's core work semantics.

## Next implementation tests

1. Validate the binding module against real A2A 1.0 SDK types.
2. Validate the MCP envelope against a 2026-07-28 SDK that supports custom extensions; Tasks runtime support is still uneven across SDKs.
3. Build a local adapter and one A2A or MCP mock adapter behind the same coordinator interface.
4. Convert external artifacts into canonical worker ResultManifest v0.1.
5. Add capability matching from A2A Agent Cards / MCP server discovery into scheduler experiments.
6. Keep protocol compatibility tests in CI.
