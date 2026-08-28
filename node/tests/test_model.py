from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from idkmesh_node.model import WorkUnitError, parse_work_unit

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "node" / "examples" / "work-unit.canonical-smoke.json"



def fixture() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class WorkUnitModelTests(unittest.TestCase):
    def test_canonical_fixture_is_valid(self) -> None:
        work = parse_work_unit(fixture())
        self.assertEqual(work.id, "node/canonical-smoke")
        self.assertEqual(work.version, 1)
        self.assertEqual(work.source.revision, "bb18ce0ea633f69fa36e2b2f59f90ad66b286064")
        self.assertEqual(work.required_validator_ids, ("result-manifest-schema", "independent-review"))

    def test_old_private_work_unit_shape_is_rejected(self) -> None:
        old_shape = {
            "version": "0.1",
            "id": "legacy-node-unit",
            "source": {
                "repo_url": "https://github.com/MSKazemi/idkmesh",
                "revision": "0" * 40,
            },
            "execution": {
                "image": "python:3.12-alpine",
                "command": ["python", "-V"],
                "network": "none",
            },
            "output": {"max_patch_bytes": 10000, "max_log_bytes": 10000},
        }
        with self.assertRaises(WorkUnitError):
            parse_work_unit(old_shape)

    def test_network_permission_is_rejected(self) -> None:
        data = fixture()
        data["permissions"]["network"] = "unrestricted"
        with self.assertRaisesRegex(WorkUnitError, "permissions.network"):
            parse_work_unit(data)

    def test_secret_permission_is_rejected(self) -> None:
        data = fixture()
        data["permissions"]["secrets"] = ["API_TOKEN"]
        with self.assertRaisesRegex(WorkUnitError, "does not expose secrets"):
            parse_work_unit(data)

    def test_binding_must_reference_git_ref(self) -> None:
        data = fixture()
        data["inputs"][0]["type"] = "file"
        with self.assertRaisesRegex(WorkUnitError, "type 'git_ref'"):
            parse_work_unit(data)

    def test_git_ref_requires_full_immutable_sha(self) -> None:
        data = fixture()
        data["inputs"][0]["digest"] = "git-sha1:main"
        with self.assertRaisesRegex(WorkUnitError, "40-character"):
            parse_work_unit(data)

    def test_node_timeout_cannot_exceed_work_unit_budget(self) -> None:
        data = fixture()
        data["budget"]["wall_seconds"] = 5
        with self.assertRaisesRegex(WorkUnitError, "budget.wall_seconds"):
            parse_work_unit(data)

    def test_path_traversal_policy_is_rejected(self) -> None:
        data = fixture()
        data["constraints"]["allowed_paths"] = ["../outside"]
        with self.assertRaisesRegex(WorkUnitError, "repository-relative"):
            parse_work_unit(data)

    def test_disallowed_container_image_is_rejected(self) -> None:
        data = copy.deepcopy(fixture())
        data["extensions"]["org.idkmesh.node.execution"]["container"]["image"] = "ubuntu:latest"
        with self.assertRaisesRegex(WorkUnitError, "container.image"):
            parse_work_unit(data)


if __name__ == "__main__":
    unittest.main()
