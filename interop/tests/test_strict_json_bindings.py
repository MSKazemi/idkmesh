from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.bindings import (  # noqa: E402
    BindingError,
    canonical_digest,
    from_a2a_send_message,
    from_mcp_tool_call,
    to_a2a_send_message,
    to_mcp_tool_call,
)


class StrictJsonBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def with_cpu_value(self, value: float) -> dict:
        work_unit = copy.deepcopy(self.work_unit)
        work_unit["requirements"]["resources"]["cpu_cores_min"] = value
        return work_unit

    def test_non_finite_numbers_cannot_be_digested_or_bound(self) -> None:
        for label, value in (
            ("nan", float("nan")),
            ("positive infinity", float("inf")),
            ("negative infinity", float("-inf")),
        ):
            work_unit = self.with_cpu_value(value)
            for operation in (
                canonical_digest,
                to_a2a_send_message,
                to_mcp_tool_call,
            ):
                with self.subTest(value=label, operation=operation.__name__):
                    with self.assertRaisesRegex(
                        BindingError,
                        r"non-finite number.*strict JSON requires finite numbers",
                    ):
                        operation(work_unit)

    def test_finite_float_round_trips_remain_unchanged(self) -> None:
        work_unit = self.with_cpu_value(0.125)

        a2a = to_a2a_send_message(work_unit)
        mcp = to_mcp_tool_call(work_unit)

        self.assertEqual(from_a2a_send_message(a2a), work_unit)
        self.assertEqual(from_mcp_tool_call(mcp), work_unit)
        self.assertTrue(a2a["request"]["message"]["messageId"].startswith("idkmesh-"))
        self.assertTrue(mcp["request"]["id"].startswith("idkmesh-"))


if __name__ == "__main__":
    unittest.main()
