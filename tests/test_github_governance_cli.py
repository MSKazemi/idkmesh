"""CLI coverage for C12 `idkmesh doctor --github`."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest

from idkmesh import cli


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "github-governance"


class GitHubGovernanceCliTests(unittest.TestCase):
    def run_cli(self, *args: str):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        return types.SimpleNamespace(
            returncode=code,
            stdout=out.getvalue(),
            stderr=err.getvalue(),
        )

    def test_github_json_doctor_passes_complete_fixture(self) -> None:
        result = self.run_cli(
            "doctor",
            "--github",
            str(EXAMPLES / "governance-pass-v0.1.json"),
            "--operation",
            "integration",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(payload["operation_allowed"])
        self.assertFalse(payload["automatic_admin_mutation"])

    def test_github_doctor_merges_workflow_lint(self) -> None:
        result = self.run_cli(
            "doctor",
            "--github",
            str(EXAMPLES / "governance-pass-v0.1.json"),
            "--operation",
            "cloud_dispatch",
            "--workflow",
            str(EXAMPLES / "oidc-cloud-dispatch.yml"),
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(len(payload["workflow_lint"]), 1)
        self.assertEqual(payload["workflow_lint"][0]["findings"], [])

    def test_github_doctor_unknown_is_nonzero_not_pass(self) -> None:
        payload = json.loads(
            (EXAMPLES / "governance-pass-v0.1.json").read_text(encoding="utf-8")
        )
        del payload["repository_rules"]["force_push_blocked"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unknown.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli(
                "doctor",
                "--github",
                str(path),
                "--operation",
                "integration",
                "--json",
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "UNKNOWN")

    def test_github_doctor_fail_is_nonzero(self) -> None:
        payload = json.loads(
            (EXAMPLES / "governance-pass-v0.1.json").read_text(encoding="utf-8")
        )
        payload["repository_rules"]["pull_request_integration"] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fail.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli(
                "doctor",
                "--github",
                str(path),
                "--operation",
                "integration",
                "--json",
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_github_doctor_can_render_codeowners_recommendation(self) -> None:
        result = self.run_cli(
            "doctor",
            "--github",
            str(EXAMPLES / "governance-pass-v0.1.json"),
            "--codeowners-owner",
            "@org/security",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(
            ".github/workflows/** @org/security",
            payload["codeowners_recommendation"],
        )

    def test_github_doctor_rejects_connector_profile_mixing(self) -> None:
        result = self.run_cli(
            "doctor",
            "connector.json",
            "--github",
            str(EXAMPLES / "governance-pass-v0.1.json"),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)

    def test_connector_doctor_still_requires_profile(self) -> None:
        result = self.run_cli("doctor")
        self.assertEqual(result.returncode, 2)
        self.assertIn("profile", result.stderr)

    def test_workflow_option_requires_github_mode(self) -> None:
        result = self.run_cli(
            "doctor",
            "connector.json",
            "--workflow",
            str(EXAMPLES / "read-only-lane.yml"),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--workflow requires --github", result.stderr)


if __name__ == "__main__":
    unittest.main()
