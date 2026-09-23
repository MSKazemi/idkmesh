"""Tests for the pure Product Spine lifecycle core."""

from __future__ import annotations

from copy import deepcopy
import unittest

from idkmesh.product_spine import (
    AttemptProjection,
    ProductSpineError,
    ProductSpineRun,
    projection_from_mapping,
    transition_attempt_state,
    transition_run_state,
)

SOURCE = "0123456789abcdef0123456789abcdef01234567"
REQUEST_DIGEST = "sha256:" + "1" * 64
WORK_UNIT_DIGEST = "sha256:" + "2" * 64
CANDIDATE_DIGEST = "sha256:" + "3" * 64
RESULT_DIGEST = "sha256:" + "4" * 64
VERIFICATION_DIGEST = "sha256:" + "5" * 64
EVIDENCE_DIGEST = "sha256:" + "6" * 64
DECISION_DIGEST = "sha256:" + "7" * 64


def _run(*, authority_mode: str = "agent_candidate") -> ProductSpineRun:
    return ProductSpineRun(
        run_id="run-001",
        request_digest=REQUEST_DIGEST,
        project_id="MSKazemi/idkmesh",
        work_unit_id="test/product-spine",
        work_unit_version=1,
        work_unit_digest=WORK_UNIT_DIGEST,
        source_revision=SOURCE,
        authority_mode=authority_mode,
        routing_policy_version="routing-v1",
    )


