"""Tests for restart-safe Product Spine idempotency composition."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

from idkmesh.candidate_reference import ArtifactBundleCandidateReference
from idkmesh.connector_routing import ConnectorProfile, RoutingDecision
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.product_spine_idempotency import (
    IdempotentOfflineProductSpineService,
    offline_idempotency_request_digest,
)
from idkmesh.product_spine_offline import (
    ObservedCandidate,
    OfflineAttemptSpec,
    OfflineProductSpineError,
    OfflineProductSpineService,
)
from idkmesh.work_unit_binding import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import run_evidence_report  # noqa: E402


SOURCE = "0123456789abcdef0123456789abcdef01234567"
CREATED = "2026-09-24T01:10:00Z"
UPDATED = "2026-09-24T01:10:01Z"
STARTED = datetime(2026, 9, 24, 1, 0, 0, tzinfo=timezone.utc)
FINISHED = datetime(2026, 9, 24, 1, 0, 1, tzinfo=timezone.utc)
VERIFIER_CONFIG_DIGEST = "sha256:" + "9" * 64


def _work_unit() -> dict:
    work = json.loads(
        (
            ROOT
            / "examples"
            / "work-units"
            / "local-verifier-smoke.work-unit.json"
        ).read_text(encoding="utf-8")
    )
    work["provenance"]["source_revision"] = SOURCE
    work["provenance"]["source"] = "offline-idempotency-fixture"
    return work


def _connector() -> ConnectorProfile:
    return ConnectorProfile(
        connection_id="fake-agent",
        kind="agent",
        driver="offline-fake",
        capability_tiers=frozenset({"T2"}),
        max_risk="low",
        external_processing=False,
        project_cost_usd=0.0,
    )


def _routing(*, tier: str = "T1") -> RoutingDecision:
    return RoutingDecision(
        required_capability_tier=tier,
        authority_mode="agent_candidate",
        risk_class="low",
        external_processing_allowed=False,
        project_spend_usd_max=0.0,
        independent_reviewer_required=True,
    )


def _attempt(
    work_unit: dict,
    candidate_root: Path,
    *,
    reference_digest_byte: str = "a",
) -> OfflineAttemptSpec:
    reference = ArtifactBundleCandidateReference(
        locator="candidate.json",
        digest="sha256:" + reference_digest_byte * 64,
        media_type="application/json",
    )
    candidate = ObservedCandidate(
        reference=reference,
        candidate_root=candidate_root,
        attempt_id="attempt-1",
        work_unit_digest=canonical_digest(work_unit),
        source_revision=SOURCE,
    )
    return OfflineAttemptSpec(
        attempt_id="attempt-1",
        outcome="candidate",
        started_at=STARTED,
        finished_at=FINISHED,
        candidate=candidate,
    )


def _offline_service(calls: list[str]) -> OfflineProductSpineService:
    def verifier(
        *,
        work_unit,
        result_manifest,
        handoff,
        candidate,
    ):
        calls.append(candidate.attempt_id)
        return {
            "schema_version": "0.1",
            "id": f"verification/{candidate.attempt_id}",
            "work_unit_id": handoff.work_unit_id,
            "work_unit_version": handoff.work_unit_version,
            "result_manifest_id": handoff.result_manifest_id,
            "verifier": {
                "id": "offline-idempotency-verifier",
                "type": "system",
                "adapter": "fixture-verifier",
                "adapter_version": "0.1",
            },
            "status": "passed",
            "checks": [
                {
                    "id": validator_id,
                    "type": "review",
                    "required": True,
                    "status": "passed",
                    "summary": "Deterministic PS-C fixture check.",
                    "evidence_ids": [],
                }
                for validator_id in handoff.required_validator_ids
            ],
            "evidence": [],
            "findings": [],
            "independence": {
                "independent_from_worker": True,
                "worker_id": result_manifest["worker"]["id"],
                "correlation_notes": "PS-C idempotency fixture.",
            },
            "provenance": {
                "work_unit_digest": handoff.work_unit_digest,
                "result_manifest_digest": handoff.result_manifest_digest,
                "source_revision": handoff.source_revision,
                "verifier_config_digest": VERIFIER_CONFIG_DIGEST,
            },
            "decision_support": {
                "recommendation": "accept_candidate",
                "rationale": "Deterministic idempotency fixture.",
            },
        }

    return OfflineProductSpineService(
        verifier=verifier,
        evidence_builder=run_evidence_report.build_report,
    )


def _execute(
    wrapper: IdempotentOfflineProductSpineService,
    *,
    work: dict,
    attempt: OfflineAttemptSpec,
    key: str = "idem/offline-run",
    routing: RoutingDecision | None = None,
):
    return wrapper.execute(
        idempotency_key=key,
        created_at=CREATED,
        updated_at=UPDATED,
        project_id="MSKazemi/idkmesh",
        work_unit=work,
        source_revision=SOURCE,
        routing_decision=routing or _routing(),
        connectors=[_connector()],
        attempts=[attempt],
    )


class ProductSpineIdempotencyTests(unittest.TestCase):
    def test_restart_replay_reuses_run_without_second_verifier_call(self):
        work = _work_unit()

        with tempfile.TemporaryDirectory(prefix="idkmesh-ps-idem-") as raw:
            root = Path(raw)
            db = root / "state.sqlite"
            attempt = _attempt(work, root / "candidate-a")

            first_calls: list[str] = []
            first = _execute(
                IdempotentOfflineProductSpineService(
                    service=_offline_service(first_calls),
                    store=LocalMetadataStore(db),
                ),
                work=work,
                attempt=attempt,
            )

            self.assertTrue(first.created)
            self.assertFalse(first.replayed)
            self.assertEqual(first_calls, ["attempt-1"])
            self.assertEqual(
                first.run.state,
                "awaiting_human_decision",
            )

            second_calls: list[str] = []
            second = _execute(
                IdempotentOfflineProductSpineService(
                    service=_offline_service(second_calls),
                    store=LocalMetadataStore(db),
                ),
                work=work,
                attempt=attempt,
            )

            self.assertFalse(second.created)
            self.assertTrue(second.replayed)
            self.assertEqual(second_calls, [])
            self.assertEqual(
                second.run.to_dict(),
                first.run.to_dict(),
            )
            self.assertEqual(
                second.evidence_report,
                first.evidence_report,
            )

            stored = LocalMetadataStore(db).get_run(first.run.run_id)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored.run_id, first.run.run_id)
            self.assertEqual(
                stored.request_digest,
                first.request_digest,
            )
            self.assertEqual(
                stored.state,
                "awaiting_human_decision",
            )

    def test_same_key_different_request_conflicts_before_new_work(self):
        work = _work_unit()

        with tempfile.TemporaryDirectory(prefix="idkmesh-ps-idem-") as raw:
            root = Path(raw)
            calls: list[str] = []
            wrapper = IdempotentOfflineProductSpineService(
                service=_offline_service(calls),
                store=LocalMetadataStore(root / "state.sqlite"),
            )
            attempt = _attempt(work, root / "candidate-a")

            _execute(wrapper, work=work, attempt=attempt)
            self.assertEqual(calls, ["attempt-1"])

            changed = deepcopy(work)
            changed["objective"] = (
                "Changed logical request under the same idempotency key."
            )
            changed_attempt = _attempt(
                changed,
                root / "candidate-b",
                reference_digest_byte="b",
            )

            with self.assertRaises(
                OfflineProductSpineError
            ) as caught:
                _execute(
                    wrapper,
                    work=changed,
                    attempt=changed_attempt,
                )

            self.assertEqual(
                caught.exception.code,
                "idempotency_conflict",
            )
            self.assertEqual(calls, ["attempt-1"])

    def test_incomplete_reserved_request_fails_closed_without_duplicate_work(self):
        work = _work_unit()

        with tempfile.TemporaryDirectory(prefix="idkmesh-ps-idem-") as raw:
            root = Path(raw)
            store = LocalMetadataStore(root / "state.sqlite")
            attempt = _attempt(work, root / "candidate-a")
            digest = offline_idempotency_request_digest(
                project_id="MSKazemi/idkmesh",
                work_unit=work,
                source_revision=SOURCE,
                routing_decision=_routing(),
                connectors=[_connector()],
                attempts=[attempt],
            )
            store.admit_run(
                run_id="offline/crash-reservation",
                idempotency_key="idem/offline-run",
                request_digest=digest,
                state="proposed",
                metadata={
                    "schema_version": "0.1",
                    "kind": "product-spine-idempotency-admission",
                },
                created_at=CREATED,
            )

            calls: list[str] = []
            wrapper = IdempotentOfflineProductSpineService(
                service=_offline_service(calls),
                store=LocalMetadataStore(root / "state.sqlite"),
            )

            with self.assertRaises(
                OfflineProductSpineError
            ) as caught:
                _execute(
                    wrapper,
                    work=work,
                    attempt=attempt,
                )

            self.assertEqual(
                caught.exception.code,
                "idempotency_recovery_required",
            )
            self.assertEqual(calls, [])

    def test_tampered_persisted_evidence_fails_closed_on_replay(self):
        work = _work_unit()

        with tempfile.TemporaryDirectory(prefix="idkmesh-ps-idem-") as raw:
            root = Path(raw)
            db = root / "state.sqlite"
            attempt = _attempt(work, root / "candidate-a")
            calls: list[str] = []
            wrapper = IdempotentOfflineProductSpineService(
                service=_offline_service(calls),
                store=LocalMetadataStore(db),
            )
            first = _execute(
                wrapper,
                work=work,
                attempt=attempt,
            )
            self.assertEqual(calls, ["attempt-1"])

            store = LocalMetadataStore(db)
            record = store.get_run(first.run.run_id)
            self.assertIsNotNone(record)
            assert record is not None
            metadata = deepcopy(dict(record.metadata))
            metadata["evidence_report"]["warnings"].append(
                "tampered-after-persistence"
            )
            store.update_run(
                record.run_id,
                state=record.state,
                metadata=metadata,
                updated_at="2026-09-24T01:11:00Z",
            )

            replay_calls: list[str] = []
            replay = IdempotentOfflineProductSpineService(
                service=_offline_service(replay_calls),
                store=LocalMetadataStore(db),
            )
            with self.assertRaises(
                OfflineProductSpineError
            ) as caught:
                _execute(
                    replay,
                    work=work,
                    attempt=attempt,
                )

            self.assertEqual(
                caught.exception.code,
                "persisted_state_corrupt",
            )
            self.assertEqual(replay_calls, [])

    def test_local_candidate_root_is_not_semantic_request_identity(self):
        work = _work_unit()
        one = _attempt(work, Path("/tmp/one"))
        two = _attempt(work, Path("/different/mount/two"))

        first = offline_idempotency_request_digest(
            project_id="MSKazemi/idkmesh",
            work_unit=work,
            source_revision=SOURCE,
            routing_decision=_routing(),
            connectors=[_connector()],
            attempts=[one],
        )
        second = offline_idempotency_request_digest(
            project_id="MSKazemi/idkmesh",
            work_unit=work,
            source_revision=SOURCE,
            routing_decision=_routing(),
            connectors=[_connector()],
            attempts=[two],
        )

        self.assertEqual(first, second)

        changed = _attempt(
            work,
            Path("/tmp/one"),
            reference_digest_byte="d",
        )
        third = offline_idempotency_request_digest(
            project_id="MSKazemi/idkmesh",
            work_unit=work,
            source_revision=SOURCE,
            routing_decision=_routing(),
            connectors=[_connector()],
            attempts=[changed],
        )
        self.assertNotEqual(first, third)


if __name__ == "__main__":
    unittest.main()
