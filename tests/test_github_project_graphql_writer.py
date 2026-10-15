"""C13-G: the GraphQL Project field writer is offline, fail-closed and secret-free.

Every test drives a recording fake transport; nothing here can reach a network.
"""

import copy
import json
import unittest

from idkmesh.github_project_sync import (
    FIELD_DATA_TYPES,
    SCHEMA_SNAPSHOT_KIND,
    UPDATE_FIELD_VALUE_MUTATION,
    GraphQLProjectFieldWriter,
    ProjectGraphQLError,
    ProjectPermissionError,
    ProjectSchemaError,
    apply_github_project_plan,
    plan_github_project_run_fields,
)
from idkmesh.github_run_label_projection import _RUN_LABEL_STATES

DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
IDS = {"state": "F_state", "verification": "F_verify", "human_decision": "F_human"}
ITEM = "PVTI_item1"
PROJECT = "PVT_proj1"
SECRET = "ghp_SECRETTOKEN0123456789"


def _options(index):
    values = sorted({row[index] for row in _RUN_LABEL_STATES.values()})
    return [{"value": v, "option_id": f"O{index}_{n}"} for n, v in enumerate(values)]


def _snapshot():
    return {
        "schema_version": "0.1",
        "kind": SCHEMA_SNAPSHOT_KIND,
        "project_id": PROJECT,
        "fields": [
            {"field_id": "F_state", "data_type": "single_select", "options": _options(0)},
            {"field_id": "F_verify", "data_type": "single_select", "options": _options(1)},
            {"field_id": "F_human", "data_type": "single_select", "options": _options(2)},
            {"field_id": "F_note", "data_type": "text", "options": []},
            {"field_id": "F_count", "data_type": "number", "options": []},
            {"field_id": "F_due", "data_type": "date", "options": []},
        ],
    }


def _option_id(field, value):
    for entry in _snapshot()["fields"]:
        if entry["field_id"] == field:
            return next(o["option_id"] for o in entry["options"] if o["value"] == value)
    raise AssertionError(field)


class Recorder:
    """Fake transport that records calls and models a tiny Project."""

    def __init__(self, response=None, raises=None):
        self.calls = []
        self.response = response
        self.raises = raises

    def __call__(self, query, variables):
        self.calls.append((query, copy.deepcopy(variables)))
        if self.raises is not None:
            raise self.raises
        if self.response is not None:
            return self.response
        return {"data": {"updateProjectV2ItemFieldValue": {
            "projectV2Item": {"id": variables["itemId"]}}}}


def _run_plan(observed=None):
    return plan_github_project_run_fields(
        run_id="run/example-1", run_state="candidate_observed",
        canonical_source_digest=DIGEST, field_ids=IDS, observed_fields=observed or {},
    )


def _manual_plan(updates, digest=DIGEST):
    entries = [{"field_id": f, "value": v} for f, v in updates]
    return {
        "schema_version": "0.1", "kind": "idkmesh-project-run-sync-plan",
        "run_id": "run/example-1", "run_state": "candidate_observed",
        "canonical_source_digest": digest, "desired_fields": entries,
        "updates": entries, "noop": not entries,
        "project_mutation_performed": False, "execution_authority": False,
        "human_decision_authority": False, "integration_authority": False,
    }


def _apply(plan, writer, digest=lambda: DIGEST):
    return apply_github_project_plan(
        plan, item_id=ITEM, trusted_item_ids={ITEM}, writer=writer,
        read_canonical_digest=digest,
    )


