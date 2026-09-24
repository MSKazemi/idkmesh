"""Deterministic end-to-end tests for the offline Product Spine service."""

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

import evaluator_plan_runner  # noqa: E402
import record_human_decision  # noqa: E402
import run_evidence_report  # noqa: E402


SOURCE = "0123456789abcdef0123456789abcdef01234567"
STARTED = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
FINISHED = datetime(2026, 9, 24, 0, 0, 1, tzinfo=timezone.utc)


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
    work["provenance"]["source"] = "offline-product-spine-fixture"
    return work


def _connector(*, tier: str = "T2") -> ConnectorProfile:
    return ConnectorProfile(
        connection_id="fake-agent",
        kind="agent",
        driver="offline-fake",
        capability_tiers=frozenset({tier}),
        max_risk="low",
        external_processing=False,
        project_cost_usd=0.0,
    )


def _routing(
    *,
    tier: str = "T1",
    authority_mode: str = "agent_candidate",
) -> RoutingDecision:
    return RoutingDecision(
        required_capability_tier=tier,
        authority_mode=authority_mode,
        risk_class="low",
        external_processing_allowed=False,
        project_spend_usd_max=0.0,
        independent_reviewer_required=True,
    )


def _write_candidate(
    root: Path,
    work_unit: dict,
    *,
    attempt_id: str,
    digest_byte: str = "a",
    source_revision: str = SOURCE,
    work_unit_digest: str | None = None,
) -> ObservedCandidate:
    candidate_root = root / attempt_id
    candidate_root.mkdir(parents=True, exist_ok=True)
    reference = ArtifactBundleCandidateReference(
        locator="candidate.json",
        digest="sha256:" + digest_byte * 64,
        media_type="application/json",
    )
    payload = json.dumps(
        reference.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    (candidate_root / "candidate.json").write_bytes(payload)
    return ObservedCandidate(
        reference=reference,
        candidate_root=candidate_root,
        attempt_id=attempt_id,
        work_unit_digest=(
            work_unit_digest
            if work_unit_digest is not None
            else canonical_digest(work_unit)
        ),
        source_revision=source_revision,
    )


def _attempt(candidate: ObservedCandidate) -> OfflineAttemptSpec:
    return OfflineAttemptSpec(
        attempt_id=candidate.attempt_id,
        outcome="candidate",
        started_at=STARTED,
        finished_at=FINISHED,
        candidate=candidate,
    )


def _worker_error(attempt_id: str) -> OfflineAttemptSpec:
    return OfflineAttemptSpec(
        attempt_id=attempt_id,
        outcome="worker_error",
        started_at=STARTED,
        finished_at=FINISHED,
        error_code="fake_worker_failed",
    )


def _service(
    plan_root: Path,
    verifier_calls: list[str],
) -> OfflineProductSpineService:
    base_plan = json.loads(
        (
            ROOT
            / "verification"
            / "fixtures"
            / "verifier-smoke-evaluator-plan.json"
        ).read_text(encoding="utf-8")
    )

    def verifier(
        *,
        work_unit,
        result_manifest,
        handoff,
        candidate,
    ):
        verifier_calls.append(candidate.attempt_id)
        plan = deepcopy(base_plan)
        plan["binding"] = handoff.evaluator_binding()
        plan["required_validator_ids"] = list(
            handoff.required_validator_ids
        )
        plan["candidate_artifact_id"] = handoff.candidate_artifact_id
        plan["required_json"] = candidate.reference.to_dict()
        plan["allowed_files"] = ["candidate.json"]
        plan_path = plan_root / f"{candidate.attempt_id}-evaluator-plan.json"
        plan_path.write_text(
            json.dumps(plan, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return evaluator_plan_runner.verify_with_plan(
            work_unit=work_unit,
            worker_result=result_manifest,
            plan=plan,
            candidate_root=candidate.candidate_root,
            plan_path=plan_path,
        )

    return OfflineProductSpineService(
        verifier=verifier,
        evidence_builder=run_evidence_report.build_report,
        decision_builder=record_human_decision.build_decision_record,
        decision_binding_verifier=record_human_decision.verify_binding,
    )


class OfflineProductSpineTests(unittest.TestCase):
    def test_supported_candidate_reaches_pending_then_bound_human_decision(self):
        work = _work_unit()
        calls: list[str] = []

        with tempfile.TemporaryDirectory(prefix="idkmesh-product-spine-") as raw:
            root = Path(raw)
            candidate = _write_candidate(
                root / "candidate-roots",
                work,
                attempt_id="attempt-1",
            )
            service = _service(root / "plans", calls)
            (root / "plans").mkdir()

            result = service.execute(
                project_id="MSKazemi/idkmesh",
                run_id="offline/run-a",
                work_unit=work,
                source_revision=SOURCE,
                routing_decision=_routing(),
                connectors=[_connector()],
                attempts=[_attempt(candidate)],
            )

            self.assertEqual(result.run.state, "awaiting_human_decision")
            self.assertEqual(
                result.route.selected_connection_id,
                "fake-agent",
            )
            self.assertEqual(calls, ["attempt-1"])
            self.assertEqual(len(result.result_manifests), 1)
            self.assertEqual(
                result.verifications[0]["status"],
                "passed",
            )
            self.assertEqual(
                result.verifications[0]["decision_support"][
                    "recommendation"
                ],
                "accept_candidate",
            )
            self.assertIsNotNone(result.evidence_report)
            assert result.evidence_report is not None
            self.assertEqual(
                result.evidence_report["summary"]["supported"],
                1,
            )
            self.assertEqual(
                result.evidence_report["human_decision"]["status"],
                "pending",
            )
            self.assertFalse(
                result.evidence_report["authority"]["merge"]
            )

            decided = service.record_human_decision(
                result,
                decision_id="decision-offline-a",
                decision="accept",
                rationale="Fixture evidence reviewed.",
                decider_id="human/reviewer-1",
                decider_type="human",
                decided_at="2026-09-24T00:05:00Z",
                selected_attempt_id="attempt-1",
            )

            self.assertEqual(decided.run.state, "decided")
            self.assertIsNotNone(decided.human_decision_record)
            assert decided.human_decision_record is not None
            self.assertFalse(
                decided.human_decision_record["authority"]["merge"]
            )
            record_human_decision.verify_binding(
                decided.human_decision_record,
                result.evidence_report,
            )

    def test_worker_failure_is_retained_while_peer_candidate_is_verified(self):
        work = _work_unit()
        calls: list[str] = []

        with tempfile.TemporaryDirectory(prefix="idkmesh-product-spine-") as raw:
            root = Path(raw)
            (root / "plans").mkdir()
            candidate = _write_candidate(
                root / "candidate-roots",
                work,
                attempt_id="attempt-2",
                digest_byte="b",
            )
            service = _service(root / "plans", calls)

            result = service.execute(
                project_id="MSKazemi/idkmesh",
                run_id="offline/run-b",
                work_unit=work,
                source_revision=SOURCE,
                routing_decision=_routing(),
                connectors=[_connector()],
                attempts=[
                    _worker_error("attempt-1"),
                    _attempt(candidate),
                ],
            )

            self.assertEqual(calls, ["attempt-2"])
            self.assertEqual(
                [attempt.state for attempt in result.run.attempts],
                ["worker_error", "verified"],
            )
            self.assertIsNotNone(result.evidence_report)
            assert result.evidence_report is not None
            self.assertEqual(
                result.evidence_report["summary"]["attempt_count"],
                2,
            )
            self.assertEqual(
                result.evidence_report["summary"]["control_errors"],
                1,
            )
            self.assertEqual(
                result.evidence_report["summary"]["supported"],
                1,
            )
            self.assertEqual(
                result.evidence_report["attempts"][0]["evidence_state"],
                "worker_error",
            )
            self.assertEqual(
                result.evidence_report["attempts"][1]["evidence_state"],
                "supported",
            )

    def test_candidate_binding_mismatch_fails_before_verifier(self):
        work = _work_unit()

        for label, candidate_overrides in (
            (
                "wrong-source",
                {
                    "source_revision": (
                        "1123456789abcdef0123456789abcdef01234567"
                    )
                },
            ),
            (
                "wrong-work-unit",
                {"work_unit_digest": "sha256:" + "0" * 64},
            ),
        ):
            with self.subTest(label=label):
                calls: list[str] = []
                with tempfile.TemporaryDirectory(
                    prefix="idkmesh-product-spine-"
                ) as raw:
                    root = Path(raw)
                    (root / "plans").mkdir()
                    candidate = _write_candidate(
                        root / "candidate-roots",
                        work,
                        attempt_id="attempt-1",
                        **candidate_overrides,
                    )
                    service = _service(root / "plans", calls)

                    with self.assertRaises(
                        OfflineProductSpineError
                    ) as caught:
                        service.execute(
                            project_id="MSKazemi/idkmesh",
                            run_id=f"offline/{label}",
                            work_unit=work,
                            source_revision=SOURCE,
                            routing_decision=_routing(),
                            connectors=[_connector()],
                            attempts=[_attempt(candidate)],
                        )

                    self.assertEqual(
                        caught.exception.code,
                        "candidate_binding_mismatch",
                    )
                    self.assertEqual(calls, [])

    def test_human_required_blocks_even_peak_capability_connector(self):
        work = _work_unit()
        calls: list[str] = []

        with tempfile.TemporaryDirectory(prefix="idkmesh-product-spine-") as raw:
            root = Path(raw)
            (root / "plans").mkdir()
            service = _service(root / "plans", calls)

            result = service.execute(
                project_id="MSKazemi/idkmesh",
                run_id="offline/run-human",
                work_unit=work,
                source_revision=SOURCE,
                routing_decision=_routing(
                    tier="T4",
                    authority_mode="human_required",
                ),
                connectors=[_connector(tier="T4")],
                attempts=[],
            )

            self.assertEqual(result.run.state, "admission_blocked")
            self.assertIsNone(result.route.selected_connection_id)
            self.assertEqual(calls, [])
            self.assertEqual(result.run.attempts, ())
            self.assertIsNone(result.evidence_report)
            reasons = {
                reason
                for rejected in result.route.ineligible
                for reason in rejected.reasons
            }
            self.assertIn("human_required", reasons)

    def test_same_offline_inputs_replay_to_same_semantic_state(self):
        work = _work_unit()
        calls: list[str] = []

        with tempfile.TemporaryDirectory(prefix="idkmesh-product-spine-") as raw:
            root = Path(raw)
            (root / "plans").mkdir()
            candidate = _write_candidate(
                root / "candidate-roots",
                work,
                attempt_id="attempt-1",
                digest_byte="c",
            )
            service = _service(root / "plans", calls)
            kwargs = {
                "project_id": "MSKazemi/idkmesh",
                "run_id": "offline/run-replay",
                "work_unit": work,
                "source_revision": SOURCE,
                "routing_decision": _routing(),
                "connectors": [_connector()],
                "attempts": [_attempt(candidate)],
            }

            first = service.execute(**kwargs)
            second = service.execute(**kwargs)

            self.assertEqual(first.run.to_dict(), second.run.to_dict())
            self.assertEqual(
                first.source_run_record,
                second.source_run_record,
            )
            self.assertEqual(
                first.evidence_report,
                second.evidence_report,
            )
            self.assertEqual(calls, ["attempt-1", "attempt-1"])


if __name__ == "__main__":
    unittest.main()
