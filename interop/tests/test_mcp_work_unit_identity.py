from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.bindings import (  # noqa: E402
    MCP_WORK_CONTRACT_EXTENSION,
    BindingError,
    from_mcp_tool_call,
    to_mcp_tool_call,
)


class MCPWorkUnitIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def test_emitted_identity_surfaces_round_trip(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        meta_identity = envelope["request"]["params"]["_meta"][
            MCP_WORK_CONTRACT_EXTENSION
        ]

        self.assertEqual(meta_identity["workUnitId"], self.work_unit["id"])
        self.assertTrue(envelope["request"]["id"].startswith("idkmesh-"))
        self.assertEqual(from_mcp_tool_call(envelope), self.work_unit)

    def test_jsonrpc_request_id_remains_transport_correlation_only(self) -> None:
        for request_id in ("gateway-request-42", 42):
            with self.subTest(request_id=request_id):
                envelope = to_mcp_tool_call(self.work_unit)
                envelope["request"]["id"] = request_id
                self.assertEqual(from_mcp_tool_call(envelope), self.work_unit)

    def test_invalid_jsonrpc_request_ids_fail_closed(self) -> None:
        invalid_ids = (None, True, 42.0, [], {})

        for request_id in invalid_ids:
            with self.subTest(request_id=request_id):
                envelope = to_mcp_tool_call(self.work_unit)
                envelope["request"]["id"] = request_id

                with self.assertRaisesRegex(
                    BindingError, "request id must be a string or integer"
                ):
                    from_mcp_tool_call(envelope)

    def test_missing_jsonrpc_request_id_fails_closed(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        del envelope["request"]["id"]

        with self.assertRaisesRegex(
            BindingError, "request id must be a string or integer"
        ):
            from_mcp_tool_call(envelope)

    def test_namespaced_work_unit_identity_drift_fails_closed(self) -> None:
        mutations = (
            (
                "work-unit-id",
                lambda identity: identity.__setitem__("workUnitId", "other/work-unit"),
                "Work Unit id mismatch",
            ),
            (
                "work-unit-digest",
                lambda identity: identity.__setitem__(
                    "workUnitDigest", "sha256:" + "0" * 64
                ),
                "Work Unit digest mismatch",
            ),
        )

        for surface, mutate, expected_error in mutations:
            with self.subTest(surface=surface):
                envelope = to_mcp_tool_call(self.work_unit)
                identity = envelope["request"]["params"]["_meta"][
                    MCP_WORK_CONTRACT_EXTENSION
                ]
                mutate(identity)

                with self.assertRaisesRegex(BindingError, expected_error):
                    from_mcp_tool_call(envelope)

    def test_missing_namespaced_work_unit_identity_fails_closed(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        del envelope["request"]["params"]["_meta"][MCP_WORK_CONTRACT_EXTENSION]

        with self.assertRaisesRegex(BindingError, "missing Work Contract identity"):
            from_mcp_tool_call(envelope)

    def test_canonical_payload_tampering_still_fails_before_identity_checks(self) -> None:
        envelope = to_mcp_tool_call(self.work_unit)
        tampered = copy.deepcopy(envelope)
        tampered["request"]["params"]["arguments"]["workUnit"]["objective"] = (
            "tampered"
        )

        with self.assertRaisesRegex(BindingError, "digest mismatch"):
            from_mcp_tool_call(tampered)


if __name__ == "__main__":
    unittest.main()
