import unittest

from idkmesh.candidate_reference import (
    GitHubPullRequestCandidateReference,
)
from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import GitHubPullRequestResolution
from idkmesh.jules_candidates import JulesPullRequestHint
from idkmesh.jules_lifecycle import (
    JulesLifecycleService,
    JulesLifecycleSnapshot,
)
from idkmesh.jules_observation import JulesSessionObservation
from idkmesh.jules_sessions import (
    JulesSessionHandle,
    JulesSessionRequest,
    ScmRevisionBinding,
)


REVISION = "0123456789abcdef0123456789abcdef01234567"
HEAD = "1123456789abcdef0123456789abcdef01234567"


def _handle():
    return JulesSessionHandle(
        session_name="sessions/123",
        session_id="123",
        work_unit_id="wu-123",
        source_name="sources/github/MSKazemi/idkmesh",
        starting_branch="idkmesh/wu-123",
        requested_source_revision=REVISION,
        revision_binding="scm_pinned_branch",
        require_plan_approval=True,
        automation_mode="AUTO_CREATE_PR",
        repository="MSKazemi/idkmesh",
        state="PLANNING",
        url="https://jules.google/session/123",
    )


def _request():
    return JulesSessionRequest(
        work_unit_id="wu-123",
        prompt="Implement one bounded task.",
        title="IDKMesh wu-123",
        source_name="sources/github/MSKazemi/idkmesh",
        binding=ScmRevisionBinding(
            github_owner="MSKazemi",
            github_repo="idkmesh",
            branch="idkmesh/wu-123",
            revision=REVISION,
            verified=True,
        ),
        automation_mode="AUTO_CREATE_PR",
    )


def _observation(
    *,
    run_state="worker_completed",
    provider_state="COMPLETED",
    session_name="sessions/123",
    session_id="123",
    candidate_output_count=1,
):
    return JulesSessionObservation(
        session_name=session_name,
        session_id=session_id,
        provider_state=provider_state,
        run_state=run_state,
        action_required=None,
        candidate_output_count=candidate_output_count,
        update_time="2026-09-24T00:00:00Z",
    )


def _hint(number=42):
    return JulesPullRequestHint(
        provider="jules",
        session_name="sessions/123",
        repository="MSKazemi/idkmesh",
        pull_request_number=number,
        url=f"https://github.com/MSKazemi/idkmesh/pull/{number}",
    )


def _candidate(number=42):
    return GitHubPullRequestResolution(
        reference=GitHubPullRequestCandidateReference(
            repository="MSKazemi/idkmesh",
            number=number,
            head_sha=HEAD,
        ),
        state="open",
        draft=False,
    )


class FakeCreator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create_session(self, request):
        self.calls.append(request)
        return self.result


class FakeObserver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_session(self, session_name):
        self.calls.append(session_name)
        return self.result


class FakeDiscoverer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def discover_pull_request_hints(self, session):
        self.calls.append(session)
        return self.result


class FakeBinder:
    def __init__(self, results=None, error=None):
        self.results = results or {}
        self.error = error
        self.calls = []

    def resolve_pull_request_hint(self, hint):
        self.calls.append(hint)
        if self.error is not None:
            raise self.error
        return self.results[hint.pull_request_number]


def _service(
    *,
    observation=None,
    hints=(),
    candidates=None,
    binder_error=None,
):
    handle = _handle()
    return (
        JulesLifecycleService(
            session_creator=FakeCreator(handle),
            observer=FakeObserver(
                observation or _observation()
            ),
            discoverer=FakeDiscoverer(hints),
            binder=FakeBinder(
                candidates or {},
                error=binder_error,
            ),
            connection_id="jules-main",
        ),
        handle,
    )


