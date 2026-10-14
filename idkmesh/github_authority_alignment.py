"""Cross-configuration authority alignment audit for GitHub dispatch (C10, #598).

Two independently maintained configurations answer related questions about the
same GitHub actors:

- :class:`idkmesh.enterprise_identity_github.GithubIdentityBindingTable`
  (E3-B) binds a numeric actor id to enterprise roles, scopes and freshness;
  :func:`idkmesh.enterprise_authz.authorize` consumes it.
- :class:`idkmesh.github_dispatch_authorization.GitHubDispatchAuthorizationPolicy`
  (C5-F) lists the trusted actors that may cross the issue-label dispatch gate.

Until now they were kept in agreement only by one acceptance test. This module
is a pure, deterministic, read-only audit that compares them and reports every
divergence as a structured finding. It never resolves a secret, never calls
GitHub, never mutates either configuration and never grants authority: an
"aligned" report is evidence about configuration consistency, not an
authorization decision. The two authority paths remain separate and both must
still permit an action.

Findings with severity ``error`` describe an actor that can pass one gate while
the other configuration contradicts or cannot back that authority. Findings
with severity ``warning`` describe configuration drift that fails closed (one
gate would refuse an actor the other would admit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from idkmesh.enterprise_authz import AuthorizationPolicy
from idkmesh.enterprise_identity_github import (
    GithubIdentityBinding,
    GithubIdentityBindingTable,
)
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    TrustedGitHubActor,
)
from idkmesh.tenant_scope import TenantScope

ALIGNMENT_REPORT_KIND = "idkmesh-github-authority-alignment-report"
ALIGNMENT_REPORT_VERSION = "0.1"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# A C5 trusted-actor role is a maintainer-owned statement about what kind of
# principal the actor is. Humans hold owner/maintainer/triager; only the
# "automation" role is a bot. A mismatch is a configuration or spoofing error.
_BOT_ACTOR_TYPES = frozenset({"github_app", "github_actions"})
_HUMAN_ACTOR_TYPES = frozenset({"human"})

FINDING_CODES = frozenset(
    {
        "dispatch_actor_unbound",
        "dispatch_actor_login_mismatch",
        "dispatch_actor_kind_mismatch",
        "dispatch_actor_binding_revoked",
        "dispatch_actor_binding_expired",
        "dispatch_actor_scope_missing",
        "dispatch_actor_lacks_kernel_dispatch_role",
        "kernel_dispatcher_not_dispatch_gate_trusted",
    }
)


class AuthorityAlignmentError(ValueError):
    """Invalid input to the alignment audit."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


@dataclass(frozen=True, slots=True)
class AlignmentFinding:
    """One divergence between the binding table and the dispatch policy."""

    code: str
    severity: str
    actor_id: int
    message: str

    def __post_init__(self) -> None:
        if self.code not in FINDING_CODES:
            raise AuthorityAlignmentError("invalid_code", "code", "unknown code")
        if self.severity not in (SEVERITY_ERROR, SEVERITY_WARNING):
            raise AuthorityAlignmentError(
                "invalid_severity", "severity", "must be error or warning"
            )
        if (
            isinstance(self.actor_id, bool)
            or not isinstance(self.actor_id, int)
            or self.actor_id < 1
        ):
            raise AuthorityAlignmentError(
                "invalid_actor_id", "actor_id", "must be an integer >= 1"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "actor_id": self.actor_id,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class AlignmentReport:
    """Deterministic audit result; carries no authority."""

    findings: tuple[AlignmentFinding, ...]
    dispatch_actors_checked: int
    bindings_checked: int

    @property
    def aligned(self) -> bool:
        """True only when there is no ``error`` finding."""

        return not any(f.severity == SEVERITY_ERROR for f in self.findings)

    @property
    def clean(self) -> bool:
        """True only when there is no finding of any severity."""

        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": ALIGNMENT_REPORT_KIND,
            "schema_version": ALIGNMENT_REPORT_VERSION,
            "aligned": self.aligned,
            "clean": self.clean,
            "dispatch_actors_checked": self.dispatch_actors_checked,
            "bindings_checked": self.bindings_checked,
            "findings": [finding.to_dict() for finding in self.findings],
            "grants_authority": False,
        }


def _find(
    code: str, severity: str, actor_id: int, message: str
) -> AlignmentFinding:
    return AlignmentFinding(code, severity, actor_id, message)


def _expected_types(actor: TrustedGitHubActor) -> frozenset[str]:
    return _BOT_ACTOR_TYPES if actor.role == "automation" else _HUMAN_ACTOR_TYPES


