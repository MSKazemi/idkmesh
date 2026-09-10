"""Conformance of the IDKMesh bindings against the pinned official SDKs.

As of this change they are the only tests in the repository that skip. They exercise
``interop/sdk_conformance.py`` against the real A2A and MCP Python
distributions, which are optional on purpose: ``requirements-phase0.txt`` does
not pull them in, so the default test run stays dependency-light and offline.

Each SDK is gated on its own import. An environment that has ``mcp`` but not
``a2a`` runs the MCP case instead of skipping both -- the previous
all-or-nothing gate hid a test that could have run. Nothing else stands between
these tests and execution: no network access at test time, no credentials, no
environment variable, and the only fixture is the tracked Work Unit below.

``interop/README.md`` holds the install command and the per-test requirement
table.
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
    """Report whether ``module_name`` actually imports.

    ``find_spec`` is not enough. A half-installed distribution can leave a
    spec behind that raises on import, which would turn an honest skip into a
    collection error at the top of the run.
    """
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def _skip_reason(module_name: str, distribution: str) -> str:
    """Say what is missing and the one command that fixes it.

    Every skip in this file is avoidable, so the reason names the remedy
    rather than only the symptom. ``pytest -ra`` prints these, which is where
    a contributor reads them.
    """
    return (
        f"optional interoperability SDK {distribution!r} not installed "
        f"(`import {module_name}` failed); "
        f"avoidable -- run `python -m pip install -r {REQUIREMENTS_FILE}` and re-run. "
        f"Needs no network access, credentials, or environment variable."
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
        self.assertEqual(report["tasks_mode"], "unsupported-for-2026-07-28")
        self.assertEqual(report["work_unit_digest"], canonical_digest(self.work_unit))
        extensions = envelope["request"]["params"]["_meta"][
            "io.modelcontextprotocol/clientCapabilities"
        ]["extensions"]
        self.assertNotIn(MCP_TASKS_EXTENSION, extensions)


if __name__ == "__main__":
    unittest.main()
