"""Protocol-neutral IDKMesh Work Contract bindings for A2A and MCP.

This module deliberately does not implement network transports. It defines a small,
executable semantic boundary that can be tested without depending on a particular
A2A/MCP SDK. The full canonical Work Unit is carried in a namespaced payload so
IDKMesh-only semantics (verification, risk, provenance, budgets, etc.) are never
silently discarded.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

# A2A protocol negotiation uses Major.Minor. Specification patch releases (for
# example 1.0.0) do not belong in requests, responses, or Agent Cards.
A2A_PROTOCOL_VERSION = "1.0"
MCP_PROTOCOL_VERSION = "2026-07-28"
A2A_WORK_CONTRACT_EXTENSION = "https://idkmesh.org/extensions/work-contract/v0.1"
MCP_WORK_CONTRACT_EXTENSION = "org.idkmesh/work-contract"
# Retained as the official extension identifier for explicit compatibility
# reporting. It is not advertised by the 2026-07-28 binding because the current
# SDK limits Tasks request metadata/capabilities to protocol revision 2025-11-25.
MCP_TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
MCP_EXECUTE_TOOL = "idkmesh.execute_work_unit"


class BindingError(ValueError):
    """Raised when an interoperability envelope is malformed or loses integrity."""


def canonical_json(value: Any) -> str:
    """Serialize canonical interoperability data as strict, portable JSON.

    Python's JSON encoder accepts NaN and infinities by default even though JSON
    does not define those numeric tokens. Reject them at the protocol-neutral
    boundary so every digest and transport mapping has the same cross-language
    meaning.
    """

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        raise BindingError(
            "canonical interoperability payload contains a non-finite number; "
            "strict JSON requires finite numbers"
        ) from exc


# Work Unit v0.2 is additive over v0.1 -- it introduced `requirements`, `security`
# and `verification_policy` and removed nothing. These bindings read only `id`,
# `objective` and `schema_version`, all of which are unchanged, so both versions
# map losslessly onto A2A and MCP work contracts.
SUPPORTED_WORK_UNIT_VERSIONS = frozenset({"0.1", "0.2"})


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_work_unit(work_unit: dict[str, Any]) -> None:
    if not isinstance(work_unit, dict):
        raise BindingError("Work Unit must be an object")
    if work_unit.get("schema_version") not in SUPPORTED_WORK_UNIT_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_WORK_UNIT_VERSIONS))
        raise BindingError(
            "unsupported canonical Work Unit schema_version "
            f"{work_unit.get('schema_version')!r}; supported: {supported}"
        )
    if not isinstance(work_unit.get("id"), str) or not work_unit["id"]:
        raise BindingError("Work Unit id is required")
    if not isinstance(work_unit.get("objective"), str) or not work_unit["objective"]:
        raise BindingError("Work Unit objective is required")


def _contract_payload(work_unit: dict[str, Any]) -> dict[str, Any]:
    _require_work_unit(work_unit)
    return {
        "schemaVersion": "0.1",
        "workUnitDigest": canonical_digest(work_unit),
        "workUnit": work_unit,
    }


def _a2a_message_id(digest: str) -> str:
    return "idkmesh-" + digest.split(":", 1)[1][:24]


def _mcp_request_id(digest: str) -> str:
    return "idkmesh-" + digest.split(":", 1)[1][:24]


def _a2a_service_parameters() -> dict[str, str]:
    """Return transport-neutral A2A service parameters for this request.

    HTTP adapters map these keys to the `A2A-Version` and `A2A-Extensions`
    headers (or equivalent request parameters). Keeping them explicit here makes
    protocol negotiation and extension activation testable without implementing
    a network transport in this module.
    """

    return {
        "A2A-Version": A2A_PROTOCOL_VERSION,
        "A2A-Extensions": A2A_WORK_CONTRACT_EXTENSION,
    }


def _require_a2a_service_parameters(envelope: dict[str, Any]) -> None:
    service_parameters = envelope.get("serviceParameters")
    if not isinstance(service_parameters, dict):
        raise BindingError("A2A binding envelope is missing service parameters")
    if service_parameters.get("A2A-Version") != A2A_PROTOCOL_VERSION:
        raise BindingError(
            "unsupported A2A-Version; expected " + A2A_PROTOCOL_VERSION
        )

    extension_value = service_parameters.get("A2A-Extensions")
    if not isinstance(extension_value, str):
        raise BindingError("A2A binding envelope is missing A2A-Extensions")
    activated_extensions = {
        value.strip() for value in extension_value.split(",") if value.strip()
    }
    if A2A_WORK_CONTRACT_EXTENSION not in activated_extensions:
        raise BindingError(
            "A2A request did not activate the IDKMesh Work Contract extension"
        )


def _require_a2a_request_identity(
    envelope: dict[str, Any],
    request: dict[str, Any],
    message: dict[str, Any],
    parts: list[Any],
    work_unit: dict[str, Any],
    digest: str,
) -> None:
    """Require every IDKMesh-emitted A2A view to name the same Work Unit.

    A2A intentionally permits native message content plus request metadata and
    extension payloads. IDKMesh emits the objective natively for agent usability
    while carrying the canonical Work Unit in its extension. Those duplicated
    views must not be allowed to disagree: a remote agent may act on the native
    text while IDKMesh later verifies the canonical payload.
    """

    envelope_extensions = envelope.get("extensions")
    if (
        not isinstance(envelope_extensions, list)
        or A2A_WORK_CONTRACT_EXTENSION not in envelope_extensions
    ):
        raise BindingError(
            "A2A binding envelope did not declare the IDKMesh Work Contract extension"
        )

    message_extensions = message.get("extensions")
    if (
        not isinstance(message_extensions, list)
        or A2A_WORK_CONTRACT_EXTENSION not in message_extensions
    ):
        raise BindingError("A2A message did not carry the IDKMesh Work Contract extension")
    if message.get("role") != "ROLE_USER":
        raise BindingError("A2A Work Contract message must use ROLE_USER")
    if message.get("messageId") != _a2a_message_id(digest):
        raise BindingError("A2A messageId does not match the canonical Work Unit digest")

    metadata = request.get("metadata")
    if not isinstance(metadata, dict):
        raise BindingError("A2A binding envelope is missing request metadata")
    if metadata.get("idkmeshWorkUnitId") != work_unit["id"]:
        raise BindingError("A2A request metadata Work Unit id mismatch")
    if metadata.get("idkmeshWorkUnitDigest") != digest:
        raise BindingError("A2A request metadata Work Unit digest mismatch")
    if metadata.get("idkmeshExtension") != A2A_WORK_CONTRACT_EXTENSION:
        raise BindingError("A2A request metadata Work Contract extension mismatch")

    text_parts = [
        part.get("text")
        for part in parts
        if isinstance(part, dict) and "text" in part
    ]
    if text_parts != [work_unit["objective"]]:
        raise BindingError(
            "A2A native objective does not match the canonical Work Unit objective"
        )


def to_a2a_send_message(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Create an A2A 1.0 SendMessage request payload.

    Native A2A fields expose the human-readable objective and lifecycle hints. The
    canonical contract is also carried as canonical JSON bytes under the IDKMesh
    extension so protobuf Struct number coercion cannot change integer fields.
    `serviceParameters` models the
    A2A-Version/A2A-Extensions negotiation that a transport adapter must send.
    """

    payload = _contract_payload(work_unit)
    digest = payload["workUnitDigest"]
    message_id = _a2a_message_id(digest)
    return {
        "protocol": "a2a",
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "serviceParameters": _a2a_service_parameters(),
        "extensions": [A2A_WORK_CONTRACT_EXTENSION],
        "request": {
            "message": {
                "messageId": message_id,
                "role": "ROLE_USER",
                "extensions": [A2A_WORK_CONTRACT_EXTENSION],
                "parts": [
                    {
                        "text": work_unit["objective"],
                        "mediaType": "text/plain",
                    },
                    {
                        "raw": base64.b64encode(
                            canonical_json(payload).encode("utf-8")
                        ).decode("ascii"),
                        "mediaType": "application/json",
                    },
                ],
            },
            "configuration": {
                "acceptedOutputModes": [
                    "application/json",
                    "text/plain",
                    "text/x-diff",
                ]
            },
            "metadata": {
                "idkmeshWorkUnitId": work_unit["id"],
                "idkmeshWorkUnitDigest": digest,
                "idkmeshExtension": A2A_WORK_CONTRACT_EXTENSION,
            },
        },
    }


