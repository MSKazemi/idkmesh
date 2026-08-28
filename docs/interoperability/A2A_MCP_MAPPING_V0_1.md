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

- negotiated A2A protocol version `1.0` (Major.Minor; specification patch versions such as `1.0.0` are not request protocol versions);
- explicit transport-neutral service parameters for `A2A-Version: 1.0` and `A2A-Extensions: https://idkmesh.org/extensions/work-contract/v0.1`;
- `ROLE_USER`;
- a text part containing the Work Unit objective;
- a JSON data part containing the complete canonical Work Unit and its canonical digest;
- the IDKMesh extension URI `https://idkmesh.org/extensions/work-contract/v0.1`;
- accepted output modes appropriate for structured result data, text, and patches.

The binding module remains transport-neutral. An HTTP adapter must map the service parameters to the standard `A2A-Version` / `A2A-Extensions` headers (or the equivalent request parameters allowed by the A2A specification). The decoder fails closed if the expected version or extension activation is absent or mismatched.

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

For A2A specifically, keep **specification release** and **negotiated protocol version** distinct: protocol negotiation uses `Major.Minor`, while patch releases do not change protocol compatibility and should not be sent as request protocol versions.

## Heterogeneous adapter boundary

`interop.adapters` now defines one coordinator-facing `WorkerAdapter` protocol.
Both `LocalAdapter` and `A2AMockAdapter` cross that same `run_with_adapter()`
path; the coordinator contains no provider- or protocol-specific branch.

The A2A mock performs a real canonical JSON serialization/deserialization of
the existing `SendMessage` binding, reconstructs the exact Work Unit, follows a
submitted → working → completed lifecycle, and returns immutable candidate
artifact bytes. The coordinator normalizes either adapter into a schema-valid
ResultManifest v0.1 with exact Work Unit and artifact digests.

Verification is a separate call and component. `verify_result_bundle()` checks
the Work Unit binding, declared artifact digests, verifier-owned expected bytes,
and the no-worker-acceptance boundary without executing candidate code. Its
VerificationResult remains decision support and explicitly has no integration
authority. The bounded mock uses one process, so it truthfully reports a shared
runtime even though worker and verifier roles remain separate.

## Remaining implementation tests

1. Validate the binding module against real A2A 1.0 SDK types and the A2A TCK.
2. Validate the MCP envelope against a 2026-07-28 SDK that supports custom extensions; Tasks runtime support is still uneven across SDKs.
3. Validate a live or official-TCK external lifecycle without weakening the
   deterministic mock boundary.
4. Add capability matching from A2A Agent Cards / MCP server discovery into
   scheduler experiments.
5. Keep protocol compatibility tests in CI.
