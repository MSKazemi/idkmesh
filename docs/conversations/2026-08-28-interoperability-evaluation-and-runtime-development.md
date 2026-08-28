# Conversation record — interoperability evaluation and runtime development

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner request

The project owner asked:

> Check the interoperability of the system, evaluate different aspects of the project, and proceed with development.

## Repository state inspected

The repository had already moved beyond documentation-only work. `main` contained:

- canonical Work Unit v0.1 and worker ResultManifest v0.1 schemas;
- experiment manifest/result schemas;
- a deterministic Phase 0 harness;
- schema fixtures and CI;
- IDKGraph/guarded self-evolution research;
- ACE community-growth automation;
- an open local worker prototype PR (#21).

The current repository audit correctly identified that PR #21 had useful Docker isolation but used a second incompatible Work Unit/result protocol.

## Interoperability research

Current official protocol material was checked for:

### A2A

- current released A2A line: 1.0;
- Agent Cards for capability discovery;
- stateful Tasks;
- Messages/Parts/Artifacts;
- protocol extension support;
- breaking v1 Part/role changes from 0.3.

Key references:

- https://a2a-protocol.org/latest/specification
- https://a2a-protocol.org/latest/whats-new-v1/
- https://a2a-protocol.org/latest/topics/extension-and-binding-governance/

### MCP

- protocol revision 2026-07-28;
- stateless core;
- formal extensions framework;
- modern routing headers;
- `io.modelcontextprotocol/tasks` extension for asynchronous long-running tool work;
- uneven Tasks runtime support across SDKs remains a practical constraint.

Key references:

- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://tasks.extensions.modelcontextprotocol.io/
- https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks

### Existing agent runtimes

OpenHands and mini-SWE-agent were reviewed as future adapters rather than core dependencies.

- OpenHands supports MCP tool servers and a remote Agent Server architecture.
- mini-SWE-agent v2 provides a deliberately small local agent surface and multiple execution environments including Docker and other isolation backends.

References:

- https://docs.openhands.dev/overview/model-context-protocol
- https://docs.openhands.dev/sdk/arch/agent-server
- https://mini-swe-agent.com/latest/
- https://mini-swe-agent.com/latest/advanced/environments/

## Interoperability conclusion

IDKMesh should not invent another generic remote-agent protocol.

The chosen model is:

```text
canonical Work Unit
  -> protocol/runtime adapter
  -> worker execution
  -> canonical ResultManifest
  -> independent verification
  -> Evidence Report
  -> human/policy integration decision
```

A2A and MCP cover execution/interoperability concerns but do not define IDKMesh acceptance semantics.

The critical invariant is:

```text
external task completed != IDKMesh accepted
```

## Development completed in this turn

A development branch `interop-runtime-integration` was created from current `main`.

### 1. Executable A2A/MCP semantic bindings

Added:

- `interop/bindings.py`
- `interop/tests/test_bindings.py`
- `interop/__init__.py`
- `docs/interoperability/A2A_MCP_MAPPING_V0_1.md`

The bindings:

- pin A2A 1.0 and MCP 2026-07-28 revisions;
- use protocol-native objective/task/artifact concepts where appropriate;
- carry the complete canonical Work Unit in a namespaced extension payload;
- include a canonical SHA-256 digest;
- reject tampered round trips;
- advertise MCP Tasks capability without making it mandatory for local v0.1;
- normalize external completion only as `pending_verification`.

### 2. Canonical local worker runtime

Instead of merging the incompatible PR #21 contract, the useful runtime ideas were ported onto canonical schemas.

Added:

- `node/src/idkmesh_node/model.py`
- `node/src/idkmesh_node/runner.py`
- `node/src/idkmesh_node/cli.py`
- `node/src/idkmesh_node/__init__.py`
- `node/src/idkmesh_node/__main__.py`
- `node/pyproject.toml`
- `node/tests/test_model.py`
- `node/tests/test_runner.py`
- `node/examples/canonical-doc-probe.work-unit.json`
- `node/README.md`

The runtime now:

- validates against canonical `schemas/work-unit-v0.1.schema.json`;
- gets Docker-specific execution configuration only from the namespaced `org.idkmesh.execution.docker` extension;
- represents source as a canonical `git_ref` input pinned to a full immutable SHA;
- requires network-off and no secrets;
- preserves Docker least-privilege controls;
- detects changed paths outside the Work Unit allowed scope or within forbidden scope;
- marks scope violations as worker failure even when the process exits zero;
- emits canonical `schemas/result-manifest-v0.1.schema.json` output;
- explicitly requests independent verification.

### 3. CI

Added `.github/workflows/interop-runtime-check.yml` to run:

- Phase 0 contract validation;
- A2A/MCP interoperability unit tests;
- local worker unit tests without Docker;
- validation of the checked-in canonical worker example.

The workflow deliberately does not execute arbitrary Work Unit Docker commands in pull-request CI.

### 4. System evaluation

Added:

- `docs/audits/2026-08-28-interoperability-and-system-evaluation.md`

The audit uses maturity levels rather than popularity/feature scores and evaluates architecture, community, contracts, interoperability, runtime, verification, security, provenance, scalability, scientific rigor, self-evolution, and product UX.

## Major remaining gap

The next central implementation is **independent verification**.

IDKMesh has a worker ResultManifest, but it still needs a canonical Evidence Report/verifier runtime before the local loop can be described as trusted or complete.

Recommended next chain:

```text
canonical Work Unit
 -> local/A2A/MCP worker adapter
 -> canonical ResultManifest
 -> independent verifier
 -> Evidence Report
 -> human decision
```

## Community impact

The changes reduce conceptual duplication and open several bounded contributor surfaces:

- protocol binding validation;
- A2A SDK adapter;
- MCP adapter;
- mini-SWE-agent/OpenHands adapters;
- sandbox backends;
- verifier plugins;
- path-policy tests;
- provenance/signing;
- developer experience and quick-start documentation.

The project remains community-first: new integrations should share the canonical Work Contract rather than creating provider-specific cores.