class ProductSpineLifecycleTests(unittest.TestCase):
    def test_happy_path_reaches_decided_without_write_authority(self) -> None:
        run = _run()
        run = run.transition("previewed")
        run = run.transition(
            "admitted",
            admitted_connectors=("fake-agent",),
        )

        attempt = AttemptProjection(
            attempt_id="attempt-1",
            order=1,
            connector_id="fake-agent",
        )
        run = run.append_attempt(attempt)
        run = run.transition("dispatched")

        attempt = attempt.transition(
            "dispatched",
            provider_reference="fake://attempt-1",
        )
        run = run.replace_attempt(attempt)

        attempt = attempt.transition(
            "candidate_observed",
            candidate_reference_digest=CANDIDATE_DIGEST,
        )
        run = run.replace_attempt(attempt)
        run = run.transition("candidate_observed")

        attempt = attempt.transition(
            "normalized",
            result_manifest_digest=RESULT_DIGEST,
        )
        run = run.replace_attempt(attempt)
        run = run.transition("normalized")

        attempt = attempt.transition("verification_requested")
        run = run.replace_attempt(attempt)
        run = run.transition("verification_requested")

        attempt = attempt.transition(
            "verified",
            verification_semantic_digest=VERIFICATION_DIGEST,
        )
        run = run.replace_attempt(attempt)

        run = run.transition(
            "evidence_ready",
            evidence_report_digest=EVIDENCE_DIGEST,
        )
        run = run.transition("awaiting_human_decision")
        run = run.transition(
            "decided",
            human_decision_record_digest=DECISION_DIGEST,
        )

        self.assertEqual(run.state, "decided")
        self.assertEqual(run.attempts[0].state, "verified")
        self.assertEqual(
            run.to_dict()["authority"],
            {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
            },
        )

    def test_round_trip_projection_is_deterministic(self) -> None:
        run = _run().transition("previewed").transition(
            "admitted",
            admitted_connectors=("fake-agent",),
        )
        run = run.append_attempt(
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="fake-agent",
            )
        )

        encoded = run.to_dict()
        decoded = projection_from_mapping(deepcopy(encoded))

        self.assertEqual(decoded, run)
        self.assertEqual(decoded.to_dict(), encoded)

    def test_human_required_work_cannot_enter_automatic_admission(self) -> None:
        run = _run(authority_mode="human_required").transition("previewed")

        with self.assertRaises(ProductSpineError) as caught:
            run.transition(
                "admitted",
                admitted_connectors=("fake-agent",),
            )

        self.assertEqual(caught.exception.code, "human_authority_required")

        blocked = run.transition("admission_blocked")
        self.assertEqual(blocked.state, "admission_blocked")

    def test_admission_blocked_cannot_dispatch(self) -> None:
        run = _run().transition("previewed").transition(
            "admission_blocked"
        )

        with self.assertRaises(ProductSpineError) as caught:
            run.transition("dispatched")

        self.assertEqual(caught.exception.code, "invalid_run_transition")

    def test_failed_attempt_is_retained_and_retry_gets_new_identity(self) -> None:
        run = _run().transition("previewed").transition(
            "admitted",
            admitted_connectors=("fake-agent",),
        )
        first = AttemptProjection(
            attempt_id="attempt-1",
            order=1,
            connector_id="fake-agent",
        ).transition(
            "dispatched",
            provider_reference="fake://attempt-1",
        )
        run = run.append_attempt(first).transition("dispatched")

        failed = first.transition(
            "worker_error",
            error_code="fake_worker_failed",
        )
        run = run.replace_attempt(failed).transition("attempt_failed")

        second = AttemptProjection(
            attempt_id="attempt-2",
            order=2,
            connector_id="fake-agent",
        )
        run = run.append_attempt(second).transition("dispatched")

        self.assertEqual(
            [item.attempt_id for item in run.attempts],
            ["attempt-1", "attempt-2"],
        )
        self.assertEqual(run.attempts[0].state, "worker_error")
        self.assertEqual(run.attempts[1].state, "created")

    def test_attempt_failure_cannot_claim_success_evidence(self) -> None:
        with self.assertRaises(ProductSpineError) as caught:
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="fake-agent",
                state="worker_error",
                error_code="failed",
                result_manifest_digest=RESULT_DIGEST,
            )

        self.assertEqual(caught.exception.code, "invalid_attempt_evidence")

    def test_verified_attempt_requires_all_binding_digests(self) -> None:
        with self.assertRaises(ProductSpineError):
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="fake-agent",
                state="verified",
                candidate_reference_digest=CANDIDATE_DIGEST,
                result_manifest_digest=RESULT_DIGEST,
            )

        verified = AttemptProjection(
            attempt_id="attempt-1",
            order=1,
            connector_id="fake-agent",
            state="verified",
            candidate_reference_digest=CANDIDATE_DIGEST,
            result_manifest_digest=RESULT_DIGEST,
            verification_semantic_digest=VERIFICATION_DIGEST,
        )
        self.assertEqual(verified.state, "verified")

    def test_attempts_require_admission_and_admitted_connector(self) -> None:
        attempt = AttemptProjection(
            attempt_id="attempt-1",
            order=1,
            connector_id="fake-agent",
        )

        with self.assertRaises(ProductSpineError) as pre_admission:
            _run().append_attempt(attempt)
        self.assertEqual(pre_admission.exception.code, "attempt_not_admitted")

        run = _run().transition("previewed").transition(
            "admitted",
            admitted_connectors=("other-agent",),
        )
        with self.assertRaises(ProductSpineError) as wrong_connector:
            run.append_attempt(attempt)
        self.assertEqual(
            wrong_connector.exception.code,
            "connector_not_admitted",
        )

    def test_illegal_reverse_transitions_fail_closed(self) -> None:
        with self.assertRaises(ProductSpineError) as run_error:
            transition_run_state("admitted", "previewed")
        self.assertEqual(run_error.exception.code, "invalid_run_transition")

        with self.assertRaises(ProductSpineError) as attempt_error:
            transition_attempt_state("verified", "dispatched")
        self.assertEqual(
            attempt_error.exception.code,
            "invalid_attempt_transition",
        )

    def test_decided_requires_evidence_and_human_decision_digest(self) -> None:
        with self.assertRaises(ProductSpineError):
            ProductSpineRun(
                run_id="run-001",
                request_digest=REQUEST_DIGEST,
                project_id="MSKazemi/idkmesh",
                work_unit_id="test/product-spine",
                work_unit_version=1,
                work_unit_digest=WORK_UNIT_DIGEST,
                source_revision=SOURCE,
                authority_mode="agent_candidate",
                routing_policy_version="routing-v1",
                state="decided",
                admitted_connectors=("fake-agent",),
            )

    def test_projection_parser_rejects_authority_broadening(self) -> None:
        encoded = _run().to_dict()
        encoded["authority"]["merge"] = True

        with self.assertRaises(ProductSpineError) as caught:
            projection_from_mapping(encoded)

        self.assertEqual(caught.exception.code, "authority_violation")

    def test_exact_source_revision_and_authority_mode_are_required(self) -> None:
        with self.assertRaises(ProductSpineError) as bad_revision:
            ProductSpineRun(
                run_id="run-001",
                request_digest=REQUEST_DIGEST,
                project_id="MSKazemi/idkmesh",
                work_unit_id="test/product-spine",
                work_unit_version=1,
                work_unit_digest=WORK_UNIT_DIGEST,
                source_revision="main",
                authority_mode="agent_candidate",
                routing_policy_version="routing-v1",
            )
        self.assertEqual(
            bad_revision.exception.code,
            "invalid_source_revision",
        )

        with self.assertRaises(ProductSpineError) as bad_authority:
            _run(authority_mode="super_model")
        self.assertEqual(
            bad_authority.exception.code,
            "invalid_authority_mode",
        )


if __name__ == "__main__":
    unittest.main()
