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
            "ExperimentManifest semantic contract tests require the Phase 0 jsonschema dependency"
        ) from exc
    raise


class ExperimentManifestConfigurationIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_path = MODULE.resolve_repo_path(
            "examples/experiments/phase0-smoke.manifest.json"
        )
        cls.fixture = MODULE.load_json(cls.fixture_path)

    def write_manifest(self, payload):
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".experiment-manifest.json",
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

    def test_canonical_manifest_semantics_still_pass(self):
        MODULE.validate_experiment_manifest_contract(self.fixture)

    def test_schema_valid_duplicate_configuration_id_fails_closed(self):
        mutated = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(mutated["configurations"][0])
        duplicate["description"] = "Distinct configuration body with a colliding logical id."
        mutated["configurations"].append(duplicate)

        self.assertEqual(
            MODULE.validation_errors(mutated, MODULE.MANIFEST_SCHEMA),
            [],
            "regression mutation must remain schema-valid so the semantic guard is exercised",
        )

        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"duplicate configuration id\(s\): single-local",
        ):
            MODULE.validate_experiment_manifest_contract(mutated)

    def test_all_duplicate_configuration_ids_are_reported_in_stable_order(self):
        mutated = copy.deepcopy(self.fixture)
        template = copy.deepcopy(mutated["configurations"][0])
        for configuration_id, description in (
            ("zeta-arm", "zeta first"),
            ("alpha-arm", "alpha first"),
            ("zeta-arm", "zeta second"),
            ("alpha-arm", "alpha second"),
        ):
            configuration = copy.deepcopy(template)
            configuration["id"] = configuration_id
            configuration["description"] = description
            mutated["configurations"].append(configuration)

        self.assertEqual(MODULE.validation_errors(mutated, MODULE.MANIFEST_SCHEMA), [])
        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"duplicate configuration id\(s\): alpha-arm, zeta-arm",
        ):
            MODULE.validate_experiment_manifest_contract(mutated)

    def test_manifest_preflight_rejects_duplicate_id_before_work_unit_io(self):
        mutated = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(mutated["configurations"][0])
        duplicate["description"] = "Duplicate arm used to exercise semantic preflight."
        mutated["configurations"].append(duplicate)
        mutated["work_units"][0]["path"] = "does/not/exist.work-unit.json"
        path = self.write_manifest(mutated)

        with self.assertRaisesRegex(
            MODULE.HarnessError,
            r"duplicate configuration id\(s\): single-local",
        ):
            MODULE.validate_manifest_and_work_units(path)


if __name__ == "__main__":
    unittest.main()
