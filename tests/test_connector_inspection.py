import json
from pathlib import Path
import tempfile
import unittest

from idkmesh.connector_inspection import (
    ConnectorInspectionError,
    doctor_report,
    explain_route,
    inspect_connectors,
    parse_connector_costs,
    parse_routing_decision_document,
)
from idkmesh.connector_profiles import parse_connector_profile_document


CHECKED_AT = "2026-09-22T18:00:00Z"


def _config(
    *,
    connection_id="agent-a",
    kind="agent",
    driver="fake-agent",
    tiers=("T1", "T2"),
    task_classes=("coder",),
    tools=("git", "pytest"),
    max_risk="medium",
    external_processing=False,
    spend_ceiling=5.0,
    enabled=True,
    secret_ref=None,
):
    raw = {
        "api_version": "idkmesh.io/v1alpha1",
        "id": connection_id,
        "kind": kind,
        "driver": driver,
        "enabled": enabled,
        "capabilities": {
            "tiers": list(tiers),
            "task_classes": list(task_classes),
            "tools": list(tools),
            "max_risk": max_risk,
        },
        "policy": {
            "external_processing": external_processing,
            "project_spend_usd_max": spend_ceiling,
        },
    }
    if secret_ref is not None:
        raw["auth"] = {"secret_ref": secret_ref}
    return parse_connector_profile_document(raw)[0]


def _decision(**overrides):
    raw = {
        "required_capability_tier": "T1",
        "authority_mode": "agent_candidate",
        "risk_class": "low",
        "task_classes": ["coder"],
        "required_tools": ["git"],
        "allowed_connector_kinds": ["agent"],
        "external_processing_allowed": True,
        "project_spend_usd_max": 0,
    }
    raw.update(overrides)
    return parse_routing_decision_document(raw)


