"""Synthetic dependency/economic planning conformance; no live performance claim."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from idkmesh.connector_routing import ConnectorProfile, RoutingDecision
from idkmesh.coordination_preflight import (
    CoordinationPreflightError, DependencyGraph, DependencyProjection, EffortEstimate,
    PrerequisiteObservation, coordination_preflight, critical_path_ranks, effort_capability,
)
from idkmesh.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "examples/work-units/composability/coding.work-unit.json").read_text())
SCOPE = TenantScope("tenant-a", "project-a")
REVISION = "a" * 40


def _unit(node, requires=(), extra=()):
    unit = deepcopy(BASE)
    unit["id"] = node
    unit["provenance"]["source_revision"] = REVISION
    unit["dependencies"] = [{"work_unit_id": target, "relationship": "requires"} for target in requires] + list(extra)
    return unit


def _graph(units):
    return DependencyGraph(SCOPE, units, source_revisions={unit["id"]: REVISION for unit in units})


def _estimate(**kwargs):
    defaults = dict(components=1, ambiguity="low", coupling="low", execution_seconds=30,
                    verification_minutes=2, integration_minutes=1, estimate_source="synthetic declaration")
    return EffortEstimate(**{**defaults, **kwargs})


def _connector(name="small", tier="T1", **kwargs):
    defaults = dict(connection_id=name, kind="agent", driver="offline-fixture", capability_tiers={tier}, max_risk="critical")
    return ConnectorProfile(**{**defaults, **kwargs})


def _observation(projection, node="task-a", *, sequence=1, state="integrated", **kwargs):
    defaults = dict(scope=SCOPE, event_id=f"event-{node}-{sequence}", sequence=sequence,
                    binding=projection.graph.bindings[node], state=state,
                    inputs_digest=projection.readiness()[node].inputs_digest or "sha256:" + "0" * 64)
    if state == "integrated":
        defaults.update(integrated_revision="b" * 40, artifacts_digest="sha256:" + "c" * 64,
                        verification_reference="fixture:independent-evidence", integration_reference="fixture:human-decision")
    return PrerequisiteObservation(**{**defaults, **kwargs})


class CoordinationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.units = [_unit("task-a"), _unit("task-b", ("task-a",)), _unit("task-c", ("task-a",)),
                      _unit("task-d", ("task-b", "task-c")), _unit("task-z")]
        self.graph = _graph(self.units)
        self.projection = DependencyProjection(self.graph)
        self.decision = RoutingDecision("T1", "agent_candidate")

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(CoordinationPreflightError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_diamond_fan_in_requires_both_current_integrated_prerequisites(self):
        initial = self.projection.readiness()
        self.assertEqual({node for node, state in initial.items() if state.ready}, {"task-a", "task-z"})
        self.projection.observe(_observation(self.projection))
        self.assertTrue(self.projection.readiness()["task-b"].ready)
        self.projection.observe(_observation(self.projection, "task-b"))
        self.assertFalse(self.projection.readiness()["task-d"].ready)
        self.projection.observe(_observation(self.projection, "task-c"))
        self.assertTrue(self.projection.readiness()["task-d"].ready)

    def test_cycle_missing_target_duplicate_edge_and_free_text_condition_fail_closed(self):
        self.assert_code("dependency_cycle", _graph, [_unit("task-a", ("task-b",)), _unit("task-b", ("task-a",))])
        self.assert_code("missing_prerequisite", _graph, [_unit("task-a", ("missing",))])
        self.assert_code("duplicate_dependency", _graph, [_unit("task-a"), _unit("task-b", ("task-a", "task-a"))])
        unit = _unit("task-a")
        unit["dependencies"] = [{"work_unit_id": "task-a", "relationship": "requires", "condition": "issue closed"}]
        self.assert_code("unsupported_condition", _graph, [unit])

    def test_only_requires_is_executable_and_other_relationships_may_reference_external_nodes(self):
        unit = _unit("task-a", extra=[{"work_unit_id": "external", "relationship": relation}
                                     for relation in ("blocks", "informs", "validates", "derived_from")])
        graph = _graph([unit])
        self.assertEqual(graph.requires["task-a"], ())
        self.assertTrue(DependencyProjection(graph).readiness()["task-a"].ready)

    def test_long_dag_has_iterative_cycle_detection_and_readiness(self):
        units = [_unit(f"task-{index}", (f"task-{index - 1}",) if index else ()) for index in range(1500)]
        graph = _graph(units)
        states = DependencyProjection(graph).readiness()
        self.assertEqual(len(graph.topological_order), 1500)
        self.assertTrue(states["task-0"].ready)
        self.assertFalse(states["task-1499"].ready)

    def test_full_work_unit_and_source_binding_are_frozen_against_caller_mutation(self):
        digest = self.graph.digest
        self.units[0]["objective"] = "changed after freezing"
        self.assertEqual(self.graph.digest, digest)
        self.assertNotEqual(_graph(self.units).digest, digest)
        unit = _unit("task-a")
        self.assert_code("source_binding_invalid", DependencyGraph, SCOPE, [unit], source_revisions={"task-a": "d" * 40})

    def test_replay_is_idempotent_and_reconstruction_restores_the_same_ready_snapshot(self):
        events = []
        for node in ("task-a", "task-b", "task-c"):
            event = _observation(self.projection, node)
            events.append(event)
            self.assertTrue(self.projection.observe(event))
            before = self.projection.readiness()
            self.assertFalse(self.projection.observe(event))
            self.assertEqual(self.projection.readiness(), before)
        restored = DependencyProjection(self.graph)
        for event in events + events:
            restored.observe(event)
        self.assertEqual(restored.readiness(), self.projection.readiness())
        self.assertEqual(restored.observation_digest, self.projection.observation_digest)

    def test_conflicting_event_or_sequence_cannot_rewrite_observed_state(self):
        event = _observation(self.projection)
        self.projection.observe(event)
        before = self.projection.observation_digest
        self.assert_code("event_conflict", self.projection.observe, replace(event, state="rejected"))
        self.assert_code("sequence_conflict", self.projection.observe, replace(event, event_id="other-delivery"))
        self.assertEqual(before, self.projection.observation_digest)

    def test_out_of_order_integrated_event_cannot_resurrect_rejected_prerequisite(self):
        old = _observation(self.projection)
        self.projection.observe(_observation(self.projection, sequence=2, state="rejected"))
        before = self.projection.observation_digest
        self.assertFalse(self.projection.observe(old))
        self.assertEqual(before, self.projection.observation_digest)
        self.assertFalse(self.projection.readiness()["task-b"].ready)

    def test_candidate_completion_and_missing_evidence_do_not_satisfy_dependencies(self):
        self.projection.observe(_observation(self.projection, state="candidate"))
        self.assertFalse(self.projection.readiness()["task-b"].ready)
        self.assert_code("integration_evidence_required", _observation, self.projection, integration_reference=None)
        self.assert_code("invalid_input", _observation, self.projection, state="done")

    def test_scope_and_exact_work_unit_digest_are_non_compensating(self):
        event = _observation(self.projection)
        self.assert_code("scope_mismatch", self.projection.observe,
                         replace(event, scope=TenantScope("tenant-b", "project-a")))
        wrong = replace(event.binding, work_unit_digest="sha256:" + "f" * 64)
        self.projection.observe(replace(event, binding=wrong))
        self.assertIn("prerequisite_binding_changed:task-a", self.projection.readiness()["task-b"].blockers)

    def test_upstream_artifact_change_invalidates_transitive_old_inputs_only(self):
        for node in ("task-a", "task-b", "task-c"):
            self.projection.observe(_observation(self.projection, node))
        before = self.projection.readiness()
        self.assertTrue(before["task-d"].ready)
        self.projection.observe(_observation(self.projection, sequence=2, artifacts_digest="sha256:" + "d" * 64))
        after = self.projection.readiness()
        self.assertNotEqual(before["task-b"].inputs_digest, after["task-b"].inputs_digest)
        self.assertFalse(after["task-b"].satisfied)
        self.assertFalse(after["task-d"].ready)
        self.assertEqual(before["task-z"], after["task-z"])
        for node in ("task-b", "task-c"):
            self.projection.observe(_observation(self.projection, node, sequence=2))
        self.assertTrue(self.projection.readiness()["task-d"].ready)

    def test_unrelated_graph_change_does_not_rebind_other_task_inputs(self):
        before = self.projection.readiness()["task-a"].inputs_digest
        changed = deepcopy(self.units)
        changed[-1]["objective"] = "a different unrelated task"
        graph = _graph(changed)
        self.assertNotEqual(graph.digest, self.graph.digest)
        self.assertEqual(DependencyProjection(graph).readiness()["task-a"].inputs_digest, before)

    def test_local_replay_budget_is_bounded_without_partial_new_state(self):
        projection = DependencyProjection(self.graph, max_events=1)
        projection.observe(_observation(projection))
        self.assert_code("event_budget_exhausted", projection.observe, _observation(projection, sequence=2, state="rejected"))
        self.assertTrue(projection.readiness()["task-b"].ready)

    def test_capability_recommendations_separate_scope_ambiguity_coupling_and_risk(self):
        cases = [({}, "low", "T1"), ({"components": 4}, "low", "T2"),
                 ({"coupling": "high"}, "low", "T3"), ({"ambiguity": "high"}, "low", "T4"),
                 ({}, "high", "T3"), ({}, "critical", "T4")]
        for kwargs, risk, expected in cases:
            with self.subTest(kwargs=kwargs, risk=risk):
                tier, _ = effort_capability(_estimate(**kwargs), replace(self.decision, risk_class=risk))
                self.assertEqual(tier, expected)
        tier, reasons = effort_capability(_estimate(), replace(self.decision, required_capability_tier="T4"))
        self.assertEqual(tier, "T4")
        self.assertIn("trusted_capability_floor_preserved", reasons)

    def test_smallest_eligible_lane_is_recommended_and_larger_lane_handles_complex_work(self):
        connectors = [_connector("strong", "T3"), _connector("small", "T1")]
        simple = coordination_preflight(self.projection, "task-a", _estimate(), self.decision, connectors)
        complex_task = coordination_preflight(self.projection, "task-a", _estimate(coupling="high"), self.decision, connectors)
        self.assertEqual(simple["routing"]["recommended_connection_id"], "small")
        self.assertEqual(complex_task["routing"]["recommended_connection_id"], "strong")

    def test_unknown_effort_or_unsatisfied_prerequisite_queues_without_a_model_guess(self):
        unknown = coordination_preflight(self.projection, "task-a", _estimate(ambiguity="unknown"), self.decision, [_connector()])
        blocked = coordination_preflight(self.projection, "task-b", _estimate(), self.decision, [_connector()])
        self.assertIsNone(unknown["routing"]["recommended_connection_id"])
        self.assertIsNone(unknown["capability"]["recommended_tier"])
        self.assertIn("effort_requirements_unknown", unknown["blockers"])
        self.assertIsNone(blocked["routing"]["recommended_connection_id"])
        self.assertFalse(blocked["ready"])

    def test_t0_uses_a_tool_and_cannot_silently_upgrade_deterministic_authority_to_llm(self):
        decision = RoutingDecision("T0", "deterministic", allowed_connector_kinds={"execution", "agent"})
        connectors = [_connector("llm", "T4"), _connector("tool", "T0", kind="execution")]
        report = coordination_preflight(self.projection, "task-a", _estimate(deterministic_operation=True), decision, connectors)
        self.assertEqual(report["routing"]["recommended_connection_id"], "tool")
        invalid = coordination_preflight(self.projection, "task-a", _estimate(coupling="high"), decision, connectors)
        self.assertIn("deterministic_context_conflict", invalid["blockers"])
        self.assertIsNone(invalid["routing"]["recommended_connection_id"])

    def test_human_gate_risk_tools_processing_secrets_and_capacity_remain_hard_gates(self):
        cases = [({"authority_mode": "human_required"}, {}, "human_required"),
                 ({"authority_mode": "human_gate_then_agent"}, {}, "human_gate_pending"),
                 ({"required_tools": {"git"}}, {}, "required_tool_missing:git"),
                 ({"risk_class": "high"}, {"max_risk": "low"}, "risk_not_allowed"),
                 ({"external_processing_allowed": False}, {"external_processing": True}, "external_processing_forbidden"),
                 ({}, {"secret_required": True, "secret_available": False}, "secret_unavailable"),
                 ({}, {"capacity_available": False}, "capacity_unavailable")]
        for decision_kwargs, connector_kwargs, reason in cases:
            with self.subTest(reason=reason):
                report = coordination_preflight(self.projection, "task-a", _estimate(),
                                                replace(self.decision, **decision_kwargs), [_connector(tier="T4", **connector_kwargs)])
                self.assertIsNone(report["routing"]["recommended_connection_id"])
                self.assertIn(reason, report["routing"]["ineligible"][0]["reasons"])

    def test_no_paid_fallback_even_when_task_template_allows_spending(self):
        report = coordination_preflight(self.projection, "task-a", _estimate(),
                                        replace(self.decision, project_spend_usd_max=100), [_connector(project_cost_usd=0.01)])
        self.assertEqual(report["routing"]["project_spend_usd_max"], 0)
        self.assertIsNone(report["routing"]["recommended_connection_id"])
        self.assertIn("project_spend_exceeded", report["routing"]["ineligible"][0]["reasons"])

    def test_work_unit_risk_floor_cannot_be_lowered_by_a_routing_template(self):
        unit = _unit("task-a")
        unit["security"]["risk_class"] = "high"
        projection = DependencyProjection(_graph([unit]))
        report = coordination_preflight(projection, "task-a", _estimate(), self.decision, [_connector(tier="T4", max_risk="low")])
        self.assertEqual(report["routing"]["risk_class"], "high")
        self.assertEqual(report["capability"]["recommended_tier"], "T3")
        self.assertIsNone(report["routing"]["recommended_connection_id"])

    def test_already_integrated_task_is_not_recommended_for_another_attempt(self):
        self.projection.observe(_observation(self.projection))
        report = coordination_preflight(self.projection, "task-a", _estimate(), self.decision, [_connector()])
        self.assertTrue(report["satisfied"])
        self.assertIn("task_already_integrated", report["blockers"])
        self.assertIsNone(report["routing"]["recommended_connection_id"])

    def test_critical_path_uses_consistent_seconds_and_includes_review_integration(self):
        estimates = {node: _estimate(execution_seconds=10, verification_minutes=1, integration_minutes=0) for node in self.graph.bindings}
        ranks = critical_path_ranks(self.graph, estimates)
        self.assertEqual(ranks["task-d"], 70)
        self.assertEqual(ranks["task-a"], 210)
        self.assertEqual(ranks["task-z"], 70)
        self.assert_code("duration_unknown", critical_path_ranks, self.graph,
                         {**estimates, "task-d": _estimate(execution_seconds=None)})

    def test_invalid_estimates_do_not_produce_numerical_precision(self):
        for kwargs in ({"execution_seconds": float("nan")}, {"verification_minutes": -1},
                       {"components": True}, {"integration_minutes": float("inf")}):
            self.assert_code("invalid_input", _estimate, **kwargs)

    def test_readonly_report_conforms_to_versioned_schema_and_preserves_authority_ceiling(self):
        schema = json.loads((ROOT / "schemas/coordination-preflight-v0.1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for node in ("task-a", "task-b"):
            report = coordination_preflight(self.projection, node, _estimate(), self.decision, [_connector()])
            validator.validate(report)
            self.assertTrue(all(value is False for value in report["authority"].values()))
        self.projection.observe(_observation(self.projection))
        validator.validate(coordination_preflight(self.projection, "task-b", _estimate(), self.decision, [_connector()]))


class CoordinationPreflightHardeningTests(unittest.TestCase):
    """Regression tests for review findings: each fails against the code before its fix."""

    def setUp(self):
        self.units = [_unit("task-a"), _unit("task-b", ("task-a",)), _unit("task-c", ("task-a",)),
                      _unit("task-d", ("task-b", "task-c")), _unit("task-z")]
        self.projection = DependencyProjection(_graph(self.units))

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(CoordinationPreflightError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_a_different_event_at_an_older_sequence_is_a_conflict_not_silently_ignored(self):
        first = _observation(self.projection, sequence=1)
        newer = _observation(self.projection, sequence=2, state="rejected")
        self.assertTrue(self.projection.observe(first))
        self.assertTrue(self.projection.observe(newer))
        before = self.projection.observation_digest

        self.assert_code("sequence_conflict", self.projection.observe,
                         replace(first, event_id="other-delivery"))

        self.assertEqual(before, self.projection.observation_digest)
        # Exact replay of the genuine old event stays a harmless no-op.
        self.assertFalse(self.projection.observe(first))

    def test_a_rejected_conflicting_event_does_not_consume_the_replay_budget(self):
        projection = DependencyProjection(_graph(self.units), max_events=2)
        first = _observation(projection, sequence=1)
        projection.observe(first)
        projection.observe(_observation(projection, sequence=2, state="rejected"))
        self.assert_code("sequence_conflict", projection.observe, replace(first, event_id="other"))
        # The budget is still exactly full, so a third distinct event still hits it.
        self.assert_code("event_budget_exhausted", projection.observe,
                         _observation(projection, sequence=3, state="rejected"))

    def test_ready_order_does_not_depend_on_the_order_units_are_supplied(self):
        forward = _graph(self.units).topological_order
        backward = _graph(list(reversed(self.units))).topological_order
        shuffled = _graph([self.units[3], self.units[0], self.units[4], self.units[2], self.units[1]]).topological_order
        self.assertEqual(forward, backward)
        self.assertEqual(forward, shuffled)

    def test_duplicate_work_unit_and_self_dependency_fail_closed(self):
        self.assert_code("duplicate_work_unit", _graph, [_unit("same"), _unit("same")])
        self.assert_code("dependency_cycle", _graph, [_unit("loop", ("loop",))])

    def test_malformed_work_units_raise_the_stable_error_not_a_raw_exception(self):
        bad_security = _unit("bad-security")
        bad_security["security"] = "restricted"
        non_finite = _unit("non-finite")
        non_finite["notes"] = float("nan")
        not_json = _unit("not-json")
        not_json["notes"] = object()
        self.assert_code("invalid_work_unit_security", _graph, [bad_security])
        self.assert_code("invalid_input", _graph, [non_finite])
        self.assert_code("invalid_input", _graph, [not_json])

    def test_demo_reports_are_schema_valid(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "preflight_demo", ROOT / "examples/coordination/preflight_demo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document = module.demo()

        schema = json.loads((ROOT / "schemas/coordination-preflight-v0.1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        self.assertEqual(document["evidence_class"], "synthetic_fixture")
        for name in ("blocked", "ready_small", "ready_strong"):
            with self.subTest(report=name):
                self.assertEqual(list(validator.iter_errors(document[name])), [])
