"""Deterministic offline Product Spine composition.

This module composes the pure Product Spine lifecycle with existing canonical
IDKMesh contracts while keeping provider, network, GitHub, and merge behavior
out of scope.

The service owns orchestration only. Verification, evidence reporting, and
human-decision construction are injected so the package does not depend on the
repository's experiments directory or gain those authorities itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    CandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.connector_routing import (
    ConnectorProfile,
    RouteResolution,
    RoutingDecision,
    resolve_routes,
)
from idkmesh.product_spine import AttemptProjection, ProductSpineError, ProductSpineRun
from idkmesh.result_manifest_builder import (
    ResourceUsage,
    ResultManifestBuildError,
    WorkerIdentity,
    build_result_manifest,
)
from idkmesh.verification_handoff import (
    VerificationHandoff,
    VerificationHandoffError,
    prepare_verification_handoff,
)
from idkmesh.work_unit_binding import (
    WorkUnitBindingError,
    WorkUnitSourceBinding,
    bind_work_unit_source,
    canonical_digest,
)


ORCHESTRATOR_VERSION = "product-spine-offline-v0.1"


class OfflineProductSpineError(ProductSpineError):
    """Fail-closed error raised by the deterministic offline composition."""


class OfflineVerifier(Protocol):
    def __call__(
        self,
        *,
        work_unit: dict[str, Any],
        result_manifest: dict[str, Any],
        handoff: VerificationHandoff,
        candidate: "ObservedCandidate",
    ) -> dict[str, Any]: ...


EvidenceBuilder = Callable[[dict[str, Any]], dict[str, Any]]
DecisionBuilder = Callable[..., dict[str, Any]]
DecisionBindingVerifier = Callable[[dict[str, Any], dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class ObservedCandidate:
    """Fake-provider observation bound to the exact admitted attempt.

    CandidateReference remains the canonical candidate identity. The extra
    fields here are operational bindings required before normalization.
    """

    reference: CandidateReference
    candidate_root: Path
    attempt_id: str
    work_unit_digest: str
    source_revision: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.reference,
            (
                ArtifactBundleCandidateReference,
                GitHubPullRequestCandidateReference,
            ),
        ):
            raise OfflineProductSpineError(
                "invalid_candidate_reference",
                "reference",
                "must be CandidateReference v0.1",
            )
        if not isinstance(self.candidate_root, Path):
            raise OfflineProductSpineError(
                "invalid_candidate_root",
                "candidate_root",
                "must be pathlib.Path",
            )
        for value, field in (
            (self.attempt_id, "attempt_id"),
            (self.work_unit_digest, "work_unit_digest"),
            (self.source_revision, "source_revision"),
        ):
            if not isinstance(value, str) or not value:
                raise OfflineProductSpineError(
                    "invalid_candidate_binding",
                    field,
                    "must be a non-empty string",
                )


@dataclass(frozen=True, slots=True)
class OfflineAttemptSpec:
    """One deterministic fake-worker attempt."""

    attempt_id: str
    outcome: str
    started_at: datetime
    finished_at: datetime
    worker_id: str = "offline/fake-worker"
    worker_adapter: str = "offline-fake"
    artifact_id: str = "candidate-result"
    candidate: ObservedCandidate | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or not self.attempt_id:
            raise OfflineProductSpineError(
                "invalid_attempt",
                "attempt_id",
                "must be a non-empty string",
            )
        if self.outcome not in {"candidate", "worker_error"}:
            raise OfflineProductSpineError(
                "invalid_attempt",
                "outcome",
                "must be candidate or worker_error",
            )
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise OfflineProductSpineError(
                "invalid_attempt",
                "started_at",
                "must be timezone-aware",
            )
        if not isinstance(self.finished_at, datetime) or self.finished_at.tzinfo is None:
            raise OfflineProductSpineError(
                "invalid_attempt",
                "finished_at",
                "must be timezone-aware",
            )
        if self.finished_at < self.started_at:
            raise OfflineProductSpineError(
                "invalid_attempt",
                "finished_at",
                "must not precede started_at",
            )
        for value, field in (
            (self.worker_id, "worker_id"),
            (self.worker_adapter, "worker_adapter"),
            (self.artifact_id, "artifact_id"),
        ):
            if not isinstance(value, str) or not value:
                raise OfflineProductSpineError(
                    "invalid_attempt",
                    field,
                    "must be a non-empty string",
                )

        if self.outcome == "candidate":
            if self.candidate is None or self.error_code is not None:
                raise OfflineProductSpineError(
                    "invalid_attempt",
                    "outcome",
                    "candidate outcome requires candidate and forbids error_code",
                )
        else:
            if self.candidate is not None or not self.error_code:
                raise OfflineProductSpineError(
                    "invalid_attempt",
                    "outcome",
                    "worker_error requires error_code and forbids candidate",
                )


@dataclass(frozen=True, slots=True)
class OfflineProductSpineResult:
    """Replay-friendly result of one deterministic offline orchestration."""

    run: ProductSpineRun
    binding: WorkUnitSourceBinding
    route: RouteResolution
    result_manifests: tuple[dict[str, Any], ...] = ()
    verifications: tuple[dict[str, Any], ...] = ()
    source_run_record: dict[str, Any] | None = None
    evidence_report: dict[str, Any] | None = None
    human_decision_record: dict[str, Any] | None = None


def _routing_request(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "required_capability_tier": decision.required_capability_tier,
        "authority_mode": decision.authority_mode,
        "risk_class": decision.risk_class,
        "task_classes": sorted(decision.task_classes),
        "required_tools": sorted(decision.required_tools),
        "allowed_connector_kinds": sorted(decision.allowed_connector_kinds),
        "external_processing_allowed": decision.external_processing_allowed,
        "project_spend_usd_max": decision.project_spend_usd_max,
        "human_gate_satisfied": decision.human_gate_satisfied,
        "prefer_zero_cost": decision.prefer_zero_cost,
        "avoid_provider_families": sorted(decision.avoid_provider_families),
        "independent_reviewer_required": decision.independent_reviewer_required,
    }


def _request_digest(
    *,
    project_id: str,
    binding: WorkUnitSourceBinding,
    decision: RoutingDecision,
) -> str:
    return canonical_digest(
        {
            "project_id": project_id,
            "work_unit": binding.to_dict(),
            "routing": _routing_request(decision),
        }
    )


def _candidate_reference_digest(candidate: ObservedCandidate) -> str:
    return canonical_digest(candidate.reference.to_dict())


def _validate_candidate_binding(
    candidate: ObservedCandidate,
    *,
    binding: WorkUnitSourceBinding,
    attempt_id: str,
) -> None:
    if candidate.attempt_id != attempt_id:
        raise OfflineProductSpineError(
            "candidate_binding_mismatch",
            "candidate.attempt_id",
            "candidate belongs to a different attempt",
        )
    if candidate.work_unit_digest != binding.work_unit_digest:
        raise OfflineProductSpineError(
            "candidate_binding_mismatch",
            "candidate.work_unit_digest",
            "candidate belongs to different WorkUnit content",
        )
    if candidate.source_revision.lower() != binding.source_revision:
        raise OfflineProductSpineError(
            "candidate_binding_mismatch",
            "candidate.source_revision",
            "candidate belongs to a different source revision",
        )


def _verification_signature(verification: Mapping[str, Any]) -> dict[str, Any]:
    checks = verification.get("checks")
    evidence = verification.get("evidence")
    decision_support = verification.get("decision_support")
    if (
        not isinstance(checks, list)
        or not isinstance(evidence, list)
        or not isinstance(decision_support, Mapping)
    ):
        raise OfflineProductSpineError(
            "invalid_verification",
            "verification",
            "missing checks/evidence/decision_support",
        )
    return {
        "status": verification.get("status"),
        "checks": [
            (
                check.get("id"),
                check.get("status"),
                tuple(check.get("evidence_ids", [])),
            )
            for check in checks
            if isinstance(check, Mapping)
        ],
        "evidence": [
            (item.get("id"), item.get("digest"))
            for item in evidence
            if isinstance(item, Mapping)
        ],
        "recommendation": decision_support.get("recommendation"),
    }


def _result_manifest_record(result: Mapping[str, Any]) -> dict[str, Any]:
    worker = result.get("worker")
    if not isinstance(worker, Mapping):
        raise OfflineProductSpineError(
            "invalid_result_manifest",
            "worker",
            "must be an object",
        )
    return {
        "id": result["id"],
        "attempt": result["attempt"],
        "worker_id": worker["id"],
        "worker_status": result["status"],
        "digest": canonical_digest(result),
    }


def _verification_record(verification: Mapping[str, Any]) -> dict[str, Any]:
    verifier = verification.get("verifier")
    provenance = verification.get("provenance")
    decision_support = verification.get("decision_support")
    checks = verification.get("checks")
    if not all(
        isinstance(value, Mapping)
        for value in (verifier, provenance, decision_support)
    ) or not isinstance(checks, list):
        raise OfflineProductSpineError(
            "invalid_verification",
            "verification",
            "missing verifier/provenance/decision_support/checks",
        )

    signature = _verification_signature(verification)
    return {
        "id": verification["id"],
        "verifier_id": verifier["id"],
        "status": verification["status"],
        "recommendation": decision_support["recommendation"],
        "checks": [
            {
                "id": check["id"],
                "status": check["status"],
                "required": check["required"],
            }
            for check in checks
        ],
        "semantic_digest": canonical_digest(signature),
        "work_unit_digest": provenance["work_unit_digest"],
        "result_manifest_digest": provenance["result_manifest_digest"],
    }


class OfflineProductSpineService:
    """Provider-neutral deterministic orchestration for the #684 offline proof."""

    def __init__(
        self,
        *,
        verifier: OfflineVerifier,
        evidence_builder: EvidenceBuilder,
        decision_builder: DecisionBuilder | None = None,
        decision_binding_verifier: DecisionBindingVerifier | None = None,
    ) -> None:
        self._verifier = verifier
        self._evidence_builder = evidence_builder
        self._decision_builder = decision_builder
        self._decision_binding_verifier = decision_binding_verifier

    def execute(
        self,
        *,
        project_id: str,
        run_id: str,
        work_unit: dict[str, Any],
        source_revision: str,
        routing_decision: RoutingDecision,
        connectors: Iterable[ConnectorProfile],
        attempts: Sequence[OfflineAttemptSpec],
    ) -> OfflineProductSpineResult:
        """Run the deterministic offline lifecycle until human decision is pending."""

        try:
            binding = bind_work_unit_source(
                work_unit,
                source_revision=source_revision,
            )
        except WorkUnitBindingError as exc:
            raise OfflineProductSpineError(
                "work_unit_binding_failed",
                "work_unit",
                str(exc),
            ) from exc

        route = resolve_routes(
            routing_decision,
            tuple(connectors),
            auto_select=True,
        )
        run = ProductSpineRun(
            run_id=run_id,
            request_digest=_request_digest(
                project_id=project_id,
                binding=binding,
                decision=routing_decision,
            ),
            project_id=project_id,
            work_unit_id=binding.work_unit_id,
            work_unit_version=binding.work_unit_version,
            work_unit_digest=binding.work_unit_digest,
            source_revision=binding.source_revision,
            authority_mode=routing_decision.authority_mode,
            routing_policy_version="connector-routing-v0.1",
        ).transition("previewed")

        selected = route.selected_connection_id
        if selected is None:
            return OfflineProductSpineResult(
                run=run.transition("admission_blocked"),
                binding=binding,
                route=route,
            )

        run = run.transition(
            "admitted",
            admitted_connectors=(selected,),
        )

        if not attempts:
            raise OfflineProductSpineError(
                "missing_attempt",
                "attempts",
                "at least one offline attempt is required after admission",
            )

        attempt_records: list[dict[str, Any]] = []
        manifests: list[dict[str, Any]] = []
        verifications: list[dict[str, Any]] = []
        verified = False

        for index, spec in enumerate(attempts):
            projection = AttemptProjection(
                attempt_id=spec.attempt_id,
                order=index + 1,
                connector_id=selected,
            )
            run = run.append_attempt(projection)
            run = run.transition("dispatched")
            projection = projection.transition(
                "dispatched",
                provider_reference=f"offline://{selected}/{spec.attempt_id}",
            )
            run = run.replace_attempt(projection)

            base_record = {
                "attempt_id": spec.attempt_id,
                "order": index + 1,
                "worker_adapter": spec.worker_adapter,
            }

            if spec.outcome == "worker_error":
                projection = projection.transition(
                    "worker_error",
                    error_code=spec.error_code,
                )
                run = run.replace_attempt(projection).transition(
                    "attempt_failed"
                )
                attempt_records.append(
                    {
                        **base_record,
                        "state": "worker_error",
                        "error": spec.error_code,
                        "result_manifest": None,
                        "verification": None,
                    }
                )
                continue

            if index != len(attempts) - 1:
                raise OfflineProductSpineError(
                    "invalid_attempt_sequence",
                    f"attempts[{index}]",
                    "a successful candidate must be the final offline attempt",
                )

            assert spec.candidate is not None
            candidate = spec.candidate
            _validate_candidate_binding(
                candidate,
                binding=binding,
                attempt_id=spec.attempt_id,
            )
            candidate_digest = _candidate_reference_digest(candidate)
            projection = projection.transition(
                "candidate_observed",
                candidate_reference_digest=candidate_digest,
            )
            run = run.replace_attempt(projection).transition(
                "candidate_observed"
            )

            duration = (
                spec.finished_at - spec.started_at
            ).total_seconds()
            manifest_id = (
                "product-spine/"
                + canonical_digest(
                    {
                        "run_id": run_id,
                        "attempt_id": spec.attempt_id,
                    }
                )[7:31]
            )
            try:
                manifest = build_result_manifest(
                    work_unit,
                    binding,
                    candidate.reference,
                    manifest_id=manifest_id,
                    attempt=index + 1,
                    worker=WorkerIdentity(
                        id=spec.worker_id,
                        type="system",
                        adapter=spec.worker_adapter,
                        adapter_version="offline-v0.1",
                    ),
                    status="succeeded",
                    started_at=spec.started_at,
                    finished_at=spec.finished_at,
                    resources=ResourceUsage(wall_seconds=duration),
                    artifact_id=spec.artifact_id,
                    verification_notes=(
                        "Deterministic offline Product Spine candidate; "
                        "independent verification is still required."
                    ),
                )
                handoff = prepare_verification_handoff(
                    work_unit,
                    manifest,
                    candidate_artifact_id=spec.artifact_id,
                )
            except (
                ResultManifestBuildError,
                VerificationHandoffError,
            ) as exc:
                projection = projection.transition(
                    "normalization_error",
                    error_code="normalization_failed",
                )
                run = run.replace_attempt(projection)
                raise OfflineProductSpineError(
                    "normalization_failed",
                    "candidate",
                    str(exc),
                ) from exc

            manifest_digest = canonical_digest(manifest)
            projection = projection.transition(
                "normalized",
                result_manifest_digest=manifest_digest,
            )
            run = run.replace_attempt(projection).transition("normalized")

            projection = projection.transition("verification_requested")
            run = run.replace_attempt(projection).transition(
                "verification_requested"
            )
            verification = self._verifier(
                work_unit=work_unit,
                result_manifest=manifest,
                handoff=handoff,
                candidate=candidate,
            )
            verification_record = _verification_record(verification)
            projection = projection.transition(
                "verified",
                verification_semantic_digest=verification_record[
                    "semantic_digest"
                ],
            )
            run = run.replace_attempt(projection)
            manifests.append(manifest)
            verifications.append(verification)
            attempt_records.append(
                {
                    **base_record,
                    "state": "verified",
                    "error": None,
                    "result_manifest": _result_manifest_record(manifest),
                    "verification": verification_record,
                }
            )
            verified = True

        if not verified:
            return OfflineProductSpineResult(
                run=run,
                binding=binding,
                route=route,
                result_manifests=tuple(manifests),
                verifications=tuple(verifications),
            )

        verifier_policy_digest = verifications[-1].get(
            "provenance", {}
        ).get("verifier_config_digest")
        if not isinstance(verifier_policy_digest, str):
            raise OfflineProductSpineError(
                "invalid_verification",
                "provenance.verifier_config_digest",
                "verification did not retain evaluator configuration digest",
            )

        source_record = {
            "schema_version": "0.1",
            "kind": "idkmesh-two-attempt-run",
            "run_id": run_id,
            "orchestrator_version": ORCHESTRATOR_VERSION,
            "config_digest": run.request_digest,
            "work_unit": {
                "id": binding.work_unit_id,
                "version": binding.work_unit_version,
                "digest": binding.work_unit_digest,
            },
            "verifier_policy_digest": verifier_policy_digest,
            "attempt_order": [
                record["attempt_id"] for record in attempt_records
            ],
            "attempts": attempt_records,
            "authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        }
        evidence_report = self._evidence_builder(source_record)
        evidence_digest = canonical_digest(evidence_report)
        run = run.transition(
            "evidence_ready",
            evidence_report_digest=evidence_digest,
        ).transition("awaiting_human_decision")

        return OfflineProductSpineResult(
            run=run,
            binding=binding,
            route=route,
            result_manifests=tuple(manifests),
            verifications=tuple(verifications),
            source_run_record=source_record,
            evidence_report=evidence_report,
        )

    def record_human_decision(
        self,
        result: OfflineProductSpineResult,
        *,
        decision_id: str,
        decision: str,
        rationale: str,
        decider_id: str,
        decider_type: str,
        decided_at: str,
        selected_attempt_id: str | None = None,
        decider_display_name: str | None = None,
    ) -> OfflineProductSpineResult:
        """Bind an explicit human decision to the exact evidence report.

        The injected decision builder may create a canonical Human Decision
        Record, but this method never performs Git or repository mutation.
        """

        if result.run.state != "awaiting_human_decision":
            raise OfflineProductSpineError(
                "decision_not_ready",
                "run.state",
                "human decision requires awaiting_human_decision",
            )
        if result.evidence_report is None:
            raise OfflineProductSpineError(
                "decision_not_ready",
                "evidence_report",
                "human decision requires retained evidence",
            )
        if self._decision_builder is None:
            raise OfflineProductSpineError(
                "decision_builder_unavailable",
                "decision",
                "no human decision builder was configured",
            )

        record = self._decision_builder(
            report=result.evidence_report,
            decision_id=decision_id,
            decision=decision,
            rationale=rationale,
            decider_id=decider_id,
            decider_type=decider_type,
            decider_display_name=decider_display_name,
            selected_attempt_id=selected_attempt_id,
            decided_at=decided_at,
        )
        if self._decision_binding_verifier is not None:
            self._decision_binding_verifier(
                record,
                result.evidence_report,
            )

        decided = result.run.transition(
            "decided",
            human_decision_record_digest=canonical_digest(record),
        )
        return replace(
            result,
            run=decided,
            human_decision_record=record,
        )
