"""Declarative GitHub governance policy for C12-A / issue 607.

This module defines policy only. It performs no GitHub API calls, reads no
secrets, mutates no repository settings, and grants no dispatch, verification,
acceptance, integration, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


POLICY_VERSION = "0.1"
PROFILE = "github-first-governance-v0.1"

REQUIREMENTS = frozenset({"required", "warn", "optional"})
OPERATIONS = frozenset(
    {
        "read_only",
        "candidate_dispatch",
        "secret_bearing_dispatch",
        "high_risk_dispatch",
        "cloud_dispatch",
        "integration",
    }
)
SOURCES = frozenset(
    {
        "repository_rules",
        "workflow_source",
        "environment_settings",
        "codeowners",
        "connector_configuration",
    }
)
CONDITIONS = frozenset(
    {
        "checkout_without_push",
        "codeowners_configured",
        "environment_protection_supported",
        "required_checks_declared",
        "risk_medium_or_higher",
        "security_sensitive_lane",
        "sensitive_paths",
        "untrusted_pr_execution_present",
    }
)
AVAILABILITY = frozenset(
    {"universal", "plan_or_repository_dependent", "provider_dependent"}
)


class GitHubGovernancePolicyError(ValueError):
    """Stable fail-closed policy-construction error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _validate_values(
    values: tuple[str, ...],
    allowed: frozenset[str],
    field: str,
    *,
    allow_empty: bool = False,
) -> None:
    if not isinstance(values, tuple):
        raise GitHubGovernancePolicyError(
            "invalid_policy_field", f"{field} must be a tuple"
        )
    if not allow_empty and not values:
        raise GitHubGovernancePolicyError(
            "invalid_policy_field", f"{field} must not be empty"
        )
    if len(values) != len(set(values)):
        raise GitHubGovernancePolicyError(
            "duplicate_policy_value", f"{field} contains duplicates"
        )
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise GitHubGovernancePolicyError(
            "unknown_policy_value",
            f"{field} contains unsupported values: {', '.join(unknown)}",
        )


@dataclass(frozen=True)
class GitHubGovernanceGuard:
    code: str
    requirement: str
    summary: str
    applies_to: tuple[str, ...]
    observation_sources: tuple[str, ...]
    conditions: tuple[str, ...] = ()
    availability: str = "universal"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.code, str)
            or len(self.code) < 3
            or not self.code.replace("-", "").isalnum()
            or self.code.lower() != self.code
            or self.code[0].isdigit()
        ):
            raise GitHubGovernancePolicyError(
                "invalid_guard_code", "guard code must be lowercase kebab-case"
            )
        if self.requirement not in REQUIREMENTS:
            raise GitHubGovernancePolicyError(
                "unknown_requirement_level",
                f"{self.code}: unsupported requirement {self.requirement!r}",
            )
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise GitHubGovernancePolicyError(
                "invalid_guard_summary",
                f"{self.code}: summary must be non-empty",
            )
        _validate_values(self.applies_to, OPERATIONS, f"{self.code}.applies_to")
        _validate_values(
            self.observation_sources,
            SOURCES,
            f"{self.code}.observation_sources",
        )
        _validate_values(
            self.conditions,
            CONDITIONS,
            f"{self.code}.conditions",
            allow_empty=True,
        )
        if self.availability not in AVAILABILITY:
            raise GitHubGovernancePolicyError(
                "unknown_availability_class",
                f"{self.code}: unsupported availability {self.availability!r}",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "requirement": self.requirement,
            "summary": self.summary,
            "applies_to": sorted(self.applies_to),
            "observation_sources": sorted(self.observation_sources),
            "conditions": sorted(self.conditions),
            "availability": self.availability,
        }


@dataclass(frozen=True)
class GitHubGovernancePolicy:
    version: str
    profile: str
    guards: tuple[GitHubGovernanceGuard, ...]
    automatic_admin_mutation: bool = False
    ruleset_proves_independent_review: bool = False

    def __post_init__(self) -> None:
        if self.version != POLICY_VERSION:
            raise GitHubGovernancePolicyError(
                "unsupported_policy_version", f"expected {POLICY_VERSION}"
            )
        if self.profile != PROFILE:
            raise GitHubGovernancePolicyError(
                "unsupported_policy_profile", f"expected {PROFILE}"
            )
        if not self.guards:
            raise GitHubGovernancePolicyError(
                "empty_governance_policy", "at least one guard is required"
            )
        codes = [guard.code for guard in self.guards]
        if len(codes) != len(set(codes)):
            raise GitHubGovernancePolicyError(
                "duplicate_guard_code", "guard codes must be unique"
            )
        if self.automatic_admin_mutation is not False:
            raise GitHubGovernancePolicyError(
                "admin_mutation_forbidden",
                "policy cannot authorize automatic GitHub admin mutation",
            )
        if self.ruleset_proves_independent_review is not False:
            raise GitHubGovernancePolicyError(
                "independence_overclaim_forbidden",
                "ruleset metadata alone cannot prove independent review",
            )

    def guards_for(self, operation: str) -> tuple[GitHubGovernanceGuard, ...]:
        if operation not in OPERATIONS:
            raise GitHubGovernancePolicyError(
                "unknown_governed_operation",
                f"unsupported operation {operation!r}",
            )
        return tuple(
            guard for guard in self.guards if operation in guard.applies_to
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile": self.profile,
            "automatic_admin_mutation": self.automatic_admin_mutation,
            "ruleset_proves_independent_review": (
                self.ruleset_proves_independent_review
            ),
            "guards": [guard.to_dict() for guard in self.guards],
        }


