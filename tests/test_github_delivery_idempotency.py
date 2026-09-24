import json
from pathlib import Path
import tempfile
import threading
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.github_delivery_idempotency import (
    GitHubDeliveryConflict,
    admit_github_delivery,
    github_delivery_idempotency_key,
    github_delivery_request_digest,
)
from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope


def _envelope(**overrides):
    values = {
        "delivery_id": "delivery-123",
        "event": "issues",
        "action": "labeled",
        "repository": "MSKazemi/idkmesh",
        "repository_id": 123,
        "sender_login": "maintainer",
        "sender_id": 42,
        "issue_number": 77,
        "label_name": "agent-ready",
        "installation_id": 999,
        "payload_digest": "sha256:" + "a" * 64,
        "payload_bytes": 512,
    }
    values.update(overrides)
    return GitHubWebhookEnvelope(**values)


class GitHubDeliveryIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "state.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def _store(self):
        return LocalMetadataStore(self.db)

    def test_first_delivery_reserves_deterministic_proposed_run(self):
        envelope = _envelope()
        result = admit_github_delivery(
            store=self._store(),
            envelope=envelope,
            received_at="2026-09-24T01:20:00Z",
        )
        self.assertTrue(result.created)
        self.assertFalse(result.replayed)
        self.assertEqual(result.record.state, "proposed")
        self.assertRegex(result.record.run_id, r"^github/[0-9a-f]{24}$")
        self.assertEqual(
            result.record.idempotency_key,
            github_delivery_idempotency_key(envelope),
        )
        self.assertEqual(
            result.record.request_digest,
            github_delivery_request_digest(envelope),
        )

    def test_exact_replay_after_restart_returns_same_run(self):
        first = admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:20:00Z",
        )
        second = admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:25:00Z",
        )
        self.assertFalse(second.created)
        self.assertTrue(second.replayed)
        self.assertEqual(second.record.run_id, first.record.run_id)
        self.assertEqual(
            second.record.created_at,
            "2026-09-24T01:20:00Z",
        )

    def test_same_delivery_with_changed_payload_fails_closed(self):
        admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:20:00Z",
        )
        with self.assertRaises(GitHubDeliveryConflict):
            admit_github_delivery(
                store=self._store(),
                envelope=_envelope(
                    payload_digest="sha256:" + "b" * 64,
                ),
                received_at="2026-09-24T01:21:00Z",
            )

    def test_same_delivery_with_changed_header_identity_fails_closed(self):
        admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:20:00Z",
        )
        for changes in (
            {"action": "unlabeled"},
            {"sender_id": 43},
            {"label_name": "other-label"},
            {"repository_id": 124},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(GitHubDeliveryConflict):
                    # Keep the idempotency namespace fixed where necessary so
                    # changed normalized content must conflict rather than form
                    # an independent repository delivery.
                    envelope = _envelope(**changes)
                    if "repository_id" in changes:
                        envelope = _envelope(
                            repository_id=123,
                            repository="Other/repo",
                        )
                    admit_github_delivery(
                        store=self._store(),
                        envelope=envelope,
                        received_at="2026-09-24T01:21:00Z",
                    )

    def test_repository_id_is_part_of_delivery_namespace(self):
        one = github_delivery_idempotency_key(_envelope(repository_id=1))
        two = github_delivery_idempotency_key(_envelope(repository_id=2))
        self.assertNotEqual(one, two)

    def test_digest_includes_event_header_identity_not_only_raw_payload_hash(self):
        base = _envelope()
        changed = _envelope(action="unlabeled")
        self.assertEqual(base.payload_digest, changed.payload_digest)
        self.assertNotEqual(
            github_delivery_request_digest(base),
            github_delivery_request_digest(changed),
        )

    def test_persisted_metadata_contains_no_raw_body_or_signature_authority(self):
        result = admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:20:00Z",
        )
        metadata = dict(result.record.metadata)
        rendered = json.dumps(metadata, sort_keys=True)
        self.assertNotIn("body", metadata)
        self.assertNotIn("title", metadata)
        self.assertNotIn("signature", rendered.casefold())
        self.assertNotIn("authorization", rendered.casefold())
        self.assertNotIn("secret", rendered.casefold())
        self.assertEqual(metadata["payload_digest"], "sha256:" + "a" * 64)

    def test_concurrent_exact_replay_creates_exactly_one_run(self):
        self._store()
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def worker(timestamp):
            try:
                store = self._store()
                barrier.wait(timeout=5)
                result = admit_github_delivery(
                    store=store,
                    envelope=_envelope(),
                    received_at=timestamp,
                )
                outcomes.append((result.record.run_id, result.created))
            except Exception as exc:
                failures.append(exc)

        threads = [
            threading.Thread(
                target=worker,
                args=("2026-09-24T01:20:00Z",),
            ),
            threading.Thread(
                target=worker,
                args=("2026-09-24T01:20:01Z",),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sum(1 for _, created in outcomes if created), 1)
        self.assertEqual(len({run_id for run_id, _ in outcomes}), 1)

    def test_to_dict_is_small_replay_projection(self):
        result = admit_github_delivery(
            store=self._store(),
            envelope=_envelope(),
            received_at="2026-09-24T01:20:00Z",
        )
        projection = result.to_dict()
        self.assertEqual(
            set(projection),
            {
                "run_id",
                "state",
                "request_digest",
                "idempotency_key",
                "created",
                "replayed",
            },
        )


if __name__ == "__main__":
    unittest.main()
