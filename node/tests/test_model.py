from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node" / "src"))

from idkmesh_node.model import WorkUnitError, parse_work_unit  # noqa: E402


def canonical_work_unit() -> dict:
    return {
        "schema_version": "0.1",
        "id": "node/test-work-unit",
        "version": 1,
        "kind": "coding",
        "objective": "Create a bounded documentation candidate in the sandbox.",
        "inputs": [
            {
                "id": "source",
                "type": "git_ref",
                "locator": "https://github.com/MSKazemi/idkmesh.git",
                "digest": "git:0123456789abcdef0123456789abcdef01234567",
            }
        ],
        "outputs": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "description": "Candidate patch for independent verification.",
                "media_type": "text/x-diff",
            }
        ],
        "dependencies": [],
        "constraints": {
            "allowed_paths": ["docs/"],
            "forbidden_paths": [".github/workflows/"],
            "policies": ["No network", "No secrets"],
        },
        "uncertainty": [],
        "permissions": {
            "network": "none",
            "network_allowlist": [],
            "filesystem_write": ["docs/"],
            "secrets": [],
            "process_execution": True,
        },
        "validators": [
            {
                "id": "schema",
                "type": "schema",
                "required": True,
                "description": "Validate the worker ResultManifest.",
            },
            {
                "id": "review",
                "type": "review",
                "required": True,
                "description": "Independent review remains required.",
            },
        ],
        "evidence_requirements": [
            {
                "type": "artifact_hash",
                "required": True,
                "description": "Hash the candidate patch.",
            }
        ],
        "budget": {"wall_seconds": 60, "compute_units": 1.0, "human_minutes": 5, "tokens": 0},
        "provenance": {
            "created_by": "node-tests",
            "creator_type": "system",
            "source": "node/tests/test_model.py",
            "parent_work_unit_ids": [],
        },
        "failure_semantics": {"retryable": False, "max_attempts": 1, "on_failure": "escalate"},
        "extensions": {
            "org.idkmesh.execution.docker": {
                "image": "python:3.12-alpine",
                "command": ["python", "-c", "print('candidate')"],
                "timeout_seconds": 30,
                "cpus": 1.0,
                "memory_mb": 256,
                "pids_limit": 64,
                "max_patch_bytes": 1000000,
                "max_log_bytes": 262144,
            }
        },
    }


class WorkUnitModelTests(unittest.TestCase):
    def test_accepts_canonical_work_unit_with_docker_binding(self) -> None:
        work = parse_work_unit(canonical_work_unit())
        self.assertEqual(work.id, "node/test-work-unit")
        self.assertEqual(work.source.revision, "0123456789abcdef0123456789abcdef01234567")
        self.assertEqual(work.execution.image, "python:3.12-alpine")
        self.assertEqual(work.validator_ids, ("schema", "review"))

    def test_rejects_noncanonical_document(self) -> None:
        data = canonical_work_unit()
        del data["validators"]
        with self.assertRaisesRegex(WorkUnitError, "canonical Work Unit validation failed"):
            parse_work_unit(data)

    def test_rejects_networked_execution(self) -> None:
        data = canonical_work_unit()
        data["permissions"]["network"] = "unrestricted"
        with self.assertRaisesRegex(WorkUnitError, "network"):
            parse_work_unit(data)

    def test_rejects_nonimmutable_git_ref(self) -> None:
        data = canonical_work_unit()
        data["inputs"][0]["digest"] = "git:main"
        with self.assertRaisesRegex(WorkUnitError, "40-character"):
            parse_work_unit(data)

    def test_execution_timeout_cannot_exceed_work_unit_budget(self) -> None:
        data = canonical_work_unit()
        data["budget"]["wall_seconds"] = 10
        data["extensions"]["org.idkmesh.execution.docker"]["timeout_seconds"] = 30
        with self.assertRaisesRegex(WorkUnitError, "between 1 and 10"):
            parse_work_unit(data)

    def test_rejects_secrets(self) -> None:
        data = copy.deepcopy(canonical_work_unit())
        data["permissions"]["secrets"] = ["TOKEN"]
        with self.assertRaisesRegex(WorkUnitError, "secrets"):
            parse_work_unit(data)


if __name__ == "__main__":
    unittest.main()
