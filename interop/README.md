# IDKMesh interoperability layer

This directory holds the protocol-neutral boundary between the canonical
IDKMesh Work Contract and the agent protocols other systems already speak. It
implements no network transport. Everything here is an in-process, deterministic
mapping that can be tested offline.

| Module | Responsibility |
| --- | --- |
| [`bindings.py`](bindings.py) | Maps a canonical Work Unit onto A2A `SendMessage` and MCP `tools/call` envelopes, and back, without discarding IDKMesh-only semantics. |
| [`adapters.py`](adapters.py) | The `WorkerAdapter` boundary and canonical result normalization. Local execution and an A2A-style lifecycle cross the same interface. |
| [`identity.py`](identity.py) | Optional, namespaced identity evidence on a ResultManifest. Identity never confers verification or integration authority. |
| [`sdk_conformance.py`](sdk_conformance.py) | Round-trips those envelopes through the *real* pinned A2A and MCP Python types, so the bindings are checked against the SDKs rather than against our own reading of the specs. |

Background: [`docs/interoperability/A2A_MCP_MAPPING_V0_1.md`](../docs/interoperability/A2A_MCP_MAPPING_V0_1.md)
and [`docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md`](../docs/interoperability/AGENT_INTEROPERABILITY_ARCHITECTURE_2026-08-28.md).

## Two tiers of test

`interop/tests/` collects **25 tests**, split by what they need:

- **23 tests** — `test_bindings.py`, `test_adapters.py`, `test_identity.py` — need
  only the default development environment. They never skip.
- **2 tests** — `test_sdk_conformance.py` — need the optional official protocol
  SDKs. Without them they skip. Measured on the commit that added this page,
  they were the only two skips anywhere in the repository's test suite.

That second tier is the reason this page exists. A skipped test reports `OK`,
so nothing about a green default run tells you the conformance checks executed.

## What each skippable test needs

Both tests below are gated on a single missing import each. Neither needs a
fixture you have to generate, an environment variable, a credential, a running
service, or network access *at test time* — only the one-off install below.

| Test | Runs when | Needs | Avoidable |
| --- | --- | --- | --- |
| `OfficialA2aSdkConformanceTests::test_a2a_v1_protobuf_preserves_exact_work_unit` | `import a2a` succeeds | `a2a-sdk==1.1.2` (pulls in `protobuf`) | Yes — install it |
| `OfficialMcpSdkConformanceTests::test_mcp_current_types_preserve_exact_work_unit_and_fail_closed_on_tasks` | `import mcp` succeeds | `mcp==2.1.1` (pulls in `pydantic`) | Yes — install it |

The two gates are independent. An environment that has `mcp` but not `a2a` runs
the MCP test and skips only the A2A one. Both tests share the tracked fixture
[`examples/work-units/phase0-smoke.work-unit.json`](../examples/work-units/phase0-smoke.work-unit.json),
which is committed — there is nothing to build.

**No test in this directory is permanently unrunnable.** Every skip here is a
missing optional install, and each skip reason names the command that fixes it.

## Running the conformance tests

The pins live in [`requirements-interoperability.txt`](../requirements-interoperability.txt),
which is the same file CI installs. From the repository root:

```bash
python -m pip install -r requirements-interoperability.txt
python -m pytest -q -rs interop/tests/test_sdk_conformance.py
```

Use `-rs`. Without it pytest prints a bare `s` and no reason, which is exactly
how these tests stayed quietly unrun.

To confirm the skips are gone rather than merely absent from the summary:

```bash
python -m pytest -q -rs interop/tests/
```

23 passed / 2 skipped means the SDKs are still missing. 25 passed means both
conformance tests really executed.

The `python -m pip install` step is the only one that reaches the network. It
is an ordinary install from the public index and costs nothing, consistent with
the zero-project-spend rule in [`PROJECT_RULES.md`](../PROJECT_RULES.md).

## Why the SDKs stay optional

`a2a-sdk` and `mcp` pull in `protobuf` and `pydantic`. Making them mandatory
would put two protocol stacks and a compiled dependency in front of every
contributor who only wants to run the unit suite, for two tests that exercise
nothing but the SDK boundary. Keeping them optional keeps the default path
small and offline; documenting them here keeps the tier honest instead of
invisible.

Continuous integration does not rely on that choice.
[`.github/workflows/interop-bindings-check.yml`](../.github/workflows/interop-bindings-check.yml)
installs `requirements-interoperability.txt` and then runs
`python -m unittest discover -s interop/tests`, so both conformance tests
execute on every pull request that touches this directory, the Work Unit
examples, the bound schemas, or that workflow.

## What the conformance tests actually assert

They are integrity checks, not smoke tests. Each one serializes an envelope
through the official types and requires the canonical Work Unit to survive
byte-for-byte, compared by `canonical_digest`:

- The A2A case parses into `lf.a2a.v1.SendMessageRequest`, serializes to
  deterministic protobuf, reads it back, and requires an identical Work Unit
  digest and protocol version `1.0`.
- The MCP case validates against `CallToolRequest`, requires protocol version
  `2026-07-28`, and fails closed if the binding ever advertises the
  `io.modelcontextprotocol/tasks` extension — the current SDK scopes Tasks
  metadata to revision `2025-11-25`, so advertising it would be a false
  capability claim.

Both also assert the SDK's own protocol-version constant still matches the
constant in `bindings.py`. If an SDK bump moves either, these tests fail rather
than letting the binding drift silently — which is the point of pinning them.

## If this path is broken

If the install fails, a conformance test errors instead of passing, or an SDK
release moves a protocol version, that is a finding worth reporting. Open an
issue with your OS, your Python version, the exact command, and the output.
Pinned-SDK drift is useful project data, not noise.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the default test commands and
the general contribution workflow.
