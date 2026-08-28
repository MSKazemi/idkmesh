from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from idkmesh_node.model import parse_work_unit
from idkmesh_node.runner import (
    _git_environment,
    _git_repo_command,
    docker_command,
    output_policy_violations,
    path_policy_violations,
    protected_metadata_violations,
    resolve_container_image_id,
    unpackaged_artifact_violations,
    untracked_paths,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "node" / "examples" / "work-unit.canonical-smoke.json"


def work_unit():
    return parse_work_unit(json.loads(EXAMPLE.read_text(encoding="utf-8")))


class RunnerPolicyTests(unittest.TestCase):
    def test_docker_command_preserves_safety_defaults(self) -> None:
        work = work_unit()
        image_id = "sha256:" + "a" * 64
        command = docker_command(
            work,
            Path("/tmp/idkmesh-test-workspace"),
            "idkmesh-test",
            Path("/tmp/idkmesh-test-git-meta"),
            image_ref=image_id,
        )
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("--security-opt no-new-privileges", joined)
        self.assertIn("--pids-limit 64", joined)
        self.assertIn("--cpus 1.0", joined)
        self.assertIn("--memory 256m", joined)
        self.assertIn("target=/git-meta,readonly", joined)
        self.assertNotIn("/var/run/docker.sock", joined)
        self.assertNotIn("--privileged", command)
        self.assertEqual(command[-4:-2], [image_id, "python"])

    @patch("idkmesh_node.runner.subprocess.run")
    def test_container_tag_is_resolved_to_immutable_local_image_id(self, run_mock) -> None:
        image_id = "sha256:" + "b" * 64
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=(image_id + "\n").encode(), stderr=b""
        )

        observed = resolve_container_image_id(
            "python:3.12-alpine",
            deadline=10**12,
        )
        self.assertEqual(observed, image_id)
        self.assertEqual(
            run_mock.call_args.args[0],
            [
                "docker",
                "image",
                "inspect",
                "--format={{.Id}}",
                "python:3.12-alpine",
            ],
        )

    @patch("idkmesh_node.runner.subprocess.run")
    def test_missing_preloaded_image_fails_closed(self, run_mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b"No such image"
        )
        with self.assertRaisesRegex(RuntimeError, "must be preloaded"):
            resolve_container_image_id(
                "python:3.12-alpine",
                deadline=10**12,
            )

    def test_git_environment_drops_inherited_git_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "git-home"
            with patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.fsmonitor",
                    "GIT_CONFIG_VALUE_0": "/tmp/host-hook",
                    "GIT_DIR": "/tmp/untrusted-git-dir",
                },
                clear=False,
            ):
                env = _git_environment(home)

            self.assertNotIn("GIT_CONFIG_COUNT", env)
            self.assertNotIn("GIT_CONFIG_KEY_0", env)
            self.assertNotIn("GIT_CONFIG_VALUE_0", env)
            self.assertNotIn("GIT_DIR", env)
            self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(env["HOME"], str(home))

    def test_host_git_commands_use_explicit_external_metadata(self) -> None:
        command = _git_repo_command(
            Path("/tmp/workspace"),
            Path("/tmp/git-meta"),
            ["status", "--short"],
        )
        self.assertEqual(
            command,
            [
                "git",
                "--git-dir",
                "/tmp/git-meta",
                "--work-tree",
                "/tmp/workspace",
                "status",
                "--short",
            ],
        )

    def test_untracked_detection_includes_gitignored_task_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            git_dir = root / "git-meta"
            git_home = root / "git-home"
            workspace.mkdir()
            empty_template = root / "empty-template"
            empty_template.mkdir()
            env = _git_environment(git_home)

            subprocess.run(
                [
                    "git",
                    "init",
                    "--quiet",
                    f"--template={empty_template}",
                    f"--separate-git-dir={git_dir}",
                    str(workspace),
                ],
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (workspace / ".gitignore").write_text("ignored-output.txt\n", encoding="utf-8")
            (workspace / "ignored-output.txt").write_text("must remain observable\n", encoding="utf-8")

            observed = untracked_paths(workspace, git_dir, git_home)
            self.assertIn("ignored-output.txt", observed)

    def test_protected_git_pointer_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            pointer = workspace / ".git"
            pointer.write_text("gitdir: /git-meta\n", encoding="utf-8")
            self.assertEqual(protected_metadata_violations(workspace), [])

            pointer.write_text("gitdir: /tmp/attacker-controlled\n", encoding="utf-8")
            violations = protected_metadata_violations(workspace)
            self.assertEqual(violations, ["task modified protected .git metadata pointer"])

    def test_allowed_candidate_change_has_no_policy_violation(self) -> None:
        self.assertEqual(path_policy_violations(work_unit(), ["README.md"]), [])

    def test_forbidden_change_is_detected(self) -> None:
        violations = path_policy_violations(
            work_unit(),
            ["README.md", ".github/workflows/unsafe.yml"],
        )
        self.assertTrue(any("forbidden path changed" in item for item in violations))
        self.assertTrue(any("outside constraints.allowed_paths" in item for item in violations))
        self.assertTrue(any("outside permissions.filesystem_write" in item for item in violations))

    def test_unapproved_path_is_detected(self) -> None:
        violations = path_policy_violations(work_unit(), ["docs/UNPLANNED.md"])
        self.assertEqual(len(violations), 2)

    def test_untracked_artifacts_fail_closed_until_packaged(self) -> None:
        violations = unpackaged_artifact_violations(
            ["NEW_FILE.txt", "reports/new-result.json"]
        )
        self.assertEqual(len(violations), 2)
        self.assertTrue(all("not packaged by node v0.1" in item for item in violations))

    def test_truncated_candidate_patch_is_a_policy_failure(self) -> None:
        self.assertEqual(
            output_policy_violations(patch_truncated=False, max_patch_bytes=1024),
            [],
        )
        violations = output_policy_violations(
            patch_truncated=True,
            max_patch_bytes=1024,
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("was truncated", violations[0])

    def test_work_unit_carries_whole_attempt_wall_budget(self) -> None:
        self.assertEqual(work_unit().wall_seconds, 60.0)


if __name__ == "__main__":
    unittest.main()