class ConnectorInspectionTests(unittest.TestCase):
    def test_offline_fake_probe_is_healthy_and_serializable(self):
        inspected = inspect_connectors([_config()], checked_at=CHECKED_AT)

        self.assertEqual(len(inspected), 1)
        self.assertIsNone(inspected[0].error_code)
        self.assertEqual(inspected[0].probe.status, "healthy")
        rendered = json.dumps(inspected[0].to_dict(), sort_keys=True)
        self.assertNotIn("secret_ref", rendered)

    def test_unknown_driver_is_reported_as_stable_inspection_error(self):
        inspected = inspect_connectors(
            [_config(driver="not-registered")],
            checked_at=CHECKED_AT,
        )

        self.assertEqual(inspected[0].error_code, "unknown_driver")
        self.assertIsNone(inspected[0].probe)

    def test_secret_reference_is_not_materialized_by_read_only_inspection(self):
        inspected = inspect_connectors(
            [_config(secret_ref="env:DO_NOT_READ_THIS")],
            checked_at=CHECKED_AT,
        )

        self.assertEqual(inspected[0].probe.status, "unavailable")
        self.assertEqual(inspected[0].probe.failure.code, "secret_unavailable")
        rendered = json.dumps(inspected[0].to_dict(), sort_keys=True)
        self.assertNotIn("DO_NOT_READ_THIS", rendered)

    def test_doctor_distinguishes_pass_warn_and_fail(self):
        passed = doctor_report(
            inspect_connectors([_config()], checked_at=CHECKED_AT)
        )
        self.assertEqual(passed["status"], "PASS")

        warned = doctor_report(
            inspect_connectors(
                [_config(enabled=False)],
                checked_at=CHECKED_AT,
            )
        )
        self.assertEqual(warned["status"], "WARN")
        self.assertEqual(warned["connections"][0]["reason"], "disabled")

        failed = doctor_report(
            inspect_connectors(
                [_config(driver="not-registered")],
                checked_at=CHECKED_AT,
            )
        )
        self.assertEqual(failed["status"], "FAIL")
        self.assertEqual(failed["connections"][0]["reason"], "unknown_driver")

    def test_human_required_route_blocks_even_healthy_connector(self):
        inspected = inspect_connectors([_config()], checked_at=CHECKED_AT)
        report = explain_route(
            _decision(authority_mode="human_required"),
            inspected,
            auto_select=True,
        )

        self.assertIsNone(report["selected_connection_id"])
        self.assertIn(
            "human_required",
            report["ineligible"][0]["reasons"],
        )

    def test_t4_route_cannot_fall_through_to_t2_fake_agent(self):
        inspected = inspect_connectors([_config()], checked_at=CHECKED_AT)
        report = explain_route(
            _decision(required_capability_tier="T4"),
            inspected,
        )

        self.assertEqual(report["eligible"], [])
        self.assertIn(
            "insufficient_capability_tier",
            report["ineligible"][0]["reasons"],
        )

    def test_profile_t4_claim_cannot_upgrade_registered_driver(self):
        inspected = inspect_connectors(
            [_config(tiers=("T4",))],
            checked_at=CHECKED_AT,
        )
        report = explain_route(
            _decision(required_capability_tier="T4"),
            inspected,
        )

        self.assertIn(
            "insufficient_capability_tier",
            report["ineligible"][0]["reasons"],
        )

    def test_risk_ceiling_is_visible(self):
        inspected = inspect_connectors([_config()], checked_at=CHECKED_AT)
        report = explain_route(
            _decision(risk_class="high"),
            inspected,
        )

        self.assertIn("risk_not_allowed", report["ineligible"][0]["reasons"])

    def test_external_processing_denial_is_visible(self):
        config = _config(
            connection_id="model-a",
            kind="model",
            driver="fake-model",
            tiers=("T1", "T2", "T3"),
            task_classes=("inference",),
            tools=(),
            max_risk="medium",
            external_processing=True,
        )
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        report = explain_route(
            _decision(
                task_classes=["inference"],
                required_tools=[],
                allowed_connector_kinds=["model"],
                external_processing_allowed=False,
            ),
            inspected,
        )

        self.assertIn(
            "external_processing_forbidden",
            report["ineligible"][0]["reasons"],
        )

    def test_project_spend_denial_is_visible_separately_from_profile_ceiling(self):
        inspected = inspect_connectors(
            [_config(spend_ceiling=5.0)],
            checked_at=CHECKED_AT,
        )
        report = explain_route(
            _decision(project_spend_usd_max=0),
            inspected,
            connector_costs={"agent-a": 1.0},
        )

        self.assertIn(
            "project_spend_exceeded",
            report["ineligible"][0]["reasons"],
        )

    def test_connector_profile_spend_ceiling_fails_before_project_route(self):
        inspected = inspect_connectors(
            [_config(spend_ceiling=0.5)],
            checked_at=CHECKED_AT,
        )
        report = explain_route(
            _decision(project_spend_usd_max=5),
            inspected,
            connector_costs={"agent-a": 1.0},
        )

        self.assertEqual(
            report["ineligible"][0]["reasons"],
            ["connector_spend_policy_exceeded"],
        )

    def test_auto_select_is_explicit(self):
        inspected = inspect_connectors([_config()], checked_at=CHECKED_AT)

        preview = explain_route(_decision(), inspected, auto_select=False)
        selected = explain_route(_decision(), inspected, auto_select=True)

        self.assertIsNone(preview["selected_connection_id"])
        self.assertEqual(selected["selected_connection_id"], "agent-a")

    def test_decision_parser_rejects_unknown_fields_and_bad_types(self):
        with self.assertRaises(ConnectorInspectionError) as unknown:
            parse_routing_decision_document(
                {
                    "required_capability_tier": "T1",
                    "authority_mode": "agent_candidate",
                    "provider": "jules",
                }
            )
        self.assertEqual(unknown.exception.code, "unknown_field")

        with self.assertRaises(ConnectorInspectionError) as wrong_type:
            parse_routing_decision_document(
                {
                    "required_capability_tier": "T1",
                    "authority_mode": "agent_candidate",
                    "task_classes": "coder",
                }
            )
        self.assertEqual(wrong_type.exception.code, "invalid_type")

    def test_cost_parser_is_strict(self):
        self.assertEqual(
            parse_connector_costs(["agent-a=1.25"]),
            {"agent-a": 1.25},
        )
        with self.assertRaises(ConnectorInspectionError):
            parse_connector_costs(["agent-a"])
        with self.assertRaises(ConnectorInspectionError):
            parse_connector_costs(["agent-a=1", "agent-a=2"])


if __name__ == "__main__":
    unittest.main()
