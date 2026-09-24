"""Restart-safe local idempotency composition for the offline Product Spine.

This PS-C adapter reuses LocalMetadataStore. It prevents duplicate execution by
atomically reserving an idempotency key before the offline service runs.

The store is a local/reference control-plane store only. It is not the durable
multi-tenant ledger required for hosted production operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Any, Iterable, Mapping, Sequence

from idkmesh.connector_routing import ConnectorProfile, RoutingDecision
from idkmesh.connector_store import (
    LocalMetadataStore,
    LocalStoreConflict,
    RunRecord,
)
from idkmesh.product_spine import ProductSpineRun, projection_from_mapping
from idkmesh.product_spine_offline import (
    OfflineAttemptSpec,
    OfflineProductSpineError,
    OfflineProductSpineService,
)
from idkmesh.work_unit_binding import (
    WorkUnitBindingError,
    bind_work_unit_source,
    canonical_digest,
)


IDEMPOTENCY_SCHEMA_VERSION = "0.1"
_RESULT_KIND = "product-spine-idempotency-result"
_ADMISSION_KIND = "product-spine-idempotency-admission"


@dataclass(frozen=True, slots=True)
class PersistedOfflineProductSpineResult:
    """Compact replay result retained by the local idempotency adapter."""

    run: ProductSpineRun
    idempotency_key: str
    request_digest: str
    created: bool
    replayed: bool
    source_run_record: dict[str, Any] | None = None
    evidence_report: dict[str, Any] | None = None


def _utc_text(value) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _routing_payload(decision: RoutingDecision) -> dict[str, Any]:
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


def _connector_payload(profile: ConnectorProfile) -> dict[str, Any]:
    return {
        "connection_id": profile.connection_id,
        "kind": profile.kind,
        "driver": profile.driver,
        "enabled": profile.enabled,
        "health": profile.health,
        "capability_tiers": sorted(profile.capability_tiers),
        "task_classes": sorted(profile.task_classes),
        "tools": sorted(profile.tools),
        "max_risk": profile.max_risk,
        "external_processing": profile.external_processing,
        "project_cost_usd": profile.project_cost_usd,
        "secret_required": profile.secret_required,
        "secret_available": profile.secret_available,
        "capacity_available": profile.capacity_available,
        "provider_family": profile.provider_family,
        "agent_family": profile.agent_family,
        "execution_family": profile.execution_family,
    }


def _attempt_payload(spec: OfflineAttemptSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "attempt_id": spec.attempt_id,
        "outcome": spec.outcome,
        "started_at": _utc_text(spec.started_at),
        "finished_at": _utc_text(spec.finished_at),
        "worker_id": spec.worker_id,
        "worker_adapter": spec.worker_adapter,
        "artifact_id": spec.artifact_id,
        "error_code": spec.error_code,
    }
    if spec.candidate is not None:
        payload["candidate"] = {
            "reference": spec.candidate.reference.to_dict(),
            "attempt_id": spec.candidate.attempt_id,
            "work_unit_digest": spec.candidate.work_unit_digest,
            "source_revision": spec.candidate.source_revision.lower(),
        }
    else:
        payload["candidate"] = None
    return payload


def offline_idempotency_request_digest(
    *,
    project_id: str,
    work_unit: dict[str, Any],
    source_revision: str,
    routing_decision: RoutingDecision,
    connectors: Iterable[ConnectorProfile],
    attempts: Sequence[OfflineAttemptSpec],
) -> str:
    """Digest the complete deterministic offline admission/dispatch request.

    Candidate filesystem roots are deliberately excluded because they are local
    execution locations, not semantic request identity. CandidateReference and
    exact WorkUnit/source/attempt bindings remain included.
    """

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

    connector_payloads = sorted(
        (_connector_payload(item) for item in connectors),
        key=lambda item: item["connection_id"],
    )
    return canonical_digest(
        {
            "schema_version": IDEMPOTENCY_SCHEMA_VERSION,
            "project_id": project_id,
            "work_unit": binding.to_dict(),
            "routing": _routing_payload(routing_decision),
            "connectors": connector_payloads,
            "attempts": [_attempt_payload(item) for item in attempts],
        }
    )


def _run_id(idempotency_key: str, request_digest: str) -> str:
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise OfflineProductSpineError(
            "invalid_idempotency_key",
            "idempotency_key",
            "must be a non-empty string",
        )
    return (
        "offline/"
        + canonical_digest(
            {
                "idempotency_key": idempotency_key,
                "request_digest": request_digest,
            }
        )[7:31]
    )


def _result_metadata(result) -> dict[str, Any]:
    return {
        "schema_version": IDEMPOTENCY_SCHEMA_VERSION,
        "kind": _RESULT_KIND,
        "projection": result.run.to_dict(),
        "source_run_record": result.source_run_record,
        "evidence_report": result.evidence_report,
        "result_manifest_digests": [
            canonical_digest(item) for item in result.result_manifests
        ],
        "verification_result_digests": [
            canonical_digest(item) for item in result.verifications
        ],
    }


def _restore(
    record: RunRecord,
    *,
    idempotency_key: str,
) -> PersistedOfflineProductSpineResult:
    metadata = record.metadata
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("schema_version") != IDEMPOTENCY_SCHEMA_VERSION
        or metadata.get("kind") != _RESULT_KIND
    ):
        raise OfflineProductSpineError(
            "idempotency_recovery_required",
            "store",
            "request identity is retained but completed semantic state is not; "
            "refusing duplicate offline execution",
        )

    projection = metadata.get("projection")
    if not isinstance(projection, Mapping):
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.projection",
            "completed record is missing Product Spine projection",
        )

    try:
        run = projection_from_mapping(projection)
    except Exception as exc:
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.projection",
            str(exc),
        ) from exc

    if run.run_id != record.run_id:
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.run_id",
            "stored projection run id differs from idempotency record",
        )
    if run.request_digest != record.request_digest:
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.request_digest",
            "stored projection request digest differs from idempotency record",
        )
    if record.idempotency_key != idempotency_key:
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.idempotency_key",
            "stored idempotency key differs from replay request",
        )

    source_run_record = metadata.get("source_run_record")
    if source_run_record is not None and not isinstance(
        source_run_record, dict
    ):
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.source_run_record",
            "must be an object or null",
        )

    evidence_report = metadata.get("evidence_report")
    if evidence_report is not None and not isinstance(evidence_report, dict):
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.evidence_report",
            "must be an object or null",
        )

    if run.evidence_report_digest is not None:
        if evidence_report is None:
            raise OfflineProductSpineError(
                "persisted_state_corrupt",
                "store.evidence_report",
                "projection requires retained evidence report",
            )
        if canonical_digest(evidence_report) != run.evidence_report_digest:
            raise OfflineProductSpineError(
                "persisted_state_corrupt",
                "store.evidence_report",
                "retained evidence digest differs from Product Spine projection",
            )

    if (
        source_run_record is not None
        and evidence_report is not None
        and evidence_report.get("source_run_digest")
        != canonical_digest(source_run_record)
    ):
        raise OfflineProductSpineError(
            "persisted_state_corrupt",
            "store.source_run_record",
            "retained evidence report is not bound to retained source run",
        )

    return PersistedOfflineProductSpineResult(
        run=run,
        idempotency_key=idempotency_key,
        request_digest=record.request_digest,
        created=False,
        replayed=True,
        source_run_record=source_run_record,
        evidence_report=evidence_report,
    )


class IdempotentOfflineProductSpineService:
    """Restart-safe local wrapper around OfflineProductSpineService."""

    def __init__(
        self,
        *,
        service: OfflineProductSpineService,
        store: LocalMetadataStore,
    ) -> None:
        if not isinstance(store, LocalMetadataStore):
            raise TypeError("store must be LocalMetadataStore")
        self._service = service
        self._store = store

    def execute(
        self,
        *,
        idempotency_key: str,
        created_at: str,
        project_id: str,
        work_unit: dict[str, Any],
        source_revision: str,
        routing_decision: RoutingDecision,
        connectors: Iterable[ConnectorProfile],
        attempts: Sequence[OfflineAttemptSpec],
        updated_at: str | None = None,
    ) -> PersistedOfflineProductSpineResult:
        """Execute once or reconstruct the already-completed semantic result."""

        connector_tuple = tuple(connectors)
        request_digest = offline_idempotency_request_digest(
            project_id=project_id,
            work_unit=work_unit,
            source_revision=source_revision,
            routing_decision=routing_decision,
            connectors=connector_tuple,
            attempts=attempts,
        )
        run_id = _run_id(idempotency_key, request_digest)

        try:
            record, created = self._store.admit_run(
                run_id=run_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                state="proposed",
                metadata={
                    "schema_version": IDEMPOTENCY_SCHEMA_VERSION,
                    "kind": _ADMISSION_KIND,
                    "project_id": project_id,
                    "work_unit_digest": canonical_digest(work_unit),
                    "source_revision": source_revision.lower(),
                },
                created_at=created_at,
            )
        except LocalStoreConflict as exc:
            raise OfflineProductSpineError(
                "idempotency_conflict",
                "idempotency_key",
                str(exc),
            ) from exc

        if not created:
            return _restore(
                record,
                idempotency_key=idempotency_key,
            )

        try:
            result = self._service.execute(
                project_id=project_id,
                run_id=run_id,
                work_unit=work_unit,
                source_revision=source_revision,
                routing_decision=routing_decision,
                connectors=connector_tuple,
                attempts=attempts,
                request_digest=request_digest,
            )
        except OfflineProductSpineError as exc:
            self._store.update_run(
                run_id,
                state="execution_error",
                metadata={
                    "schema_version": IDEMPOTENCY_SCHEMA_VERSION,
                    "kind": _ADMISSION_KIND,
                    "phase": "execution_error",
                    "error_code": exc.code,
                },
                updated_at=updated_at or created_at,
            )
            raise

        stored = self._store.update_run(
            run_id,
            state=result.run.state,
            metadata=_result_metadata(result),
            updated_at=updated_at or created_at,
        )

        restored = _restore(
            stored,
            idempotency_key=idempotency_key,
        )
        return PersistedOfflineProductSpineResult(
            run=restored.run,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            created=True,
            replayed=False,
            source_run_record=restored.source_run_record,
            evidence_report=restored.evidence_report,
        )
