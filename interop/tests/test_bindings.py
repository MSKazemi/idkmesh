from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.bindings import (  # noqa: E402
    A2A_WORK_CONTRACT_EXTENSION,
    MCP_TASKS_EXTENSION,
    MCP_WORK_CONTRACT_EXTENSION,
    BindingError,
    compatibility_report,
    from_a2a_send_message,
    from_mcp_tool_call,
    normalize_external_completion,
    to_a2a_send_message,
    to_mcp_tool_call,
    SUPPORTED_WORK_UNIT_VERSIONS,
)


class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def test_a2a_round_trip_is_lossless(self) -> None:
        envelope = to_a2a_send_message(self.work_unit)
        self.assertEqual(envelope["protocolVersion"], "1.0.0")
        self.assertIn(A2A_WORK_CONTRACT_EXTENSION, envelope["extensions"])
        self.assertEqual(
            envelope["request"]["message"]["role"],
            "ROLE_USER",
        )
        self.assertEqual(from_a2a_send_message(envelope), self.work_unit)

    def test_mcp_round_trip_is_lossless_and_advertises_tasks(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        self.assertEqual(envelope["protocolVersion"], "2026-07-28")
        self.assertEqual(envelope["request"]["method"], "tools/call")
        extensions = envelope["request"]["params"]["_meta"][
            "io.modelcontextprotocol/clientCapabilities"
        ]["extensions"]
        self.assertIn(MCP_TASKS_EXTENSION, extensions)
        self.assertIn(MCP_WORK_CONTRACT_EXTENSION, extensions)
        self.assertEqual(from_mcp_tool_call(envelope), self.work_unit)

    def test_a2a_tampering_is_detected(self) -> None:
        envelope = to_a2a_send_message(self.work_unit)
        tampered = copy.deepcopy(envelope)
        tampered["request"]["message"]["parts"][1]["data"]["workUnit"][
            "objective"
        ] = "tampered"
        with self.assertRaisesRegex(BindingError, "digest mismatch"):
            from_a2a_send_message(tampered)

    def test_mcp_tampering_is_detected(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        tampered = copy.deepcopy(envelope)
        tampered["request"]["params"]["arguments"]["workUnit"]["objective"] = (
            "tampered"
        )
        with self.assertRaisesRegex(BindingError, "digest mismatch"):
            from_mcp_tool_call(tampered)

    def test_no_canonical_work_unit_fields_are_lost(self) -> None:
        report = compatibility_report(self.work_unit)
        self.assertEqual(report["a2a"]["lost"], [])
        self.assertEqual(report["mcp"]["lost"], [])
        self.assertIn("validators", report["a2a"]["extension_carried"])
        self.assertIn("validators", report["mcp"]["extension_carried"])
        self.assertIn("permissions", report["a2a"]["extension_carried"])

    def test_protocol_completion_never_means_idkmesh_acceptance(self) -> None:
        a2a = normalize_external_completion("a2a", "TASK_STATE_COMPLETED")
        mcp = normalize_external_completion("mcp", "completed")
        self.assertEqual(a2a["execution_status"], "succeeded")
        self.assertEqual(mcp["execution_status"], "succeeded")
        self.assertEqual(a2a["acceptance_status"], "pending_verification")
        self.assertEqual(mcp["acceptance_status"], "pending_verification")


if __name__ == "__main__":
    unittest.main()


class WorkUnitVersionSupportTests(unittest.TestCase):
    """Both canonical Work Unit versions must bind losslessly.

    v0.2 is additive over v0.1 and leaves `id`, `objective` and `schema_version`
    untouched, so pinning to a single version was drift, not a safety property.
    """

    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.work_unit = json.loads(
            (root / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def test_current_canonical_example_is_supported(self):
        # Guards against the schema advancing past the bindings again.
        self.assertIn(self.work_unit["schema_version"], SUPPORTED_WORK_UNIT_VERSIONS)
        compatibility_report(self.work_unit)

    def test_both_supported_versions_bind(self):
        for version in sorted(SUPPORTED_WORK_UNIT_VERSIONS):
            unit = copy.deepcopy(self.work_unit)
            unit["schema_version"] = version
            with self.subTest(version=version):
                compatibility_report(unit)

    def test_unknown_version_is_rejected_and_names_what_is_supported(self):
        unit = copy.deepcopy(self.work_unit)
        unit["schema_version"] = "9.9"
        with self.assertRaises(BindingError) as ctx:
            compatibility_report(unit)
        self.assertIn("9.9", str(ctx.exception))
        for version in SUPPORTED_WORK_UNIT_VERSIONS:
            self.assertIn(version, str(ctx.exception))
