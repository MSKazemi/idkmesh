"""Lossless semantic bindings from IDKMesh WorkUnit v0.2 to A2A and MCP.

These helpers are intentionally transport-library neutral. They produce normalized
binding envelopes that preserve the complete canonical WorkUnit plus a digest.
A protocol SDK adapter may translate these envelopes into concrete SDK objects.

The critical invariant is that external task completion is execution evidence only;
it never means that IDKMesh has accepted the candidate artifact.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

WORK_UNIT_SCHEMA_VERSION = "0.2"
A2A_PROTOCOL_VERSION = "1.0.0"
MCP_PROTOCOL_VERSION = "2026-07-28"
A2A_EXTENSION_URI = "https://idkmesh.org/extensions/work-contract/v0.2"
MCP_EXTENSION_ID = "org.idkmesh/work-contract"
MCP_TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"
MCP_EXECUTE_TOOL = "idkmesh.execute_work_unit"


class BindingError(ValueError):
    """Raised when an interoperability binding is malformed or loses integrity."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_work_unit(work_unit: dict[str, Any]) -> None:
    if not isinstance(work_unit, dict):
        raise BindingError("WorkUnit must be an object")
    if work_unit.get("schema_version") != WORK_UNIT_SCHEMA_VERSION:
        raise BindingError("binding supports canonical WorkUnit schema_version '0.2'")
    for field in (
        "id",
        "objective",
        "requirements",
        "security",
        "permissions",
        "verification_policy",
        "validators",
        "evidence_requirements",
    ):
        if field not in work_unit:
            raise BindingError(f"WorkUnit is missing required field: {field}")
    if not isinstance(work_unit["id"], str) or not work_unit["id"]:
        raise BindingError("WorkUnit id must be a non-empty string")
    if not isinstance(work_unit["objective"], str) or not work_unit["objective"]:
        raise BindingError("WorkUnit objective must be a non-empty string")


def _payload(work_unit: dict[str, Any]) -> dict[str, Any]:
    _require_work_unit(work_unit)
    return {
        "schemaVersion": WORK_UNIT_SCHEMA_VERSION,
        "workUnitDigest": canonical_digest(work_unit),
        "workUnit": work_unit,
    }


def to_a2a_envelope(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized A2A 1.0 semantic envelope.

    The objective is exposed as a native text Part. The complete WorkUnit is also
    carried as structured data under the IDKMesh extension, because A2A does not
    define IDKMesh verification/risk/integration semantics.
    """

    payload = _payload(work_unit)
    digest = payload["workUnitDigest"]
    return {
        "binding": "a2a",
        "protocol_version": A2A_PROTOCOL_VERSION,
        "extension_uri": A2A_EXTENSION_URI,
        "send_message": {
            "message": {
                "messageId": "idkmesh-" + digest.split(":", 1)[1][:24],
                "role": "ROLE_USER",
                "extensions": [A2A_EXTENSION_URI],
                "parts": [
                    {"text": work_unit["objective"], "mediaType": "text/plain"},
                    {"data": payload, "mediaType": "application/json"},
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
            },
        },
    }


def from_a2a_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        message = envelope["send_message"]["message"]
        parts = message["parts"]
    except (KeyError, TypeError) as exc:
        raise BindingError("invalid A2A binding envelope") from exc
    if envelope.get("binding") != "a2a":
        raise BindingError("not an A2A binding envelope")
    if A2A_EXTENSION_URI not in message.get("extensions", []):
        raise BindingError("A2A message did not activate the IDKMesh extension")

    for part in parts:
        if not isinstance(part, dict):
            continue
        data = part.get("data")
        if not isinstance(data, dict) or "workUnit" not in data:
            continue
        work_unit = data["workUnit"]
        expected = data.get("workUnitDigest")
        actual = canonical_digest(work_unit)
        if expected != actual:
            raise BindingError("A2A WorkUnit digest mismatch")
        _require_work_unit(work_unit)
        return work_unit
    raise BindingError("A2A envelope contains no IDKMesh WorkUnit data Part")


def to_mcp_envelope(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized MCP 2026-07-28 tools/call semantic envelope.

    The envelope advertises MCP Tasks as an optional asynchronous capability and
    carries the complete WorkUnit in tool arguments. Local IDKMesh operation does
    not depend on MCP Tasks support.
    """

    payload = _payload(work_unit)
    digest = payload["workUnitDigest"]
    return {
        "binding": "mcp",
        "protocol_version": MCP_PROTOCOL_VERSION,
        "headers": {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": MCP_EXECUTE_TOOL,
        },
        "request": {
            "jsonrpc": "2.0",
            "id": "idkmesh-" + digest.split(":", 1)[1][:24],
            "method": "tools/call",
            "params": {
                "name": MCP_EXECUTE_TOOL,
                "arguments": payload,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "idkmesh",
                        "version": "0.2",
                    },
                    "io.modelcontextprotocol/clientCapabilities": {
                        "extensions": {
                            MCP_TASKS_EXTENSION_ID: {},
                            MCP_EXTENSION_ID: {"version": WORK_UNIT_SCHEMA_VERSION},
                        }
                    },
                    MCP_EXTENSION_ID: {
                        "workUnitId": work_unit["id"],
                        "workUnitDigest": digest,
                    },
                },
            },
        },
    }


