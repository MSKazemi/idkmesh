"""Protocol-neutral IDKMesh Work Contract bindings for A2A and MCP.

This module deliberately does not implement network transports. It defines a small,
executable semantic boundary that can be tested without depending on a particular
A2A/MCP SDK. The full canonical Work Unit is carried in a namespaced payload so
IDKMesh-only semantics (verification, risk, provenance, budgets, etc.) are never
silently discarded.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

A2A_PROTOCOL_VERSION = "1.0.0"
MCP_PROTOCOL_VERSION = "2026-07-28"
A2A_WORK_CONTRACT_EXTENSION = "https://idkmesh.org/extensions/work-contract/v0.1"
MCP_WORK_CONTRACT_EXTENSION = "org.idkmesh/work-contract"
MCP_TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
MCP_EXECUTE_TOOL = "idkmesh.execute_work_unit"


class BindingError(ValueError):
    """Raised when an interoperability envelope is malformed or loses integrity."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


def to_a2a_send_message(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Create an A2A 1.0 SendMessage request payload.

    Native A2A fields expose the human-readable objective and lifecycle hints. The
    canonical contract is also carried as JSON data under the IDKMesh extension so
    a remote adapter can reconstruct it exactly.
    """

    payload = _contract_payload(work_unit)
    digest = payload["workUnitDigest"]
    message_id = "idkmesh-" + digest.split(":", 1)[1][:24]
    return {
        "protocol": "a2a",
        "protocolVersion": A2A_PROTOCOL_VERSION,
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
                        "data": payload,
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

    if envelope.get("protocol") != "a2a":
        raise BindingError("not an A2A binding envelope")
    if A2A_WORK_CONTRACT_EXTENSION not in message.get("extensions", []):
        raise BindingError("A2A message did not activate the IDKMesh Work Contract extension")

    for part in parts:
        if not isinstance(part, dict) or "data" not in part:
            continue
        data = part["data"]
        if not isinstance(data, dict) or "workUnit" not in data:
            continue
        work_unit = data["workUnit"]
        expected = data.get("workUnitDigest")
        actual = canonical_digest(work_unit)
        if expected != actual:
            raise BindingError("A2A Work Contract digest mismatch")
        _require_work_unit(work_unit)
        return work_unit
    raise BindingError("A2A envelope contains no IDKMesh Work Contract data part")


def to_mcp_tool_call(work_unit: dict[str, Any]) -> dict[str, Any]:
    """Create an MCP 2026-07-28 tools/call request with Tasks capability.

    The MCP server may execute synchronously or return a Tasks extension handle.
    IDKMesh acceptance remains a separate verification decision either way.
    """

    payload = _contract_payload(work_unit)
    digest = payload["workUnitDigest"]
    request_id = "idkmesh-" + digest.split(":", 1)[1][:24]
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
                            MCP_TASKS_EXTENSION: {},
                            MCP_WORK_CONTRACT_EXTENSION: {"version": "0.1"},
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


def from_mcp_tool_call(envelope: dict[str, Any]) -> dict[str, Any]:
    try:
        request = envelope["request"]
        params = request["params"]
        arguments = params["arguments"]
        capabilities = params["_meta"]["io.modelcontextprotocol/clientCapabilities"]
    except (KeyError, TypeError) as exc:
        raise BindingError("invalid MCP binding envelope") from exc

    if envelope.get("protocol") != "mcp" or request.get("method") != "tools/call":
        raise BindingError("not an MCP tools/call binding envelope")
    if params.get("name") != MCP_EXECUTE_TOOL:
        raise BindingError("unexpected MCP tool name")
    extensions = capabilities.get("extensions", {})
    if MCP_WORK_CONTRACT_EXTENSION not in extensions:
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
