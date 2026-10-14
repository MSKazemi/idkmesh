"""Audited, time-bounded break-glass grant for E3-E (#670).

Break-glass is the one place where an enterprise deliberately lets a person do
something their standing roles do not allow, because an incident is under way.
The architecture rule (``docs/architecture/ENTERPRISE_CONTROL_PLANE.md``) is
that it must be "explicit, time bounded, reason required, and audited", and
must "not silently become the normal operating path".

This module is a thin, side-effect-free layer on top of
:mod:`idkmesh.enterprise_authz`. Its design decision is deliberately narrow:

* A grant is a *temporary role elevation* for one named human, in exactly one
  tenant/project, for a closed set of actions, up to a capped risk and data
  class. It is never a way to skip a check.
* The only decision a grant can change is ``role_denied``. Tenant/project
  scope, actor binding, revocation, expiry, actor type, data clearance, the
  per-rule data limit, executor separation of duties (verifier is not the
  executor) and the high-risk distinct-approver requirement are all evaluated
  by the unmodified kernel on the elevated actor, so break-glass cannot
  bypass any of them. Restricted data and ``critical`` risk can never be
  covered by a grant, and ``manage_policy`` / ``audit_export`` are not
  grantable at all.
* Issuing a grant needs a distinct, currently valid, human ``owner``/``admin``
  approver bound to the same scope, an incident id, and a written reason. The
  grant expires at the earliest of the requested TTL (hard cap
  :data:`MAX_TTL_SECONDS`), the beneficiary's own expiry and the approver's own
  expiry.
* A grant is bound to the beneficiary's ``identity_revision`` and to the
  policy id + revision it was issued under. A changed identity or an edited
  policy makes it inert (fail closed), and a revocation set is consulted on
  every use.
* Every use returns the grant digest as ``evidence_digest`` so the existing
  tamper-evident audit ledger (:mod:`idkmesh.enterprise_audit`) can record the
  elevated decision against the exact grant. The ALLOW carries the distinct
  code ``authorized_by_break_glass`` so it can never be mistaken for a normal
  authorization.

The result is policy evidence only; it executes nothing and carries no
canonical-state-write or merge authority. This module performs no network
call and does not verify a token; the beneficiary and approver
``ActorContext`` values must come from a trusted identity adapter (E3-B/E3-C).
Integrity of stored grants (a stored document is trusted exactly as far as
the store that holds it) and the revocation feed are deployment concerns.
Do not put credentials or secrets in ``reason``: it is retained verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from idkmesh.enterprise_authz import (
    ACTIONS,
    DATA_CLASSES,
    RISKS,
    ActorContext,
    AuthorizationContractError,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import TenantScope

BREAK_GLASS_KIND = "idkmesh-enterprise-break-glass-grant"
BREAK_GLASS_VERSION = "0.1"
BREAK_GLASS_ALLOW_CODE = "authorized_by_break_glass"

MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 4 * 60 * 60
MIN_REASON_LENGTH = 10
MAX_REASON_LENGTH = 500
MAX_GRANT_ACTIONS = 4

# Roles an incident may temporarily confer. ``owner``/``admin`` are the
# approving roles and ``auditor`` guards evidence, so none of the three can be
# conferred by a grant: break-glass cannot mint a new approver.
GRANTABLE_ROLES = frozenset(
    {"integrator", "worker", "reviewer", "dispatcher", "node_operator"}
)
# Policy and audit-export authority is never an emergency shortcut.
NON_GRANTABLE_ACTIONS = frozenset({"manage_policy", "audit_export"})
GRANTABLE_ACTIONS = ACTIONS - NON_GRANTABLE_ACTIONS
APPROVER_ROLES = frozenset({"owner", "admin"})
# Hard ceilings, independent of what a grant document asks for.
MAX_GRANTED_RISK = "high"
MAX_GRANTED_DATA_CLASS = "confidential"

_RISK_RANK = {value: index for index, value in enumerate(RISKS)}
_DATA_RANK = {value: index for index, value in enumerate(DATA_CLASSES)}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}\Z")
_POLICY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}\Z")

_GRANT_FIELDS = frozenset(
    {
        "kind",
        "schema_version",
        "grant_id",
        "scope",
        "incident_id",
        "reason",
        "beneficiary_principal_id",
        "beneficiary_identity_revision",
        "approver_principal_id",
        "approver_identity_revision",
        "granted_roles",
        "actions",
        "max_risk",
        "max_data_classification",
        "policy_id",
        "policy_revision",
        "issued_at_epoch",
        "expires_at_epoch",
    }
)


class BreakGlassError(AuthorizationContractError):
    """A grant request or grant document is invalid or not issuable."""


def _fail(code: str, path: str, message: str) -> BreakGlassError:
    return BreakGlassError(code, path, message)


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise _fail("invalid_identifier", path, "must be a safe identifier")
    return value


def _policy_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _POLICY_RE.fullmatch(value):
        raise _fail("invalid_policy_identifier", path, "invalid policy identifier")
    return value


def _epoch(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("invalid_epoch", path, "must be an integer >= 0")
    return value


def _reason(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise _fail("invalid_reason", path, "reason is required")
    if value != value.strip() or not (
        MIN_REASON_LENGTH <= len(value) <= MAX_REASON_LENGTH
    ):
        raise _fail(
            "invalid_reason",
            path,
            f"must be {MIN_REASON_LENGTH}-{MAX_REASON_LENGTH} characters "
            "without leading or trailing whitespace",
        )
    if any(not char.isprintable() for char in value):
        raise _fail(
            "invalid_reason", path, "must be printable single-line text"
        )
    return value


def _choice_set(
    values: Any, allowed: frozenset[str], path: str, *, max_items: int
) -> frozenset[str]:
    if not isinstance(values, (set, frozenset, tuple, list)) or not values:
        raise _fail("invalid_collection", path, "must be a non-empty collection")
    if any(not isinstance(item, str) for item in values):
        raise _fail("invalid_type", path, "must contain strings")
    result = frozenset(values)
    if len(result) != len(values):
        raise _fail("duplicate_value", path, "values must be unique")
    unknown = sorted(result - allowed)
    if unknown:
        raise _fail(
            "value_not_grantable", path, "not grantable: " + ", ".join(unknown)
        )
    if len(result) > max_items:
        raise _fail("too_many_values", path, f"at most {max_items} values")
    return result


def _ceiling(value: Any, ranks: Mapping[str, int], ceiling: str, path: str) -> str:
    if not isinstance(value, str) or value not in ranks:
        raise _fail("invalid_enum", path, "must be one of: " + ", ".join(ranks))
    if ranks[value] > ranks[ceiling]:
        raise _fail(
            "value_not_grantable",
            path,
            f"break-glass cannot cover more than {ceiling!r}",
        )
    return value


def _digest(value: Mapping[str, Any]) -> str:
    text = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BreakGlassGrant:
    """One explicit, time-bounded, reason-carrying role elevation."""

    grant_id: str
    scope: TenantScope
    incident_id: str
    reason: str
    beneficiary_principal_id: str
    beneficiary_identity_revision: str
    approver_principal_id: str
    approver_identity_revision: str
    granted_roles: frozenset[str]
    actions: frozenset[str]
    max_risk: str
    max_data_classification: str
    policy_id: str
    policy_revision: str
    issued_at_epoch: int
    expires_at_epoch: int

    def __post_init__(self) -> None:
        _identifier(self.grant_id, "grant_id")
        if not isinstance(self.scope, TenantScope):
            raise _fail("invalid_scope", "scope", "must be TenantScope")
        _identifier(self.incident_id, "incident_id")
        _reason(self.reason, "reason")
        _identifier(self.beneficiary_principal_id, "beneficiary_principal_id")
        _policy_identifier(
            self.beneficiary_identity_revision, "beneficiary_identity_revision"
        )
        _identifier(self.approver_principal_id, "approver_principal_id")
        _policy_identifier(
            self.approver_identity_revision, "approver_identity_revision"
        )
        if self.beneficiary_principal_id == self.approver_principal_id:
            raise _fail(
                "self_approval_forbidden",
                "approver_principal_id",
                "a break-glass grant needs a distinct approver",
            )
        object.__setattr__(
            self,
            "granted_roles",
            _choice_set(
                self.granted_roles,
                GRANTABLE_ROLES,
                "granted_roles",
                max_items=len(GRANTABLE_ROLES),
            ),
        )
        object.__setattr__(
            self,
            "actions",
            _choice_set(
                self.actions,
                GRANTABLE_ACTIONS,
                "actions",
                max_items=MAX_GRANT_ACTIONS,
            ),
        )
        _ceiling(self.max_risk, _RISK_RANK, MAX_GRANTED_RISK, "max_risk")
        _ceiling(
            self.max_data_classification,
            _DATA_RANK,
            MAX_GRANTED_DATA_CLASS,
            "max_data_classification",
        )
        _policy_identifier(self.policy_id, "policy_id")
        _policy_identifier(self.policy_revision, "policy_revision")
        _epoch(self.issued_at_epoch, "issued_at_epoch")
        _epoch(self.expires_at_epoch, "expires_at_epoch")
        ttl = self.expires_at_epoch - self.issued_at_epoch
        if ttl < MIN_TTL_SECONDS:
            raise _fail(
                "invalid_ttl", "expires_at_epoch", "grant window is too short"
            )
        if ttl > MAX_TTL_SECONDS:
            raise _fail(
                "invalid_ttl",
                "expires_at_epoch",
                f"grant window exceeds {MAX_TTL_SECONDS} seconds",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": BREAK_GLASS_KIND,
            "schema_version": BREAK_GLASS_VERSION,
            "grant_id": self.grant_id,
            "scope": self.scope.to_dict(),
            "incident_id": self.incident_id,
            "reason": self.reason,
            "beneficiary_principal_id": self.beneficiary_principal_id,
            "beneficiary_identity_revision": self.beneficiary_identity_revision,
            "approver_principal_id": self.approver_principal_id,
            "approver_identity_revision": self.approver_identity_revision,
            "granted_roles": sorted(self.granted_roles),
            "actions": sorted(self.actions),
            "max_risk": self.max_risk,
            "max_data_classification": self.max_data_classification,
            "policy_id": self.policy_id,
            "policy_revision": self.policy_revision,
            "issued_at_epoch": self.issued_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
        }

    @property
    def digest(self) -> str:
        """``sha256:`` digest of the canonical grant; ledger ``evidence_digest``."""

        return _digest(self.to_dict())


def parse_break_glass_grant(value: Any) -> BreakGlassGrant:
    """Parse a stored grant document strictly; unknown fields are refused."""

    if not isinstance(value, Mapping):
        raise _fail("invalid_type", "$", "grant must be an object")
    missing = sorted(_GRANT_FIELDS - set(value))
    if missing:
        raise _fail("missing_field", "$", "missing: " + ", ".join(missing))
    unknown = sorted(set(value) - _GRANT_FIELDS)
    if unknown:
        raise _fail("unknown_field", f"$.{unknown[0]}", "unknown grant field")
    if value["kind"] != BREAK_GLASS_KIND:
        raise _fail("invalid_kind", "$.kind", f"must be {BREAK_GLASS_KIND!r}")
    if value["schema_version"] != BREAK_GLASS_VERSION:
        raise _fail(
            "unsupported_version",
            "$.schema_version",
            f"must be {BREAK_GLASS_VERSION!r}",
        )
    raw_scope = value["scope"]
    if not isinstance(raw_scope, Mapping) or set(raw_scope) != {
        "tenant_id",
        "project_id",
    }:
        raise _fail(
            "invalid_scope",
            "$.scope",
            "scope must contain only tenant_id and project_id",
        )
    try:
        scope = TenantScope(raw_scope["tenant_id"], raw_scope["project_id"])
    except ValueError as exc:
        raise _fail("invalid_scope", "$.scope", str(exc)) from exc
    for field in ("granted_roles", "actions"):
        if not isinstance(value[field], list):
            raise _fail("invalid_type", f"$.{field}", "must be an array")
    return BreakGlassGrant(
        grant_id=value["grant_id"],
        scope=scope,
        incident_id=value["incident_id"],
        reason=value["reason"],
        beneficiary_principal_id=value["beneficiary_principal_id"],
        beneficiary_identity_revision=value["beneficiary_identity_revision"],
        approver_principal_id=value["approver_principal_id"],
        approver_identity_revision=value["approver_identity_revision"],
        granted_roles=frozenset(value["granted_roles"]),
        actions=frozenset(value["actions"]),
        max_risk=value["max_risk"],
        max_data_classification=value["max_data_classification"],
        policy_id=value["policy_id"],
        policy_revision=value["policy_revision"],
        issued_at_epoch=value["issued_at_epoch"],
        expires_at_epoch=value["expires_at_epoch"],
    )


def _validate_party(actor: Any, role: str, scope: TenantScope, at: int) -> None:
    if not isinstance(actor, ActorContext):
        raise _fail(f"invalid_{role}", role, "must be ActorContext")
    if not actor.authenticated:
        raise _fail(f"{role}_unauthenticated", role, "identity is not authenticated")
    if actor.revoked:
        raise _fail(f"{role}_revoked", role, "identity is revoked")
    if actor.expires_at_epoch is not None and at >= actor.expires_at_epoch:
        raise _fail(f"{role}_expired", role, "identity is expired")
    if not actor.is_bound_to(scope):
        raise _fail(
            f"{role}_scope_denied",
            role,
            "identity is not bound to the requested tenant/project",
        )
    if actor.actor_type != "human":
        raise _fail(
            f"{role}_not_human",
            role,
            "break-glass beneficiary and approver must be human principals",
        )


def issue_break_glass_grant(
    *,
    grant_id: str,
    scope: TenantScope,
    beneficiary: ActorContext,
    approver: ActorContext,
    incident_id: str,
    reason: str,
    granted_roles: Iterable[str],
    actions: Iterable[str],
    max_risk: str,
    max_data_classification: str,
    policy: AuthorizationPolicy,
    issued_at_epoch: int,
    ttl_seconds: int,
) -> BreakGlassGrant:
    """Validate and build a grant. Raises :class:`BreakGlassError` on any gap.

    Issuing does not store, publish or audit anything; the caller records the
    returned grant (and its :attr:`BreakGlassGrant.digest`) through the audit
    ledger. Nothing about the beneficiary's or approver's authority is read
    from the reason text.
    """

    _epoch(issued_at_epoch, "issued_at_epoch")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise _fail("invalid_ttl", "ttl_seconds", "must be an integer")
    if not (MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS):
        raise _fail(
            "invalid_ttl",
            "ttl_seconds",
            f"must be {MIN_TTL_SECONDS}-{MAX_TTL_SECONDS} seconds",
        )
    if not isinstance(scope, TenantScope):
        raise _fail("invalid_scope", "scope", "must be TenantScope")
    if not isinstance(policy, AuthorizationPolicy):
        raise _fail("invalid_policy", "policy", "must be AuthorizationPolicy")
    _validate_party(beneficiary, "beneficiary", scope, issued_at_epoch)
    _validate_party(approver, "approver", scope, issued_at_epoch)
    if beneficiary.principal_id == approver.principal_id:
        raise _fail(
            "self_approval_forbidden",
            "approver",
            "a break-glass grant needs a distinct approver",
        )
    if not (approver.roles & APPROVER_ROLES):
        raise _fail(
            "approver_role_denied",
            "approver",
            "approver must hold the owner or admin role",
        )
    expires = issued_at_epoch + ttl_seconds
    for party in (beneficiary, approver):
        if party.expires_at_epoch is not None:
            expires = min(expires, party.expires_at_epoch)
    grant = BreakGlassGrant(
        grant_id=grant_id,
        scope=scope,
        incident_id=incident_id,
        reason=reason,
        beneficiary_principal_id=beneficiary.principal_id,
        beneficiary_identity_revision=beneficiary.identity_revision,
        approver_principal_id=approver.principal_id,
        approver_identity_revision=approver.identity_revision,
        granted_roles=frozenset(granted_roles),
        actions=frozenset(actions),
        max_risk=max_risk,
        max_data_classification=max_data_classification,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        issued_at_epoch=issued_at_epoch,
        expires_at_epoch=expires,
    )
    if _DATA_RANK[grant.max_data_classification] > _DATA_RANK[approver.data_clearance]:
        raise _fail(
            "approver_clearance_denied",
            "approver",
            "approver clearance does not cover the granted data classification",
        )
    return grant


@dataclass(frozen=True, slots=True)
class BreakGlassOutcome:
    """Authorization decision plus break-glass provenance."""

    decision: AuthorizationDecision
    break_glass_used: bool
    grant_id: str | None = None
    incident_id: str | None = None
    # Pass as ``AuditEventInput.evidence_digest`` so the ledger event names the
    # exact grant. ``None`` when no grant took part in an ALLOW.
    evidence_digest: str | None = None


def _grant_refusal(
    grant: BreakGlassGrant,
    request: AuthorizationRequest,
    policy: AuthorizationPolicy,
    effective_risk: str,
    revoked_grant_ids: frozenset[str],
) -> tuple[str, str] | None:
    """Return a deny ``(code, message)`` when the grant does not apply."""

    at = request.evaluated_at_epoch
    if grant.grant_id in revoked_grant_ids:
        return "break_glass_revoked", "break-glass grant is revoked"
    if at < grant.issued_at_epoch:
        return "break_glass_not_yet_valid", "break-glass grant is not yet valid"
    if at >= grant.expires_at_epoch:
        return "break_glass_expired", "break-glass grant is expired"
    if grant.scope != request.scope:
        return (
            "break_glass_scope_mismatch",
            "break-glass grant is bound to a different tenant/project",
        )
    if grant.beneficiary_principal_id != request.actor.principal_id:
        return (
            "break_glass_principal_mismatch",
            "break-glass grant belongs to a different principal",
        )
    if grant.beneficiary_identity_revision != request.actor.identity_revision:
        return (
            "break_glass_identity_changed",
            "actor identity changed since the grant was issued",
        )
    if (grant.policy_id, grant.policy_revision) != (policy.policy_id, policy.revision):
        return (
            "break_glass_policy_changed",
            "policy changed since the grant was issued",
        )
    if request.action not in grant.actions:
        return (
            "break_glass_action_not_granted",
            "break-glass grant does not cover this action",
        )
    if _RISK_RANK[effective_risk] > _RISK_RANK[grant.max_risk]:
        return (
            "break_glass_risk_exceeded",
            "effective risk exceeds the break-glass grant limit",
        )
    if _DATA_RANK[request.data_classification] > _DATA_RANK[grant.max_data_classification]:
        return (
            "break_glass_data_limit",
            "data classification exceeds the break-glass grant limit",
        )
    rule = policy.rule_for(request.action)
    if rule is None or not (grant.granted_roles & rule.allowed_roles):
        return (
            "break_glass_role_insufficient",
            "granted roles do not satisfy the policy rule for this action",
        )
    return None


def authorize_with_break_glass(
    request: AuthorizationRequest,
    policy: AuthorizationPolicy,
    grant: BreakGlassGrant | None,
    *,
    revoked_grant_ids: Iterable[str] = (),
) -> BreakGlassOutcome:
    """Authorize, letting a valid grant cover only a ``role_denied`` outcome.

    The standing policy is always evaluated first. A grant is consulted only
    if the sole obstacle is the actor's roles; every other denial, and every
    ``requires_approval`` result, is returned unchanged. When the grant
    applies, the unmodified kernel re-evaluates the actor with the granted
    roles added, so data clearance, executor separation and high-risk distinct
    approval still have to pass.

    This function does not use the decision cache. A cached ALLOW would
    outlive the grant's expiry or revocation; callers must not front it with
    :class:`idkmesh.enterprise_authz_cache.AuthorizationDecisionCache`.
    """

    if grant is not None and not isinstance(grant, BreakGlassGrant):
        raise _fail("invalid_grant", "grant", "must be BreakGlassGrant or None")
    if isinstance(revoked_grant_ids, (str, bytes)):
        raise _fail("invalid_type", "revoked_grant_ids", "must be a collection")
    revoked = frozenset(revoked_grant_ids)

    standing = authorize(request, policy)
    if standing.effect == "allow" or grant is None or standing.code != "role_denied":
        return BreakGlassOutcome(decision=standing, break_glass_used=False)

    refusal = _grant_refusal(
        grant, request, policy, standing.effective_risk, revoked
    )
    if refusal is not None:
        return BreakGlassOutcome(
            decision=replace(
                standing, effect="deny", code=refusal[0], message=refusal[1]
            ),
            break_glass_used=False,
            grant_id=grant.grant_id,
            incident_id=grant.incident_id,
            evidence_digest=grant.digest,
        )

    elevated = replace(
        request,
        actor=replace(
            request.actor, roles=request.actor.roles | grant.granted_roles
        ),
    )
    result = authorize(elevated, policy)
    if result.effect != "allow":
        # Some other control still refuses (clearance, executor separation,
        # high-risk approval, ...): report it exactly as the kernel did.
        return BreakGlassOutcome(
            decision=result,
            break_glass_used=False,
            grant_id=grant.grant_id,
            incident_id=grant.incident_id,
            evidence_digest=grant.digest,
        )
    return BreakGlassOutcome(
        decision=replace(
            result,
            code=BREAK_GLASS_ALLOW_CODE,
            message=(
                "authorized by an explicit, time-bounded break-glass grant "
                f"for incident {grant.incident_id}"
            ),
        ),
        break_glass_used=True,
        grant_id=grant.grant_id,
        incident_id=grant.incident_id,
        evidence_digest=grant.digest,
    )
