"""CLI coverage for C8-B GitHub bootstrap dry-run (#596)."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest

from idkmesh import cli


SHA = "1" * 40


class GitHubBootstrapCliTests(unittest.TestCase):
    def run_cli(self, *args, cwd: Path | None = None):
        out, err = io.StringIO(), io.StringIO()
        context = contextlib.chdir(cwd) if cwd is not None else contextlib.nullcontext()
        with context, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (
                    0 if exc.code is None else 1
                )
        return types.SimpleNamespace(
            returncode=code,
            stdout=out.getvalue(),
            stderr=err.getvalue(),
        )

    def test_json_dry_run_is_deterministic_and_explicitly_side_effect_free(self):
        args = (
            "init",
            "--github",
            "--dry-run",
            "--idkmesh-ref",
            SHA,
            "--default-branch",
            "trunk",
            "--json",
        )
        first = self.run_cli(*args)
        second = self.run_cli(*args)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["kind"], "idkmesh-github-bootstrap-dry-run")
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["writes_performed"])
        self.assertFalse(payload["github_mutation_performed"])
        self.assertFalse(payload["secret_values_accessed"])
        self.assertEqual(payload["plan"]["idkmesh_ref"], SHA)
        self.assertEqual(payload["plan"]["default_branch"], "trunk")
        self.assertEqual(len(payload["plan"]["files"]), 8)
        self.assertTrue(
            all(
                item["integration_authority"] is False
                and item["secret_values_allowed"] is False
                for item in payload["plan"]["files"]
            )
        )
        rendered = payload["rendered_config_files"]
        self.assertEqual(len(rendered), 4)
        self.assertEqual(
            {item["path"] for item in rendered},
            {
                ".idkmesh/README.md",
                ".idkmesh/project.json",
                ".idkmesh/connections.json",
                (
                    ".idkmesh/domain-packs/"
                    "software-engineering-v0.1.domain-pack.json"
                ),
            },
        )
        self.assertTrue(
            all(item["content_digest"].startswith("sha256:") for item in rendered)
        )
        self.assertTrue(all("content" in item for item in rendered))
        project = next(
            item for item in rendered
            if item["path"] == ".idkmesh/project.json"
        )
        project_doc = json.loads(project["content"])
        self.assertEqual(
            project_doc["integration_policy"]["target_branch"],
            "trunk",
        )
        self.assertFalse(
            project_doc["integration_policy"]["automatic_merge_allowed"]
        )

    def test_dry_run_creates_no_files_in_the_current_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            before = sorted(path.relative_to(root) for path in root.rglob("*"))

            result = self.run_cli(
                "init",
                "--github",
                "--dry-run",
                "--idkmesh-ref",
                "v0.1.0",
                cwd=root,
            )
            after = sorted(path.relative_to(root) for path in root.rglob("*"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)
        self.assertIn("filesystem writes: no", result.stdout)
        self.assertIn("GitHub mutations: no", result.stdout)
        self.assertIn("secret values accessed: no", result.stdout)
        self.assertIn(".idkmesh/project.json", result.stdout)
        self.assertIn("rendered C8-C config files:", result.stdout)
        self.assertIn("sha256:", result.stdout)
        self.assertIn("configure-branch-protection", result.stdout)

    def test_apply_mode_fails_closed_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cli(
                "init",
                "--github",
                "--idkmesh-ref",
                "v0.1.0",
                cwd=root,
            )
            self.assertEqual(list(root.iterdir()), [])

        self.assertEqual(result.returncode, 2)
        self.assertIn("apply mode is not implemented", result.stderr)

    def test_missing_github_profile_fails_closed(self):
        result = self.run_cli(
            "init",
            "--dry-run",
            "--idkmesh-ref",
            "v0.1.0",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("only the --github profile", result.stderr)

    def test_unpinned_ref_uses_existing_bootstrap_validation(self):
        result = self.run_cli(
            "init",
            "--github",
            "--dry-run",
            "--idkmesh-ref",
            "main",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unpinned_idkmesh_ref", result.stderr)

    def test_help_states_that_current_surface_is_dry_run_only(self):
        result = self.run_cli("init", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--github", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--idkmesh-ref", result.stdout)
        self.assertIn("apply mode remains fail-closed", result.stdout)


if __name__ == "__main__":
    unittest.main()
