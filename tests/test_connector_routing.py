import unittest

from idkmesh.connector_routing import (
    ConnectorProfile,
    RoutingDecision,
    resolve_routes,
)


def _agent(
    connection_id,
    *,
    tiers=("T1",),
    task_classes=("coder",),
    tools=("git", "pytest"),
    max_risk="low",
    external_processing=False,
    project_cost_usd=0.0,
    enabled=True,
    health="healthy",
    secret_required=False,
    secret_available=True,
    capacity_available=True,
    provider_family="",
):
    return ConnectorProfile(
        connection_id=connection_id,
        kind="agent",
        driver="fake",
        enabled=enabled,
        health=health,
        capability_tiers=frozenset(tiers),
        task_classes=frozenset(task_classes),
        tools=frozenset(tools),
        max_risk=max_risk,
        external_processing=external_processing,
        project_cost_usd=project_cost_usd,
        secret_required=secret_required,
        secret_available=secret_available,
        capacity_available=capacity_available,
        provider_family=provider_family,
    )


class ConnectorRoutingTests(unittest.TestCase):
    def test_small_free_connector_beats_overpowered_paid_connector(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            required_tools=frozenset({"git", "pytest"}),
            project_spend_usd_max=5,
        )
        result = resolve_routes(
            decision,
            [
                _agent("strong-paid", tiers=("T3", "T4"), project_cost_usd=1.0),
                _agent("small-free", tiers=("T1",), project_cost_usd=0.0),
            ],
        )
        self.assertEqual(result.selected_connection_id, "small-free")
        self.assertEqual(
            [item.connection_id for item in result.eligible],
            ["small-free", "strong-paid"],
        )

    def test_t4_task_rejects_t2_connector(self):
        decision = RoutingDecision(
            required_capability_tier="T4",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            risk_class="high",
        )
        result = resolve_routes(
            decision,
            [
                _agent("standard", tiers=("T1", "T2"), max_risk="high"),
                _agent("peak", tiers=("T4",), max_risk="high"),
            ],
        )
        self.assertEqual(result.selected_connection_id, "peak")
        rejected = {item.connection_id: item.reasons for item in result.ineligible}
        self.assertIn("insufficient_capability_tier", rejected["standard"])

    def test_human_required_blocks_even_peak_connector(self):
        decision = RoutingDecision(
            required_capability_tier="T4",
            authority_mode="human_required",
            task_classes=frozenset({"coder"}),
            risk_class="high",
        )
        result = resolve_routes(
            decision,
            [_agent("peak", tiers=("T4",), max_risk="high")],
        )
        self.assertIsNone(result.selected_connection_id)
        self.assertEqual(result.eligible, ())
        self.assertIn("human_required", result.ineligible[0].reasons)

    def test_pending_human_gate_blocks_dispatch(self):
        decision = RoutingDecision(
            required_capability_tier="T3",
            authority_mode="human_gate_then_agent",
            human_gate_satisfied=False,
            task_classes=frozenset({"coder"}),
            risk_class="medium",
        )
        result = resolve_routes(
            decision,
            [_agent("strong", tiers=("T3",), max_risk="medium")],
        )
        self.assertIsNone(result.selected_connection_id)
        self.assertIn("human_gate_pending", result.ineligible[0].reasons)

    def test_external_processing_policy_prefers_local_when_external_forbidden(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            external_processing_allowed=False,
        )
        result = resolve_routes(
            decision,
            [
                _agent("hosted", external_processing=True),
                _agent("local", external_processing=False),
            ],
        )
        self.assertEqual(result.selected_connection_id, "local")
        rejected = {item.connection_id: item.reasons for item in result.ineligible}
        self.assertIn("external_processing_forbidden", rejected["hosted"])

    def test_project_spend_ceiling_is_non_compensating(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            project_spend_usd_max=0,
        )
        result = resolve_routes(
            decision,
            [
                _agent("paid", project_cost_usd=0.01),
                _agent("free", project_cost_usd=0),
            ],
        )
        self.assertEqual(result.selected_connection_id, "free")
        rejected = {item.connection_id: item.reasons for item in result.ineligible}
        self.assertIn("project_spend_exceeded", rejected["paid"])

    def test_task_tool_and_risk_rejections_are_explicit_and_stable(self):
        decision = RoutingDecision(
            required_capability_tier="T2",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder", "tooling"}),
            required_tools=frozenset({"git", "pytest", "docker"}),
            risk_class="medium",
        )
        result = resolve_routes(
            decision,
            [
                _agent(
                    "limited",
                    tiers=("T2",),
                    task_classes=("coder",),
                    tools=("git", "pytest"),
                    max_risk="low",
                )
            ],
        )
        self.assertEqual(
            result.ineligible[0].reasons,
            (
                "task_class_unsupported:tooling",
                "required_tool_missing:docker",
                "risk_not_allowed",
            ),
        )

    def test_secret_capacity_and_disabled_state_fail_closed(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
        )
        result = resolve_routes(
            decision,
            [
                _agent("disabled", enabled=False),
                _agent(
                    "missing-secret",
                    secret_required=True,
                    secret_available=False,
                ),
                _agent("full", capacity_available=False),
            ],
        )
        rejected = {item.connection_id: item.reasons for item in result.ineligible}
        self.assertIn("connector_disabled", rejected["disabled"])
        self.assertIn("secret_unavailable", rejected["missing-secret"])
        self.assertIn("capacity_unavailable", rejected["full"])
        self.assertIsNone(result.selected_connection_id)

    def test_tie_break_is_stable_by_connection_id(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
        )
        result = resolve_routes(
            decision,
            [_agent("zeta"), _agent("alpha")],
        )
        self.assertEqual(result.selected_connection_id, "alpha")
        self.assertEqual(
            [item.connection_id for item in result.eligible],
            ["alpha", "zeta"],
        )

    def test_avoided_provider_family_loses_same_tier_tie(self):
        decision = RoutingDecision(
            required_capability_tier="T2",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
            avoid_provider_families=frozenset({"family-a"}),
        )
        result = resolve_routes(
            decision,
            [
                _agent("a", tiers=("T2",), provider_family="family-a"),
                _agent("b", tiers=("T2",), provider_family="family-b"),
            ],
        )
        self.assertEqual(result.selected_connection_id, "b")

    def test_auto_select_false_returns_ranked_eligibility_without_dispatch_choice(self):
        decision = RoutingDecision(
            required_capability_tier="T1",
            authority_mode="agent_candidate",
            task_classes=frozenset({"coder"}),
        )
        result = resolve_routes(
            decision,
            [_agent("small")],
            auto_select=False,
        )
        self.assertEqual([item.connection_id for item in result.eligible], ["small"])
        self.assertIsNone(result.selected_connection_id)
        self.assertEqual(result.selection_reason, ())


if __name__ == "__main__":
    unittest.main()
