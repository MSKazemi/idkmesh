# A2A semantic identity invariant

**Status:** implemented interoperability invariant  
**Protocol:** A2A 1.0  
**Binding:** `interop.bindings.to_a2a_send_message()` / `from_a2a_send_message()`

IDKMesh deliberately exposes some Work Unit semantics twice in an A2A request:

1. the human-readable objective is a native A2A text part so an external agent can act on it;
2. the complete canonical Work Unit and SHA-256 digest are carried in the IDKMesh Work Contract extension so IDKMesh-only constraints are not lost.

Request metadata, extension activation, and the deterministic message ID also repeat parts of the same logical identity. These surfaces are useful to transports and agents, but they create a dual-view risk if they are allowed to disagree.

## Invariant

For an IDKMesh-produced A2A `SendMessage` envelope, every IDKMesh-controlled representation of the task must identify the same canonical Work Unit.

The decoder therefore fails closed unless all of the following agree:

- envelope protocol and negotiated `A2A-Version` are `1.0`;
- `A2A-Extensions` activates the IDKMesh Work Contract extension;
- the envelope-level and message-level extension declarations contain the same IDKMesh extension;
- the message role is `ROLE_USER`;
- the message ID is the deterministic ID derived from the canonical Work Unit digest;
- request metadata repeats the canonical Work Unit ID, digest, and extension URI exactly;
- there is exactly one native text part and it equals the canonical Work Unit objective;
- there is exactly one IDKMesh Work Contract payload part;
- the Work Contract payload schema version is `0.1`;
- the payload digest matches the complete canonical Work Unit.

A mismatch is an interoperability error, not a recoverable hint.

## Why fail closed

A2A `SendMessageRequest` intentionally contains a native `message`, optional request metadata, and extension mechanisms. That flexibility is useful, but a gateway or external agent can make decisions from the native message before IDKMesh sees the returned evidence. If the native objective says one thing while the canonical extension payload says another, the agent could execute one task while IDKMesh later verifies a different task.

The same problem exists for duplicated identity metadata: accepting a canonical payload while ignoring conflicting routing or diagnostic identity would make one envelope have different meanings to different components.

IDKMesh therefore treats the canonical payload as authoritative **and** requires every IDKMesh-emitted duplicate semantic surface to be consistent with it.

## Compatibility

This hardening does not change the shape or protocol version of valid envelopes emitted by `to_a2a_send_message()`. It can reject hand-written or legacy envelopes that previously passed despite missing or conflicting IDKMesh metadata, multiple canonical payloads, altered native objective text, or a changed message identity. That rejection is intentional.

The existing pre-SDK `data` payload decoder remains available for the canonical payload itself, but it is still subject to the same semantic-identity checks.

## Authority boundary

Passing these checks proves only that the A2A request is internally consistent with the canonical Work Unit carried by IDKMesh. It does not prove that:

- the remote agent is trustworthy;
- the work was executed correctly;
- returned artifacts are valid;
- the worker is independent from a verifier;
- the result should be accepted or merged.

Worker completion remains separate from verification and integration authority.

## Upstream basis

Checked against the current A2A specification on 2026-09-17. The A2A specification defines `SendMessageRequest` as a request containing a message, configuration, and metadata, and defines `A2A-Extensions` as the service parameter used to activate extension URIs. The A2A 1.0 release is the stable protocol baseline used by this binding.

Upstream references:

- https://a2a-protocol.org/dev/specification/
- https://a2a-protocol.org/dev/blog/2026/03/12/a2a-protocol-ships-v10-production-ready-standard-for-agent-to-agent-communication/

## Regression coverage

`interop/tests/test_a2a_semantic_identity.py` covers the valid round trip and fails closed on:

- native objective mismatch;
- Work Unit ID/digest/extension metadata mismatch;
- message ID mismatch;
- incorrect sender role;
- inconsistent extension declarations;
- multiple canonical payload parts;
- unsupported Work Contract payload schema version.
