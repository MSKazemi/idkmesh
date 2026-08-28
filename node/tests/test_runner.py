from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from idkmesh_node.model import parse_work_unit
from idkmesh_node.runner import (
    _git_environment,
    _git_repo_command,
    _remaining_seconds,
    docker_command,
    output_policy_violations,
    parse_image_inspect,
    path_policy_violations,
    protected_metadata_violations,
    resolve_container_image,
    unpackaged_artifact_violations,
    untracked_paths,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "node" / "examples" / "work-unit.canonical-smoke.json"


def work_unit():
    return parse_work_unit(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_deadline() -> float:
    return time.monotonic() + 60.0


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

    def test_canonical_smoke_decoded_python_command_compiles(self) -> None:
        command = list(work_unit().execution.command)
        self.assertGreaterEqual(len(command), 3)
        self.assertEqual(command[:2], ["python", "-c"])
        compile(command[2], "<canonical-node-smoke>", "exec")

    def test_image_inspect_binds_id_and_matching_repository_digest(self) -> None:
        image_id = "sha256:" + "b" * 64
        repo_digest = "python@sha256:" + "c" * 64
        payload = json.dumps(
            [{"Id": image_id, "RepoDigests": [repo_digest]}]
        ).encode()

        observed_id, observed_digest = parse_image_inspect(
            payload,
            "python:3.12-alpine",
        )
        self.assertEqual(observed_id, image_id)
        self.assertEqual(observed_digest, repo_digest)

    def test_locally_retagged_image_without_repo_digest_fails_closed(self) -> None:
        image_id = "sha256:" + "b" * 64
        payload = json.dumps([{"Id": image_id, "RepoDigests": []}]).encode()
        with self.assertRaisesRegex(RuntimeError, "no matching immutable repository digest"):
            parse_image_inspect(payload, "python:3.12-alpine")

    @patch("idkmesh_node.runner.subprocess.run")
    def test_container_tag_is_resolved_before_execution(self, run_mock) -> None:
        image_id = "sha256:" + "d" * 64
        repo_digest = "python@sha256:" + "e" * 64
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"Id": image_id, "RepoDigests": [repo_digest]}]
            ).encode(),
            stderr=b"",
        )

        observed = resolve_container_image(work_unit(), deadline=test_deadline())
        self.assertEqual(observed, (image_id, repo_digest))
        self.assertEqual(
            run_mock.call_args.args[0],
            ["docker", "image", "inspect", "python:3.12-alpine"],
        )

    @patch("idkmesh_node.runner.subprocess.run")
    def test_missing_preloaded_image_fails_closed(self, run_mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b"No such image"
        )
        with self.assertRaisesRegex(RuntimeError, "No such image|not available locally"):
            resolve_container_image(work_unit(), deadline=test_deadline())

    def test_wall_budget_helper_fails_after_deadline(self) -> None:
        with patch("idkmesh_node.runner.time.monotonic", return_value=10.0):
            self.assertEqual(_remaining_seconds(12.5, "test phase"), 2.5)
            with self.assertRaisesRegex(RuntimeError, "wall budget exhausted"):
                _remaining_seconds(9.0, "test phase")

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

            observed = untracked_paths(
                workspace,
                git_dir,
                git_home,
                deadline=test_deadline(),
            )
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
