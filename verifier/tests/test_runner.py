from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verifier" / "src"))
sys.path.insert(0, str(ROOT / "verifier" / "tests"))

from idkmesh_verifier.model import file_digest, parse_context  # noqa: E402
from idkmesh_verifier.runner import (  # noqa: E402
    docker_check_command,
    fresh_check_workspace,
    resolve_artifact,
    run_verification,
    scope_violations,
)
from test_model import fixtures  # noqa: E402


class VerifierRunnerTests(unittest.TestCase):
    def test_artifact_root_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir()
            outside = Path(temp_dir) / "outside.patch"
            outside.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "escapes artifact root"):
                resolve_artifact(root, "../outside.patch")

    def test_scope_policy_checks_allowed_write_and_forbidden_paths(self) -> None:
        work_unit, result, plan = fixtures()
        context = parse_context(work_unit, result, plan)
        violations = scope_violations(context, ["README.md", ".github/workflows/unsafe.yml", "OTHER.md"])
        self.assertEqual(len(violations), 3)
        self.assertTrue(any("forbidden path" in value for value in violations))
        self.assertTrue(any("allowed_paths" in value for value in violations))
        self.assertTrue(any("filesystem_write" in value for value in violations))

    def test_docker_verifier_is_network_disabled_and_least_privilege(self) -> None:
        work_unit, result, plan = fixtures()
        context = parse_context(work_unit, result, plan)
        with tempfile.TemporaryDirectory() as temp_dir:
            command = docker_check_command(context, Path(temp_dir), ("python", "-V"))
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("no-new-privileges", command)
        self.assertNotIn("/var/run/docker.sock", joined)

    def test_each_hidden_check_gets_fresh_candidate_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = root / "base"
            copies = root / "copies"
            base.mkdir()
            copies.mkdir()
            (base / "candidate.txt").write_text("original\n", encoding="utf-8")

            first = fresh_check_workspace(base, copies, "check-a")
            (first / "candidate.txt").write_text("mutated-by-check-a\n", encoding="utf-8")
            second = fresh_check_workspace(base, copies, "check-b")

            self.assertEqual(
                (second / "candidate.txt").read_text(encoding="utf-8"),
                "original\n",
            )
            self.assertEqual(
                (base / "candidate.txt").read_text(encoding="utf-8"),
                "original\n",
            )

    @patch("idkmesh_verifier.runner.platform.platform", return_value="test-platform")
    @patch("idkmesh_verifier.runner.require_tools")
    @patch("idkmesh_verifier.runner.clone_revision")
    @patch("idkmesh_verifier.runner.apply_patch")
    @patch("idkmesh_verifier.runner.changed_paths", return_value=["README.md"])
    @patch("idkmesh_verifier.runner.subprocess.run")
    def test_successful_checks_emit_schema_valid_independent_verification_result(
        self,
        subprocess_mock,
        changed_paths_mock,
        apply_patch_mock,
        clone_revision_mock,
        require_tools_mock,
        platform_mock,
    ) -> None:
        subprocess_mock.return_value = subprocess.CompletedProcess(
            args=["docker", "run"], returncode=0, stdout=b"hidden pass\n", stderr=b""
        )
        work_unit, result, plan = fixtures()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            patch_path = artifacts / "changes.patch"
            patch_path.write_text("diff --git a/README.md b/README.md\n", encoding="utf-8")
            result["produced_artifacts"][0]["digest"] = file_digest(patch_path)
            context = parse_context(work_unit, result, plan)
            output = root / "verification"
            verification = run_verification(
                context,
                artifact_root=artifacts,
                output_dir=output,
            )
            self.assertTrue((output / "verification-result.json").exists())

        self.assertEqual(verification["status"], "passed")
        self.assertEqual(verification["decision_support"]["recommendation"], "accept_candidate")
        self.assertTrue(verification["independence"]["independent_from_worker"])
        self.assertNotEqual(verification["verifier"]["id"], result["worker"]["id"])
        self.assertEqual(verification["provenance"]["source_revision"], result["provenance"]["source_revision"])
        self.assertEqual(
            verification["extensions"]["org.idkmesh.verifier"]["evaluator_plan_schema_version"],
            "0.2",
        )
        self.assertTrue(
            verification["extensions"]["org.idkmesh.verifier"]["fresh_workspace_per_container_check"]
        )

    @patch("idkmesh_verifier.runner.platform.platform", return_value="test-platform")
    @patch("idkmesh_verifier.runner.require_tools")
    @patch("idkmesh_verifier.runner.clone_revision")
    @patch("idkmesh_verifier.runner.apply_patch")
    @patch("idkmesh_verifier.runner.changed_paths", return_value=["OTHER.md"])
    @patch("idkmesh_verifier.runner.subprocess.run")
    def test_scope_violation_rejects_candidate_even_if_hidden_test_passes(
        self,
        subprocess_mock,
        changed_paths_mock,
        apply_patch_mock,
        clone_revision_mock,
        require_tools_mock,
        platform_mock,
    ) -> None:
        subprocess_mock.return_value = subprocess.CompletedProcess(
            args=["docker", "run"], returncode=0, stdout=b"ok\n", stderr=b""
        )
        work_unit, result, plan = fixtures()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            patch_path = artifacts / "changes.patch"
            patch_path.write_text("diff --git a/OTHER.md b/OTHER.md\n", encoding="utf-8")
            result["produced_artifacts"][0]["digest"] = file_digest(patch_path)
            context = parse_context(work_unit, result, plan)
            verification = run_verification(
                context,
                artifact_root=artifacts,
                output_dir=root / "verification",
            )

        self.assertEqual(verification["status"], "failed")
        self.assertEqual(verification["decision_support"]["recommendation"], "reject_candidate")
        self.assertTrue(any(item["category"] == "scope" for item in verification["findings"]))


if __name__ == "__main__":
    unittest.main()
