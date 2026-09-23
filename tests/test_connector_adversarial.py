from copy import deepcopy
import json
from pathlib import Path
import unittest

from idkmesh.connector_inspection import (
    ConnectorInspectionError,
    explain_route,
    inspect_connectors,
    parse_routing_decision_document,
)
from idkmesh.connector_profiles import (
    ConnectorProfileError,
    parse_connector_profile_document,
)
from idkmesh.connector_routing import (
    ConnectorProfile,
    RoutingDecision,
    resolve_routes,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "connector_adversarial" / "cases.json"
)
CHECKED_AT = "2026-09-22T18:30:00Z"


def _cases():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _normal_agent(cases):
    raw = deepcopy(cases["profile_t4_overclaim"])
    raw["id"] = "agent-a"
    raw["capabilities"]["tiers"] = ["T1", "T2"]
    return raw


class ConnectorAdversarialFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = _cases()

    def test_inline_secret_is_rejected_without_echoing_value(self):
        sentinel = "sentinel-must-never-render"
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(
                self.cases["profile_inline_secret"]
            )

        self.assertEqual(caught.exception.code, "inline_secret_forbidden")
        self.assertNotIn(sentinel, str(caught.exception))

    def test_secret_ref_outside_auth_is_rejected(self):
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(
                self.cases["profile_secret_ref_outside_auth"]
            )

        self.assertEqual(caught.exception.code, "secret_ref_outside_auth")

    def test_routing_input_cannot_inject_secret_reference(self):
        with self.assertRaises(ConnectorInspectionError) as caught:
            parse_routing_decision_document(
                self.cases["decision_secret_injection"]
            )

        self.assertEqual(caught.exception.code, "unknown_field")
        self.assertNotIn(
            "SHOULD_NOT_BE_ACCEPTED",
            str(caught.exception),
        )

    def test_routing_input_cannot_choose_executable(self):
        with self.assertRaises(ConnectorInspectionError) as caught:
            parse_routing_decision_document(
                self.cases["decision_executable_injection"]
            )

        self.assertEqual(caught.exception.code, "unknown_field")

    def test_free_text_negative_scope_phrase_is_not_a_routing_control_field(self):
        with self.assertRaises(ConnectorInspectionError) as caught:
            parse_routing_decision_document(
                self.cases["decision_negative_scope_text"]
            )

        self.assertEqual(caught.exception.code, "unknown_field")
        self.assertIn("$.task_text", str(caught.exception))

    def test_profile_t4_overclaim_cannot_upgrade_fake_agent(self):
        config = parse_connector_profile_document(
            self.cases["profile_t4_overclaim"]
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        decision = parse_routing_decision_document(
            self.cases["decision_t4"]
        )

        report = explain_route(decision, inspected)

        self.assertEqual(report["eligible"], [])
        self.assertIn(
            "insufficient_capability_tier",
            report["ineligible"][0]["reasons"],
        )

    def test_human_required_t4_blocks_a_genuinely_t4_profile(self):
        decision = RoutingDecision(
            required_capability_tier="T4",
            authority_mode="human_required",
            risk_class="high",
            task_classes=frozenset({"coder"}),
            required_tools=frozenset({"git"}),
            allowed_connector_kinds=frozenset({"agent"}),
            project_spend_usd_max=0,
        )
        profile = ConnectorProfile(
            connection_id="peak-agent",
            kind="agent",
            driver="fake-peak",
            enabled=True,
            health="healthy",
            capability_tiers=frozenset({"T4"}),
            task_classes=frozenset({"coder"}),
            tools=frozenset({"git"}),
            max_risk="high",
            external_processing=False,
            project_cost_usd=0,
            secret_required=False,
            secret_available=True,
            capacity_available=True,
            provider_family="family-peak",
        )

        result = resolve_routes(decision, [profile], auto_select=True)

        self.assertIsNone(result.selected_connection_id)
        self.assertIn("human_required", result.ineligible[0].reasons)

    def test_high_risk_task_is_rejected_by_medium_risk_driver(self):
        config = parse_connector_profile_document(
            _normal_agent(self.cases)
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        decision = parse_routing_decision_document(
            self.cases["decision_high_risk"]
        )

        report = explain_route(decision, inspected)

        self.assertIn(
            "risk_not_allowed",
            report["ineligible"][0]["reasons"],
        )

    def test_external_processing_forbidden_rejects_external_model(self):
        config = parse_connector_profile_document(
            self.cases["profile_fake_model"]
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        decision = parse_routing_decision_document(
            self.cases["decision_no_external"]
        )

        report = explain_route(decision, inspected)

        self.assertIn(
            "external_processing_forbidden",
            report["ineligible"][0]["reasons"],
        )

    def test_project_spend_ceiling_rejection_is_stable(self):
        config = parse_connector_profile_document(
            _normal_agent(self.cases)
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        decision = parse_routing_decision_document(
            self.cases["decision_zero_spend"]
        )

        first = explain_route(
            decision,
            inspected,
            connector_costs={"agent-a": 1.0},
        )
        second = explain_route(
            decision,
            inspected,
            connector_costs={"agent-a": 1.0},
        )

        self.assertEqual(first, second)
        self.assertIn(
            "project_spend_exceeded",
            first["ineligible"][0]["reasons"],
        )

    def test_missing_secret_remains_unavailable_without_materialization(self):
        config = parse_connector_profile_document(
            self.cases["profile_missing_secret"]
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)

        self.assertEqual(inspected[0].probe.status, "unavailable")
        self.assertEqual(
            inspected[0].probe.failure.code,
            "secret_unavailable",
        )
        rendered = json.dumps(inspected[0].to_dict(), sort_keys=True)
        self.assertNotIn("UNRESOLVED_PROVIDER_KEY", rendered)

    def test_disabled_connector_stays_ineligible(self):
        config = parse_connector_profile_document(
            self.cases["profile_disabled"]
        )[0]
        inspected = inspect_connectors([config], checked_at=CHECKED_AT)
        decision = parse_routing_decision_document(
            self.cases["decision_zero_spend"]
        )

        report = explain_route(decision, inspected)

        self.assertIn(
            "connector_disabled",
            report["ineligible"][0]["reasons"],
        )

    def test_duplicate_connection_ids_fail_closed(self):
        with self.assertRaises(ConnectorProfileError) as caught:
            parse_connector_profile_document(
                self.cases["profile_duplicate_ids"]
            )

        self.assertEqual(caught.exception.code, "duplicate_connection_id")

    def test_deterministic_tie_break_is_stable(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            allowed_connector_kinds=frozenset({"agent"}),
            project_spend_usd_max=0,
        )
        profiles = [
            ConnectorProfile(
                connection_id=connection_id,
                kind="agent",
                driver="fake",
                enabled=True,
                health="healthy",
                capability_tiers=frozenset({"T1"}),
                task_classes=frozenset({"coder"}),
                max_risk="low",
                project_cost_usd=0,
                capacity_available=True,
            )
            for connection_id in ("zeta", "alpha")
        ]

        first = resolve_routes(decision, profiles, auto_select=True)
        second = resolve_routes(
            decision, list(reversed(profiles)), auto_select=True
        )

        self.assertEqual(first.selected_connection_id, "alpha")
        self.assertEqual(second.selected_connection_id, "alpha")

    def test_same_family_avoidance_prefers_different_family(self):
        decision = RoutingDecision(
            required_capability_tier="T2",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            allowed_connector_kinds=frozenset({"agent"}),
            project_spend_usd_max=0,
            avoid_provider_families=frozenset({"family-a"}),
        )
        profiles = [
            ConnectorProfile(
                connection_id="same-family",
                kind="agent",
                driver="fake",
                health="healthy",
                capability_tiers=frozenset({"T2"}),
                task_classes=frozenset({"coder"}),
                max_risk="low",
                project_cost_usd=0,
                capacity_available=True,
                provider_family="family-a",
            ),
            ConnectorProfile(
                connection_id="different-family",
                kind="agent",
                driver="fake",
                health="healthy",
                capability_tiers=frozenset({"T2"}),
                task_classes=frozenset({"coder"}),
                max_risk="low",
                project_cost_usd=0,
                capacity_available=True,
                provider_family="family-b",
            ),
        ]

        result = resolve_routes(decision, profiles, auto_select=True)

        self.assertEqual(
            result.selected_connection_id,
            "different-family",
        )


if __name__ == "__main__":
    unittest.main()
