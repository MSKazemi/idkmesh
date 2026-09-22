from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.enterprise_profile import (
    EnterpriseProfileError,
    evaluate_profile,
    summarize,
    validate_structure,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "enterprise-control-profile.example.json"


def load_example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def finding_map(profile):
    return {item.code: item for item in evaluate_profile(profile)}


class EnterpriseProfileTests(unittest.TestCase):
    def test_reference_profile_is_declaration_ready(self):
        result = summarize(load_example())
        self.assertTrue(result["declaration_ready"])
        self.assertEqual(result["counts"]["FAIL"], 0)
        self.assertIn("does not prove observed enforcement", result["authority"])

    def test_g3_requires_multi_tenant_enforced_isolation(self):
        profile = load_example()
        profile["deployment"]["tenant_isolation"] = "declared"
        findings = finding_map(profile)
        self.assertEqual(findings["tenant.g3_isolation"].status, "FAIL")

    def test_non_g3_cannot_claim_shared_multi_tenant_mode(self):
        profile = load_example()
        profile["deployment"]["profile"] = "G2"
        findings = finding_map(profile)
        self.assertEqual(findings["tenant.profile_alignment"].status, "FAIL")

    def test_production_audit_only_mode_fails(self):
        profile = load_example()
        profile["metadata"]["enforcement_mode"] = "audit"
        findings = finding_map(profile)
        self.assertEqual(
            findings["production.enforcement_mode"].status,
            "FAIL",
        )

    def test_restricted_data_cannot_be_external_processing_eligible(self):
        profile = load_example()
        profile["data"]["external_processing_allowed_classes"].append(
            "restricted"
        )
        findings = finding_map(profile)
        self.assertEqual(
            findings["data.restricted_external_processing"].status,
            "FAIL",
        )

    def test_production_long_lived_cloud_keys_fail(self):
        profile = load_example()
        profile["secrets"]["long_lived_cloud_keys_allowed"] = True
        findings = finding_map(profile)
        self.assertEqual(
            findings["secrets.long_lived_cloud_keys"].status,
            "FAIL",
        )

    def test_production_requires_mfa_sod_and_two_person_rule(self):
        profile = load_example()
        profile["identity"]["mfa_required"] = False
        profile["identity"]["high_risk_separation_of_duties"] = False
        profile["change_management"]["high_risk_two_person_rule"] = False
        findings = finding_map(profile)
        self.assertEqual(findings["identity.mfa"].status, "FAIL")
        self.assertEqual(findings["identity.high_risk_sod"].status, "FAIL")
        self.assertEqual(
            findings["change.high_risk_two_person"].status,
            "FAIL",
        )

    def test_enabled_break_glass_must_be_reasoned_audited_and_bounded(self):
        profile = load_example()
        profile["change_management"]["break_glass"]["reason_required"] = False
        findings = finding_map(profile)
        self.assertEqual(findings["change.break_glass"].status, "FAIL")

    def test_service_production_requires_audit_export_and_workload_identity(self):
        profile = load_example()
        profile["audit"]["external_export_required"] = False
        profile["secrets"]["workload_identity"] = "none"
        findings = finding_map(profile)
        self.assertEqual(findings["audit.external_export"].status, "FAIL")
        self.assertEqual(
            findings["secrets.service_workload_identity"].status,
            "FAIL",
        )

    def test_shorter_retention_and_restore_interval_are_warnings_not_failures(self):
        profile = load_example()
        profile["audit"]["retention_days"] = 90
        profile["reliability"]["restore_test_interval_days"] = 180
        result = summarize(profile)
        findings = finding_map(profile)
        self.assertTrue(result["declaration_ready"])
        self.assertEqual(findings["audit.retention"].status, "WARN")
        self.assertEqual(
            findings["reliability.restore_test_interval"].status,
            "WARN",
        )

    def test_development_profile_can_use_audit_mode(self):
        profile = load_example()
        profile["metadata"]["environment"] = "development"
        profile["metadata"]["enforcement_mode"] = "audit"
        profile["deployment"] = {
            "profile": "G0",
            "tenant_mode": "single_project",
            "tenant_isolation": "not_applicable",
            "network_mode": "public",
        }
        result = summarize(profile)
        self.assertEqual(result["counts"]["FAIL"], 0)

    def test_unknown_top_level_field_fails_structure(self):
        profile = load_example()
        profile["compliant"] = True
        with self.assertRaisesRegex(
            EnterpriseProfileError,
            "unknown top-level",
        ):
            validate_structure(profile)

    def test_missing_required_section_fails_structure(self):
        profile = load_example()
        del profile["audit"]
        with self.assertRaisesRegex(
            EnterpriseProfileError,
            "audit must be an object",
        ):
            validate_structure(profile)

    def test_unknown_nested_field_fails_structure(self):
        profile = load_example()
        profile["identity"]["super_admin"] = True
        with self.assertRaisesRegex(
            EnterpriseProfileError,
            "identity has unknown field",
        ):
            validate_structure(profile)

    def test_non_string_external_processing_class_fails_cleanly(self):
        profile = load_example()
        profile["data"]["external_processing_allowed_classes"] = [
            "public",
            {"class": "internal"},
        ]
        with self.assertRaisesRegex(
            EnterpriseProfileError,
            "must contain strings",
        ):
            validate_structure(profile)

    def test_non_finite_availability_target_fails_structure(self):
        profile = load_example()
        profile["reliability"]["availability_target_percent"] = float("nan")
        with self.assertRaisesRegex(EnterpriseProfileError, "must be finite"):
            validate_structure(profile)

    def test_duplicate_external_processing_class_fails_structure(self):
        profile = load_example()
        profile["data"]["external_processing_allowed_classes"] = [
            "public",
            "public",
        ]
        with self.assertRaisesRegex(EnterpriseProfileError, "duplicates"):
            validate_structure(profile)

    def test_json_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(
                json.dumps(load_example(), indent=2),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "tools" / "enterprise_profile.py"),
                str(path),
                "--json",
            ]
            first = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertTrue(payload["declaration_ready"])

    def test_cli_returns_one_for_semantic_failure_and_two_for_parse_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            failing = load_example()
            failing["metadata"]["enforcement_mode"] = "audit"
            fail_path = Path(tmp) / "fail.json"
            fail_path.write_text(json.dumps(failing), encoding="utf-8")
            fail = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "enterprise_profile.py"),
                    str(fail_path),
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text("{", encoding="utf-8")
            bad = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "enterprise_profile.py"),
                    str(bad_path),
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(fail.returncode, 1)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(fail.stdout)["declaration_ready"])
        self.assertFalse(json.loads(bad.stderr)["declaration_ready"])


if __name__ == "__main__":
    unittest.main()
