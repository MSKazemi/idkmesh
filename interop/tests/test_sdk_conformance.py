"""Conformance of IDKMesh bindings against the pinned official SDKs.

The protocol SDKs are optional in the default development environment, so each
SDK-backed test is gated independently. A partial installation therefore runs
the conformance test it can run instead of hiding both behind one all-or-nothing
skip. ``interop/README.md`` documents the installation and focused test path.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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

REQUIREMENTS_FILE = "requirements-interoperability.txt"
WORK_UNIT_FIXTURE = ROOT / "examples/work-units/phase0-smoke.work-unit.json"


def _importable(module_name: str) -> bool:
    """Return whether the module imports successfully.

    ``find_spec`` alone is insufficient because a broken or partial install can
    leave import metadata behind. Only a genuinely missing optional dependency
    is converted to a skip; other import-time failures should stay loud.
    """
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def _skip_reason(module_name: str, distribution: str) -> str:
    return (
        f"optional interoperability SDK {distribution!r} not installed "
        f"(`import {module_name}` failed); run "
        f"`python -m pip install -r {REQUIREMENTS_FILE}` and re-run. "
        "Test execution needs no network access, credentials, or environment variable."
    )


A2A_AVAILABLE = _importable("a2a")
MCP_AVAILABLE = _importable("mcp")


def _load_work_unit() -> dict:
    return json.loads(WORK_UNIT_FIXTURE.read_text(encoding="utf-8"))


@unittest.skipUnless(A2A_AVAILABLE, _skip_reason("a2a", "a2a-sdk"))
class OfficialA2aSdkConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = _load_work_unit()

    def test_a2a_v1_protobuf_preserves_exact_work_unit(self) -> None:
        report = validate_a2a_sdk_round_trip(to_a2a_send_message(self.work_unit))
        self.assertEqual(report["distribution"], "a2a-sdk")
        self.assertEqual(report["protocol_version"], "1.0")
        self.assertEqual(report["request_type"], "lf.a2a.v1.SendMessageRequest")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))


@unittest.skipUnless(MCP_AVAILABLE, _skip_reason("mcp", "mcp"))
class OfficialMcpSdkConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = _load_work_unit()

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
