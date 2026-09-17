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
    from_a2a_send_message,
    to_a2a_send_message,
)


class A2AMessageIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work_unit = json.loads(
            (ROOT / "examples/work-units/phase0-smoke.work-unit.json").read_text(
                encoding="utf-8"
            )
        )

    def test_sender_selected_message_id_does_not_change_work_unit_identity(self) -> None:
        envelope = to_a2a_send_message(self.work_unit)
        envelope["request"]["message"]["messageId"] = "relay-generated-message-42"

        self.assertEqual(from_a2a_send_message(envelope), self.work_unit)

    def test_message_id_must_remain_a_non_empty_string(self) -> None:
        for invalid in (None, "", 42):
            with self.subTest(message_id=invalid):
                envelope = to_a2a_send_message(self.work_unit)
                envelope["request"]["message"]["messageId"] = invalid
                with self.assertRaisesRegex(BindingError, "non-empty messageId"):
                    from_a2a_send_message(envelope)

    def test_work_contract_metadata_remains_semantic_identity(self) -> None:
        id_mismatch = to_a2a_send_message(self.work_unit)
        id_mismatch["request"]["metadata"]["idkmeshWorkUnitId"] = "other-work-unit"
        with self.assertRaisesRegex(BindingError, "Work Unit id mismatch"):
            from_a2a_send_message(id_mismatch)

        digest_mismatch = to_a2a_send_message(self.work_unit)
        digest_mismatch["request"]["metadata"]["idkmeshWorkUnitDigest"] = "sha256:deadbeef"
        with self.assertRaisesRegex(BindingError, "Work Unit digest mismatch"):
            from_a2a_send_message(digest_mismatch)

    def test_message_id_change_does_not_mask_payload_tampering(self) -> None:
        envelope = to_a2a_send_message(self.work_unit)
        envelope["request"]["message"]["messageId"] = "new-message-id"
        tampered = copy.deepcopy(envelope)
        tampered["request"]["metadata"]["idkmeshWorkUnitId"] = "tampered"

        with self.assertRaisesRegex(BindingError, "Work Unit id mismatch"):
            from_a2a_send_message(tampered)


if __name__ == "__main__":
    unittest.main()