def _guard(
    code: str,
    requirement: str,
    summary: str,
    *,
    applies_to: tuple[str, ...],
    sources: tuple[str, ...],
    conditions: tuple[str, ...] = (),
    availability: str = "universal",
) -> GitHubGovernanceGuard:
    return GitHubGovernanceGuard(
        code=code,
        requirement=requirement,
        summary=summary,
        applies_to=applies_to,
        observation_sources=sources,
        conditions=conditions,
        availability=availability,
    )


def build_github_governance_policy() -> GitHubGovernancePolicy:
    """Build the canonical C12-A GitHub-first governance baseline."""

    protected = (
        "candidate_dispatch",
        "cloud_dispatch",
        "high_risk_dispatch",
        "integration",
        "secret_bearing_dispatch",
    )
    workflows = (
        "candidate_dispatch",
        "cloud_dispatch",
        "high_risk_dispatch",
        "read_only",
        "secret_bearing_dispatch",
    )
    secret_bearing = (
        "cloud_dispatch",
        "high_risk_dispatch",
        "secret_bearing_dispatch",
    )

    guards = (
        _guard(
            "actions-default-contents-read",
            "required",
            "Workflow token defaults to contents read.",
            applies_to=workflows,
            sources=("workflow_source",),
        ),
        _guard(
            "branch-deletion-blocked",
            "required",
            "Protected integration branch deletion is blocked.",
            applies_to=protected,
            sources=("repository_rules",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "checkout-persist-credentials-disabled",
            "required",
            "Checkout does not persist credentials when push is unnecessary.",
            applies_to=workflows,
            sources=("workflow_source",),
            conditions=("checkout_without_push",),
        ),
        _guard(
            "codeowner-review-enforced",
            "required",
            "Configured CODEOWNERS review is enforced on sensitive paths.",
            applies_to=protected,
            sources=("codeowners", "repository_rules"),
            conditions=("codeowners_configured", "sensitive_paths"),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "force-push-blocked",
            "required",
            "Force pushes are blocked on protected integration.",
            applies_to=protected,
            sources=("repository_rules",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "high-risk-environment-approval",
            "required",
            "Secret-bearing or high-risk work crosses an approval boundary before secrets.",
            applies_to=secret_bearing,
            sources=("environment_settings", "workflow_source"),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "immutable-security-actions",
            "required",
            "Security-sensitive third-party actions use immutable revisions.",
            applies_to=secret_bearing,
            sources=("workflow_source",),
            conditions=("security_sensitive_lane",),
        ),
        _guard(
            "narrow-bypass-actors",
            "required",
            "Ruleset bypass authority is absent or narrowly scoped.",
            applies_to=protected,
            sources=("repository_rules",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "pull-request-integration",
            "required",
            "Canonical integration requires pull requests.",
            applies_to=protected,
            sources=("repository_rules",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "required-checks-enforced",
            "required",
            "Declared stable required checks are enforced.",
            applies_to=protected,
            sources=("repository_rules",),
            conditions=("required_checks_declared",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "risk-review-required",
            "required",
            "Medium or higher risk work crosses the configured review boundary.",
            applies_to=protected,
            sources=("repository_rules",),
            conditions=("risk_medium_or_higher",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "untrusted-pr-secret-isolation",
            "required",
            "Untrusted PR execution cannot reach secret-bearing privileged jobs.",
            applies_to=secret_bearing,
            sources=("workflow_source",),
            conditions=("untrusted_pr_execution_present",),
        ),
        _guard(
            "environment-self-review-prevented",
            "warn",
            "Environment approval prevents self-review where supported.",
            applies_to=secret_bearing,
            sources=("environment_settings",),
            conditions=("environment_protection_supported",),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "sensitive-path-codeowners",
            "warn",
            "Sensitive control-plane paths have scoped CODEOWNERS guidance.",
            applies_to=protected,
            sources=("codeowners",),
            conditions=("sensitive_paths",),
        ),
        _guard(
            "stable-ci-checks-present",
            "warn",
            "At least one understood stable integration check is available.",
            applies_to=protected,
            sources=("repository_rules", "workflow_source"),
            availability="plan_or_repository_dependent",
        ),
        _guard(
            "oidc-short-lived-cloud-auth",
            "optional",
            "Cloud dispatch prefers OIDC short-lived identity.",
            applies_to=("cloud_dispatch",),
            sources=("connector_configuration", "workflow_source"),
            availability="provider_dependent",
        ),
    )

    return GitHubGovernancePolicy(
        version=POLICY_VERSION,
        profile=PROFILE,
        guards=tuple(sorted(guards, key=lambda guard: guard.code)),
    )
