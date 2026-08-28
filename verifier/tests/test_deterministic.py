from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from verifier.deterministic import VerificationError, file_digest, verify

ROOT = Path(__file__).resolve().parents[2]
WORK_UNIT = ROOT / "examples/work-units/deterministic-verifier.work-unit.json"
RESULT = ROOT / "examples/verifier-bundle/result-manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DeterministicVerifierTests(unittest.TestCase):
    def test_good_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "verification.json"
            result, code = verify(
                repo_root=ROOT,
                artifact_root=ROOT,
                work_unit_path=WORK_UNIT,
                result_manifest_path=RESULT,
                output_path=output,
                verifier_id="test-independent-verifier",
            )
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                result["decision_support"]["recommendation"], "accept_candidate"
            )
            required = {check["id"]: check for check in result["checks"] if check["required"]}
            self.assertEqual(
                set(required),
                {
                    "result-manifest-schema",
                    "work-unit-digest",
                    "artifact-digests",
                    "path-policy",
                },
            )
            self.assertTrue(all(check["status"] == "passed" for check in required.values()))
            self.assertTrue(output.is_file())

    def test_digest_mismatch_rejects_candidate(self) -> None:
        manifest = load_json(RESULT)
        manifest["produced_artifacts"][0]["digest"] = "sha256:" + "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            manifest_path = temp / "result.json"
            output = temp / "verification.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, code = verify(
                repo_root=ROOT,
                artifact_root=ROOT,
                work_unit_path=WORK_UNIT,
                result_manifest_path=manifest_path,
                output_path=output,
                verifier_id="test-independent-verifier",
            )
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "failed")
            checks = {check["id"]: check for check in result["checks"]}
            self.assertEqual(checks["artifact-digests"]["status"], "failed")
            self.assertGreater(result["metrics"]["digest_failures"], 0)

    def test_out_of_scope_patch_rejects_candidate(self) -> None:
        manifest = load_json(RESULT)
        bad_patch = """diff --git a/SECURITY.md b/SECURITY.md
index 1111111..2222222 100644
--- a/SECURITY.md
+++ b/SECURITY.md
@@ -1 +1,2 @@
 # Security
+unauthorized fixture change
"""
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            patch_path = temp / "candidate.patch"
            patch_path.write_text(bad_patch, encoding="utf-8")
            manifest["produced_artifacts"][0]["locator"] = "candidate.patch"
            manifest["produced_artifacts"][0]["digest"] = file_digest(patch_path)
            manifest_path = temp / "result.json"
            output = temp / "verification.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, code = verify(
                repo_root=ROOT,
                artifact_root=temp,
                work_unit_path=WORK_UNIT,
                result_manifest_path=manifest_path,
                output_path=output,
                verifier_id="test-independent-verifier",
            )
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "failed")
            checks = {check["id"]: check for check in result["checks"]}
            self.assertEqual(checks["artifact-digests"]["status"], "passed")
            self.assertEqual(checks["path-policy"]["status"], "failed")
            self.assertGreater(result["metrics"]["path_violations"], 0)

    def test_worker_cannot_verify_own_result(self) -> None:
        manifest = load_json(RESULT)
        worker_id = manifest["worker"]["id"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(VerificationError):
                verify(
                    repo_root=ROOT,
                    artifact_root=ROOT,
                    work_unit_path=WORK_UNIT,
                    result_manifest_path=RESULT,
                    output_path=Path(tmp) / "verification.json",
                    verifier_id=worker_id,
                )

    def test_locator_escape_fails_closed(self) -> None:
        manifest = load_json(RESULT)
        manifest["produced_artifacts"][0]["locator"] = "../outside.patch"
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            manifest_path = temp / "result.json"
            output = temp / "verification.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, code = verify(
                repo_root=ROOT,
                artifact_root=temp,
                work_unit_path=WORK_UNIT,
                result_manifest_path=manifest_path,
                output_path=output,
                verifier_id="test-independent-verifier",
            )
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(
                any("escapes artifact root" in finding["summary"] for finding in result["findings"])
            )


if __name__ == "__main__":
    unittest.main()
