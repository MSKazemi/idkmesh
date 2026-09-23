"""Enterprise actor identity and authorization kernel for E3 (#670).

This module composes with :mod:`idkmesh.tenant_scope`. Tenant scope answers
"which tenant/project owns this resource?"; this module answers whether a
trusted actor/service identity is authorized for one action against that exact
scope.

The kernel is intentionally side-effect free. An ALLOW decision is policy
evidence consumed by a later executor; the decision object does not itself
dispatch, reveal a secret, write canonical state, or merge code.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from idkmesh.tenant_scope import (
    ScopedResourceRef,
    TenantIsolationError,
    TenantScope,
    assert_same_scope,
)

AUTHZ_VERSION = "0.1"
ACTOR_KIND = "idkmesh-enterprise-actor-context"
DECISION_KIND = "idkmesh-enterprise-authorization-decision"

ACTOR_TYPES = frozenset(
    {
        "human",
        "github_app",
        "github_actions",
        "service",
        "provider",
        "node",
    }
)
ROLES = frozenset(
    {
        "owner",
        "admin",
        "integrator",
        "worker",
        "reviewer",
        "dispatcher",
        "node_operator",
        "auditor",
    }
)
ACTIONS = frozenset(
    {
        "read",
        "claim",
        "release",
        "dispatch",
        "execute",
        "verify",
        "integrate",
        "manage_policy",
        "audit_export",
    }
)
RISKS = ("low", "medium", "high", "critical")
DATA_CLASSES = ("public", "internal", "confidential", "restricted")
EFFECTS = frozenset({"allow", "deny", "requires_approval"})

_RISK_RANK = {value: index for index, value in enumerate(RISKS)}
_DATA_RANK = {value: index for index, value in enumerate(DATA_CLASSES)}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_POLICY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class AuthorizationContractError(ValueError):
    """Invalid trusted identity/policy/request input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> AuthorizationContractError:
    return AuthorizationContractError(code, path, message)


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise _fail(
            "invalid_identifier",
            path,
            "must be 1-256 characters using letters, digits, '.', '_', ':', "
            "'/', '@' or '-' and start with a letter or digit",
        )
    return value


def _policy_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _POLICY_RE.fullmatch(value):
        raise _fail("invalid_policy_identifier", path, "invalid policy identifier")
    return value


