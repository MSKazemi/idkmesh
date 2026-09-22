# IDKMesh interoperability layer

This directory holds the protocol-neutral boundary between the canonical IDKMesh Work Contract and the agent protocols other systems already speak. It implements no network transport. Everything here is an in-process, deterministic mapping that can be tested offline.

| Module | Responsibility |
| --- | --- |
| [`bindings.py`](bindings.py) | Maps a canonical Work Unit onto A2A `SendMessage` and MCP `tools/call` envelopes, and back, without discarding IDKMesh-only semantics. |
| [`adapters.py`](adapters.py) | The `WorkerAdapter` boundary and canonical result normalization. Local execution and an A2A-style lifecycle cross the same interface. |
| [`identity.py`](identity.py) | Optional, namespaced identity evidence on a ResultManifest. Identity never confers verification or integration authority. |
| [`sdk_conformance.py`](sdk_conformance.py) | Round-trips those envelopes through the real pinned A2A and MCP Python types, so the bindings are checked against the SDKs rather than only against our own reading of the specs. |
| [`PROTOCOL_SCOPE.md`](PROTOCOL_SCOPE.md) | Protocol-layer decision record, including the required disambiguation between the legacy IBM/BeeAI Agent Communication Protocol and the active Agent Client Protocol that share the acronym `ACP`. |

Background: [`docs/interoperability/A2A_MCP_MAPPING_V0_1.md`](../docs/interoperability/A2A_MCP_MAPPING_V0_1.md) and [`docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md`](../docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md).

Before proposing another protocol adapter, read [`PROTOCOL_SCOPE.md`](PROTOCOL_SCOPE.md). In particular, new work should not use unqualified `ACP`: the archived IBM/BeeAI Agent Communication Protocol is a legacy compatibility concern now folded into A2A, while Agent Client Protocol is an active editor-to-coding-agent protocol and belongs at a different layer.

## Default tests versus SDK conformance

Most tests under `interop/tests/` run in the default development environment. The two tests in `test_sdk_conformance.py` additionally exercise the optional official A2A and MCP SDKs.

The availability gates are **independent**: the A2A conformance test runs whenever `a2a-sdk` is installed, and the MCP conformance test runs whenever `mcp` is installed. Installing or working on one protocol no longer requires the unrelated SDK merely to preserve the conformance evidence that is available. If neither SDK is installed, both protocol-specific tests skip independently.

A skipped test is not conformance evidence. Use `pytest -rs` when you specifically need to confirm which SDK-backed checks executed.

## What the conformance tests need

Neither test needs generated fixtures, credentials, environment variables, a running service, or network access at test time. The only network access is the one-off dependency installation.

Current pins are defined in [`requirements-interoperability.txt`](../requirements-interoperability.txt):

- `a2a-sdk==1.1.5`
- `mcp==2.2.0`

That requirements file is canonical. If this page ever disagrees with it, the requirements file wins and this page should be corrected.

Both tests share the tracked fixture [`examples/work-units/phase0-smoke.work-unit.json`](../examples/work-units/phase0-smoke.work-unit.json).

## Running the conformance tests

From the repository root, first observe the default environment if useful:

```bash
python -m pytest -q -rs interop/tests/test_sdk_conformance.py
```

Then install the pinned interoperability dependencies and rerun:

```bash
python -m pip install -r requirements-interoperability.txt
python -m pytest -q -rs interop/tests/test_sdk_conformance.py
```

A contributor working on only one protocol may also install that pinned SDK alongside the Phase 0 requirements and run the same test module. The installed protocol's conformance test executes while the unrelated protocol's test reports an explicit skip reason.

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
- The MCP case validates against the pinned SDK's `CallToolRequest`, requires protocol version `2026-07-28` and JSON-RPC `2.0`, and fails closed if the binding advertises the `io.modelcontextprotocol/tasks` extension where the supported revision does not justify that capability claim.

The tests also require the SDK protocol-version constants to remain consistent with the IDKMesh binding. An SDK bump that changes those semantics should fail loudly and be reviewed rather than silently drifting.

## Canonical JSON boundary

The Work Contract binding uses **strict JSON** before computing a canonical digest or producing either an A2A or MCP envelope. Python objects containing `NaN`, positive infinity, or negative infinity are rejected with `BindingError`; they are never coerced to `null`, strings, zero, or protocol-specific representations.

This is a portability invariant rather than a new wire version. JSON does not define non-finite numeric tokens, even though Python's default encoder can emit them. Rejecting those values at the protocol-neutral boundary keeps the same Work Unit digest meaningful to strict JSON implementations and non-Python agents. Finite JSON numbers and existing supported Work Unit versions are unchanged.

## Transport identifiers versus Work Unit identity

Protocol-level correlation identifiers are not IDKMesh semantic identity. The A2A `messageId` belongs to the message sender, while MCP's JSON-RPC `id` belongs to the request/correlation layer. IDKMesh may generate deterministic values for both when it creates an envelope, but decoders do not require those generated values to survive a conforming client, relay, gateway, or SDK round trip.

For A2A, a decoded message must still carry a non-empty string `messageId`, but the ID may differ from the one IDKMesh originally emitted. The canonical Work Unit identity is instead enforced by the `idkmeshWorkUnitId` and `idkmeshWorkUnitDigest` request metadata plus the canonical payload digest. For MCP, the equivalent semantic identity lives in the namespaced `org.idkmesh/work-contract` metadata and canonical payload digest.

MCP caller ownership does **not** mean that any JSON value is a valid request identifier. For the supported MCP `2026-07-28` request shape, the decoder requires `id` to be present, non-null, and either a JSON string or integer. JSON booleans are rejected even though Python represents `bool` as an `int` subclass; floats, arrays, objects, missing IDs, and `null` are rejected as well. The in-process decoder validates this request shape only: it does not maintain transport state or prove uniqueness among outstanding request IDs.

This separation prevents transport ownership from becoming an accidental compatibility constraint while preserving fail-closed semantic and protocol-shape checks. Changing a transport identifier cannot make payload or Work Contract metadata tampering valid, and a caller-owned identifier still has to satisfy the supported protocol shape.

## Result-bundle artifact identity

Artifact IDs are a semantic reference namespace across worker output and independent verification. `run_with_adapter()` already refuses to create a ResultManifest with duplicate produced-artifact IDs. `verify_result_bundle()` independently enforces the same uniqueness rule on the manifest it receives instead of assuming that every bundle came directly from the local normalizer.

This matters for stored, externally supplied, or protocol-carried ResultBundles: two artifacts with the same logical ID but different locators must not be silently collapsed by a dictionary/set conversion. The verifier fails closed before resolving digests or evidence when duplicate produced-artifact IDs are present. This is a semantic integrity check; it does not change the ResultManifest JSON Schema version, and passing it does not grant acceptance or integration authority.

## If this path is broken

If installation fails, a conformance test errors instead of passing, or an SDK release changes a protocol contract, open an issue with your OS, Python version, exact command, and output. Pinned-SDK drift is useful project data.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the default test commands and general contribution workflow.
