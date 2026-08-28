from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node" / "src"))

from idkmesh_node.model import parse_work_unit  # noqa: E402
from idkmesh_node.runner import docker_command, policy_violations, run_work_unit  # noqa: E402
from test_model import canonical_work_unit  # noqa: E402


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = parse_work_unit(canonical_work_unit())

    def test_docker_command_uses_mvp_safety_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            command = docker_command(self.work, Path(temp_dir), "idkmesh-test")
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("no-new-privileges", command)
        self.assertNotIn("/var/run/docker.sock", joined)

    def test_path_policy_rejects_forbidden_and_out_of_scope_changes(self) -> None:
        violations = policy_violations(
            self.work,
            ["docs/ok.md", ".github/workflows/unsafe.yml", "README.md"],
        )
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("forbidden path" in item for item in violations))
        self.assertTrue(any("outside" in item for item in violations))

    @patch("idkmesh_node.runner.require_tools")
    @patch("idkmesh_node.runner.clone_revision")
    @patch("idkmesh_node.runner.docker_command", return_value=["docker", "run"])
    @patch("idkmesh_node.runner._changed_paths", return_value=(["docs/candidate.md"], ["docs/candidate.md"]))
    @patch("idkmesh_node.runner._capture_patch", return_value=(b"diff --git a/docs/candidate.md b/docs/candidate.md\n", False))
    @patch("idkmesh_node.runner.subprocess.run")
    def test_run_emits_schema_valid_result_manifest(
        self,
        run_mock,
        capture_patch_mock,
        changed_paths_mock,
        docker_command_mock,
        clone_revision_mock,
        require_tools_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["docker", "run"],
            returncode=0,
            stdout=b"worker output\n",
            stderr=b"",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_work_unit(self.work, temp_dir)
            self.assertTrue((Path(temp_dir) / "result-manifest.json").exists())
            self.assertTrue((Path(temp_dir) / "changes.patch").exists())

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["work_unit_id"], self.work.id)
        self.assertEqual(result["verification_request"]["expected_validator_ids"], ["schema", "review"])
        self.assertEqual(result["verification_request"]["evidence_artifact_ids"], ["candidate-patch"])
        self.assertIn("independent verification", result["verification_request"]["notes"])

    @patch("idkmesh_node.runner.require_tools")
    @patch("idkmesh_node.runner.clone_revision")
    @patch("idkmesh_node.runner.docker_command", return_value=["docker", "run"])
    @patch("idkmesh_node.runner._changed_paths", return_value=(["README.md"], []))
    @patch("idkmesh_node.runner._capture_patch", return_value=(b"diff --git a/README.md b/README.md\n", False))
    @patch("idkmesh_node.runner.subprocess.run")
    def test_successful_process_is_failed_when_scope_policy_is_violated(
        self,
        run_mock,
        capture_patch_mock,
        changed_paths_mock,
        docker_command_mock,
        clone_revision_mock,
        require_tools_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["docker", "run"],
            returncode=0,
            stdout=b"",
            stderr=b"",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_work_unit(self.work, temp_dir)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["metrics"]["policy_violation_count"], 1)


if __name__ == "__main__":
    unittest.main()
