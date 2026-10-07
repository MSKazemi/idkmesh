"""Tests for the C12-A GitHub governance policy contract."""

from __future__ import annotations

import json
import unittest

from idkmesh.github_governance_policy import (
    OPERATIONS,
    GitHubGovernanceGuard,
    GitHubGovernancePolicy,
    GitHubGovernancePolicyError,
    build_github_governance_policy,
)


class GitHubGovernancePolicyTests(unittest.TestCase):
    def test_policy_is_deterministic_and_json_safe(self) -> None:
        first = build_github_governance_policy()
        second = build_github_governance_policy()
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")),
            json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    def test_policy_has_no_admin_or_independence_authority(self) -> None:
        policy = build_github_governance_policy()
        self.assertFalse(policy.automatic_admin_mutation)
        self.assertFalse(policy.ruleset_proves_independent_review)

    def test_every_operation_has_explicit_guards(self) -> None:
        policy = build_github_governance_policy()
        for operation in sorted(OPERATIONS):
            with self.subTest(operation=operation):
                self.assertTrue(policy.guards_for(operation))

    def test_read_only_requires_least_privilege_not_branch_admin(self) -> None:
        codes = {
            guard.code
            for guard in build_github_governance_policy().guards_for(
                "read_only"
            )
        }
        self.assertIn("actions-default-contents-read", codes)
        self.assertIn("checkout-persist-credentials-disabled", codes)
        self.assertNotIn("pull-request-integration", codes)
        self.assertNotIn("force-push-blocked", codes)

    def test_candidate_dispatch_requires_protected_integration(self) -> None:
        guards = build_github_governance_policy().guards_for(
            "candidate_dispatch"
        )
        unconditional_required = {
            guard.code
            for guard in guards
            if guard.requirement == "required" and not guard.conditions
        }
        self.assertTrue(
            {
                "pull-request-integration",
                "force-push-blocked",
                "branch-deletion-blocked",
                "narrow-bypass-actors",
            }.issubset(unconditional_required)
        )

    def test_secret_bearing_dispatch_has_hard_secret_isolation(self) -> None:
        guards = {
            guard.code: guard
            for guard in build_github_governance_policy().guards_for(
                "secret_bearing_dispatch"
            )
        }
        self.assertEqual(
            guards["high-risk-environment-approval"].requirement,
            "required",
        )
        self.assertEqual(
            guards["untrusted-pr-secret-isolation"].requirement,
            "required",
        )
        self.assertIn(
            "untrusted_pr_execution_present",
            guards["untrusted-pr-secret-isolation"].conditions,
        )
        self.assertEqual(
            guards["environment-self-review-prevented"].requirement,
            "warn",
        )

    def test_oidc_is_optional_and_cloud_only(self) -> None:
        guard = next(
            guard
            for guard in build_github_governance_policy().guards
            if guard.code == "oidc-short-lived-cloud-auth"
        )
        self.assertEqual(guard.requirement, "optional")
        self.assertEqual(guard.applies_to, ("cloud_dispatch",))
        self.assertEqual(guard.availability, "provider_dependent")

    def test_required_checks_are_conditional_on_declared_checks(self) -> None:
        guard = next(
            guard
            for guard in build_github_governance_policy().guards
            if guard.code == "required-checks-enforced"
        )
        self.assertEqual(guard.requirement, "required")
        self.assertEqual(guard.conditions, ("required_checks_declared",))

    def test_unknown_operation_fails_closed(self) -> None:
        with self.assertRaises(GitHubGovernancePolicyError) as caught:
            build_github_governance_policy().guards_for("merge_everything")
        self.assertEqual(caught.exception.code, "unknown_governed_operation")

    def test_policy_cannot_enable_admin_mutation(self) -> None:
        guard = GitHubGovernanceGuard(
            code="example-guard",
            requirement="required",
            summary="Example guard.",
            applies_to=("read_only",),
            observation_sources=("workflow_source",),
        )
        with self.assertRaises(GitHubGovernancePolicyError) as caught:
            GitHubGovernancePolicy(
                version="0.1",
                profile="github-first-governance-v0.1",
                guards=(guard,),
                automatic_admin_mutation=True,
            )
        self.assertEqual(caught.exception.code, "admin_mutation_forbidden")

    def test_policy_cannot_claim_ruleset_proves_independence(self) -> None:
        guard = GitHubGovernanceGuard(
            code="example-guard",
            requirement="warn",
            summary="Example guard.",
            applies_to=("integration",),
            observation_sources=("repository_rules",),
        )
        with self.assertRaises(GitHubGovernancePolicyError) as caught:
            GitHubGovernancePolicy(
                version="0.1",
                profile="github-first-governance-v0.1",
                guards=(guard,),
                ruleset_proves_independent_review=True,
            )
        self.assertEqual(
            caught.exception.code,
            "independence_overclaim_forbidden",
        )

    def test_unknown_guard_vocabulary_fails_closed(self) -> None:
        cases = (
            (
                {"requirement": "ignore"},
                "unknown_requirement_level",
            ),
            (
                {"applies_to": ("unknown",)},
                "unknown_policy_value",
            ),
            (
                {"observation_sources": ("magic_api",)},
                "unknown_policy_value",
            ),
            (
                {"conditions": ("trust_me",)},
                "unknown_policy_value",
            ),
            (
                {"availability": "guaranteed"},
                "unknown_availability_class",
            ),
        )
        for overrides, code in cases:
            with self.subTest(code=code):
                values = {
                    "code": "example-guard",
                    "requirement": "required",
                    "summary": "Example guard.",
                    "applies_to": ("read_only",),
                    "observation_sources": ("workflow_source",),
                }
                values.update(overrides)
                with self.assertRaises(GitHubGovernancePolicyError) as caught:
                    GitHubGovernanceGuard(**values)
                self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
