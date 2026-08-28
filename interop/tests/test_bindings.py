from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.bindings import (  # noqa: E402
    A2A_EXTENSION_URI,
    MCP_EXTENSION_ID,
    MCP_TASKS_EXTENSION_ID,
    BindingError,
    compatibility_report,
    from_a2a_envelope,
    from_mcp_envelope,
    normalize_external_completion,
    to_a2a_envelope,
    to_mcp_envelope,
)


class InteroperabilityBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def test_fixture_is_current_workunit_v0_2(self) -> None:
        self.assertEqual(self.work_unit["schema_version"], "0.2")
        self.assertIn("security", self.work_unit)
        self.assertIn("verification_policy", self.work_unit)

    def test_a2a_round_trip_preserves_complete_contract(self) -> None:
        envelope = to_a2a_envelope(self.work_unit)
        self.assertEqual(envelope["protocol_version"], "1.0.0")
        self.assertEqual(envelope["extension_uri"], A2A_EXTENSION_URI)
        self.assertEqual(envelope["send_message"]["message"]["role"], "ROLE_USER")
        self.assertEqual(from_a2a_envelope(envelope), self.work_unit)

    def test_mcp_round_trip_preserves_complete_contract(self) -> None:
        envelope = to_mcp_envelope(self.work_unit)
        self.assertEqual(envelope["protocol_version"], "2026-07-28")
        self.assertEqual(envelope["request"]["method"], "tools/call")
        extensions = envelope["request"]["params"]["_meta"][
            "io.modelcontextprotocol/clientCapabilities"
        ]["extensions"]
        self.assertIn(MCP_TASKS_EXTENSION_ID, extensions)
        self.assertIn(MCP_EXTENSION_ID, extensions)
        self.assertEqual(from_mcp_envelope(envelope), self.work_unit)

    def test_a2a_tampering_is_rejected(self) -> None:
        envelope = copy.deepcopy(to_a2a_envelope(self.work_unit))
        envelope["send_message"]["message"]["parts"][1]["data"]["workUnit"][
            "security"
        ]["risk_class"] = "critical"
        with self.assertRaisesRegex(BindingError, "digest mismatch"):
            from_a2a_envelope(envelope)

    def test_mcp_tampering_is_rejected(self) -> None:
        envelope = copy.deepcopy(to_mcp_envelope(self.work_unit))
        envelope["request"]["params"]["arguments"]["workUnit"][
            "verification_policy"
        ]["minimum_independent_verifiers"] = 0
        with self.assertRaisesRegex(BindingError, "digest mismatch"):
            from_mcp_envelope(envelope)

    def test_security_and_verification_fields_are_never_lost(self) -> None:
        report = compatibility_report(self.work_unit)
        for protocol in ("a2a", "mcp"):
            self.assertEqual(report[protocol]["lost"], [])
            self.assertIn("security", report[protocol]["extension_carried"])
            self.assertIn("permissions", report[protocol]["extension_carried"])
            self.assertIn("verification_policy", report[protocol]["extension_carried"])
            self.assertIn("evidence_requirements", report[protocol]["extension_carried"])

    def test_external_completion_is_never_acceptance(self) -> None:
        a2a = normalize_external_completion("a2a", "TASK_STATE_COMPLETED")
        mcp = normalize_external_completion("mcp", "completed")
        self.assertEqual(a2a["execution_status"], "succeeded")
        self.assertEqual(mcp["execution_status"], "succeeded")
        self.assertEqual(
            a2a["acceptance_status"], "pending_independent_verification"
        )
        self.assertEqual(
            mcp["acceptance_status"], "pending_independent_verification"
        )

    def test_old_workunit_version_is_rejected_by_current_binding(self) -> None:
        old = copy.deepcopy(self.work_unit)
        old["schema_version"] = "0.1"
        with self.assertRaisesRegex(BindingError, "schema_version '0.2'"):
            to_a2a_envelope(old)


if __name__ == "__main__":
    unittest.main()
