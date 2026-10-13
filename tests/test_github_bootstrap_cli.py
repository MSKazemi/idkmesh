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
        self.assertIn("choose exactly one of --dry-run, --check, or --apply", result.stderr)

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

    def test_help_lists_every_init_mode(self):
        result = self.run_cli("init", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--github", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--idkmesh-ref", result.stdout)
        self.assertIn("--apply", result.stdout)
        self.assertIn("--check", result.stdout)


class GitHubBootstrapApplyCliTests(unittest.TestCase):
    """The C8-F `--check` / `--apply` modes through the real CLI entry point."""

    run_cli = GitHubBootstrapCliTests.run_cli

    def repo(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / ".git").mkdir()
        return root

    def tree(self, root: Path) -> list[str]:
        return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())

    def test_check_inspects_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp)
            result = self.run_cli(
                "init", "--github", "--check", "--idkmesh-ref", SHA, "--json", cwd=root
            )
            self.assertEqual(self.tree(root), [])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["writes_performed"])
        self.assertFalse(payload["github_mutation_performed"])
        self.assertEqual({a["action"] for a in payload["actions"]}, {"create"})
        self.assertEqual(len(payload["actions"]), 8)

    def test_apply_writes_the_eight_files_then_rerun_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp)
            first = self.run_cli("init", "--github", "--apply", "--idkmesh-ref", SHA, cwd=root)
            written = self.tree(root)
            second = self.run_cli(
                "init", "--github", "--apply", "--idkmesh-ref", SHA, "--json", cwd=root
            )
            self.assertEqual(self.tree(root), written)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("GitHub bootstrap applied", first.stdout)
        self.assertIn("filesystem writes: yes", first.stdout)
        self.assertIn("GitHub mutations: no", first.stdout)
        self.assertIn(".idkmesh/bootstrap-state.json", written)
        self.assertEqual(len(written), 9)  # eight canonical files plus the state record
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(json.loads(second.stdout)["writes_performed"])

    def test_apply_refuses_an_edited_managed_file_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp)
            self.run_cli("init", "--github", "--apply", "--idkmesh-ref", SHA, cwd=root)
            edited = root / ".idkmesh/README.md"
            edited.write_text("local edit\n", encoding="utf-8")
            result = self.run_cli("init", "--github", "--apply", "--idkmesh-ref", SHA, cwd=root)
            self.assertEqual(edited.read_text(encoding="utf-8"), "local edit\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("managed_file_modified", result.stderr)

    def test_apply_outside_a_git_repository_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cli("init", "--github", "--apply", "--idkmesh-ref", SHA, cwd=root)
            self.assertEqual(self.tree(root), [])
        self.assertEqual(result.returncode, 2)
        self.assertIn("git_repository_required", result.stderr)

    def test_modes_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp)
            result = self.run_cli(
                "init", "--github", "--dry-run", "--apply", "--idkmesh-ref", SHA, cwd=root
            )
            self.assertEqual(self.tree(root), [])
        self.assertEqual(result.returncode, 2)
        self.assertIn("choose exactly one of --dry-run, --check, or --apply", result.stderr)


if __name__ == "__main__":
    unittest.main()
