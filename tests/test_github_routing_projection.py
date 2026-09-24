import unittest

from idkmesh.connector_routing import (
    ConnectorProfile,
    RouteResolution,
    RoutingDecision,
    EligibleConnector,
    resolve_routes,
)
from idkmesh.github_routing_projection import (
    MANAGED_LABEL_PREFIX,
    project_routing_to_github,
    replace_managed_routing_labels,
)


def _decision(**overrides):
    values = {
        "required_capability_tier": "T2",
        "authority_mode": "agent_candidate",
        "risk_class": "low",
        "task_classes": frozenset({"coding"}),
        "required_tools": frozenset({"git"}),
        "allowed_connector_kinds": frozenset({"agent"}),
        "external_processing_allowed": False,
        "project_spend_usd_max": 0,
        "prefer_zero_cost": True,
        "independent_reviewer_required": True,
    }
    values.update(overrides)
    return RoutingDecision(**values)


def _connector(connection_id, **overrides):
    values = {
        "connection_id": connection_id,
        "kind": "agent",
        "driver": "fixture",
        "capability_tiers": frozenset({"T2"}),
        "task_classes": frozenset({"coding"}),
        "tools": frozenset({"git"}),
        "max_risk": "low",
        "external_processing": False,
        "project_cost_usd": 0,
    }
    values.update(overrides)
    return ConnectorProfile(**values)


class GitHubRoutingProjectionTests(unittest.TestCase):
    def test_selected_route_projects_canonical_managed_labels(self):
        decision = _decision()
        resolution = resolve_routes(
            decision,
            [_connector("agent-b"), _connector("agent-a")],
        )
        projection = project_routing_to_github(
            decision,
            resolution,
        )

        self.assertEqual(projection.route_state, "selected")
        self.assertEqual(
            projection.selected_connection_id,
            "agent-a",
        )
        self.assertTrue(
            projection.routing_digest.startswith("sha256:")
        )
        self.assertIn(
            "idkmesh:tier:T2",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:authority:agent-candidate",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:risk:low",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:route:selected",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:processing:local-only",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:review:independent-required",
            projection.managed_labels,
        )
        self.assertFalse(
            projection.to_dict()["github_mutation_performed"]
        )

    def test_blocked_route_is_projected_without_inventing_selection(self):
        decision = _decision(risk_class="high")
        resolution = resolve_routes(
            decision,
            [_connector("low-risk-only")],
        )
        projection = project_routing_to_github(
            decision,
            resolution,
        )

        self.assertEqual(projection.route_state, "blocked")
        self.assertIsNone(projection.selected_connection_id)
        self.assertEqual(projection.eligible_connection_ids, ())
        self.assertIn(
            "idkmesh:route:blocked",
            projection.managed_labels,
        )
        self.assertIn(
            "risk_not_allowed",
            projection.ineligible[0][1],
        )

    def test_manual_resolution_with_eligible_connectors_is_not_selected(self):
        decision = _decision()
        resolution = resolve_routes(
            decision,
            [_connector("agent-a")],
            auto_select=False,
        )
        projection = project_routing_to_github(
            decision,
            resolution,
        )
        self.assertEqual(projection.route_state, "eligible")
        self.assertIsNone(projection.selected_connection_id)
        self.assertIn(
            "idkmesh:route:eligible",
            projection.managed_labels,
        )

    def test_human_required_authority_remains_blocked(self):
        decision = _decision(
            required_capability_tier="T2",
            authority_mode="human_required",
        )
        resolution = resolve_routes(
            decision,
            [_connector("agent-a")],
        )
        projection = project_routing_to_github(
            decision,
            resolution,
        )
        self.assertEqual(projection.route_state, "blocked")
        self.assertIn(
            "idkmesh:authority:human-required",
            projection.managed_labels,
        )
        self.assertIn(
            "human_required",
            projection.ineligible[0][1],
        )

    def test_existing_human_labels_are_preserved_and_stale_managed_removed(self):
        projection = project_routing_to_github(
            _decision(),
            resolve_routes(
                _decision(),
                [_connector("agent-a")],
            ),
        )
        merged = replace_managed_routing_labels(
            (
                "bug",
                "agent-ready",
                "IDKMESH:route:blocked",
                "idkmesh:tier:T4",
                "Bug",
            ),
            projection,
        )
        self.assertEqual(merged[0:2], ("bug", "agent-ready"))
        self.assertEqual(
            sum(
                label.casefold() == "bug"
                for label in merged
            ),
            1,
        )
        self.assertNotIn("IDKMESH:route:blocked", merged)
        self.assertNotIn("idkmesh:tier:T4", merged)
        self.assertIn("idkmesh:route:selected", merged)
        self.assertIn("idkmesh:tier:T2", merged)

    def test_human_labels_cannot_change_routing_digest(self):
        decision = _decision()
        resolution = resolve_routes(
            decision,
            [_connector("agent-a")],
        )
        projection = project_routing_to_github(
            decision,
            resolution,
        )
        first = replace_managed_routing_labels(
            ("bug",),
            projection,
        )
        second = replace_managed_routing_labels(
            ("feature", "priority-high"),
            projection,
        )
        self.assertNotEqual(first, second)
        self.assertEqual(
            projection.routing_digest,
            project_routing_to_github(
                decision,
                resolution,
            ).routing_digest,
        )

    def test_external_processing_and_review_flags_are_projected(self):
        decision = _decision(
            external_processing_allowed=True,
            independent_reviewer_required=False,
        )
        projection = project_routing_to_github(
            decision,
            resolve_routes(
                decision,
                [
                    _connector(
                        "external-agent",
                        external_processing=True,
                    )
                ],
            ),
        )
        self.assertIn(
            "idkmesh:processing:external-ok",
            projection.managed_labels,
        )
        self.assertIn(
            "idkmesh:review:standard",
            projection.managed_labels,
        )

    def test_projection_rejects_inconsistent_selected_connector(self):
        bad = RouteResolution(
            eligible=(
                EligibleConnector(
                    connection_id="agent-a",
                    supported_tier="T2",
                    selection_key=(0, 0, 0, 0, 0, 0.0, "agent-a"),
                ),
            ),
            ineligible=(),
            selected_connection_id="agent-b",
            selection_reason=("invalid",),
        )
        with self.assertRaisesRegex(ValueError, "eligible"):
            project_routing_to_github(
                _decision(),
                bad,
            )

    def test_managed_labels_are_github_bounded_and_namespaced(self):
        projection = project_routing_to_github(
            _decision(),
            resolve_routes(
                _decision(),
                [_connector("agent-a")],
            ),
        )
        for label in projection.managed_labels:
            self.assertTrue(
                label.casefold().startswith(MANAGED_LABEL_PREFIX)
            )
            self.assertLessEqual(len(label), 50)

    def test_existing_label_input_must_be_structured(self):
        projection = project_routing_to_github(
            _decision(),
            resolve_routes(
                _decision(),
                [_connector("agent-a")],
            ),
        )
        with self.assertRaisesRegex(ValueError, "iterable"):
            replace_managed_routing_labels(
                "bug",
                projection,
            )
        with self.assertRaisesRegex(ValueError, "non-empty"):
            replace_managed_routing_labels(
                ("bug", ""),
                projection,
            )


if __name__ == "__main__":
    unittest.main()