def from_mcp_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        request = envelope["request"]
        params = request["params"]
        arguments = params["arguments"]
        extensions = params["_meta"]["io.modelcontextprotocol/clientCapabilities"][
            "extensions"
        ]
    except (KeyError, TypeError) as exc:
        raise BindingError("invalid MCP binding envelope") from exc
    if envelope.get("binding") != "mcp" or request.get("method") != "tools/call":
        raise BindingError("not an MCP tools/call binding envelope")
    if params.get("name") != MCP_EXECUTE_TOOL:
        raise BindingError("unexpected MCP tool name")
    if MCP_EXTENSION_ID not in extensions:
        raise BindingError("MCP client did not advertise the IDKMesh Work Contract extension")

    try:
        work_unit = arguments["workUnit"]
        expected = arguments["workUnitDigest"]
    except (KeyError, TypeError) as exc:
        raise BindingError("MCP envelope contains no IDKMesh WorkUnit") from exc
    actual = canonical_digest(work_unit)
    if expected != actual:
        raise BindingError("MCP WorkUnit digest mismatch")
    _require_work_unit(work_unit)
    return work_unit


def normalize_external_completion(protocol: str, state: str) -> dict[str, str]:
    """Normalize worker execution state without creating an acceptance verdict."""

    protocol = protocol.lower()
    if protocol == "a2a":
        successful = state in {"TASK_STATE_COMPLETED", "completed"}
    elif protocol == "mcp":
        successful = state == "completed"
    else:
        raise BindingError(f"unsupported protocol: {protocol}")
    return {
        "protocol": protocol,
        "execution_status": "succeeded" if successful else "not_succeeded",
        "acceptance_status": "pending_independent_verification",
    }


def compatibility_report(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Explain which WorkUnit fields are native hints vs IDKMesh semantics.

    Every field is preserved because the full canonical document travels in the
    extension payload. `native` means the external protocol has a closely related
    concept; `extension_carried` means IDKMesh remains semantically authoritative.
    """

    _require_work_unit(work_unit)
    fields = set(work_unit)
    a2a_native = {"id", "objective", "inputs", "outputs", "context"} & fields
    mcp_native = {"objective", "inputs", "outputs"} & fields
    return {
        "work_unit_id": work_unit["id"],
        "work_unit_digest": canonical_digest(work_unit),
        "a2a": {
            "protocol_version": A2A_PROTOCOL_VERSION,
            "native": sorted(a2a_native),
            "extension_carried": sorted(fields - a2a_native),
            "lost": [],
        },
        "mcp": {
            "protocol_version": MCP_PROTOCOL_VERSION,
            "native": sorted(mcp_native),
            "extension_carried": sorted(fields - mcp_native),
            "lost": [],
        },
    }
