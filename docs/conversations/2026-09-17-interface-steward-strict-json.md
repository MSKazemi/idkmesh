# Interface Steward — strict JSON numeric boundary

Date: 2026-09-17

## Project-owner requirement

The IDKMesh Interface Steward is tasked with improving APIs, interfaces, protocols, and communications between IDKMesh and external agents/tools/services/compute resources. Each run should inspect current repository state, avoid duplicate work, make one bounded high-value improvement, add tests and documentation when contracts change, validate the change, and use a focused pull request rather than pushing substantive work directly to `main`.

## Finding

Issue #504 identified a protocol-neutral portability gap in `interop/bindings.py`: Python's default `json.dumps()` accepts and emits `NaN`, `Infinity`, and `-Infinity`, although those are not JSON numbers. A Work Unit containing such a value could therefore receive an IDKMesh digest before a strict transport or non-Python implementation rejected it.

The issue was still open with no implementation PR when this run began. Open PR #498 touches `interop/README.md` only for ACP terminology/scope and does not implement strict numeric serialization.

## Implementation

The focused branch `interop/strict-json-numbers-504` changes the canonical serializer to use `allow_nan=False` and converts the resulting refusal into the stable protocol-neutral `BindingError` message:

> canonical interoperability payload contains a non-finite number; strict JSON requires finite numbers

The change deliberately does not coerce non-finite values to `null`, strings, or zero because that would change Work Unit semantics and canonical digests.

A dedicated regression module exercises `NaN`, positive infinity, and negative infinity through canonical digesting, A2A envelope creation, and MCP envelope creation. A finite-float round trip remains covered as a compatibility guard.

`interop/README.md` now documents strict JSON as an interoperability invariant. The existing Work Unit versions and finite-number wire semantics are unchanged, so no protocol or schema version bump is introduced.

## Validation boundary

The exact pull-request head and repository CI are the integration evidence for this connector-driven run. Required protected-main gates are `gate (3.11)` and `gate (3.13)`, and the interoperability workflow should exercise the optional pinned A2A/MCP SDK conformance path for the changed binding surface.

Owner-controlled automation is not independent human review.

## Community impact

External integrations get one early, protocol-neutral failure for a non-portable numeric payload instead of transport-dependent behavior. That reduces cross-language surprises without adding dependencies or new contributor setup.
