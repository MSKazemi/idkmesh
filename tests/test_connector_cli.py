import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConnectorCliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )

    def write_profile(self, directory, data):
        path = Path(directory) / "connections.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def valid_profiles(self):
        return [
            {
                "api_version": "idkmesh.io/v1alpha1",
                "id": "agent-a",
                "kind": "agent",
                "driver": "fake-agent",
                "enabled": True,
                "auth": {"secret_ref": "env:SHOULD_NOT_RENDER"},
                "capabilities": {
                    "tiers": ["T1", "T2"],
                    "task_classes": ["coder"],
                    "tools": ["git", "pytest"],
                    "candidate_types": ["artifact_bundle"],
                    "max_risk": "medium",
                },
                "policy": {
                    "external_processing": False,
                    "project_spend_usd_max": 0,
                    "max_concurrency": 1,
                },
            },
            {
                "api_version": "idkmesh.io/v1alpha1",
                "id": "exec-b",
                "kind": "execution",
                "driver": "fake-execution",
                "enabled": False,
                "capabilities": {
                    "tiers": ["T0"],
                    "task_classes": ["execution"],
                },
            },
        ]

    def test_connections_validate_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, self.valid_profiles())
            proc = self.run_cli("connections", "validate", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("valid: 2 connector profile(s)", proc.stdout)
        self.assertIn("agent-a (agent/fake-agent)", proc.stdout)
        self.assertNotIn("SHOULD_NOT_RENDER", proc.stdout)

    def test_connections_validate_json_is_deterministic_and_secret_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, self.valid_profiles())
            first = self.run_cli("connections", "validate", str(path), "--json")
            second = self.run_cli("connections", "validate", str(path), "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["count"], 2)
        self.assertTrue(payload["connections"][0]["auth_ref_configured"])
        self.assertNotIn("SHOULD_NOT_RENDER", first.stdout)

    def test_connections_list_human_output_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, self.valid_profiles())
            proc = self.run_cli("connections", "list", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(
            lines[0],
            "id\tkind\tdriver\tenabled\ttiers\tmax_risk",
        )
        self.assertEqual(
            lines[1],
            "agent-a\tagent\tfake-agent\tyes\tT1,T2\tmedium",
        )
        self.assertEqual(
            lines[2],
            "exec-b\texecution\tfake-execution\tno\tT0\tlow",
        )

    def test_connections_list_json_contains_metadata_not_settings_or_secret_ref(self):
        profiles = self.valid_profiles()
        profiles[0]["settings"] = {
            "source": "repo/example",
            "require_plan_approval": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, profiles)
            proc = self.run_cli("connections", "list", str(path), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        item = payload["connections"][0]
        self.assertNotIn("settings", item)
        self.assertNotIn("secret_ref", item)
        self.assertNotIn("SHOULD_NOT_RENDER", proc.stdout)

    def test_invalid_profile_exits_two_with_actionable_human_error(self):
        profiles = self.valid_profiles()
        profiles[0]["kind"] = "unknown"
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, profiles)
            proc = self.run_cli("connections", "validate", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown_connector_kind", proc.stderr)
        self.assertIn("$[0].kind", proc.stderr)

    def test_invalid_profile_json_mode_returns_stable_machine_error(self):
        profiles = self.valid_profiles()
        profiles[0]["api_version"] = "idkmesh.io/v9"
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, profiles)
            proc = self.run_cli(
                "connections", "validate", str(path), "--json"
            )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertFalse(payload["valid"])
        self.assertEqual(
            payload["error"]["code"],
            "unsupported_api_version",
        )
        self.assertEqual(payload["error"]["path"], "$[0].api_version")

    def test_inline_secret_is_rejected_without_echoing_value(self):
        profiles = self.valid_profiles()
        profiles[0]["settings"] = {"api_key": "sentinel-do-not-render"}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_profile(tmp, profiles)
            proc = self.run_cli(
                "connections", "validate", str(path), "--json"
            )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("inline_secret_forbidden", proc.stderr)
        self.assertNotIn("sentinel-do-not-render", proc.stderr)

    def test_connections_help_is_read_only_in_language(self):
        proc = self.run_cli("connections", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("validate", proc.stdout)
        self.assertIn("list", proc.stdout)

    def test_existing_gate_audit_help_still_works(self):
        proc = self.run_cli("gate-audit", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("verifier panel", proc.stdout)


if __name__ == "__main__":
    unittest.main()