class JulesLifecycleServiceTests(unittest.TestCase):
    def test_start_delegates_only_to_guarded_session_creator(self):
        handle = _handle()
        creator = FakeCreator(handle)
        service = JulesLifecycleService(
            session_creator=creator,
            observer=FakeObserver(_observation()),
            discoverer=FakeDiscoverer(()),
            binder=FakeBinder(),
            connection_id="jules-main",
        )
        request = _request()

        self.assertEqual(service.start(request), handle)
        self.assertEqual(creator.calls, [request])

    def test_waiting_state_never_enters_candidate_discovery(self):
        discoverer = FakeDiscoverer((_hint(),))
        binder = FakeBinder({42: _candidate()})
        service = JulesLifecycleService(
            session_creator=FakeCreator(_handle()),
            observer=FakeObserver(
                _observation(
                    run_state="waiting_for_agent",
                    provider_state="IN_PROGRESS",
                )
            ),
            discoverer=discoverer,
            binder=binder,
            connection_id="jules-main",
        )

        snapshot = service.inspect(_handle())

        self.assertEqual(snapshot.phase, "waiting_for_agent")
        self.assertEqual(snapshot.candidates, ())
        self.assertEqual(discoverer.calls, [])
        self.assertEqual(binder.calls, [])

    def test_failed_state_never_enters_candidate_discovery(self):
        service, handle = _service(
            observation=_observation(
                run_state="failed",
                provider_state="FAILED",
                candidate_output_count=0,
            ),
            hints=(_hint(),),
            candidates={42: _candidate()},
        )
        snapshot = service.inspect(handle)
        self.assertEqual(snapshot.phase, "failed")
        self.assertEqual(snapshot.candidates, ())

    def test_worker_completed_without_hint_stays_worker_completed(self):
        service, handle = _service(
            observation=_observation(candidate_output_count=0),
            hints=(),
        )

        snapshot = service.inspect(handle)

        self.assertEqual(snapshot.phase, "worker_completed")
        self.assertEqual(snapshot.candidate_references, ())
        self.assertIn(
            "worker_completed_without_candidate",
            snapshot.warnings,
        )

    def test_exact_scm_resolution_advances_to_candidate_ready(self):
        hint = _hint()
        candidate = _candidate()
        service, handle = _service(
            hints=(hint,),
            candidates={42: candidate},
        )

        snapshot = service.inspect(handle)

        self.assertEqual(snapshot.phase, "candidate_ready")
        self.assertEqual(snapshot.candidate_hints, (hint,))
        self.assertEqual(snapshot.candidates, (candidate,))
        self.assertEqual(
            snapshot.candidate_references,
            (candidate.reference,),
        )

    def test_multiple_candidates_are_retained_without_selection(self):
        hints = (_hint(42), _hint(43))
        candidates = {
            42: _candidate(42),
            43: _candidate(43),
        }
        service, handle = _service(
            observation=_observation(candidate_output_count=2),
            hints=hints,
            candidates=candidates,
        )

        snapshot = service.inspect(handle)

        self.assertEqual(snapshot.phase, "candidate_ready")
        self.assertEqual(
            tuple(item.reference.number for item in snapshot.candidates),
            (42, 43),
        )
        self.assertFalse(hasattr(snapshot, "selected_candidate"))

    def test_any_binding_failure_prevents_partial_candidate_ready(self):
        service, handle = _service(
            observation=_observation(candidate_output_count=2),
            hints=(_hint(42), _hint(43)),
            binder_error=ConnectorError(
                code="result_normalization_error",
                message="synthetic SCM failure",
                connection_id="jules-main",
            ),
        )

        with self.assertRaises(ConnectorError):
            service.inspect(handle)

    def test_session_observation_must_match_retained_handle(self):
        for observation in (
            _observation(session_name="sessions/other"),
            _observation(session_id="other"),
        ):
            with self.subTest(observation=observation):
                service, handle = _service(
                    observation=observation,
                )
                with self.assertRaisesRegex(
                    ConnectorError,
                    "does not match",
                ):
                    service.inspect(handle)

    def test_hint_must_match_retained_session_identity(self):
        bad_hint = JulesPullRequestHint(
            provider="jules",
            session_name="sessions/other",
            repository="MSKazemi/idkmesh",
            pull_request_number=42,
            url="https://github.com/MSKazemi/idkmesh/pull/42",
        )
        service, handle = _service(
            hints=(bad_hint,),
            candidates={42: _candidate()},
        )
        with self.assertRaisesRegex(
            ConnectorError,
            "does not match",
        ):
            service.inspect(handle)

    def test_duplicate_provider_outputs_are_visible_as_warning(self):
        service, handle = _service(
            observation=_observation(candidate_output_count=2),
            hints=(_hint(),),
            candidates={42: _candidate()},
        )
        snapshot = service.inspect(handle)
        self.assertIn(
            "candidate_output_count_differs_from_unique_hints",
            snapshot.warnings,
        )

    def test_snapshot_has_no_verification_or_integration_authority(self):
        service, handle = _service(
            hints=(_hint(),),
            candidates={42: _candidate()},
        )
        snapshot = service.inspect(handle)
        for field in (
            "verified",
            "accepted",
            "recommendation",
            "merge_authorized",
            "integration_authorized",
            "human_decision",
        ):
            self.assertFalse(hasattr(snapshot, field))

    def test_snapshot_invariants_reject_partial_candidate_ready(self):
        with self.assertRaises(ValueError):
            JulesLifecycleSnapshot(
                session=_handle(),
                observation=_observation(),
                phase="candidate_ready",
                candidate_hints=(_hint(),),
                candidates=(),
            )


