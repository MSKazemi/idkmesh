from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interop.identity import (  # noqa: E402
    IDENTITY_BINDING_EXTENSION,
    IdentityBindingError,
    attach_identity_binding,
    build_identity_binding,
    get_identity_binding,
)


class IdentityBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result_manifest = json.loads(
            (ROOT / "examples/results/phase0-smoke.result-manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_a2a_identity_evidence_attaches_without_changing_core_worker(self) -> None:
        binding = build_identity_binding(
            protocol="a2a",
            subject="https://agent.example/.well-known/agent-card.json",
            verified=True,
            evidence_digest="sha256:" + "a" * 64,
            evidence_locator="agent-card.json",
            verification_method="signed-agent-card",
        )
        updated = attach_identity_binding(self.result_manifest, binding)

        self.assertEqual(updated["worker"], self.result_manifest["worker"])
        self.assertNotIn(IDENTITY_BINDING_EXTENSION, self.result_manifest.get("extensions", {}))
        self.assertEqual(get_identity_binding(updated), binding)

    def test_unverified_binding_is_valid_but_not_promoted_to_authority(self) -> None:
        binding = build_identity_binding(
            protocol="direct",
            subject="local-worker-1",
            verified=False,
        )
        updated = attach_identity_binding(self.result_manifest, binding)
        self.assertFalse(get_identity_binding(updated)["verified"])
        self.assertNotIn("authorized", get_identity_binding(updated))
        self.assertNotIn("accepted", get_identity_binding(updated))

    def test_malformed_digest_fails_closed(self) -> None:
        with self.assertRaisesRegex(IdentityBindingError, "evidence_digest"):
            build_identity_binding(
                protocol="a2a",
                subject="agent-card",
                verified=True,
                evidence_digest="sha256:not-a-real-digest",
            )

    def test_existing_identity_evidence_is_not_silently_overwritten(self) -> None:
        first = build_identity_binding(
            protocol="a2a",
            subject="agent-one",
            verified=True,
        )
        second = build_identity_binding(
            protocol="mcp",
            subject="workload-two",
            verified=True,
        )
        updated = attach_identity_binding(self.result_manifest, first)
        with self.assertRaisesRegex(IdentityBindingError, "already exists"):
            attach_identity_binding(updated, second)

    def test_identity_extension_remains_optional(self) -> None:
        self.assertIsNone(get_identity_binding(self.result_manifest))


if __name__ == "__main__":
    unittest.main()
