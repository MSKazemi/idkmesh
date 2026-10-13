"""Regression checks for local GitHub bootstrap application (C8-F)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.github_bootstrap import build_github_bootstrap_plan
from idkmesh.github_bootstrap_render import render_github_bootstrap_config
from idkmesh.github_bootstrap_workflows import render_github_bootstrap_workflows
from idkmesh.github_bootstrap_apply import (
    STATE_PATH, BootstrapApplyError, apply_github_bootstrap, plan_github_bootstrap_apply,
)


def candidate(ref="1" * 40):
    plan = build_github_bootstrap_plan(idkmesh_ref=ref)
    return plan, render_github_bootstrap_config(plan) + render_github_bootstrap_workflows(plan)


class BootstrapApplyTests(unittest.TestCase):
    def test_first_install_preview_noop_and_user_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            plan, files = candidate()
            preview = plan_github_bootstrap_apply(root, plan, files)
            self.assertEqual(len(preview["actions"]), 8)
            self.assertFalse((root / ".idkmesh").exists())
            report = apply_github_bootstrap(root, plan, files)
            self.assertTrue(report["writes_performed"])
            self.assertTrue((root / STATE_PATH).is_file())
            self.assertEqual(len(json.loads((root / STATE_PATH).read_text())["managed_digests"]), 6)
            for item in files:
                self.assertEqual((root / item.path).read_text(), item.content)
            seed = root / ".idkmesh/project.json"
            seed.write_text("owner changed this\n")
            again = apply_github_bootstrap(root, plan, files)
            self.assertFalse(again["writes_performed"])
            self.assertEqual(seed.read_text(), "owner changed this\n")

    def test_version_upgrade_and_modified_managed_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            apply_github_bootstrap(root, *candidate())
            target = root / ".idkmesh/README.md"
            target.write_text("custom content\n")
            with self.assertRaisesRegex(BootstrapApplyError, "managed_file_modified"):
                apply_github_bootstrap(root, *candidate("2" * 40))
            target.write_text(next(x.content for x in candidate()[1] if x.path == ".idkmesh/README.md"))
            result = apply_github_bootstrap(root, *candidate("2" * 40))
            self.assertTrue(result["writes_performed"])
            self.assertEqual(json.loads((root / STATE_PATH).read_text())["idkmesh_ref"], "2" * 40)

    def test_existing_untracked_file_and_state_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".idkmesh").mkdir()
            (root / ".idkmesh/README.md").write_text("foreign\n")
            with self.assertRaisesRegex(BootstrapApplyError, "untracked_managed_file"):
                apply_github_bootstrap(root, *candidate())
            self.assertFalse((root / STATE_PATH).exists())
            (root / ".idkmesh/README.md").unlink()
            apply_github_bootstrap(root, *candidate())
            state = root / STATE_PATH
            state.write_text(state.read_text().replace("1" * 40, "2" * 40))
            with self.assertRaisesRegex(BootstrapApplyError, "invalid_state"):
                apply_github_bootstrap(root, *candidate("2" * 40))

    def test_symlink_parent_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "elsewhere").mkdir()
            (root / ".idkmesh").symlink_to(root / "elsewhere", target_is_directory=True)
            with self.assertRaisesRegex(BootstrapApplyError, "unsafe_path"):
                apply_github_bootstrap(root, *candidate())
            self.assertEqual(list((root / "elsewhere").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
