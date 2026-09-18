# A2A semantic identity invariant

**Status:** implemented interoperability invariant  
**Protocol:** A2A 1.0  
**Binding:** `interop.bindings.to_a2a_send_message()` / `from_a2a_send_message()`

IDKMesh deliberately exposes some Work Unit semantics twice in an A2A request:

1. the human-readable objective is a native A2A text part so an external agent can act on it;
2. the complete canonical Work Unit and SHA-256 digest are carried in the IDKMesh Work Contract extension so IDKMesh-only constraints are not lost.

Request metadata and extension activation repeat parts of the same logical Work Unit identity. Those duplicated semantic surfaces are useful to transports and agents, but they create a dual-view risk if they are allowed to disagree.

A2A `messageId` is different: it is a sender-owned protocol correlation identifier, not IDKMesh Work Unit semantic identity. IDKMesh emits a deterministic value when it creates a message, but a conforming sender, relay, client, gateway, or SDK path may choose another non-empty string without changing the Work Unit. See [Transport identifiers versus Work Unit identity](README.md#transport-identifiers-versus-work-unit-identity).

## Invariant

For an IDKMesh-produced A2A `SendMessage` envelope, every IDKMesh-controlled **semantic** representation of the task must identify the same canonical Work Unit.

The decoder therefore fails closed unless all of the following hold:

- envelope protocol and negotiated `A2A-Version` are `1.0`;
- `A2A-Extensions` activates the IDKMesh Work Contract extension;
- the envelope-level and message-level extension declarations contain the same IDKMesh extension;
- the message role is `ROLE_USER`;
- `messageId` is present as a non-empty string, without requiring IDKMesh's emitted deterministic value;
- request metadata repeats the canonical Work Unit ID, digest, and extension URI exactly;
- there is exactly one native text part and it equals the canonical Work Unit objective;
- there is exactly one IDKMesh Work Contract payload part;
- the Work Contract payload schema version is `0.1`;
- the payload digest matches the complete canonical Work Unit.

A mismatch on a semantic Work Unit surface is an interoperability error, not a recoverable hint. A different valid `messageId` is not a semantic mismatch.

## Why fail closed

A2A `SendMessageRequest` intentionally contains a native `message`, optional request metadata, and extension mechanisms. That flexibility is useful, but a gateway or external agent can make decisions from the native message before IDKMesh sees the returned evidence. If the native objective says one thing while the canonical extension payload says another, the agent could execute one task while IDKMesh later verifies a different task.

The same problem exists for duplicated IDKMesh semantic metadata: accepting a canonical payload while ignoring conflicting Work Unit ID/digest or extension identity would make one envelope have different meanings to different components.

IDKMesh therefore treats the canonical payload as authoritative **and** requires every IDKMesh-emitted duplicate semantic surface to be consistent with it. Transport correlation remains separate so protocol-owned identifiers do not accidentally become application-level task identity.

## Compatibility

This hardening does not change the shape or protocol version of valid envelopes emitted by `to_a2a_send_message()`. It can reject hand-written or legacy envelopes that previously passed despite missing or conflicting IDKMesh metadata, multiple canonical payloads, altered native objective text, invalid role, or a missing/empty/non-string `messageId`. Those rejections are intentional.

A non-empty sender-selected `messageId` is accepted even when it differs from IDKMesh's deterministic emitted value. Changing only that transport identifier does not change the canonical Work Unit, and it cannot mask tampering with Work Contract metadata or payload content.

The existing pre-SDK `data` payload decoder remains available for the canonical payload itself, but it is still subject to the same semantic-identity checks.

## Authority boundary

Passing these checks proves only that the A2A request is internally consistent with the canonical Work Unit carried by IDKMesh and that required protocol structure is present. It does not prove that:

- the remote agent is trustworthy;
- the work was executed correctly;
- returned artifacts are valid;
- the worker is independent from a verifier;
- the result should be accepted or merged.

Worker completion remains separate from verification and integration authority.

## Upstream basis

Checked against the A2A 1.0 specification on 2026-09-17. The A2A specification defines `SendMessageRequest` as a request containing a message, configuration, and metadata, defines `A2A-Extensions` as the service parameter used to activate extension URIs, and treats `messageId` as a message-sender-generated identifier that can support correlation/idempotency rather than application task identity.

Upstream references:

- https://a2a-protocol.org/v1.0.0/
- https://a2a-protocol.org/dev/specification/
- https://a2a-protocol.org/dev/blog/2026/03/12/a2a-protocol-ships-v10-production-ready-standard-for-agent-to-agent-communication/

## Regression coverage

`interop/tests/test_a2a_semantic_identity.py` covers the valid round trip and fails closed on:

- native objective mismatch;
- Work Unit ID/digest/extension metadata mismatch;
- incorrect sender role;
- inconsistent extension declarations;
- multiple canonical payload parts;
- unsupported Work Contract payload schema version.

`interop/tests/test_a2a_message_identity.py` separately pins the transport/semantic boundary:

- a sender-selected non-empty `messageId` preserves the exact canonical Work Unit;
- missing, empty, or non-string `messageId` values fail closed;
- changing `messageId` cannot mask Work Unit ID/digest metadata tampering.