class JulesLifecycleCollaboratorContractTests(unittest.TestCase):
    """Malformed collaborator output must fail closed, never degrade quietly."""

    def test_connection_id_must_be_a_non_empty_string(self):
        for connection_id in ("", "   "):
            with self.assertRaises(ValueError):
                JulesLifecycleService(
                    session_creator=FakeCreator(_handle()),
                    observer=FakeObserver(_observation()),
                    discoverer=FakeDiscoverer(()),
                    binder=FakeBinder(),
                    connection_id=connection_id,
                )

    def test_start_rejects_a_non_request_argument(self):
        service, _ = _service()
        with self.assertRaises(ValueError):
            service.start({"work_unit_id": "wu-123"})

    def test_start_rejects_an_unexpected_handle_type(self):
        service = JulesLifecycleService(
            session_creator=FakeCreator({"name": "sessions/123"}),
            observer=FakeObserver(_observation()),
            discoverer=FakeDiscoverer(()),
            binder=FakeBinder(),
            connection_id="jules-main",
        )
        with self.assertRaises(ConnectorError) as raised:
            service.start(_request())
        self.assertEqual(raised.exception.code, "result_normalization_error")

    def test_inspect_rejects_a_non_handle_argument(self):
        service, _ = _service()
        with self.assertRaises(ValueError):
            service.inspect("sessions/123")

    def test_inspect_rejects_an_unexpected_observation_type(self):
        service = JulesLifecycleService(
            session_creator=FakeCreator(_handle()),
            observer=FakeObserver({"run_state": "worker_completed"}),
            discoverer=FakeDiscoverer(()),
            binder=FakeBinder(),
            connection_id="jules-main",
        )
        with self.assertRaises(ConnectorError) as raised:
            service.inspect(_handle())
        self.assertEqual(raised.exception.code, "result_normalization_error")

    def test_inspect_rejects_an_unsupported_run_state(self):
        service = JulesLifecycleService(
            session_creator=FakeCreator(_handle()),
            observer=FakeObserver(
                JulesSessionObservation(
                    session_name="sessions/123",
                    session_id="123",
                    provider_state="COMPLETED",
                    run_state="candidate_ready",
                    action_required=None,
                    candidate_output_count=1,
                    update_time="2026-09-24T00:00:00Z",
                )
            ),
            discoverer=FakeDiscoverer((_hint(),)),
            binder=FakeBinder({42: _candidate()}),
            connection_id="jules-main",
        )
        with self.assertRaises(ConnectorError) as raised:
            service.inspect(_handle())
        self.assertEqual(raised.exception.code, "result_normalization_error")
        self.assertEqual(
            raised.exception.details.get("run_state"),
            "candidate_ready",
        )

    def test_inspect_rejects_malformed_discovery_output(self):
        for hints in ([_hint()], ("sessions/123",), (None,)):
            service, handle = _service(hints=hints)
            with self.assertRaises(ConnectorError) as raised:
                service.inspect(handle)
            self.assertEqual(
                raised.exception.code,
                "result_normalization_error",
            )

    def test_inspect_rejects_an_unexpected_binder_resolution_type(self):
        service, handle = _service(
            hints=(_hint(),),
            candidates={42: {"number": 42}},
        )
        with self.assertRaises(ConnectorError) as raised:
            service.inspect(handle)
        self.assertEqual(
            raised.exception.code,
            "result_normalization_error",
        )

    def test_candidate_references_expose_only_scm_resolved_identity(self):
        service, handle = _service(
            hints=(_hint(), _hint(43)),
            candidates={42: _candidate(), 43: _candidate(43)},
        )
        snapshot = service.inspect(handle)
        self.assertEqual(snapshot.phase, "candidate_ready")
        self.assertEqual(
            [reference.number for reference in snapshot.candidate_references],
            [42, 43],
        )
        for reference in snapshot.candidate_references:
            self.assertIsInstance(
                reference,
                GitHubPullRequestCandidateReference,
            )
            self.assertEqual(reference.head_sha, HEAD)


if __name__ == "__main__":
    unittest.main()
