import copy
import json
import tempfile
import unittest
from pathlib import Path

try:
    from experiments import harness as MODULE
except ModuleNotFoundError as exc:
    if exc.name == "jsonschema":
        raise unittest.SkipTest(
            "ResultManifest semantic contract tests require the Phase 0 jsonschema dependency"
        ) from exc
    raise


class ResultManifestArtifactIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_path = MODULE.resolve_repo_path(
            "examples/results/phase0-smoke.result-manifest.json"
        )
        cls.fixture = MODULE.load_json(cls.fixture_path)
        cls.work_units = {
            cls.fixture["work_unit_id"]: {"version": cls.fixture["work_unit_version"]}
        }

    def write_result(self, payload):
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".result-manifest.json",
            encoding="utf-8",
            delete=False,
        )
        try:
            json.dump(payload, handle)
        finally:
            handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_canonical_result_manifest_still_passes(self):
        result = MODULE.validate_worker_result_contract(
            self.fixture_path,
            self.work_units,
        )
        self.assertEqual(result["id"], self.fixture["id"])

    def test_schema_valid_duplicate_artifact_id_fails_closed(self):
        mutated = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(mutated["produced_artifacts"][0])
        duplicate["locator"] = "results/phase0-smoke-shadow.jsonl"
        duplicate["digest"] = "sha256:" + "f" * 64
        mutated["produced_artifacts"].append(duplicate)

        self.assertEqual(
            MODULE.validation_errors(mutated, MODULE.WORKER_RESULT_SCHEMA),
            [],
            "regression mutation must remain schema-valid so the semantic guard is exercised",
        )

        path = self.write_result(mutated)
        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"duplicate produced artifact id\(s\): candidate-result",
        ):
            MODULE.validate_worker_result_contract(path, self.work_units)

    def test_all_duplicate_artifact_ids_are_reported_in_stable_order(self):
        mutated = copy.deepcopy(self.fixture)
        candidate = mutated["produced_artifacts"][0]
        alpha = copy.deepcopy(candidate)
        alpha.update(
            {
                "id": "alpha-result",
                "locator": "results/alpha.jsonl",
                "digest": "sha256:" + "2" * 64,
            }
        )
        mutated["produced_artifacts"].extend(
            [
                alpha,
                {**copy.deepcopy(candidate), "locator": "results/candidate-copy.jsonl"},
                {**copy.deepcopy(alpha), "locator": "results/alpha-copy.jsonl"},
            ]
        )

        self.assertEqual(
            MODULE.validation_errors(mutated, MODULE.WORKER_RESULT_SCHEMA),
            [],
            "multiple duplicate IDs must remain schema-valid so semantic validation is exercised",
        )

        path = self.write_result(mutated)
        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"duplicate produced artifact id\(s\): alpha-result, candidate-result",
        ):
            MODULE.validate_worker_result_contract(path, self.work_units)

    def test_unknown_requested_artifact_still_fails(self):
        mutated = copy.deepcopy(self.fixture)
        mutated["verification_request"]["evidence_artifact_ids"] = ["missing-result"]
        path = self.write_result(mutated)

        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"unknown artifact id\(s\): missing-result",
        ):
            MODULE.validate_worker_result_contract(path, self.work_units)


if __name__ == "__main__":
    unittest.main()