def _audit_dispatch_actor(
    actor: TrustedGitHubActor,
    binding: GithubIdentityBinding | None,
    *,
    can_cross_gate: bool,
    dispatch_roles: frozenset[str],
    dispatch_actor_types: frozenset[str],
    scope: TenantScope | None,
    now_epoch: int | None,
) -> list[AlignmentFinding]:
    findings: list[AlignmentFinding] = []
    if binding is None:
        findings.append(
            _find(
                "dispatch_actor_unbound",
                SEVERITY_ERROR,
                actor.actor_id,
                "trusted dispatch actor has no reviewed identity binding",
            )
        )
        return findings

    context = binding.context
    if binding.login.casefold() != actor.login.casefold():
        findings.append(
            _find(
                "dispatch_actor_login_mismatch",
                SEVERITY_ERROR,
                actor.actor_id,
                "binding table and dispatch policy name different logins "
                "for this actor id",
            )
        )
    if context.actor_type not in _expected_types(actor):
        findings.append(
            _find(
                "dispatch_actor_kind_mismatch",
                SEVERITY_ERROR,
                actor.actor_id,
                f"dispatch role {actor.role!r} is inconsistent with bound "
                f"actor_type {context.actor_type!r}",
            )
        )
    if context.revoked:
        findings.append(
            _find(
                "dispatch_actor_binding_revoked",
                SEVERITY_ERROR,
                actor.actor_id,
                "dispatch actor's identity binding is revoked",
            )
        )
    if (
        now_epoch is not None
        and context.expires_at_epoch is not None
        and now_epoch >= context.expires_at_epoch
    ):
        findings.append(
            _find(
                "dispatch_actor_binding_expired",
                SEVERITY_ERROR,
                actor.actor_id,
                "dispatch actor's identity binding has expired",
            )
        )
    if scope is not None and not context.is_bound_to(scope):
        findings.append(
            _find(
                "dispatch_actor_scope_missing",
                SEVERITY_ERROR,
                actor.actor_id,
                "dispatch actor's identity binding is not bound to the "
                "audited tenant/project scope",
            )
        )
    # Only an actor that can actually cross the label gate needs the kernel to
    # back that authority; a trusted-but-role-disallowed actor is refused by
    # the C5 gate itself.
    if can_cross_gate and (
        not (context.roles & dispatch_roles)
        or context.actor_type not in dispatch_actor_types
    ):
        findings.append(
            _find(
                "dispatch_actor_lacks_kernel_dispatch_role",
                SEVERITY_ERROR,
                actor.actor_id,
                "actor can cross the label dispatch gate but holds no role "
                "that the authorization policy allows to dispatch",
            )
        )
    return findings


def audit_dispatch_authority_alignment(
    table: GithubIdentityBindingTable,
    dispatch_policy: GitHubDispatchAuthorizationPolicy,
    *,
    authorization_policy: AuthorizationPolicy | None = None,
    scope: TenantScope | None = None,
    now_epoch: int | None = None,
) -> AlignmentReport:
    """Compare the identity binding table with the C5 dispatch trusted list.

    ``authorization_policy`` defaults to the enterprise baseline. ``scope``
    and ``now_epoch`` are optional; scope and expiry findings are produced
    only when they are supplied, so the audit never invents a clock or scope.
    The result is ordered by ``(actor_id, code)`` and is therefore
    deterministic for equal inputs.
    """

    if not isinstance(table, GithubIdentityBindingTable):
        raise AuthorityAlignmentError(
            "invalid_table", "table", "must be GithubIdentityBindingTable"
        )
    if not isinstance(dispatch_policy, GitHubDispatchAuthorizationPolicy):
        raise AuthorityAlignmentError(
            "invalid_policy",
            "dispatch_policy",
            "must be GitHubDispatchAuthorizationPolicy",
        )
    if authorization_policy is None:
        authorization_policy = AuthorizationPolicy.enterprise_baseline()
    elif not isinstance(authorization_policy, AuthorizationPolicy):
        raise AuthorityAlignmentError(
            "invalid_authorization_policy",
            "authorization_policy",
            "must be AuthorizationPolicy",
        )
    if scope is not None and not isinstance(scope, TenantScope):
        raise AuthorityAlignmentError("invalid_scope", "scope", "must be TenantScope")
    if now_epoch is not None and (
        isinstance(now_epoch, bool)
        or not isinstance(now_epoch, int)
        or now_epoch < 0
    ):
        raise AuthorityAlignmentError(
            "invalid_epoch", "now_epoch", "must be an integer >= 0"
        )

    rule = authorization_policy.rule_for("dispatch")
    if rule is None:
        # No dispatch rule means the kernel can never allow dispatch; every
        # actor that can cross the label gate is unbacked.
        dispatch_roles: frozenset[str] = frozenset()
        dispatch_actor_types: frozenset[str] = frozenset()
    else:
        dispatch_roles = rule.allowed_roles
        dispatch_actor_types = rule.allowed_actor_types

    findings: list[AlignmentFinding] = []
    trusted_ids = {actor.actor_id for actor in dispatch_policy.trusted_actors}
    gate_ids = {
        actor.actor_id
        for actor in dispatch_policy.trusted_actors
        if actor.role in dispatch_policy.allowed_roles
    }

    for actor in dispatch_policy.trusted_actors:
        findings.extend(
            _audit_dispatch_actor(
                actor,
                table.by_actor_id(actor.actor_id),
                can_cross_gate=actor.actor_id in gate_ids,
                dispatch_roles=dispatch_roles,
                dispatch_actor_types=dispatch_actor_types,
                scope=scope,
                now_epoch=now_epoch,
            )
        )

    for binding in table.bindings:
        if binding.actor_id in gate_ids:
            continue
        ctx = binding.context
        if (
            ctx.roles & dispatch_roles
            and ctx.actor_type in dispatch_actor_types
            and not ctx.revoked
        ):
            findings.append(
                _find(
                    "kernel_dispatcher_not_dispatch_gate_trusted",
                    SEVERITY_WARNING,
                    binding.actor_id,
                    "binding holds a kernel dispatch role but cannot cross "
                    "the label dispatch gate"
                    + (
                        " (trusted with a role the gate does not allow)"
                        if binding.actor_id in trusted_ids
                        else " (not in the trusted actor list)"
                    ),
                )
            )

    findings.sort(key=lambda f: (f.actor_id, f.code))
    return AlignmentReport(
        findings=tuple(findings),
        dispatch_actors_checked=len(dispatch_policy.trusted_actors),
        bindings_checked=len(table.bindings),
    )
