import unittest

from idkmesh.connector_errors import ConnectorError
from idkmesh.jules_observation import (
    JulesObservationService,
    parse_activity_observation,
    parse_session_observation,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        return self.responses.pop(0)


def _session(state="IN_PROGRESS", **extra):
    payload = {
        "name": "sessions/123",
        "id": "123",
        "state": state,
        "updateTime": "2026-09-23T12:00:00Z",
    }
    payload.update(extra)
    return payload


def _activity(**extra):
    payload = {
        "name": "sessions/123/activities/a1",
        "id": "a1",
        "originator": "agent",
        "createTime": "2026-09-23T12:00:01Z",
    }
    payload.update(extra)
    return payload


class JulesObservationTests(unittest.TestCase):
    def test_completed_maps_only_to_candidate_ready(self):
        observation = parse_session_observation(
            _session("COMPLETED", outputs=[{"pullRequest": {"url": "https://example"}}]),
            expected_session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.run_state, "candidate_ready")
        self.assertEqual(observation.candidate_output_count, 1)
        self.assertNotEqual(observation.run_state, "verified")
        self.assertNotEqual(observation.run_state, "integrated")

    def test_failed_maps_to_failed(self):
        observation = parse_session_observation(
            _session("FAILED"),
            expected_session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.run_state, "failed")

    def test_action_required_states_are_explicit(self):
        expected = {
            "AWAITING_PLAN_APPROVAL": "approve_plan",
            "AWAITING_USER_FEEDBACK": "user_feedback",
            "PAUSED": "inspect_paused_session",
        }
        for state, action in expected.items():
            with self.subTest(state=state):
                observation = parse_session_observation(
                    _session(state),
                    expected_session_name="sessions/123",
                    connection_id="jules-main",
                )
                self.assertEqual(observation.run_state, "waiting_for_agent")
                self.assertEqual(observation.action_required, action)

    def test_unknown_future_state_fails_safe_as_nonterminal_warning(self):
        observation = parse_session_observation(
            _session("SOMETHING_NEW"),
            expected_session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.run_state, "waiting_for_agent")
        self.assertIn("unknown_provider_state", observation.warnings)

    def test_state_unspecified_never_advances_candidate(self):
        observation = parse_session_observation(
            _session("STATE_UNSPECIFIED"),
            expected_session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.run_state, "waiting_for_agent")
        self.assertIn("provider_state_unspecified", observation.warnings)

    def test_non_object_observations_fail_closed(self):
        with self.assertRaises(ConnectorError) as session:
            parse_session_observation(
                [],
                expected_session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(session.exception.code, "result_normalization_error")

        with self.assertRaises(ConnectorError) as activity:
            parse_activity_observation(
                [],
                session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(activity.exception.code, "result_normalization_error")

    def test_wrong_session_identity_fails_closed(self):
        with self.assertRaises(ConnectorError) as caught:
            parse_session_observation(
                _session("IN_PROGRESS", name="sessions/other"),
                expected_session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_session_outputs_must_be_structural_metadata(self):
        with self.assertRaises(ConnectorError) as caught:
            parse_session_observation(
                _session("COMPLETED", outputs=["raw-output"]),
                expected_session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_plan_generated_activity_normalizes_without_message_content(self):
        observation = parse_activity_observation(
            _activity(
                description="Plan generated with sensitive task text",
                planGenerated={"plan": {"id": "plan-1", "steps": []}},
            ),
            session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.event_type, "plan_generated")
        self.assertEqual(observation.plan_id, "plan-1")
        self.assertFalse(hasattr(observation, "description"))

    def test_change_set_artifact_is_counted_without_patch_retention(self):
        observation = parse_activity_observation(
            _activity(
                artifacts=[
                    {
                        "changeSet": {
                            "source": "sources/github/MSKazemi/idkmesh",
                            "gitPatch": {"unidiffPatch": "secret-ish patch body"},
                        }
                    }
                ]
            ),
            session_name="sessions/123",
            connection_id="jules-main",
        )
        self.assertEqual(observation.artifact_count, 1)
        self.assertTrue(observation.has_change_set)
        self.assertFalse(hasattr(observation, "artifacts"))

    def test_multiple_known_event_types_fail_closed(self):
        with self.assertRaises(ConnectorError) as caught:
            parse_activity_observation(
                _activity(
                    planApproved={"planId": "p1"},
                    sessionCompleted={},
                ),
                session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_unknown_originator_fails_closed(self):
        with self.assertRaises(ConnectorError) as caught:
            parse_activity_observation(
                _activity(originator="mystery"),
                session_name="sessions/123",
                connection_id="jules-main",
            )
        self.assertEqual(caught.exception.code, "result_normalization_error")

    def test_list_activities_uses_incremental_filter_and_pagination(self):
        client = FakeClient(
            [
                {
                    "activities": [
                        _activity(progressUpdated={"title": "Tests", "description": "Running"})
                    ],
                    "nextPageToken": "next-token",
                }
            ]
        )
        service = JulesObservationService(client, connection_id="jules-main")
        page = service.list_activities(
            "sessions/123",
            page_size=20,
            page_token="token-1",
            create_time="2026-09-23T12:00:00Z",
        )
        self.assertEqual(page.next_page_token, "next-token")
        self.assertEqual(page.activities[0].event_type, "progress_updated")
        self.assertEqual(
            client.calls,
            [
                (
                    "/sessions/123/activities",
                    {
                        "pageSize": 20,
                        "pageToken": "token-1",
                        "createTime": "2026-09-23T12:00:00Z",
                    },
                )
            ],
        )

    def test_get_session_uses_exact_resource_name(self):
        client = FakeClient([_session("IN_PROGRESS")])
        service = JulesObservationService(client, connection_id="jules-main")
        observation = service.get_session("sessions/123")
        self.assertEqual(observation.provider_state, "IN_PROGRESS")
        self.assertEqual(client.calls, [("/sessions/123", None)])

    def test_invalid_session_or_page_inputs_fail_before_client(self):
        client = FakeClient([])
        service = JulesObservationService(client, connection_id="jules-main")

        for session_name in ("123", "sessions/", "sessions/a/b"):
            with self.subTest(session_name=session_name):
                with self.assertRaises(ConnectorError) as caught:
                    service.get_session(session_name)
                self.assertEqual(caught.exception.code, "configuration_error")

        with self.assertRaisesRegex(ValueError, "page_size"):
            service.list_activities("sessions/123", page_size=0)
        with self.assertRaisesRegex(ValueError, "page_token"):
            service.list_activities("sessions/123", page_token="")
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
