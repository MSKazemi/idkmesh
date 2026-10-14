"""Authorized, audited gateway in front of the Human Decision service (#740).

This module is the policy-and-audit layer that
:mod:`idkmesh.human_decision_service` deliberately does not contain.  It is
**transport-neutral and not routed**: no HTTP path, CLI verb or Control Tower
endpoint calls it.  A future network adapter (blocked on the live identity
and policy enforcement of #670 and the network security boundary of #743) must
reach the decision store only through :class:`AuthorizedHumanDecisionGateway`.

For every attempt the gateway:

1. validates the untrusted request shape (pure, no I/O);
2. evaluates the ``decide`` action of :mod:`idkmesh.enterprise_authz` for the
   trusted :class:`ActorContext` against the retained run-evidence resource, so
   tenant isolation, role, human-only actor type, clearance and (at high risk)
   a distinct human approver are enforced by the policy kernel;
3. only on ``allow``, delegates to :class:`HumanDecisionService`, which binds the
   decision to the exact retained evidence digest and persists it append-only;
4. appends exactly one :mod:`idkmesh.enterprise_audit` event for the attempt,
   whatever its outcome (``denied``, ``not_executed``, ``failed``,
   ``succeeded``).

Authority ceiling.  Recording a decision never dispatches work, writes canonical
project state, pushes Git or merges.  The verifier recommendation is never read
as the human decision: the decision is exactly what the authenticated human
sent.  Nothing here can approve on anyone's behalf.

Known gap (documented, not hidden).  The decision store and the audit ledger are
two SQLite files, so there is no cross-store transaction.  If the audit append
fails *after* a decision was persisted, the gateway raises
``audit_unavailable``; the decision is durable and a retry with the same
``Idempotency-Key`` replays it (recorded as a ``not_executed`` audit event,
because replaying executes nothing).  The original ``succeeded`` event is then
absent from the ledger; callers must treat ``audit_unavailable`` as an
incomplete operation to be reconciled, never as "nothing happened".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from idkmesh.enterprise_audit import (
    SERVICE_ACTOR_TYPES,
    AuditEventInput,
    EnterpriseAuditError,
    LocalEnterpriseAuditLedger,
)
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.human_decision_service import (
    HumanDecisionService,
    HumanDecisionServiceError,
    PersistedHumanDecision,
    normalize_request,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantIsolationError, TenantScope

ACTION = "decide"
RESOURCE_TYPE = "run-evidence-report"
DEFAULT_RETENTION_DAYS = 365


class HumanDecisionAuthorizationError(HumanDecisionServiceError):
    """The policy kernel did not allow the decision; nothing was persisted.

    ``code`` is ``authorization_denied`` (effect ``deny``) or
    ``approval_required`` (effect ``requires_approval``).  ``decision`` carries
    the kernel's stable reason code and message; ``audit_event`` is the event
    that recorded the refusal.
    """

    def __init__(
        self,
        code: str,
        decision: AuthorizationDecision,
        audit_event: Mapping[str, Any],
    ) -> None:
        super().__init__(code, f"{decision.code}: {decision.message}")
        self.decision = decision
        self.audit_event = dict(audit_event)


@dataclass(frozen=True, slots=True)
class AuthorizedDecisionResult:
    """A persisted decision together with the authorization and audit evidence."""

    decision: PersistedHumanDecision
    authorization: AuthorizationDecision
    audit_event: Mapping[str, Any]


def _decided_at(now_epoch: int) -> str:
    return datetime.fromtimestamp(now_epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


class AuthorizedHumanDecisionGateway:
    """Authorize, record and audit one human decision per call."""

    def __init__(
        self,
        *,
        service: HumanDecisionService,
        policy: AuthorizationPolicy,
        audit_ledger: LocalEnterpriseAuditLedger,
        audit_writer: ActorContext,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        if not isinstance(service, HumanDecisionService):
            raise HumanDecisionServiceError("invalid_gateway", "service is required")
        if not isinstance(policy, AuthorizationPolicy):
            raise HumanDecisionServiceError("invalid_gateway", "policy is required")
        if policy.rule_for(ACTION) is None:
            # Fail closed at construction: a policy without a ``decide`` rule
            # would deny every attempt anyway; refusing to build is clearer.
            raise HumanDecisionServiceError(
                "invalid_gateway", f"policy has no {ACTION!r} rule"
            )
        if not isinstance(audit_ledger, LocalEnterpriseAuditLedger):
            raise HumanDecisionServiceError(
                "invalid_gateway", "an enterprise audit ledger is required"
            )
        if (
            not isinstance(audit_writer, ActorContext)
            or audit_writer.actor_type not in SERVICE_ACTOR_TYPES
            or not audit_writer.authenticated
            or audit_writer.revoked
        ):
            raise HumanDecisionServiceError(
                "invalid_gateway",
                "audit_writer must be an authenticated, non-revoked service identity",
            )
        if (
            isinstance(retention_days, bool)
            or not isinstance(retention_days, int)
            or not 1 <= retention_days <= 36500
        ):
            raise HumanDecisionServiceError(
                "invalid_gateway", "retention_days must be an integer in 1..36500"
            )
        self._service = service
        self._policy = policy
        self._ledger = audit_ledger
        self._writer = audit_writer
        self._retention_days = retention_days

    def _audit(
        self,
        *,
        now_epoch: int,
        actor: ActorContext,
        decision: AuthorizationDecision,
        evidence_digest: str,
        run_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        try:
            return self._ledger.append(
                AuditEventInput(
                    occurred_at_epoch=now_epoch,
                    actor=actor,
                    service=self._writer,
                    decision=decision,
                    resource_revision=evidence_digest,
                    outcome=outcome,
                    run_id=run_id,
                    evidence_digest=evidence_digest,
                    retention_days=self._retention_days,
                )
            )
        except EnterpriseAuditError as exc:
            raise HumanDecisionServiceError(
                "audit_unavailable",
                "the audit event could not be recorded; the operation is "
                "incomplete and must be reconciled before it is trusted",
            ) from exc

    def record(
        self,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
        actor: ActorContext,
        scope: TenantScope,
        request_id: str,
        now_epoch: int,
        risk: str,
        data_classification: str,
        approver: ActorContext | None = None,
        approval_reference: str | None = None,
    ) -> AuthorizedDecisionResult:
        """Record one human decision, or raise without persisting anything.

        ``actor`` and ``approver`` must come from a trusted authentication
        adapter, never from the request body.  ``risk`` and
        ``data_classification`` are required (no permissive default) and are
        raised to the policy floor by the kernel.  ``now_epoch`` is the single
        trusted clock reading used for identity expiry, ``decided_at`` and the
        audit timestamp.
        """

        # 1. Shape only; no authorization-sensitive I/O has happened yet.
        normalized = normalize_request(request)
        evidence = normalized["evidence_report"]
        run_id: str = evidence["run_id"]
        evidence_digest: str = evidence["digest"]

        # 2. Policy authorization against the retained-evidence resource.
        try:
            authz_request = AuthorizationRequest(
                request_id=request_id,
                scope=scope,
                # Run ids may contain "/" (e.g. "offline/<hex>"), which a scoped
                # resource id forbids; the immutable evidence digest is the
                # resource being decided on, so identify it by that.
                resource=ScopedResourceRef(
                    scope, RESOURCE_TYPE, evidence_digest.replace(":", "-")
                ),
                actor=actor,
                action=ACTION,
                risk=risk,
                data_classification=data_classification,
                evaluated_at_epoch=now_epoch,
                approver=approver,
                approval_reference=approval_reference,
            )
        except (AuthorizationContractError, TenantIsolationError) as exc:
            raise HumanDecisionServiceError(
                "invalid_authorization_input", str(exc)
            ) from exc

        # Pre-flight: if the audit writer cannot record this attempt, refuse
        # *before* anything is persisted (fail closed, not "decide then lose
        # the audit trail").
        writer = self._writer
        if not writer.is_bound_to(scope) or (
            writer.expires_at_epoch is not None and now_epoch >= writer.expires_at_epoch
        ):
            raise HumanDecisionServiceError(
                "audit_unavailable",
                "the audit writer identity is not valid for this tenant/project now",
            )
        authorization = authorize(authz_request, self._policy)

        if authorization.effect != "allow":
            event = self._audit(
                now_epoch=now_epoch,
                actor=actor,
                decision=authorization,
                evidence_digest=evidence_digest,
                run_id=run_id,
                outcome="denied" if authorization.effect == "deny" else "not_executed",
            )
            raise HumanDecisionAuthorizationError(
                "authorization_denied"
                if authorization.effect == "deny"
                else "approval_required",
                authorization,
                event,
            )

        # 3. Allowed: bind to exact evidence and persist append-only.
        try:
            persisted = self._service.record(
                request,
                idempotency_key=idempotency_key,
                actor=actor,
                decided_at=_decided_at(now_epoch),
                evaluated_at_epoch=now_epoch,
            )
        except HumanDecisionServiceError:
            self._audit(
                now_epoch=now_epoch,
                actor=actor,
                decision=authorization,
                evidence_digest=evidence_digest,
                run_id=run_id,
                outcome="failed",
            )
            raise

        # 4. Exactly one audit event for the attempt; a replay executed nothing.
        event = self._audit(
            now_epoch=now_epoch,
            actor=actor,
            decision=authorization,
            evidence_digest=evidence_digest,
            run_id=run_id,
            outcome="succeeded" if persisted.created else "not_executed",
        )
        return AuthorizedDecisionResult(
            decision=persisted, authorization=authorization, audit_event=event
        )
