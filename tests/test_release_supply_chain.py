from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.build_release_supply_chain import build_metadata, main


SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


class ReleaseSupplyChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "pyproject.toml").write_text(
            """[project]
name = "idkmesh"
version = "0.1.0"
dependencies = []
[project.optional-dependencies]
verify = ["jsonschema>=4.26,<5"]
""",
            encoding="utf-8",
        )
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "idkmesh-0.1.0.tar.gz").write_bytes(b"sdist")
        (self.dist / "idkmesh-0.1.0-py3-none-any.whl").write_bytes(b"wheel")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metadata_binds_artifacts_source_workflow_and_dependency_inventory(self) -> None:
        sbom, provenance, checksums = build_metadata(
            pyproject=self.root / "pyproject.toml",
            dist_dir=self.dist,
            source_sha=SHA,
            source_ref="refs/tags/v0.1.0",
            workflow_ref="MSKazemi/idkmesh/.github/workflows/publish-pypi.yml@refs/tags/v0.1.0",
            workflow_sha=WORKFLOW_SHA,
            run_id="123",
            run_attempt="2",
            created_at="2026-10-08T00:00:00Z",
        )
        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        annotation = json.loads(sbom["packages"][0]["annotations"][0]["comment"])
        self.assertEqual(annotation["runtime_dependencies"], [])
        self.assertEqual(
            annotation["optional_dependencies"]["verify"],
            ["jsonschema>=4.26,<5"],
        )
        self.assertEqual(provenance["source"]["commit_sha"], SHA)
        self.assertEqual(provenance["workflow"]["commit_sha"], WORKFLOW_SHA)
        self.assertEqual(len(provenance["artifacts"]), 2)
        self.assertFalse(provenance["authority"]["proves_functional_correctness"])
        for artifact in provenance["artifacts"]:
            self.assertIn(artifact["sha256"], checksums)
            self.assertIn(artifact["name"], checksums)

    def test_metadata_is_deterministic_for_same_inputs(self) -> None:
        kwargs = dict(
            pyproject=self.root / "pyproject.toml",
            dist_dir=self.dist,
            source_sha=SHA,
            source_ref="refs/tags/v0.1.0",
            workflow_ref="workflow@tag",
            workflow_sha=WORKFLOW_SHA,
            run_id="123",
            run_attempt="1",
            created_at="2026-10-08T00:00:00Z",
        )
        self.assertEqual(build_metadata(**kwargs), build_metadata(**kwargs))

    def test_invalid_sha_or_empty_dist_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "40-hex"):
            build_metadata(
                pyproject=self.root / "pyproject.toml",
                dist_dir=self.dist,
                source_sha="main",
                source_ref="refs/heads/main",
                workflow_ref="workflow@main",
                workflow_sha=WORKFLOW_SHA,
                run_id="1",
                run_attempt="1",
                created_at="2026-10-08T00:00:00Z",
            )
        for path in self.dist.iterdir():
            path.unlink()
        with self.assertRaisesRegex(ValueError, "no release artifacts"):
            build_metadata(
                pyproject=self.root / "pyproject.toml",
                dist_dir=self.dist,
                source_sha=SHA,
                source_ref="refs/tags/v0.1.0",
                workflow_ref="workflow@tag",
                workflow_sha=WORKFLOW_SHA,
                run_id="1",
                run_attempt="1",
                created_at="2026-10-08T00:00:00Z",
            )

    def test_cli_writes_expected_files(self) -> None:
        out = self.root / "metadata"
        rc = main([
            "--pyproject", str(self.root / "pyproject.toml"),
            "--dist", str(self.dist),
            "--output", str(out),
            "--source-sha", SHA,
            "--source-ref", "refs/tags/v0.1.0",
            "--workflow-ref", "workflow@tag",
            "--workflow-sha", WORKFLOW_SHA,
            "--run-id", "1",
            "--run-attempt", "1",
            "--created-at", "2026-10-08T00:00:00Z",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(
            {p.name for p in out.iterdir()},
            {"checksums.txt", "release-provenance.json", "sbom.spdx.json"},
        )


if __name__ == "__main__":
    unittest.main()
