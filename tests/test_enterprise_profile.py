"""Tests for Enterprise Control Profile v0.1."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.enterprise_profile import (
    EnterpriseProfileError,
    parse_enterprise_profile_text,
    validate_enterprise_profile,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "enterprise-control-profile-v0.1.schema.json"
G1_PATH = ROOT / "examples" / "enterprise" / "g1-github-native.example.json"
G2_PATH = ROOT / "examples" / "enterprise" / "g2-self-hosted.example.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class EnterpriseProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.g1 = load(G1_PATH)
        cls.g2 = load(G2_PATH)

    def test_retained_examples_pass_dependency_free_validation(self) -> None:
        validate_enterprise_profile(deepcopy(self.g1))
        validate_enterprise_profile(deepcopy(self.g2))

    def test_profile_is_explicitly_policy_input_not_observed_control(self) -> None:
        for profile in (self.g1, self.g2):
            self.assertEqual(
                profile["semantics"]["profile_role"],
                "policy_input_only",
            )
            self.assertEqual(
                profile["semantics"]["control_evidence"],
                "declared_not_observed",
            )
            self.assertFalse(
                profile["semantics"]["grants_runtime_authority"]
            )

    def test_profile_id_matches_schema_boundary(self) -> None:
        profile = deepcopy(self.g1)
        profile["profile_id"] = ".hidden"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "invalid_value")
        self.assertEqual(caught.exception.path, "$.profile_id")

    def test_unknown_fields_fail_closed(self) -> None:
        profile = deepcopy(self.g1)
        profile["deployment"]["magic_admin_mode"] = True

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "unknown_field")
        self.assertIn("magic_admin_mode", str(caught.exception))

    def test_g1_cannot_substitute_local_identity(self) -> None:
        profile = deepcopy(self.g1)
        profile["identity"]["human_source"] = "local_trusted_operator"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(caught.exception.path, "$.identity.human_source")

    def test_g2_requires_long_lived_service_and_remote_api(self) -> None:
        profile = deepcopy(self.g2)
        profile["deployment"]["coordinator_lifecycle"] = "local_process"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(
            caught.exception.path,
            "$.deployment.coordinator_lifecycle",
        )

    def test_g3_requires_multi_tenant_scope_distinct_approval_and_supply_chain(self) -> None:
        profile = deepcopy(self.g2)
        profile["profile_id"] = "g3-invalid"
        profile["deployment"]["profile"] = "g3_multi_tenant_service"
        profile["deployment"]["tenant_scope"] = "single_org"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(caught.exception.path, "$.deployment.tenant_scope")

    def test_break_glass_requires_audit_and_reason(self) -> None:
        profile = deepcopy(self.g2)
        profile["audit"]["enabled"] = False
        profile["audit"]["tamper_evident_required"] = False
        profile["audit"]["export"] = "none"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(
            caught.exception.path,
            "$.identity.break_glass_enabled",
        )

    def test_oidc_workload_identity_forbids_long_lived_cloud_keys(self) -> None:
        profile = deepcopy(self.g2)
        profile["secrets"]["long_lived_cloud_keys_allowed"] = True

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(
            caught.exception.path,
            "$.secrets.long_lived_cloud_keys_allowed",
        )

    def test_enforce_mode_fails_closed_on_unknown_controls(self) -> None:
        profile = deepcopy(self.g1)
        profile["enforcement"]["unknown_control_behavior"] = "warn"

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(
            caught.exception.path,
            "$.enforcement.unknown_control_behavior",
        )

    def test_default_data_class_must_be_admitted(self) -> None:
        profile = deepcopy(self.g1)
        profile["data"]["allowed_classifications"] = ["public"]

        with self.assertRaises(EnterpriseProfileError) as caught:
            validate_enterprise_profile(profile)

        self.assertEqual(caught.exception.code, "contradictory_profile")
        self.assertEqual(
            caught.exception.path,
            "$.data.default_classification",
        )

    def test_parser_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        duplicate = (
            '{"kind":"idkmesh-enterprise-control-profile",'
            '"kind":"idkmesh-enterprise-control-profile"}'
        )
        with self.assertRaises(EnterpriseProfileError) as caught:
            parse_enterprise_profile_text(duplicate, source="duplicate.json")
        self.assertEqual(caught.exception.code, "duplicate_key")

        text = json.dumps(self.g1).replace(
            '"availability_target": 0.99',
            '"availability_target": NaN',
        )
        with self.assertRaises(EnterpriseProfileError) as nonfinite:
            parse_enterprise_profile_text(text, source="nan.json")
        self.assertEqual(nonfinite.exception.code, "invalid_json_number")


@unittest.skipUnless(HAS_JSONSCHEMA, "schema validation requires jsonschema")
class EnterpriseProfileSchemaTests(unittest.TestCase):
    def test_schema_is_valid_and_examples_conform(self) -> None:
        schema = load(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)

        for path in (G1_PATH, G2_PATH):
            with self.subTest(example=path.name):
                validator.validate(load(path))

    def test_schema_forbids_authority_broadening(self) -> None:
        schema = load(SCHEMA_PATH)
        profile = load(G1_PATH)
        profile["authority"]["worker_can_merge"] = True

        errors = list(Draft202012Validator(schema).iter_errors(profile))

        self.assertTrue(errors)
        self.assertTrue(
            any(
                list(error.absolute_path)
                == ["authority", "worker_can_merge"]
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
