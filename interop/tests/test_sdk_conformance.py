from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Callable
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _detect_sdk_availability(
    find_spec: Callable[[str], object | None] = importlib.util.find_spec,
) -> tuple[bool, bool]:
    """Return A2A and MCP availability without coupling the optional SDKs."""

    return find_spec("a2a") is not None, find_spec("mcp") is not None


# Keep optional protocol SDKs independent. A contributor may be working on one
# binding only, and a missing unrelated SDK must not erase the conformance
# evidence that is available for the installed protocol.
A2A_SDK_AVAILABLE, MCP_SDK_AVAILABLE = _detect_sdk_availability()

from interop.bindings import (  # noqa: E402
    MCP_TASKS_EXTENSION,
    canonical_digest,
    to_a2a_send_message,
    to_mcp_tool_call,
)
from interop.sdk_conformance import (  # noqa: E402
    validate_a2a_sdk_round_trip,
    validate_mcp_sdk_round_trip,
)


class SdkAvailabilityGateTests(unittest.TestCase):
    def test_partial_sdk_installs_are_detected_independently(self) -> None:
        for installed, expected in (
            ({"a2a"}, (True, False)),
            ({"mcp"}, (False, True)),
            ({"a2a", "mcp"}, (True, True)),
            (set(), (False, False)),
        ):
            with self.subTest(installed=installed):
                detected = _detect_sdk_availability(
                    lambda module_name: object() if module_name in installed else None
                )
                self.assertEqual(detected, expected)


class OfficialSdkConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text()
        )

    @unittest.skipUnless(A2A_SDK_AVAILABLE, "official a2a-sdk is not installed")
    def test_a2a_v1_protobuf_preserves_exact_work_unit(self) -> None:
        report = validate_a2a_sdk_round_trip(to_a2a_send_message(self.work_unit))
        self.assertEqual(report["distribution"], "a2a-sdk")
        self.assertEqual(report["protocol_version"], "1.0")
        self.assertEqual(report["request_type"], "lf.a2a.v1.SendMessageRequest")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))

    @unittest.skipUnless(MCP_SDK_AVAILABLE, "official mcp SDK is not installed")
    def test_mcp_current_types_preserve_exact_work_unit_and_fail_closed_on_tasks(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        report = validate_mcp_sdk_round_trip(envelope)
        self.assertEqual(report["distribution"], "mcp")
        self.assertEqual(report["protocol_version"], "2026-07-28")
        self.assertEqual(report["jsonrpc_version"], "2.0")
        self.assertEqual(report["tasks_mode"], "unsupported-for-2026-07-28")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))
        extensions = envelope["request"]["params"]["_meta"][
            "io.modelcontextprotocol/clientCapabilities"
        ]["extensions"]
        self.assertNotIn(MCP_TASKS_EXTENSION, extensions)


if __name__ == "__main__":
    unittest.main()
