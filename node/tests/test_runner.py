import tempfile
import unittest
from pathlib import Path

from idkmesh_node.model import parse_work_unit
from idkmesh_node.runner import docker_command


class DockerCommandTests(unittest.TestCase):
    def test_security_flags_are_present(self):
        work = parse_work_unit({
            "version": "0.1",
            "id": "security-test",
            "source": {
                "repo_url": "https://github.com/MSKazemi/idkmesh",
                "revision": "b" * 40,
            },
            "execution": {
                "image": "alpine:3.20",
                "command": ["true"],
                "network": "none",
            },
        })
        with tempfile.TemporaryDirectory() as temp:
            cmd = docker_command(work, Path(temp), "idkmesh-test")
        joined = " ".join(cmd)
        self.assertIn("--network none", joined)
        self.assertIn("--read-only", cmd)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("--security-opt no-new-privileges", joined)
        self.assertIn("--pids-limit", cmd)
        self.assertNotIn("--privileged", cmd)


if __name__ == "__main__":
    unittest.main()
