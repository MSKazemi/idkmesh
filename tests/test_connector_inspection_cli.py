import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKED_AT = "2026-09-22T18:00:00Z"


class ConnectorInspectionCliTests(unittest.TestCase):
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

    def write_json(self, directory, name, data):
        path = Path(directory) / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def agent_profile(self, *, driver="fake-agent"):
        return [
            {
                "api_version": "idkmesh.io/v1alpha1",
                "id": "agent-a",
                "kind": "agent",
                "driver": driver,
                "enabled": True,
                "capabilities": {
                    "tiers": ["T1", "T2"],
                    "task_classes": ["coder"],
                    "tools": ["git", "pytest"],
                    "max_risk": "medium",
                },
                "policy": {
                    "external_processing": False,
                    "project_spend_usd_max": 5,
                },
            }
        ]

    def decision(self, **overrides):
        data = {
            "required_capability_tier": "T1",
            "authority_mode": "agent_candidate",
            "risk_class": "low",
            "task_classes": ["coder"],
            "required_tools": ["git"],
            "allowed_connector_kinds": ["agent"],
            "external_processing_allowed": True,
            "project_spend_usd_max": 0,
        }
        data.update(overrides)
        return data

    def test_connections_probe_json_is_read_only_and_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp, "connections.json", self.agent_profile()
            )
            proc = self.run_cli(
                "connections",
                "probe",
                str(profile),
                "--checked-at",
                CHECKED_AT,
                "--json",
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["checked_at"], CHECKED_AT)
        self.assertEqual(payload["connections"][0]["probe"]["status"], "healthy")
        self.assertIsNone(payload["connections"][0]["error"])

    def test_doctor_human_output_passes_for_offline_fake(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp, "connections.json", self.agent_profile()
            )
            proc = self.run_cli(
                "doctor",
                str(profile),
                "--checked-at",
                CHECKED_AT,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("doctor: PASS", proc.stdout)
        self.assertIn("agent-a: PASS (healthy)", proc.stdout)

    def test_doctor_returns_one_for_unknown_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp,
                "connections.json",
                self.agent_profile(driver="not-registered"),
            )
            proc = self.run_cli(
                "doctor",
                str(profile),
                "--checked-at",
                CHECKED_AT,
                "--json",
            )

        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(
            payload["connections"][0]["reason"],
            "unknown_driver",
        )

    def test_route_explain_json_shows_human_required_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp, "connections.json", self.agent_profile()
            )
            decision = self.write_json(
                tmp,
                "decision.json",
                self.decision(authority_mode="human_required"),
            )
            proc = self.run_cli(
                "route",
                "explain",
                str(profile),
                str(decision),
                "--checked-at",
                CHECKED_AT,
                "--auto-select",
                "--json",
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIsNone(payload["selected_connection_id"])
        self.assertIn(
            "human_required",
            payload["ineligible"][0]["reasons"],
        )

    def test_route_explain_human_output_shows_tier_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp, "connections.json", self.agent_profile()
            )
            decision = self.write_json(
                tmp,
                "decision.json",
                self.decision(required_capability_tier="T4"),
            )
            proc = self.run_cli(
                "route",
                "explain",
                str(profile),
                str(decision),
                "--checked-at",
                CHECKED_AT,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("eligible:\n- none", proc.stdout)
        self.assertIn("insufficient_capability_tier", proc.stdout)
        self.assertIn("selected: none", proc.stdout)

    def test_route_explain_cost_flag_surfaces_project_spend_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write_json(
                tmp, "connections.json", self.agent_profile()
            )
            decision = self.write_json(
                tmp, "decision.json", self.decision(project_spend_usd_max=0)
            )
            proc = self.run_cli(
                "route",
                "explain",
                str(profile),
                str(decision),
                "--checked-at",
                CHECKED_AT,
                "--cost",
                "agent-a=1",
                "--json",
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIn(
            "project_spend_exceeded",
            payload["ineligible"][0]["reasons"],
        )

    def test_inspection_help_stays_explicitly_read_only(self):
        probe = self.run_cli("connections", "probe", "--help")
        doctor = self.run_cli("doctor", "--help")
        route = self.run_cli("route", "explain", "--help")

        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertEqual(route.returncode, 0, route.stderr)
        self.assertIn("offline fake", probe.stdout.lower())
        self.assertIn("without dispatching", doctor.stdout.lower())
        self.assertIn("eligible/rejected", route.stdout.lower())


if __name__ == "__main__":
    unittest.main()
