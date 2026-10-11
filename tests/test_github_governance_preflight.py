from __future__ import annotations

import json
from pathlib import Path
import unittest

import idkmesh.github_governance_preflight as preflight
from idkmesh.github_governance_policy import build_github_governance_policy

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "github-governance"


def complete_observation() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "repository_rules": {
            "pull_request_integration": True, "force_push_blocked": True,
            "branch_deletion_blocked": True, "narrow_bypass_actors": True,
            "required_checks_enforced": True, "risk_review_required": True,
            "codeowner_review_required": True, "stable_ci_checks_present": True,
        },
        "environment_settings": {"approval_required": True, "prevent_self_review": True},
        "codeowners": {"configured": True, "sensitive_paths_covered": True},
        "connector_configuration": {"uses_oidc": True},
        "workflow_source": {
            "actions_default_contents_read": True,
            "checkout_persist_credentials_disabled": True,
            "immutable_security_actions": True,
            "untrusted_pr_secret_isolation": True,
            "environment_bound": True,
            "oidc_token_permission": True,
        },
        "conditions": {condition: True for condition in build_github_governance_policy().guards[0].conditions},
        "unknown_reasons": {},
    }


def with_all_conditions(observation: dict[str, object]) -> dict[str, object]:
    observation["conditions"] = {
        "checkout_without_push": True,
        "codeowners_configured": True,
        "environment_protection_supported": True,
        "required_checks_declared": True,
        "risk_medium_or_higher": True,
        "security_sensitive_lane": True,
        "sensitive_paths": True,
        "untrusted_pr_execution_present": True,
    }
    return observation


class GitHubGovernancePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = with_all_conditions(complete_observation())

    def test_every_policy_guard_is_mapped(self) -> None:
        self.assertEqual(
            {guard.code for guard in build_github_governance_policy().guards},
            set(preflight.GUARD_INPUTS),
        )

    def test_complete_integration_passes_without_admin_authority(self) -> None:
        report = preflight.evaluate_governance("integration", self.observation)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["operation_allowed"])
        self.assertFalse(report["automatic_admin_mutation"])
        self.assertFalse(report["ruleset_proves_independent_review"])

    def test_required_false_fails_and_unknown_blocks(self) -> None:
        self.observation["repository_rules"]["force_push_blocked"] = False
        report = preflight.evaluate_governance("integration", self.observation)
        self.assertEqual(report["status"], "FAIL")
        with self.assertRaises(preflight.GitHubGovernancePreflightError):
            preflight.require_governance("integration", self.observation)

        self.observation = with_all_conditions(complete_observation())
        del self.observation["repository_rules"]["force_push_blocked"]
        report = preflight.evaluate_governance("integration", self.observation)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertFalse(report["operation_allowed"])

    def test_false_condition_is_not_applicable_but_missing_condition_is_unknown(self) -> None:
        self.observation["conditions"]["required_checks_declared"] = False
        report = preflight.evaluate_governance("integration", self.observation)
        row = next(r for r in report["guards"] if r["code"] == "required-checks-enforced")
        self.assertEqual(row["status"], "NOT_APPLICABLE")

        self.observation = with_all_conditions(complete_observation())
        del self.observation["conditions"]["required_checks_declared"]
        report = preflight.evaluate_governance("integration", self.observation)
        row = next(r for r in report["guards"] if r["code"] == "required-checks-enforced")
        self.assertEqual(row["status"], "UNKNOWN")

    def test_read_only_does_not_inherit_integration_guards(self) -> None:
        self.observation["repository_rules"]["force_push_blocked"] = False
        self.assertEqual(preflight.evaluate_governance("read_only", self.observation)["status"], "PASS")

    def test_unobserved_warn_and_optional_guards_do_not_block(self) -> None:
        del self.observation["environment_settings"]["prevent_self_review"]
        del self.observation["connector_configuration"]["uses_oidc"]
        del self.observation["workflow_source"]["oidc_token_permission"]

        report = preflight.evaluate_governance("cloud_dispatch", self.observation)
        rows = {row["code"]: row for row in report["guards"]}

        self.assertEqual(rows["environment-self-review-prevented"]["status"], "WARN")
        self.assertEqual(rows["oidc-short-lived-cloud-auth"]["status"], "WARN")
        self.assertEqual(report["status"], "WARN")
        self.assertTrue(report["operation_allowed"])
        self.assertEqual(
            preflight.require_governance("cloud_dispatch", self.observation)["status"],
            "WARN",
        )

    def test_unobserved_warn_condition_does_not_block(self) -> None:
        del self.observation["conditions"]["environment_protection_supported"]

        report = preflight.evaluate_governance("cloud_dispatch", self.observation)
        row = next(
            item
            for item in report["guards"]
            if item["code"] == "environment-self-review-prevented"
        )

        self.assertEqual(row["status"], "WARN")
        self.assertTrue(report["operation_allowed"])

    def test_input_validation_fails_closed(self) -> None:
        with self.assertRaises(preflight.GitHubGovernancePreflightError) as caught:
            preflight.parse_observation_text('{"schema_version":"0.1","schema_version":"0.1"}')
        self.assertEqual(caught.exception.code, "duplicate_json_key")
        self.observation["repository_rules"]["invented"] = True
        with self.assertRaises(preflight.GitHubGovernancePreflightError):
            preflight.validate_observation(self.observation)
        with self.assertRaises(preflight.GitHubGovernancePreflightError) as caught:
            preflight.parse_observation_text(None)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "invalid_observation_text")
        with self.assertRaises(preflight.GitHubGovernancePreflightError) as caught:
            preflight.lint_workflow_text(None)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "invalid_workflow_source")

    def test_committed_observation_fixture_is_deterministic(self) -> None:
        text = (EXAMPLES / "governance-pass-v0.1.json").read_text(encoding="utf-8")
        self.assertEqual(preflight.parse_observation_text(text), preflight.parse_observation_text(text))
        self.assertEqual(preflight.evaluate_governance("integration", json.loads(text))["status"], "PASS")

    def test_read_only_workflow_is_least_privilege_and_secret_free(self) -> None:
        source = (EXAMPLES / "read-only-lane.yml").read_text(encoding="utf-8")
        report = preflight.lint_workflow_text(source)
        self.assertEqual(report["findings"], [])
        self.assertNotIn("secrets.", source)
        self.assertNotIn("id-token: write", source)

    def test_oidc_example_passes_shape_check(self) -> None:
        source = (EXAMPLES / "oidc-cloud-dispatch.yml").read_text(encoding="utf-8")
        self.assertEqual(preflight.lint_workflow_text(source)["findings"], [])
        self.assertEqual(preflight.oidc_preflight(source)["status"], "PASS")

    def test_unsafe_pr_workflow_reports_all_critical_findings(self) -> None:
        source = """on:\n  pull_request_target:\npermissions: write-all\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo '${{ secrets.CLOUD_KEY }}'\n"""
        codes = {f["code"] for f in preflight.lint_workflow_text(source)["findings"]}
        self.assertTrue({
            "actions-default-contents-read", "immutable-security-actions",
            "checkout-persist-credentials-disabled", "untrusted-pr-secret-isolation",
        }.issubset(codes))

    def test_inline_pr_trigger_and_bracket_secret_are_isolated(self) -> None:
        secret_expr = "$" + "{{ secrets['PROVIDER_TOKEN'] }}"
        source = f"""on: [push, pull_request]
permissions:
  contents: read
jobs:
  t:
    runs-on: ubuntu-latest
    steps:
      - uses: "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
        with:
          persist-credentials: false
      - run: echo "{secret_expr}"
"""
        report = preflight.lint_workflow_text(source)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("untrusted-pr-secret-isolation", codes)
        self.assertNotIn("checkout-persist-credentials-disabled", codes)

    def test_permission_and_environment_lookalikes_do_not_count(self) -> None:
        source = """on: workflow_dispatch
permissions:
  contents: read
env:
    environment: top-level-variable
jobs:
  t:
    runs-on: ubuntu-latest
    env:
      id-token: write
      environment: production
    steps:
      - run: echo safe
"""
        observed = preflight.lint_workflow_text(source)["workflow_source"]
        self.assertFalse(observed["oidc_token_permission"])
        self.assertFalse(observed["environment_bound"])

    def test_job_write_all_permission_is_not_least_privilege(self) -> None:
        source = """on: workflow_dispatch
permissions:
  contents: read
jobs:
  t:
    permissions: write-all
    runs-on: ubuntu-latest
    steps:
      - run: echo unsafe
"""
        report = preflight.lint_workflow_text(source)
        self.assertIn(
            "actions-default-contents-read",
            {item["code"] for item in report["findings"]},
        )

    def test_pr_reusable_workflow_secrets_inherit_comment_is_detected(self) -> None:
        source = """on: [pull_request]
permissions:
  contents: read
jobs:
  call:
    uses: org/repo/.github/workflows/reusable.yml@11d5960a326750d5838078e36cf38b85af677262
    secrets: inherit # forwards caller secrets
"""
        report = preflight.lint_workflow_text(source)
        self.assertIn(
            "untrusted-pr-secret-isolation",
            {item["code"] for item in report["findings"]},
        )

    def test_pull_request_target_github_head_ref_is_privileged_head(self) -> None:
        head_expr = "$" + "{{ github.head_ref }}"
        source = f"""on:
  pull_request_target:
permissions:
  contents: read
jobs:
  t:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
          ref: "{head_expr}"
"""
        report = preflight.lint_workflow_text(source)
        self.assertIn(
            "untrusted-pr-secret-isolation",
            {item["code"] for item in report["findings"]},
        )

    def test_job_level_oidc_permission_and_environment_are_detected(self) -> None:
        source = """on: workflow_dispatch
permissions:
  contents: read
jobs:
  t:
    permissions:
      contents: read
      id-token: write
    runs-on: ubuntu-latest
    environment: production
    steps:
      - run: echo safe
"""
        observed = preflight.lint_workflow_text(source)["workflow_source"]
        self.assertTrue(observed["oidc_token_permission"])
        self.assertTrue(observed["environment_bound"])

    def test_malformed_docker_digest_is_not_immutable(self) -> None:
        source = """on: workflow_dispatch
permissions:
  contents: read
jobs:
  t:
    runs-on: ubuntu-latest
    steps:
      - uses: docker://example.invalid/tool@sha256:not-a-digest
"""
        report = preflight.lint_workflow_text(source)
        self.assertIn(
            "immutable-security-actions",
            {item["code"] for item in report["findings"]},
        )

    def test_oidc_rejects_bracket_form_long_lived_cloud_secret(self) -> None:
        secret_expr = "$" + "{{ secrets['AWS_SECRET_ACCESS_KEY'] }}"
        source = (EXAMPLES / "oidc-cloud-dispatch.yml").read_text(encoding="utf-8")
        source += f"\n# {secret_expr}\n"
        self.assertEqual(preflight.oidc_preflight(source)["status"], "FAIL")

    def test_multiple_workflows_merge_conservatively(self) -> None:
        good = (EXAMPLES / "read-only-lane.yml").read_text(encoding="utf-8")
        bad = good.replace("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", "actions/checkout@v4")
        merged = preflight.merge_workflow_lints(
            self.observation,
            [preflight.lint_workflow_text(good), preflight.lint_workflow_text(bad)],
        )
        self.assertFalse(merged["workflow_source"]["immutable_security_actions"])

    def test_codeowners_requires_explicit_owner(self) -> None:
        rendered = preflight.render_codeowners_recommendation("@org/security")
        self.assertIn(".github/workflows/** @org/security", rendered)
        self.assertIn(".idkmesh/** @org/security", rendered)
        with self.assertRaises(preflight.GitHubGovernancePreflightError):
            preflight.render_codeowners_recommendation("security")

    def test_oidc_rejects_long_lived_cloud_secret_reference(self) -> None:
        source = (EXAMPLES / "oidc-cloud-dispatch.yml").read_text(encoding="utf-8")
        source += "\n# ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n"
        report = preflight.oidc_preflight(source)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["long_lived_cloud_secret_reference"])


if __name__ == "__main__":
    unittest.main()
