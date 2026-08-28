from __future__ import annotations

import json
from pathlib import Path
import unittest

from idkmesh_node.model import parse_work_unit
from idkmesh_node.runner import docker_command, path_policy_violations

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "node" / "examples" / "work-unit.canonical-smoke.json"



def work_unit():
    return parse_work_unit(json.loads(EXAMPLE.read_text(encoding="utf-8")))


class RunnerPolicyTests(unittest.TestCase):
    def test_docker_command_preserves_safety_defaults(self) -> None:
        work = work_unit()
        command = docker_command(work, Path("/tmp/idkmesh-test-workspace"), "idkmesh-test")
        joined = " ".join(command)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("--security-opt no-new-privileges", joined)
        self.assertIn("--pids-limit 64", joined)
        self.assertIn("--cpus 1.0", joined)
        self.assertIn("--memory 256m", joined)
        self.assertNotIn("/var/run/docker.sock", joined)
        self.assertNotIn("--privileged", command)
        self.assertEqual(command[-3:-1], ["python:3.12-alpine", "python"])

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


if __name__ == "__main__":
    unittest.main()
