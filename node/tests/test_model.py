import unittest

from idkmesh_node.model import WorkUnitError, parse_work_unit


BASE = {
    "version": "0.1",
    "id": "example-1",
    "source": {
        "repo_url": "https://github.com/MSKazemi/idkmesh",
        "revision": "a" * 40,
    },
    "execution": {
        "image": "python:3.12-alpine",
        "command": ["python", "--version"],
        "network": "none",
        "timeout_seconds": 30,
        "cpus": 1,
        "memory_mb": 256,
    },
}


class WorkUnitTests(unittest.TestCase):
    def test_valid_work_unit(self):
        work = parse_work_unit(BASE)
        self.assertEqual(work.id, "example-1")
        self.assertEqual(work.execution.command, ("python", "--version"))

    def test_requires_full_commit_sha(self):
        data = {**BASE, "source": {**BASE["source"], "revision": "main"}}
        with self.assertRaises(WorkUnitError):
            parse_work_unit(data)

    def test_rejects_network(self):
        data = {**BASE, "execution": {**BASE["execution"], "network": "bridge"}}
        with self.assertRaises(WorkUnitError):
            parse_work_unit(data)

    def test_rejects_non_github_source(self):
        data = {**BASE, "source": {**BASE["source"], "repo_url": "https://example.com/repo"}}
        with self.assertRaises(WorkUnitError):
            parse_work_unit(data)

    def test_rejects_unapproved_image(self):
        data = {**BASE, "execution": {**BASE["execution"], "image": "ubuntu:latest"}}
        with self.assertRaises(WorkUnitError):
            parse_work_unit(data)

    def test_rejects_unknown_top_level_fields(self):
        data = {**BASE, "surprise": True}
        with self.assertRaises(WorkUnitError):
            parse_work_unit(data)


if __name__ == "__main__":
    unittest.main()