def _enum(value: Any, allowed: frozenset[str] | tuple[str, ...], path: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _fail(
            "invalid_enum",
            path,
            "must be one of: " + ", ".join(sorted(allowed)),
        )
    return value


def _epoch(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("invalid_epoch", path, "must be an integer >= 0")
    return value


def _normalize_set(
    values: Any,
    *,
    allowed: frozenset[str],
    path: str,
    allow_empty: bool,
) -> frozenset[str]:
    if not isinstance(values, (set, frozenset, tuple, list)):
        raise _fail("invalid_type", path, "must be a collection")
    if not values and not allow_empty:
        raise _fail("empty_collection", path, "must not be empty")
    if any(not isinstance(item, str) for item in values):
        raise _fail("invalid_type", path, "must contain strings")
    result = frozenset(values)
    unknown = sorted(result - allowed)
    if unknown:
        raise _fail("unknown_value", path, "unknown: " + ", ".join(unknown))
    return result


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Trusted normalized identity claims supplied by an authentication adapter."""

    principal_id: str
    actor_type: str
    issuer: str
    roles: frozenset[str]
    scopes: tuple[TenantScope, ...]
    data_clearance: str
    identity_revision: str
    authenticated: bool = True
    revoked: bool = False
    expires_at_epoch: int | None = None

    def __post_init__(self) -> None:
        _identifier(self.principal_id, "principal_id")
        _enum(self.actor_type, ACTOR_TYPES, "actor_type")
        _identifier(self.issuer, "issuer")
        normalized_roles = _normalize_set(
            self.roles,
            allowed=ROLES,
            path="roles",
            allow_empty=True,
        )
        object.__setattr__(self, "roles", normalized_roles)
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or any(not isinstance(scope, TenantScope) for scope in self.scopes)
        ):
            raise _fail(
                "invalid_scopes",
                "scopes",
                "must be a non-empty tuple of TenantScope values",
            )
        if len(set(self.scopes)) != len(self.scopes):
            raise _fail("duplicate_scope", "scopes", "scope bindings must be unique")
        _enum(self.data_clearance, DATA_CLASSES, "data_clearance")
        _policy_identifier(self.identity_revision, "identity_revision")
        if type(self.authenticated) is not bool:
            raise _fail("invalid_type", "authenticated", "must be boolean")
        if type(self.revoked) is not bool:
            raise _fail("invalid_type", "revoked", "must be boolean")
        if self.expires_at_epoch is not None:
            _epoch(self.expires_at_epoch, "expires_at_epoch")

    def is_bound_to(self, scope: TenantScope) -> bool:
        return scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": ACTOR_KIND,
            "schema_version": AUTHZ_VERSION,
            "principal_id": self.principal_id,
            "actor_type": self.actor_type,
            "issuer": self.issuer,
            "roles": sorted(self.roles),
            "scopes": [scope.to_dict() for scope in self.scopes],
            "data_clearance": self.data_clearance,
            "identity_revision": self.identity_revision,
            "authenticated": self.authenticated,
            "revoked": self.revoked,
            "expires_at_epoch": self.expires_at_epoch,
        }


def parse_actor_context(value: Any) -> ActorContext:
    """Parse only normalized trusted claims; task/issue text is not accepted."""

    if not isinstance(value, Mapping):
        raise _fail("invalid_type", "$", "actor context must be an object")
    fields = {
        "kind",
        "schema_version",
        "principal_id",
        "actor_type",
        "issuer",
        "roles",
        "scopes",
        "data_clearance",
        "identity_revision",
        "authenticated",
        "revoked",
        "expires_at_epoch",
    }
    missing = sorted(fields - set(value))
    if missing:
        raise _fail("missing_field", "$", "missing: " + ", ".join(missing))
    unknown = sorted(set(value) - fields)
    if unknown:
        raise _fail("unknown_field", f"$.{unknown[0]}", "unknown actor field")

    if value["kind"] != ACTOR_KIND:
        raise _fail("invalid_kind", "$.kind", f"must be {ACTOR_KIND!r}")
    if value["schema_version"] != AUTHZ_VERSION:
        raise _fail(
            "unsupported_version",
            "$.schema_version",
            f"must be {AUTHZ_VERSION!r}",
        )

    raw_scopes = value["scopes"]
    if not isinstance(raw_scopes, list) or not raw_scopes:
        raise _fail("invalid_scopes", "$.scopes", "must be a non-empty array")
    scopes: list[TenantScope] = []
    for index, item in enumerate(raw_scopes):
        if not isinstance(item, Mapping):
            raise _fail("invalid_type", f"$.scopes[{index}]", "must be an object")
        if set(item) != {"tenant_id", "project_id"}:
            raise _fail(
                "invalid_scope",
                f"$.scopes[{index}]",
                "scope must contain only tenant_id and project_id",
            )
        scopes.append(
            TenantScope(
                tenant_id=item["tenant_id"],
                project_id=item["project_id"],
            )
        )

    roles = _normalize_set(
        value["roles"],
        allowed=ROLES,
        path="$.roles",
        allow_empty=True,
    )
    expires = value["expires_at_epoch"]
    if expires is not None:
        _epoch(expires, "$.expires_at_epoch")

    return ActorContext(
        principal_id=_identifier(value["principal_id"], "$.principal_id"),
        actor_type=_enum(value["actor_type"], ACTOR_TYPES, "$.actor_type"),
        issuer=_identifier(value["issuer"], "$.issuer"),
        roles=roles,
        scopes=tuple(scopes),
        data_clearance=_enum(
            value["data_clearance"], DATA_CLASSES, "$.data_clearance"
        ),
        identity_revision=_policy_identifier(
            value["identity_revision"], "$.identity_revision"
        ),
        authenticated=value["authenticated"],
        revoked=value["revoked"],
        expires_at_epoch=expires,
    )


@dataclass(frozen=True, slots=True)
class PolicyRule:
    action: str
    allowed_roles: frozenset[str]
    allowed_actor_types: frozenset[str]
    max_data_classification: str = "restricted"
    risk_floor: str = "low"
    distinct_approval_at_risk: str | None = None
    approval_roles: frozenset[str] = frozenset()
    approval_actor_types: frozenset[str] = frozenset({"human"})

    def __post_init__(self) -> None:
        _enum(self.action, ACTIONS, "rule.action")
        object.__setattr__(
            self,
            "allowed_roles",
            _normalize_set(
                self.allowed_roles,
                allowed=ROLES,
                path=f"rule[{self.action}].allowed_roles",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "allowed_actor_types",
            _normalize_set(
                self.allowed_actor_types,
                allowed=ACTOR_TYPES,
                path=f"rule[{self.action}].allowed_actor_types",
                allow_empty=False,
            ),
        )
        _enum(
            self.max_data_classification,
            DATA_CLASSES,
            f"rule[{self.action}].max_data_classification",
        )
        _enum(self.risk_floor, RISKS, f"rule[{self.action}].risk_floor")
        if self.distinct_approval_at_risk is not None:
            _enum(
                self.distinct_approval_at_risk,
                RISKS,
                f"rule[{self.action}].distinct_approval_at_risk",
            )
            object.__setattr__(
                self,
                "approval_roles",
                _normalize_set(
                    self.approval_roles,
                    allowed=ROLES,
                    path=f"rule[{self.action}].approval_roles",
                    allow_empty=False,
                ),
            )
            object.__setattr__(
                self,
                "approval_actor_types",
                _normalize_set(
                    self.approval_actor_types,
                    allowed=ACTOR_TYPES,
                    path=f"rule[{self.action}].approval_actor_types",
                    allow_empty=False,
                ),
            )


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    policy_id: str
    revision: str
    rules: tuple[PolicyRule, ...]

    def __post_init__(self) -> None:
        _policy_identifier(self.policy_id, "policy_id")
        _policy_identifier(self.revision, "policy.revision")
        if not isinstance(self.rules, tuple) or not self.rules:
            raise _fail("invalid_rules", "rules", "must be a non-empty tuple")
        if any(not isinstance(rule, PolicyRule) for rule in self.rules):
            raise _fail("invalid_rules", "rules", "must contain PolicyRule values")
        actions = [rule.action for rule in self.rules]
        if len(actions) != len(set(actions)):
            raise _fail("duplicate_rule", "rules", "actions must be unique")

    def rule_for(self, action: str) -> PolicyRule | None:
        return next((rule for rule in self.rules if rule.action == action), None)

    @classmethod
    def enterprise_baseline(cls) -> "AuthorizationPolicy":
        human_or_service = frozenset(
            {"human", "github_app", "github_actions", "service"}
        )
        worker_types = frozenset(
            {"human", "github_app", "github_actions", "service", "provider", "node"}
        )
        all_types = ACTOR_TYPES
        all_roles = ROLES
        human = frozenset({"human"})
        high_approvers = frozenset({"owner", "admin", "dispatcher", "integrator"})
        return cls(
            policy_id="idkmesh.enterprise.baseline",
            revision="0.1",
            rules=(
                PolicyRule("read", all_roles, all_types),
                PolicyRule(
                    "claim",
                    frozenset({"worker", "dispatcher", "node_operator"}),
                    worker_types,
                ),
                PolicyRule(
                    "release",
                    frozenset({"worker", "dispatcher", "node_operator"}),
                    worker_types,
                ),
                PolicyRule(
                    "dispatch",
                    frozenset({"dispatcher", "admin", "owner"}),
                    human_or_service,
                    distinct_approval_at_risk="high",
                    approval_roles=high_approvers,
                    approval_actor_types=human,
                ),
                PolicyRule(
                    "execute",
                    frozenset({"worker", "node_operator"}),
                    worker_types,
                    distinct_approval_at_risk="high",
                    approval_roles=frozenset({"dispatcher", "admin", "owner"}),
                    approval_actor_types=human,
                ),
                PolicyRule(
                    "verify",
                    frozenset({"reviewer", "auditor"}),
                    human_or_service,
                ),
                PolicyRule(
                    "integrate",
                    frozenset({"integrator", "admin", "owner"}),
                    human,
                    distinct_approval_at_risk="high",
                    approval_roles=frozenset({"integrator", "admin", "owner"}),
                    approval_actor_types=human,
                ),
                PolicyRule(
                    "manage_policy",
                    frozenset({"admin", "owner"}),
                    human,
                    risk_floor="high",
                    distinct_approval_at_risk="high",
                    approval_roles=frozenset({"admin", "owner"}),
                    approval_actor_types=human,
                ),
                PolicyRule(
                    "audit_export",
                    frozenset({"auditor", "admin", "owner"}),
                    frozenset({"human", "github_app", "service"}),
                    risk_floor="medium",
                    distinct_approval_at_risk="critical",
                    approval_roles=frozenset({"auditor", "admin", "owner"}),
                    approval_actor_types=human,
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    request_id: str
    scope: TenantScope
    resource: ScopedResourceRef
    actor: ActorContext
    action: str
    risk: str
    data_classification: str
    evaluated_at_epoch: int
    approver: ActorContext | None = None
    approval_reference: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.request_id, "request_id")
        if not isinstance(self.scope, TenantScope):
            raise _fail("invalid_scope", "scope", "must be TenantScope")
        if not isinstance(self.resource, ScopedResourceRef):
            raise _fail("invalid_resource", "resource", "must be ScopedResourceRef")
        if not isinstance(self.actor, ActorContext):
            raise _fail("invalid_actor", "actor", "must be ActorContext")
        _enum(self.action, ACTIONS, "action")
        _enum(self.risk, RISKS, "risk")
        _enum(self.data_classification, DATA_CLASSES, "data_classification")
        _epoch(self.evaluated_at_epoch, "evaluated_at_epoch")
        if self.approver is not None and not isinstance(self.approver, ActorContext):
            raise _fail("invalid_approver", "approver", "must be ActorContext")
        if self.approver is None and self.approval_reference is not None:
            raise _fail(
                "approval_without_actor",
                "approval_reference",
                "cannot exist without approver",
            )
        if self.approver is not None:
            _identifier(self.approval_reference, "approval_reference")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    effect: str
    code: str
    message: str
    request_id: str
    principal_id: str
    action: str
    tenant_id: str
    project_id: str
    resource_type: str
    resource_id: str
    requested_risk: str
    effective_risk: str
    data_classification: str
    policy_id: str
    policy_revision: str
    identity_revision: str
    evaluated_at_epoch: int
    approved_by: str | None = None
    approval_reference: str | None = None

    def __post_init__(self) -> None:
        _enum(self.effect, EFFECTS, "decision.effect")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": DECISION_KIND,
            "schema_version": AUTHZ_VERSION,
            "effect": self.effect,
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "principal_id": self.principal_id,
            "action": self.action,
            "resource": {
                "tenant_id": self.tenant_id,
                "project_id": self.project_id,
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
            },
            "requested_risk": self.requested_risk,
            "effective_risk": self.effective_risk,
            "data_classification": self.data_classification,
            "policy": {
                "policy_id": self.policy_id,
                "revision": self.policy_revision,
            },
            "identity_revision": self.identity_revision,
            "evaluated_at_epoch": self.evaluated_at_epoch,
            "approved_by": self.approved_by,
            "approval_reference": self.approval_reference,
            "authority": {
                "executes_action": False,
                "canonical_state_write": False,
                "merge": False,
            },
        }


def _effective_risk(requested: str, floor: str) -> str:
    return requested if _RISK_RANK[requested] >= _RISK_RANK[floor] else floor


def _identity_failure(actor: ActorContext, at: int, prefix: str) -> tuple[str, str] | None:
    if not actor.authenticated:
        return f"{prefix}_unauthenticated", "identity is not authenticated"
    if actor.revoked:
        return f"{prefix}_revoked", "identity is revoked"
    if actor.expires_at_epoch is not None and at >= actor.expires_at_epoch:
        return f"{prefix}_expired", "identity is expired"
    return None


def authorize(
    request: AuthorizationRequest,
    policy: AuthorizationPolicy,
) -> AuthorizationDecision:
    """Evaluate one authorization request without performing side effects."""

    rule = policy.rule_for(request.action)
    effective_risk = request.risk if rule is None else _effective_risk(
        request.risk, rule.risk_floor
    )

    def decision(
        effect: str,
        code: str,
        message: str,
        *,
        approved_by: str | None = None,
        approval_reference: str | None = None,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            effect=effect,
            code=code,
            message=message,
            request_id=request.request_id,
            principal_id=request.actor.principal_id,
            action=request.action,
            tenant_id=request.scope.tenant_id,
            project_id=request.scope.project_id,
            resource_type=request.resource.resource_type,
            resource_id=request.resource.resource_id,
            requested_risk=request.risk,
            effective_risk=effective_risk,
            data_classification=request.data_classification,
            policy_id=policy.policy_id,
            policy_revision=policy.revision,
            identity_revision=request.actor.identity_revision,
            evaluated_at_epoch=request.evaluated_at_epoch,
            approved_by=approved_by,
            approval_reference=approval_reference,
        )

    try:
        assert_same_scope(
            request.scope,
            request.resource.scope,
            path="resource.scope",
        )
    except TenantIsolationError:
        return decision(
            "deny",
            "scope_mismatch",
            "resource tenant/project scope does not match request scope",
        )

    if not request.actor.is_bound_to(request.scope):
        return decision(
            "deny",
            "actor_scope_denied",
            "actor identity is not bound to the requested tenant/project",
        )

    failure = _identity_failure(
        request.actor,
        request.evaluated_at_epoch,
        "actor",
    )
    if failure is not None:
        return decision("deny", failure[0], failure[1])

    if rule is None:
        return decision(
            "deny",
            "no_policy_rule",
            "no authorization rule exists for the requested action",
        )

    if request.actor.actor_type not in rule.allowed_actor_types:
        return decision(
            "deny",
            "actor_type_denied",
            "actor type is not allowed for this action",
        )

    if not (request.actor.roles & rule.allowed_roles):
        return decision(
            "deny",
            "role_denied",
            "actor has no role allowed for this action",
        )

    if _DATA_RANK[request.data_classification] > _DATA_RANK[request.actor.data_clearance]:
        return decision(
            "deny",
            "data_clearance_denied",
            "requested data classification exceeds actor clearance",
        )

    if _DATA_RANK[request.data_classification] > _DATA_RANK[rule.max_data_classification]:
        return decision(
            "deny",
            "rule_data_limit_denied",
            "requested data classification exceeds the policy-rule limit",
        )

    approval_threshold = rule.distinct_approval_at_risk
    requires_approval = (
        approval_threshold is not None
        and _RISK_RANK[effective_risk] >= _RISK_RANK[approval_threshold]
    )
    if not requires_approval:
        return decision("allow", "authorized", "policy authorizes the request")

    approver = request.approver
    if approver is None:
        return decision(
            "requires_approval",
            "distinct_approval_required",
            "effective risk requires a distinct authorized approver",
        )
    if approver.principal_id == request.actor.principal_id:
        return decision(
            "requires_approval",
            "self_approval_forbidden",
            "high-risk approval must come from a distinct principal",
        )
    if not approver.is_bound_to(request.scope):
        return decision(
            "requires_approval",
            "approver_scope_denied",
            "approver is not bound to the requested tenant/project",
        )
    approver_failure = _identity_failure(
        approver,
        request.evaluated_at_epoch,
        "approver",
    )
    if approver_failure is not None:
        return decision(
            "requires_approval",
            approver_failure[0],
            approver_failure[1],
        )
    if approver.actor_type not in rule.approval_actor_types:
        return decision(
            "requires_approval",
            "approver_type_denied",
            "approver actor type is not allowed by policy",
        )
    if not (approver.roles & rule.approval_roles):
        return decision(
            "requires_approval",
            "approver_role_denied",
            "approver has no role allowed for this approval",
        )
    if _DATA_RANK[request.data_classification] > _DATA_RANK[approver.data_clearance]:
        return decision(
            "requires_approval",
            "approver_clearance_denied",
            "requested data classification exceeds approver clearance",
        )

    return decision(
        "allow",
        "authorized_with_distinct_approval",
        "policy authorizes the request with distinct approval",
        approved_by=approver.principal_id,
        approval_reference=request.approval_reference,
    )
