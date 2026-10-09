"""Tests for deterministic C8-C bootstrap configuration rendering."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

try:
    import jsonschema
except ImportError:  # pragma: no cover - base package remains dependency-free
    jsonschema = None

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.github_bootstrap import build_github_bootstrap_plan
from idkmesh.github_bootstrap_render import (
    BootstrapRenderError,
    render_github_bootstrap_config,
)


ROOT = Path(__file__).resolve().parents[1]
SHA = "1" * 40
CONFIG_PATHS = {
    ".idkmesh/README.md",
    ".idkmesh/connections.json",
    ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json",
    ".idkmesh/project.json",
}


def _by_path(rendered):
    return {item.path: item for item in rendered}


class GitHubBootstrapRenderTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_github_bootstrap_plan(
            idkmesh_ref=SHA,
            default_branch="trunk",
        )

    def test_render_is_deterministic_and_exactly_c8_c(self):
        first = render_github_bootstrap_config(self.plan)
        second = render_github_bootstrap_config(self.plan)

        self.assertEqual(first, second)
        self.assertEqual({item.path for item in first}, CONFIG_PATHS)
        self.assertFalse(
            any(item.path.startswith(".github/workflows/") for item in first)
        )

        for item in first:
            expected = "sha256:" + hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest()
            self.assertEqual(item.content_digest, expected)
            self.assertEqual(item.size_bytes, len(item.content.encode("utf-8")))
            self.assertTrue(item.content.endswith("\n"))
            self.assertFalse(item.to_dict()["secret_values_accessed"])
            self.assertFalse(item.to_dict()["integration_authority"])

    def test_project_seed_preserves_human_integration_and_local_domain_pack(self):
        project = json.loads(
            _by_path(render_github_bootstrap_config(self.plan))[
                ".idkmesh/project.json"
            ].content
        )

        self.assertEqual(project["integration_policy"]["target_branch"], "trunk")
        self.assertFalse(
            project["integration_policy"]["automatic_merge_allowed"]
        )
        self.assertTrue(
            project["integration_policy"]["human_decision_required"]
        )
        self.assertTrue(
            project["verification"]["human_integration_required"]
        )
        self.assertEqual(
            project["domain_packs"][0]["path"],
            (
                ".idkmesh/domain-packs/"
                "software-engineering-v0.1.domain-pack.json"
            ),
        )
        self.assertTrue(project["metadata"]["customize_before_dispatch"])
        self.assertEqual(project["metadata"]["idkmesh_ref"], SHA)

    @unittest.skipUnless(jsonschema is not None, "jsonschema is optional")
    def test_project_seed_validates_against_project_manifest_schema(self):
        project = json.loads(
            _by_path(render_github_bootstrap_config(self.plan))[
                ".idkmesh/project.json"
            ].content
        )
        schema = json.loads(
            (ROOT / "schemas" / "project-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(project)

    def test_connector_seed_is_valid_disabled_and_secret_reference_only(self):
        raw = json.loads(
            _by_path(render_github_bootstrap_config(self.plan))[
                ".idkmesh/connections.json"
            ].content
        )
        configs = parse_connector_profile_document(raw)

        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.id, "jules-main")
        self.assertFalse(config.enabled)
        self.assertEqual(config.secret_ref, "env:JULES_API_KEY")
        self.assertEqual(config.settings["starting_branch"], "trunk")
        self.assertEqual(
            config.settings["source"],
            "sources/github/OWNER/REPOSITORY",
        )

        forbidden_keys = {
            "api_key",
            "apikey",
            "access_token",
            "auth_token",
            "authorization",
            "bearer_token",
            "client_secret",
            "credentials",
            "password",
            "secret",
            "token",
        }

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(str(key).lower(), forbidden_keys)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(raw)

    @unittest.skipUnless(jsonschema is not None, "jsonschema is optional")
    def test_vendored_domain_pack_matches_canonical_source_and_schema(self):
        rendered = json.loads(
            _by_path(render_github_bootstrap_config(self.plan))[
                (
                    ".idkmesh/domain-packs/"
                    "software-engineering-v0.1.domain-pack.json"
                )
            ].content
        )
        canonical = json.loads(
            (
                ROOT
                / "examples"
                / "domain-packs"
                / "software-engineering-v0.1.domain-pack.json"
            ).read_text(encoding="utf-8")
        )
        schema = json.loads(
            (ROOT / "schemas" / "domain-pack.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(rendered, canonical)
        jsonschema.Draft202012Validator(schema).validate(rendered)

    def test_readme_records_ownership_and_authority_boundary(self):
        readme = _by_path(render_github_bootstrap_config(self.plan))[
            ".idkmesh/README.md"
        ].content

        self.assertIn("user_seed", readme)
        self.assertIn("idkmesh_managed", readme)
        self.assertIn("JULES_API_KEY", readme)
        self.assertIn("no filesystem or GitHub", readme)
        self.assertIn("does not grant", readme)
        self.assertIn(SHA, readme)
        self.assertIn("trunk", readme)

    def test_plan_drift_fails_closed_instead_of_silently_dropping_config(self):
        missing_project = replace(
            self.plan,
            files=tuple(
                item
                for item in self.plan.files
                if item.path != ".idkmesh/project.json"
            ),
        )
        with self.assertRaisesRegex(
            BootstrapRenderError,
            "config_plan_mismatch",
        ):
            render_github_bootstrap_config(missing_project)


if __name__ == "__main__":
    unittest.main()
