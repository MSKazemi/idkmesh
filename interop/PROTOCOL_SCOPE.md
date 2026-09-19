# Interoperability protocol scope

Status: architecture boundary, checked against upstream primary sources on 2026-09-17.

IDKMesh uses protocol adapters only when they preserve the canonical WorkUnit / ResultManifest / VerificationResult trust boundaries. A protocol name is not, by itself, a reason to add another adapter. This note exists because **ACP is currently ambiguous** and the two protocols that use that acronym belong to different layers.

## Current IDKMesh protocol roles

| Protocol | Layer | IDKMesh role |
| --- | --- | --- |
| A2A (Agent2Agent) | agent-to-agent delegation and task lifecycle | Current agent-to-agent binding. New peer-agent interoperability work should target A2A unless a concrete compatibility requirement says otherwise. |
| MCP (Model Context Protocol) | agent/model-to-tool, resource, and server capabilities | Current tool-call binding. MCP is not treated as a replacement for the canonical Work Contract or for independent verification. |
| ACP (IBM/BeeAI Agent Communication Protocol) | historical agent communication protocol | **Legacy compatibility only.** The upstream project states that ACP is now part of A2A under Linux Foundation governance, and the original repository is archived. IDKMesh should not create a new parallel canonical ACP binding for greenfield peer-agent work. |
| ACP (Agent Client Protocol) | editor/client-to-coding-agent integration | **Different protocol, different layer.** This remains an active protocol for connecting editors and coding agents. It is a plausible future IDKMesh client surface, but not an agent-to-agent replacement for A2A. |

## Why the ACP distinction matters

Two unrelated interoperability efforts use the same acronym:

1. **Agent Communication Protocol** from IBM/BeeAI. The original `i-am-bee/acp` project is archived and its own repository says ACP is now part of A2A. For new IDKMesh agent-to-agent work, adding a second first-class binding for that historical protocol would duplicate the layer already represented by A2A. A compatibility adapter may still be justified for a real legacy deployment, but it should remain an ingress/egress compatibility boundary rather than a new canonical task model.
2. **Agent Client Protocol** from the `agentclientprotocol` project. Its official project describes a protocol for connecting code editors to coding agents, and its ecosystem includes editors plus adapters for coding agents such as Codex and Claude. That is useful to IDKMesh only when the product goal is an interactive editor/client experience around IDKMesh work, review, permission, or progress events.

The two meanings must not be conflated in issues, architecture documents, or implementation names.

## Decision rules

1. **Do not write unqualified `ACP` in new IDKMesh architecture or implementation work.** Use `Agent Communication Protocol (legacy ACP)` or `Agent Client Protocol (ACP)` on first mention.
2. **Use A2A for new peer-agent task delegation.** A legacy Agent Communication Protocol adapter requires an identified interoperability consumer or fixture; speculative duplication is not enough.
3. **Use Agent Client Protocol only for editor/client integration.** It may expose an IDKMesh-backed coding agent to Zed, JetBrains, VS Code, or another ACP client, but it must not redefine WorkUnit semantics.
4. **Protocol sessions do not grant authority.** An A2A task completion, MCP tool result, or Agent Client Protocol session event does not imply IDKMesh acceptance, verifier independence, or merge/integration authority.
5. **Preserve semantic identity across bridges.** If a future adapter mirrors WorkUnit identity, objective, artifacts, digests, or policy metadata into protocol-native fields, disagreement must fail closed rather than choosing one representation silently.
6. **Keep protocol-specific lifecycle state outside canonical schemas unless the evidence model actually needs it.** Transport/session identifiers may be provenance, but they are not logical execution identity by default.

## When a future Agent Client Protocol adapter is justified

A bounded implementation becomes useful when IDKMesh has a concrete interactive coding-agent/client use case, for example:

- exposing an IDKMesh-backed worker to an ACP-compatible editor;
- mapping editor permission requests to an explicit policy boundary without auto-granting authority;
- streaming progress while the canonical WorkUnit remains the task source of truth;
- returning ResultManifest-backed artifacts for human review;
- recording protocol/session identifiers as provenance without treating them as verifier identity.

The first implementation should be an optional adapter behind the existing protocol-neutral boundary, with official-SDK conformance tests if a stable SDK is available. It should not add a second orchestration authority or bypass the existing acceptance path.

## What not to build

- Do not add a greenfield IBM/BeeAI ACP task binding merely because older ecosystem diagrams list ACP beside A2A.
- Do not treat Agent Client Protocol as a peer-agent delegation protocol.
- Do not map editor approval directly to verification or merge authority.
- Do not put editor/session-specific fields into the canonical WorkUnit solely to satisfy one client protocol.
- Do not claim protocol support from a hand-written envelope alone; use upstream types/conformance evidence when support is implemented.

## Upstream evidence checked

Primary sources checked on 2026-09-17:

- IBM/BeeAI Agent Communication Protocol repository: https://github.com/i-am-bee/acp — archived, with an upstream notice that ACP is now part of A2A.
- Agent Client Protocol project: https://github.com/agentclientprotocol/agent-client-protocol — active protocol for connecting editors and agents.
- Zed Agent Client Protocol overview: https://zed.dev/acp — describes the editor-to-agent interoperability role.

This note records protocol ownership and scope, not production-support claims. Implemented support remains whatever is exercised by the code and tests in this directory.
