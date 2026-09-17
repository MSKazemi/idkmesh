# IDKMesh interoperability layer

This directory holds the protocol-neutral boundary between the canonical IDKMesh Work Contract and the agent protocols other systems already speak. It implements no network transport. Everything here is an in-process, deterministic mapping that can be tested offline.

| Module | Responsibility |
| --- | --- |
| [`bindings.py`](bindings.py) | Maps a canonical Work Unit onto A2A `SendMessage` and MCP `tools/call` envelopes, and back, without discarding IDKMesh-only semantics. |
| [`adapters.py`](adapters.py) | The `WorkerAdapter` boundary and canonical result normalization. Local execution and an A2A-style lifecycle cross the same interface. |
| [`identity.py`](identity.py) | Optional, namespaced identity evidence on a ResultManifest. Identity never confers verification or integration authority. |
| [`sdk_conformance.py`](sdk_conformance.py) | Round-trips those envelopes through the real pinned A2A and MCP Python types, so the bindings are checked against the SDKs rather than only against our own reading of the specs. |

Background: [`docs/interoperability/A2A_MCP_MAPPING_V0_1.md`](../docs/interoperability/A2A_MCP_MAPPING_V0_1.md) and [`docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md`](../docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md).

## Two test tiers

Most tests under `interop/tests/` run in the default development environment. The two tests in `test_sdk_conformance.py` additionally need the optional official protocol SDKs. Without the relevant SDK, that individual conformance test skips; the A2A and MCP gates are independent, so a partial install still runs the test it can run.

A skipped test is not conformance evidence. Use `pytest -rs` when you specifically need to confirm whether these SDK-backed checks executed.

## What each skippable test needs

Neither conformance test needs generated fixtures, credentials, environment variables, a running service, or network access at test time. The only network access is the one-off dependency installation.

| Test | Runs when | Current pin |
| --- | --- | --- |
| `OfficialA2aSdkConformanceTests::test_a2a_v1_protobuf_preserves_exact_work_unit` | `import a2a` succeeds | `a2a-sdk==1.1.2` |
| `OfficialMcpSdkConformanceTests::test_mcp_current_types_preserve_exact_work_unit_and_fail_closed_on_tasks` | `import mcp` succeeds | `mcp==2.2.0` |

The canonical dependency source is [`requirements-interoperability.txt`](../requirements-interoperability.txt). If this table ever disagrees with that file, the requirements file wins and this page should be corrected.

Both tests share the tracked fixture [`examples/work-units/phase0-smoke.work-unit.json`](../examples/work-units/phase0-smoke.work-unit.json).

## Running the conformance tests

From the repository root:

```bash
python -m pip install -r requirements-interoperability.txt
python -m pytest -q -rs interop/tests/test_sdk_conformance.py
```

To run the whole interoperability test directory with skip reasons visible:

```bash
python -m pytest -q -rs interop/tests/
```

The installation step may reach the public package index. Test execution itself is local and requires no model account or API credential. This is compatible with the zero-project-spend rule in [`PROJECT_RULES.md`](../PROJECT_RULES.md).

## Why the SDKs stay optional

The protocol SDKs bring dependencies that contributors working on unrelated parts of IDKMesh do not need. Keeping them optional preserves a small default setup while the dedicated interoperability workflow installs the pinned SDKs and exercises the conformance boundary.

[`.github/workflows/interop-bindings-check.yml`](../.github/workflows/interop-bindings-check.yml) installs `requirements-interoperability.txt` before running the interoperability tests on relevant changes.

## What the conformance tests assert

These are integrity checks, not claims that IDKMesh has production integrations with every external agent framework.

- The A2A case parses the IDKMesh envelope into `lf.a2a.v1.SendMessageRequest`, serializes and reads it back, and requires the canonical Work Unit digest and protocol version `1.0` to survive unchanged.
- The MCP case validates against the pinned SDK's `CallToolRequest`, requires protocol version `2026-07-28`, and fails closed if the binding advertises the `io.modelcontextprotocol/tasks` extension where the supported revision does not justify that capability claim.

The tests also require the SDK protocol-version constants to remain consistent with the IDKMesh binding. An SDK bump that changes those semantics should fail loudly and be reviewed rather than silently drifting.

## If this path is broken

If installation fails, a conformance test errors instead of passing, or an SDK release changes a protocol contract, open an issue with your OS, Python version, exact command, and output. Pinned-SDK drift is useful project data.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the default test commands and general contribution workflow.
