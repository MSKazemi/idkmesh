"""Conformance checks against pinned official A2A and MCP Python types."""

from __future__ import annotations

import copy
from importlib import metadata
from typing import Any

from interop.bindings import (
    A2A_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_TASKS_EXTENSION,
    BindingError,
    canonical_digest,
    from_a2a_send_message,
    from_mcp_tool_call,
)


def validate_a2a_sdk_round_trip(envelope: dict[str, Any]) -> dict[str, Any]:
    """Round-trip a SendMessage request through official v1 protobuf types."""

    try:
        from a2a.types import SendMessageRequest
        from a2a.utils.constants import PROTOCOL_VERSION_1_0
        from google.protobuf.json_format import MessageToDict, ParseDict
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise BindingError("official a2a-sdk is required for conformance") from exc

    if PROTOCOL_VERSION_1_0 != A2A_PROTOCOL_VERSION:
        raise BindingError("A2A SDK protocol version does not match the binding")
    original = from_a2a_send_message(envelope)
    request = ParseDict(envelope["request"], SendMessageRequest())
    wire = request.SerializeToString(deterministic=True)
    reconstructed_request = MessageToDict(
        SendMessageRequest.FromString(wire),
        preserving_proto_field_name=False,
    )
    reconstructed_envelope = copy.deepcopy(envelope)
    reconstructed_envelope["request"] = reconstructed_request
    reconstructed = from_a2a_send_message(reconstructed_envelope)
    if reconstructed != original:
        raise BindingError("A2A SDK round trip changed the canonical Work Unit")
    return {
        "distribution": "a2a-sdk",
        "distribution_version": metadata.version("a2a-sdk"),
        "protocol_version": PROTOCOL_VERSION_1_0,
        "request_type": request.DESCRIPTOR.full_name,
        "wire_digest": canonical_digest({"protobuf_hex": wire.hex()}),
        "work_unit_digest": canonical_digest(reconstructed),
    }


def validate_mcp_sdk_round_trip(envelope: dict[str, Any]) -> dict[str, Any]:
    """Round-trip tools/call through current official Pydantic request types."""

    try:
        from mcp.types import CallToolRequest, LATEST_PROTOCOL_VERSION, TaskMetadata
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise BindingError("official mcp SDK is required for conformance") from exc

    if LATEST_PROTOCOL_VERSION != MCP_PROTOCOL_VERSION:
        raise BindingError("MCP SDK protocol version does not match the binding")
    original = from_mcp_tool_call(envelope)
    request = CallToolRequest.model_validate(envelope["request"])
    if request.params.task is not None:
        raise BindingError("MCP 2026-07-28 binding must not request legacy Tasks execution")
    advertised = request.params.meta.get(
        "io.modelcontextprotocol/clientCapabilities", {}
    ).get("extensions", {})
    if MCP_TASKS_EXTENSION in advertised:
        raise BindingError("MCP 2026-07-28 binding advertised unsupported Tasks")
    request_dict = request.model_dump(by_alias=True, exclude_none=True, mode="json")
    reconstructed_envelope = copy.deepcopy(envelope)
    reconstructed_envelope["request"] = request_dict
    reconstructed = from_mcp_tool_call(reconstructed_envelope)
    if reconstructed != original:
        raise BindingError("MCP SDK round trip changed the canonical Work Unit")
    task_scope = TaskMetadata.__doc__ or ""
    if "2025-11-25 only" not in task_scope:
        raise BindingError("MCP SDK Tasks revision scope changed; review the binding")
    return {
        "distribution": "mcp",
        "distribution_version": metadata.version("mcp"),
        "protocol_version": LATEST_PROTOCOL_VERSION,
        "request_type": type(request).__name__,
        "tasks_mode": "unsupported-for-2026-07-28",
        "work_unit_digest": canonical_digest(reconstructed),
    }
