import json
import unittest

from idkmesh.github_bootstrap import (
    BOOTSTRAP_PLAN_VERSION,
    BootstrapFileSpec,
    BootstrapPlanError,
    GitHubBootstrapPlan,
    OwnerAction,
    build_github_bootstrap_plan,
)


SHA = "1" * 40


class GitHubBootstrapPlanTests(unittest.TestCase):
    def test_canonical_plan_is_deterministic_and_json_safe(self):
        first = build_github_bootstrap_plan(
            idkmesh_ref="v0.1.0",
            default_branch="main",
        )
        second = build_github_bootstrap_plan(
            idkmesh_ref="v0.1.0",
            default_branch="main",
        )

        self.assertEqual(first, second)
        self.assertEqual(first.plan_version, BOOTSTRAP_PLAN_VERSION)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")),
            json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    def test_plan_has_exact_bootstrap_file_set(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        self.assertEqual(
            {item.path for item in plan.files},
            {
                ".idkmesh/README.md",
                ".idkmesh/project.json",
                ".idkmesh/connections.json",
                ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json",
                ".github/workflows/idkmesh-preview.yml",
                ".github/workflows/idkmesh-dispatch.yml",
                ".github/workflows/idkmesh-verify.yml",
                ".github/workflows/idkmesh-status.yml",
            },
        )

    def test_external_project_plan_vendors_repository_local_domain_pack(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        domain = next(
            item
            for item in plan.files
            if item.path.endswith("software-engineering-v0.1.domain-pack.json")
        )
        self.assertTrue(domain.path.startswith(".idkmesh/domain-packs/"))
        self.assertEqual(domain.ownership, "idkmesh_managed")
        self.assertEqual(domain.phase, "C8-C")
        self.assertIn(SHA, domain.render_source)
        self.assertNotIn("http://", domain.render_source)
        self.assertNotIn("https://", domain.render_source)

    def test_user_seed_files_are_create_if_absent_only(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        user_seed = [item for item in plan.files if item.ownership == "user_seed"]
        self.assertEqual(
            {item.path for item in user_seed},
            {".idkmesh/project.json", ".idkmesh/connections.json"},
        )
        self.assertTrue(
            all(item.overwrite_policy == "create_if_absent" for item in user_seed)
        )

    def test_managed_files_require_generated_digest_match_for_replacement(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        managed = [item for item in plan.files if item.ownership == "idkmesh_managed"]
        self.assertTrue(managed)
        self.assertTrue(
            all(
                item.overwrite_policy == "replace_if_generated_digest_matches"
                for item in managed
            )
        )

    def test_no_planned_file_contains_secret_values_or_integration_authority(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        self.assertTrue(
            all(item.secret_values_allowed is False for item in plan.files)
        )
        self.assertTrue(
            all(item.integration_authority is False for item in plan.files)
        )

    def test_only_dispatch_wrapper_declares_candidate_dispatch(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        dispatchers = [
            item.path
            for item in plan.files
            if item.execution_effect == "candidate_dispatch"
        ]
        self.assertEqual(dispatchers, [".github/workflows/idkmesh-dispatch.yml"])

    def test_workflow_effects_are_explicit_not_merge_authority(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        effects = {
            item.path: item.execution_effect
            for item in plan.files
            if item.path.startswith(".github/workflows/")
        }
        self.assertEqual(
            effects,
            {
                ".github/workflows/idkmesh-dispatch.yml": "candidate_dispatch",
                ".github/workflows/idkmesh-preview.yml": "none",
                ".github/workflows/idkmesh-status.yml": "publication",
                ".github/workflows/idkmesh-verify.yml": "verification",
            },
        )

    def test_floating_or_short_idkmesh_refs_fail_closed(self):
        bad_refs = [
            "main",
            "master",
            "latest",
            "HEAD",
            "v0.1",
            "abcdef1",
            "1" * 39,
            "1" * 41,
            "V0.1.0",
        ]
        for ref in bad_refs:
            with self.subTest(ref=ref):
                with self.assertRaises(BootstrapPlanError) as caught:
                    build_github_bootstrap_plan(idkmesh_ref=ref)
                self.assertEqual(caught.exception.code, "unpinned_idkmesh_ref")

    def test_release_tag_and_full_sha_are_valid_pins(self):
        for ref in ("v0.1.0", "v2.10.3-rc.1", "v2.10.3-0.alpha-1", SHA):
            with self.subTest(ref=ref):
                self.assertEqual(
                    build_github_bootstrap_plan(idkmesh_ref=ref).idkmesh_ref,
                    ref,
                )

    def test_release_tag_rejects_non_semantic_versions(self):
        for ref in (
            "v01.2.3",
            "v1.02.3",
            "v1.2.03",
            "v1.2.3-01",
            "v1.2.3-rc.",
            "v1.2.3-rc..1",
        ):
            with self.subTest(ref=ref):
                with self.assertRaises(BootstrapPlanError) as caught:
                    build_github_bootstrap_plan(idkmesh_ref=ref)
                self.assertEqual(caught.exception.code, "unpinned_idkmesh_ref")

    def test_unsafe_default_branch_names_fail_closed(self):
        for branch in (
            "",
            "../main",
            "feature//x",
            "feature/.hidden",
            "feature/main.lock/x",
            "bad branch",
            "main.lock",
            ".main",
        ):
            with self.subTest(branch=branch):
                with self.assertRaises(BootstrapPlanError) as caught:
                    build_github_bootstrap_plan(
                        idkmesh_ref=SHA,
                        default_branch=branch,
                    )
                self.assertEqual(caught.exception.code, "invalid_default_branch")

    def test_owner_actions_are_explicit_and_never_automatic(self):
        plan = build_github_bootstrap_plan(idkmesh_ref=SHA)
        self.assertEqual(
            {item.code for item in plan.owner_actions},
            {
                "authorize-provider-apps",
                "configure-branch-protection",
                "configure-provider-secrets",
                "configure-secret-environments",
            },
        )
        self.assertTrue(
            all(item.requires_repository_owner for item in plan.owner_actions)
        )
        self.assertTrue(all(item.automatic is False for item in plan.owner_actions))

    def test_unsafe_paths_are_rejected(self):
        for path in (
            "/absolute",
            "../escape",
            "a//b",
            "a\\b",
            ".git/config",
            ".GIT/config",
            "safe/.git/config",
            "line\nbreak",
            "control\x1fcharacter",
        ):
            with self.subTest(path=path):
                with self.assertRaises(BootstrapPlanError) as caught:
                    BootstrapFileSpec(
                        path=path,
                        ownership="user_seed",
                        phase="C8-C",
                        overwrite_policy="create_if_absent",
                        purpose="test",
                        render_source="test",
                    )
                self.assertEqual(caught.exception.code, "invalid_path")

    def test_user_seed_cannot_be_declared_overwritable(self):
        with self.assertRaises(BootstrapPlanError) as caught:
            BootstrapFileSpec(
                path=".idkmesh/project.json",
                ownership="user_seed",
                phase="C8-C",
                overwrite_policy="replace_if_generated_digest_matches",
                purpose="test",
                render_source="test",
            )
        self.assertEqual(caught.exception.code, "unsafe_user_overwrite")

    def test_secret_or_integration_authority_flags_fail_closed(self):
        for kwargs, code in (
            ({"secret_values_allowed": True}, "secret_values_forbidden"),
            ({"integration_authority": True}, "integration_authority_forbidden"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(BootstrapPlanError) as caught:
                    BootstrapFileSpec(
                        path=".idkmesh/test.json",
                        ownership="user_seed",
                        phase="C8-C",
                        overwrite_policy="create_if_absent",
                        purpose="test",
                        render_source="test",
                        **kwargs,
                    )
                self.assertEqual(caught.exception.code, code)

    def test_duplicate_paths_fail_closed(self):
        item = BootstrapFileSpec(
            path=".idkmesh/project.json",
            ownership="user_seed",
            phase="C8-C",
            overwrite_policy="create_if_absent",
            purpose="test",
            render_source="test",
        )
        action = OwnerAction(
            code="owner-step",
            summary="owner",
            reason="test",
        )
        with self.assertRaises(BootstrapPlanError) as caught:
            GitHubBootstrapPlan(
                plan_version=BOOTSTRAP_PLAN_VERSION,
                idkmesh_ref=SHA,
                default_branch="main",
                files=(item, item),
                owner_actions=(action,),
            )
        self.assertEqual(caught.exception.code, "duplicate_path")


if __name__ == "__main__":
    unittest.main()