def from_a2a_send_message(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        request = envelope["request"]
        message = request["message"]
        parts = message["parts"]
    except (KeyError, TypeError) as exc:
        raise BindingError("invalid A2A binding envelope") from exc

    if (
        not isinstance(request, dict)
        or not isinstance(message, dict)
        or not isinstance(parts, list)
    ):
        raise BindingError("invalid A2A binding envelope")
    if envelope.get("protocol") != "a2a":
        raise BindingError("not an A2A binding envelope")
    if envelope.get("protocolVersion") != A2A_PROTOCOL_VERSION:
        raise BindingError(
            "unsupported A2A protocolVersion; expected " + A2A_PROTOCOL_VERSION
        )
    _require_a2a_service_parameters(envelope)

    contract_payloads: list[dict[str, Any]] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        data = None
        if "raw" in part:
            try:
                raw = base64.b64decode(part["raw"], validate=True)
                data = json.loads(raw.decode("utf-8"))
            except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BindingError("invalid A2A canonical JSON bytes part") from exc
        elif "data" in part:
            # Backward-compatible decoder for pre-SDK-conformance envelopes.
            data = part["data"]
        if isinstance(data, dict) and "workUnit" in data:
            contract_payloads.append(data)

    if not contract_payloads:
        raise BindingError("A2A envelope contains no IDKMesh Work Contract payload part")
    if len(contract_payloads) != 1:
        raise BindingError(
            "A2A envelope contains multiple IDKMesh Work Contract payload parts"
        )

    data = contract_payloads[0]
    if data.get("schemaVersion") != "0.1":
        raise BindingError("unsupported A2A Work Contract payload schemaVersion")
    work_unit = data["workUnit"]
    expected = data.get("workUnitDigest")
    actual = canonical_digest(work_unit)
    if expected != actual:
        raise BindingError("A2A Work Contract digest mismatch")
    _require_work_unit(work_unit)
    _require_a2a_request_identity(envelope, request, message, parts, work_unit, actual)
    return work_unit


def to_mcp_tool_call(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Create a synchronous MCP 2026-07-28 tools/call request.

    Official SDK 2.2.0 marks Tasks request metadata and capabilities as
    2025-11-25-only. This newer protocol binding therefore fails closed to a
    synchronous call and declares Tasks unsupported instead of advertising a
    capability that the selected revision does not define.
    """

    payload = _contract_payload(work_unit)
    digest = payload["workUnitDigest"]
    request_id = _mcp_request_id(digest)
    return {
        "protocol": "mcp",
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "headers": {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": MCP_EXECUTE_TOOL,
        },
        "request": {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": MCP_EXECUTE_TOOL,
                "arguments": payload,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "idkmesh",
                        "version": "0.1",
                    },
                    "io.modelcontextprotocol/clientCapabilities": {
                        "extensions": {
                            MCP_WORK_CONTRACT_EXTENSION: {
                                "version": "0.1",
                                "asyncTaskMode": "unsupported-for-2026-07-28",
                            },
                        }
                    },
                    MCP_WORK_CONTRACT_EXTENSION: {
                        "workUnitId": work_unit["id"],
                        "workUnitDigest": digest,
                    },
                },
            },
        },
    }


def _require_mcp_request_identity(
    envelope: dict[str, Any],
    request: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed when MCP 2026-07-28 request identity disagrees across layers.

    The 2026-07-28 protocol is stateless: protocol revision, caller metadata, and
    routing information travel with each request. Accepting one representation
    while ignoring a conflicting header or ``_meta`` value would let the same
    envelope mean different things to a transport, SDK, and IDKMesh.
    """

    if envelope.get("protocolVersion") != MCP_PROTOCOL_VERSION:
        raise BindingError(
            "unsupported MCP protocolVersion; expected " + MCP_PROTOCOL_VERSION
        )

    headers = envelope.get("headers")
    if not isinstance(headers, dict):
        raise BindingError("MCP binding envelope is missing routing headers")
    if headers.get("MCP-Protocol-Version") != MCP_PROTOCOL_VERSION:
        raise BindingError(
            "unsupported MCP-Protocol-Version; expected " + MCP_PROTOCOL_VERSION
        )

    if request.get("jsonrpc") != "2.0":
        raise BindingError("MCP binding envelope must use JSON-RPC 2.0")
    if headers.get("Mcp-Method") != request.get("method"):
        raise BindingError("Mcp-Method header does not match JSON-RPC method")
    if headers.get("Mcp-Name") != params.get("name"):
        raise BindingError("Mcp-Name header does not match tools/call name")

    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise BindingError("MCP binding envelope is missing request _meta")
    if meta.get("io.modelcontextprotocol/protocolVersion") != MCP_PROTOCOL_VERSION:
        raise BindingError(
            "MCP request _meta protocol version does not match "
            + MCP_PROTOCOL_VERSION
        )
    return meta


def _require_mcp_work_unit_identity(
    request: dict[str, Any],
    meta: dict[str, Any],
    work_unit: dict[str, Any],
    digest: str,
) -> None:
    """Require every IDKMesh-emitted MCP identity surface to agree.

    The canonical Work Contract already carries a digest, while IDKMesh also
    emits a deterministic JSON-RPC request id and namespaced request metadata for
    routing and observability. A decoder must not accept an envelope where those
    redundant identity views disagree with the canonical Work Unit.
    """

    if request.get("id") != _mcp_request_id(digest):
        raise BindingError("MCP request id does not match the canonical Work Unit digest")

    identity = meta.get(MCP_WORK_CONTRACT_EXTENSION)
    if not isinstance(identity, dict):
        raise BindingError("MCP request _meta is missing Work Contract identity")
    if identity.get("workUnitId") != work_unit["id"]:
        raise BindingError("MCP request _meta Work Unit id mismatch")
    if identity.get("workUnitDigest") != digest:
        raise BindingError("MCP request _meta Work Unit digest mismatch")


def from_mcp_tool_call(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        request = envelope["request"]
        params = request["params"]
        arguments = params["arguments"]
    except (KeyError, TypeError) as exc:
        raise BindingError("invalid MCP binding envelope") from exc

    if envelope.get("protocol") != "mcp" or request.get("method") != "tools/call":
        raise BindingError("not an MCP tools/call binding envelope")
    if params.get("name") != MCP_EXECUTE_TOOL:
        raise BindingError("unexpected MCP tool name")

    meta = _require_mcp_request_identity(envelope, request, params)
    capabilities = meta.get("io.modelcontextprotocol/clientCapabilities")
    if not isinstance(capabilities, dict):
        raise BindingError("MCP binding envelope is missing client capabilities")
    extensions = capabilities.get("extensions", {})
    if not isinstance(extensions, dict) or MCP_WORK_CONTRACT_EXTENSION not in extensions:
        raise BindingError("MCP client did not advertise the IDKMesh Work Contract extension")

    try:
        work_unit = arguments["workUnit"]
        expected = arguments["workUnitDigest"]
    except (KeyError, TypeError) as exc:
        raise BindingError("MCP tool call contains no IDKMesh Work Contract") from exc
    actual = canonical_digest(work_unit)
    if expected != actual:
        raise BindingError("MCP Work Contract digest mismatch")
    _require_work_unit(work_unit)
    _require_mcp_work_unit_identity(request, meta, work_unit, actual)
    return work_unit


def compatibility_report(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Return a machine-readable semantic preservation report.

    `native` means the external protocol has a concept that can be used directly.
    `extension_carried` means IDKMesh retains the canonical semantics in its
    namespaced payload because the protocol does not define the acceptance meaning.
    """

    _require_work_unit(work_unit)
    all_fields = set(work_unit)
    a2a_native = {"id", "objective", "outputs", "context"} & all_fields
    mcp_native = {"objective"} & all_fields
    return {
        "work_unit_id": work_unit["id"],
        "digest": canonical_digest(work_unit),
        "a2a": {
            "protocol_version": A2A_PROTOCOL_VERSION,
            "native": sorted(a2a_native),
            "extension_carried": sorted(all_fields - a2a_native),
            "lost": [],
        },
        "mcp": {
            "protocol_version": MCP_PROTOCOL_VERSION,
            "native": sorted(mcp_native),
            "extension_carried": sorted(all_fields - mcp_native),
            "lost": [],
        },
    }


def normalize_external_completion(protocol: str, state: str) -> dict[str, str]:
    """Normalize protocol completion without confusing it with acceptance."""

    normalized_protocol = protocol.lower()
    if normalized_protocol == "a2a":
        succeeded = state in {"TASK_STATE_COMPLETED", "completed"}
    elif normalized_protocol == "mcp":
        succeeded = state == "completed"
    else:
        raise BindingError(f"unsupported protocol: {protocol}")
    return {
        "protocol": normalized_protocol,
        "execution_status": "succeeded" if succeeded else "not_succeeded",
        "acceptance_status": "pending_verification",
    }
