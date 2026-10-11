"""Machine-readable safety contract for GitHub WorkUnit intake (#608 C13-A)."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
INTAKE_SCHEMA_PATH = ROOT / "schemas" / "github-workunit-intake-v0.1.schema.json"
WORK_UNIT_SCHEMA_PATH = ROOT / "schemas" / "work-unit-v0.2.schema.json"


def _schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _intake(**overrides) -> dict:
    value = {
        "schema_version": "0.1",
        "kind": "idkmesh-github-workunit-intake",
        "objective": "Add a bounded regression test.",
        "task_class": "testing",
        "expected_outputs": ["A focused regression test"],
        "requested_allowed_paths": ["tests/**"],
        "requested_forbidden_paths": [".github/**", "SECURITY.md"],
        "dependencies": [
            {"reference": "#742", "relation": "informs"},
        ],
        "acceptance_checks": ["The focused test passes."],
        "risk_hint": "low",
        "external_processing_hint": "unspecified",
        "data_sensitivity_hint": "public",
        "human_review_hint": "required",
        "preferred_connector_hint": None,
        "authority_ceiling": {
            "policy_authority": False,
            "secret_authority": False,
            "command_authority": False,
            "network_authority": False,
            "filesystem_authority": False,
            "connector_selection_authority": False,
            "dispatch_authority": False,
            "verification_authority": False,
            "integration_authority": False,
        },
    }
    value.update(overrides)
    return value


class GitHubWorkUnitIntakeContractTests(unittest.TestCase):
    def test_task_class_vocabulary_matches_work_unit_kind(self) -> None:
        intake = _schema(INTAKE_SCHEMA_PATH)
        work_unit = _schema(WORK_UNIT_SCHEMA_PATH)
        self.assertEqual(
            set(intake["properties"]["task_class"]["enum"]),
            set(work_unit["properties"]["kind"]["enum"]),
        )

    def test_contract_has_no_direct_authority_fields(self) -> None:
        properties = set(_schema(INTAKE_SCHEMA_PATH)["properties"])
        forbidden = {
            "permissions",
            "secrets",
            "secret_ref",
            "command",
            "commands",
            "network",
            "filesystem_write",
            "selected_connector",
            "dispatch",
            "accepted",
            "merge_authority",
            "integration_authority",
        }
        self.assertTrue(forbidden.isdisjoint(properties))

    def test_authority_ceiling_is_structurally_all_false(self) -> None:
        authority = _schema(INTAKE_SCHEMA_PATH)["properties"]["authority_ceiling"]
        for name in authority["required"]:
            self.assertEqual(authority["properties"][name], {"const": False})


@unittest.skipUnless(HAS_JSONSCHEMA, "contract validation requires jsonschema")
class GitHubWorkUnitIntakeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = Draft202012Validator(_schema(INTAKE_SCHEMA_PATH))

    def assert_valid(self, document: dict) -> None:
        self.assertEqual([], list(self.validator.iter_errors(document)))

    def assert_invalid(self, document: dict) -> None:
        self.assertNotEqual([], list(self.validator.iter_errors(document)))

    def test_representative_intake_is_valid(self) -> None:
        self.assert_valid(_intake())

    def test_unexpected_authority_bearing_fields_fail_closed(self) -> None:
        for field, value in (
            ("secrets", ["env:TOKEN"]),
            ("command", ["sh", "-c", "do something"]),
            ("permissions", {"network": "unrestricted"}),
            ("selected_connector", "agent-powerful"),
            ("merge_authority", True),
        ):
            with self.subTest(field=field):
                candidate = _intake()
                candidate[field] = value
                self.assert_invalid(candidate)

    def test_no_authority_ceiling_flag_can_be_enabled(self) -> None:
        for field in _intake()["authority_ceiling"]:
            with self.subTest(field=field):
                candidate = copy.deepcopy(_intake())
                candidate["authority_ceiling"][field] = True
                self.assert_invalid(candidate)

    def test_hints_are_bounded_vocabularies_not_policy_objects(self) -> None:
        self.assert_invalid(_intake(risk_hint="none"))
        self.assert_invalid(_intake(external_processing_hint="force_external"))
        self.assert_invalid(_intake(data_sensitivity_hint="downgrade_to_public"))
        self.assert_invalid(_intake(human_review_hint="waived"))
        self.assert_invalid(_intake(preferred_connector_hint={"id": "agent-a"}))


if __name__ == "__main__":
    unittest.main()
