from __future__ import annotations

import base64
import copy
import json
import unittest

from interop.bindings import (
    A2A_WORK_CONTRACT_EXTENSION,
    BindingError,
    canonical_json,
    from_a2a_send_message,
    to_a2a_send_message,
)


WORK_UNIT = {
    "schema_version": "0.2",
    "id": "a2a-semantic-identity-smoke",
    "objective": "Preserve one canonical task across every A2A request view.",
}


def _rewrite_payload(envelope: dict, mutate) -> None:
    raw_part = envelope["request"]["message"]["parts"][1]
    payload = json.loads(base64.b64decode(raw_part["raw"]).decode("utf-8"))
    mutate(payload)
    raw_part["raw"] = base64.b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")


class A2ASemanticIdentityTests(unittest.TestCase):
    def test_emitted_request_round_trips(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        self.assertEqual(from_a2a_send_message(envelope), WORK_UNIT)

    def test_native_objective_cannot_disagree_with_canonical_payload(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        envelope["request"]["message"]["parts"][0]["text"] = "Do something else."
        with self.assertRaisesRegex(BindingError, "native objective"):
            from_a2a_send_message(envelope)

    def test_request_metadata_must_match_canonical_identity(self) -> None:
        mutations = (
            ("id", "idkmeshWorkUnitId", "other", "id mismatch"),
            (
                "digest",
                "idkmeshWorkUnitDigest",
                "sha256:" + "0" * 64,
                "digest mismatch",
            ),
            (
                "extension",
                "idkmeshExtension",
                "https://example.invalid/other",
                "extension mismatch",
            ),
        )
        for name, key, value, message in mutations:
            with self.subTest(name=name):
                envelope = to_a2a_send_message(WORK_UNIT)
                envelope["request"]["metadata"][key] = value
                with self.assertRaisesRegex(BindingError, message):
                    from_a2a_send_message(envelope)

    def test_message_role_must_match_the_binding(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        envelope["request"]["message"]["role"] = "ROLE_AGENT"
        with self.assertRaisesRegex(BindingError, "ROLE_USER"):
            from_a2a_send_message(envelope)

    def test_extension_declaration_must_be_consistent(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        envelope["extensions"] = []
        with self.assertRaisesRegex(BindingError, "did not declare"):
            from_a2a_send_message(envelope)

        envelope = to_a2a_send_message(WORK_UNIT)
        envelope["request"]["message"]["extensions"] = []
        with self.assertRaisesRegex(BindingError, "did not carry"):
            from_a2a_send_message(envelope)

        envelope = to_a2a_send_message(WORK_UNIT)
        self.assertIn(A2A_WORK_CONTRACT_EXTENSION, envelope["extensions"])

    def test_multiple_canonical_payloads_are_ambiguous_and_rejected(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        envelope["request"]["message"]["parts"].append(
            copy.deepcopy(envelope["request"]["message"]["parts"][1])
        )
        with self.assertRaisesRegex(BindingError, "multiple"):
            from_a2a_send_message(envelope)

    def test_work_contract_payload_version_is_checked(self) -> None:
        envelope = to_a2a_send_message(WORK_UNIT)
        _rewrite_payload(
            envelope,
            lambda payload: payload.__setitem__("schemaVersion", "9.9"),
        )
        with self.assertRaisesRegex(BindingError, "schemaVersion"):
            from_a2a_send_message(envelope)


if __name__ == "__main__":
    unittest.main()
