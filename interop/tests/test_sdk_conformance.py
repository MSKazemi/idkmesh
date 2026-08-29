from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import a2a  # noqa: F401
    import mcp  # noqa: F401
except ImportError:
    OFFICIAL_SDKS_AVAILABLE = False
else:
    OFFICIAL_SDKS_AVAILABLE = True

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


@unittest.skipUnless(OFFICIAL_SDKS_AVAILABLE, "official interoperability SDKs not installed")
class OfficialSdkConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text()
        )

    def test_a2a_v1_protobuf_preserves_exact_work_unit(self) -> None:
        report = validate_a2a_sdk_round_trip(to_a2a_send_message(self.work_unit))
        self.assertEqual(report["distribution"], "a2a-sdk")
        self.assertEqual(report["protocol_version"], "1.0")
        self.assertEqual(report["request_type"], "lf.a2a.v1.SendMessageRequest")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))

    def test_mcp_current_types_preserve_exact_work_unit_and_fail_closed_on_tasks(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        report = validate_mcp_sdk_round_trip(envelope)
        self.assertEqual(report["distribution"], "mcp")
        self.assertEqual(report["protocol_version"], "2026-07-28")
        self.assertEqual(report["tasks_mode"], "unsupported-for-2026-07-28")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))
        extensions = envelope["request"]["params"]["_meta"][
            "io.modelcontextprotocol/clientCapabilities"
        ]["extensions"]
        self.assertNotIn(MCP_TASKS_EXTENSION, extensions)


if __name__ == "__main__":
    unittest.main()