class MutationShapeTests(unittest.TestCase):
    def test_query_is_a_fixed_constant_and_values_are_variables(self):
        transport = Recorder()
        writer = GraphQLProjectFieldWriter(transport, _snapshot())
        writer.update_field(ITEM, "F_note", "hello-world")
        query, variables = transport.calls[0]
        self.assertIs(query, UPDATE_FIELD_VALUE_MUTATION)
        for needle in (ITEM, PROJECT, "F_note", "hello-world"):
            self.assertNotIn(needle, query)
        self.assertIn("updateProjectV2ItemFieldValue", query)
        self.assertEqual(set(FIELD_DATA_TYPES), {"single_select", "text", "number", "date"})

    def test_exact_variables_for_each_field_type(self):
        cases = [
            ("F_state", "candidate-observed",
             {"singleSelectOptionId": _option_id("F_state", "candidate-observed")}),
            ("F_note", "hello-world", {"text": "hello-world"}),
            ("F_count", "42", {"number": 42.0}),
            ("F_due", "2026-10-15", {"date": "2026-10-15"}),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                transport = Recorder()
                GraphQLProjectFieldWriter(transport, _snapshot()).update_field(ITEM, field, value)
                self.assertEqual(
                    transport.calls[0][1],
                    {"projectId": PROJECT, "itemId": ITEM, "fieldId": field, "value": expected},
                )

    def test_plan_applies_through_the_real_applier_with_exact_calls(self):
        transport = Recorder()
        result = _apply(_run_plan(), GraphQLProjectFieldWriter(transport, _snapshot()))
        self.assertEqual(result.status, "applied")
        sent = {c[1]["fieldId"]: c[1]["value"] for c in transport.calls}
        self.assertEqual(sent, {
            "F_state": {"singleSelectOptionId": _option_id("F_state", "candidate-observed")},
            "F_verify": {"singleSelectOptionId": _option_id("F_verify", "not-started")},
            "F_human": {"singleSelectOptionId": _option_id("F_human", "unrecorded")},
        })
        self.assertTrue(all(c[0] is UPDATE_FIELD_VALUE_MUTATION for c in transport.calls))


class FailClosedTests(unittest.TestCase):
    def test_unknown_option_aborts_with_zero_writes_and_no_digest_read(self):
        snapshot = _snapshot()
        snapshot["fields"][2]["options"] = snapshot["fields"][2]["options"][:1]
        transport = Recorder()

        def boom():
            raise AssertionError("must not read before preflight")

        plan = _manual_plan([("F_state", "candidate-observed"), ("F_human", "recorded")])
        result = _apply(plan, GraphQLProjectFieldWriter(transport, snapshot), digest=boom)
        self.assertEqual(result.status, "failed")
        self.assertIn("ProjectSchemaError", result.detail)
        self.assertEqual(transport.calls, [])

    def test_unknown_field_and_bad_typed_values_fail_closed(self):
        writer = GraphQLProjectFieldWriter(Recorder(), _snapshot())
        for field, value in [("F_missing", "x"), ("F_state", "no-such-option"),
                             ("F_count", "abc"), ("F_count", "1-2"),
                             ("F_due", "2026-13-40"), ("F_due", "tomorrow"),
                             ("F_note", "Has Caps")]:
            with self.subTest(field=field, value=value), self.assertRaises(ProjectSchemaError):
                writer.update_field(ITEM, field, value)
        with self.assertRaises(ProjectSchemaError):
            writer.update_field("bad item!", "F_note", "x")

    def test_stale_digest_still_aborts_before_any_transport_call(self):
        transport = Recorder()
        result = _apply(_run_plan(), GraphQLProjectFieldWriter(transport, _snapshot()),
                        digest=lambda: OTHER)
        self.assertEqual(result.status, "aborted_source_changed")
        self.assertEqual(transport.calls, [])

    def test_digest_moving_mid_update_stops_after_first_write(self):
        transport = Recorder()
        digests = iter([DIGEST, OTHER, OTHER])
        result = _apply(_run_plan(), GraphQLProjectFieldWriter(transport, _snapshot()),
                        digest=lambda: next(digests))
        self.assertEqual(result.status, "aborted_source_changed")
        self.assertEqual(len(transport.calls), 1)

    def test_snapshot_validation_rejects_malformed_input(self):
        def mutate(fn):
            snapshot = _snapshot()
            fn(snapshot)
            return snapshot

        bad = [
            "not a mapping",
            mutate(lambda s: s.update(extra=1)),
            mutate(lambda s: s.update(kind="other")),
            mutate(lambda s: s.update(schema_version="9")),
            mutate(lambda s: s.update(project_id="has space")),
            mutate(lambda s: s.update(fields=[])),
            mutate(lambda s: s.update(fields="x")),
            mutate(lambda s: s["fields"].append(copy.deepcopy(s["fields"][0]))),
            mutate(lambda s: s["fields"][3].update(data_type="iteration")),
            mutate(lambda s: s["fields"][3].update(options=[{"value": "a", "option_id": "O"}])),
            mutate(lambda s: s["fields"][0].update(options=[])),
            mutate(lambda s: s["fields"][0]["options"][0].update(extra=1)),
            mutate(lambda s: s["fields"][0]["options"][0].update(value="Bad Value")),
            mutate(lambda s: s["fields"][0]["options"][0].update(option_id="bad id")),
            mutate(lambda s: s["fields"][0]["options"][1].update(
                value=s["fields"][0]["options"][0]["value"])),
            mutate(lambda s: s["fields"][0]["options"][1].update(
                option_id=s["fields"][0]["options"][0]["option_id"])),
            mutate(lambda s: s["fields"][3].update(field_id=PROJECT)),
            mutate(lambda s: s["fields"][0].pop("options")),
            mutate(lambda s: s.update(fields=[copy.deepcopy(s["fields"][3])] * 65)),
        ]
        for snapshot in bad:
            with self.subTest(snapshot=str(snapshot)[:80]), self.assertRaises(ProjectSchemaError):
                GraphQLProjectFieldWriter(Recorder(), snapshot)
        with self.assertRaises(TypeError):
            GraphQLProjectFieldWriter("not callable", _snapshot())


class ErrorMappingTests(unittest.TestCase):
    def _run(self, **kw):
        transport = Recorder(**kw)
        result = _apply(_run_plan(), GraphQLProjectFieldWriter(transport, _snapshot()))
        return result, transport

    def test_permission_errors_map_to_skipped_unauthorized(self):
        for kind in ("FORBIDDEN", "INSUFFICIENT_SCOPES", "UNAUTHORIZED"):
            with self.subTest(kind=kind):
                result, transport = self._run(response={
                    "data": None,
                    "errors": [{"type": kind, "message": f"token {SECRET} lacks scope"}],
                })
                self.assertEqual(result.status, "skipped_unauthorized")
                self.assertEqual(len(transport.calls), 1)
                self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_other_graphql_errors_map_to_failed_with_class_name_only(self):
        shapes = [
            {"errors": [{"type": "NOT_FOUND", "message": SECRET}]},
            {"errors": [{"message": SECRET}]},
            {"errors": [{"type": ["FORBIDDEN"]}]},
            {"errors": "boom " + SECRET},
            {"errors": [SECRET]},
            {"data": {"updateProjectV2ItemFieldValue": None}},
            {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_other"}}}},
            {"data": {}},
            {},
        ]
        for response in shapes:
            with self.subTest(response=str(response)[:60]):
                result, _ = self._run(response=response)
                self.assertEqual(result.status, "failed")
                self.assertIn("ProjectGraphQLError", result.detail)
                self.assertNotIn(SECRET, json.dumps(result.to_dict()))

    def test_non_mapping_response_fails(self):
        for response in (["x"], "x", 3):
            with self.subTest(response=response):
                result, _ = self._run(response=response)
                self.assertEqual(result.status, "failed")

    def test_transport_exception_is_reported_by_class_name_only(self):
        result, transport = self._run(raises=ConnectionError(f"proxy auth {SECRET}"))
        self.assertEqual(result.status, "failed")
        self.assertIn("ConnectionError", result.detail)
        self.assertNotIn(SECRET, json.dumps(result.to_dict()))
        self.assertEqual(len(transport.calls), 1)  # no retry

    def test_writer_raises_fixed_messages(self):
        writer = GraphQLProjectFieldWriter(
            Recorder(response={"errors": [{"type": "FORBIDDEN", "message": SECRET}]}),
            _snapshot())
        with self.assertRaises(ProjectPermissionError) as ctx:
            writer.update_field(ITEM, "F_note", "x")
        self.assertNotIn(SECRET, str(ctx.exception))
        writer = GraphQLProjectFieldWriter(
            Recorder(response={"errors": [{"message": SECRET}]}), _snapshot())
        with self.assertRaises(ProjectGraphQLError) as ctx:
            writer.update_field(ITEM, "F_note", "x")
        self.assertNotIn(SECRET, str(ctx.exception))


class IdempotenceTests(unittest.TestCase):
    def test_replay_after_converge_is_a_noop_with_no_transport_call(self):
        transport = Recorder()
        writer = GraphQLProjectFieldWriter(transport, _snapshot())
        first = _run_plan()
        self.assertEqual(_apply(first, writer).status, "applied")
        sent = len(transport.calls)
        observed = {d["field_id"]: d["value"] for d in first["desired_fields"]}
        again = _apply(_run_plan(observed), writer)
        self.assertEqual(again.status, "noop")
        self.assertEqual(len(transport.calls), sent)

    def test_mixed_type_plan_writes_each_field_once_in_plan_order(self):
        transport = Recorder()
        plan = _manual_plan([("F_count", "7"), ("F_due", "2026-01-31"), ("F_note", "ok")])
        result = _apply(plan, GraphQLProjectFieldWriter(transport, _snapshot()))
        self.assertEqual(result.applied, ("F_count", "F_due", "F_note"))
        self.assertEqual([c[1]["fieldId"] for c in transport.calls],
                         ["F_count", "F_due", "F_note"])


if __name__ == "__main__":
    unittest.main()
